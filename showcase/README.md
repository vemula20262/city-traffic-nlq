# Showcase App (No-AWS Demo Path)

This folder provides a customer-facing demo path without AWS access:
- React frontend (`showcase/frontend`)
- Flask API backend (`showcase/backend`)
- Local distributed MongoDB replica set (`showcase/infra/replicaset`)

## 1) Start distributed MongoDB locally

```bash
cd showcase/infra/replicaset
docker compose up -d
./init-rs.sh
./get-primary-uri.sh
```

This creates a 3-node MongoDB replica set exposed on:
- `localhost:27017`
- `localhost:27018`
- `localhost:27019`

The helper `get-primary-uri.sh` prints a direct URI to the current primary.

## 2) Seed demo data (from main pipeline)

From repo root, run:

```bash
MONGO_URI="$(showcase/infra/replicaset/get-primary-uri.sh)" CSV_FILE="$(pwd)/docs/examples/sample_crashes.csv" .venv/bin/python -m city_traffic_nlq.cli import --no-confirm
MONGO_URI="$(showcase/infra/replicaset/get-primary-uri.sh)" .venv/bin/python -m city_traffic_nlq.cli geohash
MONGO_URI="$(showcase/infra/replicaset/get-primary-uri.sh)" .venv/bin/python -m city_traffic_nlq.cli cleanup
MONGO_URI="$(showcase/infra/replicaset/get-primary-uri.sh)" .venv/bin/python -m city_traffic_nlq.cli indexes
MONGO_URI="$(showcase/infra/replicaset/get-primary-uri.sh)" EMBEDDING_CHECKPOINT="$(pwd)/logs/showcase_embedding_checkpoint.json" .venv/bin/python -m city_traffic_nlq.cli embeddings --limit 100
```

## 3) Run backend locally

```bash
./showcase/run_backend_local.sh
```

Backend URL: `http://localhost:5000`

## 4) Run frontend locally

```bash
./showcase/run_frontend_local.sh
```

Frontend URL: `http://localhost:5173`

If frontend and backend run on different domains, set:
- `VITE_API_BASE_URL=https://your-backend-domain`

## 5) Free hosting (recommended)

### Option A (easy): Render + Vercel + MongoDB Atlas Free Tier

1. **MongoDB Atlas**
   - Create free M0 cluster (already distributed/replica-set based).
   - Create DB user and IP allowlist.
   - Copy SRV connection string.

2. **Backend on Render (Free Web Service)**
   - Root directory: `showcase/backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn --bind 0.0.0.0:$PORT app:app`
   - Env vars:
     - `MONGO_URI=<Atlas connection string>`
     - `MONGO_DB=traffic`
     - `MONGO_COLLECTION=traffic`

3. **Frontend on Vercel (Free)**
   - Root directory: `showcase/frontend`
   - Build: default Vite settings
   - Env var:
     - `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`

## 6) What to showcase in interview

- Distributed DB story:
  - Local: 3-node Mongo replica set (or Atlas distributed cluster).
- Product story:
  - NLQ query box + map visualization + metrics + insights.
- Engineering story:
  - Backend now uses environment-driven Mongo URI (no AWS hard dependency).
