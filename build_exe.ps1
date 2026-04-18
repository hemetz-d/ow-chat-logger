<#
Build script for OW Chat Logger

This script builds a Windows standalone folder app via Nuitka.

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
    --standalone `
    --msvc=latest `
    --windows-console-mode=attach `
    --follow-imports `
    --nofollow-import-to=easyocr `
    --nofollow-import-to=torch `
    --nofollow-import-to=torchvision `
    --nofollow-import-to=pytesseract `
    --nofollow-import-to=ow_chat_logger.ocr.easyocr_backend `
    --nofollow-import-to=ow_chat_logger.ocr.tesseract_backend `
    --assume-yes-for-downloads `
    --include-package=ow_chat_logger `
    --include-package=customtkinter `
    --include-package-data=customtkinter `
    --include-package=darkdetect `
    --include-package=winrt `
    --include-package=winrt.runtime `
    --include-package=winrt.system `
    --include-package=winrt.windows.foundation `
    --include-package=winrt.windows.foundation.collections `
    --include-package=winrt.windows.globalization `
    --include-package=winrt.windows.graphics.imaging `
    --include-package=winrt.windows.media.ocr `
    --include-package=winrt.windows.storage.streams `
    --enable-plugin=tk-inter `
    --output-dir=dist `
    --output-filename=ow-chat-logger.exe `
    packaging\nuitka_entry.py
}
Write-Host "Standalone build complete under dist\\" -ForegroundColor Green

Write-Host "Packaging release zip..." -ForegroundColor Yellow
$zipPath = "dist\ow-chat-logger-windows.zip"
Remove-Item -Force -ErrorAction SilentlyContinue $zipPath
Compress-Archive -Path "dist\nuitka_entry.dist\*" -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "Release zip ready: $zipPath" -ForegroundColor Green

Write-Host "Build finished." -ForegroundColor Cyan
