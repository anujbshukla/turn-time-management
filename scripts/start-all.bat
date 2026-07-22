@echo off
setlocal

cd /d "%~dp0.."

echo Starting PostgreSQL...
docker compose up -d

if errorlevel 1 (
    echo Docker services could not be started.
    echo Make sure Docker Desktop is running.
    pause
    exit /b 1
)

echo Starting FastAPI backend...
start "Turn Time Backend" cmd /k "%~dp0start-backend.bat"

timeout /t 3 /nobreak > nul

echo Starting React frontend...
start "Turn Time Frontend" cmd /k "%~dp0start-frontend.bat"

echo.
echo Turn Time Management services are starting.
echo Backend: http://127.0.0.1:8000
echo API Docs: http://127.0.0.1:8000/docs
echo Frontend: check the frontend terminal for the Vite URL.
echo.

endlocal