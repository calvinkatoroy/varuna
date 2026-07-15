# Varuna — Web VAPT Report Generator

AI-assisted web VAPT scanning + report generation for ILCS. Control plane (Docker
Compose) plus a per-user agent. Specs: [docs/SRS.md](docs/SRS.md) (v3.1),
[docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md).

## Status

**Phase A — foundations.** Control-plane skeleton: redis + ollama + caddy. The
FastAPI agent-API and the two Streamlit UIs land in later phases (see the plan).

## Bring up the control plane (Linux VM)

```bash
cp .env.example .env   # set VARUNA_DOMAIN / CADDY_EMAIL for a real domain
bash setup.sh          # docker compose up -d + one-time model pull
```

Local dev: leave `VARUNA_DOMAIN=localhost` — Caddy uses its internal CA so HTTPS
still works. Only Caddy (:80/:443) is published; redis and ollama stay internal
to `vapt-net`.

## Layout

```
docker-compose.yml   controlplane services (redis/ollama/caddy so far)
Caddyfile            HTTPS reverse proxy
controlplane/        common/ (models, redis_store), later: api/ pipeline/ report/ ui_*/
agent/               per-user scan agent (later phase)
docs/                SRS, PRD, MRD, architecture, plan
```
