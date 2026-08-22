@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_service.ps1"
timeout /t 2 /nobreak >nul
