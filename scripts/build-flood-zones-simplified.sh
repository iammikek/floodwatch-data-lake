#!/usr/bin/env bash
# Build data/curated/ea/{REGION}_fz2_3_simplified.geojson from the normalized layer.
# Required for map-friendly GET /v1/polygons?format=simplified&inline=true.
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${1:-SOM}"
SRC="data/curated/ea/${REGION}_fz2_3_normalized.geojson"
DST="data/curated/ea/${REGION}_fz2_3_simplified.geojson"
if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC — fetch/curate flood zones first." >&2
  exit 1
fi
python - <<PY
import json, os, time
from ingestion.cli import _decimate_line

src = "${SRC}"
dst = "${DST}"
MAX = 48

def simp_geom(geom):
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Polygon":
        out = []
        for ring in coords or []:
            closed = len(ring) > 1 and ring[0] == ring[-1]
            core = ring[:-1] if closed else ring
            core = _decimate_line(core, MAX)
            if len(core) < 3:
                continue
            if core[0] != core[-1]:
                core = core + [core[0]]
            out.append(core)
        return {"type": "Polygon", "coordinates": out} if out else None
    if t == "MultiPolygon":
        polys = []
        for poly in coords or []:
            rings = []
            for ring in poly:
                closed = len(ring) > 1 and ring[0] == ring[-1]
                core = ring[:-1] if closed else ring
                core = _decimate_line(core, MAX)
                if len(core) < 3:
                    continue
                if core[0] != core[-1]:
                    core = core + [core[0]]
                rings.append(core)
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    return geom

t0 = time.time()
with open(src) as f:
    doc = json.load(f)
feats = []
for feat in doc.get("features") or []:
    g = simp_geom(feat.get("geometry") or {})
    if not g:
        continue
    feats.append({"type": "Feature", "properties": feat.get("properties"), "geometry": g})
with open(dst, "w") as f:
    json.dump({"type": "FeatureCollection", "features": feats}, f)
print(dst, "features", len(feats), "mb", round(os.path.getsize(dst) / 1e6, 1), "sec", round(time.time() - t0, 1))
PY
