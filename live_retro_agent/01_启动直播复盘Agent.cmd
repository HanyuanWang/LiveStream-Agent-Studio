@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" start
if %ERRORLEVEL% EQU 0 exit /b 0
echo.
echo Agent failed to start. Please run 02_检查直播复盘Agent.cmd.
pause

