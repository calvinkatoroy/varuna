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
Unregister-ScheduledTask -TaskName VarunaAgent -Confirm:$false
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Varuna"
```
