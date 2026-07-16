# Varuna: Web VAPT Report Generator

AI-assisted web application VAPT platform for ILCS. A React single-page app talks to a
FastAPI JSON API; a per-user agent runs the scan tools locally and reports back; a local LLM
enriches the findings into a formatted report. Specs live in `docs/` (SRS, PRD, MRD,
architecture, implementation plan).

## Architecture

Two halves plus a data-locality split:

- **Control plane** (cloud VM, Docker Compose): a React SPA served by Caddy, a public FastAPI
  browser API (JWT), a FastAPI agent API, Redis, Ollama enrichment, and report generation. It
  is split into a public plane (login, submission, approval, status) and a private data plane
  (findings, reports, Ollama) bound to Tailscale only, with no public listener (NFR-24).
- **Per-user agent**: a self-installed program that runs Katana, Nuclei, and SQLMap on the
  user's own machine and ships raw output back over an authenticated HTTPS poll.

Two roles: Standard (zero-config submission, sanitized Executive Summary) and Pro (full scan
control, approvals, findings review, all four report templates).

## Layout

```
frontend/            React + TypeScript + Vite + Tailwind SPA
controlplane/
  common/            models, redis_store, auth, jwt_auth, classifier, dispatch, audit, tokens
  api/               browser.py (public API), private_api.py (Tailscale API), main.py (agent API), ingest.py
  pipeline/          parse, correlate, ollama enrichment
  report/            generator (4 templates), sanitize, store
  tests/             offline test suite
agent/               per-user scan agent (tools/, scan.py, agent.py)
docker-compose.yml   Caddy, Redis, Ollama (app services added at deploy)
Caddyfile            HTTPS reverse proxy plus security headers
docs/                SRS, PRD, MRD, architecture, plan (kept local)
```

## Development quickstart

The Compose Redis is internal only, so for local dev run a throwaway Redis with a published
port:

```bash
docker run --rm -p 6379:6379 redis:7-alpine
export REDIS_URL=redis://localhost:6379/0
```

Bootstrap an account (there is no self-registration):

```bash
python controlplane/seed_account.py admin admin123 pro
```

Run the services, each in its own terminal:

```bash
cd controlplane/api && uvicorn browser:app --port 8000        # public browser API
cd controlplane/api && uvicorn main:app --port 8001           # agent API
cd controlplane/api && uvicorn private_api:app --port 8010    # private (Tailscale) API
cd frontend && npm install && npm run dev                     # React app on :5173
```

Open the app, log in, use the Install Agent page (it gives a one-line command), run the agent,
then submit a scan.

## Tests

Offline suite, no live services needed:

```bash
for f in controlplane/tests/test_*.py; do python "$f"; done
cd frontend && npm run build && npm run typecheck
```

## Scan tools

The agent runs Katana, Nuclei, and SQLMap as native processes. Install them on the agent
machine (`go install` for Katana and Nuclei, `pip install sqlmap`), then run
`nuclei -update-templates` once.
