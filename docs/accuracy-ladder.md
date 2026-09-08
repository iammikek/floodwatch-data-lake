# Accuracy ladder (History)

Place accuracy work serves **historical analysis**, not the live monitor.

| Step | Status | Notes |
|------|--------|-------|
| 1. Honesty labels | ✅ | Planning FZ ≠ event edge on map/copy |
| 2. Event GeoJSON extents | ✅ | Hand-curated `impact_geometry` in `api/config/storm_extents.py` |
| 3. LiDAR DTM ingest | ✅ | WCS Composite DTM 2 m tiles under `data/curated/lidar/{place}/dtm-2m/` |
| 4. Volume v0 | ✅ | Outline × DEM bathtub; History panel |
| 4b. Gauge-linked rise + A361 strip | ✅ | Great Bow peak−summer rise; road centreline depths |
| 5. HiPIMS / depth-over-road | Deferred | After extents + DEM prove useful |

## Extents → DEM → volume checklist

Use this when adding a place or storm:

### Extents

- [ ] Storm listed in `api/config/storms.py` with `bounds_mode: impact` (or `none` for controls)
- [ ] Curated polygon in `api/config/storm_extents.py` (closed ring, WGS84)
- [ ] Catalogue returns `impact_geometry` + `impact_bbox`; History map outline syncs on select
- [ ] Copy never calls the outline surveyed inundation

### DEM

- [ ] Place bbox in `api/config/place_bboxes.py` (`bng_core` / `bng_full`)
- [ ] `ingest-lidar-dtm --place … --resolution 2m --extent core --resume` completed
- [ ] `provenance.json` present next to tiles; attribution retained

### Volume

- [ ] `GET /v1/storms/{id}/volume` returns `available: true` with area/depth/volume + method notes
- [ ] Prefer `method.mode: gauge_rise` (Great Bow peak − summer baseline) when archive exists
- [ ] Response includes `road` strip (max/mean depth, length ≥ 0.3 / 0.5 / 1.0 m) when centreline configured
- [ ] Summer / `bounds_mode: none` returns `available: false`
- [ ] Flood Watch History mounts Event volume panel; Live/Transport do not
- [ ] Panel shows Low confidence / gauge-rise or percentile method (no mock fill)

## What we do not do

- Treat FZ2/FZ3 as event inundation
- Show LiDAR volume on the Live monitor
- Treat v0 hand polygons as surveyed truth
- One mega-layout with every panel greyed out
