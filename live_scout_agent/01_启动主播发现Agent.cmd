@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_service.ps1"
if %ERRORLEVEL% EQU 0 exit /b 0
echo.
echo Agent failed to start. Please run the configuration check script.
echo Press any key to close.
pause >nul
