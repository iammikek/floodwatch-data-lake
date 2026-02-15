# Freight & Logistics Flood Intelligence Platform — Project Brief

## 1) Executive Summary & Objective

- Vision: Build an agentic flood intelligence platform for UK logistics that converts 10+ years of hydrological and weather data plus live monitoring into route‑level, vehicle‑aware decisions.
- Problem: Flooding strands vehicles, disrupts schedules, and drives costs (downtime, detours, insurance). Static flood maps lack time‑to‑impact and depth estimates per route.
- Solution: An Agentic RAG system that correlates historical and live signals to deliver “Safe‑to‑Pass” guidance at street level for specific vehicle profiles (e.g., wading depth 200 mm).
- Initial Focus: West Country corridor (M4/M5/A38) and the Somerset Levels, aligning with Flood Watch domain and existing data/tooling.

## 2) Core Technical Components

### A) Data Lake (Python / FastAPI)

- Backfill: 10 years of EA hydrometric stations (stage/level), targeted Met Office rainfall grids.
- Geospatial: PostGIS with Ordnance Survey postcode polygons and relevant flood‑risk layers.
- Terrain: DEFRA 1 m/2 m LiDAR to estimate water depth relative to carriageway elevations.
- Database: Postgres 16 + PostGIS + pgvector for spatial and vector search.
- Storage: S3/MinIO for raw snapshots and parquet artifacts; Parquet via PyArrow.
- Orchestration: Dagster (recommended) for backfills, nightly aggregations, embedding refresh.
- API: FastAPI exposing contracts for measurements, warnings, forecast, and RAG retrieval.
- OpenAPI: docs/openapi-data-lake.yaml
- Endpoints:
  - GET /v1/measurements: station_id/from/to/aggregate/bbox → time series + metadata
  - GET /v1/warnings: bbox/region/since → active warnings with geometry and severity
  - GET /v1/forecast: region → 5‑day outlook
  - GET /v1/retrieve-context: region/route/time_window/query → signals + retrieved snippets
  - POST /v1/jobs/backfill: dataset/from/to/slice_size → job id + status URL
- SLAs: p99 < 2 s for standard queries; structure errors; partial results allowed.
- Security: Bearer service tokens; least‑privilege scopes; per‑token/IP rate limits; audit logs.

### B) AI Orchestration (Agentic RAG with MCP)

- Tools (MCP): check_route_depth, get_flood_lag_time, QueryMeasurements, QueryWarnings, RetrieveContext.
- Reasoning Loop:
  - Detect heavy rain events and relevant catchments.
  - Compute lag time from rainfall to river response for the route corridor.
  - Estimate depth vs. vehicle wading limit and classify passability with confidence.
  - Produce explanation + recommended actions and alternate routing hints.

### C) Frontend (Laravel 12.x / Livewire)

- App: Flood Watch (Laravel 12) provides UI, auth, orchestration, and caching.
- Fleet Command: Dashboard for managers to enter postcodes or upload GPX routes.
- Alerts: Real‑time notifications when predicted flood impacts scheduled routes.
- Integration: Laravel calls lake APIs; thin cache of recent results; Octane for concurrency; Horizon for workers.

## 3) Logistics‑Specific Requirements

- Vehicle Profiles: Registry of wading depth, ground clearance, weight class; assign to routes.
- Route Resilience Score (1–10): Combines historic flood frequency, current rain, catchment lag, and exposure to flood‑prone segments.
- Alternative Routing: Integrate routing APIs (e.g., Google/Mapbox) to compute “Dry Path” variants avoiding polygons where predicted depth > X mm.
- Auditability: Persist inputs, versioned models, and decisions for compliance and post‑event analysis.

## 4) Success Metrics (KPIs)

- Accuracy: Predicted depth within ±10 cm of historical marks for validation sites.
- Latency: MCP tool response < 2 s for 10‑year queries on constrained corridors.
- Impact: Reduced stranded vehicle incidents and route diversions for pilot fleets.
- Coverage: % of routes with valid lag‑time and depth predictions in the focus area.

## 5) Initial Geographic Focus

- Corridor: West Country (M4/M5/A38) and the Somerset Levels.
- Watchpoints:
  - M5 J24 / A38 (North Petherton): monitor Northmoor Pumping Station & River Parrett (Bridgwater).
  - A361 East Lyng → Burrowbridge: monitor Currymoor Pumping Station & River Tone.
  - M5 / A38 (Gloucestershire/Bristol): monitor Colliters Brook & River Avon (Bristol).
  - Somerset Levels Moors: Saltmoor, Northmoor, King’s Sedgemoor Drain (reservoir behavior).
- High‑Value Data:
  - EA Hydrology (Parrett & Tone catchments): 10‑year stage series for key stations.
  - Somerset Rivers Authority briefings: qualitative signals for pumping/defense status (RAG).
  - DEFRA LiDAR (1 m): elevation for depth over road; rasterio‑based profiling along routes.

## 6) Technical Requirements (Data Lake)

- Language & API: Python 3.11+, FastAPI + Uvicorn, Pydantic models, httpx clients.
- DB & Migrations: Postgres 16, PostGIS, pgvector; SQLAlchemy (async) + GeoAlchemy2; Alembic.
- Storage: S3/MinIO (boto3), Parquet (PyArrow), optional DuckDB for local analytics.
- ETL: Dagster jobs for backfills (date‑sliced), nightly aggregations, embedding refresh.
- Workers: Celery (Redis/RabbitMQ) or Dramatiq; APScheduler for lightweight cron.
- Embeddings: sentence‑transformers/OpenAI; IVFFlat/HNSW indexes in pgvector.
- Geospatial Ops: ST_Intersects/ST_DWithin/ST_Contains; spatial indexes for bbox/route queries.
- Caching/Quotas: Redis; stale‑while‑revalidate; per‑token/IP rate limits.
- Observability: Prometheus metrics, OpenTelemetry traces, Sentry; structured JSON logs.
- Testing: pytest, Hypothesis, Testcontainers (Postgres), golden‑file contract tests.

## 7) Security & Governance

- Secrets: Environment‑scoped tokens; rotate regularly; encrypt at rest and in transit.
- Access: Separate roles for raw snapshots vs. curated tables; strict prod read‑only for app tokens.
- Compliance: Data lineage for each decision; store source timestamps and versions.

## 8) Delivery Phases

- Phase 1 — Corridor Pilot: Ingest backfill for Parrett & Tone catchments; implement /v1 endpoints; vehicle‑aware depth estimation; Fleet Command MVP in Laravel.
- Phase 2 — Resilience Scoring: Calibrate Route Resilience Score; alternate routing integration; alerting.
- Phase 3 — Scale‑Out: Expand to additional corridors; optimize indexes; harden SLAs and quotas.

## 9) Interfaces & Contracts (Examples)

- measurements: { station: { id, name, lat, lng }, series: [{ t, value, agg, quality }] }
- warnings: [{ id, severity, title, issued_at, updated_at, geometry, source }]
- retrieve‑context: { signals: {...}, snippets: [{ source, text, score }], window: { from, to } }

## 10) Alignment with Flood Watch

- Main App: Flood Watch is a Laravel 12 application integrating EA flood data and National Highways incidents for the South West; it uses Livewire, Redis caching, and OpenAI tool calling.
- Integration: Flood Watch calls the lake’s HTTP APIs for hydrological signals and RAG context; keeps orchestration, dashboards, and cache warming on the Laravel side.

## 11) “Previsico‑Lite” Scope & Trade‑Offs

- Positioning: Deliver a lightweight, open‑data version inspired by Previsico’s depth‑aware flood intelligence, focused on the West Country corridor and Somerset Levels with pragmatic methods and transparent limits.
- Must‑Haves:
  - Route‑level “Safe‑to‑Pass” classification using vehicle profiles (wading depth, clearance).
  - Depth‑over‑road estimates along priority segments using DEFRA LiDAR + hydrological signals.
  - Catchment lag estimation using historical cross‑correlation between rainfall and river stage.
  - Alerts and Route Resilience Score integrated into the Laravel Fleet Command dashboard.
- Simplifications vs. Full Hydrodynamic Models:
  - No proprietary 2D hydrodynamic simulation; use LiDAR‑derived depressions and stage‑to‑depth heuristics.
  - Limited spatial scope (priority corridors, watchpoints) to keep compute and data volume manageable.
  - Coarser temporal resolution for backfills (e.g., hourly aggregates) when sufficient for routing.
  - Emphasis on explainability and auditable inputs over black‑box model complexity.
- Non‑Goals (Phase 1):
  - National coverage beyond the defined corridor.
  - Real‑time street‑scale pluvial modeling for entire cities.
  - High‑precision hydraulic calibration for every micro‑catchment.
- Validation Plan:
  - Select benchmark segments (e.g., A361 East Lyng → Burrowbridge, M5 J24 → A38).
  - Compare predicted depths against historical marks, incident logs, and EA post‑event reports.
  - Iterate thresholds for “safe”, “caution”, “no‑go” by vehicle class until KPI targets are met.

## 12) Optional Hydrodynamics Integration (Shallow Water Equations with HiPIMS‑CUDA)

- Purpose: For pilot corridors and watchpoints, optionally run a GPU‑accelerated 2D shallow water solver to estimate depth‑over‑road during events. This complements the heuristic depth approach and provides stronger physical grounding where GPUs are available.
- Solver: HiPIMS‑CUDA solves the 2D shallow water equations on a uniform rectangular grid using Godunov‑type finite volume schemes with well‑balanced source term treatments, friction (e.g., Manning), rainfall/boundary forcing, and robust wetting/drying.
- Python Access: Use the Python tooling exposed for HiPIMS to prepare inputs, run simulations, and read outputs from Python without binding directly to CUDA/C++; treat the solver as a compute backend invoked by Dagster jobs.
- Inputs Mapping:
  - DEM: DEFRA LiDAR tiles merged and resampled to 2–5 m resolution for corridor‑scale tiles (1 m for micro‑sites if runtime allows).
  - Land Cover → Friction: map OS land cover classes to Manning’s n rasters (urban, grassland, open water, etc.).
  - Rainfall: gridded rainfall time series for the domain (from radar/NWP or EA/Met Office products); support spatiotemporal coverages.
  - Boundary Conditions: gauge‑derived inflows/outflows at domain edges (EA stations) and tidal levels where relevant (Severn estuary influence).
  - Initial Water: dry DEM or steady‑state spin‑up for rivers/moors where needed.
- Runtime Strategy:
  - Domain Tiling: pre‑define tiles covering A38, A361 watchpoints, and M5 J24 area; snap to uniform grid; cache domain metadata.
  - Triggered Runs: start on detected heavy rain or rising stage; simulate forecast horizon with observed/forecast forcing.
  - Performance Targets: prioritize 2–5 m cell size to keep wall‑clock < real‑time; degrade resolution gracefully under load.
- Outputs & Post‑Processing:
  - Depth Rasters: periodic water‑depth rasters per tile; store as Cloud‑Optimized GeoTIFF or Parquet arrays with spatial index.
  - Route Sampling: sample along route polylines to compute depth profiles and max depth; return “safe/caution/no‑go” vs vehicle thresholds.
  - Provenance: attach forcing timestamps, DEM/LiDAR versions, and friction maps to each run for auditability.
- Orchestration:
  - Dagster job creates input folders (mesh/fields), writes DEM.txt, friction, rainfall, boundary files, and times_setup.
  - Launch solver process on a GPU node; monitor progress; on completion, ingest outputs to S3 and index in Postgres (raster footprints + metadata).
  - Expose summaries via /v1/retrieve‑context and a specific /v1/route‑depth endpoint.
- Licensing & Packaging:
  - HiPIMS‑CUDA is GPLv3; keep it isolated as an optional service to ensure license compliance if the main stack is not GPLv3.
  - Package inputs/outputs via well‑defined folders and JSON manifests to allow swapping solvers or running CPU fallbacks.
- Fallback Path:
  - If GPUs are unavailable, run a simplified local‑inertial SWE or depth‑from‑stage heuristic on the same tiles; keep endpoint contracts identical.

— End of Brief —
