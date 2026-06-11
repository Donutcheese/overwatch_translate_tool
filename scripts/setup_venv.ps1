# OW-Light-Translator - create venv and install dependencies
# Usage (from project root):
#   .\scripts\setup_venv.ps1

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvDir = Join-Path $ProjectRoot "venv"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

Set-Location $ProjectRoot

Write-Host "OW-Light-Translator - venv setup" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

function Get-PythonLauncher {
    $candidates = @(
        @{ Command = "python"; Args = @() },
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "py"; Args = @() }
    )
    if ($env:CONDA_PYTHON_EXE -and (Test-Path $env:CONDA_PYTHON_EXE)) {
        $candidates = @(
            @{ Command = $env:CONDA_PYTHON_EXE; Args = @() }
        ) + $candidates
    }
    foreach ($item in $candidates) {
        $cmd = Get-Command $item.Command -ErrorAction SilentlyContinue
        if (-not $cmd -and -not (Test-Path $item.Command)) { continue }
        $verText = & $item.Command @($item.Args) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0 -or -not $verText) { continue }
        return @{
            Command = $item.Command
            Args = $item.Args
            Version = $verText.Trim()
        }
    }
    return $null
}

$py = Get-PythonLauncher
if (-not $py) {
    Write-Host "[ERROR] Python 3.10+ not found in PATH." -ForegroundColor Red
    exit 1
}

$majorMinor = [version]$py.Version
if ($majorMinor -lt [version]"3.10") {
    Write-Host "[ERROR] Python 3.10+ required, found $($py.Version)" -ForegroundColor Red
    exit 1
}

Write-Host "Using: $($py.Command) ($($py.Version))" -ForegroundColor Green

if (Test-Path $VenvDir) {
    Write-Host "[SKIP] venv already exists: $VenvDir" -ForegroundColor Yellow
} else {
    Write-Host "Creating venv: $VenvDir"
    & $py.Command @($py.Args) -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create venv." -ForegroundColor Red
        exit 1
    }
    Write-Host "venv created." -ForegroundColor Green
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Missing $VenvPython" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Upgrading pip..."
& $VenvPython -m pip install -U pip

Write-Host "Installing requirements.txt..."
& $VenvPip install -r $Requirements
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip install failed." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot "img\icon.ico")) -and (Test-Path (Join-Path $ProjectRoot "img\icon.png"))) {
    Write-Host "Generating img\icon.ico..."
    & $VenvPip install -q Pillow
    & $VenvPython (Join-Path $ProjectRoot "scripts\generate_icon.py")
}

Write-Host ""
Write-Host "Running pywin32 post-install (Windows)..."
& $VenvPython -m pywin32_postinstall -install 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] pywin32_postinstall skipped (may already be configured)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "venv ready." -ForegroundColor Green
Write-Host ""
Write-Host "Activate (PowerShell):"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Run app:"
Write-Host "  python main.py"
Write-Host ""
Write-Host "Note: venv/ is in .gitignore - do NOT commit it." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
