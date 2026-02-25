#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PRIMARY_URI="$($REPO_ROOT/showcase/infra/replicaset/get-primary-uri.sh)"

cd "$REPO_ROOT/showcase/backend"
MONGO_URI="$PRIMARY_URI" PORT="${PORT:-5050}" "$REPO_ROOT/.venv/bin/python" app.py
