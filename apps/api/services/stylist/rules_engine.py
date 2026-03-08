"""
Styling Rules Engine
====================
Loads Styling_Rules.json and maps biometric data to hairstyle/clothing tags.
Returns ranked HairstyleRecommendation and ClothingRecommendation objects.
"""
from __future__ import annotations
import json, os, random
from typing import Any

_RULES_PATH = os.path.join(os.path.dirname(__file__), "Styling_Rules.json")

def _load_rules() -> dict:
    with open(_RULES_PATH, "r") as f:
        return json.load(f)

_RULES = _load_rules()

# ---- Tag → human label maps ----
_HAIRSTYLE_LABELS = {
    "curtain-bangs":      "Curtain Bangs",
    "textured-quiff":     "Textured Quiff",
    "layered":            "Layered Cut",
    "long-layers":        "Long Layers",
    "side-swept":         "Side-Swept",
    "side-part":          "Classic Side Part",
    "full-fringe":        "Full Fringe",
    "wispy-fringe":       "Wispy Fringe",
    "blunt-cut":          "Blunt Cut",
    "medium-length":      "Medium Length",
    "wide-curls":         "Wide Curls",
    "chin-length-bob":    "Chin-Length Bob",
    "undercut":           "Undercut",
    "pompadour":          "Pompadour",
    "deep-side-part":     "Deep Side Part",
    "textured-waves":     "Textured Waves",
    "high-top-fade":      "High-Top Fade",
    "volume-at-crown":    "Crown Volume",
    "soft-waves":         "Soft Waves",
    "lob":                "Lob (Long Bob)",
    "tousled":            "Tousled / Effortless",
}

_CLOTHING_LABELS = {
    "wide-leg-trouser":   ("Wide-Leg Trousers", "bottoms",   "wide-leg"),
    "A-line-skirt":       ("A-Line Skirt",       "bottoms",   "A-line"),
    "pencil-skirt":       ("Pencil Skirt",        "bottoms",   "fitted"),
    "wrap-top":           ("Wrap Top",            "tops",      "wrap"),
    "fitted-blouse":      ("Fitted Blouse",       "tops",      "fitted"),
    "peplum":             ("Peplum Top",          "tops",      "peplum"),
    "bodysuit":           ("Bodysuit",            "tops",      "fitted"),
    "ruffled":            ("Ruffled Top",         "tops",      "ruffled"),
    "V-neck":             ("V-Neck Top",          "tops",      "V-neck"),
    "off-shoulder":       ("Off-Shoulder Top",   "tops",      "off-shoulder"),
    "empire-waist":       ("Empire Waist Dress", "full-outfit","empire"),
    "belted-coat":        ("Belted Coat",         "outerwear", "belted"),
    "bomber-jacket":      ("Bomber Jacket",       "outerwear", "relaxed"),
    "longline-jacket":    ("Longline Jacket",     "outerwear", "longline"),
    "high-waist-jeans":   ("High-Rise Jeans",     "bottoms",   "high-waist"),
    "straight-leg":       ("Straight-Leg Trousers","bottoms",  "straight"),
    "flared-jeans":       ("Flared Jeans",        "bottoms",   "flared"),
    "full-skirt":         ("Full / Midi Skirt",   "bottoms",   "full"),
    "paperbag-waist":     ("Paperbag-Waist Trousers","bottoms","paperbag"),
    "dark-solid-top":     ("Dark Solid-Colour Top","tops",     "minimal"),
    "boat-neck":          ("Boat-Neck Top",       "tops",      "boat-neck"),
    "wrap-blazer":        ("Wrap Blazer",         "outerwear", "wrap"),
    "slim-fit-shirt":     ("Slim-Fit Shirt",      "tops",      "slim"),
    "structured-blazer":  ("Structured Blazer",   "outerwear", "structured"),
}

_RATIONALE_HAIR = {
    "Oval":    "Your balanced proportions suit almost any style — this keeps your natural symmetry front and centre.",
    "Round":   "This style adds height and elongates your face, balancing the softness of your cheekbone width.",
    "Square":  "Soft, layered movement around the jawline beautifully offsets your strong, defined jaw.",
    "Heart":   "Width below the temples balances your broader forehead and draws attention to your defined jaw.",
    "Oblong":  "Horizontal volume reduces the length of your face and creates a more proportionate silhouette.",
    "Diamond": "This frames your standout cheekbones while adding width at forehead and chin.",
    "Triangle":"Top volume balances a wider jaw and draws the eye upward.",
}

_RATIONALE_CLOTHING = {
    "Hourglass":         "Accentuates your natural waist-to-hip symmetry without adding bulk.",
    "Rectangle":         "Creates the illusion of a defined waist and adds feminine or masculine shape.",
    "InvertedTriangle":  "Balances broad shoulders by adding visual interest below the waist.",
    "Triangle":          "Draws the eye upward to balance narrower shoulders against wider hips.",
    "Apple":             "Creates a long, vertical line through the centre, elongating the torso.",
    "Athletic":          "Showcases a strong physique with clean, well-fitted tailoring.",
}


def _hair_recommendations(face_shape: str, facial_thirds: list, jawline_angle: float) -> list:
    rules = _RULES.get("face_shape_rules", {}).get(face_shape, {})
    rec_tags: list = rules.get("hairstyle_tags", {}).get("recommend", [])

    # Apply forehead override
    upper = facial_thirds[0] if facial_thirds else 0.33
    if upper > 0.38:
        fringe_boost = ["full-fringe", "curtain-bangs", "wispy-fringe"]
        rec_tags = fringe_boost + [t for t in rec_tags if t not in fringe_boost]
    elif upper < 0.28:
        rec_tags = [t for t in rec_tags if "fringe" not in t and "bang" not in t]

    # Apply jawline override
    jaw_rules = _RULES.get("jawline_rules", {})
    if jawline_angle < 120:
        extra = jaw_rules.get("sharp_jaw", {}).get("hairstyle_tags", {}).get("recommend", [])
    elif jawline_angle > 140:
        extra = jaw_rules.get("soft_jaw", {}).get("hairstyle_tags", {}).get("recommend", [])
    else:
        extra = []
    for t in extra:
        if t not in rec_tags:
            rec_tags.append(t)

    rationale_base = _RATIONALE_HAIR.get(face_shape, "A thoughtful pick for your unique features.")
    results = []
    for i, tag in enumerate(rec_tags[:5]):
        label = _HAIRSTYLE_LABELS.get(tag, tag.replace("-", " ").title())
        results.append({
            "name": label,
            "slug": tag,
            "primary_tag": tag,
            "tags": [tag, face_shape.lower()],
            "rationale": rationale_base,
            "confidence": round(max(0.55, 0.92 - i * 0.07), 3),
        })
    return results


def _clothing_recommendations(body_type: str, torso_leg_ratio: float) -> list:
    rules = _RULES.get("body_type_rules", {}).get(body_type, {})
    clothing_tags_map: dict = rules.get("clothing_tags", {})

    # Collect tags across all categories
    all_tags: list[tuple[str, str]] = []
    for cat, cat_rules in clothing_tags_map.items():
        if cat in ("tops", "bottoms", "outerwear", "full-outfit"):
            rec = cat_rules if isinstance(cat_rules, list) else cat_rules.get("recommend", [])
            for t in rec[:2]:
                all_tags.append((t, cat))

    # Vertical proportion override
    prop_rules = _RULES.get("vertical_proportion_rules", {})
    if torso_leg_ratio > 0.60:
        for t in prop_rules.get("long_torso_short_legs", {}).get("clothing_tags", {}).get("tops", [])[:1]:
            all_tags.insert(0, (t, "tops"))
    elif torso_leg_ratio < 0.45:
        for t in prop_rules.get("short_torso_long_legs", {}).get("clothing_tags", {}).get("bottoms", [])[:1]:
            all_tags.insert(0, (t, "bottoms"))

    rationale_base = _RATIONALE_CLOTHING.get(body_type, "Chosen to complement your natural proportions.")
    results = []
    seen = set()
    for i, (tag, cat) in enumerate(all_tags[:6]):
        if tag in seen:
            continue
        seen.add(tag)
        label_data = _CLOTHING_LABELS.get(tag)
        if label_data:
            name, category, silhouette = label_data
        else:
            name, category, silhouette = tag.replace("-", " ").title(), cat, tag
        results.append({
            "category": category,
            "name": name,
            "slug": tag,
            "silhouette": silhouette,
            "primary_tag": tag,
            "tags": [tag, body_type.lower()],
            "rationale": rationale_base,
            "confidence": round(max(0.55, 0.90 - i * 0.06), 3),
        })
    return results


def _color_recommendations(season_variant: str, recommended_palette: list) -> list:
    rules = _RULES.get("color_palette_rules", {}).get(season_variant, {})
    best  = rules.get("best_colours", recommended_palette[:6])
    avoid = rules.get("avoid_colours", [])
    makeup = rules.get("makeup_guidance", {})
    hair_c = rules.get("hair_colour_guidance", {})

    recs = [
        {
            "category": "clothing",
            "recommended_colors": best[:6],
            "colors_to_avoid": avoid[:3],
            "rationale": f"As a {season_variant} season, these tones harmonise with your skin's natural undertone.",
        },
    ]
    if makeup:
        lip = makeup.get("lip", [])
        recs.append({
            "category": "makeup",
            "recommended_colors": lip[:4],
            "colors_to_avoid": [],
            "rationale": f"Lip shades in {', '.join(lip[:3])} complement your seasonal palette.",
        })
    if hair_c:
        recs.append({
            "category": "accessories",
            "recommended_colors": hair_c.get("recommend", [])[:4],
            "colors_to_avoid": hair_c.get("avoid", [])[:2],
            "rationale": "Hair colour recommendations to harmonise with your seasonal type.",
        })
    return recs


def apply_rules(
    facial_metrics: dict,
    body_metrics: dict,
    color_profile: dict,
) -> dict:
    """Return hairstyles, clothing, and color_guidance lists."""
    face_shape    = facial_metrics.get("face_shape", "Oval")
    facial_thirds = facial_metrics.get("facial_thirds_ratio", [0.33, 0.33, 0.34])
    jaw_angle     = facial_metrics.get("jawline_angle", 130.0)
    body_type     = body_metrics.get("body_type", "Rectangle")
    torso_leg     = body_metrics.get("torso_to_leg_ratio", 0.52)
    season_var    = color_profile.get("season_variant", "True Spring")
    palette       = color_profile.get("recommended_palette", [])

    return {
        "hairstyles":     _hair_recommendations(face_shape, facial_thirds, jaw_angle),
        "clothing":       _clothing_recommendations(body_type, torso_leg),
        "color_guidance": _color_recommendations(season_var, palette),
    }
