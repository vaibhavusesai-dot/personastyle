"""
PersonaStyle — Face Shape Detector
===================================
Uses MediaPipe FaceMesh (468 landmarks) + OpenCV to:
  1. Extract key facial geometry measurements.
  2. Compute QOVES-inspired metrics (Facial Thirds, Canthal Tilt, Jawline Angle).
  3. Classify one of 5 canonical face shapes:
     Oval | Round | Square | Heart | Oblong (+ Diamond as a bonus 6th).

Usage
-----
  python face_shape.py --image path/to/selfie.jpg [--debug]

Dependencies
------------
  pip install mediapipe opencv-python-headless numpy

Architecture
------------
  ImageLoader → FaceMeshExtractor → GeometryCalculator → ShapeClassifier → Result
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("personastyle.face_shape")

# ---------------------------------------------------------------------------
# MediaPipe landmark indices (subset of the 468-point FaceMesh)
# Reference: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
# ---------------------------------------------------------------------------

# Hairline / top of face (approximate — FaceMesh doesn't track hairline directly)
TOP_OF_FACE = 10        # mid-forehead, closest to hairline

# Chin
CHIN_TIP = 152

# Cheekbones (widest point of face)
LEFT_CHEEK = 234
RIGHT_CHEEK = 454

# Forehead width (approx temple region)
LEFT_TEMPLE = 162
RIGHT_TEMPLE = 389

# Jawline corners (gonion)
LEFT_JAW = 172
RIGHT_JAW = 397

# Jaw midpoints for angle calculation
LEFT_JAW_MID = 136
RIGHT_JAW_MID = 365

# Brow landmarks
LEFT_BROW_INNER = 55
RIGHT_BROW_INNER = 285
LEFT_BROW_OUTER = 46
RIGHT_BROW_OUTER = 276

# Nose base
NOSE_BASE = 2
NOSE_TIP = 4
LEFT_NOSE_WING = 129
RIGHT_NOSE_WING = 358

# Eye corners (canthus)
LEFT_EYE_INNER = 133   # inner canthus
LEFT_EYE_OUTER = 33    # outer canthus
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263

# Lip corners
UPPER_LIP_TOP = 0
LOWER_LIP_BOTTOM = 17


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Point2D:
    x: float
    y: float

    def distance_to(self, other: "Point2D") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def angle_to(self, other: "Point2D") -> float:
        """Angle in degrees from self to other (clockwise positive)."""
        return math.degrees(math.atan2(other.y - self.y, other.x - self.x))


@dataclasses.dataclass
class FacialGeometry:
    """Raw measurements extracted from landmarks (all in pixel space)."""

    # Width measurements
    bizygomatic_width: float        # cheek-to-cheek (widest)
    forehead_width: float           # temple-to-temple
    jaw_width: float                # gonion-to-gonion
    nose_width: float

    # Height measurements
    face_height: float              # top-of-face to chin tip
    upper_third: float              # forehead (top → brow)
    middle_third: float             # nose region (brow → nose base)
    lower_third: float              # lower face (nose base → chin)

    # Angles
    canthal_tilt_deg: float         # positive = upward slant
    left_jawline_angle_deg: float
    right_jawline_angle_deg: float

    # Derived ratios
    width_to_height_ratio: float
    cheek_to_jaw_ratio: float
    forehead_to_jaw_ratio: float


@dataclasses.dataclass
class FaceShapeResult:
    face_shape: str
    confidence: float               # [0, 1]
    runner_up: str
    runner_up_confidence: float
    geometry: FacialGeometry
    facial_thirds: Tuple[float, float, float]
    canthal_tilt: float
    jawline_angle: float            # average of left/right
    debug_image_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "face_shape": self.face_shape,
            "confidence": round(self.confidence, 3),
            "runner_up": self.runner_up,
            "runner_up_confidence": round(self.runner_up_confidence, 3),
            "metrics": {
                "facial_thirds": [round(v, 3) for v in self.facial_thirds],
                "canthal_tilt_deg": round(self.canthal_tilt, 2),
                "jawline_angle_deg": round(self.jawline_angle, 2),
                "width_to_height_ratio": round(self.geometry.width_to_height_ratio, 3),
                "cheek_to_jaw_ratio": round(self.geometry.cheek_to_jaw_ratio, 3),
                "forehead_to_jaw_ratio": round(self.geometry.forehead_to_jaw_ratio, 3),
                "bizygomatic_width_px": round(self.geometry.bizygomatic_width, 1),
                "jaw_width_px": round(self.geometry.jaw_width, 1),
                "face_height_px": round(self.geometry.face_height, 1),
            },
        }


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------

class FaceMeshExtractor:
    """Wraps MediaPipe FaceMesh and yields landmark arrays."""

    def __init__(self, static_mode: bool = True, max_faces: int = 1):
        self._mp_face_mesh = mp.solutions.face_mesh
        self._face_mesh = self._mp_face_mesh.FaceMesh(
            static_image_mode=static_mode,
            max_num_faces=max_faces,
            refine_landmarks=True,   # enables iris landmarks (468 → 478)
            min_detection_confidence=0.5,
        )

    def extract(self, bgr_image: np.ndarray) -> Optional[List[mp.framework.formats.landmark_pb2.NormalizedLandmark]]:
        """Return landmark list for the first detected face, or None."""
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            log.warning("No face detected in image.")
            return None
        if len(results.multi_face_landmarks) > 1:
            log.info("Multiple faces detected; using the largest (index 0).")
        return results.multi_face_landmarks[0].landmark

    def close(self):
        self._face_mesh.close()


class GeometryCalculator:
    """Converts a MediaPipe landmark list into FacialGeometry measurements."""

    def __init__(self, image_width: int, image_height: int):
        self.w = image_width
        self.h = image_height

    def _lm(self, landmarks, idx: int) -> Point2D:
        lm = landmarks[idx]
        return Point2D(lm.x * self.w, lm.y * self.h)

    def _angle_at_vertex(self, a: Point2D, vertex: Point2D, b: Point2D) -> float:
        """Interior angle at `vertex` formed by rays vertex→a and vertex→b (degrees)."""
        v1 = (a.x - vertex.x, a.y - vertex.y)
        v2 = (b.x - vertex.x, b.y - vertex.y)
        cos_angle = (v1[0]*v2[0] + v1[1]*v2[1]) / (
            math.hypot(*v1) * math.hypot(*v2) + 1e-9
        )
        return math.degrees(math.acos(max(-1.0, min(1.0, cos_angle))))

    def calculate(self, landmarks) -> FacialGeometry:
        lm = self._lm  # shorthand

        # --- Width measurements ---
        bizygomatic_width = lm(landmarks, LEFT_CHEEK).distance_to(lm(landmarks, RIGHT_CHEEK))
        forehead_width    = lm(landmarks, LEFT_TEMPLE).distance_to(lm(landmarks, RIGHT_TEMPLE))
        jaw_width         = lm(landmarks, LEFT_JAW).distance_to(lm(landmarks, RIGHT_JAW))
        nose_width        = lm(landmarks, LEFT_NOSE_WING).distance_to(lm(landmarks, RIGHT_NOSE_WING))

        # --- Height / thirds ---
        top     = lm(landmarks, TOP_OF_FACE)
        brow_l  = lm(landmarks, LEFT_BROW_INNER)
        brow_r  = lm(landmarks, RIGHT_BROW_INNER)
        brow_mid_y = (brow_l.y + brow_r.y) / 2
        nose_base_pt = lm(landmarks, NOSE_BASE)
        chin    = lm(landmarks, CHIN_TIP)

        face_height   = top.distance_to(chin)
        upper_third   = abs(brow_mid_y - top.y)
        middle_third  = abs(nose_base_pt.y - brow_mid_y)
        lower_third   = abs(chin.y - nose_base_pt.y)

        # --- Canthal tilt (left eye; averaged with right) ---
        def _canthal_tilt(inner: Point2D, outer: Point2D) -> float:
            return outer.angle_to(inner)   # deg; positive = upward outer canthus

        ct_left  = _canthal_tilt(lm(landmarks, LEFT_EYE_INNER),  lm(landmarks, LEFT_EYE_OUTER))
        ct_right = _canthal_tilt(lm(landmarks, RIGHT_EYE_INNER), lm(landmarks, RIGHT_EYE_OUTER))
        canthal_tilt = (ct_left + ct_right) / 2

        # --- Jawline angle (at gonion) ---
        def _jaw_angle(jaw_pt: Point2D, chin_pt: Point2D, cheek_pt: Point2D) -> float:
            return self._angle_at_vertex(chin_pt, jaw_pt, cheek_pt)

        left_jaw_angle  = _jaw_angle(
            lm(landmarks, LEFT_JAW),
            lm(landmarks, CHIN_TIP),
            lm(landmarks, LEFT_CHEEK),
        )
        right_jaw_angle = _jaw_angle(
            lm(landmarks, RIGHT_JAW),
            lm(landmarks, CHIN_TIP),
            lm(landmarks, RIGHT_CHEEK),
        )

        # --- Ratios ---
        whr = bizygomatic_width / (face_height + 1e-9)
        c2j = bizygomatic_width / (jaw_width + 1e-9)
        f2j = forehead_width    / (jaw_width + 1e-9)

        return FacialGeometry(
            bizygomatic_width=bizygomatic_width,
            forehead_width=forehead_width,
            jaw_width=jaw_width,
            nose_width=nose_width,
            face_height=face_height,
            upper_third=upper_third,
            middle_third=middle_third,
            lower_third=lower_third,
            canthal_tilt_deg=canthal_tilt,
            left_jawline_angle_deg=left_jaw_angle,
            right_jawline_angle_deg=right_jaw_angle,
            width_to_height_ratio=whr,
            cheek_to_jaw_ratio=c2j,
            forehead_to_jaw_ratio=f2j,
        )


class ShapeClassifier:
    """
    Rule-based classifier mapping FacialGeometry to one of 6 face shapes.

    Shape Decision Tree
    -------------------
    Face shapes are distinguished by three primary axes:
      A. Width-to-height ratio (WHR)      — wide vs narrow face
      B. Cheek-to-jaw ratio (C2J)         — tapered vs wide jaw
      C. Forehead-to-jaw ratio (F2J)      — balanced vs tapered top/bottom
      D. Jawline angle                    — defined/angular vs soft/round
      E. Face height relative to width    — elongated vs compact

    Canonical thresholds (empirically derived from academic literature):
      Oval:    WHR 0.65–0.75, C2J > 1.15 (cheek wider than jaw), F2J ≈ 1.0–1.2
      Round:   WHR > 0.75, C2J 1.0–1.15, jaw angle > 130°
      Square:  WHR 0.75–0.85, jaw angle < 120°, C2J ≈ 1.0
      Heart:   F2J > 1.25 (wide forehead, narrow jaw), chin pointed
      Oblong:  WHR < 0.65 (narrow/tall face), jaw and cheek similar width
      Diamond: C2J > 1.2, narrow forehead (F2J < 0.9)
    """

    # (shape_name, weight_vector) — weights applied to normalised feature deltas
    SHAPES = ["Oval", "Round", "Square", "Heart", "Oblong", "Diamond"]

    # Ideal centroid values for each shape: [WHR, C2J, F2J, jaw_angle_norm]
    # jaw_angle_norm = jaw_angle / 180
    CENTROIDS: dict[str, list[float]] = {
        "Oval":    [0.70, 1.20, 1.10, 0.72],  # balanced proportions
        "Round":   [0.82, 1.08, 1.05, 0.76],  # wide, soft jaw
        "Square":  [0.80, 1.02, 1.00, 0.62],  # wide, angular jaw
        "Heart":   [0.72, 1.30, 1.35, 0.70],  # wide forehead, narrow jaw
        "Oblong":  [0.58, 1.18, 1.08, 0.70],  # long, narrow
        "Diamond": [0.68, 1.35, 0.85, 0.68],  # prominent cheeks, narrow top & bottom
    }

    FEATURE_WEIGHTS = [3.0, 2.5, 2.5, 2.0]   # WHR, C2J, F2J, jaw_angle_norm

    def classify(self, geo: FacialGeometry) -> dict[str, float]:
        """Return {shape: confidence} dict sorted by descending confidence."""
        jaw_angle_avg = (geo.left_jawline_angle_deg + geo.right_jawline_angle_deg) / 2
        features = [
            geo.width_to_height_ratio,
            geo.cheek_to_jaw_ratio,
            geo.forehead_to_jaw_ratio,
            jaw_angle_avg / 180.0,
        ]

        scores: dict[str, float] = {}
        for shape, centroid in self.CENTROIDS.items():
            # Weighted Euclidean distance to centroid
            dist = math.sqrt(
                sum(
                    w * (f - c) ** 2
                    for w, f, c in zip(self.FEATURE_WEIGHTS, features, centroid)
                )
            )
            scores[shape] = dist

        # Convert distance to confidence: softmax of inverse distances
        inv = {s: 1.0 / (d + 1e-6) for s, d in scores.items()}
        total = sum(inv.values())
        confidences = {s: v / total for s, v in inv.items()}
        return dict(sorted(confidences.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# Debug visualisation
# ---------------------------------------------------------------------------

class DebugVisualiser:
    """Draws landmarks, measurements and shape label onto the image."""

    COLORS = {
        "landmark": (0, 255, 0),
        "key_point": (0, 0, 255),
        "line": (255, 200, 0),
        "text": (255, 255, 255),
        "text_bg": (30, 30, 30),
    }

    KEY_INDICES = [
        TOP_OF_FACE, CHIN_TIP,
        LEFT_CHEEK, RIGHT_CHEEK,
        LEFT_TEMPLE, RIGHT_TEMPLE,
        LEFT_JAW, RIGHT_JAW,
        LEFT_EYE_INNER, LEFT_EYE_OUTER,
        RIGHT_EYE_INNER, RIGHT_EYE_OUTER,
    ]

    def draw(
        self,
        bgr_image: np.ndarray,
        landmarks,
        result: FaceShapeResult,
    ) -> np.ndarray:
        img = bgr_image.copy()
        h, w = img.shape[:2]

        def px(idx: int) -> Tuple[int, int]:
            lm = landmarks[idx]
            return (int(lm.x * w), int(lm.y * h))

        # Draw all 468 landmarks (small dots)
        for lm in landmarks:
            cv2.circle(img, (int(lm.x * w), int(lm.y * h)), 1, self.COLORS["landmark"], -1)

        # Draw key measurement points
        for idx in self.KEY_INDICES:
            cv2.circle(img, px(idx), 5, self.COLORS["key_point"], -1)

        # Width lines
        cv2.line(img, px(LEFT_CHEEK), px(RIGHT_CHEEK), self.COLORS["line"], 2)
        cv2.line(img, px(LEFT_JAW),   px(RIGHT_JAW),   self.COLORS["line"], 2)
        cv2.line(img, px(LEFT_TEMPLE),px(RIGHT_TEMPLE),self.COLORS["line"], 2)

        # Height line
        cv2.line(img, px(TOP_OF_FACE), px(CHIN_TIP), self.COLORS["line"], 2)

        # Jawline path (simplified)
        jaw_path = [LEFT_TEMPLE, LEFT_JAW, CHIN_TIP, RIGHT_JAW, RIGHT_TEMPLE]
        for i in range(len(jaw_path) - 1):
            cv2.line(img, px(jaw_path[i]), px(jaw_path[i+1]), (255, 100, 100), 2)

        # Overlay result text
        label = f"{result.face_shape}  ({result.confidence*100:.1f}%)"
        sub   = f"Runner-up: {result.runner_up} ({result.runner_up_confidence*100:.1f}%)"
        whr   = f"WHR: {result.geometry.width_to_height_ratio:.2f}  C2J: {result.geometry.cheek_to_jaw_ratio:.2f}  F2J: {result.geometry.forehead_to_jaw_ratio:.2f}"
        angles= f"Jaw: {result.jawline_angle:.1f}°  Canthal: {result.canthal_tilt:.1f}°"

        for i, text in enumerate([label, sub, whr, angles]):
            y = 32 + i * 28
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(img, (8, y - th - 6), (8 + tw + 6, y + 4), self.COLORS["text_bg"], -1)
            cv2.putText(img, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLORS["text"], 2)

        return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_face(image_path: str, debug: bool = False) -> FaceShapeResult:
    """
    Full pipeline: load image → extract landmarks → compute geometry → classify.

    Parameters
    ----------
    image_path : str
        Path to the input selfie image.
    debug : bool
        If True, saves an annotated debug image alongside the input.

    Returns
    -------
    FaceShapeResult
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    bgr = cv2.imread(str(path))
    if bgr is None:
        raise ValueError(f"OpenCV could not read image: {image_path}")

    h, w = bgr.shape[:2]
    log.info("Image loaded: %s (%dx%d)", path.name, w, h)

    # 1. Extract landmarks
    extractor  = FaceMeshExtractor()
    landmarks  = extractor.extract(bgr)
    extractor.close()

    if landmarks is None:
        raise RuntimeError("Face detection failed — ensure the image contains a clear frontal face.")

    log.info("Landmarks extracted: %d points", len(landmarks))

    # 2. Compute geometry
    calc = GeometryCalculator(w, h)
    geo  = calc.calculate(landmarks)

    # 3. Classify shape
    classifier   = ShapeClassifier()
    confidences  = classifier.classify(geo)
    ranked       = list(confidences.items())   # sorted descending

    face_shape         = ranked[0][0]
    confidence         = ranked[0][1]
    runner_up          = ranked[1][0]
    runner_up_conf     = ranked[1][1]

    log.info(
        "Classification: %s (%.1f%%)  |  Runner-up: %s (%.1f%%)",
        face_shape, confidence * 100,
        runner_up, runner_up_conf * 100,
    )

    # 4. Compose result
    thirds = (geo.upper_third, geo.middle_third, geo.lower_third)
    total  = sum(thirds) + 1e-9
    thirds_normalised = (thirds[0]/total, thirds[1]/total, thirds[2]/total)
    jaw_avg = (geo.left_jawline_angle_deg + geo.right_jawline_angle_deg) / 2

    result = FaceShapeResult(
        face_shape=face_shape,
        confidence=confidence,
        runner_up=runner_up,
        runner_up_confidence=runner_up_conf,
        geometry=geo,
        facial_thirds=thirds_normalised,
        canthal_tilt=geo.canthal_tilt_deg,
        jawline_angle=jaw_avg,
    )

    # 5. Optional debug output
    if debug:
        vis         = DebugVisualiser()
        debug_img   = vis.draw(bgr, landmarks, result)
        debug_path  = path.with_stem(path.stem + "_debug").with_suffix(".jpg")
        cv2.imwrite(str(debug_path), debug_img)
        result.debug_image_path = str(debug_path)
        log.info("Debug image saved: %s", debug_path)

    return result


def analyze_face_from_array(
    bgr_image: np.ndarray,
) -> FaceShapeResult:
    """
    Same as analyze_face() but accepts a pre-loaded BGR numpy array.
    Suitable for use within the FastAPI service (no disk I/O).
    """
    h, w = bgr_image.shape[:2]
    extractor = FaceMeshExtractor()
    landmarks = extractor.extract(bgr_image)
    extractor.close()

    if landmarks is None:
        raise RuntimeError("No face detected in the provided image array.")

    calc        = GeometryCalculator(w, h)
    geo         = calc.calculate(landmarks)
    classifier  = ShapeClassifier()
    confidences = classifier.classify(geo)
    ranked      = list(confidences.items())

    thirds      = (geo.upper_third, geo.middle_third, geo.lower_third)
    total       = sum(thirds) + 1e-9
    thirds_norm = (thirds[0]/total, thirds[1]/total, thirds[2]/total)
    jaw_avg     = (geo.left_jawline_angle_deg + geo.right_jawline_angle_deg) / 2

    return FaceShapeResult(
        face_shape=ranked[0][0],
        confidence=ranked[0][1],
        runner_up=ranked[1][0],
        runner_up_confidence=ranked[1][1],
        geometry=geo,
        facial_thirds=thirds_norm,
        canthal_tilt=geo.canthal_tilt_deg,
        jawline_angle=jaw_avg,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(
        description="PersonaStyle Face Shape Analyzer — MediaPipe + OpenCV"
    )
    parser.add_argument("--image", required=True, help="Path to input selfie image")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save annotated debug image with landmarks and measurements",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON to stdout",
    )
    args = parser.parse_args()

    try:
        result = analyze_face(args.image, debug=args.debug)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        log.error("Analysis failed: %s", exc)
        sys.exit(1)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("\n" + "=" * 50)
        print(f"  Face Shape    : {result.face_shape}")
        print(f"  Confidence    : {result.confidence*100:.1f}%")
        print(f"  Runner-up     : {result.runner_up} ({result.runner_up_confidence*100:.1f}%)")
        print("-" * 50)
        print(f"  WHR           : {result.geometry.width_to_height_ratio:.3f}")
        print(f"  Cheek/Jaw     : {result.geometry.cheek_to_jaw_ratio:.3f}")
        print(f"  Forehead/Jaw  : {result.geometry.forehead_to_jaw_ratio:.3f}")
        print(f"  Jawline Angle : {result.jawline_angle:.1f}°")
        print(f"  Canthal Tilt  : {result.canthal_tilt:.1f}°")
        print(f"  Facial Thirds : {[f'{v:.2%}' for v in result.facial_thirds]}")
        if result.debug_image_path:
            print(f"  Debug Image   : {result.debug_image_path}")
        print("=" * 50 + "\n")


if __name__ == "__main__":
    _cli()
