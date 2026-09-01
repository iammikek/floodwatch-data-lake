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

How to Start Collector
- Prereqs: Docker Desktop installed; running on macOS (Apple Silicon supported).
- Start worker and run hydrology backfill for a region:
  - FROM=YYYY-MM TO=YYYY-MM REGION=SOM MAX_STATIONS=1 MAX_MEASURES=1 ./scripts/run-collector.sh
- **Prediction corridor (4 gauges, A361 Muchelney):**
  - FROM=2022-01 TO=YYYY-MM ./scripts/run-corridor-backfill.sh
  - Docs: `docs/prediction-corridor-backfill.md`
- Alternative via Makefile:
  - FROM=YYYY-MM TO=YYYY-MM REGION=SOM make collector
  - FROM=2022-01 TO=YYYY-MM make corridor-backfill

Saved Data Format
- Path pattern: data/raw/ea/readings/{measure_id}/{YYYY}-{MM}.ndjson.gz
- Each line: NDJSON object with keys like @id, dateTime (UTC ISO-8601), value, measure.
- Stations and measures discovery outputs:
  - data/raw/ea/stations/*.ndjson.gz
  - data/raw/ea/measures/*.ndjson.gz

Failure & Restart
- Idempotent: re-running the same slice rewrites the same file deterministically.
- If interrupted: rerun the same command; use MAX_STATIONS/MAX_MEASURES to throttle.
- Network errors: the EA client retries with backoff; repeated 5xx will surface as errors.
- To inspect recent logs:
  - make logs-worker
