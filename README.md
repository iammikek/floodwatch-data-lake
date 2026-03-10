# Flood Watch Data Lake

Data ingestion and API for UK flood monitoring, curated polygons, and time‑series access.

## Overview
- Services
  - lake-worker: runs ingestion and backfill jobs
  - lake-api: FastAPI service serving Data Lake endpoints
- Sources
  - Environment Agency Flood Monitoring (hydrology, rainfall, flood zones, RSE)
- Data layout
  - Raw readings: data/raw/ea/readings/{measure_id}/{YYYY}-{MM}.ndjson.gz
  - Discovery outputs: data/raw/ea/stations/*.ndjson.gz; data/raw/ea/measures/*.ndjson.gz
  - Curated polygons: data/curated/ea/*.geojson

## Prerequisites
- Docker Desktop installed (macOS, Apple Silicon supported)

## Quick Start
- Start services:
  - make up
- Tail logs:
  - make logs-worker
  - make logs-api
- Restart API:
  - make restart-api

## Collect Data
- Run collector (month range and region):
  - FROM=YYYY-MM TO=YYYY-MM REGION=SOM MAX_STATIONS=1 MAX_MEASURES=1 ./scripts/run-collector.sh
- Makefile shortcut:
  - FROM=YYYY-MM TO=YYYY-MM REGION=SOM make collector
- Notes
  - Idempotent writes per slice
  - Re-run same slice to resume after interruptions

## API
- Base: lake-api (Uvicorn) started by docker compose
- Health:
  - GET /healthz
- Polygons:
  - GET /v1/polygons?dataset=flood_zones&region=SOM&inline=true&bbox=w,s,e,n
  - GET /v1/polygons/tiles/{dataset}/{z}/{x}/{y}?region=SOM
- Measurements:
  - GET /v1/measurements?measure_id={id}&from=YYYY-MM-DDTHH:MM:SSZ&to=YYYY-MM-DDTHH:MM:SSZ&aggregate=raw|hour|day&page=1&limit=500
- Rate limits and caching:
  - In‑process TTL cache; per‑IP quotas

## Testing
- API tests (inside lake-api container):
  - make test-api
- Ingestion tests (inside lake-worker container):
  - make test

## CI
- CI uses Docker targets to run tests on push

## Documentation
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- OpenAPI: [docs/openapi-data-lake.yaml](docs/openapi-data-lake.yaml)
- Architecture: [docs/architecture-plan.md](docs/architecture-plan.md)
- Data Sources: [docs/data-sources.md](docs/data-sources.md)
- Project Brief: [docs/project-brief.md](docs/project-brief.md)
- Agents: [AGENTS.md](AGENTS.md)

## API Examples
- Measurements (raw)
  
  ```bash
  curl "http://localhost:8000/v1/measurements?measure_id=TESTMEASURE&from=2026-03-10T00:00:00Z&to=2026-03-10T02:00:00Z&aggregate=raw&limit=100"
  ```

- Measurements (hourly)
  
  ```bash
  curl "http://localhost:8000/v1/measurements?measure_id=TESTMEASURE&from=2026-03-10T00:00:00Z&to=2026-03-10T02:00:00Z&aggregate=hour&limit=100"
  ```

- Polygons (inline metadata + small bbox)
  
  ```bash
  curl "http://localhost:8000/v1/polygons?dataset=flood_zones&region=SOM&format=simplified&inline=true&bbox=-3.90,50.90,-2.20,51.40"
  ```

- Polygons tiles (Web Mercator)
  
  ```bash
  curl "http://localhost:8000/v1/polygons/tiles/flood_zones/10/511/340?region=SOM&format=simplified"
  ```

- Warnings (with geometry; min severity = Flood Alert)
  
  ```bash
  curl "http://localhost:8000/v1/warnings?region=SOM&min_severity=3"
  ```
 
- Warnings (county filter, no region)
  
  ```bash
  curl "http://localhost:8000/v1/warnings?county=Somerset&min_severity=2"
  ```
