"""GET /api/v1/session/{id} — poll for analysis results."""
import hmac, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from core import storage

router = APIRouter()
log = logging.getLogger("personastyle.session")

@router.get("/{session_id}")
async def get_session(
    session_id: str,
    x_session_token: Optional[str] = Header(default=None),
):
    data = storage.get(session_id)

    # FIX #4 — always 404 (not 403) for missing or wrong token: prevents enumeration
    if data is None:
        raise HTTPException(404, "Session not found")

    stored_token = data.get("session_token", "")
    provided     = x_session_token or ""

    # FIX #4 — constant-time comparison prevents timing-based token guessing
    if not hmac.compare_digest(stored_token.encode(), provided.encode()):
        log.warning("Bad session token for session %s", session_id)
        raise HTTPException(404, "Session not found")

    # Strip internal token field before returning to client
    return {k: v for k, v in data.items() if k != "session_token"}
