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
