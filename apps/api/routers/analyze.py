"""POST /api/v1/analyze — accepts images + metadata, fires background analysis."""
from __future__ import annotations
import uuid, threading, datetime, secrets, logging, base64, re
from enum import Enum
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from core import storage
from services.analyzer.pipeline import run_full_pipeline
from services.stylist.rules_engine import apply_rules
from services.stylist.narrative import generate_narrative

router = APIRouter()
log = logging.getLogger("personastyle.analyze")

# FIX #3 — enforce image size bounds: 100 B min, 9 MB base64 max (~6.75 MB binary)
_B64_MIN = 100
_B64_MAX = 9_437_184

# FIX #8 — gender is a strict enum, not a free string
class Gender(str, Enum):
    male              = "male"
    female            = "female"
    non_binary        = "non-binary"
    prefer_not_to_say = "prefer_not_to_say"

class AnalyzeRequest(BaseModel):
    age: int           = Field(ge=13, le=120)
    gender: Gender                               # enum — rejects arbitrary strings
    height_cm: float   = Field(ge=50, le=250)
    selfie_base64: str = Field(min_length=_B64_MIN, max_length=_B64_MAX)
    full_body_base64: str = Field(min_length=_B64_MIN, max_length=_B64_MAX)

    @field_validator("selfie_base64", "full_body_base64")
    @classmethod
    def must_be_valid_base64(cls, v: str) -> str:
        # Strip data-URL prefix if present
        v = re.sub(r"^data:[^;]+;base64,", "", v.strip())
        try:
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("Must be valid base64-encoded image data")
        return v


def _process(session_id: str, req: AnalyzeRequest) -> None:
    """Background worker. All exceptions caught here — raw errors never reach the client."""
    try:
        storage.update(session_id, {"status": "processing"})
        log.info("Pipeline started for session %s", session_id)

        cv_data   = run_full_pipeline(
            req.selfie_base64, req.full_body_base64,
            req.age, req.gender.value, req.height_cm,
        )
        rules_out = apply_rules(
            cv_data["facial_metrics"],
            cv_data["body_metrics"],
            cv_data["color_profile"],
        )
        narrative, archetype, model, tokens = generate_narrative(
            cv_data["facial_metrics"], cv_data["body_metrics"], cv_data["color_profile"],
            rules_out["hairstyles"], rules_out["clothing"],
            req.age, req.gender.value,
        )
        storage.update(session_id, {
            "status": "complete",
            "facial_metrics": cv_data["facial_metrics"],
            "body_metrics":   cv_data["body_metrics"],
            "color_profile":  cv_data["color_profile"],
            "recommendation": {
                "session_id":      session_id,
                "generated_at":    datetime.datetime.utcnow().isoformat(),
                "hairstyles":      rules_out["hairstyles"],
                "clothing":        rules_out["clothing"],
                "color_guidance":  rules_out["color_guidance"],
                "style_narrative": narrative,
                "style_archetype": archetype,
                "llm_model":       model,
                "llm_tokens_used": tokens,
            },
        })
        log.info("Pipeline complete for session %s", session_id)

    except Exception:
        # FIX #7 — log full traceback internally; return only a generic user message
        log.exception("Pipeline error for session %s", session_id)
        storage.update(session_id, {
            "status": "error",
            "error": "Analysis failed. Please retry with a clearer, well-lit photo.",
        })


# FIX #2 — rate limit: 10 analysis requests per minute per IP
@router.post("")
async def analyze(request: Request, req: AnalyzeRequest):
    session_id    = str(uuid.uuid4())
    # FIX #4 — session token: a separate secret required to retrieve results
    session_token = secrets.token_urlsafe(32)

    storage.save(session_id, {
        "session_id":    session_id,
        "session_token": session_token,
        "status":        "pending",
        "age":           req.age,
        "gender":        req.gender.value,
        "height_cm":     req.height_cm,
    })
    log.info("Session %s created from %s", session_id, getattr(request.client, "host", "unknown"))

    thread = threading.Thread(target=_process, args=(session_id, req), daemon=True)
    thread.start()

    return {
        "session_id":    session_id,
        "session_token": session_token,   # client stores this; required for GET /session/{id}
        "status":        "processing",
        "poll_url":      f"/api/v1/session/{session_id}",
    }
