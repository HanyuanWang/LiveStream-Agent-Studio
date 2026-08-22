param([string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$portableRuntime = Join-Path (Split-Path -Parent $projectDir) '.runtime'
$runtime = if (Test-Path -LiteralPath (Join-Path $portableRuntime 'python\python.exe')) { $portableRuntime } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies' }
$pythonExe = Join-Path $runtime 'python\python.exe'
$nodeExe = if ($runtime -eq $portableRuntime) { Join-Path $runtime 'node\node.exe' } else { Join-Path $runtime 'node\bin\node.exe' }
$modules = if ($runtime -eq $portableRuntime) { Join-Path $runtime 'node\node_modules' } else { Join-Path $runtime 'node\node_modules' }
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = 'python' }
if (-not (Test-Path -LiteralPath $nodeExe)) { $nodeExe = 'node' }
$link = Join-Path $projectDir 'node_modules'
if (-not (Test-Path -LiteralPath $link) -and (Test-Path -LiteralPath $modules)) {
  New-Item -ItemType Junction -Path $link -Target $modules | Out-Null
}
$env:PYTHONPATH = Join-Path $projectDir 'src'
$env:LIVE_RETRO_NODE = $nodeExe
$env:LIVE_RETRO_PORT = '8775'
& $pythonExe -m live_retro_agent.cli $Action
exit $LASTEXITCODE
