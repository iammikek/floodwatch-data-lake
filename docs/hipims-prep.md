# HiPIMS / finer DEM prep (History accuracy ladder step 5)

Status: **DEM prep in progress** — 1 m hotspot ingest + volume `resolution=auto`. Full HiPIMS-CUDA solver **not wired**.

## Goal

1. Prefer **finer DEM (1 m)** for History volume / A361 depth strip when tiles exist.
2. Define the Muchelney **hotspot** domain HiPIMS will run on later.
3. Keep the GPLv3 solver isolated until we need depth-over-road hydrodynamics.

## What ships now

| Piece | Location |
|-------|----------|
| Hotspot BNG bbox | `api/config/place_bboxes.py` → `bng_hotspot` |
| HiPIMS pilot config | `api/config/hipims.py` (`status: dem_prep`, `solver.wired: false`) |
| Volume resolution | `GET /v1/storms/{id}/volume?resolution=auto\|1m\|2m` (`auto` uses 1 m only when coverage looks core-sized; hotspot-only 1 m keeps 2 m for storm-wide bathtub) |
| DEM status | `GET /v1/places/{place_id}/dem` |

### Ingest 1 m hotspot

```bash
python -m ingestion.cli ingest-lidar-dtm \
  --place a361-muchelney --resolution 1m --extent hotspot --resume
```

Tiles land under `data/curated/lidar/a361-muchelney/dtm-1m/` (gitignored) with `provenance.json`.

Core 2 m remains the wide-area bathtub fallback until a full 1 m core (or mosaic) exists.

## What is deferred (true HiPIMS)

Per `docs/architecture-plan.md` Phase 2:

- hipims / pypims / hipims_io CUDA runner
- Manning roughness + rainfall forcing
- `POST /v1/jobs/hipims-run` + depth COGs
- Passability vs vehicle wading limits

Do **not** vendor HiPIMS into the main API image until license isolation is decided (GPLv3).

## Accuracy ladder

See [accuracy-ladder.md](accuracy-ladder.md) step 5a / 5b.
