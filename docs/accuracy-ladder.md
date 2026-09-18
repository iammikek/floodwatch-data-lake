# Accuracy ladder (History)

Place accuracy work serves **historical analysis**, not the live monitor.

| Step | Status | Notes |
|------|--------|-------|
| 1. Honesty labels | ✅ | Planning FZ ≠ event edge on map/copy |
| 2. Event GeoJSON extents | ✅ | Hand-curated `impact_geometry` in `api/config/storm_extents.py` |
| 3. LiDAR DTM ingest | ✅ | WCS Composite DTM 2 m tiles under `data/curated/lidar/{place}/dtm-2m/` |
| 4. Volume v0 | ✅ | Outline × DEM bathtub; History panel |
| 4b. Gauge-linked rise + A361 strip | ✅ | Great Bow peak−summer rise; road centreline depths |
| 4c. Historic flood warnings (AfA435) | ✅ | Chandra, Dennis, 2014; Ciara empty-window notes; `GET /v1/storms/{id}/warnings` |
| 5a. Finer DEM (1 m hotspot) | ✅ | A361 hotspot ingest; volume `resolution=1m` / auto when core-sized |
| 5b. HiPIMS / depth-over-road | Deferred | DEM contract in `docs/hipims-prep.md`; solver not wired |

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
- [ ] History compare table lists Chandra / Dennis / 2014 / Ciara volume metrics
- [ ] Compare membership is lake-owned (`volume_compare` on storms / `?volume_compare=true`)
- [ ] Map draws A361 depth strip from `road.samples` (lng/lat/depthM) in History

### Historic warnings (AfA435)

- [ ] Corridor issue rows curated in `api/config/storm_warnings.py` for founding events (Chandra, Dennis, 2014; Ciara noted empty)
- [ ] Storm enrichment attaches `warning_evidence` (`floodwatch.storm_warning_evidence.v0`)
- [ ] `GET /v1/storms/{id}/warnings` returns items + counts (or `available: false`)
- [ ] Notes call out issue-date semantics and known archive gaps (e.g. 112FWFEAS10A in 2026)
- [ ] Flood Watch History mounts Historic flood warnings panel (not live warnings layer)
- [ ] History map plots AfA435 severity markers; 112FWFEAS10A accents the A361 strip

### Finer DEM / HiPIMS prep

- [ ] `bng_hotspot` defined for A361 East Lyng / Othery strip
- [ ] `ingest-lidar-dtm --resolution 1m --extent hotspot` documented and runnable
- [ ] Volume `resolution=auto` uses 1 m only when coverage looks core-sized; hotspot-only keeps 2 m
- [ ] `GET /v1/places/{id}/dem` reports tile counts + HiPIMS pilot (`dem_prep`)
- [ ] History volume panel shows DEM resolution used
- [ ] Full HiPIMS-CUDA job API remains deferred (`docs/hipims-prep.md`)

## What we do not do

- Treat FZ2/FZ3 as event inundation
- Show LiDAR volume on the Live monitor
- Treat v0 hand polygons as surveyed truth
- One mega-layout with every panel greyed out
