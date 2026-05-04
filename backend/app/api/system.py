"""
Signal-Recorder: System API (시스템 및 업데이트 관리)
"""

import sys
from pathlib import Path
from fastapi import APIRouter

from app.main import get_updater_service

router = APIRouter(prefix="/api/system", tags=["System"])

def _detect_environment() -> str:
    """현재 실행 환경을 감지한다."""
    # 1. PyInstaller (Windows EXE 등)
    if getattr(sys, "frozen", False):
        return "windows-exe"
    
    # 2. Docker
    if Path("/.dockerenv").exists():
        return "docker"
        
    # 3. 그 외 (Linux Native / 개발환경 등)
    return "linux-native"

@router.get("/update")
async def get_update_status():
    """업데이트 상태 및 환경 정보를 반환한다."""
    updater = get_updater_service()
    info = updater.get_cached_info()
    
    # 환경 정보 추가
    info["environment"] = _detect_environment()
    
    return info

@router.post("/update/check")
async def check_update_now():
    """강제로 업데이트를 즉시 확인한다."""
    updater = get_updater_service()
    info = await updater.check_update_now()
    
    # 환경 정보 추가
    info["environment"] = _detect_environment()
    
    return info
