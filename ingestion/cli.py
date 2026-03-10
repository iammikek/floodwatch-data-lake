import argparse
import os
import json
import gzip
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ingestion.regions import REGION_BBOX, REGION_NEAR
try:
    from ingestion.clients.ea import EAClient  # type: ignore
except Exception:
    EAClient = None  # type: ignore
try:
    from ingestion.io import write_ndjson_gz  # type: ignore
except Exception:
    def write_ndjson_gz(path: str, items: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(path, "wt") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")


def iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def next_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(year, month + 1, 1, tzinfo=timezone.utc)


def cmd_fetch_ea_stations(args: argparse.Namespace) -> None:
    client = EAClient()
    items = client.get_stations(bbox=args.bbox, parameter=args.parameter)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or f"data/raw/ea/stations/stations_{ts}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)


def cmd_fetch_ea_measures(args: argparse.Namespace) -> None:
    client = EAClient()
    items = client.get_measures(station=args.station, parameter=args.parameter)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sid = args.station or "all"
    out = args.out or f"data/raw/ea/measures/measures_{sid}_{ts}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)


def cmd_fetch_ea_readings_month(args: argparse.Namespace) -> None:
    client = EAClient()
    start = datetime(args.year, args.month, 1, tzinfo=timezone.utc)
    end = next_month(args.year, args.month)
    since = start.strftime("%Y-%m-%d")
    until = (end - timedelta(days=1)).strftime("%Y-%m-%d")
    items: List[Dict[str, Any]] = client.get_readings(args.measure, since=since, until=until, sorted_flag=True)
    out = args.out or f"data/raw/ea/readings/{args.measure}/{args.year:04d}-{args.month:02d}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)

def cmd_fetch_ea_stations_region(args: argparse.Namespace) -> None:
    near = REGION_NEAR.get(args.region)
    client = EAClient()
    if near:
        centers = near if isinstance(near, list) else [near]
        seen = set()
        items = []
        for c in centers:
            chunk = client.get_stations_near(c["lat"], c["long"], c["dist"], parameter=args.parameter)
            for it in chunk:
                nid = it.get("notation") or it.get("stationReference") or it.get("@id")
                if nid and nid in seen:
                    continue
                if nid:
                    seen.add(nid)
                items.append(it)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = args.out or f"data/raw/ea/stations/{args.region}_{ts}.ndjson.gz"
        write_ndjson_gz(out, items)
        print(out)
    else:
        bbox = REGION_BBOX[args.region]
        ns = argparse.Namespace(bbox=bbox, parameter=args.parameter, out=args.out)
        cmd_fetch_ea_stations(ns)

def cmd_fetch_ea_readings_range(args: argparse.Namespace) -> None:
    client = EAClient()
    start_year, start_month = map(int, args.from_month.split("-"))
    end_year, end_month = map(int, args.to_month.split("-"))
    y, m = start_year, start_month
    while True:
        s = datetime(y, m, 1, tzinfo=timezone.utc)
        e = next_month(y, m)
        since = s.strftime("%Y-%m-%d")
        until = (e - timedelta(days=1)).strftime("%Y-%m-%d")
        items: List[Dict[str, Any]] = client.get_readings(args.measure, since=since, until=until, sorted_flag=True)
        out = f"data/raw/ea/readings/{args.measure}/{y:04d}-{m:02d}.ndjson.gz"
        write_ndjson_gz(out, items)
        if y == end_year and m == end_month:
            break
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

def _measure_notation(m: Dict[str, Any]) -> str:
    nid = m.get("notation")
    if nid:
        return nid
    mid = m.get("@id", "")
    if "/id/measures/" in mid:
        return mid.split("/id/measures/")[-1]
    return mid

def _station_id(s: Dict[str, Any]) -> str:
    return s.get("notation") or s.get("stationReference") or s.get("@id", "")

def cmd_backfill_ea_region(args: argparse.Namespace) -> None:
    client = EAClient()
    near = REGION_NEAR.get(args.region)
    if near and hasattr(client, "get_stations_near"):
        centers = near if isinstance(near, list) else [near]
        seen = set()
        stations: List[Dict[str, Any]] = []
        for c in centers:
            chunk = client.get_stations_near(c["lat"], c["long"], c["dist"])
            for it in chunk:
                nid = _station_id(it)
                if nid and nid in seen:
                    continue
                if nid:
                    seen.add(nid)
                stations.append(it)
    else:
        bbox = REGION_BBOX[args.region]
        stations = client.get_stations(bbox=bbox)
    params = [p.strip() for p in (args.parameters.split(",") if args.parameters else ["level","flow"])]
    excludes = [q.strip() for q in (args.exclude_qualifiers.split(",") if getattr(args, "exclude_qualifiers", None) else []) if q.strip()]
    # Default range: last 10 years through current month if not provided
    now = datetime.now(timezone.utc)
    if args.from_month and args.to_month:
        from_month = args.from_month
        to_month = args.to_month
    else:
        fy = now.year - 10
        fm = now.month
        from_month = f"{fy:04d}-{fm:02d}"
        to_month = f"{now.year:04d}-{now.month:02d}"
    station_count = 0
    measure_total = 0
    for s in stations:
        station_count += 1
        if args.max_stations and station_count > args.max_stations:
            break
        sid = _station_id(s)
        try:
            measures = client.get_measures(station=sid)
        except Exception:
            continue
        selected = [
            m for m in measures
            if m.get("parameter") in params and (not excludes or (m.get("qualifier") or "") not in excludes)
        ]
        if not selected:
            tidal = [m for m in measures if m.get("parameter") == "level" and (m.get("qualifier") or "") == "Tidal Level"]
            if tidal:
                selected = tidal
        for m in selected:
            if args.max_measures and measure_total >= args.max_measures:
                break
            measure_id = _measure_notation(m)
            if getattr(args, "resume", False):
                sy, sm = map(int, from_month.split("-"))
                ey, em = map(int, to_month.split("-"))
                y, mo = sy, sm
                while True:
                    out_path = f"data/raw/ea/readings/{measure_id}/{y:04d}-{mo:02d}.ndjson.gz"
                    if not os.path.exists(out_path):
                        sdt = datetime(y, mo, 1, tzinfo=timezone.utc)
                        edt = next_month(y, mo)
                        since = sdt.strftime("%Y-%m-%d")
                        until = (edt - timedelta(days=1)).strftime("%Y-%m-%d")
                        items: List[Dict[str, Any]] = client.get_readings(measure_id, since=since, until=until, sorted_flag=True)
                        write_ndjson_gz(out_path, items)
                    if y == ey and mo == em:
                        break
                    if mo == 12:
                        y += 1
                        mo = 1
                    else:
                        mo += 1
            else:
                rng_args = argparse.Namespace(measure=measure_id, from_month=from_month, to_month=to_month)
                cmd_fetch_ea_readings_range(rng_args)
            measure_total += 1
        if args.max_measures and measure_total >= args.max_measures:
            break
    print(f"region={args.region} stations_processed={min(station_count, args.max_stations or station_count)} measures_processed={measure_total}")

def _bbox_points(bbox: str):
    w, s, e, n = [float(x) for x in bbox.split(",")]
    cx = (w + e) / 2.0
    cy = (s + n) / 2.0
    return [
        (cy, cx),
        ((s + cy) / 2.0, (w + cx) / 2.0),
        ((s + cy) / 2.0, (cx + e) / 2.0),
        ((cy + n) / 2.0, (w + cx) / 2.0),
        ((cy + n) / 2.0, (cx + e) / 2.0),
    ]

def _tile_bbox(bbox: str):
    w, s, e, n = [float(x) for x in bbox.split(",")]
    cx = (w + e) / 2.0
    cy = (s + n) / 2.0
    return [
        f"{w},{s},{cx},{cy}",
        f"{cx},{s},{e},{cy}",
        f"{w},{cy},{cx},{n}",
        f"{cx},{cy},{e},{n}",
    ]

def cmd_fetch_ea_flood_areas_region(args: argparse.Namespace) -> None:
    import httpx
    bbox = REGION_BBOX[args.region]
    pts = _bbox_points(bbox)
    base = "https://environment.data.gov.uk/flood-monitoring"
    seen = {}
    client = httpx.Client(timeout=20)
    for lat, lon in pts:
        try:
            r = client.get(f"{base}/id/floodAreas", params={"lat": lat, "long": lon, "dist": args.dist_km})
        except Exception:
            continue
        if r.status_code != 200:
            continue
        items = r.json().get("items") or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            key = it.get("notation") or it.get("@id")
            if not key or key in seen:
                continue
            poly = it.get("polygon")
            href = None
            if isinstance(poly, dict):
                href = poly.get("@id") or poly.get("href")
            elif isinstance(poly, str):
                href = poly
            geom = None
            if href:
                try:
                    gj = client.get(href, timeout=20)
                    if gj.status_code == 200:
                        geo = gj.json()
                        if geo.get("type") == "FeatureCollection":
                            feats = geo.get("features") or []
                            if feats:
                                geom = feats[0].get("geometry")
                        elif geo.get("type") == "Feature":
                            geom = geo.get("geometry")
                        elif "coordinates" in geo:
                            geom = geo
                except Exception:
                    pass
            seen[key] = {
                "type": "Feature",
                "properties": {
                    "id": key,
                    "label": it.get("label"),
                    "longName": it.get("longName"),
                    "riverOrSea": it.get("riverOrSea"),
                    "eaAreaName": it.get("eaAreaName"),
                },
                "geometry": geom,
            }
    feats = list(seen.values())
    out = args.out or f"data/raw/ea/flood_areas/{args.region}.geojson"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    print(out)

def _ogc_fetch_collection_items(base: str, collection_id: str, bbox: str, limit: int = 100, verbose: bool = False) -> Dict[str, Any]:
    import httpx
    url = f"{base}/collections/{collection_id}/items"
    params = {"bbox": bbox, "limit": limit}
    client = httpx.Client(timeout=60, headers={"Accept": "application/geo+json, application/json;q=0.9"})
    all_features: List[Dict[str, Any]] = []
    next_url = url
    next_params = params
    while next_url:
        if verbose:
            print(f"requesting collection={collection_id} bbox={bbox} limit={limit} so_far={len(all_features)}")
        r = client.get(next_url, params=next_params)
        if r.status_code != 200:
            break
        data = r.json()
        feats = data.get("features") or []
        if isinstance(feats, dict):
            feats = [feats]
        all_features.extend(feats)
        next_url = None
        next_params = None
        for link in data.get("links") or []:
            if link.get("rel") == "next":
                next_url = link.get("href")
                if verbose:
                    print(f"next page detected for collection={collection_id}")
                # Some servers provide absolute URL with embedded params; leave params None
    if verbose:
        print(f"collected features collection={collection_id} bbox={bbox} total={len(all_features)}")
    return {"type": "FeatureCollection", "features": all_features}

def cmd_fetch_ea_flood_zones_region(args: argparse.Namespace) -> None:
    bbox = REGION_BBOX[args.region]
    base = "https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1"
    tiles = _tile_bbox(bbox)
    features = {}
    for tb in tiles:
        print(f"tile start bbox={tb}")
        chunk = _ogc_fetch_collection_items(base, "Flood_Zones_2_3_Rivers_and_Sea", tb, limit=args.page_size, verbose=True)
        for feat in chunk.get("features", []):
            key = feat.get("id") or str(hash(json.dumps(feat.get("geometry"), sort_keys=True)))
            if key not in features:
                features[key] = feat
        print(f"tile done bbox={tb} cum_features={len(features)}")
    out = args.out or f"data/raw/ea/flood_zones/{args.region}_fz2_3.geojson"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"type": "FeatureCollection", "features": list(features.values())}, f)
    print(out)

_RSE_COLLECTIONS = {
    "defended_1in100_1in200": "Rivers_1in100_Sea_1in200_defended_extents",
    "undefended_1in100_1in200": "Rivers_1in100_Sea_1in200_undefended_extents",
    "defended_1in1000": "Rivers_1in1000_Sea_1in1000_defended_extents",
    "undefended_1in1000": "Rivers_1in1000_Sea_1in1000_undefended_extents",
}

def cmd_fetch_ea_rivers_sea_extents_region(args: argparse.Namespace) -> None:
    bbox = REGION_BBOX[args.region]
    base = "https://environment.data.gov.uk/spatialdata/rivers-and-sea-defended-and-undefended-flood-risk-extents-present-day/ogc/features/v1"
    to_fetch = []
    if args.scenario == "all":
        to_fetch = list(_RSE_COLLECTIONS.items())
    else:
        to_fetch = [(args.scenario, _RSE_COLLECTIONS[args.scenario])]
    tiles = _tile_bbox(bbox)
    for key, coll in to_fetch:
        features = {}
        for tb in tiles:
            print(f"tile start collection={coll} bbox={tb}")
            chunk = _ogc_fetch_collection_items(base, coll, tb, limit=args.page_size, verbose=True)
            for feat in chunk.get("features", []):
                k = feat.get("id") or str(hash(json.dumps(feat.get("geometry"), sort_keys=True)))
                if k not in features:
                    features[k] = feat
            print(f"tile done collection={coll} bbox={tb} cum_features={len(features)}")
        out = args.out or f"data/raw/ea/rivers_sea_extents/{args.region}_{key}.geojson"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            json.dump({"type": "FeatureCollection", "features": list(features.values())}, f)
        print(out)

def _decimate_line(points: List[List[float]], max_points: int) -> List[List[float]]:
    n = len(points)
    if n <= max_points:
        return points
    step = max(1, n // max_points)
    out = [points[i] for i in range(0, n, step)]
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out

def _simplify_geometry(geom: Dict[str, Any], tolerance: float) -> Dict[str, Any]:
    t = geom.get("type")
    if t == "Polygon":
        rings = geom.get("coordinates") or []
        out_rings = []
        for ring in rings:
            closed = len(ring) > 1 and ring[0] == ring[-1]
            core = ring[:-1] if closed else ring
            simp = _decimate_line(core, max_points=max(200, int(200 / max(1e-9, tolerance / 0.0005))))
            if closed:
                if simp[0] != simp[-1]:
                    simp = simp + [simp[0]]
            out_rings.append(simp)
        return {"type": "Polygon", "coordinates": out_rings}
    if t == "MultiPolygon":
        polys = geom.get("coordinates") or []
        out_polys = []
        for poly in polys:
            out_rings = []
            for ring in poly:
                closed = len(ring) > 1 and ring[0] == ring[-1]
                core = ring[:-1] if closed else ring
                simp = _decimate_line(core, max_points=max(200, int(200 / max(1e-9, tolerance / 0.0005))))
                if closed:
                    if simp[0] != simp[-1]:
                        simp = simp + [simp[0]]
                out_rings.append(simp)
            out_polys.append(out_rings)
        return {"type": "MultiPolygon", "coordinates": out_polys}
    return geom

def cmd_curate_polygons(args: argparse.Namespace) -> None:
    with open(args.in_path, "r") as f:
        data = json.load(f)
    feats = data.get("features") or []
    seen: Dict[str, Dict[str, Any]] = {}
    for feat in feats:
        gid = feat.get("id") or feat.get("properties", {}).get("id")
        geom = feat.get("geometry")
        if not geom:
            continue
        key = gid or str(hash(json.dumps(geom, sort_keys=True)))
        if key in seen:
            continue
        props = feat.get("properties") or {}
        props["id"] = gid or props.get("id") or key
        seen[key] = {"type": "Feature", "properties": props, "geometry": geom}
    normalized = {"type": "FeatureCollection", "features": list(seen.values())}
    base = os.path.basename(args.in_path)
    name, _ = os.path.splitext(base)
    out_dir = args.out_dir or os.path.join("data", "curated", "ea")
    os.makedirs(out_dir, exist_ok=True)
    norm_path = os.path.join(out_dir, f"{name}_normalized.geojson")
    with open(norm_path, "w") as f:
        json.dump(normalized, f)
    simp_feats = []
    for feat in normalized["features"]:
        geom = feat.get("geometry")
        simp = _simplify_geometry(geom, args.tolerance)
        simp_feats.append({"type": "Feature", "properties": feat.get("properties"), "geometry": simp})
    simp_path = os.path.join(out_dir, f"{name}_simplified.geojson")
    with open(simp_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": simp_feats}, f)
    print(norm_path)
    print(simp_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingestion")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("fetch-ea-stations")
    ps.add_argument("--bbox", help="west,south,east,north")
    ps.add_argument("--parameter", help="e.g. level, flow")
    ps.add_argument("--out")
    ps.set_defaults(func=cmd_fetch_ea_stations)
    psr = sub.add_parser("fetch-ea-stations-region")
    psr.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    psr.add_argument("--parameter")
    psr.add_argument("--out")
    psr.set_defaults(func=cmd_fetch_ea_stations_region)


    pm = sub.add_parser("fetch-ea-measures")
    pm.add_argument("--station", help="station notation or ref")
    pm.add_argument("--parameter", help="e.g. level, flow")
    pm.add_argument("--out")
    pm.set_defaults(func=cmd_fetch_ea_measures)

    pr = sub.add_parser("fetch-ea-readings-month")
    pr.add_argument("--measure", required=True, help="measure id")
    pr.add_argument("--year", type=int, required=True)
    pr.add_argument("--month", type=int, required=True)
    pr.add_argument("--out")
    pr.set_defaults(func=cmd_fetch_ea_readings_month)
    prng = sub.add_parser("fetch-ea-readings-range")
    prng.add_argument("--measure", required=True)
    prng.add_argument("--from", dest="from_month", required=True, help="YYYY-MM")
    prng.add_argument("--to", dest="to_month", required=True, help="YYYY-MM")
    prng.set_defaults(func=cmd_fetch_ea_readings_range)

    pbr = sub.add_parser("backfill-ea-region")
    pbr.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    pbr.add_argument("--parameters", default="level,flow", help="comma-separated, e.g. level,flow")
    pbr.add_argument("--from", dest="from_month", help="YYYY-MM; default last 10y from current month")
    pbr.add_argument("--to", dest="to_month", help="YYYY-MM; default current month")
    pbr.add_argument("--max-stations", type=int, help="limit stations for trial runs")
    pbr.add_argument("--max-measures", type=int, help="limit measures for trial runs")
    pbr.add_argument("--exclude-qualifiers", default="Tidal Level", help="comma-separated measure qualifiers to exclude (e.g. Tidal Level)")
    pbr.add_argument("--resume", action="store_true", help="skip existing monthly files to continue where left off")
    pbr.set_defaults(func=cmd_backfill_ea_region)

    pfa = sub.add_parser("fetch-ea-flood-areas-region")
    pfa.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    pfa.add_argument("--dist-km", type=int, default=60)
    pfa.add_argument("--out")
    pfa.set_defaults(func=cmd_fetch_ea_flood_areas_region)
    pfz = sub.add_parser("fetch-ea-flood-zones-region")
    pfz.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    pfz.add_argument("--page-size", type=int, default=100)
    pfz.add_argument("--out")
    pfz.set_defaults(func=cmd_fetch_ea_flood_zones_region)
    prse = sub.add_parser("fetch-ea-rivers-sea-extents-region")
    prse.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    prse.add_argument("--scenario", choices=["defended_1in100_1in200","undefended_1in100_1in200","defended_1in1000","undefended_1in1000","all"], default="all")
    prse.add_argument("--page-size", type=int, default=100)
    prse.add_argument("--out")
    prse.set_defaults(func=cmd_fetch_ea_rivers_sea_extents_region)
    pc = sub.add_parser("curate-polygons")
    pc.add_argument("--in", dest="in_path", required=True)
    pc.add_argument("--out-dir")
    pc.add_argument("--tolerance", type=float, default=0.0005)
    pc.set_defaults(func=cmd_curate_polygons)

    return p

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
