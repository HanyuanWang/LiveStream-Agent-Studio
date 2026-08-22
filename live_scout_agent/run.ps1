$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$portablePython = Join-Path (Split-Path -Parent $projectDir) '.runtime\python\python.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonExe = if (Test-Path -LiteralPath $portablePython) { $portablePython } elseif (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { 'python' }
$env:PYTHONPATH = Join-Path $projectDir 'src'
& $pythonExe -m live_scout_agent.cli @args
exit $LASTEXITCODE
