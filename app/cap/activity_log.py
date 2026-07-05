# app/cap/activity_log.py
import asyncio
from datetime import datetime
from collections import deque

_MAX_EVENTS = 50
_log = deque(maxlen=_MAX_EVENTS)
_lock = asyncio.Lock()


async def log_event(event_type: str, detail: str, meta: dict | None = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "detail": detail,
        "meta": meta or {},
    }
    async with _lock:
        _log.appendleft(entry)
    print(f"[CAP][{event_type}] {detail}")


def get_events(limit: int = 20):
    return list(_log)[:limit]