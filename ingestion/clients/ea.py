import os
from typing import Any, Dict, List, Optional
import time
import httpx


class EAClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None, retries: Optional[int] = None, backoff: float = 0.5):
        self.base_url = base_url or os.getenv("EA_BASE_URL", "https://environment.data.gov.uk/flood-monitoring")
        self.timeout = float(timeout or os.getenv("TOTAL_TIMEOUT", "10.0"))
        self.retries = int(retries or os.getenv("RETRIES", "3"))
        self.backoff = backoff
        self._client = httpx.Client(timeout=self.timeout)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        attempt = 0
        last_exc = None
        while attempt <= self.retries:
            try:
                r = self._client.get(url, params=params)
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=r.request, response=r)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_exc = e
                attempt += 1
                if attempt > self.retries:
                    break
                time.sleep(self.backoff * attempt)
        raise RuntimeError(f"request failed: {url} params={params} error={last_exc}")

    def get_stations(self, bbox: Optional[str] = None, parameter: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if bbox:
            params["bbox"] = bbox
        if parameter:
            params["parameter"] = parameter
        data = self._get("/id/stations", params=params)
        return data.get("items", [])

    def get_measures(self, station: Optional[str] = None, parameter: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if station:
            params["station"] = station
        if parameter:
            params["parameter"] = parameter
        data = self._get("/id/measures", params=params)
        return data.get("items", [])

    def get_readings(self, measure_id: str, since: Optional[str] = None, until: Optional[str] = None, sorted_flag: bool = True) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if since:
            params["startdate"] = since
        if until:
            params["enddate"] = until
        if sorted_flag:
            params["_sorted"] = ""
        data = self._get(f"/id/measures/{measure_id}/readings", params=params)
        return data.get("items", [])
