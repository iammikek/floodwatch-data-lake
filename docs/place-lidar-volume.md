# Place-mode LiDAR volume / runoff

Status: **DTM ingest scaffolding live — volume panel not implemented yet**

## Goal

Under **History** analysis only:

1. Ingest DEFRA/EA LiDAR DEM for the Muchelney / A361 place bbox.
2. Intersect curated storm `impact_geometry` with the DEM.
3. Estimate flooded area / mean depth / volume with method notes.
4. Surface as a History-only analytic panel (never mock).

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
- Ingest writes **tiles**, not a single mosaic. Volume v0 should read tiles (or mosaic offline with GDAL/rasterio).
- Event outlines remain hand-curated v0 polygons (`api/config/storm_extents.py`) — not surveyed inundation.

## Volume v0 (next)

1. For a selected storm, load `impact_geometry` + overlapping DTM tiles.
2. Mask DEM cells inside the polygon; treat a reference water surface (e.g. flat stage or gauge-linked) vs terrain.
3. Report area / mean depth / volume + confidence / method notes on a History-only panel.
4. HiPIMS / depth-over-road remains deferred until this proves useful.

## Depends on

- Place-first History shell ✅
- Curated storm extents ✅
- DTM tiles on disk for `a361-muchelney` ← run CLI above

Related: [data-sources.md](data-sources.md), accuracy plan (extents → DEM → volume).
