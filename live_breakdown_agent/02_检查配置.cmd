@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" doctor
echo.
echo SET 表示已填写，MISSING 表示还缺少。
pause

