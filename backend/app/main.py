"""
Signal-Recorder: FastAPI 진입점
Lifespan 컨텍스트 매니저를 통해 Conductor 라이프사이클을 관리한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# NOTE: Windows 이벤트 루프 정책은 app/__init__.py에서 설정됨

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logger import logger
from app.engine.auth import AuthManager
from app.engine.conductor import Conductor
from app.services.recorder import RecorderService
from app.services.discord_bot import DiscordBotService

# API Routers
from app.api.stream import router as stream_router
from app.api.vod import router as vod_router
from app.api.settings import router as settings_router
from app.api.chat import router as chat_router
from app.api.stats import router as stats_router
from app.api.setup import router as setup_router
from app.api.platforms import router as platforms_router
from app.api.archive import router as archive_router
from app.api.tags import router as tags_router
from app.api.events import router as events_router

# ── 전역 인스턴스 ────────────────────────────────────────
_recorder_service: RecorderService | None = None


def get_recorder_service() -> RecorderService:
    """RecorderService 인스턴스를 반환한다. (DI용)"""
    if _recorder_service is None:
        raise RuntimeError("RecorderService가 초기화되지 않았습니다.")
    return _recorder_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 시작/종료 라이프사이클 관리."""
    global _recorder_service

    settings = get_settings()
    logger.info(f"🚀 {settings.app_name} 시작 중...")

    # FFmpeg 경로 검증
    try:
        ffmpeg = settings.resolve_ffmpeg_path()
        logger.info(f"✅ FFmpeg 확인: {ffmpeg}")
    except FileNotFoundError as e:
        logger.warning(f"⚠️ {e}")

    # yt-dlp 경로 검증 (Windows exe 환경에서 없으면 자동 다운로드)
    try:
        ytdlp = settings.resolve_ytdlp_path(auto_download=True)
        logger.info(f"✅ yt-dlp 확인: {ytdlp}")
    except Exception as e:
        logger.warning(f"⚠️ yt-dlp 확인 실패: {e}")

    # 서비스 초기화
    auth = AuthManager()
    conductor = Conductor(auth=auth)
    _recorder_service = RecorderService(conductor=conductor, auth=auth)

    if auth.is_authenticated:
        logger.info("🔑 인증 쿠키 로드 완료.")
    else:
        logger.info("🔓 비로그인 모드로 동작합니다.")

    # Discord Bot 시작 (토큰이 설정되어 있으면 자동 구동)
    discord_bot = DiscordBotService(recorder_service=_recorder_service)
    await discord_bot.start()

    # Conductor와 VodEngine에 Discord Bot 연결 (순환 참조 방지를 위해 나중에 설정)
    conductor._discord_bot = discord_bot
    _recorder_service._vod_engine._discord_bot = discord_bot

    logger.info(f"✅ {settings.app_name} Engine Started!")

    # Conductor 시작 (감시 루프 실행)
    await conductor.start()

    yield

    # ── 종료 ──
    logger.info(f"🛑 {settings.app_name} 종료 중...")
    if discord_bot:
        await discord_bot.stop()
    if conductor:
        await conductor.stop()
    _recorder_service = None
    logger.info("👋 Goodbye!")


# ── 정적 파일 경로 ─────────────────────────────────────────
# PyInstaller onefile → sys._MEIPASS
# PyInstaller onedir  → sys.executable 옆 _internal/app/static
# 일반 실행            → 현재 파일 기준

def _resolve_static_dir() -> Path:
    """PyInstaller 빌드 방식에 관계없이 static 폴더를 찾는다."""
    candidates = []

    # 1) PyInstaller onefile: _MEIPASS 사용
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "app" / "static")

    # 2) PyInstaller onedir: exe 옆 _internal 폴더
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "_internal" / "app" / "static")

    # 3) 일반 실행: 현재 파일 기준
    candidates.append(Path(__file__).resolve().parent / "static")

    for path in candidates:
        if path.exists() and (path / "index.html").exists():
            return path

    # 어디에도 없으면 기본값 반환 (경고는 아래에서 처리)
    return candidates[-1]

STATIC_DIR = _resolve_static_dir()


# ── FastAPI 앱 ───────────────────────────────────────────
app = FastAPI(
    title="Signal-Recorder",
    description="다중 플랫폼 스트리밍 및 VOD 전문 녹화 솔루션",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (개발 환경 프록시 연동용 — 프로덕션에서는 동일 오리진이므로 실질적 영향 없음)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ──────────────────────────────────────────
app.include_router(stream_router)
app.include_router(vod_router)
app.include_router(settings_router)
app.include_router(chat_router)
app.include_router(stats_router)
app.include_router(setup_router)
app.include_router(platforms_router)
app.include_router(archive_router)
app.include_router(tags_router)
app.include_router(events_router)
app.include_router(chat_router)
app.include_router(stats_router)
app.include_router(setup_router)
app.include_router(platforms_router)
app.include_router(archive_router)
app.include_router(tags_router)


# ── 헬스 체크 ────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check_root():
    """헬스 체크 엔드포인트."""
    return {"message": "Signal-Recorder Engine Started"}


@app.get("/health/detail", tags=["Health"])
async def health_check():
    """상세 헬스 체크."""
    settings = get_settings()
    try:
        get_recorder_service()
    except RuntimeError:
        pass

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "authenticated": bool(settings.nid_aut and settings.nid_ses),
    }


# ── 프론트엔드 SPA 서빙 ────────────────────────────────────
# API 라우터 등록 이후에 마운트해야 API가 우선 처리됨
if STATIC_DIR.exists():
    # /assets 등 정적 리소스 서빙
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_spa_root():
        """SPA 루트 페이지 반환."""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_fallback(request: Request, full_path: str):
        """SPA 클라이언트 라우팅 지원 — API 경로가 아닌 모든 요청을 index.html로 반환."""
        # API / health 경로는 404로 반환 (이미 등록된 라우터가 처리)
        if full_path.startswith(("api/", "health", "docs", "openapi")):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(STATIC_DIR / "index.html")
else:
    logger.warning(
        "⚠️  static 폴더를 찾을 수 없습니다. 개발 환경(Vite dev server)으로 동작합니다. "
        "배포 시 'npm run build'를 먼저 실행하세요."
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
