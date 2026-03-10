from fastapi import APIRouter, Query, Request
from typing import Optional, List, Dict
from datetime import datetime
from api.models import Warning
from api.utils.cache import cache_get, cache_set, rate_limit
from api.services.warnings import list_warnings, build_key

router = APIRouter()

@router.get("/v1/warnings", response_model=Dict[str, List[Warning]])
def get_warnings(
    request: Request,
    bbox: Optional[str] = None,
    region: Optional[str] = Query(None, pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    since: Optional[datetime] = None,
):
    rate_limit(request)
    key = f"warnings:{build_key(bbox, region, since)}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    resp = list_warnings(bbox, region, since)
    cache_set(key, resp, ttl=30)
    return resp
