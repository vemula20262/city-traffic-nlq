# Submission Audit Report (2026-02-24)

This report summarizes what was found in `/Users/thusharreddy/Desktop/submission` and what was verified.

## 1) Artifacts found in submission folder

- `DDS_PROJECT.mp4`
- `DDS_Project_final_PDF.pdf`
- `MongoDB AWS Setup and Loadtesting.zip`
- `city-traffic-nlq-dashboard.zip`
- `dags.zip`

## 2) Dashboard archive inspection

Archive: `city-traffic-nlq-dashboard.zip`

Contains:
- Frontend React/Vite app (`frontend/` with `package.json`, `src/App.jsx`)
- Backend Flask app (`backend/app.py`)
- EC2 Mongo connection helper (`connect_mongodb_ec2.py`)
- Additional docs/readmes/sample data

### Corruption note
- One screenshot file inside the ZIP is corrupted (CRC error), but source code files extract correctly.
- Corrupted file does not impact code verification.

## 3) Feature verification (what exists in code)

### Customer query capability
- Frontend includes NLQ/search UI in `frontend/src/App.jsx`.
- Frontend calls backend endpoint `POST /api/vector-search`.
- Backend implements `POST /api/vector-search` in `backend/app.py`.

### Data visualization capability
- Frontend includes:
  - Metric comparison table (multi-year)
  - Incident map (Leaflet)
  - Metric insights panel
- Backend implements data endpoints:
  - `GET /api/traffic-stats`
  - `GET /api/incidents`
  - `GET /api/metric-insights`
  - `GET /api/filters`

## 4) Runtime verification performed

### Backend startup
- Command: run `backend/app.py`.
- Result: Flask server starts, but Mongo data layer fails due to EC2 SSH tunnel timeout.
- Health endpoint response:
  - `GET /` => `{ "status": "ok", "mongodb": "disconnected" }`
- Data endpoint response:
  - `GET /api/filters` => 500 with `Database not available`.

### Frontend build
- Commands: `npm ci` then `npm run build` in `frontend/`.
- Result: ✅ successful production build with Vite.

## 5) Why full customer flow is currently blocked

The submitted backend is wired to AWS EC2 Mongo via SSH tunnel (`connect_mongodb_ec2.py`) and does not default to local MongoDB URI.

So on this machine, without reachable EC2 + working credentials/network path:
- UI can compile,
- API server can run,
- but customer query/data endpoints cannot return live data.

## 6) Conclusion

- The submitted project **does include** a customer-facing dashboard (query + visualization code exists).
- I **verified code presence and frontend build success**.
- I **verified backend process startup**, but live data APIs are blocked by external EC2 Mongo connectivity requirements.

## 7) Recommended next step

For reliable interview demos, use one of these:
1. Add local Mongo fallback mode in backend (`MONGO_URI` env-based) and run against local dataset.
2. Keep EC2 mode but document and verify tunnel preconditions before demo.
