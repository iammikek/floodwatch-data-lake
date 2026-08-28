import os
import secrets
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.status import HTTP_401_UNAUTHORIZED

from ingestion.clients.ea import EAClient
from api.utils.cache import rate_limit

_bearer_scheme = HTTPBearer(auto_error=False)


def get_ea_client() -> EAClient:
    base = os.getenv("EA_BASE_URL")
    timeout = os.getenv("TOTAL_TIMEOUT")
    retries = os.getenv("RETRIES")
    return EAClient(
        base_url=base or None,
        timeout=float(timeout) if timeout else None,
        retries=int(retries) if retries else None,
    )


def require_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> None:
    """Enforce Bearer auth when LAKE_API_TOKEN is set. No-op when unset (local/dev)."""
    expected = (os.getenv("LAKE_API_TOKEN") or "").strip()
    if not expected:
        return
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provided = (credentials.credentials or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


def rate_limiter(req: Request) -> Dict[str, int]:
    lim = os.getenv("RL_LIMIT")
    win = os.getenv("RL_WINDOW_S")
    limit = int(lim) if lim else None
    window_s = int(win) if win else None
    return rate_limit(req, limit=limit, window_s=window_s)


def _get_ttl(env_name: str, default: int = 30) -> int:
    val = os.getenv(env_name)
    try:
        return int(val) if val else default
    except Exception:
        return default


def warnings_ttl() -> int:
    return _get_ttl("WARNINGS_TTL", 30)


def polygons_ttl() -> int:
    return _get_ttl("POLYGONS_TTL", 30)


def measurements_ttl() -> int:
    return _get_ttl("MEASUREMENTS_TTL", 30)
