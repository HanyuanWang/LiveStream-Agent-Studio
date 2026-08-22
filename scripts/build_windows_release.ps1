param([string]$OutputDirectory = "")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$artifacts = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $root 'artifacts' }
$stage = Join-Path $artifacts 'LiveAgent-Studio-Windows-x64'
$zip = Join-Path $artifacts 'LiveAgent-Studio-Windows-x64.zip'
$temp = Join-Path $env:TEMP ('liveagent-build-' + [guid]::NewGuid().ToString('N'))

function Invoke-ReleaseDownload([string]$Uri, [string]$Destination) {
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination
      if ((Get-Item -LiteralPath $Destination).Length -le 0) { throw 'Downloaded file is empty.' }
      return
    }
    catch {
      Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
      if ($attempt -eq 3) { throw }
      Start-Sleep -Seconds (2 * $attempt)
    }
  }
}

New-Item -ItemType Directory -Path $artifacts,$temp -Force | Out-Null
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
  $copyItems = @('liveagent-studio','live_scout_agent','live_breakdown_agent','live_retro_agent','docs','launcher','LICENSE','README.md','SECURITY.md','THIRD_PARTY_NOTICES.md','CHANGELOG.md','requirements-windows.txt')
  foreach ($item in $copyItems) {
    $source = Join-Path $root $item
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $stage -Recurse -Force }
  }
  Get-ChildItem -LiteralPath $stage -Directory -Recurse -Force | Where-Object { $_.Name -in @('workspace','node_modules','dist','tests','examples','__pycache__','.git','.next','.vinext','.wrangler') -or $_.Name -like '*.egg-info' } | Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath $stage -File -Recurse -Force | Where-Object { $_.Name -eq '.env' -or $_.Extension -in @('.pyc','.log') } | Remove-Item -Force

  $runtime = Join-Path $stage '.runtime'
  $pythonDir = Join-Path $runtime 'python'
  $nodeDir = Join-Path $runtime 'node'
  New-Item -ItemType Directory -Path $pythonDir,$nodeDir -Force | Out-Null

  $pythonZip = Join-Path $temp 'python.zip'
  Invoke-ReleaseDownload 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' $pythonZip
  Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir -Force
  $pth = Get-ChildItem -LiteralPath $pythonDir -Filter 'python*._pth' | Select-Object -First 1
  (Get-Content -LiteralPath $pth.FullName) -replace '^#import site$', 'import site' | Set-Content -LiteralPath $pth.FullName -Encoding ascii
  Add-Content -LiteralPath $pth.FullName -Encoding ascii -Value @(
    '..\..\live_scout_agent\src',
    '..\..\live_breakdown_agent\src',
    '..\..\live_retro_agent\src'
  )
  $getPip = Join-Path $temp 'get-pip.py'
  Invoke-ReleaseDownload 'https://bootstrap.pypa.io/get-pip.py' $getPip
  & (Join-Path $pythonDir 'python.exe') $getPip
  & (Join-Path $pythonDir 'python.exe') -m pip install --no-warn-script-location --upgrade pip setuptools wheel
  if ($LASTEXITCODE -ne 0) { throw 'Python build tools installation failed.' }
  Push-Location $stage
  try {
    & (Join-Path $pythonDir 'python.exe') -m pip install --no-warn-script-location -r (Join-Path $stage 'requirements-windows.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败。' }
  }
  finally { Pop-Location }

  $nodeZip = Join-Path $temp 'node.zip'
  Invoke-ReleaseDownload 'https://nodejs.org/dist/v22.18.0/node-v22.18.0-win-x64.zip' $nodeZip
  $nodeExtract = Join-Path $temp 'node'
  Expand-Archive -LiteralPath $nodeZip -DestinationPath $nodeExtract -Force
  Copy-Item -Path (Join-Path $nodeExtract 'node-v22.18.0-win-x64\*') -Destination $nodeDir -Recurse -Force

  $ffmpegZip = Join-Path $temp 'ffmpeg.zip'
  Invoke-ReleaseDownload 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' $ffmpegZip
  $ffmpegRoot = Join-Path $stage 'tools\ffmpeg\bits_unz'
  New-Item -ItemType Directory -Path $ffmpegRoot -Force | Out-Null
  Expand-Archive -LiteralPath $ffmpegZip -DestinationPath $ffmpegRoot -Force
  $ffmpegPackage = Get-ChildItem -LiteralPath $ffmpegRoot -Directory | Select-Object -First 1
  if ($ffmpegPackage) {
    Remove-Item -LiteralPath (Join-Path $ffmpegPackage.FullName 'bin\ffplay.exe') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $ffmpegPackage.FullName 'doc') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $ffmpegPackage.FullName 'presets') -Recurse -Force -ErrorAction SilentlyContinue
  }

  $studio = Join-Path $stage 'liveagent-studio'
  $env:PATH = "$nodeDir;$env:PATH"
  Push-Location $studio
  try {
    & (Join-Path $nodeDir 'npm.cmd') ci --no-audit --no-fund --prefer-offline
    if ($LASTEXITCODE -ne 0) { throw '网页依赖安装失败。' }
    & (Join-Path $nodeDir 'npm.cmd') run build
    if ($LASTEXITCODE -ne 0) { throw '网页构建失败。' }
  }
  finally { Pop-Location }

  $csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
  if (-not (Test-Path -LiteralPath $csc)) { throw '未找到 Windows C# 编译器。' }
  $outArg = '/out:' + (Join-Path $stage 'LiveAgentStudio.exe')
  & $csc /nologo /target:winexe /reference:System.Windows.Forms.dll $outArg (Join-Path $stage 'launcher\LiveAgentStudioLauncher.cs')
  if ($LASTEXITCODE -ne 0) { throw 'EXE 启动器编译失败。' }

  if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
  Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal
  $zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
  Set-Content -LiteralPath ($zip + '.sha256') -Encoding ascii -Value ($zipHash + '  ' + [IO.Path]::GetFileName($zip))
  Write-Host "Windows 发布包已生成：$zip" -ForegroundColor Green
}
finally {
  if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
