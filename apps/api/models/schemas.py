"""
PersonaStyle — Pydantic request/response schemas (mirrors TypeScript interfaces).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Gender(str, Enum):
    male = "male"
    female = "female"
    non_binary = "non-binary"
    prefer_not = "prefer_not_to_say"


class Season(str, Enum):
    spring = "Spring"
    summer = "Summer"
    autumn = "Autumn"
    winter = "Winter"


class FaceShape(str, Enum):
    oval     = "Oval"
    round    = "Round"
    square   = "Square"
    heart    = "Heart"
    diamond  = "Diamond"
    oblong   = "Oblong"
    triangle = "Triangle"


class BodyType(str, Enum):
    hourglass          = "Hourglass"
    rectangle          = "Rectangle"
    inverted_triangle  = "InvertedTriangle"
    triangle           = "Triangle"
    apple              = "Apple"
    athletic           = "Athletic"


class AnalysisStatus(str, Enum):
    pending    = "pending"
    processing = "processing"
    complete   = "complete"
    error      = "error"


# ---------------------------------------------------------------------------
# CV output schemas
# ---------------------------------------------------------------------------

class FacialMetrics(BaseModel):
    facial_thirds_ratio: Tuple[float, float, float]
    canthal_tilt: float
    jawline_angle: float
    width_to_height_ratio: float
    cheek_to_jaw_ratio: float
    forehead_to_jaw_ratio: float
    eye_spacing_ratio: float
    nose_to_eye_ratio: float
    face_shape: FaceShape
    face_shape_confidence: float = Field(ge=0, le=1)


class BodyMetrics(BaseModel):
    body_type: BodyType
    shoulder_to_hip_ratio: float
    waist_to_hip_ratio: float
    shoulder_to_waist_ratio: float
    torso_to_leg_ratio: float
    estimated_height_cm: Optional[float] = None


class ColorProfile(BaseModel):
    season: Season
    season_variant: str
    skin_undertone: str
    fitzpatrick_scale: int = Field(ge=1, le=6)
    eye_color: str
    hair_color: str
    skin_hex_sample: str
    overall_contrast: str
    recommended_palette: List[str]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    age: int = Field(ge=13, le=120)
    gender: Gender
    height_cm: float = Field(ge=50, le=250)
    selfie_base64: str
    full_body_base64: str


class AnalyzeResponse(BaseModel):
    session_id: str
    status: AnalysisStatus = AnalysisStatus.processing
    poll_url: str


class HairstyleRecommendation(BaseModel):
    name: str
    slug: str
    primary_tag: str
    tags: List[str]
    rationale: str
    confidence: float = Field(ge=0, le=1)
    reference_image_url: Optional[str] = None


class ClothingRecommendation(BaseModel):
    category: str
    name: str
    slug: str
    silhouette: str
    primary_tag: str
    tags: List[str]
    rationale: str
    confidence: float = Field(ge=0, le=1)
    reference_image_url: Optional[str] = None


class ColorRecommendation(BaseModel):
    category: str
    recommended_colors: List[str]
    colors_to_avoid: List[str]
    rationale: str


class StyleRecommendation(BaseModel):
    session_id: str
    generated_at: str
    hairstyles: List[HairstyleRecommendation]
    clothing: List[ClothingRecommendation]
    color_guidance: List[ColorRecommendation]
    style_narrative: str
    style_archetype: str
    llm_model: str
    llm_tokens_used: Optional[int] = None


class SessionResponse(BaseModel):
    session_id: str
    status: AnalysisStatus
    facial_metrics: Optional[FacialMetrics] = None
    body_metrics: Optional[BodyMetrics] = None
    color_profile: Optional[ColorProfile] = None
    recommendation: Optional[StyleRecommendation] = None
    error: Optional[str] = None


class TryOnRequest(BaseModel):
    session_id: str
    hairstyle_slug: str
    clothing_slug: Optional[str] = None


class TryOnResponse(BaseModel):
    result_image_url: str
    processing_ms: int
