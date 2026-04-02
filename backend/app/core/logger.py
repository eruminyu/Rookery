"""
Signal-Recorder: 구조화된 로깅 모듈
표준 logging 모듈 기반. 콘솔 + 파일 동시 출력.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


class _StderrToLogger:
    """sys.stderr를 로거로 리다이렉트하는 래퍼.

    FFmpeg subprocess 에러, uvicorn 내부 오류 등 stderr로 가는 모든 출력을
    로거를 통해 타임스탬프와 함께 기록한다.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._buf = ""

    def write(self, msg: str) -> None:
        self._buf += msg
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._logger.error(line)

    def flush(self) -> None:
        if self._buf.strip():
            self._logger.error(self._buf)
            self._buf = ""

    def fileno(self) -> int:  # subprocess 호환성
        return sys.__stderr__.fileno()


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

    # ── 포맷터 ───────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── 콘솔 핸들러 ─────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # ── 파일 핸들러 (선택) ───────────────────────────────
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / f"{name}.log",
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
