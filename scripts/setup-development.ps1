$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$studio = Join-Path $root 'liveagent-studio'

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $python) { throw '需要 Python 3.11 或更高版本：https://www.python.org/downloads/windows/' }
if (-not $node) { throw '需要 Node.js 22.13 或更高版本：https://nodejs.org/' }

& $python -m pip install -r (Join-Path $root 'requirements-windows.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败。' }

Push-Location $studio
try {
  & npm.cmd ci
  if ($LASTEXITCODE -ne 0) { throw '网页依赖安装失败。' }
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw '网页构建失败。' }
}
finally { Pop-Location }

Write-Host '开发环境已准备完成。' -ForegroundColor Green

