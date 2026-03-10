from fastapi import FastAPI, Query, Request
from typing import Optional, Dict, Any
from datetime import datetime, date
from api.models import (
    MeasurementsResponse,
    RainfallResponse,
    Warning,
    RetrieveContextResponse,
    ForecastResponse,
    BackfillRequest,
    BackfillAccepted,
)
from api.utils.cache import cache_get, cache_set, rate_limit
from api.routes.measurements import router as measurements_router
from api.routes.polygons import router as polygons_router
from api.routes.warnings import router as warnings_router


app = FastAPI(title="Flood Watch Data Lake API", version="0.1.0")
app.include_router(measurements_router)
app.include_router(polygons_router)
app.include_router(warnings_router)

@app.get("/healthz")
def healthz():
    now = datetime.utcnow()
    return {"status": "ok", "version": app.version, "time": now.isoformat() + "Z"}


 


@app.get("/v1/rainfall", response_model=RainfallResponse)
def get_rainfall(
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    cell_id: Optional[str] = None,
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = None,
):
    now = datetime.utcnow()
    resp = RainfallResponse(
        region_id=region,
        cell_id=cell_id,
        series=[],
        provenance={"dataset": "haduk_grid_daily", "version": "v1", "as_of": now},
    )
    return resp


 


@app.get("/v1/retrieve-context", response_model=RetrieveContextResponse)
def retrieve_context(
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    route: Optional[str] = None,
    time_window: Optional[str] = None,
    query: Optional[str] = None,
):
    now = datetime.utcnow()
    return {
        "signals": {},
        "snippets": [],
        "window": {"from": now, "to": now},
    }


@app.get("/v1/forecast", response_model=ForecastResponse)
def get_forecast(region: str = Query(..., pattern="^(BRI|SOM|DOR|DEV|CON)$")):
    now = datetime.utcnow()
    return {
        "region_id": region,
        "days": [],
        "provenance": {"source": "lake", "as_of": now},
    }


@app.post("/v1/jobs/backfill", response_model=BackfillAccepted, status_code=202)
def post_backfill(req: BackfillRequest):
    job_id = "job-0001"
    return {"job_id": job_id, "status_url": f"/v1/jobs/{job_id}"}


 
