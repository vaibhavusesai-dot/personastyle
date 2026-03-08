"""POST /api/v1/analyze — accepts images + metadata, fires background analysis."""
from __future__ import annotations
import uuid, threading, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import storage
from services.analyzer.pipeline import run_full_pipeline
from services.stylist.rules_engine import apply_rules
from services.stylist.narrative import generate_narrative

router = APIRouter()

class AnalyzeRequest(BaseModel):
    age: int = Field(ge=13, le=120)
    gender: str
    height_cm: float = Field(ge=50, le=250)
    selfie_base64: str
    full_body_base64: str

def _process(session_id: str, req: AnalyzeRequest):
    try:
        storage.update(session_id, {"status": "processing"})

        # 1. CV pipeline
        cv_data = run_full_pipeline(
            req.selfie_base64, req.full_body_base64,
            req.age, req.gender, req.height_cm,
        )

        # 2. Rules engine
        rules_out = apply_rules(
            cv_data["facial_metrics"],
            cv_data["body_metrics"],
            cv_data["color_profile"],
        )

        # 3. LLM narrative
        narrative, archetype, model, tokens = generate_narrative(
            cv_data["facial_metrics"],
            cv_data["body_metrics"],
            cv_data["color_profile"],
            rules_out["hairstyles"],
            rules_out["clothing"],
            req.age, req.gender,
        )

        recommendation = {
            "session_id": session_id,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "hairstyles": rules_out["hairstyles"],
            "clothing": rules_out["clothing"],
            "color_guidance": rules_out["color_guidance"],
            "style_narrative": narrative,
            "style_archetype": archetype,
            "llm_model": model,
            "llm_tokens_used": tokens,
        }

        storage.update(session_id, {
            "status": "complete",
            "facial_metrics": cv_data["facial_metrics"],
            "body_metrics": cv_data["body_metrics"],
            "color_profile": cv_data["color_profile"],
            "recommendation": recommendation,
        })

    except Exception as e:
        storage.update(session_id, {"status": "error", "error": str(e)})


@router.post("")
async def analyze(req: AnalyzeRequest):
    if len(req.selfie_base64) < 100:
        raise HTTPException(400, "selfie_base64 is too short or invalid")
    if len(req.full_body_base64) < 100:
        raise HTTPException(400, "full_body_base64 is too short or invalid")

    session_id = str(uuid.uuid4())
    storage.save(session_id, {
        "session_id": session_id,
        "status": "pending",
        "age": req.age,
        "gender": req.gender,
        "height_cm": req.height_cm,
    })

    thread = threading.Thread(target=_process, args=(session_id, req), daemon=True)
    thread.start()

    return {
        "session_id": session_id,
        "status": "processing",
        "poll_url": f"/api/v1/session/{session_id}",
    }
