# Registers a daily Windows scheduled task that runs the HedgeFund watchlist monitor.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_monitor_task.ps1

$TaskName = "HedgeFundWatchlistMonitor"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$ScriptArgs = "-m pipeline.monitor"
$LogPath = Join-Path $ProjectRoot "logs\monitor_task.log"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe - create venv first."
    exit 1
}

# Remove existing task if present
schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing task $TaskName..."
    schtasks /Delete /TN $TaskName /F | Out-Null
}

# Create new daily task at 16:30 local time (after US market close)
$Command = "cmd.exe /c `"cd /d `"`"$ProjectRoot`"`" && `"`"$PythonExe`"`" $ScriptArgs >> `"`"$LogPath`"`" 2>&1`""

schtasks /Create `
    /TN $TaskName `
    /TR $Command `
    /SC DAILY `
    /ST 16:30 `
    /RL LIMITED `
    /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "Scheduled task '$TaskName' installed - runs daily at 16:30."
    Write-Host "  Logs: $LogPath"
    Write-Host "  Verify: schtasks /Query /TN $TaskName /V /FO LIST"
    Write-Host "  Run now: schtasks /Run /TN $TaskName"
} else {
    Write-Error "Failed to register scheduled task."
    exit 1
}
