$TaskName = "HedgeFundWatchlistMonitor"
schtasks /Delete /TN $TaskName /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "Task '$TaskName' removed."
} else {
    Write-Error "Failed to remove task '$TaskName' (may not exist)."
}
