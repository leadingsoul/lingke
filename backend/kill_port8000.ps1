$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $connections) {
    $ownerPid = $conn.OwningProcess
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    Write-Host "Killed process $ownerPid"
}
Write-Host "Done"
