# Run Mylar locally for UI review (from mylar3-src directory).
# Usage:  .\devtools\run_local.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Creating venv and installing requirements (first run)..."
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
}
# Folder you can set as Comic Location (destination_dir) when testing on Windows
$comics = Join-Path (Get-Location) "local-dev-data\comics"
if (-not (Test-Path $comics)) { New-Item -ItemType Directory -Path $comics -Force | Out-Null }

if (-not (Test-Path local-dev-data\mylar.db)) {
    Write-Host "Bootstrapping local-dev-data database..."
    .\.venv\Scripts\python.exe devtools\bootstrap_local_db.py
    .\.venv\Scripts\python.exe devtools\seed_dummy_series.py
}
Write-Host "Starting Mylar on http://127.0.0.1:8090/ (Ctrl+C to stop)"
.\.venv\Scripts\python.exe Mylar.py --datadir=local-dev-data --nolaunch -p 8090
