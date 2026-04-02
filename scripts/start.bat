@echo off
echo [INFO] Starting Signal-Recorder...

cd /d "%~dp0\.."

echo [INFO] Activating virtual environment...
call backend\.venv\Scripts\activate.bat

echo [INFO] Launching Backend Server...
python -m uvicorn app.main:app --reload --app-dir backend

pause
