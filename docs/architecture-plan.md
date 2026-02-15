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

## Next Steps

- Finalize table schemas and ledger model aligned to the above contracts.
- Draft ingestion jobs for EA hydrology (levels/flow) and HadUK‑Grid rainfall with region clipping.
- Add metrics and dashboards for backfill progress and data quality.
