import os
from typing import Optional, Tuple
from fastapi import Depends, Request
from ingestion.clients.ea import EAClient
from api.utils.cache import rate_limit


def get_ea_client() -> EAClient:
    base = os.getenv("EA_BASE_URL")
    timeout = os.getenv("TOTAL_TIMEOUT")
    retries = os.getenv("RETRIES")
    return EAClient(
        base_url=base or None,
        timeout=float(timeout) if timeout else None,
        retries=int(retries) if retries else None,
    )


def rate_limiter(req: Request) -> None:
    rate_limit(req)
