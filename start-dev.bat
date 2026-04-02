@echo off
chcp 65001 > nul
echo [INFO] Signal-Recorder 개발 서버 시작...

cd /d "%~dp0"

:: 백엔드 (새 창)
start "Backend" cmd /k "call backend\.venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --app-dir backend"

:: 프론트엔드 (새 창)
start "Frontend" cmd /k "cd frontend && npm run dev"

echo [INFO] 백엔드 / 프론트엔드 창이 열렸습니다.
