# Builder with MCP

## Thought Process

## Short Answer

- Yes, it’s usually worth separating a 10‑year data lake/ingestion pipeline from the user‑facing Flood Watch app. The warehouse has different dependencies, scaling, SLAs, and cadence than the Livewire UI and on‑demand search.

## When Separate Is Better

- Different infrastructure: Postgres + PostGIS + pgvector, large backfills, long‑running jobs, object storage for raw dumps.
- Scaling and cost isolation: spin workers for ETL/backfill without affecting user traffic, upgrade DB independently.
- Release cadence: schema evolution and ETL changes shouldn’t block app releases.
- Security and governance: stricter access to raw data, distinct secrets and IAM.
- Performance risk: heavy aggregation or historic backfills won’t contend with UI/cache workloads.

## When to Keep It Inside

- Small scope: if you only need a few aggregates and limited history, a bounded “Analytics” module in the same repo can work.
- Shared domain code: reuse value objects/services easily, simpler local dev.
- Single datastore: if you avoid PostGIS/pgvector and keep standard MySQL/SQLite, integration overhead is low.

## Recommended Architecture

- Separate app: “flood-watch-data-lake”
  - Persistence: Postgres with PostGIS + pgvector; S3-compatible storage for raw snapshots.
  - Services: ingestion (EA measurements, flood warnings, weather), feature engineering, embeddings, retrieval API.
  - Interfaces:
    - HTTP API: region/time/route queries return structured signals and retrieved snippets.
    - MCP tools: “QueryMeasurements”, “QueryWarnings”, “RetrieveContext” for agent workflows.
  - Jobs: date‑sliced backfills, nightly aggregations, embedding refresh.
  - Auth: service tokens for the web app; principle of least privilege.
- Main app integration:
  - Call data-lake APIs for hydrological signals and RAG context.
  - Keep UI/LLM orchestration and cache warming in Flood Watch.
  - Maintain a thin cache of recent lake results to control latency/cost.

## Deployment

- Monorepo vs multi-repo:
  - Monorepo: apps/web and apps/data-lake directories; shared CI and docs; independent containers.
  - Multi-repo: clearer ownership and versioning; separate pipelines.
- Queues and scheduling: dedicated workers for backfill; cron to drive data-lake ETL; keep Flood Watch scheduler for polling/warm-cache.

## Decision Checklist

- Do you need PostGIS/pgvector and large backfills? If yes, separate.
- Do you want independent scaling and DB upgrades? If yes, separate.
- Are dev teams or release cadences different? If yes, separate.
- Is governance/privacy stricter for raw data? If yes, separate.
- If most answers are no and scope is modest, embed as a bounded module.

If you want, I can sketch the two-app monorepo layout and the initial endpoints/tools to expose from the data-lake to Flood Watch.

## Tech Choice: Laravel Integration

- Flood Watch app: Laravel 12.x (Livewire, Redis, openai-php/laravel) remains the user-facing UI and orchestration layer.
- Data lake: separate service focused on ingestion, geospatial joins, embeddings, and retrieval, backed by Postgres+PostGIS+pgvector and object storage.
- Interaction: Laravel calls lake HTTP APIs for hydrological signals and context; Laravel caches recent results and controls latency/cost.
- MCP: lake exposes tools mapped to endpoints; Laravel can trigger tools directly or via an MCP server if needed.

## Initial Data‑Lake Endpoints

- GET /v1/measurements
  - Query: station_id, from, to, aggregate (raw|hour|day), bbox(optional)
  - Returns: time series with station metadata, quality flags, aggregates
- GET /v1/warnings
  - Query: bbox, region, since
  - Returns: active warnings/alerts with geometry, severity, issued/updated times, source
- GET /v1/retrieve-context
  - Query: region, route(optional), time_window, query(optional)
  - Returns: structured signals plus retrieved snippets for RAG
- GET /v1/forecast
  - Query: region
  - Returns: 5‑day outlook and weather summary aligned to regions
- POST /v1/jobs/backfill
  - Body: dataset, from, to, slice_size
  - Returns: job id and status URL

## Auth and SLAs

- Auth: Authorization: Bearer <service_token>; tokens scoped to read‑only endpoints; least privilege.
- Rate limits: per token and per IP; burst allowance for dashboard warm‑up.
- Caching: recommend TTLs per endpoint; Laravel to use Redis with stale‑while‑revalidate for recent queries.
- Error policy: structured error payloads; partial data allowed; include source attribution and timestamps.

## Contracts (Examples)

- measurements payload: { station: { id, name, lat, lng }, series: [{ t, value, agg, quality }] }
- warnings payload: [{ id, severity, title, issued_at, updated_at, geometry, source }]
- retrieve-context payload: { signals: {...}, snippets: [{ source, text, score }], window: { from, to } }

## MCP Tools Mapping

- QueryMeasurements → GET /v1/measurements
- QueryWarnings → GET /v1/warnings
- RetrieveContext → GET /v1/retrieve-context

## Monorepo Sketch

- apps/web: Laravel Flood Watch (UI, auth, orchestration, caching)
- apps/data-lake: lake service (ingestion, features, retrieval API)
- packages/shared: shared value objects and region schemas when helpful
- infra: compose/k8s manifests, queues, scheduled jobs

## Flood Watch Integration Steps

- Add LAKE_BASE_URL and LAKE_TOKEN to environment and config.
- Create a LakeClient service to call endpoints with retry/timeouts and Redis caching.
- Wire correlation services to use lake signals and RAG snippets in summaries.
- Use Octane for API concurrency; Horizon for queue monitoring; isolate workers from web traffic.

## Data‑Lake Tech Stack (Python)

- Language: Python 3.11+ for modern async and typing.
- API: FastAPI + Uvicorn; Pydantic for request/response contracts; httpx for upstream calls.
- Database: Postgres 16 with PostGIS and pgvector; SQLAlchemy (async) + asyncpg; GeoAlchemy2 for geospatial; Alembic for migrations.
- Storage: S3/MinIO via boto3; parquet files via PyArrow for intermediate artifacts.
- ETL/Data: pandas or Polars + PyArrow; GeoPandas + Shapely for geometry ops; optional DuckDB for local analytics.
- Orchestration: Dagster (recommended) or Airflow/Temporal for backfills, nightly jobs, and dependency graphs.
- Workers: Celery (Redis/RabbitMQ) or Dramatiq for job execution; APScheduler for lightweight cron.
- Embeddings/RAG: sentence-transformers or OpenAI embeddings; store vectors in pgvector; create IVFFlat or HNSW indexes.
- Geospatial: use PostGIS functions (ST_Intersects, ST_DWithin, ST_Contains) and spatial indexes for bbox/route queries.
- Caching/Rate Limits: Redis for response caching and token quotas; stale‑while‑revalidate for low latency.
- Observability: Prometheus metrics, OpenTelemetry traces, structured JSON logs, Sentry for errors.
- Testing: pytest; property tests with Hypothesis; Testcontainers for Postgres; golden‑file tests for payload contracts.

## Minimal Scaffold Outline

- api: FastAPI app exposing /v1 endpoints; Pydantic models for contracts.
- services/ingestion: collectors for Environment Agency, National Highways, weather; writes raw snapshots to S3 and curated tables to Postgres.
- services/features: aggregations, joins, feature engineering, embeddings.
- jobs: backfill runners (date‑sliced), nightly schedulers, refresh tasks.
- db: SQLAlchemy models, migrations, index management (spatial/vector).
- clients: shared HTTP clients with retries/timeouts; auth token management.
- config: environment loading, secrets, rate limit policies.
- infra: docker-compose for app + workers + Postgres + MinIO + Redis.

## 10‑Year Backfill Plan (Phase 1)

- Scope
  - Regions: West Country corridor and Somerset Levels priority catchments (Parrett, Tone, Exe, Avon).
  - Window: Rolling 10 years (today − 10y → present), including current month partials.
  - Datasets: EA hydrology time‑series (levels/flow), HadUK‑Grid daily precipitation (CEDA), NRFA curated flows (reference), ERA5/Land (bootstrap/gap‑fill).

- Pipeline Outline
  - Station Discovery: list stations within region and enumerate measures with metadata (units, qualifiers, typical ranges).
  - Month‑Sliced Ingestion: fetch monthly slices per series with strict timeouts, retries with jitter, and rate limits.
  - Normalization: write observations with quality flags and provenance; upsert on (series_id, t).
  - Rainfall Processing: clip HadUK‑Grid NetCDF to region/catchments; compute daily aggregates (mean/max) and per‑cell totals.
  - Ledger: maintain a backfill ledger for resumability and progress tracking.
  - Storage: Postgres tables for stations, measures, observations, rainfall_cells, rainfall_daily, rainfall_region_daily.

- Operations
  - Concurrency control to respect provider limits.
  - Idempotent writes; safe re‑runs per slice.
  - Observability: metrics for slice latency, rows ingested, error rates; structured logs and trace ids.

## Acceptance Criteria (Phase 1: 10‑Year Backfill)

- Coverage
  - Hydrology: ≥ 95% of stations within scope with at least one level or flow series populated over the 10‑year window.
  - Rainfall: 100% daily coverage for selected HadUK‑Grid cells within region over the 10‑year window or documented gaps with ERA5/Land substitutions.

- Completeness & Quality
  - No duplicate (series_id, t) keys; primary key constraint enforced.
  - Missing‑day rate ≤ 1% per series per year, excluding documented outages.
  - Quality flags preserved from source; out‑of‑range values flagged against typical ranges.

- Performance
  - Month slice ingest p95 < 5 s per measure under normal conditions; automatic retry with jitter on failures.
  - End‑to‑end initial backfill finishes within the configured concurrency/rate limits for the scoped region.

- Idempotency & Resilience
  - Re‑running any month slice yields zero net new rows unless source changed.
  - Restarting after failure resumes from last successful ledger entry without manual intervention.

- Provenance & Audit
  - Each row includes source identifier and version tag; ingestion timestamp recorded.
  - Ledger exposes per‑slice status, counts, duration, and last error (if any).

- Deliverables
  - Queryable time‑series endpoints for hydrology and rainfall aggregates scoped by region and time.
  - Station/measure metadata endpoints to support selection in downstream apps.
  - Documentation for schemas, contracts, and known data caveats.

## Phase 1 Definition of Done (Checklist)

- Scope & Inputs
  - Regions finalized: Bristol, Somerset, Dorset, Devon, Cornwall.
  - Rolling window set to last 10 years.
  - Sources confirmed: EA hydrology time‑series, HadUK‑Grid daily, ERA5/Land fallback.

- Storage & Schemas
  - Tables created: stations, measures, observations, observations_daily, rainfall_cells, rainfall_daily, rainfall_region_daily.
  - backfill_ledger table deployed with unique slice keys, status, metrics, provenance.

- Raw Acquisition
  - Station discovery for in‑scope regions completed and stored.
  - Month‑sliced EA readings fetch operational with timeouts/retries.
  - HadUK‑Grid daily dataset subset downloaded and checksummed.
  - ERA5/Land hourly bootstrap path available for gaps.

- Normalization & Aggregation
  - EA snapshots parsed into observations with quality flags and source_version.
  - HadUK‑Grid clipped; per‑cell and region daily aggregates produced.
  - Daily metrics implemented: mean, max, min, p95, exceedance counts, hours above typical high.

- Quality & Validation
  - Coverage checks and thresholds enforced; partial days flagged.
  - Typical range checks active; NRFA cross‑checks for overlap stations.
  - Provenance recorded for all datasets.

- Ledger & Idempotency
  - Deterministic slice records created and updated via state machine.
  - Skips performed when artifacts match etag/hash.
  - Curated writes use upserts keyed by strong PKs.

- Observability
  - Metrics emitted per slice: duration, rows, bytes, failures.
  - Structured logs include slice identifiers and trace ids.

- APIs
  - /v1/measurements returns raw/hour/day aggregates with provenance.
  - /v1/rainfall returns per‑cell and region daily aggregates by region/time.

## Next Steps

- Finalize table schemas and ledger model aligned to the above contracts.
- Draft ingestion jobs for EA hydrology (levels/flow) and HadUK‑Grid rainfall with region clipping.
- Add metrics and dashboards for backfill progress and data quality.

## Phase 2 — HiPIMS Scenario Runner (Depth‑Over‑Road)

- Objective
  - Integrate the Loughborough HiPIMS ecosystem (hipims, pypims, hipims_io) to simulate 2D shallow‑water flows and produce route‑level depth estimates for Bristol, Somerset, Dorset, Devon, and Cornwall.
  - Expose a job‑based API and MCP tools to trigger nowcast/hindcast runs and retrieve summarized outputs for route safety classification.

- Inputs & Preprocessing
  - DEM: DEFRA LiDAR (1–2 m) mosaicked and clipped to tiles per region; sinks filled; handled via hipims_io.
  - Land Cover/Roughness: assign Manning’s n from land cover classes; store lookup and rasterize to simulation grid.
  - Rainfall Forcing:
    - HadUK‑Grid (daily) for climatology; ERA5/Land (hourly) for event forcing; interpolate to grid and time step.
  - Hydrology Boundary Conditions:
    - River stage/flow from EA stations mapped to boundary cells where appropriate; optional for river‑adjacent tiles.
  - Domain Tiling:
    - Grid tiles sized to balance resolution (1–5 m target) and runtime; overlap/buffer to reduce edge artifacts.
    - Route‑aware subsetting: prioritize tiles intersecting critical corridors; cache common tiles.

- Model Configuration
  - Resolution: start at 5 m for corridor pilot; evaluate 1–2 m for hotspots.
  - Time Step: adaptive CFL‑based stepping; target simulated horizon 6–24 h depending on scenario.
  - Schemes: use pypims defaults initially; tune solvers and boundary conditions per QA results.
  - Outputs:
    - Depth rasters per step and max‑depth composite.
    - Depth‑over‑road time series at sampled points along routes.
    - Max/mean depth summaries per road segment.

- Orchestration & Jobs
  - API
    - POST /v1/jobs/hipims-run
      - Body: { region_id, bbox|route, start_time, duration_h, grid_res_m, rainfall_source, boundary_opts, vehicle_profile? }
      - Returns: job_id and status URL.
    - GET /v1/jobs/{job_id}
      - Returns: status: queued|running|succeeded|failed; artifacts and metrics.
    - GET /v1/route-depth
      - Query: route_id|polyline, vehicle_profile, time_window
      - Returns: per‑segment depth stats; passability classification vs wading limit.
  - MCP Tools
    - RunHiPIMSScenario → POST /v1/jobs/hipims-run
    - GetRouteDepth → GET /v1/route-depth
  - Scheduling
    - Hindcast library for recent severe events for validation.
    - Nowcast runs triggered by rainfall thresholds or operator request; reuse cached tiles.

- Storage & Contracts
  - Artifacts
    - Depth rasters: Cloud‑Optimized GeoTIFF per tile/time; compressed; overviews for quick reads.
    - Time series: Parquet per route/segment with timestamps and depths.
    - Summaries: Parquet tables keyed by region/tile/time_window with max/mean depths.
  - Metadata
    - Store config hashes (DEM version, roughness map hash, rainfall slice id), solver parameters, and run logs for reproducibility.
  - Retrieval
    - Region/route scoped endpoints return compact JSON summaries and signed URLs to artifacts if needed.

- Performance & Ops
  - Compute
    - Prefer GPU (CUDA) where available; CPU fallback for small tiles or quick checks.
    - Constrain concurrency; queue long‑running runs in a dedicated worker pool.
  - Budgets
    - P95 route‑depth summary retrieval < 2 s from cached artifacts.
    - Full tile simulation targets under 10–30 min depending on grid and horizon; asynchronous only.
  - Observability
    - Track run durations, tile coverage, artifact sizes, and errors per scenario.

- QA & Validation
  - Hindcast severe events and compare inundation extents against EA/LA reports and imagery where available.
  - Sanity checks: monotonic runoff with increased rainfall; boundary condition sensitivity; DEM resolution sensitivity.
  - Route checks: validate depth thresholds vs known closures and field reports.

- Acceptance Criteria (Phase 2)
  - Functionality
    - API accepts scenario requests and returns job status and artifacts.
    - Route‑depth endpoint returns per‑segment max/mean depth and passability classification for specified vehicle profiles.
  - Reproducibility
    - Runs store config hashes and inputs; results reproducible within tolerance.
  - Performance
    - Cached route summaries return within 2 s; long runs execute asynchronously with clear status.
  - Quality
    - Hindcast validation shows plausible extents and segment depths against reference events; discrepancies documented.

## Backfill Ledger Spec

- Purpose
  - Track progress of date‑sliced ingestion for resumability, idempotency, and observability.

- Table: backfill_ledger
  - id: uuid
  - dataset: enum("hydrology_readings","haduk_grid_daily","era5_land_hourly","nrfa_daily","incidents","other")
  - region_id: nullable string (e.g., BRI,SOM,DOR,DEV,CON); null for non‑regional datasets
  - series_id: nullable string (e.g., EA measure id) for per‑series slices
  - slice_from: timestamptz (inclusive)
  - slice_to: timestamptz (exclusive)
  - grain: enum("month","day","hour") — month for hydrology reads; day/hour as needed
  - source_url: text — deterministic URL or descriptor used for the slice
  - source_etag: nullable text — ETag/Last‑Modified/hash for change detection
  - dest_path: text — deterministic raw artifact path (e.g., data/raw/ea/readings/{series}/{YYYY‑MM}.ndjson.gz)
  - status: enum("pending","running","success","partial","failed","skipped")
  - attempt_count: int default 0
  - rows_ingested: int default 0
  - bytes_raw: bigint default 0
  - duration_ms: bigint default 0
  - started_at: timestamptz nullable
  - finished_at: timestamptz nullable
  - last_error: text nullable (truncated message or code)
  - worker_id: nullable string (hostname/pod id) for attribution
  - created_at: timestamptz default now()
  - updated_at: timestamptz default now()

- Constraints & Indexes
  - unique(dataset, region_id, series_id, slice_from, slice_to)
  - check(slice_to > slice_from)
  - index on status for queue scanning
  - index on dataset, region_id, slice_from for reporting

- State Machine
  - pending → running → success | partial | failed
  - failed: retry increments attempt_count; backoff with jitter; cap by policy
  - partial: terminal with warning (e.g., reduced coverage); allowed when source incomplete
  - skipped: set when artifact exists with matching checksum and rows > 0 (fast‑path idempotency)

- Idempotency
  - dest_path and (dataset, region_id, series_id, slice_from, slice_to) are deterministic
  - If dest_path exists and source_etag matches, mark skipped or success without re‑download
  - Upserts to curated tables keyed by primary keys (e.g., (series_id, t))

- Retry & Backoff
  - attempt_count increments on each run; backoff = base * 2^attempt_count ± jitter
  - reset to pending after backoff window for reprocessing

- Coverage & QA
  - For hourly/daily derived coverage, store coverage_ratio in a side table or compute on read
  - partial status used when coverage < threshold (e.g., < 0.8 expected samples)

- Metrics (emit per slice)
  - ingestion_slice_duration_ms{dataset,region}
  - ingestion_rows_total{dataset,region}
  - ingestion_bytes_total{dataset,region}
  - ingestion_failures_total{dataset,region,error_code}

- Examples
  - Hydrology measure month:
    - dataset=hydrology_readings, series_id=EA‑MEASURE‑123, grain=month
    - slice_from=2021‑01‑01T00:00Z, slice_to=2021‑02‑01T00:00Z
    - dest_path=data/raw/ea/readings/EA‑MEASURE‑123/2021‑01.ndjson.gz
  - HadUK‑Grid daily:
    - dataset=haduk_grid_daily, region_id=SOM, grain=day
    - slice_from=2021‑01‑01T00:00Z, slice_to=2021‑01‑02T00:00Z
    - dest_path=data/raw/haduk/daily/SOM/2021/2021‑01‑01.parquet
