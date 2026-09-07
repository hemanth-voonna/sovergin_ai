@echo off
setlocal
cd /d "%~dp0"
title SovereignAI Workbench - Stop
echo Stopping SovereignAI Workbench dev servers (ports 8000 and 5173)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
echo Done. You can close this window.
timeout /t 3 /nobreak >nul
endlocal
