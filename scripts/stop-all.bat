@echo off
setlocal

cd /d "%~dp0.."

echo Stopping PostgreSQL container...
docker compose stop

echo.
echo PostgreSQL stopped.
echo Close the backend and frontend terminal windows separately.
echo.

pause
endlocal