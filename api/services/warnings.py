from typing import List, Dict, Any, Optional
from datetime import datetime
from api.models import Warning


def build_key(bbox: Optional[str], region: Optional[str], since: Optional[datetime]) -> str:
    return f"{bbox}:{region}:{since.isoformat() if since else ''}"


def list_warnings(bbox: Optional[str], region: Optional[str], since: Optional[datetime]) -> Dict[str, List[Warning]]:
    return {"items": []}
