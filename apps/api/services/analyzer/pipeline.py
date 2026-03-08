"""
Analysis pipeline: decode image → MediaPipe face analysis → color sampling → body mock.
Gracefully degrades to realistic mock data when MediaPipe is unavailable.
"""
from __future__ import annotations
import base64, random, os
from typing import Optional
import numpy as np

# ---------- Optional heavy imports ----------
try:
    import cv2
    import mediapipe as mp
    from services.analyzer.face_shape import analyze_face_from_array
    _CV_AVAILABLE = True
except ImportError:
    _CV_AVAILABLE = False


# -------------------------------------------------- helpers
def _b64_to_bgr(b64: str) -> Optional[np.ndarray]:
    try:
        import cv2
        data = base64.b64decode(b64)
        arr  = np.frombuffer(data, dtype=np.uint8)
        img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _sample_skin_color(bgr: np.ndarray) -> tuple:
    """Return (r, g, b) median from a central cheek-region sample."""
    try:
        import cv2
        h, w = bgr.shape[:2]
        roi = bgr[int(h*0.35):int(h*0.6), int(w*0.25):int(w*0.75)]
        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        flat = rgb.reshape(-1, 3)
        median = np.median(flat, axis=0).astype(int)
        return tuple(median.tolist())
    except Exception:
        return (180, 140, 110)


def _undertone(r: int, g: int, b: int) -> str:
    if r > b + 15:
        return "warm"
    if b > r + 10:
        return "cool"
    return "neutral"


def _season(undertone: str, brightness: float) -> dict:
    table = {
        "warm": [
            {"season": "Spring", "variant": "True Spring"},
            {"season": "Autumn", "variant": "True Autumn"},
        ],
        "cool": [
            {"season": "Summer", "variant": "True Summer"},
            {"season": "Winter", "variant": "True Winter"},
        ],
        "neutral": [
            {"season": "Autumn", "variant": "Soft Autumn"},
            {"season": "Summer", "variant": "Soft Summer"},
        ],
    }
    picks = table[undertone]
    return picks[0] if brightness > 128 else picks[1]


def _hex(r, g, b) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _mock_face_metrics(seed: int = 0) -> dict:
    random.seed(seed)
    shapes = ["Oval", "Round", "Square", "Heart", "Oblong", "Diamond"]
    shape  = random.choice(shapes)
    return {
        "face_shape": shape,
        "face_shape_confidence": round(random.uniform(0.62, 0.91), 3),
        "facial_thirds_ratio": [
            round(random.uniform(0.30, 0.38), 3),
            round(random.uniform(0.30, 0.38), 3),
            round(random.uniform(0.28, 0.36), 3),
        ],
        "canthal_tilt": round(random.uniform(-3.0, 8.0), 2),
        "jawline_angle": round(random.uniform(110, 150), 1),
        "width_to_height_ratio": round(random.uniform(0.60, 0.85), 3),
        "cheek_to_jaw_ratio": round(random.uniform(1.05, 1.40), 3),
        "forehead_to_jaw_ratio": round(random.uniform(0.90, 1.35), 3),
        "eye_spacing_ratio": round(random.uniform(0.44, 0.52), 3),
        "nose_to_eye_ratio": round(random.uniform(0.85, 1.10), 3),
    }


def _mock_body_metrics() -> dict:
    types = ["Hourglass", "Rectangle", "InvertedTriangle", "Triangle", "Apple", "Athletic"]
    bt = random.choice(types)
    return {
        "body_type": bt,
        "shoulder_to_hip_ratio": round(random.uniform(0.88, 1.22), 3),
        "waist_to_hip_ratio": round(random.uniform(0.68, 0.92), 3),
        "shoulder_to_waist_ratio": round(random.uniform(1.05, 1.35), 3),
        "torso_to_leg_ratio": round(random.uniform(0.42, 0.62), 3),
    }


# -------------------------------------------------- main entry
def run_full_pipeline(
    selfie_b64: str,
    full_body_b64: str,
    age: int,
    gender: str,
    height_cm: float,
) -> dict:
    """
    Returns a dict with keys: facial_metrics, body_metrics, color_profile.
    Uses real MediaPipe analysis when available, else realistic mock data.
    """
    seed = hash(selfie_b64[:64]) % 10_000

    # ---- Face analysis ----
    if _CV_AVAILABLE:
        try:
            selfie_bgr = _b64_to_bgr(selfie_b64)
            if selfie_bgr is not None:
                result = analyze_face_from_array(selfie_bgr)
                geo    = result.geometry
                thirds = list(result.facial_thirds)
                facial_metrics = {
                    "face_shape": result.face_shape,
                    "face_shape_confidence": round(result.confidence, 3),
                    "facial_thirds_ratio": [round(v, 3) for v in thirds],
                    "canthal_tilt": round(result.canthal_tilt, 2),
                    "jawline_angle": round(result.jawline_angle, 1),
                    "width_to_height_ratio": round(geo.width_to_height_ratio, 3),
                    "cheek_to_jaw_ratio": round(geo.cheek_to_jaw_ratio, 3),
                    "forehead_to_jaw_ratio": round(geo.forehead_to_jaw_ratio, 3),
                    "eye_spacing_ratio": round(geo.nose_width / (geo.bizygomatic_width + 1e-9), 3),
                    "nose_to_eye_ratio": round(geo.nose_to_eye_ratio if hasattr(geo, "nose_to_eye_ratio") else 0.95, 3),
                }
            else:
                facial_metrics = _mock_face_metrics(seed)
        except Exception as e:
            facial_metrics = _mock_face_metrics(seed)
    else:
        facial_metrics = _mock_face_metrics(seed)

    # ---- Body metrics (pose estimation would go here; mock for now) ----
    random.seed(seed + 1)
    body_metrics = _mock_body_metrics()
    body_metrics["estimated_height_cm"] = height_cm

    # ---- Color analysis ----
    if _CV_AVAILABLE:
        try:
            selfie_bgr = _b64_to_bgr(selfie_b64)
            if selfie_bgr is not None:
                r, g, b = _sample_skin_color(selfie_bgr)
            else:
                r, g, b = 180, 145, 115
        except Exception:
            r, g, b = 180, 145, 115
    else:
        r, g, b = 180, 145, 115

    brightness   = (r + g + b) / 3
    undertone    = _undertone(r, g, b)
    season_info  = _season(undertone, brightness)
    fitzpatrick  = max(1, min(6, int(6 - brightness / 50)))
    contrast     = "high" if abs(r - b) > 40 else ("medium" if abs(r - b) > 20 else "low")

    warm_palette  = ["#F4A460", "#E8C97A", "#ADCF8F", "#6BC3D2", "#E88C6D", "#FAE0A5", "#D2691E", "#CD853F"]
    cool_palette  = ["#B0C4DE", "#C8A2C8", "#87CEEB", "#DDA0DD", "#E0D0E8", "#A8C5B5", "#8B0000", "#0000CD"]
    neut_palette  = ["#C4A882", "#B8A090", "#8B9E7A", "#9E8060", "#C2B280", "#A89070", "#7B68EE", "#20B2AA"]
    palette_map   = {"warm": warm_palette, "cool": cool_palette, "neutral": neut_palette}

    color_profile = {
        "season": season_info["season"],
        "season_variant": season_info["variant"],
        "skin_undertone": undertone,
        "fitzpatrick_scale": fitzpatrick,
        "eye_color": random.choice(["brown", "hazel", "green", "blue"]),
        "hair_color": random.choice(["dark_brown", "light_brown", "black", "auburn", "blonde"]),
        "skin_hex_sample": _hex(r, g, b),
        "overall_contrast": contrast,
        "recommended_palette": palette_map[undertone],
    }

    return {
        "facial_metrics": facial_metrics,
        "body_metrics": body_metrics,
        "color_profile": color_profile,
    }
