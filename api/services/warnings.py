from typing import List, Dict, Any, Optional
from datetime import datetime
from api.models import Warning
from ingestion.clients.ea import EAClient


def build_key(bbox: Optional[str], region: Optional[str], since: Optional[datetime]) -> str:
    return f"{bbox}:{region}:{since.isoformat() if since else ''}"


def list_warnings(bbox: Optional[str], region: Optional[str], since: Optional[datetime], ea: Optional[EAClient] = None) -> Dict[str, List[Warning]]:
    return {"items": []}
