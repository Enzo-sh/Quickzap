<#
.SYNOPSIS
  Installs and configures Ollama + a model for Quickzap (Windows 10/11).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Model qwen2.5:3b
#>
param(
  [string]$Model = "auto",   # "auto" chooses based on your GPU (see: python -m quickzap recommend)
  [switch]$SkipVerify
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Find-Ollama {
  $cmd = Get-Command ollama -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $known = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (Test-Path $known) { return $known }
  return $null
}
function Test-Python {
  try { & python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null; return ($LASTEXITCODE -eq 0) }
  catch { return $false }
}
function Test-OllamaUp {
  try { Invoke-RestMethod "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null; return $true }
  catch { return $false }
}

Step "1/5  Python 3.9 or later"
if (-not (Test-Python)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing Python with winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    Refresh-Path
  }
  if (-not (Test-Python)) { throw "Could not find Python 3.9+. Install it from https://www.python.org/downloads/ (check 'Add to PATH') and run this script again." }
}
Write-Host "Python OK: $(& python --version)"

Step "2/5  Ollama"
$ollama = Find-Ollama
if (-not $ollama) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing Ollama with winget..."
    winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  } else {
    Write-Host "Downloading the official Ollama installer..."
    $installer = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer
    Start-Process $installer -ArgumentList "/SILENT" -Wait
  }
  Refresh-Path
  $ollama = Find-Ollama
  if (-not $ollama) { throw "Could not install Ollama automatically. Install it from https://ollama.com/download and run this script again." }
}
Write-Host "Ollama encontrado: $ollama"

Step "3/5  Starting the Ollama service"
if (-not (Test-OllamaUp)) {
  Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) { if (Test-OllamaUp) { $ready = $true; break }; Start-Sleep -Seconds 1 }
  if (-not $ready) { throw "Ollama did not respond within 30 seconds. Open the Ollama app manually and try again." }
}
Write-Host "Ollama running at http://127.0.0.1:11434"

Step "4/5  Downloading the model"
if ($Model -eq "auto") { $Model = (& python -m quickzap recommend --plain).Trim() }
Write-Host "Model: $Model (may take a while depending on your connection; several GB)"
& python -m quickzap pull $Model
if ($LASTEXITCODE -ne 0) { throw "Failed to download model $Model." }

if (-not $SkipVerify) {
  Step "5/5  Verification"
  & python -m quickzap doctor
  if ($LASTEXITCODE -ne 0) { throw "Verification found problems (see above)." }
}

# Save the total time for benchmark reports (python -m quickzap bench)
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
$json = '{"install_seconds": ' + [int]$stopwatch.Elapsed.TotalSeconds + '}'
Set-Content -Path (Join-Path $PSScriptRoot "data\install_timing.json") -Value $json -Encoding ascii

Write-Host "`nDone. To start Quickzap run:  python -m quickzap" -ForegroundColor Green
