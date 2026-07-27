#!/usr/bin/env bash
# DEP-1: one-command control-plane bringup on the Linux VM. See DEPLOY.md for full setup.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Set JWT_SECRET (openssl rand -hex 32) and the domain, then re-run."
  exit 1
fi

docker compose up -d --build
./init-ollama.sh

# Stage the Windows agent installer bundle for Caddy to serve at /dist/.
rm -rf agent-dist && mkdir -p agent-dist
cp agent/install.ps1 agent-dist/install.ps1
( cd agent && zip -qr ../agent-dist/agent-bundle.zip agent.py scan.py tools -x '*/__pycache__/*' )
echo "Staged agent-dist/: install.ps1 + agent-bundle.zip"

# shellcheck disable=SC1091
source .env 2>/dev/null || true
echo "Varuna control plane up. UI: https://${VARUNA_DOMAIN:-localhost}"
