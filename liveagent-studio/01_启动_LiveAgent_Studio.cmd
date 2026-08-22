@echo off
title LiveAgent Studio Launcher
echo.
echo ================================================
echo   LiveAgent Studio is starting. Please wait.
echo ================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0\01_启动_LiveAgent_Studio.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [START FAILED] Exit code: %EXIT_CODE%
  echo Please capture this window and send it to Codex.
  echo.
  pause
)
