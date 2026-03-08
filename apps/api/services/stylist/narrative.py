"""
LLM Narrative Generator
=======================
Calls Claude to produce a personalised Style Narrative.
Falls back to a rich template-generated narrative if ANTHROPIC_API_KEY is unset.
"""
from __future__ import annotations
import os, json, textwrap, re

_RULES_PATH = os.path.join(os.path.dirname(__file__), "Styling_Rules.json")

# FIX #11 — allowlists for enum-typed fields used in LLM prompts
_VALID_FACE_SHAPES  = {"Oval","Round","Square","Heart","Diamond","Oblong","Triangle"}
_VALID_BODY_TYPES   = {"Hourglass","Rectangle","InvertedTriangle","Triangle","Apple","Athletic"}
_VALID_UNDERTONES   = {"warm","cool","neutral"}
_VALID_CONTRASTS    = {"low","medium","high"}
_VALID_GENDERS      = {"male","female","non-binary","prefer_not_to_say"}

def _safe_str(value: str, allowed: set, fallback: str) -> str:
    """Return value only if it's in the allowlist, else fallback. Prevents prompt injection."""
    return value if value in allowed else fallback

def _sanitize_tag_list(tags: str, max_len: int = 120) -> str:
    """Strip control characters and limit length for tags inserted into prompts."""
    cleaned = re.sub(r"[^\w\s,\-()]", "", tags)
    return cleaned[:max_len]

def _load_prompt_template() -> dict:
    with open(_RULES_PATH) as f:
        rules = json.load(f)
    return rules.get("llm_prompt_template", {})

_TMPL = _load_prompt_template()

_ARCHETYPES = {
    ("Oval",    "Hourglass"):         "Timeless Romantic",
    ("Oval",    "Rectangle"):         "Modern Classic",
    ("Oval",    "Athletic"):          "Polished Athlete",
    ("Round",   "Apple"):             "Bohemian Free Spirit",
    ("Round",   "Rectangle"):         "Casual Contemporary",
    ("Square",  "InvertedTriangle"):  "Power Minimalist",
    ("Square",  "Athletic"):          "Urban Architect",
    ("Heart",   "Triangle"):          "Vintage Feminine",
    ("Heart",   "Hourglass"):         "Hollywood Glamour",
    ("Diamond", "Hourglass"):         "Sculptural Elegance",
    ("Oblong",  "Rectangle"):         "Editorial Modernist",
    ("Triangle","Triangle"):          "Laid-back Chic",
}


def _fallback_narrative(context: dict) -> str:
    face  = context["face_shape"]
    body  = context["body_type"]
    season= context["season_variant"]
    hair  = context.get("hairstyle_tags", "layered cut")
    cloth = context.get("clothing_tags", "tailored silhouettes")
    colour= context.get("recommended_colours", "earthy tones")
    age   = context.get("age", "")
    thirds= context.get("facial_thirds", [0.33, 0.33, 0.34])
    upper = thirds[0] if thirds else 0.33

    forehead_note = (
        "Your elevated forehead is a mark of classical beauty — a gentle fringe or curtain bangs will frame your face exquisitely."
        if upper > 0.38 else
        "Your compact forehead creates a naturally youthful proportion — wear your hair swept back to show it off."
        if upper < 0.28 else
        "Your forehead sits in ideal proportion with your other features."
    )

    return textwrap.dedent(f"""
        **Your Style Identity: {_ARCHETYPES.get((face, body), 'Modern Individual')}**

        You carry a naturally {face.lower()} face shape — one of the most {
        'versatile' if face == 'Oval' else 'distinctive and characterful'
        } silhouettes in classical aesthetics. {forehead_note}

        **Hairstyle Direction**
        For your {face} face, the ideal approach centres on {hair}. These choices work
        with your facial geometry rather than against it, enhancing your strongest features
        and creating balance where it counts most.

        **Clothing & Silhouette**
        Your {body} body type means your styling sweet spot lies in {cloth}.
        The goal is always to highlight your natural proportions — not to hide them.
        Pieces that {
        'define the waist' if body == 'Hourglass' else
        'add curves and interest' if body == 'Rectangle' else
        'draw the eye downward' if body == 'InvertedTriangle' else
        'build visual width at the shoulder' if body == 'Triangle' else
        'create a long vertical line' if body == 'Apple' else
        'fit cleanly and showcase your physique'
        } will always be your most powerful tool.

        **Colour & Palette**
        As a {season} type, your natural colouring comes alive in {colour}. These shades
        share your skin's undertone and contrast level, making you appear rested, radiant,
        and unmistakably yourself. When in doubt, reach for these first.

        **Final Word**
        Style is not about following rules — it's about understanding your canvas. You now
        have the map. Wear what makes you feel extraordinary, and let these principles be
        your compass, not your cage.
    """).strip()


def generate_narrative(
    facial_metrics: dict,
    body_metrics: dict,
    color_profile: dict,
    hairstyle_tags: list,
    clothing_tags: list,
    age: int,
    gender: str,
) -> "tuple[str, str, str, int | None]":
    """Returns (narrative, style_archetype, model_used, tokens_used)."""

    # FIX #11 — validate all enum-typed fields against allowlists before prompt insertion
    face_shape = _safe_str(facial_metrics.get("face_shape", "Oval"), _VALID_FACE_SHAPES, "Oval")
    body_type  = _safe_str(body_metrics.get("body_type", "Rectangle"), _VALID_BODY_TYPES, "Rectangle")
    undertone  = _safe_str(color_profile.get("skin_undertone", "neutral"), _VALID_UNDERTONES, "neutral")
    contrast   = _safe_str(color_profile.get("overall_contrast", "medium"), _VALID_CONTRASTS, "medium")
    safe_gender = _safe_str(gender, _VALID_GENDERS, "prefer_not_to_say")
    safe_age   = max(13, min(120, int(age)))   # clamp to valid range

    season_var  = color_profile.get("season_variant", "True Spring")
    thirds      = facial_metrics.get("facial_thirds_ratio", [0.33, 0.33, 0.34])
    canthal     = float(facial_metrics.get("canthal_tilt", 2.0))
    jaw         = float(facial_metrics.get("jawline_angle", 130.0))
    palette     = color_profile.get("recommended_palette", [])
    archetype   = _ARCHETYPES.get((face_shape, body_type), "Modern Individual")

    # FIX #11 — sanitize tag strings: strip control chars, limit length
    h_tags  = _sanitize_tag_list(", ".join(r.get("name", "") for r in hairstyle_tags[:3]))
    c_tags  = _sanitize_tag_list(", ".join(r.get("name", "") for r in clothing_tags[:3]))
    colours = _sanitize_tag_list(", ".join(str(c) for c in palette[:4]))

    context = dict(
        face_shape=face_shape, body_type=body_type, season_variant=season_var,
        facial_thirds=thirds, canthal_tilt=canthal, jawline_angle=jaw,
        skin_undertone=undertone, overall_contrast=contrast,
        age=safe_age, gender=safe_gender,
        hairstyle_tags=h_tags, clothing_tags=c_tags, recommended_colours=colours,
        upper_third=f"{thirds[0]*100:.0f}", middle_third=f"{thirds[1]*100:.0f}",
        lower_third=f"{thirds[2]*100:.0f}",
        confidence=facial_metrics.get("face_shape_confidence", 0.8),
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _fallback_narrative(context), archetype, "template", None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        sys_prompt  = _TMPL.get("system_prompt", "You are a professional stylist.")
        user_tmpl   = _TMPL.get("user_prompt_template", "Describe the style for: {face_shape}")
        user_prompt = user_tmpl.format(**{
            "face_shape":     face_shape,
            "confidence":     f"{context['confidence']*100:.0f}",
            "body_type":      body_type,
            "season_variant": season_var,
            "upper_third":    context["upper_third"],
            "middle_third":   context["middle_third"],
            "lower_third":    context["lower_third"],
            "canthal_tilt":   canthal,
            "jawline_angle":  jaw,
            "skin_undertone": undertone,
            "overall_contrast": contrast,
            "age":            safe_age,
            "gender":         safe_gender,
            "hairstyle_tags": h_tags,
            "clothing_tags":  c_tags,
            "recommended_colours": colours,
        })

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=sys_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        narrative = msg.content[0].text
        tokens    = msg.usage.input_tokens + msg.usage.output_tokens
        return narrative, archetype, "claude-sonnet-4-6", tokens

    except Exception:
        return _fallback_narrative(context), archetype, "template-fallback", None
