from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from api.models import MeasurementsResponse, Station, SeriesPoint
from api.services.measurements import month_iter, read_ndjson_gz, series_points, aggregate_points
from api.deps import rate_limiter, measurements_ttl
import os

router = APIRouter()

@router.get("/v1/measurements", response_model=MeasurementsResponse)
def get_measurements(
    request: Request,
    station_id: Optional[str] = None,
    measure_id: Optional[str] = None,
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    bbox: Optional[str] = None,
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = None,
    aggregate: str = "raw",
    page: int = 1,
    limit: int = 500,
    rl: Dict[str, int] = Depends(rate_limiter),
):
    now = datetime.now(timezone.utc)
    f = from_ or (now - timedelta(days=1))
    t = to or now
    series: List[SeriesPoint] = []
    if measure_id:
        months = month_iter(f, t)
        for y, m in months:
            mm = f"{y:04d}-{m:02d}"
            path = os.path.join("data", "raw", "ea", "readings", measure_id, f"{mm}.ndjson.gz")
            items = read_ndjson_gz(path)
            series.extend(series_points(items, f, t))
    if aggregate in ("hour", "day"):
        series = aggregate_points(series, aggregate)
    if page < 1:
        page = 1
    if limit < 1:
        limit = 1
    start = (page - 1) * limit
    end = start + limit
    series = series[start:end]
    resp = MeasurementsResponse(
        station=Station(id=station_id or "unknown"),
        series=series,
        window={"from": f, "to": t},
        provenance={"as_of": now, "source": "lake"},
    )
    cnt = len(series)
    key = f"measurements:{measure_id or station_id}:{aggregate}:{f.isoformat()}:{t.isoformat()}:{page}:{limit}"
    etag = f"W/{hash((key, cnt))}"
    ttl = measurements_ttl()
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
    return JSONResponse(content=jsonable_encoder(resp), headers=headers)
