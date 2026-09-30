# Daily host backup: SQLite snapshot + generated reports, copied out of the docker volumes into ./backups.
# Register once:  powershell -File backup-host.ps1 -Register      (runs daily 02:00 as the current user)
param([switch]$Register, [int]$Keep = 14)
$root = $PSScriptRoot
if ($Register) {
    $act = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Register-ScheduledTask -TaskName "VarunaBackup" -Action $act -Trigger (New-ScheduledTaskTrigger -Daily -At 2am) -Force | Out-Null
    "registered VarunaBackup (daily 02:00)"
    return
}
Set-Location $root
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "backups\$stamp"
New-Item -ItemType Directory -Force $dest | Out-Null
docker compose exec -T api-public python /app/controlplane/backup_db.py /dbdata/backups $Keep | Out-Null
docker compose cp api-public:/dbdata/backups "$dest\db"
docker compose cp api-public:/data/reports "$dest\reports"
# keep the newest $Keep host snapshots
Get-ChildItem (Join-Path $root "backups") -Directory | Sort-Object Name -Descending | Select-Object -Skip $Keep | Remove-Item -Recurse -Force
