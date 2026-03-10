from fastapi import APIRouter, Query, Request, Depends
from typing import Optional, List, Dict
from datetime import datetime
from api.models import Warning
from api.utils.cache import cache_get, cache_set, rate_limit
from api.services.warnings import list_warnings, build_key
from api.deps import get_ea_client, rate_limiter
from ingestion.clients.ea import EAClient

router = APIRouter()

@router.get("/v1/warnings", response_model=Dict[str, List[Warning]])
def get_warnings(
    request: Request,
    bbox: Optional[str] = None,
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    since: Optional[datetime] = None,
    _: None = Depends(rate_limiter),
    ea: EAClient = Depends(get_ea_client),
    min_severity: Optional[int] = Query(3, ge=1, le=4),
):
    key = f"warnings:{build_key(bbox, region, since)}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    resp = list_warnings(bbox, region, since, ea)
    cache_set(key, resp, ttl=30)
    resp = list_warnings(bbox, region, since, ea, min_severity=min_severity)
    cache_set(key, resp, ttl=30)
    return resp
