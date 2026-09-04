from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.config.corridors import list_corridor_ids
from api.config.storms import get_storm, list_storms
from api.services.predictions import predict_corridor

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
