from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.config.corridors import list_corridor_ids
from api.config.hipims import get_hipims_pilot, list_hipims_pilot_ids
from api.config.place_bboxes import get_place_bbox, list_place_ids
from api.config.storms import get_storm, list_storms, list_volume_compare_storms
from api.services.predictions import predict_corridor
from api.services.volume import list_dtm_tiles, resolve_dtm_resolution

router = APIRouter()


def _parse_as_of(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"detail": f"Invalid as_of timestamp: {raw}", "code": "invalid_as_of"},
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/v1/predictions")
def get_predictions(
    corridor: str = Query(..., description="Corridor id, e.g. a361-muchelney"),
    history_days: int = Query(120, ge=7, le=400),
    as_of: Optional[str] = Query(
        None,
        description="UTC ISO-8601 evaluation instant for storm replay / hindcast",
    ),
) -> JSONResponse:
    if corridor not in list_corridor_ids():
        raise HTTPException(
            status_code=404,
            detail={
                "detail": f"Unknown corridor '{corridor}'",
                "code": "corridor_not_found",
                "known": list_corridor_ids(),
            },
        )
    now = _parse_as_of(as_of)
    try:
        doc: Dict[str, Any] = predict_corridor(
            corridor, history_days=history_days, now=now
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content=jsonable_encoder(doc))


@router.get("/v1/predictions/corridors")
def get_prediction_corridors() -> Dict[str, Any]:
    from api.config.corridors import CORRIDORS

    return {
        "corridors": [
            {"id": c["id"], "label": c["label"], "region": c["region"]}
            for c in CORRIDORS.values()
        ]
    }


@router.get("/v1/storms")
def get_storms(
    corridor: Optional[str] = Query(None, description="Filter by corridor id"),
    volume_compare: Optional[bool] = Query(
        None,
        description="When true, return only lake-curated History volume-compare storms (ordered)",
    ),
) -> Dict[str, Any]:
    if corridor and corridor not in list_corridor_ids():
        raise HTTPException(
            status_code=404,
            detail={
                "detail": f"Unknown corridor '{corridor}'",
                "code": "corridor_not_found",
                "known": list_corridor_ids(),
            },
        )
    if volume_compare is True:
        return {"storms": list_volume_compare_storms(corridor)}
    return {"storms": list_storms(corridor)}


@router.get("/v1/storms/{storm_id}")
def get_storm_by_id(storm_id: str) -> Dict[str, Any]:
    storm = get_storm(storm_id)
    if not storm:
        raise HTTPException(
            status_code=404,
            detail={"detail": f"Unknown storm '{storm_id}'", "code": "storm_not_found"},
        )
    return storm


@router.get("/v1/places/{place_id}/dem")
def get_place_dem_status(place_id: str) -> Dict[str, Any]:
    """Available LiDAR DTM resolutions + HiPIMS prep status for a place."""
    if place_id not in list_place_ids():
        raise HTTPException(
            status_code=404,
            detail={"detail": f"Unknown place '{place_id}'", "code": "place_not_found"},
        )
    place = get_place_bbox(place_id)
    tiles_1m = list_dtm_tiles(place_id, resolution="1m")
    tiles_2m = list_dtm_tiles(place_id, resolution="2m")
    preferred = resolve_dtm_resolution(place_id, "auto")
    hipims = None
    if place_id in list_hipims_pilot_ids():
        hipims = get_hipims_pilot(place_id)
    return {
        "schema": "floodwatch.place_dem.v0",
        "placeId": place_id,
        "label": place.get("label"),
        "preferredResolution": preferred,
        "resolutions": {
            "1m": {"available": bool(tiles_1m), "tileCount": len(tiles_1m)},
            "2m": {"available": bool(tiles_2m), "tileCount": len(tiles_2m)},
        },
        "extents": {
            "core": place.get("bng_core"),
            "hotspot": place.get("bng_hotspot"),
            "full": place.get("bng_full"),
        },
        "hipims": hipims,
        "attribution": (
            "© Environment Agency copyright and/or database right 2022. "
            "LIDAR Composite DTM."
        ),
    }


@router.get("/v1/storms/{storm_id}/volume")
def get_storm_volume(
    storm_id: str,
    place: Optional[str] = Query(
        None, description="Place id for DTM path (defaults to storm corridor)"
    ),
    resolution: str = Query(
        "auto",
        description="DTM resolution: auto (prefer 1m when present), 1m, or 2m",
    ),
) -> Dict[str, Any]:
    """Bathtub volume estimate: curated impact outline × LiDAR DTM (History analytic)."""
    from api.services.volume import estimate_storm_volume

    if not get_storm(storm_id):
        raise HTTPException(
            status_code=404,
            detail={"detail": f"Unknown storm '{storm_id}'", "code": "storm_not_found"},
        )
    try:
        return estimate_storm_volume(
            storm_id, place_id=place, resolution=resolution
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"detail": str(exc), "code": "volume_invalid"},
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/v1/storms/{storm_id}/warnings")
def get_storm_warnings(storm_id: str) -> Dict[str, Any]:
    """Curated AfA435 historic warning evidence for a storm (History analytic)."""
    from api.config.storm_warnings import warning_evidence_for

    storm = get_storm(storm_id)
    if not storm:
        raise HTTPException(
            status_code=404,
            detail={"detail": f"Unknown storm '{storm_id}'", "code": "storm_not_found"},
        )
    evidence = storm.get("warning_evidence") or warning_evidence_for(storm_id)
    if not evidence:
        return {
            "schema": "floodwatch.storm_warning_evidence.v0",
            "stormId": storm_id,
            "available": False,
            "reason": "no_warning_evidence",
            "items": [],
            "counts": {
                "total": 0,
                "floodWarning": 0,
                "floodAlert": 0,
                "severeFloodWarning": 0,
            },
        }
    has_items = bool(evidence.get("items"))
    return {
        **evidence,
        "available": has_items,
        "reason": None if has_items else "no_corridor_issues_in_window",
    }
