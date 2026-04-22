# Start Mylar using repo .venv if present, else python on PATH.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root "local-dev-data"
$Mylar = Join-Path $Root "Mylar.py"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    & $VenvPy $Mylar --datadir $Data --nolaunch
} else {
    & python $Mylar --datadir $Data --nolaunch
}
