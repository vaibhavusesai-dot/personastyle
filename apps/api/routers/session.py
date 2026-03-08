"""GET /api/v1/session/{id} — poll for analysis results."""
from fastapi import APIRouter, HTTPException
from core import storage

router = APIRouter()

@router.get("/{session_id}")
async def get_session(session_id: str):
    data = storage.get(session_id)
    if data is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    return data
