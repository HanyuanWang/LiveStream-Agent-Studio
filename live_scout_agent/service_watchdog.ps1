$ErrorActionPreference = 'Continue'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serviceDir = Join-Path $projectDir 'workspace\service'
$stopPath = Join-Path $serviceDir 'stop.request'
$watchdogPidPath = Join-Path $serviceDir 'watchdog.pid'
$serverPidPath = Join-Path $serviceDir 'server.pid'
$watchdogLogPath = Join-Path $serviceDir 'watchdog.log'
$portablePython = Join-Path (Split-Path -Parent $projectDir) '.runtime\python\python.exe'
$portablePythonW = Join-Path (Split-Path -Parent $projectDir) '.runtime\python\pythonw.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$bundledPythonW = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe'
# The web service has no interactive console.  Using python.exe can make
# Windows Terminal display an empty black window even though the service is
# healthy; pythonw.exe keeps it fully in the background.
$pythonExe = if (Test-Path -LiteralPath $portablePythonW) {
    $portablePythonW
} elseif (Test-Path -LiteralPath $portablePython) {
    $portablePython
} elseif (Test-Path -LiteralPath $bundledPythonW) {
    $bundledPythonW
} elseif (Test-Path -LiteralPath $bundledPython) {
    $bundledPython
} else {
    'pythonw'
}

New-Item -ItemType Directory -Path $serviceDir -Force | Out-Null
$mutex = New-Object System.Threading.Mutex($false, 'LiveScoutAgentWatchdog_8765')
$ownsMutex = $false

try {
    $ownsMutex = $mutex.WaitOne(0)
    if (-not $ownsMutex) {
        exit 0
    }

    Set-Content -LiteralPath $watchdogPidPath -Value $PID -Encoding ascii
    Add-Content -LiteralPath $watchdogLogPath -Encoding utf8 -Value (
        '[{0}] watchdog started, pid={1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $PID
    )

    # Some desktop hosts pass both `Path` and `PATH`. PowerShell Start-Process
    # treats them as duplicate dictionary keys and then loops without ever
    # starting the service. Collapse them to one process-level variable.
    $inheritedPath = if ($env:Path) { $env:Path } else { $env:PATH }
    [System.Environment]::SetEnvironmentVariable('Path', $null, 'Process')
    [System.Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
    [System.Environment]::SetEnvironmentVariable('Path', $inheritedPath, 'Process')
    $env:PYTHONPATH = Join-Path $projectDir 'src'
    while (-not (Test-Path -LiteralPath $stopPath)) {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $stdoutPath = Join-Path $serviceDir ('server_{0}.out.log' -f $stamp)
        $stderrPath = Join-Path $serviceDir ('server_{0}.err.log' -f $stamp)
        try {
            $server = Start-Process `
                -FilePath $pythonExe `
                -ArgumentList @('-m', 'live_scout_agent.cli', 'start', '--no-browser') `
                -WorkingDirectory $projectDir `
                -WindowStyle Hidden `
                -RedirectStandardOutput $stdoutPath `
                -RedirectStandardError $stderrPath `
                -PassThru
            Set-Content -LiteralPath $serverPidPath -Value $server.Id -Encoding ascii
            Add-Content -LiteralPath $watchdogLogPath -Encoding utf8 -Value (
                '[{0}] server started, pid={1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $server.Id
            )
            $server.WaitForExit()
            Add-Content -LiteralPath $watchdogLogPath -Encoding utf8 -Value (
                '[{0}] server exited, code={1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $server.ExitCode
            )
        }
        catch {
            Add-Content -LiteralPath $watchdogLogPath -Encoding utf8 -Value (
                '[{0}] server launch failed: {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $_.Exception.Message
            )
        }
        finally {
            Remove-Item -LiteralPath $serverPidPath -Force -ErrorAction SilentlyContinue
        }

        if (-not (Test-Path -LiteralPath $stopPath)) {
            Start-Sleep -Seconds 3
        }
    }
}
finally {
    if ($ownsMutex) {
        Remove-Item -LiteralPath $serverPidPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $watchdogPidPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
        Add-Content -LiteralPath $watchdogLogPath -Encoding utf8 -Value (
            '[{0}] watchdog stopped' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        )
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
