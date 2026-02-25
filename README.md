# City Traffic NLQ

End-to-end data pipeline for NYC motor vehicle collision records, prepared for geospatial search and semantic retrieval workflows.

## Why this project matters

- Converts raw crash CSV data into query-ready MongoDB documents.
- Adds geospatial primitives (`LOCATION` GeoJSON + `geohash`) for low-latency location queries.
- Generates text embeddings to support natural language search over crash context.
- Includes operational checks and benchmark query scripts.

## Repository layout

```
city-traffic-nlq/
├── src/city_traffic_nlq/        # Core reusable pipeline modules
├── scripts/                     # Numbered compatibility entrypoints
├── pyproject.toml               # Installable package + CLI config
├── requirements.txt             # Runtime dependencies
├── .env.example                 # Environment variable template
└── README.md
```

## Quick setup

1. Create and activate a Python virtual environment.
2. Install dependencies:
	```bash
	pip install -r requirements.txt
	pip install -e .
	```
3. Copy env template and set paths:
	```bash
	cp .env.example .env
	```
4. Ensure MongoDB replica set is running and reachable.

## Configuration

The pipeline uses environment variables:

- `MONGO_URI`
- `MONGO_DATABASE`
- `MONGO_COLLECTION`
- `CSV_FILE`
- `EMBEDDING_MODEL`
- `EMBEDDING_BATCH_SIZE`
- `EMBEDDING_CHECKPOINT`

Detailed local setup and command-by-command verification guide:
- `docs/LOCAL_SETUP_AND_VERIFICATION.md`
- Includes a dated execution log with live outputs from a full sample end-to-end run.

## Running the pipeline

### Option A: Modern unified CLI

```bash
traffic-pipeline import
traffic-pipeline geohash
traffic-pipeline cleanup
traffic-pipeline indexes
traffic-pipeline embeddings --limit 50000
traffic-pipeline status
traffic-pipeline test-queries
```

### Option B: Numbered script flow (legacy-compatible)

```bash
python scripts/01_import_data.py
python scripts/02_add_geohash.py
python scripts/03_fix_all_data.py
python scripts/04_create_indexes.py
python scripts/05_generate_embeddings.py --limit 50000
python scripts/06_check_status.py
python scripts/07_test_queries.py
```

## Interview talking points

- **Data engineering:** batching, cleanup, deduplication, and checkpointed jobs.
- **Search architecture:** geospatial indexing + semantic embeddings in one pipeline.
- **Operational reliability:** resumable embedding generation and status observability.
- **Refactoring:** migrated from ad-hoc scripts to a modular, maintainable package.

## Interview demo script (2 minutes)

1. **Problem statement (20s):**
	- "I built a pipeline that turns raw NYC crash data into a query-ready geospatial + semantic search dataset in MongoDB."

2. **Architecture snapshot (25s):**
	- `import` ingests CSV and normalizes types.
	- `geohash` + `cleanup` prepare spatial fields (`geohash`, GeoJSON `LOCATION`).
	- `indexes` creates high-impact query indexes.
	- `embeddings` generates vector fields for NLQ retrieval.

3. **Live command flow (45s):**
	```bash
	python -m city_traffic_nlq.cli status
	python -m city_traffic_nlq.cli test-queries
	```
	- Explain output: total coverage, index health, and query latency checks.

4. **Engineering quality improvements (20s):**
	- Moved from ad-hoc scripts to package-based modules.
	- Added a unified CLI, environment-driven config, and checkpointed embedding jobs.
	- Added reproducible runbook and dated validation logs.

5. **Production-readiness note (10s):**
	- "This repo currently contains the validated data/backend pipeline. UI integration can be layered on top using an API/dashboard service."

## Scope note

- This repository currently does **not** include a customer-facing website/UI (no frontend framework or web server app present).
- Verified scope is the backend data pipeline and query-validation scripts.
