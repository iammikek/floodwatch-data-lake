# Flood Watch Data Lake – Roadmap

## Current Milestone (Phase 1)
- Ingestion
  - Discover stations/measures in region scope; write NDJSON snapshots
  - Backfill readings by month slices with resume capability
  - Fetch EA Flood Zones 2/3 and Rivers & Sea present‑day extents
- Curation
  - Normalize/dedupe polygons and produce simplified GeoJSON for mapping
  - Store curated outputs under data/curated/ea
- API
  - FastAPI app scaffold with /healthz
  - /v1/polygons: metadata mode and inline FeatureCollection for small bbox
  - /v1/polygons/tiles: TMS tile route with bbox filtering
  - /v1/measurements: NDJSON-backed raw/hour/day with pagination
  - In‑process caching and basic per‑IP rate limits
  - MVC layout: routers, services, models, utils
  - OpenAPI updated (polygons; measurements/tiles ongoing)
- Tooling & Tests
  - Docker Compose for lake‑worker and lake‑api
  - Makefile targets for up/down/logs and containerized tests (test, test‑api)

## Done So Far
- EA ingestion stable for Somerset (stations, measures, month‑sliced readings)
- Curated polygons generated (Flood Zones, Rivers & Sea): normalized and simplified
- /v1/polygons implemented with inline small‑bbox support and metadata responses
- /v1/polygons/tiles returns FeatureCollections filtered by tile bbox
- /v1/measurements returns raw series and hourly/daily aggregates
- In‑memory TTL cache and per‑IP rate limits; unit tests added
- MVC refactor: routes/services/models/utilities separated
- OpenAPI and tests updated; FastAPI /healthz live; Dockerized tests passing (Python 3.11)
- Makefile workflows: up/down/logs, test, test‑api

## Near‑Term Deliverables
- Integrate EA flood warnings into /v1/warnings (geometry + severity)
- Expand OpenAPI to document measurements and tiles + warnings schema
- Optional: Introduce Redis caching adapter; document error contracts
- CI uses Docker targets to run tests on push

## Next Up (Highlighted)
- Wire EA warnings feed into /v1/warnings with geometry/levels
- Complete OpenAPI for measurements/tiles/warnings
- Add configurable rate‑limit hooks and more API tests
- Evaluate Redis caching adapter and DI for cache/config

## Mid‑Term Deliverables
- PostGIS ingestion for curated polygons and time series (schemas + indexes)
- Spatial joins: station→Flood Zone/RSE membership; expose via API
- Streaming downloads for curated layers (gzip, range)
- Aggregations: daily/hourly rollups for hydrology and rainfall
- Observability: structured logs and basic metrics; SLO tracking

## Long‑Term (Phase 2)
- HiPIMS integration for corridor‑scale flood simulation and route depth
- Vector embeddings for contextual RAG; retrieval endpoints and tools
- Scheduling/orchestration for nightly jobs and event‑triggered runs

## Acceptance Criteria (Phase 1)
- EA ingestion stable: backfills and recent slices complete without errors
- Curated polygons available per region/scenario; simplified for web maps
- API operational: /healthz, /v1/polygons inline/metadata; tests green in Docker
- Documentation and OpenAPI reflect implemented endpoints and parameters

## References
- Architecture: docs/architecture-plan.md
- Project Brief: docs/project-brief.md
- OpenAPI Spec: docs/openapi-data-lake.yaml
