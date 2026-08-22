$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$codexRoot = Split-Path -Parent $studioRoot
$portableRuntime = Join-Path $codexRoot '.runtime'
if (Test-Path -LiteralPath (Join-Path $portableRuntime 'node\node.exe')) {
  $nodeBin = Join-Path $portableRuntime 'node'
  $fallbackBin = $nodeBin
}
else {
  $runtimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
  $nodeBin = Join-Path $runtimeRoot 'node\bin'
  $fallbackBin = Join-Path $runtimeRoot 'bin\fallback'
}
$env:PATH = "$nodeBin;$fallbackBin;$env:PATH"
Set-Location -LiteralPath $studioRoot
$env:WRANGLER_LOG_PATH = '.wrangler/wrangler.log'
$vinextExe = Join-Path $studioRoot 'node_modules\.bin\vinext.cmd'
if (-not (Test-Path -LiteralPath $vinextExe)) { throw "Studio web program not found: $vinextExe" }
& $vinextExe start --host 127.0.0.1 --port 4173
