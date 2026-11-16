<#
.SYNOPSIS
  Instala y configura Ollama + un modelo para Quickzap (Windows 10/11).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Model qwen2.5:3b
#>
param(
  [string]$Model = "auto",   # "auto" elige segun tu GPU (ver: python -m quickzap recommend)
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

Step "1/5  Python 3.9 o superior"
if (-not (Test-Python)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Instalando Python con winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    Refresh-Path
  }
  if (-not (Test-Python)) { throw "No se encontro Python 3.9+. Instalalo desde https://www.python.org/downloads/ (marca 'Add to PATH') y ejecuta este script otra vez." }
}
Write-Host "Python OK: $(& python --version)"

Step "2/5  Ollama"
$ollama = Find-Ollama
if (-not $ollama) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Instalando Ollama con winget..."
    winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  } else {
    Write-Host "Descargando el instalador oficial de Ollama..."
    $installer = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer
    Start-Process $installer -ArgumentList "/SILENT" -Wait
  }
  Refresh-Path
  $ollama = Find-Ollama
  if (-not $ollama) { throw "No se pudo instalar Ollama automaticamente. Instalalo desde https://ollama.com/download y ejecuta este script otra vez." }
}
Write-Host "Ollama encontrado: $ollama"

Step "3/5  Iniciando el servicio de Ollama"
if (-not (Test-OllamaUp)) {
  Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) { if (Test-OllamaUp) { $ready = $true; break }; Start-Sleep -Seconds 1 }
  if (-not $ready) { throw "Ollama no respondio en 30 segundos. Abre la aplicacion Ollama manualmente y vuelve a intentar." }
}
Write-Host "Ollama activo en http://127.0.0.1:11434"

Step "4/5  Descargando el modelo"
if ($Model -eq "auto") { $Model = (& python -m quickzap recommend --plain).Trim() }
Write-Host "Modelo: $Model (puede tardar segun tu conexion; son varios GB)"
& python -m quickzap pull $Model
if ($LASTEXITCODE -ne 0) { throw "Fallo la descarga del modelo $Model." }

if (-not $SkipVerify) {
  Step "5/5  Verificacion"
  & python -m quickzap doctor
  if ($LASTEXITCODE -ne 0) { throw "La verificacion encontro problemas (ver arriba)." }
}

# Guarda el tiempo total para los informes de benchmark (python -m quickzap bench)
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
$json = '{"install_seconds": ' + [int]$stopwatch.Elapsed.TotalSeconds + '}'
Set-Content -Path (Join-Path $PSScriptRoot "data\install_timing.json") -Value $json -Encoding ascii

Write-Host "`nListo. Para iniciar Quickzap ejecuta:  python -m quickzap" -ForegroundColor Green
