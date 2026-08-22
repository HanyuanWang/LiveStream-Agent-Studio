@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" doctor
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/api/status' -TimeoutSec 3; if($r.StatusCode -eq 200){ Write-Host 'background_service: RUNNING' -ForegroundColor Green; exit 0 } } catch {}; Write-Host 'background_service: STOPPED' -ForegroundColor Red; Write-Host 'Run 01_启动主播发现Agent.cmd to start it.'"
echo service_logs: %~dp0workspace\service
echo.
pause
