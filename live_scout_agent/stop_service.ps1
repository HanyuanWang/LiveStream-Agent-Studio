$ErrorActionPreference = 'Continue'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serviceDir = Join-Path $projectDir 'workspace\service'
$stopPath = Join-Path $serviceDir 'stop.request'
$serverPidPath = Join-Path $serviceDir 'server.pid'
$watchdogPidPath = Join-Path $serviceDir 'watchdog.pid'

New-Item -ItemType Directory -Path $serviceDir -Force | Out-Null
Set-Content -LiteralPath $stopPath -Value (Get-Date -Format o) -Encoding utf8

foreach ($pidPath in @($serverPidPath, $watchdogPidPath)) {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        continue
    }
    $processId = Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($processId -match '^\d+$') {
        Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
    }
}

$watchdogPattern = (
    '(?i)-File\s+"?{0}"?\s*$' -f
    [regex]::Escape((Join-Path $projectDir 'service_watchdog.ps1'))
)
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match $watchdogPattern } |
    ForEach-Object {
        Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction SilentlyContinue
    }

# PID文件可能因旧版本看门狗异常清理而丢失。端口监听进程是本Agent的最终事实来源。
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener -and $listener.OwningProcess) {
    $listenerProcess = Get-CimInstance Win32_Process -Filter (
        'ProcessId={0}' -f [int]$listener.OwningProcess
    ) -ErrorAction SilentlyContinue
    if (
        $listenerProcess -and
        $listenerProcess.Name -eq 'python.exe' -and
        $listenerProcess.CommandLine -match 'live_scout_agent\.cli'
    ) {
        Stop-Process -Id ([int]$listener.OwningProcess) -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1
Remove-Item -LiteralPath $serverPidPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $watchdogPidPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
Write-Host 'Live Scout Agent stopped.'
