#!/usr/bin/env bash
# DEP-1: one-command control-plane bringup on the Linux VM.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example, edit it for a real domain."; }

docker compose up -d
./init-ollama.sh

# shellcheck disable=SC1091
source .env 2>/dev/null || true
echo "Varuna control plane up. UI: https://${VARUNA_DOMAIN:-localhost}"
