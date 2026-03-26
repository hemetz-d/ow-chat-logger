<#
Build script for OW Chat Logger

This script builds the standalone EXE via Nuitka.

Usage:
  .\build_exe.ps1
#>

$ErrorActionPreference = "Stop"

function Invoke-Step {
  param(
    [string]$Description,
    [scriptblock]$Action
  )

  Write-Host $Description -ForegroundColor Yellow
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed during step: $Description"
  }
}

Write-Host "=== OW Chat Logger Build ===" -ForegroundColor Cyan

Invoke-Step "Installing packaging dependencies..." { python -m pip install -r requirements.txt }
Invoke-Step "Installing Nuitka..." { python -m pip install "nuitka[onefile]" }

Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\build, .\dist, .\ow-chat-logger.spec 2>$null
$env:NUITKA_CACHE_DIR = Join-Path (Get-Location) ".nuitka-cache"
$env:PYTHONPATH = Join-Path (Get-Location) "src"

Invoke-Step "Building executable with Nuitka..." {
  python -m nuitka `
    --onefile `
    --standalone `
    --follow-imports `
    --assume-yes-for-downloads `
    --include-package=ow_chat_logger `
    --include-package=easyocr `
    --include-package=torch `
    --module-parameter=torch-disable-jit=yes `
    --enable-plugin=tk-inter `
    --output-dir=dist `
    --output-filename=ow-chat-logger.exe `
    packaging\nuitka_entry.py
}
Write-Host "EXE build complete: dist\\ow-chat-logger.exe" -ForegroundColor Green

Write-Host "Build finished." -ForegroundColor Cyan
