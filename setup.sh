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

# shellcheck disable=SC1091
source .env 2>/dev/null || true
echo "Varuna control plane up. UI: https://${VARUNA_DOMAIN:-localhost}"
