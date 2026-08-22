$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serviceDir = Join-Path $projectDir 'workspace\service'
$stopPath = Join-Path $serviceDir 'stop.request'
$watchdogScript = Join-Path $projectDir 'service_watchdog.ps1'
$url = 'http://127.0.0.1:8765/'
$statusUrl = 'http://127.0.0.1:8765/api/status'

New-Item -ItemType Directory -Path $serviceDir -Force | Out-Null

function Test-AgentReady {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $statusUrl -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (Test-AgentReady) {
    Start-Process $url
    exit 0
}

Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
Start-Process `
    -FilePath 'powershell.exe' `
    -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $watchdogScript)
    ) `
    -WorkingDirectory $projectDir `
    -WindowStyle Hidden

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-AgentReady) {
        Start-Process $url
        exit 0
    }
}

Write-Host 'Live Scout Agent startup timed out.'
Write-Host ('Please inspect logs in: {0}' -f $serviceDir)
exit 1
