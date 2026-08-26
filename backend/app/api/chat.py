"""
Rookery: Chat Logs API Router
채팅 아카이빙 로그 파일 목록 조회, 메시지 조회, 다운로드 엔드포인트.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── 유틸 ─────────────────────────────────────────────────

def _encode_file_id(relative_path: str) -> str:
    """상대 경로를 URL-safe Base64로 인코딩한다."""
    return base64.urlsafe_b64encode(
        relative_path.encode("utf-8")
    ).decode().rstrip("=")


def _decode_file_id(file_id: str) -> str:
    """URL-safe Base64 file_id를 상대 경로로 디코딩한다."""
    padding = 4 - len(file_id) % 4
    if padding != 4:
        file_id += "=" * padding
    return base64.urlsafe_b64decode(file_id).decode("utf-8")


def _resolve_and_validate(file_id: str) -> Path:
    """file_id를 절대 경로로 변환하고 base_dir 하위인지 검증한다."""
    settings = get_settings()
    base_dir = Path(settings.download_dir).resolve()

    try:
        relative = _decode_file_id(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="유효하지 않은 file_id입니다.")

    full_path = (base_dir / relative).resolve()

    # 경로 탈출 공격 방지
    if not full_path.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="접근이 허용되지 않는 경로입니다.")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return full_path


# ── 응답 스키마 ──────────────────────────────────────────

class ChatLogFile(BaseModel):
    """채팅 로그 파일 정보."""

    file_id: str
    filename: str
    channel: str
    size_bytes: int
    message_count: int
    created_at: str
    modified_at: str


class ChatMessageItem(BaseModel):
    """채팅 메시지 단건."""

    timestamp: str
    user_id: Optional[str]
    nickname: str
    message: str


class MessagesResponse(BaseModel):
    """페이지네이션 채팅 메시지 응답."""

    messages: list[ChatMessageItem]
    total: int
    page: int
    limit: int
    has_next: bool


# ── 엔드포인트 ───────────────────────────────────────────

@router.get("/files", response_model=list[ChatLogFile], summary="채팅 로그 파일 목록")
async def list_chat_files():
    """download_dir 하위의 모든 .jsonl 파일 목록을 반환합니다."""
    settings = get_settings()
    base_dir = Path(settings.download_dir).resolve()

    if not base_dir.exists():
        return []

    result: list[dict] = []
    for file in base_dir.glob("**/*.jsonl"):
        try:
            stat = file.stat()
            relative = str(file.relative_to(base_dir))
            file_id = _encode_file_id(relative)

            # 줄 수 카운트 = 메시지 수
            with open(file, "rb") as f:
                message_count = sum(1 for line in f if line.strip())

            result.append({
                "file_id": file_id,
                "filename": file.name,
                "channel": file.parent.name,
                "size_bytes": stat.st_size,
                "message_count": message_count,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except Exception:
            continue  # 손상된 파일 스킵

    result.sort(key=lambda x: x["modified_at"], reverse=True)
    return result


@router.get(
    "/files/{file_id}/messages",
    response_model=MessagesResponse,
    summary="채팅 메시지 조회",
)
async def get_chat_messages(
    file_id: str,
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(100, ge=1, le=500, description="페이지당 메시지 수"),
    search: Optional[str] = Query(None, description="메시지 내용 키워드 필터"),
    nickname: Optional[str] = Query(None, description="닉네임 필터"),
):
    """특정 JSONL 파일의 채팅 메시지를 페이지네이션으로 반환합니다."""
    file_path = _resolve_and_validate(file_id)

    messages: list[dict] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                # profile 키는 레거시 데이터 호환용으로 읽되, 응답에는 포함하지 않음
                messages.append({
                    "timestamp": raw.get("timestamp", ""),
                    "user_id": raw.get("user_id"),
                    "nickname": raw.get("nickname", "Unknown"),
                    "message": raw.get("message", ""),
                })
            except json.JSONDecodeError:
                continue

    # 필터 적용
    if nickname:
        nick_lower = nickname.lower()
        messages = [m for m in messages if nick_lower in m.get("nickname", "").lower()]
    if search:
        search_lower = search.lower()
        messages = [m for m in messages if search_lower in m.get("message", "").lower()]

    total = len(messages)
    start = (page - 1) * limit
    end = start + limit
    page_messages = messages[start:end]

    return {
        "messages": page_messages,
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": end < total,
    }


@router.get("/files/{file_id}/download", summary="채팅 로그 파일 다운로드")
async def download_chat_file(file_id: str):
    """JSONL 파일을 직접 다운로드합니다."""
    file_path = _resolve_and_validate(file_id)

    return FileResponse(
        path=str(file_path),
        media_type="application/jsonlines+json",
        filename=file_path.name,
    )
