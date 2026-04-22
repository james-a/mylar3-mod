# Stop a local Mylar dev instance that was started with --datadir .../local-dev-data
# (or ...\mylar3-src\local-dev-data) so mylar.db can be replaced. Safe: only processes
# whose command line includes both "Mylar.py" and "local-dev-data" are considered.
$ErrorActionPreference = "Stop"
$killed = 0
$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $c = $_.CommandLine
    if (-not $c) { return $false }
    $c = $c.ToString()
    return ($c -match "Mylar\.py") -and ($c -match "local-dev-data")
  }
$seen = @{}
foreach ($p in $procs) {
  $id = $p.ProcessId
  if ($seen[$id]) { continue }
  $seen[$id] = $true
  try {
    Stop-Process -Id $id -Force -ErrorAction Stop
    Write-Host "[stop_mylar_dev_instance] Stopped PID $id"
    $killed++
  } catch {
    Write-Host "[stop_mylar_dev_instance] Could not stop PID $id (it may have already exited): $_" -ForegroundColor Yellow
  }
}
if ($killed -eq 0) {
  Write-Host "[stop_mylar_dev_instance] No matching Mylar (Mylar.py + local-dev-data) process found."
}
exit 0
