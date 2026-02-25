#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/showcase/frontend"

if [[ ! -d node_modules ]]; then
  npm install
fi

VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:5050}" npm run dev
