# Place-mode LiDAR volume / runoff

Status: **Volume v1 live** — gauge-rise bathtub + A361 depth strip (History only)

## Goal

Under **History** analysis only:

1. Ingest DEFRA/EA LiDAR DEM for the Muchelney / A361 place bbox. ✅
2. Intersect curated storm `impact_geometry` with the DEM. ✅
3. Estimate flooded area / mean depth / volume with method notes. ✅
4. Surface as a History-only analytic panel (never mock). ✅

## Place bbox

Configured in [`api/config/place_bboxes.py`](../api/config/place_bboxes.py):

| Window | CRS | Use |
|--------|-----|-----|
| `wgs84` | EPSG:4326 | Map / product reference |
| `bng_core` | EPSG:27700 | Default LiDAR ingest (~10 km Muchelney) |
| `bng_full` | EPSG:27700 | Storm-footprint envelope (~22×24 km) |

## DTM ingest (v0)

Source: **LIDAR Composite DTM** via WCS GetCoverage (no auth).

```bash
# Core Muchelney window at 2 m (recommended default)
python -m ingestion.cli ingest-lidar-dtm --place a361-muchelney --resolution 2m --extent core --resume

# Full storm-envelope window (more tiles / larger download)
python -m ingestion.cli ingest-lidar-dtm --place a361-muchelney --resolution 2m --extent full --resume
```

Outputs (gitignored under `data/`):

- `data/curated/lidar/a361-muchelney/dtm-2m/*.tif` — BNG tiles (~5 km)
- `data/curated/lidar/a361-muchelney/dtm-2m/provenance.json` — product id, bbox, attribution, tile list

Attribution: © Environment Agency copyright and/or database right 2022. LIDAR Composite DTM.

### Notes

- Native CRS is **EPSG:27700** (`subset=E(...)` / `subset=N(...)`).
- Prefer **2 m** for corridor-scale volume v0; 1 m is available but heavier.
- Ingest writes **tiles**, not a single mosaic. Volume reads overlapping tiles via rasterio.
- Event outlines remain hand-curated v0 polygons (`api/config/storm_extents.py`) — not surveyed inundation.

## Volume v0 → v1 (gauge rise + road strip)

**API:** `GET /v1/storms/{storm_id}/volume?place=a361-muchelney&resolution=2m`

**Schema:** `floodwatch.storm_volume.v1`

**Preferred method:** `bathtub_gauge_rise_v1`

1. Load storm `impact_geometry` → mask DEM inside the polygon.
2. Load corridor `volume_stage` (Langport Great Bow) peak over the storm window and median over the late-summer baseline window.
3. Rise = `max(0, peak − baseline)`; DEM floor = percentile inside the outline (default 15th).
4. Water surface = DEM floor + rise; depth = `max(0, surface − terrain)`.
5. Sample curated A361 centreline (`api/config/road_lines.py`) every 20 m → max/mean depth and length above 0.3 / 0.5 / 1.0 m. Each sample includes WGS84 `lng`/`lat` for History map colouring.
6. If gauge series is missing, fall back to DEM-percentile bathtub (`bathtub_fill_percentile_v0`).

**Why Great Bow, not Gaw:** Gaw Bridge mASD barely moves flood vs summer in the archive; Great Bow (m) tracks Levels free-surface rise.

**UI:** History panel shows volume stats + A361 depth strip on the map (coloured by depth) and a cross-storm compare table (Chandra, Dennis, 2014, Ciara).

**Laravel proxy:** `GET /flood-watch/storms/{stormId}/volume`

Summer control (`bounds_mode: none`) returns `available: false` / `reason: no_impact_geometry`.

HiPIMS / depth-over-road hydrodynamic modelling remains deferred.

## Accuracy checklist (extents → DEM → volume)

See [accuracy-ladder.md](accuracy-ladder.md).

## Depends on

- Place-first History shell ✅
- Curated storm extents ✅
- DTM tiles on disk for `a361-muchelney` ← run CLI above
- Volume service + History panel ✅

Related: [data-sources.md](data-sources.md), [cockpit-use-cases.md](cockpit-use-cases.md) (Flood Watch), [accuracy-ladder.md](accuracy-ladder.md).
