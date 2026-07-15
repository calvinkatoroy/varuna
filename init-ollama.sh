#!/usr/bin/env bash
# DEP-3: one-time Ollama model pull. Safe to re-run (ollama skips if already present).
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
echo "Pulling ${MODEL} (one-time, several GB)..."
docker compose exec -T ollama ollama pull "${MODEL}"
echo "Model ${MODEL} ready."
