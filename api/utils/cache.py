import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, Request

_cache: Dict[str, Tuple[float, Any]] = {}
_rl: Dict[str, List[float]] = {}
_rl_limit: int = 120
_rl_window_s: int = 60

def cache_get(k: str) -> Optional[Any]:
    entry = _cache.get(k)
    if not entry:
        return None
    exp, val = entry
    if exp < time.time():
        _cache.pop(k, None)
        return None
    return val

def cache_set(k: str, v: Any, ttl: int = 30) -> None:
    _cache[k] = (time.time() + ttl, v)

def rate_limit(req: Request, limit: Optional[int] = None, window_s: Optional[int] = None) -> None:
    lim = limit or _rl_limit
    win = window_s or _rl_window_s
    ip = req.client.host if req.client else "unknown"
    now = time.time()
    q = _rl.get(ip) or []
    q = [t for t in q if now - t < win]
    if len(q) >= lim:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    q.append(now)
    _rl[ip] = q

def set_rate_limit_config(limit: int, window_s: int) -> None:
    global _rl_limit, _rl_window_s
    _rl_limit = limit
    _rl_window_s = window_s

def clear_rate_limit() -> None:
    _rl.clear()

def clear_cache() -> None:
    _cache.clear()
