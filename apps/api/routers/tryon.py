"""POST /api/v1/tryon — Virtual try-on stub (ControlNet pipeline placeholder)."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class TryOnRequest(BaseModel):
    session_id: str
    hairstyle_slug: str
    clothing_slug: Optional[str] = None

@router.post("")
async def tryon(req: TryOnRequest):
    # Production: run ControlNet / img2img Stable Diffusion pipeline here
    return {
        "result_image_url": "https://placehold.co/512x512/1e1e2e/a78bfa?text=Try-On+Coming+Soon",
        "processing_ms": 0,
        "note": "Virtual try-on pipeline (Stable Diffusion + ControlNet) is under development.",
    }
