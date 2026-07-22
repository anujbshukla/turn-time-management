@echo off
setlocal

cd /d "%~dp0..\frontend"

if not exist "package.json" (
    echo Frontend package.json was not found.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install

    if errorlevel 1 (
        echo Frontend dependency installation failed.
        pause
        exit /b 1
    )
)

echo Starting React frontend...
call npm run dev

endlocal