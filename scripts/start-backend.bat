@echo off
setlocal

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
    echo Backend virtual environment was not found.
    echo Expected: backend\.venv
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Starting FastAPI backend...
python -m uvicorn app.main:app --reload --port 8000

endlocal