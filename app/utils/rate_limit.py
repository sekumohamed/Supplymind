# app/utils/rate_limit.py
import time
import asyncio
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from app.config import get_settings

settings = get_settings()

# Public, unauthenticated calls to /analyze are capped per client IP.
# This protects real Groq/Tavily API spend from abuse or scraping —
# it is NOT a substitute for the real CROO payment gate, which is a
# separate, already-correct path (CROO verifies payment server-side
# before ever calling into this app).
MAX_REQUESTS_PER_WINDOW = 15
WINDOW_SECONDS = 3600  # 1 hour

_request_log: dict[str, deque] = defaultdict(deque)
_lock = asyncio.Lock()


def _get_client_ip(request: Request) -> str:
    # Respect X-Forwarded-For if running behind a reverse proxy (e.g. HF Spaces),
    # since request.client.host would otherwise just show the proxy's IP.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(request: Request):
    """
    FastAPI dependency. Raises 429 if the caller has exceeded
    MAX_REQUESTS_PER_WINDOW within WINDOW_SECONDS.

    Bypass: if settings.internal_api_key is set AND the caller sends a
    matching X-Internal-Key header, the limit is skipped entirely.
    This is intended ONLY for local development, scripts, or CI — never
    for the public-facing dashboard, since any header shipped to a
    public frontend is visible to anyone via browser dev tools and
    provides no real security.
    """
    if settings.internal_api_key:
        provided_key = request.headers.get("x-internal-key", "")
        if provided_key and provided_key == settings.internal_api_key:
            return  # trusted internal caller — no limit applied

    client_ip = _get_client_ip(request)
    now = time.time()

    async with _lock:
        window = _request_log[client_ip]

        # Drop timestamps outside the current window
        while window and window[0] <= now - WINDOW_SECONDS:
            window.popleft()

        if len(window) >= MAX_REQUESTS_PER_WINDOW:
            retry_after = int(WINDOW_SECONDS - (now - window[0]))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} requests "
                    f"per {WINDOW_SECONDS // 60} minutes on this endpoint. "
                    f"Retry after {retry_after}s, or place a paid order via the "
                    f"CROO Agent Store for unmetered access."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)