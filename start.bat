@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SovereignAI Workbench - Launcher

rem --- pick a local Python (repo venv at .venv or backend\.venv) ---
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "backend\.venv\Scripts\python.exe" set "PY=backend\.venv\Scripts\python.exe"

if not defined PY (
    echo.
    echo [SETUP NEEDED] Python environment not found. Run these once:
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r backend\requirements.txt
    echo   cd frontend ^&^& npm install ^&^& cd ..
    echo.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo.
    echo [SETUP NEEDED] Frontend dependencies missing. Run once:
    echo   cd frontend ^&^& npm install ^&^& cd ..
    echo.
    pause
    exit /b 1
)

"%PY%" backend\scripts\launch_app.py
if errorlevel 1 (
    echo.
    echo Launch failed - see messages above.
    pause
)
endlocal
