"""In-memory session store (swap for Redis in production)."""
from __future__ import annotations
from typing import Dict, Any, Optional
import threading

_store: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()

def save(session_id: str, data: Dict[str, Any]) -> None:
    with _lock:
        _store[session_id] = data

def get(session_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return _store.get(session_id)

def update(session_id: str, patch: Dict[str, Any]) -> None:
    with _lock:
        if session_id in _store:
            _store[session_id].update(patch)
