from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.config.corridors import list_corridor_ids
from api.services.predictions import predict_corridor

router = APIRouter()


@router.get("/v1/predictions")
def get_predictions(
    corridor: str = Query(..., description="Corridor id, e.g. a361-muchelney"),
    history_days: int = Query(120, ge=7, le=400),
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
    try:
        doc: Dict[str, Any] = predict_corridor(corridor, history_days=history_days)
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
