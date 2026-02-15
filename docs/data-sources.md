# Data Sources

## Primary Sources

- Environment Agency Flood Monitoring API
  - Live river levels/readings, station metadata, and active flood warnings.
  - Public JSON/GeoJSON endpoints; no auth for core data.
  - Use for measurements time series, station locations, and warnings.
  - Base: https://environment.data.gov.uk/flood-monitoring

- National Highways Roads API
  - Live incidents, closures, and congestion on strategic roads.
  - Requires a free API key; JSON responses.
  - Use for route safety context and closures on M‑/A‑roads.
  - Base: https://api.data.nationalhighways.co.uk/roads/v2.0

- Weather Forecasts
  - Met Office DataHub: official UK forecasts and weather warnings (API key).
  - Open‑Meteo: no‑auth, fast forecasts suitable for initial build.
  - Use for 5‑day outlooks and near‑term precipitation/wind signals.
  - Open‑Meteo Base: https://api.open-meteo.com

## Supporting Datasets

- Ordnance Survey Open Data
  - OS Open Roads: national road network geometry for mapping/joins.
  - Code‑Point Open: postcode → lat/lng for corridor/region queries.
  - BoundaryLine: region/LA polygons to scope queries and caches.

- EA Flood Risk Layers (WMS/WFS)
  - Flood Map for Planning, Risk of Flooding from Rivers and Sea.
  - Useful for reference overlays and pre‑computed joins.

- DEFRA/EA LiDAR (1 m/2 m)
  - Elevation for depth‑over‑road estimates; larger ETL effort, optional later.

- Local Authority Feeds (e.g., Somerset Council)
  - Some councils publish roadworks/closures; quality varies. Start with National Highways; add LA feeds opportunistically.

## Access & Cadence

- Environment Agency Flood Monitoring
  - Readings/stations: near‑real‑time, many stations update ~15 min.
  - Warnings: event‑driven; poll every 60 s; cache TTL ~60 s.

- National Highways
  - Incidents change frequently; poll 30–60 s; cache TTL ~60 s.

- Forecasts
  - Update cadence ~hourly; cache TTL ~30 min.

- OS/Boundaries
  - Static; ingest once and version.

## Granularity & Frequency

- Hydrology (EA levels/flow)
  - Native resolution: typically 15‑min (some 5‑min or hourly depending on station).
  - Stored: raw series retained; daily aggregates (mean, max, min, p95, exceedances vs typical high); optional hourly rollups.

- Rainfall (HadUK‑Grid via CEDA)
  - Native resolution: daily per 1 km grid cell.
  - Stored: daily per‑cell totals and daily region aggregates (mean, max).

- Rainfall (ERA5/Land via Open‑Meteo)
  - Native resolution: hourly.
  - Stored: aggregated to daily totals (mm/day) for parity with HadUK‑Grid; keep hourly only if required by analyses.

- Roads/Incidents (National Highways, LAs)
  - Native: event‑based with timestamps (start, update, end).
  - Stored: event stream + optional daily aggregates (counts, durations) for analytics.

- Geospatial (OS Open Roads, BoundaryLine, Code‑Point Open)
  - Native: static datasets (periodic releases).
  - Stored: latest version in PostGIS; retain historical versions when needed.

## Daily Aggregations (Published Columns)

- Hydrology (observations_daily)
  - series_id
  - date
  - value_mean
  - value_max
  - value_min
  - value_p95
  - exceedances_typical_high
  - hours_above_typical_high
  - sample_count
  - source_version
  - ingested_at

- Rainfall Per Cell (rainfall_daily)
  - cell_id
  - date
  - prcp_mm
  - source_version
  - ingested_at

- Rainfall Regional Aggregates (rainfall_region_daily)
  - region_id
  - date
  - prcp_mm_mean
  - prcp_mm_max
  - prcp_mm_p95
  - cell_count
  - source_version
  - ingested_at

- Incidents (incidents_daily_agg)
  - region_id
  - date
  - incident_count
  - active_duration_hours_sum
  - closure_count
  - source_version
  - ingested_at

## Derivation Mapping (Raw → Hourly → Daily)

- Hydrology
  - Raw (observations): direct from EA readings; keep all samples with UTC timestamps and quality.
  - Hourly (observations_hourly):
    - Bucket: t_hour = floor(to_hour(t, UTC)).
    - value_mean/max/min = aggregates over samples in the hour.
    - sample_count = count of samples in the hour.
  - Daily (observations_daily):
    - Bucket: date = UTC calendar day.
    - value_mean/max/min/p95 = aggregates over day samples (p95 via nearest-rank on sorted values).
    - exceedances_typical_high = count(samples where value > measures.typical_high).
    - hours_above_typical_high = sum over hours where any sample > typical_high (or fractional by sample coverage).
    - sample_count = total samples for the day.
    - Missing data handling: if coverage < 80% of expected samples, flag day for QA.

- Rainfall
  - HadUK‑Grid:
    - Raw: daily per‑cell totals from NetCDF (mm/day).
    - Region daily: prcp_mm_mean = area‑weighted mean across cells intersecting region; prcp_mm_max and prcp_mm_p95 similarly by cell values.
  - ERA5/Land:
    - Raw: hourly precipitation; aggregate to daily per coordinate/cell by sum(mm/hour) → mm/day.
    - Coverage rule: if < 80% of hours present, mark day as partial.

- Incidents
  - Raw: event stream with start/end timestamps and updates.
  - Daily aggregates:
    - incident_count = number of events active at any time during day.
    - active_duration_hours_sum = sum of intersection duration between event [start,end] and day window.
    - closure_count = count of events with closure severity during day.

## Hourly Rollups (Published Columns, Optional)

- Hydrology (observations_hourly)
  - series_id
  - t_hour          // UTC hour bucket start
  - value_mean
  - value_max
  - value_min
  - sample_count
  - source_version
  - ingested_at

## Raw Observations Schema (Canonical)

- Hydrology (observations)
  - series_id       // references measures.id
  - t               // UTC timestamp
  - value           // numeric
  - quality         // source quality flag where provided
  - source_version  // e.g., API version or dataset release id
  - ingested_at     // ingestion timestamp
  - Notes:
    - Units and parameter are defined by the measure/series metadata (measures.unit, measures.parameter).
    - Typical ranges (typical_low, typical_high) stored on measures for exceedance calculations.

## V1 Recommendation (West Country Focus)

- Hydrology: EA stations + latest readings, plus active flood warnings.
- Roads: National Highways incidents for the SW corridor (M4/M5/A38).
- Weather: Open‑Meteo forecasts initially; add Met Office DataHub when keys ready.
- Geospatial: OS Open Roads + BoundaryLine for geometry/region scoping; Code‑Point Open for postcode lookup.

## Regions In Scope (Phase 1)

- Regions
  - Bristol (Unitary Authority)
  - Somerset
  - Dorset
  - Devon
  - Cornwall (incl. Isles of Scilly as needed)

- Region IDs (proposed)
  - BRI, SOM, DOR, DEV, CON
  - Use these in cache keys, Parquet partitions, and API filters.

- Boundary Source
  - OS BoundaryLine: use UA/County polygons for exact selection and aggregation.
  - PostGIS storage with spatial indexes; convert to EPSG:4326 for APIs.

- Approximate BBoxes (discovery only; use polygons for final selection)
  - Bristol: -2.75, 51.40, -2.45, 51.55
  - Somerset: -3.90, 50.90, -2.20, 51.40
  - Dorset: -2.96, 50.50, -1.70, 51.00
  - Devon: -4.75, 50.20, -2.95, 51.25
  - Cornwall: -5.80, 49.90, -4.00, 50.80

Notes:
- Use bboxes to prune upstream discovery requests; snap final station/cell membership to region polygons.
- Keep region versions in metadata to support boundary updates over time.

## Caching & Resilience Defaults

- Timeouts: connect 500 ms; total 1500–2000 ms; retry 3× with jitter.
- Caching: short TTLs with stale‑while‑revalidate; deterministic, region‑scoped keys.
- Circuit breaker: open after successive failures; serve last known good with “as of” timestamp.

## Acquisition Formats & Storage

- Environment Agency Flood Monitoring / Hydrology
  - Transport: HTTP JSON.
  - Raw Retention: NDJSON (.ndjson.gz) snapshots per month/series for audit and reprocessing.
  - Canonicalization: observations table in Postgres (series_id, t, value, quality) and optional Parquet partitioned by series_id/year for analytics.

- National Highways
  - Transport: HTTP JSON.
  - Raw Retention: NDJSON snapshots by day.
  - Canonicalization: incidents table with geometry and status fields; geometry stored in PostGIS (SRID 4326).

- Rainfall (HadUK‑Grid via CEDA)
  - Transport: NetCDF files (daily precipitation).
  - Raw Retention: original NetCDF kept in object storage; tracked by checksum and version.
  - Canonicalization: per‑cell and regional daily aggregates written to Parquet (partitioned by year/region) and to Postgres summary tables for fast queries.

- Rainfall (ERA5/Land via Open‑Meteo)
  - Transport: HTTP JSON.
  - Canonicalization: daily precipitation series harmonized to mm/day, stored alongside provenance to distinguish from HadUK‑Grid.

- Ordnance Survey (Open Roads, BoundaryLine, Code‑Point Open)
  - Transport: GML/GeoPackage/CSV (varies by product).
  - Canonicalization: loaded once into PostGIS; indexed for spatial queries (SRID 27700 converted to 4326 where required).

- Serialization & Units
  - Time: UTC ISO‑8601 for all timestamps.
  - Units: precipitation mm/day; stage m; flow m³/s.
  - Geometry: WGS84 (EPSG:4326) for API/view; retain native projections for processing when needed.

## Notes

- Keep payloads small and region‑scoped to reduce latency and improve cacheability.
- Add Met Office and local authority feeds as credentials and stability allow.

## 10‑Year Historical Data

- Hydrology (Levels/Flow)
  - Environment Agency Hydrology Time‑Series API (levels and flow).
  - Use for 10‑year water level (stage) and discharge time series per station.
  - Approach: discover stations in region scope; backfill by month to avoid payload limits; store readings with station and measure identifiers.
  - Notes: open data under OGL; the flood‑monitoring API is optimized for recent data, prefer hydrology time‑series for long history.

- Long‑Term Flow (Curated)
  - National River Flow Archive (NRFA) daily mean flow and peaks (curated).
  - Use for QA’d historical flows and catchment metadata where available.
  - Notes: registration and licensing apply; API and bulk downloads supported.

- Rainfall (Gridded)
  - Met Office HadUK‑Grid (1 km) daily precipitation via the CEDA archive.
  - Use for regional rainfall climatology and event backfills across 10 years.
  - Notes: account required; NetCDF files are large — pre‑select region/bbox and time window; preprocess to regional aggregates for storage.

- Rainfall/Weather (Reanalysis, Quick Start)
  - Open‑Meteo historical ERA5/Land via the archive API.
  - Use for pragmatic historical precipitation and temperature series per coordinate.
  - Notes: free and fast for bootstrapping; validate against authoritative datasets for production analytics.

### Backfill Strategy

- Scope: limit to West Country corridor/catchments first to cap volumes.
- Chunking: slice by month per station/coordinate; parallelize with rate limits.
- Idempotency: upsert on (series_id, timestamp); track last successful slice.
- Quality: store quality flags; record source, version, and retrieval timestamps.
- Storage: Postgres tables for stations/measures and observations; retain raw files for audit where feasible.

### 10‑Year Backfill Scope (Phase 1)

- Spatial Focus
  - West Country corridor and Somerset Levels priority catchments: Parrett, Tone, Exe, Avon.
  - Use a corridor bbox and catchment boundaries to constrain station and grid selection.

- Time Window
  - Rolling 10 years: from (today − 10y) to present; include partial current month.

- Datasets and Priority
  - P1: EA Hydrology Time‑Series — river level (stage) and flow per station/measure.
  - P1: Met Office HadUK‑Grid daily precipitation (regional subset via CEDA).
  - P2: NRFA curated daily mean flows and peaks for overlap stations (QA/reference).
  - P3: ERA5/Land historical precipitation via Open‑Meteo for gap‑fill/quick bootstrap.

- Pipeline Steps
  - Discover stations within region; record station and measure metadata.
  - Enumerate measures (level/flow) with units, qualifiers, and typical ranges.
  - For each measure, fetch monthly slices; retry with jitter and strict timeouts.
  - Parse and normalize to observations table; persist quality flags and provenance.
  - For rainfall, pre‑clip NetCDF to region; compute area‑weighted regional aggregates and per‑cell summaries; store daily aggregates.
  - Maintain a backfill ledger to track completed slices and support resumption.

- Data Contracts (Proposed Tables)
  - stations(id, notation, name, lat, lng, catchment_id, river_name, provider, created_at)
  - measures(id, station_id, parameter, unit, qualifier, typical_low, typical_high, provider, created_at)
  - observations(series_id, t, value, quality, source_version, ingested_at, primary key(series_id, t))
  - rainfall_cells(id, lat, lng, cell_id, provider)
  - rainfall_daily(cell_id, t, prcp_mm, source_version, ingested_at, primary key(cell_id, t))

- Validation and QA
  - Check for duplicate timestamps and monotonic monthly coverage.
  - Flag out‑of‑range values vs typical ranges; compute basic completeness metrics.
  - Cross‑check selected stations against NRFA daily means where available.

- Deliverables
  - Region‑scoped queryable series for level/flow and regional rainfall aggregates.
  - Metadata endpoints for stations/measures supporting downstream selection.
  - Provenance and “as of” timestamps for all backfilled data.

### Rainfall Focus (Details)

- Met Office HadUK‑Grid (Daily Precipitation)
  - Coverage: UK‑wide, 1 km grid, daily totals.
  - Source: CEDA Archive (registration required).
  - Access: NetCDF files per period; advisable to select a West Country subset.
  - Processing:
    - Clip to bbox or catchment shapes.
    - Compute daily regional aggregates (area‑weighted mean, max).
    - Persist per‑cell daily totals for higher‑resolution queries.
  - Storage:
    - rainfall_cells(cell_id, lat, lng).
    - rainfall_daily(cell_id, t, prcp_mm).
    - rainfall_region_daily(region_id, t, prcp_mm_mean, prcp_mm_max).

- Open‑Meteo ERA5/Land (Bootstrap/Gaps)
  - Coverage: Global; hourly/daily variables derived from ERA5/Land.
  - Use: Rapid bootstrap for historical precipitation where HadUK‑Grid workflow is pending.
  - Processing:
    - Sample representative coordinates per region/catchment.
    - Aggregate hourly to daily where required; harmonize units (mm/day).
  - Caveat: Reanalysis differs from gauge‑based datasets; document provenance.

- Quality and Consistency
  - Harmonize units (mm) and timezones (UTC) across sources.
  - Validate day counts and detect missing days; backfill or flag gaps.
  - Record dataset version, CEDA DOIs where applicable, and retrieval hashes.
