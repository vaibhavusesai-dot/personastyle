"""
In-memory session store with TTL-based expiration (swap for Redis in production).
FIX #6 — sessions expire after SESSION_TTL_SECONDS; a background reaper thread
         prevents unbounded memory growth.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
import threading, time, logging

log = logging.getLogger("personastyle.storage")

# Sessions expire 2 hours after creation; reaper runs every 10 minutes
SESSION_TTL_SECONDS = 2 * 60 * 60
_REAP_INTERVAL      = 10 * 60

_store: Dict[str, Dict[str, Any]] = {}
_lock  = threading.Lock()


def save(session_id: str, data: Dict[str, Any]) -> None:
    with _lock:
        _store[session_id] = {**data, "_created_at": time.monotonic()}


def get(session_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        entry = _store.get(session_id)
        if entry is None:
            return None
        # Treat expired sessions as non-existent
        if time.monotonic() - entry.get("_created_at", 0) > SESSION_TTL_SECONDS:
            del _store[session_id]
            return None
        # Return a copy without the internal timestamp key
        return {k: v for k, v in entry.items() if k != "_created_at"}


def update(session_id: str, patch: Dict[str, Any]) -> None:
    with _lock:
        if session_id in _store:
            _store[session_id].update(patch)


def _reap_expired() -> None:
    """Background thread: removes sessions older than SESSION_TTL_SECONDS."""
    while True:
        time.sleep(_REAP_INTERVAL)
        cutoff = time.monotonic() - SESSION_TTL_SECONDS
        with _lock:
            expired = [sid for sid, data in _store.items()
                       if data.get("_created_at", 0) < cutoff]
            for sid in expired:
                del _store[sid]
        if expired:
            log.info("Reaped %d expired sessions", len(expired))


# Start reaper daemon on module load
_reaper = threading.Thread(target=_reap_expired, daemon=True, name="session-reaper")
_reaper.start()
