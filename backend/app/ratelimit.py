"""Small in-memory sliding-window limiter (per process). For multi-instance deployments use nginx limit_req or Redis."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import TRUST_PROXY

_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(key: str, limit: int, window: int, now: float | None = None) -> int:
    """Returns 0 if allowed, else seconds to wait."""
    now = time.monotonic() if now is None else now
    q = _hits[key]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        return max(1, int(q[0] + window - now) + 1)
    q.append(now)
    return 0


def limit(name: str, limit_n: int, window: int):
    def dep(request: Request) -> None:
        wait = check(f"{name}:{client_ip(request)}", limit_n, window)
        if wait:
            raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": str(wait)})
    return dep
