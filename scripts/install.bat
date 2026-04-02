@echo off
echo [INFO] Installing Signal-Recorder Dependencies...

cd /d "%~dp0\.."

REM Backend Setup
if not exist "backend\.venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv backend\.venv
)

echo [INFO] Activating virtual environment...
call backend\.venv\Scripts\activate.bat

echo [INFO] Installing backend requirements...
pip install -r backend\requirements.txt

echo [SUCCESS] Installation Complete!
pause
