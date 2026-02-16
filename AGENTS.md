# Agents

- lake-worker
  - Purpose: runs ingestion and backfill scripts
  - Entry points: ingestion/cli.py and ingestion/jobs/slice_runner.py
  - Storage: writes NDJSON to data/raw/** paths

- lake-api
  - Purpose: serves Data Lake endpoints for internal use
  - Entrypoint: api/main.py via Uvicorn
  - Health: GET /healthz

Notes
- External source: Environment Agency Flood Monitoring (hydrology, rainfall)
- Date params: use YYYY-MM-DD (startdate/enddate) for readings

