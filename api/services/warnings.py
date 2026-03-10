from typing import List, Dict, Any, Optional
from datetime import datetime
from api.models import Warning
from ingestion.clients.ea import EAClient
from ingestion.regions import REGION_NEAR


def build_key(bbox: Optional[str], region: Optional[str], since: Optional[datetime]) -> str:
    return f"{bbox}:{region}:{since.isoformat() if since else ''}"


def _severity_text(level: Optional[int], text: Optional[str]) -> str:
    if text:
        return text
    m = {1: "Severe Flood Warning", 2: "Flood Warning", 3: "Flood Alert", 4: "No Longer In Force"}
    return m.get(level or 0, "Unknown")


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.utcnow()
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _to_warning(item: Dict[str, Any]) -> Warning:
    wid = item.get("@id") or item.get("id") or item.get("floodAreaID") or item.get("message")
    sev = _severity_text(item.get("severityLevel"), item.get("severity"))
    title = item.get("description") or item.get("message") or "Flood Warning"
    issued = _parse_dt(item.get("timeRaised") or item.get("timeMessageReceived"))
    updated = _parse_dt(item.get("timeSeverityChanged") or item.get("timeRaised"))
    return Warning(
        id=str(wid),
        severity=sev,
        title=title,
        issued_at=issued,
        updated_at=updated,
        geometry=None,
        source="ea:flood-monitoring",
    )


def list_warnings(bbox: Optional[str], region: Optional[str], since: Optional[datetime], ea: Optional[EAClient] = None) -> Dict[str, List[Warning]]:
    client = ea or EAClient()
    items: List[Dict[str, Any]] = []
    centers = None
    if region:
        near = REGION_NEAR.get(region)
        centers = near if isinstance(near, list) else ([near] if near else None)
    if centers:
        seen = set()
        for c in centers:
            chunk = client.get_floods(min_severity=3, lat=c["lat"], lon=c["long"], dist_km=c["dist"])
            for it in chunk:
                k = it.get("@id") or it.get("id") or it.get("message")
                if k and k in seen:
                    continue
                if k:
                    seen.add(k)
                items.append(it)
    else:
        items = client.get_floods(min_severity=3)
    warnings = [_to_warning(it) for it in items]
    return {"items": warnings}
