# -*- mode: python ; coding: utf-8 -*-
# Rookery PyInstaller 빌드 스펙 (onefile 방식)
# 사용법: pyinstaller rookery.spec --clean

import certifi
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── 숨겨진 임포트 (자동 탐지가 안 되는 모듈) ─────────────────
hidden_imports = [
    *collect_submodules("uvicorn"),
    *collect_submodules("fastapi"),
    *collect_submodules("app"),
    # UI 트레이
    "pystray",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    # 비동기 / HTTP
    *collect_submodules("aiofiles"),
    "aiofiles",
    "aiofiles.os",
    "aiofiles.threadpool",
    *collect_submodules("aiohttp"),
    "aiohttp",
    "websockets",
    # FastAPI 의존
    "multipart",
    "python_multipart",
    "email.mime.text",
    "email.mime.multipart",
    # pydantic / settings
    "pydantic",
    "pydantic.v1",
    "pydantic_settings",
    "pydantic_core",
    "pydantic_core._pydantic_core",
    # chzzkpy
    "chzzkpy",
    # discord
    "discord",
    "discord.ext.commands",
    # yt-dlp
    "yt_dlp",
    # dotenv
    "dotenv",
    # ssl
    "certifi",
]

# ── 데이터 파일 ───────────────────────────────────────────────
datas = [
    # 빌드된 프론트엔드 정적 파일
    ("backend/app/static", "app/static"),
    # 앱 아이콘
    ("assets/icon.png", "assets"),
    # SSL 인증서 번들 (certifi)
    (certifi.where(), "certifi"),
]

# ── 외부 바이너리: ffmpeg는 라이선스 문제로 번들하지 않음 ──────
# 사용자가 bin/ffmpeg.exe에 넣거나 시스템 PATH에 설치해야 함.
# run.py의 _run_dependency_check()가 시작 시 자동 감지 및 안내함.
binaries = []

a = Analysis(
    ["backend/run.py"],
    pathex=["backend"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest", "pytest", "setuptools"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Rookery",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # 의존성 감지 안내 때 CMD 창이 필요하므로 True
    icon="assets/icon.ico", # Windows 아이콘
)
