"""
Signal-Recorder: Settings API Router
시스템 설정 및 인증 쿠키 관리 엔드포인트.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import os
import platform
import string

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logger import logger
from app.core.utils import update_env_file as _update_env_file
from app.services.notifications import KIND_LABELS, NotificationKind

router = APIRouter(prefix="/api/settings", tags=["Settings"])


# ── 요청 스키마 ──────────────────────────────────────────

class CookieUpdateRequest(BaseModel):
    """인증 쿠키 업데이트 요청."""

    nid_aut: str = Field(..., description="NID_AUT 쿠키 값")
    nid_ses: str = Field(..., description="NID_SES 쿠키 값")


class DownloadSettingsUpdateRequest(BaseModel):
    """다운로드 설정 업데이트 요청."""

    keep_download_parts: bool = Field(..., description="VOD 다운로드 중단 시 .part 파일 유지 여부")
    max_record_retries: int = Field(..., ge=0, le=100, description="라이브 녹화 자동 재시도 횟수")


class GeneralSettingsUpdateRequest(BaseModel):
    """일반 설정 업데이트 요청."""

    download_dir: Optional[str] = Field(None, description="녹화 저장 경로")
    monitor_interval: Optional[int] = Field(None, ge=5, le=300, description="감시 주기 (초)")
    live_format: Optional[str] = Field(None, description="라이브 녹화 포맷 (ts, mkv, mp4)")
    recording_quality: Optional[str] = Field(None, description="녹화 품질 (best, 1080p, 720p, 480p)")
    split_download_dirs: Optional[bool] = Field(None, description="분할 저장 경로 사용 여부")
    vod_chzzk_dir: Optional[str] = Field(None, description="치지직 VOD/클립 저장 경로 (빈 문자열=기본 경로 사용)")
    vod_external_dir: Optional[str] = Field(None, description="외부 URL 저장 경로 (빈 문자열=기본 경로 사용)")


class VodSettingsUpdateRequest(BaseModel):
    """VOD 다운로드 설정 업데이트 요청."""

    vod_max_concurrent: Optional[int] = Field(None, ge=1, le=10, description="동시 다운로드 최대 개수")
    vod_default_quality: Optional[str] = Field(None, description="기본 화질 (best, 1080p, 720p, 480p)")
    vod_max_speed: Optional[int] = Field(None, ge=0, le=1000, description="최대 다운로드 속도 (MB/s, 0=무제한)")
    vod_format: Optional[str] = Field(None, description="VOD 다운로드 포맷 (mp4, mkv, ts)")


class ChatSettingsUpdateRequest(BaseModel):
    """채팅 아카이빙 설정 업데이트 요청."""

    chat_archive_enabled: bool = Field(..., description="녹화 시 채팅 자동 아카이빙 여부")


class DiscordSettingsUpdateRequest(BaseModel):
    """Discord Bot 및 알림 설정 업데이트 요청."""

    discord_bot_token: Optional[str] = Field(None, description="Discord Bot 토큰")
    discord_notification_channel_id: Optional[str] = Field(None, description="알림을 보낼 Discord 채널 ID")
    discord_command_user_ids: Optional[str] = Field(None, description="봇 명령어를 실행할 수 있는 사용자 ID (쉼표 구분)")
    discord_command_channel_id: Optional[str] = Field(None, description="봇 명령어를 허용할 채널 ID (미설정 시 알림 채널 사용)")
    discord_webhook_url: Optional[str] = Field(
        None, description="Bot 장애 시 폴백으로 사용할 Discord Webhook URL"
    )
    discord_notify_events: Optional[list[str]] = Field(
        None, description="전송할 알림 종류 목록. 전체 허용은 ['all']"
    )
    discord_mention_events: Optional[list[str]] = Field(
        None, description="멘션을 붙일 알림 종류 목록"
    )
    discord_mention_target: Optional[str] = Field(
        None, description="멘션 대상: @here, @everyone, <@&역할ID>"
    )
    discord_notify_ttl: Optional[int] = Field(
        None, ge=60, le=86400, description="대기 중인 알림의 최대 수명 (초)"
    )


def _csv_to_list(value: Optional[str]) -> list[str]:
    """CSV 설정값을 목록으로 변환한다. 'all'/'none'은 그대로 보존한다."""
    raw = (value or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _list_to_csv(values: Optional[list[str]]) -> str:
    """목록을 CSV 설정값으로 변환한다."""
    if values is None:
        return ""
    return ",".join(v.strip() for v in values if v.strip())


# ── 엔드포인트 ───────────────────────────────────────────

VALID_FORMATS = {"ts", "mp4", "mkv"}
VALID_QUALITIES = {"best", "1080p", "720p", "480p"}


@router.get("", summary="현재 설정 조회")
@router.get("/", include_in_schema=False)
async def get_current_settings():
    """현재 애플리케이션 설정을 조회합니다 (민감정보 마스킹)."""
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "download_dir": settings.download_dir,
        "ffmpeg_path": settings.ffmpeg_path,
        "monitor_interval": settings.monitor_interval,
        "host": settings.host,
        "port": settings.port,
        "authenticated": bool(settings.nid_aut and settings.nid_ses),
        "discord_bot_configured": bool(settings.discord_bot_token),
        "keep_download_parts": settings.keep_download_parts,
        "max_record_retries": settings.max_record_retries,
        "live_format": settings.live_format,
        "vod_format": settings.vod_format,
        "recording_quality": settings.recording_quality,
        # VOD 설정
        "vod_max_concurrent": settings.vod_max_concurrent,
        "vod_default_quality": settings.vod_default_quality,
        "vod_max_speed": settings.vod_max_speed,
        # 채팅 설정
        "chat_archive_enabled": settings.chat_archive_enabled,
        # Discord 설정
        "discord_notification_channel_id": settings.discord_notification_channel_id,
        "discord_command_user_ids": settings.discord_command_user_ids,
        "discord_command_channel_id": settings.discord_command_channel_id,
        # 알림 설정 (Webhook URL은 토큰과 동등한 비밀값이므로 설정 여부만 노출)
        "discord_webhook_configured": bool(settings.discord_webhook_url),
        "discord_notify_events": _csv_to_list(settings.discord_notify_events) or ["all"],
        "discord_mention_events": _csv_to_list(settings.discord_mention_events),
        "discord_mention_target": settings.discord_mention_target,
        "discord_notify_ttl": settings.discord_notify_ttl,
        "notification_kinds": [
            {"value": kind.value, "label": label}
            for kind, label in KIND_LABELS.items()
        ],
        # 분할 저장 경로
        "split_download_dirs": settings.split_download_dirs,
        "vod_chzzk_dir": settings.vod_chzzk_dir,
        "vod_external_dir": settings.vod_external_dir,
        # TwitCasting 인증 (설정 여부만 — 실제 값은 노출 안 함)
        "twitcasting_client_id": "***" if settings.twitcasting_client_id else None,
        "twitcasting_client_secret": None,
        # X Spaces 인증
        "x_cookie_file": settings.x_cookie_file,
    }


@router.put("/download", summary="다운로드/녹화 설정 업데이트")
async def update_download_settings(req: DownloadSettingsUpdateRequest):
    """다운로드 및 녹화 관련 설정을 업데이트합니다."""
    settings = get_settings()
    settings.keep_download_parts = req.keep_download_parts
    settings.max_record_retries = req.max_record_retries

    try:
        _update_env_file({
            "KEEP_DOWNLOAD_PARTS": str(req.keep_download_parts).lower(),
            "MAX_RECORD_RETRIES": str(req.max_record_retries),
        })
    except Exception as e:
        print(f"설정 파일 저장 실패: {e}")

    return {
        "message": "다운로드 설정이 업데이트되었습니다.",
        "settings": {
            "keep_download_parts": settings.keep_download_parts,
            "max_record_retries": settings.max_record_retries,
        },
    }


@router.put("/general", summary="일반 설정 업데이트")
async def update_general_settings(req: GeneralSettingsUpdateRequest):
    """일반 설정(저장 경로, 감시 주기, 포맷, 품질)을 업데이트합니다."""
    settings = get_settings()
    env_updates: dict[str, str] = {}

    # ── download_dir ──
    if req.download_dir is not None:
        dir_path = Path(req.download_dir)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(
                status_code=400,
                detail=f"저장 경로를 생성할 수 없습니다: {e}",
            )
        settings.download_dir = req.download_dir
        env_updates["DOWNLOAD_DIR"] = req.download_dir

    # ── monitor_interval ──
    if req.monitor_interval is not None:
        settings.monitor_interval = req.monitor_interval
        env_updates["MONITOR_INTERVAL"] = str(req.monitor_interval)

    # ── live_format ──
    if req.live_format is not None:
        fmt = req.live_format.lower()
        if fmt not in VALID_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 포맷입니다. 사용 가능: {', '.join(VALID_FORMATS)}",
            )
        settings.live_format = fmt
        env_updates["LIVE_FORMAT"] = fmt

    # ── recording_quality ──
    if req.recording_quality is not None:
        quality = req.recording_quality.lower()
        if quality not in VALID_QUALITIES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 품질입니다. 사용 가능: {', '.join(VALID_QUALITIES)}",
            )
        settings.recording_quality = quality
        env_updates["RECORDING_QUALITY"] = quality

    # ── split_download_dirs ──
    if req.split_download_dirs is not None:
        settings.split_download_dirs = req.split_download_dirs
        env_updates["SPLIT_DOWNLOAD_DIRS"] = str(req.split_download_dirs).lower()

    # ── vod_chzzk_dir ──
    if req.vod_chzzk_dir is not None:
        if req.vod_chzzk_dir:
            try:
                Path(req.vod_chzzk_dir).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"치지직 VOD 저장 경로를 생성할 수 없습니다: {e}",
                )
        settings.vod_chzzk_dir = req.vod_chzzk_dir
        env_updates["VOD_CHZZK_DIR"] = req.vod_chzzk_dir

    # ── vod_external_dir ──
    if req.vod_external_dir is not None:
        if req.vod_external_dir:
            try:
                Path(req.vod_external_dir).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"외부 다운로드 저장 경로를 생성할 수 없습니다: {e}",
                )
        settings.vod_external_dir = req.vod_external_dir
        env_updates["VOD_EXTERNAL_DIR"] = req.vod_external_dir

    # .env 영구 저장
    if env_updates:
        try:
            _update_env_file(env_updates)
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")

    return {
        "message": "설정이 업데이트되었습니다.",
        "settings": {
            "download_dir": settings.download_dir,
            "monitor_interval": settings.monitor_interval,
            "live_format": settings.live_format,
            "recording_quality": settings.recording_quality,
            "split_download_dirs": settings.split_download_dirs,
            "vod_chzzk_dir": settings.vod_chzzk_dir,
            "vod_external_dir": settings.vod_external_dir,
        },
    }


@router.put("/cookies", summary="인증 쿠키 업데이트")
async def update_cookies(req: CookieUpdateRequest):
    """치지직 인증 쿠키(NID_AUT, NID_SES)를 업데이트합니다."""
    from app.main import get_recorder_service

    service = get_recorder_service()
    return service.update_cookies(req.nid_aut, req.nid_ses)


@router.post("/cookies/test", summary="쿠키 유효성 검증")
async def test_cookies():
    """현재 설정된 쿠키로 치지직 API에 접근하여 유효성을 검증합니다."""
    import httpx

    from app.main import get_recorder_service

    service = get_recorder_service()
    auth_status = service.get_auth_status()

    if not auth_status["authenticated"]:
        raise HTTPException(
            status_code=400,
            detail="쿠키가 설정되지 않았습니다. 먼저 쿠키를 입력해주세요.",
        )

    try:
        from app.engine.auth import AuthManager

        auth = AuthManager()
        headers = auth.get_http_headers()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://comm-api.game.naver.com/nng_main/v1/user/getUserStatus",
                headers=headers,
                timeout=10.0,
            )
            data = resp.json()

        if data.get("code") == 200:
            content = data.get("content") or {}
            from app.core.logger import logger as _logger
            _logger.debug(f"getUserStatus content keys: {list(content.keys()) if content else 'empty'}")
            return {
                "valid": True,
                "message": "쿠키 검증 성공! 로그인 상태가 확인되었습니다.",
                "user_status": content,
            }
        else:
            return {
                "valid": False,
                "message": "쿠키가 만료되었거나 유효하지 않습니다.",
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"쿠키 검증 중 오류 발생: {e}",
        )


@router.put("/vod", summary="VOD 다운로드 설정 업데이트")
async def update_vod_settings(req: VodSettingsUpdateRequest):
    """VOD 다운로드 설정을 업데이트합니다."""
    settings = get_settings()
    env_updates: dict[str, str] = {}

    # ── vod_max_concurrent ──
    if req.vod_max_concurrent is not None:
        settings.vod_max_concurrent = req.vod_max_concurrent
        env_updates["VOD_MAX_CONCURRENT"] = str(req.vod_max_concurrent)

    # ── vod_default_quality ──
    if req.vod_default_quality is not None:
        quality = req.vod_default_quality.lower()
        if quality not in VALID_QUALITIES:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 품질입니다. 사용 가능: {', '.join(VALID_QUALITIES)}",
            )
        settings.vod_default_quality = quality
        env_updates["VOD_DEFAULT_QUALITY"] = quality

    # ── vod_max_speed ──
    if req.vod_max_speed is not None:
        settings.vod_max_speed = req.vod_max_speed
        env_updates["VOD_MAX_SPEED"] = str(req.vod_max_speed)

    # ── vod_format ──
    if req.vod_format is not None:
        fmt = req.vod_format.lower()
        if fmt not in VALID_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 포맷입니다. 사용 가능: {', '.join(VALID_FORMATS)}",
            )
        settings.vod_format = fmt
        env_updates["VOD_FORMAT"] = fmt

    # .env 영구 저장
    if env_updates:
        try:
            _update_env_file(env_updates)
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")

    # VodEngine의 세마포어를 업데이트하려면 재시작이 필요
    # 현재는 런타임 중 반영 불가 (재시작 필요 안내)
    return {
        "message": "VOD 설정이 업데이트되었습니다. 일부 설정은 서버 재시작 후 적용됩니다.",
        "settings": {
            "vod_max_concurrent": settings.vod_max_concurrent,
            "vod_default_quality": settings.vod_default_quality,
            "vod_max_speed": settings.vod_max_speed,
            "vod_format": settings.vod_format,
        },
    }


@router.put("/chat", summary="채팅 아카이빙 설정 업데이트")
async def update_chat_settings(req: ChatSettingsUpdateRequest):
    """채팅 아카이빙 설정을 업데이트합니다."""
    settings = get_settings()
    settings.chat_archive_enabled = req.chat_archive_enabled

    try:
        _update_env_file({
            "CHAT_ARCHIVE_ENABLED": str(req.chat_archive_enabled).lower(),
        })
    except Exception as e:
        print(f"설정 파일 저장 실패: {e}")

    return {
        "message": "채팅 아카이빙 설정이 업데이트되었습니다.",
        "settings": {
            "chat_archive_enabled": settings.chat_archive_enabled,
        },
    }


@router.put("/discord", summary="Discord Bot 및 알림 설정 업데이트")
async def update_discord_settings(req: DiscordSettingsUpdateRequest):
    """Discord Bot 및 알림 설정을 업데이트합니다.

    토큰/채널 ID 변경은 재시작 후 적용되지만, 알림 종류·멘션·TTL은
    매 전송 시 설정을 다시 읽으므로 즉시 반영됩니다.
    """
    settings = get_settings()

    updates = {}
    if req.discord_bot_token is not None:
        settings.discord_bot_token = req.discord_bot_token if req.discord_bot_token.strip() else None
        updates["DISCORD_BOT_TOKEN"] = req.discord_bot_token.strip()

    if req.discord_notification_channel_id is not None:
        settings.discord_notification_channel_id = req.discord_notification_channel_id if req.discord_notification_channel_id.strip() else None
        updates["DISCORD_NOTIFICATION_CHANNEL_ID"] = req.discord_notification_channel_id.strip()

    if req.discord_command_user_ids is not None:
        cleaned = ",".join(
            part.strip()
            for part in req.discord_command_user_ids.replace(";", ",").split(",")
            if part.strip()
        )
        settings.discord_command_user_ids = cleaned or None
        updates["DISCORD_COMMAND_USER_IDS"] = cleaned

    if req.discord_command_channel_id is not None:
        settings.discord_command_channel_id = req.discord_command_channel_id.strip() or None
        updates["DISCORD_COMMAND_CHANNEL_ID"] = req.discord_command_channel_id.strip()

    if req.discord_webhook_url is not None:
        url = req.discord_webhook_url.strip()
        if url and not url.startswith("https://"):
            raise HTTPException(
                status_code=400,
                detail="Webhook URL은 https://로 시작해야 합니다.",
            )
        settings.discord_webhook_url = url or None
        updates["DISCORD_WEBHOOK_URL"] = url

    if req.discord_notify_events is not None:
        settings.discord_notify_events = _list_to_csv(req.discord_notify_events) or "none"
        updates["DISCORD_NOTIFY_EVENTS"] = settings.discord_notify_events

    if req.discord_mention_events is not None:
        settings.discord_mention_events = _list_to_csv(req.discord_mention_events)
        updates["DISCORD_MENTION_EVENTS"] = settings.discord_mention_events

    if req.discord_mention_target is not None:
        settings.discord_mention_target = req.discord_mention_target.strip() or "@here"
        updates["DISCORD_MENTION_TARGET"] = settings.discord_mention_target

    if req.discord_notify_ttl is not None:
        settings.discord_notify_ttl = req.discord_notify_ttl
        updates["DISCORD_NOTIFY_TTL"] = str(req.discord_notify_ttl)

    try:
        _update_env_file(updates)
    except Exception as e:
        logger.error(f"설정 파일 저장 실패: {e}")

    return {
        "message": "Discord 설정이 업데이트되었습니다. 토큰/채널 변경은 재시작 후 적용됩니다.",
        "settings": {
            "discord_bot_configured": bool(settings.discord_bot_token),
            "discord_notification_channel_id": settings.discord_notification_channel_id,
            "discord_command_user_ids": settings.discord_command_user_ids,
            "discord_command_channel_id": settings.discord_command_channel_id,
            "discord_webhook_configured": bool(settings.discord_webhook_url),
            "discord_notify_events": _csv_to_list(settings.discord_notify_events) or ["all"],
            "discord_mention_events": _csv_to_list(settings.discord_mention_events),
            "discord_mention_target": settings.discord_mention_target,
            "discord_notify_ttl": settings.discord_notify_ttl,
        },
    }


@router.get("/discord/status", summary="알림 파이프라인 상태 조회")
async def get_notification_status():
    """알림 큐와 전송 채널 상태를 반환합니다 (알림 누락 진단용)."""
    from app.main import get_notification_service

    try:
        service = get_notification_service()
    except RuntimeError:
        return {"available": False, "reason": "알림 서비스가 초기화되지 않았습니다."}

    return {"available": True, **service.get_stats()}


@router.post("/discord/test", summary="테스트 알림 전송")
async def send_test_notification():
    """설정된 알림 채널로 테스트 알림을 발행합니다."""
    from app.main import get_notification_service

    try:
        service = get_notification_service()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="알림 서비스가 초기화되지 않았습니다.")

    if not service.has_transport:
        raise HTTPException(
            status_code=400,
            detail="Discord Bot 토큰+채널 ID 또는 Webhook URL 중 하나는 설정되어야 합니다.",
        )

    service.notify(
        kind=NotificationKind.SYSTEM,
        title="🔔 테스트 알림",
        description="알림 파이프라인이 정상 동작합니다.",
        color="green",
        fields={"발신": "설정 페이지"},
    )
    return {"message": "테스트 알림을 큐에 넣었습니다. Discord 채널을 확인하세요."}


@router.get("/browse-dirs", summary="디렉토리 탐색")
async def browse_dirs(
    path: str = Query("", description="탐색할 디렉토리 경로. 비어있으면 드라이브 루트 목록 반환"),
):
    """서버 파일시스템의 디렉토리 목록을 반환합니다.

    - path가 비어있으면: Windows 드라이브 루트 목록 반환 (C:\\, D:\\ 등)
    - path가 주어지면: 해당 경로의 하위 폴더 목록 반환
    """
    if not path:
        if platform.system() == "Windows":
            drives = [
                f"{c}:\\"
                for c in string.ascii_uppercase
                if os.path.exists(f"{c}:\\")
            ]
            return {
                "current": "",
                "parent": None,
                "dirs": [{"name": d, "path": d} for d in drives],
            }
        else:
            # Linux/Docker: 가상 파일시스템 제외하고 실제 디렉토리만 탐색
            SKIP_DIRS = {"/proc", "/sys", "/dev", "/run", "/snap"}
            root = Path("/")
            dirs = []
            try:
                for entry in sorted(root.iterdir()):
                    if not entry.is_dir() or str(entry) in SKIP_DIRS:
                        continue
                    dirs.append({"name": entry.name, "path": str(entry)})
            except OSError:
                pass
            return {"current": "/", "parent": None, "dirs": dirs}

    target = Path(path).resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"디렉토리를 찾을 수 없습니다: {path}")

    # 상위 경로 계산:
    # Windows 드라이브 루트(C:\): parent가 자기 자신 → None 처리
    if target.parent == target:
        # 이미 드라이브 루트
        parent_path = None
    else:
        parent_path = str(target.parent)

    # 하위 폴더 목록 (접근 불가 폴더 스킵)
    sub_dirs = []
    try:
        for entry in sorted(target.iterdir()):
            if not entry.is_dir():
                continue
            sub_dirs.append({"name": entry.name, "path": str(entry)})
    except OSError:
        pass

    return {
        "current": str(target),
        "parent": parent_path,
        "dirs": sub_dirs,
    }


@router.get("/auth", summary="인증 상태 확인")
async def get_auth_status():
    """현재 인증 상태를 확인합니다."""
    from app.main import get_recorder_service

    service = get_recorder_service()
    return service.get_auth_status()


@router.get("/cookie-status", summary="X 쿠키 유효성 상태 조회")
async def get_cookie_status():
    """X Spaces 쿠키의 유효성 상태를 반환합니다.

    쿠키는 하루 1회 자동 검증되며, 이 엔드포인트는 가장 최근 검증 결과를 반환합니다.
    프론트엔드 Settings 페이지 만료 배너에 사용됩니다.
    """
    from app.main import get_recorder_service

    service = get_recorder_service()
    conductor = service._conductor
    return {"x": conductor.get_cookie_status()}


@router.post("/cookie-status/check", summary="X 쿠키 즉시 검증")
async def check_cookie_now():
    """X Spaces 쿠키를 즉시 검증합니다 (24시간 주기 무시)."""
    from app.main import get_recorder_service

    service = get_recorder_service()
    conductor = service._conductor
    await conductor._check_x_cookie()
    return {"x": conductor.get_cookie_status()}
