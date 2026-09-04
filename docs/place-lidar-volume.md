# Place-mode LiDAR volume / runoff (deferred)

Status: **planned — not implemented**

When place-mode map + flood bounds are stable and archive storm replay is credible:

1. Ingest DEFRA/EA LiDAR DEM tiles for the Muchelney / A361 place bbox.
2. Intersect flood outline (warning polygons or modelled inundation) with DEM.
3. Estimate water volume and simple runoff contribution for the place.
4. Surface as a place-mode analytic panel (never mock).

Depends on: place-first cockpit map, reliable flood polygon layers, storm replay labelled as such.

Related: [docs/data-sources.md](data-sources.md) (DEFRA/EA LiDAR note).
