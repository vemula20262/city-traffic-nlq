#!/usr/bin/env bash
set -euo pipefail

for i in {1..30}; do
  if docker exec city-mongo1 mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker exec city-mongo1 mongosh --quiet --eval '
try {
  rs.status().ok;
  print("replica set already initialized")
} catch (e) {
  rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "host.docker.internal:27017" },
      { _id: 1, host: "host.docker.internal:27018" },
      { _id: 2, host: "host.docker.internal:27019" }
    ]
  });
  print("replica set initialized")
}
'
