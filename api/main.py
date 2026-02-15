from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class Station(BaseModel):
    id: str
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    river_name: Optional[str] = None
    provider: Optional[str] = None


class SeriesPoint(BaseModel):
    t: datetime
    value: float
    agg: str
    quality: Optional[str] = None


class MeasurementsResponse(BaseModel):
    station: Optional[Station] = None
    series: List[SeriesPoint]
    window: Dict[str, datetime]
    provenance: Dict[str, Any]


class RainfallDaily(BaseModel):
    date: date
    prcp_mm: float


class RainfallResponse(BaseModel):
    region_id: Optional[str] = None
    cell_id: Optional[str] = None
    series: List[RainfallDaily]
    provenance: Dict[str, Any]


class Warning(BaseModel):
    id: str
    severity: str
    title: str
    issued_at: datetime
    updated_at: datetime
    geometry: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class RetrieveContextResponse(BaseModel):
    signals: Dict[str, Any]
    snippets: List[Dict[str, Any]]
    window: Dict[str, datetime]


class ForecastDay(BaseModel):
    date: date
    summary: Optional[str] = None
    prcp_mm: Optional[float] = None
    wind_kph: Optional[float] = None


class ForecastResponse(BaseModel):
    region_id: str
    days: List[ForecastDay]
    provenance: Dict[str, Any]


class BackfillRequest(BaseModel):
    dataset: str
    region_id: Optional[str] = None
    series_id: Optional[str] = None
    from_: datetime
    to: datetime
    slice_size: Optional[str] = None


class BackfillAccepted(BaseModel):
    job_id: str
    status_url: str


app = FastAPI(title="Flood Watch Data Lake API", version="0.1.0")

@app.get("/healthz")
def healthz():
    now = datetime.utcnow()
    return {"status": "ok", "version": app.version, "time": now.isoformat() + "Z"}


@app.get("/v1/measurements", response_model=MeasurementsResponse)
def get_measurements(
    station_id: Optional[str] = None,
    measure_id: Optional[str] = None,
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    bbox: Optional[str] = None,
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = None,
    aggregate: str = "raw",
    page: int = 1,
    limit: int = 500,
):
    now = datetime.utcnow()
    resp = MeasurementsResponse(
        station=Station(id=station_id or "unknown"),
        series=[],
        window={"from": from_ or now, "to": to or now},
        provenance={"as_of": now, "source": "lake"},
    )
    return resp


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


@app.get("/v1/warnings", response_model=Dict[str, List[Warning]])
def get_warnings(
    bbox: Optional[str] = None,
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    since: Optional[datetime] = None,
):
    return {"items": []}


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
