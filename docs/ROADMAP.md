# Flood Watch Data Lake – Roadmap

Last aligned: **2026-09-18** (post AfA435 multi-storm + finer DEM prep).

Product surface for History accuracy lives in Flood Watch (Live | History | Transport). This repo owns ingestion, analytics APIs, and DEM/volume contracts.

## Status snapshot

| Track | Status |
|-------|--------|
| Phase 1 — EA ingest + polygons + measurements + live warnings | ✅ Done |
| Place History accuracy ladder (through 5a) | ✅ Done — see [accuracy-ladder.md](accuracy-ladder.md) |
| HiPIMS / depth-over-road solver | Deferred — DEM prep only ([hipims-prep.md](hipims-prep.md)) |
| PostGIS / precomputed rollups / Redis | Mid-term backlog |

## Done (Phase 1 + place History)

### Ingestion & curation
- EA stations/measures discovery; month-sliced readings with resume
- Corridor hydrology backfill (A361 Muchelney; Great Bow primary / Gaw exclude_from_analogue)
- Flood Zones 2/3 + Rivers & Sea extents → curated GeoJSON under `data/curated/ea`
- LiDAR Composite DTM ingest (2 m core, 1 m hotspot) + provenance

### API
- `/healthz`, `/v1/polygons`, `/v1/polygons/tiles`, `/v1/measurements`, `/v1/warnings`
- `/v1/predictions` + `/v1/predictions/corridors` — historic analogue hindcast
- `/v1/storms` — curated storm catalogue (extents, warning evidence)
- `/v1/storms/{id}/volume` — gauge-rise bathtub + A361 road strip (`resolution=auto|1m|2m`)
- `/v1/storms/{id}/warnings` — AfA435 curated issue rows
- `/v1/places/{id}/dem` — DTM availability + HiPIMS pilot status
- In-process TTL cache + per-IP rate limits; OpenAPI + Dockerized tests/CI

### History accuracy ladder (A361 Muchelney)
1. Honesty labels (planning FZ ≠ event edge) ✅
2. Curated event GeoJSON extents ✅
3. LiDAR DTM 2 m core ✅
4. Volume v0/v1 (bathtub + gauge rise + road strip + compare) ✅
4c. AfA435 historic warnings (Chandra, Dennis, 2014; Ciara empty-window notes) ✅
5a. Finer DEM 1 m hotspot + volume resolution policy ✅
5b. HiPIMS CUDA / depth-over-road — **not started** (prep config only)

### Tooling
- Docker Compose `lake-api` / `lake-worker`; Makefile up/logs/test
- Why Python (not Laravel): [README.md](../README.md)

## Next up (product priority)

Ordered for A361 place value — not Redis-first:

1. **Gaw scale reconcile** — re-admit Gaw to analogues once FM vs Thorney Mill proxy scales match (or keep excluded with clearer live/history copy)
2. **1 m core DEM** (or mosaic) — so volume `auto` can prefer 1 m without undercounting outside the hotspot
3. **Postgres / precompute** — stop scanning NDJSON for every hindcast; store analogue indexes / volume snapshots
4. **HiPIMS Phase 2** — only after (2) and a license-isolated solver service ([hipims-prep.md](hipims-prep.md), [architecture-plan.md](architecture-plan.md))

## Near-term (infra polish)

- Optional Redis caching adapter + DI for cache/config
- Stronger structured error contracts; broaden API tests where gaps remain
- Observability: structured logs, basic metrics, SLO tracking

## Mid-term

- PostGIS for curated polygons + time series (schemas/indexes)
- Spatial joins: station → Flood Zone / RSE membership
- Streaming downloads for curated layers (gzip, range)
- Daily/hourly rollups for hydrology (and rainfall when ingested)
- `GET /v1/polygons/depth` — polygon depth summaries **after** HiPIMS depth rasters exist

## Long-term (Phase 2+)

- HiPIMS corridor flood simulation + route depth / passability vs vehicle wading limits
- Vector embeddings + RAG retrieval endpoints/tools
- Scheduling/orchestration for nightly jobs and event-triggered runs
- Multi-place corridors beyond `a361-muchelney`

## Acceptance criteria

### Phase 1 (met)
- EA ingest stable for SOM; curated polygons for maps
- Core read APIs green in Docker CI; OpenAPI covers shipped routes

### Place History (met for Muchelney ladder through 5a)
- Storm select shows extents, as-of prediction, volume, AfA435 evidence
- Volume never mocks; summer control returns `available: false`
- DEM resolution honesty (hotspot 1 m does not silently replace 2 m bathtub)

### Phase 2 (not met)
- Depth-over-road from hydrodynamic run, not bathtub alone
- Job API for scenario runs; GPLv3 solver isolated from main API image

## Future API sketch (depth summaries)

Depends on HiPIMS depth rasters:

- `GET /v1/polygons/depth`
  - Query: `dataset`, `region`, `scenario` (RSE), `format`, optional `bbox`
  - Returns per-feature `{ min, mean, max, p95 }` + provenance `{ source: hipims, as_of }`

## References

- [accuracy-ladder.md](accuracy-ladder.md) — History step checklist
- [hipims-prep.md](hipims-prep.md) — DEM domain + deferred solver
- [place-lidar-volume.md](place-lidar-volume.md) — volume method
- [architecture-plan.md](architecture-plan.md) — Phase 2 HiPIMS design
- [project-brief.md](project-brief.md) — product vision
- [openapi-data-lake.yaml](openapi-data-lake.yaml)
- Flood Watch: `docs/cockpit-use-cases.md` (Live | History | Transport)
