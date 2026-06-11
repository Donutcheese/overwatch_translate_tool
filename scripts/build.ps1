#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "OW-Light-Translator - build exe" -ForegroundColor Cyan

& $Python -m pip install -q -r requirements-build.txt

Write-Host "Generating icon.ico from icon.png..."
& $Python scripts/generate_icon.py

if (-not (Test-Path "img\icon.ico")) {
    Write-Host "[ERROR] img\icon.ico not found." -ForegroundColor Red
    exit 1
}

Write-Host "Running PyInstaller..."
& $Python -m PyInstaller build.spec --noconfirm --clean

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  dist\OW-Color-Fluent-Translator.exe"
Write-Host ""
