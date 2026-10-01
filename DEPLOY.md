# Deploying the Varuna control plane

The control plane runs as a Docker Compose stack on a single Linux VM the developer owns
(A-13). This is the server half only; the per-user agent is installed separately on each
user's machine.

## Prerequisites

1. A Linux VM with a public IPv4 address (TBD-11: a free tier works for the PoC).
2. Docker Engine v24+ and Compose v2 (not Docker Desktop; this is a headless server).
3. A domain with DNS you control (TBD-4), pointed at the VM's public IP. Needed for Caddy's
   automatic HTTPS and, later, Interactsh's NS delegation.
4. Tailscale installed on the VM and joined to the ILCS tailnet (for the private plane, NFR-24):
   `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`. Note the VM's
   tailscale IP (`tailscale ip -4`).

## Configure

```bash
git clone https://github.com/calvinkatoroy/varuna.git && cd varuna
cp .env.example .env
```

Edit `.env`:

- `JWT_SECRET` : `openssl rand -hex 32` (REQUIRED; the stack refuses to start without it)
- `VARUNA_DOMAIN` : your domain, e.g. `varuna.example.com`
- `CADDY_EMAIL` : your email (Let's Encrypt)
- `VARUNA_CORS_ORIGINS` : `https://varuna.example.com`
- `TAILSCALE_BIND` : the VM's tailscale IP (so the private API has no public listener)
- `VITE_PRIVATE_API` : `http://<tailscale-ip>:8010` (baked into the SPA at build)

## Bring up

```bash
bash setup.sh          # builds images, starts the stack, pulls the Ollama model
```

This starts: Caddy (serves the SPA + proxies the APIs), the public browser API, the agent
API, the private API (Tailscale-bound), Redis, and Ollama.

## First account

There is no self-registration. Provision the first Pro account from inside the container:

```bash
docker compose exec api-public python /app/controlplane/seed_account.py admin '<password>' pro
```

## Verify

- `https://<domain>` serves the React app and login works.
- A user can install their agent (Install Agent page) and it connects.
- The private API is reachable ONLY over Tailscale: from a non-tailnet host,
  `http://<public-ip>:8010` must NOT connect; from a tailnet device it does.

## Still to wire (VM-specific, not in compose yet)

- **Interactsh** self-hosted OOB server + NS delegation of a subdomain to the VM (§3.4), port
  53 open. Needed for blind SSRF/RCE/OOB detection (REQ-21b).

### Offboarding (engagement end, NFR-28)

Destroys all findings, reports, scan data, and the audit log (accounts and agent bindings are
kept; remove those separately if the engagement is fully ending):

```bash
docker compose exec api-public python /app/controlplane/wipe_data.py --confirm
```

Then tear down the agent on each user's Windows machine:

```powershell
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name VarunaAgent -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.ExecutablePath -like "*\Varuna\.venv\*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Varuna"
```

## v2 operations (accounts, backups, notifications)

### Planes and logins
- **Team address:** `http://<tailscale-ip>:8080/team` (Caddy's second listener, published only on the
  host's Tailscale address by `TAILSCALE_BIND`). It serves the same app with `/api` wired to the
  private API, so the page and its API share one origin: no CORS, no mixed content. Set
  `VITE_PRIVATE_API=same` in `.env` for this. The public tunnel targets `:80` only, so the team
  plane is never reachable through it. Do not add port 8080 or 8010 to the tunnel.
- Clients sign in on the public plane (`/api/login`). Security-team accounts sign in on the
  **private** plane (`POST http://<tailscale-host>:8010/api/login`); the public API refuses team
  logins and team tokens (NFR-24). For local dev with no private plane only, set
  `VARUNA_PUBLIC_TEAM_LOGIN=1`.
- `seed_account.py --team-defaults` gives each team account a random password (shown once). The
  dev-only `--dev` flag uses `changeme`; `--rotate-defaults` replaces any that remain. The private
  API prints a startup warning while any remain; change them at once (account menu > Change password, or the
  lead pentester's admin API below).

### Team account administration (lead pentester, private plane)
```
GET  /api/admin/accounts
POST /api/admin/accounts                       {username, password, role}
POST /api/admin/accounts/{user}/reset-password {password}
POST /api/admin/accounts/{user}/disable | enable
```
A disabled account cannot log in and its live tokens stop working immediately.

### Demo data and two-factor for the team
- Demo clients (globex, initech, umbrella, acme, stark, wayne) sit at every stage: reporter, lead, governance, delivered,
  pending and rejected. Seed with `docker compose exec api-public python /app/controlplane/seed_demo.py`; it prints
  `CRED user password` lines, so redirect those into the gitignored `.demo-credentials.txt`. Passwords are random per
  account, never a shared default. It skips itself if the demo clients already exist.
- All four team accounts have two-factor. Secrets are in `.team-credentials.txt` (gitignored): add each to an
  authenticator app with "Enter a setup key" (time based), or on this laptop run `python team-code.py <user>` for the
  current code during a demo.

### Hosting on a laptop, no domain (the default for this PoC)
Tailscale Funnel gives a free, permanent HTTPS address (`https://<machine>.<tailnet>.ts.net`) with a valid
certificate and no inbound ports. One command starts everything and prints the addresses:
`powershell -File start-varuna.ps1`. For it to stay reachable: keep the laptop on and awake (Power & sleep:
never sleep while plugged in), set Docker Desktop to start at sign-in (containers restart on their own), and
keep Tailscale and Ollama running. Funnel is set once with `tailscale funnel --bg 80`. Clients use the
`.ts.net` address; the team uses `http://<tailscale-ip>:8080/team`. The Cloudflare options below are only
for a custom domain.

### Public domain with valid HTTPS (Cloudflare Tunnel)
The client plane needs a real hostname. A Cloudflare Tunnel gives a valid certificate, works behind
CGNAT and opens no inbound port. You need a domain whose DNS is on Cloudflare (free plan is enough).

1. Cloudflare dashboard > Zero Trust > Networks > Tunnels > Create a tunnel (Cloudflared). Copy the token.
2. In the tunnel, add a Public hostname: `varuna.<your-domain>` -> Service `HTTP` `caddy:80`.
3. In `.env` set:
   ```
   VARUNA_DOMAIN=:80
   CLOUDFLARE_TUNNEL_TOKEN=<token>
   VARUNA_CORS_ORIGINS=https://varuna.<your-domain>
   VARUNA_PUBLIC_URL=https://varuna.<your-domain>
   ```
4. `docker compose --profile tunnel up -d --build`

Trial without a domain: `docker compose --profile quicktunnel up -d`, then
`docker compose logs cloudflared-quick | findstr trycloudflare` for the URL (it changes on every restart).
Only the public plane goes through the tunnel. Keep the team plane (:8010) on Tailscale; never add it
to the tunnel. Tailscale Funnel can be switched off once the tunnel works.

### Upgrading an existing install: containers now run unprivileged
The control-plane image runs as user `varuna` (uid 10001), not root. A fresh install needs nothing.
Volumes created by an older (root) image must be handed over once, or the API cannot write to them:
```bash
docker compose run --rm --user root api-public chown -R 10001:10001 /dbdata /data/reports
```
Python dependency versions are pinned in `controlplane/requirements.lock`; refresh it when you change
`requirements.txt` (`docker compose run --rm api-public pip freeze > controlplane/requirements.lock`).

### Two-factor login for the team (TOTP)
Team members turn it on from the account menu (Two-factor authentication): paste the setup key into
any authenticator app (Google/Microsoft Authenticator, Authy, 1Password) and confirm with a code.
From then on a password alone cannot sign in: the login asks for the 6-digit code. Codes are
standard RFC 6238 (30 s, 6 digits), tolerate one step of clock drift, cannot be replayed, and wrong
codes count toward the same lockout as wrong passwords. A lost phone is recovered by the lead
pentester (`POST /api/admin/accounts/{user}/reset-mfa`, or "Reset 2FA" on `/team/accounts`). The
private API prints which team accounts still lack two-factor at startup. Clients do not use it.

### Backups
```bash
docker compose exec api-public python /app/controlplane/backup_db.py           # SQLite -> /data/backups (keeps 14)
docker compose cp api-public:/dbdata/backups ./backups                          # copy off the host
```
Also back up the reports volume (`report_output`, generated `.docx` versions and delivered PDFs).
Schedule the first command daily (Windows Task Scheduler / cron) and copy the files off the machine.

### Notifications (optional)
Set `NOTIFY_WEBHOOK_URL` (a Slack/Teams/Discord incoming webhook) in `.env` and the team is
messaged when a proposal arrives or a report reaches a stage. Only event names and short ids are
sent, never finding detail. Unset = off.

### After a scan finishes
Findings are enriched and the report is created automatically at the reporter stage for every
approved proposal. Scans started directly by the team (advanced scan) have no proposal; start
their review with `POST /api/pipeline/reports {job_id, template}`.
Templates: Full Technical, Formal Handover, Executive Summary, Raw Findings (plus the older
OWASP Web App and ILCS Internal layouts).

### Advanced scan options (team only; clients can never set these)
The advanced-scan drawer sends a flat options object that the server validates and clamps
(`controlplane/common/scanopts.py`: unknown keys dropped, ranges enforced). SQLMap level above 2,
risk above 1, `--dump` and `--os-shell` are refused unless the caller is the lead pentester and
has opted in to aggressive mode (safe-profile lock). Reviewers can also upload an edited .docx
as the next report version and regenerate a report in another template from the review drawer;
the lead manages team accounts at `/team/accounts`.
`opts.deep` adds CVE/vuln Nuclei templates (slow); `opts.rate` overrides the Nuclei rate;
`opts.auth` logs in first for an authenticated scan:
`{login_url, username, password, username_field, password_field, json, token_path}`. The login URL
must be on the scanned host. Credentials live only in the job record (24h TTL).
`opts.auth.form=true` makes the login a classic HTML form: the agent loads the login page first, sends
its hidden fields (CSRF token) back with the credentials, and fails the scan if the login form comes
back. `opts.headless` crawls with a browser and uses a locally installed Chrome or Edge when one is
found (bounded by the crawl-time cap either way).
Fine tuning (all clamped, none can make a scan destructive): Nuclei `concurrency`, `timeout`,
`retries`, `exclude_tags` (the safety excludes always stay); SQLMap `threads`, `delay`,
`sqlmap_timeout`, `dbms`, `random_agent`.
Out-of-band checks: Nuclei never calls the public `oast.*` servers. Set `opts.interactsh` to your own
Interactsh server to enable OOB templates for DAST; without it they are skipped, so findings and
target details stay on-premise.

### Capacity (why SQLite, not Postgres)
Measured with 12 concurrent writers on the WAL-mode database: 1,800 writes, 0 errors, about 720
writes/s, p99 under 4 ms. The team and clients never produce that load, so SQLite stays. Revisit
only if the API logs `database is locked` errors.
