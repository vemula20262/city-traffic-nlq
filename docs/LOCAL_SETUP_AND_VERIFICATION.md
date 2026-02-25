# Local Setup and Verification Runbook

This document captures the exact process used to bring the project up locally and verify that it works.

## 1) Prepare Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

What this does:
- Creates an isolated environment.
- Installs runtime dependencies.
- Installs this repo as an editable package (so CLI and `src/` imports work).

## 2) Start MongoDB (Docker, replica set mode)

The project default URI expects replica set mode:
- `mongodb://localhost:27017/?replicaSet=rs0`

Commands:

```bash
open -a Docker
docker rm -f city-traffic-mongo >/dev/null 2>&1 || true
docker run -d --name city-traffic-mongo -p 27017:27017 mongo:7 --replSet rs0 --bind_ip_all
```

Initialize replica set:

```bash
docker exec city-traffic-mongo mongosh --quiet --eval "try { rs.status().ok } catch (e) { rs.initiate({_id:'rs0', members:[{_id:0, host:'localhost:27017'}]}); 1 }"
```

Expected output:
- `1` (replica set healthy or successfully initiated)

## 3) Smoke-test project health

### Syntax/import checks

```bash
.venv/bin/python -m compileall -q src scripts
.venv/bin/python -c "import city_traffic_nlq; import city_traffic_nlq.cli as c; print('imports_ok')"
```

Expected output:
- `imports_ok`

### CLI command listing

```bash
.venv/bin/python -m city_traffic_nlq.cli --help
```

Expected behavior:
- Shows commands: `import`, `geohash`, `cleanup`, `indexes`, `embeddings`, `status`, `test-queries`.

### Runtime check against DB

```bash
.venv/bin/python -m city_traffic_nlq.cli status
```

Current expected output for a fresh DB:
- `Total docs: 0`
- No errors.

### Legacy script compatibility check

```bash
.venv/bin/python scripts/06_check_status.py
```

Expected:
- Same output as the CLI `status` command.

## 4) What was fixed for reliability

`src/city_traffic_nlq/cli.py` now handles expected runtime failures cleanly:
- Missing file errors (e.g., CSV path) show concise message.
- Mongo connection errors show concise message and next step.

This avoids long tracebacks during demos/interviews.

## 5) End-to-end run sequence (after setting CSV path)

Set `.env` from `.env.example`, then run:

```bash
.venv/bin/python -m city_traffic_nlq.cli import
.venv/bin/python -m city_traffic_nlq.cli geohash
.venv/bin/python -m city_traffic_nlq.cli cleanup
.venv/bin/python -m city_traffic_nlq.cli indexes
.venv/bin/python -m city_traffic_nlq.cli embeddings --limit 50000
.venv/bin/python -m city_traffic_nlq.cli status
.venv/bin/python -m city_traffic_nlq.cli test-queries
```

## 6) Troubleshooting quick notes

- `Connection refused`:
  - Docker daemon not running or container stopped.
  - Fix: start Docker Desktop and re-run container commands.
- `MongoDB error ... ReplicaSetNoPrimary`:
  - Replica set not initialized.
  - Fix: run the `rs.initiate(...)` command above.
- `Missing required file`:
  - CSV path not valid.
  - Fix: update `CSV_FILE` in `.env`.

## 7) Actual execution log (2026-02-24)

This section records what was executed in this repo during live validation.

### Context
- Full NYC CSV was not found locally, so a controlled sample file was created:
  - `docs/examples/sample_crashes.csv` (3 rows)
- Mongo was run in Docker using replica set mode (`rs0`) to match project defaults.

### Commands executed

```bash
# Start Mongo replica set in Docker
open -a Docker
docker rm -f city-traffic-mongo >/dev/null 2>&1 || true
docker run -d --name city-traffic-mongo -p 27017:27017 mongo:7 --replSet rs0 --bind_ip_all
docker exec city-traffic-mongo mongosh --quiet --eval "try { rs.status().ok } catch (e) { rs.initiate({_id:'rs0', members:[{_id:0, host:'localhost:27017'}]}); 1 }"

# Reset collection for clean test run
docker exec city-traffic-mongo mongosh --quiet --eval "db.getSiblingDB('traffic').traffic.drop(); print('dropped')"

# Pipeline run
CSV_FILE="/Users/thusharreddy/city-traffic-nlq/docs/examples/sample_crashes.csv" .venv/bin/python -m city_traffic_nlq.cli import --no-confirm
.venv/bin/python -m city_traffic_nlq.cli geohash
.venv/bin/python -m city_traffic_nlq.cli cleanup
.venv/bin/python -m city_traffic_nlq.cli indexes
.venv/bin/python -m city_traffic_nlq.cli status
.venv/bin/python -m city_traffic_nlq.cli test-queries
EMBEDDING_CHECKPOINT="/Users/thusharreddy/city-traffic-nlq/logs/sample_embedding_checkpoint.json" .venv/bin/python -m city_traffic_nlq.cli embeddings --limit 3
.venv/bin/python -m city_traffic_nlq.cli status
```

### Observed results
- Import: `3` docs inserted.
- Geohash: `3` docs updated.
- Cleanup: `3` valid GeoJSON locations.
- Indexes: all expected indexes created (`_id_`, shard/date, date, collision unique, borough, 2dsphere).
- Query tests:
  - Times Square near query returned `1` result.
  - Manhattan count returned `1`.
  - 2024 regex date count returned `3`.
- Embeddings: `3/3` docs embedded (100%).
- Final status:
  - `Total docs: 3`
  - `With geohash: 3`
  - `With GeoJSON: 3`
  - `With embeddings: 3`

### Notes
- This confirms the full pipeline is operational end-to-end in local environment.
- For production-scale validation, replace sample file with full NYC CSV and rerun same command sequence.
