// ============================================================
// PersonaStyle — Shared TypeScript Interfaces
// packages/shared-types/src/index.ts
// ============================================================

// -----------------------------------------------------------
// Primitives
// -----------------------------------------------------------

export type Gender = "male" | "female" | "non-binary" | "prefer_not_to_say";

export type Season = "Spring" | "Summer" | "Autumn" | "Winter";
export type SeasonVariant =
  | "True Spring"
  | "Light Spring"
  | "Warm Spring"
  | "True Summer"
  | "Light Summer"
  | "Soft Summer"
  | "True Autumn"
  | "Soft Autumn"
  | "Deep Autumn"
  | "True Winter"
  | "Deep Winter"
  | "Bright Winter";

export type FaceShape =
  | "Oval"
  | "Round"
  | "Square"
  | "Heart"
  | "Diamond"
  | "Oblong"
  | "Triangle";

export type BodyType =
  | "Hourglass"
  | "Rectangle"
  | "InvertedTriangle"
  | "Triangle"
  | "Apple"
  | "Athletic";

// -----------------------------------------------------------
// CV Metrics
// -----------------------------------------------------------

/** Raw landmark coordinates from MediaPipe FaceMesh (468 points) */
export interface FaceLandmark {
  x: number; // normalized [0, 1]
  y: number;
  z: number; // relative depth
}

/**
 * QOVES-inspired facial geometry metrics derived from FaceMesh landmarks.
 * All angles in degrees, all ratios unitless.
 */
export interface FacialMetrics {
  /** Upper third (hairline→brow), middle third (brow→nose base), lower third (nose→chin) */
  facialThirdsRatio: [number, number, number];

  /** Angle of the outer canthus relative to the inner canthus (positive = upward tilt) */
  canthalTilt: number;

  /** Angle formed by the ramus and the mandible body at the gonion */
  jawlineAngle: number;

  /** Bizygomatic width / face height */
  widthToHeightRatio: number;

  /** Bizygomatic width / bigonial width */
  cheekToJawRatio: number;

  /** Interocular distance / bizygomatic width */
  eyeSpacingRatio: number;

  /** Nose width / interocular distance */
  noseToEyeRatio: number;

  faceShape: FaceShape;
}

/** Body proportion metrics derived from pose estimation */
export interface BodyMetrics {
  bodyType: BodyType;

  /** Shoulder width / hip width */
  shoulderToHipRatio: number;

  /** Waist width / hip width */
  waistToHipRatio: number;

  /** Shoulder width / waist width */
  shoulderToWaistRatio: number;

  /** Upper body length / lower body length */
  torsoToLegRatio: number;

  /** Estimated in cm if user-provided height is available */
  estimatedHeightCm?: number;
}

/** Color analysis derived from sampled skin, eye, and hair pixels */
export interface ColorProfile {
  season: Season;
  seasonVariant: SeasonVariant;

  /** Dominant undertone: warm, cool, or neutral */
  skinUndertone: "warm" | "cool" | "neutral";

  /** Fitzpatrick scale I–VI */
  fitzpatrickScale: 1 | 2 | 3 | 4 | 5 | 6;

  /** Dominant eye color family */
  eyeColor: "blue" | "green" | "hazel" | "brown" | "amber" | "gray";

  /** Dominant hair color family */
  hairColor:
    | "blonde"
    | "red"
    | "auburn"
    | "light_brown"
    | "dark_brown"
    | "black"
    | "gray"
    | "white";

  /** Hex sampled from skin ROI (cheek area) */
  skinHexSample: string;

  /** Contrast level between hair/skin/eyes */
  overallContrast: "low" | "medium" | "high";

  /** Recommended palette hex codes (up to 12) */
  recommendedPalette: string[];
}

// -----------------------------------------------------------
// Core Domain Model
// -----------------------------------------------------------

/**
 * Complete biometric profile for a single analysis session.
 * Populated progressively as each CV pipeline stage completes.
 */
export interface UserBiometrics {
  /** UUID for this analysis session */
  sessionId: string;

  /** Wall-clock time the session was created (ISO-8601) */
  createdAt: string;

  // --- User-supplied metadata ---
  age: number;
  gender: Gender;

  /** Height in centimetres, supplied by the user for calibration */
  heightCm: number;

  // --- Uploaded image references (object-storage keys / data-URLs) ---
  selfieImageKey: string;
  fullBodyImageKey: string;

  // --- Pipeline outputs (undefined until that stage completes) ---
  facialMetrics?: FacialMetrics;
  bodyMetrics?: BodyMetrics;
  colorProfile?: ColorProfile;

  /** Raw MediaPipe FaceMesh 468-point array (omitted in API responses by default) */
  rawLandmarks?: FaceLandmark[];

  /** Pipeline processing status */
  analysisStatus: "pending" | "processing" | "complete" | "error";
  analysisError?: string;
}

// -----------------------------------------------------------
// Recommendation Domain
// -----------------------------------------------------------

export interface HairstyleRecommendation {
  /** Human-readable name, e.g. "Textured Quiff" */
  name: string;

  /** Slug for asset lookup, e.g. "textured-quiff" */
  slug: string;

  /** Primary driving rule tag, e.g. "high-forehead" */
  primaryTag: string;

  /** Additional tags from the Styling Rules Engine */
  tags: string[];

  /** Why this style suits the user */
  rationale: string;

  /** Confidence score [0, 1] from rules engine */
  confidence: number;

  /** Optional URL to reference image */
  referenceImageUrl?: string;
}

export interface ClothingRecommendation {
  category:
    | "tops"
    | "bottoms"
    | "outerwear"
    | "footwear"
    | "accessories"
    | "full-outfit";
  name: string;
  slug: string;
  silhouette: string; // e.g. "wide-leg", "A-line", "fitted"
  primaryTag: string;
  tags: string[];
  rationale: string;
  confidence: number;
  referenceImageUrl?: string;
}

export interface ColorRecommendation {
  category: "clothing" | "makeup" | "accessories";
  recommendedColors: string[]; // hex codes
  colorsToAvoid: string[];
  rationale: string;
}

/**
 * The complete style recommendation produced by the Stylist engine
 * for one UserBiometrics session.
 */
export interface StyleRecommendation {
  /** Links back to the originating session */
  sessionId: string;

  generatedAt: string;

  /** Top-ranked hairstyle options (max 5) */
  hairstyles: HairstyleRecommendation[];

  /** Clothing recommendations grouped by category */
  clothing: ClothingRecommendation[];

  /** Palette-based color recommendations */
  colorGuidance: ColorRecommendation[];

  /**
   * LLM-generated narrative (~300 words) that weaves together
   * all metric findings into a cohesive style identity story.
   */
  styleNarrative: string;

  /**
   * Distilled "style archetype" label, e.g. "Modern Classic",
   * "Bohemian Romantic", "Urban Minimalist"
   */
  styleArchetype: string;

  /** Which model generated the narrative */
  llmModel: string;

  /** Input token cost for the LLM call */
  llmTokensUsed?: number;
}

// -----------------------------------------------------------
// API Shapes
// -----------------------------------------------------------

/** POST /analyze — request body (multipart decoded to this shape) */
export interface AnalyzeRequest {
  age: number;
  gender: Gender;
  heightCm: number;
  selfieBase64: string;
  fullBodyBase64: string;
}

/** POST /analyze — initial response (analysis runs async) */
export interface AnalyzeResponse {
  sessionId: string;
  status: "processing";
  pollUrl: string;
}

/** GET /session/:id — response when analysis complete */
export interface SessionResponse {
  biometrics: UserBiometrics;
  recommendation?: StyleRecommendation;
}

/** POST /tryon — virtual try-on request */
export interface TryOnRequest {
  sessionId: string;
  hairstyleSlug: string;
  /** Optional clothing item overlay */
  clothingSlug?: string;
}

/** POST /tryon — response */
export interface TryOnResponse {
  resultImageUrl: string;
  /** Processing time in ms */
  processingMs: number;
}
