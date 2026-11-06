# StageForge bootstrap for Windows (PowerShell).
# Creates .venv, installs the package with dev extras, registers hooks.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/4] Checking Python..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python was not found on PATH. Install Python 3.11+ first."
}
$ver = & python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"
Write-Host "      Python $ver"

Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    & python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "[3/4] Installing stageforge[dev]..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host "[4/4] Installing pre-commit hooks..." -ForegroundColor Cyan
& .\.venv\Scripts\pre-commit.exe install

Write-Host ""
Write-Host "Done. Activate with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "Then run:             make test   (or: pytest -q)" -ForegroundColor Green
