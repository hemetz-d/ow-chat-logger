<#
Build script for OW Chat Logger

This script performs a full build:
  1) Builds the standalone EXE via Nuitka
  2) Builds the Inno Setup installer (setup_OW Chat Logger.exe)

Usage:
  .\build_exe.ps1           # build exe + installer
  .\build_exe.ps1 -NoInstaller  # build only exe
#>

param(
  [switch]$NoInstaller
)

$ErrorActionPreference = "Stop"

Write-Host "=== OW Chat Logger Build ===" -ForegroundColor Cyan

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements.txt
python -m pip install "nuitka[onefile]"

Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\build, .\dist, .\ow-chat-logger.spec, .\setup_OW* 2>$null

Write-Host "Building executable with Nuitka..." -ForegroundColor Yellow
python -m nuitka --onefile --nofollow-imports --output-dir=dist --output-filename=ow-chat-logger.exe src\ow_chat_logger\main.py
Write-Host "EXE build complete: dist\\ow-chat-logger.exe" -ForegroundColor Green

if (-not $NoInstaller) {
  Write-Host "Building Inno Setup installer..." -ForegroundColor Yellow

  $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  if (-not (Test-Path $iscc)) {
    Write-Error "Inno Setup compiler not found at: $iscc`nPlease install Inno Setup or update the path in this script."
    exit 1
  }

  $installerOutput = "setup_OW Chat Logger.exe"
  if (Test-Path $installerOutput) {
    try {
      Remove-Item -Force $installerOutput
    } catch {
      Write-Warning "Could not delete existing installer ($installerOutput). It may be in use. Please close it and re-run this script."
      exit 1
    }
  }

  & $iscc "installer.iss"
  Write-Host "Installer build complete: $installerOutput" -ForegroundColor Green
}

Write-Host "Build finished." -ForegroundColor Cyan
