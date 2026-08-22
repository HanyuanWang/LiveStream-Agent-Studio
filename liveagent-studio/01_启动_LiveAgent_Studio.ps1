$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$codexRoot = Split-Path -Parent $studioRoot
$portableRuntime = Join-Path $codexRoot '.runtime'
$codexRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
if (Test-Path -LiteralPath (Join-Path $portableRuntime 'python\python.exe')) {
  $runtimeRoot = $portableRuntime
  $pythonExe = Join-Path $runtimeRoot 'python\python.exe'
  $nodeBin = Join-Path $runtimeRoot 'node'
  $fallbackBin = $nodeBin
}
else {
  $runtimeRoot = $codexRuntime
  $pythonExe = Join-Path $runtimeRoot 'python\python.exe'
  $nodeBin = Join-Path $runtimeRoot 'node\bin'
  $fallbackBin = Join-Path $runtimeRoot 'bin\fallback'
}
$env:PATH = "$nodeBin;$fallbackBin;$env:PATH"

function Test-StudioPort([int]$Port) {
  # Get-NetTCPConnection may require elevated permission on some Windows
  # installations. A normal user can still verify the local service by making
  # a short loopback TCP connection, which is all the launcher needs here.
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $result = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    if (-not $result.AsyncWaitHandle.WaitOne(500, $false)) { return $false }
    $client.EndConnect($result)
    return $true
  }
  catch {
    return $false
  }
  finally {
    $client.Close()
  }
}

Write-Host '[1/5] Checking local runtime...' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Python runtime not found: $pythonExe" }
if (-not (Test-Path -LiteralPath (Join-Path $nodeBin 'node.exe'))) { throw "Web runtime not found: $nodeBin" }

# The Video Director Agent reads only user-provided video links and transcribes
# their audio. Install the link parser once on first launch.
& $pythonExe -c "import yt_dlp, playwright, oss2" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host '[setup] Installing short-video link parser...' -ForegroundColor Cyan
  & $pythonExe -m pip install -r (Join-Path $studioRoot 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Could not install the short-video link parser. Check the network and restart Studio.' }
}

if (-not (Test-StudioPort 8765)) {
  Write-Host '[2/5] Starting Creator Scout Agent...' -ForegroundColor Cyan
  $watchdog = Join-Path $codexRoot 'live_scout_agent\service_watchdog.ps1'
  Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $watchdog) -WorkingDirectory (Join-Path $codexRoot 'live_scout_agent') -WindowStyle Hidden
}

if (-not (Test-StudioPort 8775)) {
  Write-Host '[3/5] Starting Live Review Agent...' -ForegroundColor Cyan
  $reviewRoot = Join-Path $codexRoot 'live_retro_agent'
  $env:PYTHONPATH = Join-Path $reviewRoot 'src'
  $env:LIVE_RETRO_NODE = Join-Path $nodeBin 'node.exe'
  Start-Process -FilePath $pythonExe -ArgumentList @('-m','live_retro_agent.server') -WorkingDirectory $reviewRoot -WindowStyle Hidden
}

if (-not (Test-StudioPort 8785)) {
  Write-Host '[4/5] Starting local processing service...' -ForegroundColor Cyan
  Start-Process -FilePath $pythonExe -ArgumentList @((Join-Path $studioRoot 'local_gateway.py')) -WorkingDirectory $studioRoot -WindowStyle Hidden
}

if (-not (Test-StudioPort 4173)) {
  Write-Host '[5/5] Starting LiveAgent Studio page...' -ForegroundColor Cyan
  $webScript = Join-Path $studioRoot 'start_web.ps1'
  Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $webScript) -WorkingDirectory $studioRoot -WindowStyle Hidden
}

for ($index = 0; $index -lt 60; $index++) {
  if ((Test-StudioPort 4173) -and (Test-StudioPort 8785)) { break }
  Start-Sleep -Milliseconds 300
}

if (-not (Test-StudioPort 4173)) { throw 'LiveAgent Studio web page did not start (port 4173).' }
if (-not (Test-StudioPort 8785)) { throw 'Local processing service did not start (port 8785).' }

Write-Host ''
Write-Host 'LiveAgent Studio is ready. Opening the page...' -ForegroundColor Green
# Add a harmless cache-busting query so an already-open browser tab cannot
# keep showing an older frontend bundle after Studio has been upgraded.
$refreshToken = [DateTimeOffset]::Now.ToUnixTimeSeconds()
$studioUrl = "http://127.0.0.1:4173/?refresh=$refreshToken"
try {
  Start-Process $studioUrl
}
catch {
  try {
    Start-Process -FilePath 'explorer.exe' -ArgumentList $studioUrl
  }
  catch {
    # The services are already ready. Do not turn a browser-association issue
    # into a launcher failure; show the exact address for manual opening.
    Write-Host "Could not open the browser automatically. Open this address: $studioUrl" -ForegroundColor Yellow
  }
}
