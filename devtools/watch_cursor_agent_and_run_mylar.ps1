# Watch a Cursor parent chat transcript for quiescence, then verify Python, refresh the dev
# environment, and start the local Mylar server. Use this so you do not have to hand-run
# setup + start after another agent finishes editing the tree.
#
# The transcript folder appears under Cursor's project agent-transcripts when that chat
# exists. Default base matches a typical project path; override with -TranscriptBase if yours differs.
#
# One-shot: after the first “quiet” period on the .jsonl, the script runs verify + ensure_dev + Mylar.
# Re-run the script (or a new chat with the other agent) for the next development cycle.
#
# Example:
#   powershell -NoProfile -ExecutionPolicy Bypass -File devtools/watch_cursor_agent_and_run_mylar.ps1 `
#     -AgentId '5e24c61f-66f3-4b7c-8243-7d78c864782d'

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $AgentId,
    [string] $TranscriptBase = (Join-Path $env:USERPROFILE ".cursor\projects\c-Users-james-Git-mylar-mod\agent-transcripts"),
    [int] $PollSeconds = 5,
    [int] $QuiesceSeconds = 25,
    [int] $MaxWaitMinutes = 0,
    [switch] $WithPytest,
    [switch] $NoStartServer
)

$ErrorActionPreference = "Stop"

function Write-Info([string] $m) { Write-Host "[watch-agent] $m" -ForegroundColor Cyan }

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
$Py = if (Test-Path $VenvPy) { $VenvPy } else { "python" }

$dir = Join-Path $TranscriptBase $AgentId
$jsonl = Join-Path $dir ("{0}.jsonl" -f $AgentId)

$deadline = $null
if ($MaxWaitMinutes -gt 0) {
    $deadline = [datetime]::UtcNow.AddMinutes($MaxWaitMinutes)
}

Write-Info "Waiting for transcript folder: $dir"
while (-not (Test-Path -LiteralPath $dir)) {
    if ($null -ne $deadline -and [datetime]::UtcNow -gt $deadline) {
        throw "Timeout waiting for agent folder (MaxWaitMinutes=$MaxWaitMinutes)."
    }
    Start-Sleep -Seconds $PollSeconds
}
Write-Info "Found folder; waiting for $jsonl"
while (-not (Test-Path -LiteralPath $jsonl)) {
    if ($null -ne $deadline -and [datetime]::UtcNow -gt $deadline) {
        throw "Timeout waiting for jsonl (MaxWaitMinutes=$MaxWaitMinutes)."
    }
    Start-Sleep -Seconds $PollSeconds
}

Write-Info "Waiting until transcript stops growing (~$QuiesceSeconds s stable)…"
$lastSize = -1L
$lastWrite = [datetime]::MinValue
$stableSince = $null
while ($true) {
    $item = Get-Item -LiteralPath $jsonl
    if ($item.Length -eq $lastSize -and $item.LastWriteTimeUtc -eq $lastWrite) {
        if ($null -eq $stableSince) { $stableSince = [datetime]::UtcNow }
        $elapsed = ([datetime]::UtcNow - $stableSince).TotalSeconds
        if ($elapsed -ge $QuiesceSeconds) { break }
    }
    else {
        $lastSize = $item.Length
        $lastWrite = $item.LastWriteTimeUtc
        $stableSince = $null
    }
    if ($null -ne $deadline -and [datetime]::UtcNow -gt $deadline) {
        throw "Timeout waiting for quiescence (MaxWaitMinutes=$MaxWaitMinutes)."
    }
    Start-Sleep -Seconds $PollSeconds
}
Write-Info "Transcript looks idle; running verification…"

Set-Location -LiteralPath $Root

# Quick syntax check on application packages (fails fast on bad edits)
$compileArgs = @("-m", "compileall", "-q", "mylar", "Mylar.py")
& $Py @compileArgs
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }

if ($WithPytest) {
    if (Test-Path (Join-Path $Root "tests\pytest.ini")) {
        Write-Info "Running pytest (unit)…"
        & $Py -m pytest -m "unit" --tb=short -q tests
        if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    }
    else {
        Write-Info "No tests\pytest.ini; skipping pytest."
    }
}

Write-Info "Mylar: Full dev setup (ensure_dev_environment)…"
& $Py "devtools\ensure_dev_environment.py"
if ($LASTEXITCODE -ne 0) { throw "ensure_dev_environment failed" }

if ($NoStartServer) {
    Write-Info "Done (NoStartServer). Open Run and Debug or task Mylar: Start server when ready."
    exit 0
}

$runner = Join-Path $Root "devtools\run_mylar_dev.ps1"
Write-Info "Starting Mylar in a new window (http://127.0.0.1:8090)…"
Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $runner
) -WorkingDirectory $Root
Write-Info "Mylar start requested. If the port is already in use, stop the old process first."
