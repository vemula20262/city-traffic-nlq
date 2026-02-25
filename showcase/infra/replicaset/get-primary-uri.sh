#!/usr/bin/env bash
set -euo pipefail

primary_host_port=$(docker exec city-mongo1 mongosh --quiet --eval '
const primary = rs.status().members.find(m => m.stateStr === "PRIMARY");
print(primary ? primary.name : "");
')

if [[ -z "$primary_host_port" ]]; then
  echo "Could not determine primary" >&2
  exit 1
fi

primary_port="${primary_host_port##*:}"
echo "mongodb://localhost:${primary_port}/?directConnection=true"
