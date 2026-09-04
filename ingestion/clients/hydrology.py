"""EA Hydrology Time-Series API client (long-retention archive)."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional


class HydrologyClient:
    """Client for https://environment.data.gov.uk/hydrology."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        backoff: float = 0.5,
    ):
        import httpx

        self.base_url = base_url or os.getenv(
            "EA_HYDROLOGY_BASE_URL",
            "https://environment.data.gov.uk/hydrology",
        )
        self.timeout = float(timeout or os.getenv("TOTAL_TIMEOUT", "30.0"))
        self.retries = int(retries or os.getenv("RETRIES", "3"))
        self.backoff = backoff
        self._client = httpx.Client(timeout=self.timeout)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import httpx

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= self.retries:
            try:
                r = self._client.get(url, params=params)
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "server error", request=r.request, response=r
                    )
                r.raise_for_status()
                return r.json()
            except Exception as exc:  # noqa: BLE001 - retry wrapper
                last_exc = exc
                attempt += 1
                if attempt > self.retries:
                    break
                time.sleep(self.backoff * attempt)
        raise RuntimeError(f"request failed: {url} params={params} error={last_exc}")

    def get_readings(
        self,
        measure_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """Fetch readings for a hydrology measure GUID/notation.

        Uses inclusive mineq-date / maxeq-date (YYYY-MM-DD).
        """
        params: Dict[str, Any] = {"_limit": limit}
        if since:
            params["mineq-date"] = since
        if until:
            params["maxeq-date"] = until
        data = self._get(f"/id/measures/{measure_id}/readings", params=params)
        return data.get("items", [])

    @staticmethod
    def to_flood_monitoring_shape(
        items: List[Dict[str, Any]],
        flood_monitoring_measure_id: str,
        *,
        proxy: bool = False,
        proxy_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Normalise hydrology readings into flood-monitoring-like NDJSON rows."""
        out: List[Dict[str, Any]] = []
        for item in items:
            value = item.get("value")
            if value is None:
                continue
            date_time = item.get("dateTime") or item.get("date")
            if not date_time:
                continue
            # Normalise to UTC ISO-8601 with Z so lake loaders stay timezone-aware.
            dt_text = str(date_time).strip()
            if dt_text.endswith("Z"):
                pass
            elif "+" in dt_text[10:] or dt_text.endswith("UTC"):
                pass
            else:
                dt_text = f"{dt_text}Z"
            row: Dict[str, Any] = {
                "@id": item.get("@id"),
                "dateTime": dt_text,
                "value": value,
                "measure": flood_monitoring_measure_id,
                "quality": item.get("quality"),
                "provenance": "ea_hydrology_archive",
            }
            if proxy:
                row["proxy"] = True
                if proxy_label:
                    row["proxyStation"] = proxy_label
            out.append(row)
        return out
