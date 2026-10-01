# One command to bring Varuna up on this laptop and show where everything is.
# Run:  powershell -File start-varuna.ps1
Set-Location $PSScriptRoot
$ts = (tailscale ip -4 | Select-Object -First 1)
python build-agent-dist.py   # clients download the CURRENT agent, never a stale one
docker compose up -d
if ($LASTEXITCODE -ne 0) { "Docker is not running. Start Docker Desktop and run this again."; return }
if (-not (tailscale funnel status 2>$null | Select-String "Funnel on")) { tailscale funnel --bg 80 | Out-Null }
$ollama = try { (Invoke-WebRequest http://localhost:11434 -UseBasicParsing -TimeoutSec 3).StatusCode } catch { "not running (start Ollama for AI report text)" }
# Cloud scanner: an agent on THIS laptop that runs the scans clients choose as "By Varuna (cloud)".
# It enrols once (token kept in .cloud-agent-token, gitignored) and is restarted here if it is not checking in.
$cloudTok = Join-Path $PSScriptRoot '.cloud-agent-token'
$env:VARUNA_AGENT_TOKEN_FILE = $cloudTok
$env:VARUNA_URL = 'http://localhost'
$online = (docker compose exec -T api-agent python /app/controlplane/mint_cloud_token.py --online | Select-Object -Last 1).Trim()
if ($online -ne 'True') {
    # Not checking in: enrol afresh (replaces any stale token) and start it under a loop that restarts it.
    $t = (docker compose exec -T api-agent python /app/controlplane/mint_cloud_token.py | Select-Object -Last 1).Trim()
    python agent\agent.py --enroll $t | Out-Null
    $loop = "`$env:VARUNA_URL='http://localhost'; `$env:VARUNA_AGENT_TOKEN_FILE='$cloudTok'; while (`$true) { python agent\agent.py; Start-Sleep 5 }"
    Start-Process -WindowStyle Hidden powershell -ArgumentList '-NoProfile','-Command',$loop -WorkingDirectory $PSScriptRoot
    Start-Sleep 8
}
$cloud = (docker compose exec -T api-agent python /app/controlplane/mint_cloud_token.py --online | Select-Object -Last 1).Trim()
""
"Cloud scanner:     $(if ($cloud -eq 'True') { 'online' } else { 'NOT online (check python and the scan tools are installed)' })"
"Clients (public):  https://kalpinoos.tail91d02e.ts.net"
"Team (Tailscale):  http://${ts}:8080/team"
"Ollama:            $ollama"
"Agent for a test client:  python agent\agent.py --enroll <token from the client's screen>, then python agent\agent.py"
