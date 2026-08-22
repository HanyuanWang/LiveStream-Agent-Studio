@echo off
setlocal
chcp 65001 >nul
title Live Breakdown Agent Status
cd /d "%~dp0"
set "PYEXE=%~dp0..\.runtime\python\python.exe"
if not exist "%PYEXE%" set "PYEXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

if "%~1"=="" (
  "%PYEXE%" "%~dp0process_video_with_status.py" --missing-video
  if "%LIVE_AGENT_NO_PAUSE%"=="1" exit /b 1
  pause
  exit /b 1
)

echo ============================================================
echo Live Breakdown Agent
echo Video: %~f1
echo Status: starting; this window will remain open
echo ============================================================
echo.

"%PYEXE%" "%~dp0process_video_with_status.py" "%~f1"
set "AGENT_EXIT=%ERRORLEVEL%"

echo.
if "%AGENT_EXIT%"=="0" (
  echo COMPLETED. See workspace\output.
) else (
  echo FAILED. See workspace\logs\latest.log.
)
echo.
if "%LIVE_AGENT_NO_PAUSE%"=="1" exit /b %AGENT_EXIT%
pause
exit /b %AGENT_EXIT%
