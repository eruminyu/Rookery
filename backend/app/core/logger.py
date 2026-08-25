"""
Signal-Recorder: 구조화된 로깅 모듈
표준 logging 모듈 기반. 콘솔 + 파일 동시 출력.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path


class _StderrToLogger:
    """sys.stderr를 로거로 리다이렉트하는 래퍼.

    FFmpeg subprocess 에러, uvicorn 내부 오류 등 stderr로 가는 모든 출력을
    로거를 통해 타임스탬프와 함께 기록한다.

    재진입 방지가 핵심이다. 콘솔 핸들러가 출력에 실패하면 logging은
    handleError()에서 sys.stderr에 쓰는데, 그 stderr가 다시 이 래퍼이므로
    로거 → 핸들러 실패 → stderr → 로거 … 로 무한 재귀에 빠진다.
    (한국어 Windows 콘솔에서 이모지가 섞인 로그를 찍을 때 실제로 발생했다.)
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._buf = ""
        self._local = threading.local()

    def _emit(self, line: str) -> None:
        """로깅 중 재진입이면 원래 stderr로 직접 내보낸다."""
        if getattr(self._local, "busy", False):
            try:
                sys.__stderr__.write(line + "\n")
            except Exception:
                pass
            return

        self._local.busy = True
        try:
            self._logger.error(line)
        except Exception:
            try:
                sys.__stderr__.write(line + "\n")
            except Exception:
                pass
        finally:
            self._local.busy = False

    def write(self, msg: str) -> None:
        self._buf += msg
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._emit(line)

    def flush(self) -> None:
        if self._buf.strip():
            self._emit(self._buf)
        self._buf = ""

    def fileno(self) -> int:  # subprocess 호환성
        return sys.__stderr__.fileno()

    def isatty(self) -> bool:
        try:
            return sys.__stderr__.isatty()
        except Exception:
            return False


def _make_console_handler() -> logging.StreamHandler:
    """콘솔 핸들러를 만든다.

    Windows 기본 콘솔 코드페이지(cp949 등)는 로그에 쓰이는 이모지를
    인코딩하지 못해 UnicodeEncodeError를 낸다. 스트림을 UTF-8로 바꾸고,
    그마저 안 되면 인코딩 불가 문자를 대체 문자로 흘려보낸다.
    """
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # 파이프로 연결된 경우 등 재설정이 불가능하면 그대로 둔다.
            pass

    return logging.StreamHandler(stream)


def setup_logger(
    name: str = "chzzk",
    *,
    level: int = logging.INFO,
    log_dir: str | None = None,
) -> logging.Logger:
    """구조화된 로거를 생성하고 반환한다.

    Args:
        name: 로거 이름.
        level: 로그 레벨.
        log_dir: 로그 파일 저장 디렉토리. None이면 파일 출력 비활성화.
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 있으면 중복 추가 방지
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 핸들러 내부 오류를 stderr로 뱉지 않게 한다 — 위 재진입 문제의 근원이다.
    logging.raiseExceptions = False

    # ── 포맷터 ───────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── 콘솔 핸들러 ─────────────────────────────────────
    console_handler = _make_console_handler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # ── 파일 핸들러 (선택) ───────────────────────────────
    if log_dir:
        from logging.handlers import TimedRotatingFileHandler

        log_path = Path(log_dir)
        if not log_path.is_absolute():
            # 상대 경로인 경우 프로젝트 루트 기준으로 해석
            # backend/app/core/logger.py 기준 상위 3단계가 프로젝트 루트
            project_root = Path(__file__).resolve().parents[3]
            log_path = project_root / log_path

        log_path.mkdir(parents=True, exist_ok=True)

        # service.log 로 통일하고 TimedRotatingFileHandler 적용 (매일 자정 롤링, 7일간 보존)
        file_handler = TimedRotatingFileHandler(
            log_path / "service.log",
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


# ── 기본 로거 인스턴스 ──────────────────────────────────
def _get_default_logger():
    from app.core.config import get_settings
    try:
        settings = get_settings()
        level = logging.DEBUG if settings.debug else logging.INFO
    except Exception:
        level = logging.INFO
    _logger = setup_logger(level=level, log_dir="logs")
    sys.stderr = _StderrToLogger(_logger)  # type: ignore[assignment]
    return _logger

logger = _get_default_logger()
