# One command to bring Varuna up on this laptop and show where everything is.
# Run:  powershell -File start-varuna.ps1
Set-Location $PSScriptRoot
$ts = (tailscale ip -4 | Select-Object -First 1)
docker compose up -d
if ($LASTEXITCODE -ne 0) { "Docker is not running. Start Docker Desktop and run this again."; return }
if (-not (tailscale funnel status 2>$null | Select-String "Funnel on")) { tailscale funnel --bg 80 | Out-Null }
$ollama = try { (Invoke-WebRequest http://localhost:11434 -UseBasicParsing -TimeoutSec 3).StatusCode } catch { "not running (start Ollama for AI report text)" }
""
"Clients (public):  https://kalpinoos.tail91d02e.ts.net"
"Team (Tailscale):  http://${ts}:8080/team"
"Ollama:            $ollama"
"Agent for a test client:  python agent\agent.py --enroll <token from the client's screen>, then python agent\agent.py"
