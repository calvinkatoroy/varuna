# Varuna: AI-Assisted VAPT Platform

AI-assisted VAPT platform for ILCS. A client submits a scan target; a per-user agent runs the
scan (Katana crawl, then Nuclei + SQLMap) on the client's own machine so raw scanning never
leaves their network; findings are parsed, correlated, AI-enriched (local Ollama), and carried
through a human review pipeline before a signed, password-protected report is delivered.

## Branch model

- `main` — the live, working single-gate PoC. Deployed and demoable; do not break it.
- `varuna-v2` (this branch) — active re-architecture into a multi-tenant, role-based,
  request-to-handover platform. Everything below describes `varuna-v2`.

## Architecture

Two planes, mapped to two audiences:

- **Public plane** (Caddy, login-gated) — for **clients**: register, submit scan proposals,
  install their own agent, download their own protected reports. Clients never touch Tailscale.
- **Private plane** (Tailscale-gated, no public listener, NFR-24) — the **security team**
  workspace: the review pipeline board, all-client visibility, raw findings, sign-offs, the
  advanced-scan GUI.

Six roles: `client` (submit proposals, view/download own delivered reports, install own agent),
`pentester` (advanced scans, sees all clients), `lead_pentester` (approve/reject proposals,
edit+version reports), `reporter` (first report pass), `governance` (final review, forwards to
client), `soc` (reserved, general team access).

**Persistence is split by durability need**, not by convenience:

- **SQLite** (`controlplane/common/db.py`, WAL mode, named Docker volume) — the durable
  relational store: accounts, proposals, reports + versions, findings, audit log. Findings live
  here specifically so they survive the multi-day review pipeline (they used to be Redis-only
  with a 24h TTL — too short once a report can sit in review for days).
- **Redis** (`controlplane/common/redis_store.py`) — ephemeral coordination only: the per-user
  agent job queue, login-throttle counters, agent-online liveness, scan suspend flags.

**Proposal → delivery state machine:**

```text
PENDING → (lead approves) APPROVED → RUNNING → SCANNED →
IN_REVIEW_REPORTER → IN_REVIEW_LEAD → IN_REVIEW_GOVERNANCE → DELIVERED
```

Registering an account only grants app access — it unlocks nothing until a proposal is
separately approved by a lead pentester (so self-register spam is inert). Any reviewer can send
a report back a stage. The client only sees the report once it hits `DELIVERED`, as a
password-protected PDF (password shown once in-app, re-issuable by governance).

**Client onboarding flow** (`AuthGate.tsx`, one stepper, not separate pages): Account →
Proposal → Approval → **Agent** — the last step shows a one-line PowerShell installer
(`irm <host>/dist/install.ps1 | iex`) with a real one-time enrollment token. The agent still
runs locally on the client's own machine either way; only the routing changed from a standalone
"Install Agent" page (v1/`main`) to an inline onboarding step (v2).

## Layout

```text
frontend/src/
  screens/           route-level pages: ClientCockpit, ClientProposals, ClientFindings,
                      ClientReports, AuthGate, TeamLogin, TeamBoard, FindingsReview,
                      AdvancedScanDrawer, NewProposalDrawer
  components/         shared chrome: ClientTopbar/Nav/Shell, BrandMark, ScanProgress,
                      AgentStatus, ProposalForm, ErrorRetry, Splash, TeamAccount, ThemeToggle
  components/ui/      shadcn-style primitives (button, drawer, dropdown-menu, slider, switch)
  components/viz/     Gauge, SegBar, PostureBubbles, TrendChart
  mock/               fixtures.ts + index.ts - the whole app runs on these when VITE_MOCK=1,
                      no backend needed (see "Frontend, mock mode" below)
  lib/                motion (anime.js), toast, useApiData, useScrambleText, useScrollThreshold
controlplane/
  common/            db (SQLite), redis_store, auth, jwt_auth, models, tenancy, dispatch,
                     board.py (team kanban composition), cockpit.py (client dashboard
                     aggregate), report_pipeline.py (stage transitions), pdf_deliver, audit
  api/               browser.py (public API), private_api.py (Tailscale API),
                     main.py (agent API), ingest.py, deps.py
  pipeline/          parse, correlate, ollama enrichment
  report/            generator (templates), sanitize, store
  tests/             offline test suite (TestClient + FakeRedis + db.reset_for_test)
  seed_account.py    bootstrap one account, or --team-defaults for the 4 demo team logins
  seed_demo.py       seeds a realistic pipeline (proposals at every review stage) via the
                     real endpoint functions, not hand-replicated logic - local/dev only
agent/               per-user scan agent (tools/, scan.py, agent.py)
docker-compose.yml   redis, api-public, api-agent, api-private, caddy
docker-compose.v2local.yml   local-only override: publishes API ports to loopback, no Caddy
Caddyfile            HTTPS reverse proxy plus security headers
docs/                SRS, PRD, MRD, architecture, plan (gitignored, local-only)
```

## Development quickstart

Full local stack via Docker Compose:

```bash
cp .env.example .env.v2local     # separate from the real .env - never touches production secrets
# set JWT_SECRET, VARUNA_CORS_ORIGINS=http://localhost:5173, TAILSCALE_BIND=127.0.0.1
docker compose --env-file .env.v2local -f docker-compose.yml -f docker-compose.v2local.yml up -d
```

Seed accounts and a realistic pipeline (inside the `api-public` container, so imports/env match):

```bash
docker compose exec api-public python /app/controlplane/seed_account.py --team-defaults --dev   # dev: password 'changeme'; omit --dev for random ones
docker compose exec api-public python /app/controlplane/seed_account.py acme demo1234 client
docker compose exec api-public python /app/controlplane/seed_demo.py
```

Run the frontend against the real backend:

```bash
cd frontend
npm install
echo "VITE_MOCK=0" > .env.local
npm run dev                      # :5173, proxies /api and /agent per vite.config.ts
```

Team logins (private plane, `/team`): `riyan` / lead_pentester, `dimas` / pentester,
`aisah` / reporter, `hani` / governance — password `changeme` with `--dev`, otherwise the random
ones printed at seed time. On any real deployment run `seed_account.py --rotate-defaults`.

### Frontend, mock mode (no backend)

`VITE_MOCK` defaults to `1` when unset, so `npm run dev` with no `.env` at all runs the entire
app on the fixtures in `src/mock/` — every screen, every mutation (approve/reject/suspend/mark
fixed), fully interactive, zero backend. This is what a static demo deploy (Netlify/Cloudflare
Pages drag-drop of `npm run build`'s `dist/`) ships as, and it's also the fastest way to work on
UI without standing up Docker. Team routes (`/team`) skip the login gate entirely in mock mode
and auto-sign in as `admin` (see `App.tsx`'s `RoleRoute`) — real deployments still require a
real login.

Ollama is Compose-internal (`http://ollama:11434` in containers) or, if it's running natively on
the host (needed for GPU passthrough on Windows), point at it via `OLLAMA_URL=http://host.docker.internal:11434`
and make sure Ollama binds `0.0.0.0` (`OLLAMA_HOST=0.0.0.0`).

## Tests

```bash
cd controlplane && python -m pytest
cd frontend && npm run build && npx tsc --noEmit
```

## Scan tools

The agent runs Katana, Nuclei, and SQLMap as native processes on the client's own machine.
Install them there (`go install` for Katana/Nuclei, `pip install sqlmap`), then run
`nuclei -update-templates` once.
