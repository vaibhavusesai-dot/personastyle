"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

type Step = "landing" | "metadata" | "selfie" | "body" | "analyzing" | "results";
type Gender = "male" | "female" | "non-binary" | "prefer_not_to_say";

interface Metadata { age: number; gender: Gender; heightCm: number; }

interface HairstyleRec {
  name: string; slug: string; primary_tag: string; tags: string[];
  rationale: string; confidence: number;
}
interface ClothingRec {
  category: string; name: string; slug: string; silhouette: string;
  primary_tag: string; tags: string[]; rationale: string; confidence: number;
}
interface ColorRec {
  category: string; recommended_colors: string[];
  colors_to_avoid: string[]; rationale: string;
}
interface FacialMetrics {
  face_shape: string; face_shape_confidence: number;
  facial_thirds_ratio: number[]; canthal_tilt: number;
  jawline_angle: number; width_to_height_ratio: number;
  cheek_to_jaw_ratio: number; forehead_to_jaw_ratio: number;
}
interface BodyMetrics {
  body_type: string; shoulder_to_hip_ratio: number;
  waist_to_hip_ratio: number; torso_to_leg_ratio: number;
}
interface ColorProfile {
  season: string; season_variant: string; skin_undertone: string;
  fitzpatrick_scale: number; eye_color: string; hair_color: string;
  skin_hex_sample: string; overall_contrast: string; recommended_palette: string[];
}
interface Recommendation {
  hairstyles: HairstyleRec[]; clothing: ClothingRec[];
  color_guidance: ColorRec[]; style_narrative: string;
  style_archetype: string; llm_model: string;
}
interface SessionData {
  session_id: string; status: string;
  facial_metrics?: FacialMetrics; body_metrics?: BodyMetrics;
  color_profile?: ColorProfile; recommendation?: Recommendation;
  error?: string;
}

// FIX #14 — never hardcode API URL; always read from env var
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toBase64(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload  = () => res((r.result as string).split(",")[1]);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}

function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-zinc-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-white/5 text-sm">
      <span className="text-zinc-400">{label}</span>
      <span className="font-medium text-white">{value}</span>
    </div>
  );
}

function Tag({ label }: { label: string }) {
  return (
    <span className="px-2 py-0.5 rounded-full bg-violet-900/40 text-violet-300 text-xs border border-violet-700/30">
      {label}
    </span>
  );
}

// ─── Sub-pages ────────────────────────────────────────────────────────────────

function Landing({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center gap-8">
      {/* Glow orb */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-violet-600/10 blur-3xl pointer-events-none" />

      <div className="relative space-y-4 max-w-lg">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-900/40 border border-violet-700/30 text-violet-300 text-sm font-medium">
          <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
          AI-Powered · Style Intelligence
        </div>
        <h1 className="text-5xl font-extrabold leading-tight tracking-tight">
          Discover your{" "}
          <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            Style DNA
          </span>
        </h1>
        <p className="text-zinc-400 text-lg leading-relaxed">
          Two photos. Three minutes. A hyper-personalised hairstyle, wardrobe, and colour palette — built on your actual facial geometry and body type.
        </p>
      </div>

      <div className="relative grid grid-cols-3 gap-4 max-w-md w-full text-sm">
        {[
          { icon: "◉", title: "Face Analysis", sub: "468-point FaceMesh" },
          { icon: "⬡", title: "Body Typing", sub: "Pose-ratio engine" },
          { icon: "◈", title: "Colour Season", sub: "Skin-pixel sampling" },
        ].map((f) => (
          <div key={f.title} className="card-gradient p-4 text-center space-y-1.5 rounded-xl">
            <div className="text-2xl text-violet-400">{f.icon}</div>
            <div className="font-semibold text-white text-xs">{f.title}</div>
            <div className="text-zinc-500 text-xs">{f.sub}</div>
          </div>
        ))}
      </div>

      <button
        onClick={onStart}
        className="relative inline-flex items-center gap-3 px-8 py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-lg shadow-lg glow hover:scale-105 active:scale-95 transition-transform"
      >
        Begin Analysis
        <span className="text-2xl">→</span>
      </button>

      <p className="text-zinc-600 text-xs">Photos are processed locally and never stored permanently.</p>
    </div>
  );
}

function MetadataForm({ onNext }: { onNext: (m: Metadata) => void }) {
  const [age, setAge]       = useState(25);
  const [gender, setGender] = useState<Gender>("prefer_not_to_say");
  const [height, setHeight] = useState(170);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 gap-8">
      <div className="w-full max-w-md space-y-6">
        <div>
          <div className="text-xs text-violet-400 font-semibold tracking-widest uppercase mb-2">Step 1 of 3</div>
          <h2 className="text-3xl font-bold">Tell us about yourself</h2>
          <p className="text-zinc-400 mt-1">Used to calibrate proportion measurements.</p>
        </div>

        <div className="card-gradient p-6 space-y-5 rounded-2xl">
          {/* Age */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Age: <span className="text-violet-400">{age}</span></label>
            <input type="range" min={13} max={90} value={age} onChange={e => setAge(+e.target.value)}
              className="w-full accent-violet-500" />
          </div>

          {/* Gender */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Gender</label>
            <div className="grid grid-cols-2 gap-2">
              {(["male","female","non-binary","prefer_not_to_say"] as Gender[]).map(g => (
                <button key={g} onClick={() => setGender(g)}
                  className={`py-2 px-3 rounded-xl text-sm font-medium border transition-all ${
                    gender === g
                      ? "bg-violet-600 border-violet-500 text-white"
                      : "bg-white/5 border-white/10 text-zinc-400 hover:bg-white/10"
                  }`}>
                  {g === "prefer_not_to_say" ? "Prefer not to say" : g.charAt(0).toUpperCase() + g.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Height */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Height: <span className="text-violet-400">{height} cm</span></label>
            <input type="range" min={140} max={220} value={height} onChange={e => setHeight(+e.target.value)}
              className="w-full accent-violet-500" />
          </div>
        </div>

        <button onClick={() => onNext({ age, gender, heightCm: height })}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-lg hover:opacity-90 active:scale-95 transition-all">
          Continue →
        </button>
      </div>
    </div>
  );
}

function PhotoUpload({
  title, description, hint, onPhoto, stepLabel,
}: {
  title: string; description: string; hint: string;
  onPhoto: (b64: string, preview: string) => void; stepLabel: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    const b64  = await toBase64(file);
    const prev = URL.createObjectURL(file);
    setPreview(prev);
    onPhoto(b64, prev);
  }, [onPhoto]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) handleFile(file);
  }, [handleFile]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 gap-6">
      <div className="w-full max-w-md space-y-6">
        <div>
          <div className="text-xs text-violet-400 font-semibold tracking-widest uppercase mb-2">{stepLabel}</div>
          <h2 className="text-3xl font-bold">{title}</h2>
          <p className="text-zinc-400 mt-1">{description}</p>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed cursor-pointer transition-all overflow-hidden
            ${dragging ? "border-violet-400 bg-violet-900/20" : "border-white/10 bg-white/3 hover:border-violet-600/50 hover:bg-white/5"}
            ${preview ? "h-80" : "h-60"}`}
        >
          <input ref={inputRef} type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          {preview ? (
            <img src={preview} alt="preview" className="w-full h-full object-cover" />
          ) : (
            <div className="text-center space-y-3 px-6">
              <div className="text-5xl opacity-40">📷</div>
              <p className="text-zinc-400 text-sm">Drag & drop or <span className="text-violet-400 font-semibold">click to upload</span></p>
              <p className="text-zinc-600 text-xs">{hint}</p>
            </div>
          )}
        </div>

        {preview && (
          <button onClick={() => { setPreview(null); inputRef.current && (inputRef.current.value = ""); }}
            className="w-full py-2 rounded-xl bg-white/5 border border-white/10 text-zinc-400 text-sm hover:bg-white/10 transition-colors">
            Change Photo
          </button>
        )}
      </div>
    </div>
  );
}

function AnalyzingScreen({ progress }: { progress: string }) {
  const steps = [
    "Extracting 468 facial landmarks…",
    "Computing QOVES geometry metrics…",
    "Sampling skin & eye pixels…",
    "Determining seasonal colour palette…",
    "Running body proportion analysis…",
    "Applying style rules engine…",
    "Generating personalised narrative…",
    "Finalising your Style DNA…",
  ];
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep(s => Math.min(s + 1, steps.length - 1)), 1400);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 gap-10">
      {/* Animated rings */}
      <div className="relative w-40 h-40 flex items-center justify-center">
        <div className="absolute inset-0 rounded-full border-2 border-violet-600/30 animate-ping" />
        <div className="absolute inset-2 rounded-full border-2 border-fuchsia-600/20 animate-spin-slow" />
        <div className="absolute inset-4 rounded-full border-2 border-violet-500/40 animate-pulse-slow" />
        <div className="text-4xl">✦</div>
      </div>

      <div className="text-center space-y-3">
        <h2 className="text-2xl font-bold">Analysing your Style DNA</h2>
        <p className="text-violet-300 text-sm animate-pulse">{steps[step]}</p>
      </div>

      <div className="w-full max-w-xs space-y-2">
        {steps.slice(0, step + 1).map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="text-green-500">✓</span> {s}
          </div>
        ))}
      </div>
    </div>
  );
}

function Results({ data }: { data: SessionData }) {
  const fm  = data.facial_metrics!;
  const bm  = data.body_metrics!;
  const cp  = data.color_profile!;
  const rec = data.recommendation!;

  const faceEmoji: Record<string, string> = {
    Oval: "◎", Round: "○", Square: "▢", Heart: "♡", Diamond: "◇", Oblong: "▭", Triangle: "△",
  };
  const bodyEmoji: Record<string, string> = {
    Hourglass: "⧖", Rectangle: "▬", InvertedTriangle: "▽", Triangle: "△", Apple: "●", Athletic: "⬡",
  };

  return (
    <div className="min-h-screen px-4 py-12 max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="text-violet-400 text-sm font-semibold tracking-widest uppercase">Your Style DNA</div>
        <h1 className="text-4xl font-extrabold bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
          {rec.style_archetype}
        </h1>
        <p className="text-zinc-400">Analysis complete · {rec.llm_model}</p>
      </div>

      {/* Archetype badge strip */}
      <div className="grid grid-cols-3 gap-3 text-center">
        {[
          { label: "Face Shape", value: fm.face_shape, emoji: faceEmoji[fm.face_shape] ?? "◉" },
          { label: "Body Type",  value: bm.body_type,  emoji: bodyEmoji[bm.body_type]  ?? "⬡" },
          { label: "Colour Season", value: cp.season_variant.split(" ")[0], emoji: "◈" },
        ].map(c => (
          <div key={c.label} className="card-gradient p-4 rounded-2xl space-y-1">
            <div className="text-3xl text-violet-300">{c.emoji}</div>
            <div className="text-white font-bold text-sm">{c.value}</div>
            <div className="text-zinc-500 text-xs">{c.label}</div>
          </div>
        ))}
      </div>

      {/* Facial metrics */}
      <div className="card-gradient p-6 rounded-2xl space-y-3">
        <h2 className="font-bold text-lg">Facial Geometry</h2>
        <Confidence value={fm.face_shape_confidence} />
        <MetricRow label="Width / Height Ratio" value={fm.width_to_height_ratio.toFixed(3)} />
        <MetricRow label="Cheek / Jaw Ratio"    value={fm.cheek_to_jaw_ratio.toFixed(3)} />
        <MetricRow label="Forehead / Jaw Ratio" value={fm.forehead_to_jaw_ratio.toFixed(3)} />
        <MetricRow label="Jawline Angle"         value={`${fm.jawline_angle.toFixed(1)}°`} />
        <MetricRow label="Canthal Tilt"          value={`${fm.canthal_tilt.toFixed(1)}°`} />
        <div className="pt-2">
          <div className="text-xs text-zinc-500 mb-1.5">Facial Thirds</div>
          <div className="flex gap-1 h-5">
            {fm.facial_thirds_ratio.map((v, i) => (
              <div key={i} className="rounded-sm bg-gradient-to-b from-violet-600 to-fuchsia-700"
                style={{ width: `${(v * 100).toFixed(0)}%` }}
                title={["Upper", "Middle", "Lower"][i] + `: ${(v*100).toFixed(0)}%`} />
            ))}
          </div>
          <div className="flex text-xs text-zinc-500 mt-1 gap-1">
            {fm.facial_thirds_ratio.map((v, i) => (
              <span key={i} style={{ width: `${(v * 100).toFixed(0)}%` }}>
                {(v * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Colour palette */}
      <div className="card-gradient p-6 rounded-2xl space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-bold text-lg">Seasonal Palette</h2>
            <p className="text-zinc-400 text-sm">{cp.season_variant} · {cp.skin_undertone} undertone · {cp.overall_contrast} contrast</p>
          </div>
          <div className="w-8 h-8 rounded-full border-2 border-white/20 flex-shrink-0"
            style={{ background: cp.skin_hex_sample }} title={`Skin: ${cp.skin_hex_sample}`} />
        </div>
        <div className="flex flex-wrap gap-2">
          {cp.recommended_palette.map(hex => (
            <div key={hex} className="swatch" style={{ background: hex }} title={hex} />
          ))}
        </div>
        <div className="flex gap-3 text-sm text-zinc-400">
          <span>👁 {cp.eye_color}</span>
          <span>·</span>
          <span>💇 {cp.hair_color.replace("_", " ")}</span>
          <span>·</span>
          <span>Fitzpatrick {cp.fitzpatrick_scale}</span>
        </div>
      </div>

      {/* Hairstyle recommendations */}
      <div className="card-gradient p-6 rounded-2xl space-y-4">
        <h2 className="font-bold text-lg">Hairstyle Recommendations</h2>
        <div className="space-y-3">
          {rec.hairstyles.map((h, i) => (
            <div key={h.slug} className={`p-4 rounded-xl border transition-all ${
              i === 0 ? "border-violet-500/50 bg-violet-900/20" : "border-white/5 bg-white/3"
            }`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    {i === 0 && <span className="text-xs bg-violet-600 text-white px-2 py-0.5 rounded-full font-semibold">Top Pick</span>}
                    <span className="font-semibold text-white">{h.name}</span>
                  </div>
                  <Confidence value={h.confidence} />
                </div>
              </div>
              <p className="text-zinc-400 text-sm mt-2">{h.rationale}</p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {h.tags.map(t => <Tag key={t} label={t} />)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Clothing recommendations */}
      <div className="card-gradient p-6 rounded-2xl space-y-4">
        <h2 className="font-bold text-lg">Clothing Recommendations</h2>
        <div className="space-y-3">
          {rec.clothing.map((c, i) => (
            <div key={c.slug + i} className="p-4 rounded-xl border border-white/5 bg-white/3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{c.name}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-zinc-400 capitalize">{c.category}</span>
              </div>
              <Confidence value={c.confidence} />
              <p className="text-zinc-400 text-sm">{c.rationale}</p>
              <div className="flex flex-wrap gap-1.5">
                <Tag label={c.silhouette} />
                {c.tags.slice(0, 2).map(t => <Tag key={t} label={t} />)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Color guidance */}
      {rec.color_guidance.length > 0 && (
        <div className="card-gradient p-6 rounded-2xl space-y-4">
          <h2 className="font-bold text-lg">Colour Guidance</h2>
          {rec.color_guidance.map((cg, i) => (
            <div key={i} className="space-y-2">
              <div className="text-sm font-medium text-zinc-300 capitalize">{cg.category}</div>
              <div className="flex flex-wrap gap-2">
                {cg.recommended_colors.map((c, j) => (
                  typeof c === "string" && c.startsWith("#")
                    ? <div key={j} className="swatch" style={{ background: c }} title={c} />
                    : <Tag key={j} label={c} />
                ))}
              </div>
              {cg.colors_to_avoid.length > 0 && (
                <p className="text-xs text-zinc-500">
                  Avoid: {cg.colors_to_avoid.map(c =>
                    typeof c === "string" && c.startsWith("#")
                      ? <span key={c} className="inline-block w-3 h-3 rounded-full mx-0.5 align-middle border border-white/20" style={{ background: c }} />
                      : c + " "
                  )}
                </p>
              )}
              <p className="text-zinc-400 text-sm">{cg.rationale}</p>
            </div>
          ))}
        </div>
      )}

      {/* Style narrative */}
      <div className="card-gradient p-6 rounded-2xl space-y-3">
        <h2 className="font-bold text-lg">Your Style Narrative</h2>
        <div className="narrative text-zinc-300 text-sm leading-relaxed whitespace-pre-line">
          {rec.style_narrative}
        </div>
      </div>

      {/* Restart */}
      <div className="text-center pb-8">
        <button onClick={() => window.location.reload()}
          className="px-8 py-3 rounded-2xl bg-white/5 border border-white/10 text-zinc-300 hover:bg-white/10 transition-colors">
          Start New Analysis
        </button>
      </div>
    </div>
  );
}

// ─── App Shell ────────────────────────────────────────────────────────────────

export default function App() {
  const [step, setStep]               = useState<Step>("landing");
  const [meta, setMeta]               = useState<Metadata | null>(null);
  const [selfieB64, setSelfieB64]     = useState("");
  const [bodyB64, setBodyB64]         = useState("");
  const [selfiePreview, setSelfiePreview] = useState("");
  const [bodyPreview, setBodyPreview]     = useState("");
  const [session, setSession]         = useState<SessionData | null>(null);
  const [error, setError]             = useState<string | null>(null);
  // FIX #4 — store session token in memory (not localStorage) to send with polls
  const sessionTokenRef = useRef<string>("");
  const pollRef         = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => { if (pollRef.current) clearInterval(pollRef.current); };

  const startAnalysis = useCallback(async () => {
    if (!meta || !selfieB64 || !bodyB64) return;
    setStep("analyzing");
    setError(null);

    try {
      const res = await fetch(`${API}/api/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: meta.age,
          gender: meta.gender,
          height_cm: meta.heightCm,
          selfie_base64: selfieB64,
          full_body_base64: bodyB64,
        }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const { session_id, session_token } = await res.json();

      // FIX #4 — store token in ref (not state/localStorage) to avoid exposure
      sessionTokenRef.current = session_token;

      // Poll until complete, sending token every request
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/api/v1/session/${session_id}`, {
            headers: { "X-Session-Token": sessionTokenRef.current },
          });
          const d: SessionData = await r.json();
          if (d.status === "complete") {
            stopPolling();
            setSession(d);
            setStep("results");
          } else if (d.status === "error") {
            stopPolling();
            setError(d.error ?? "Analysis failed");
            setStep("selfie");
          }
        } catch { /* keep polling */ }
      }, 1500);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to connect to API.";
      setError(msg);
      setStep("selfie");
    }
  }, [meta, selfieB64, bodyB64]);

  // Trigger analysis once both photos are ready
  useEffect(() => {
    if (step === "analyzing" && selfieB64 && bodyB64 && meta) {
      startAnalysis();
    }
    return stopPolling;
  }, []);

  // Render
  if (step === "landing") return <Landing onStart={() => setStep("metadata")} />;

  if (step === "metadata") return (
    <MetadataForm onNext={m => { setMeta(m); setStep("selfie"); }} />
  );

  if (step === "selfie") return (
    <>
      {error && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-xl bg-red-900/80 border border-red-700 text-red-200 text-sm max-w-sm text-center">
          {error}
        </div>
      )}
      <PhotoUpload
        stepLabel="Step 2 of 3"
        title="Upload your selfie"
        description="A clear, neutral-expression, front-facing photo. Even lighting, no sunglasses."
        hint="JPG or PNG · Natural lighting · Face centred"
        onPhoto={(b64, prev) => {
          setSelfieB64(b64);
          setSelfiePreview(prev);
        }}
      />
      {selfieB64 && (
        <div className="fixed bottom-6 left-0 right-0 flex justify-center">
          <button onClick={() => setStep("body")}
            className="px-10 py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-lg shadow-lg hover:opacity-90 active:scale-95 transition-all">
            Next →
          </button>
        </div>
      )}
    </>
  );

  if (step === "body") return (
    <>
      <PhotoUpload
        stepLabel="Step 3 of 3"
        title="Upload a full-body photo"
        description="Stand naturally, facing forward, arms slightly away from your body."
        hint="Full height visible · Fitted clothing · Neutral background"
        onPhoto={(b64, prev) => {
          setBodyB64(b64);
          setBodyPreview(prev);
        }}
      />
      {bodyB64 && (
        <div className="fixed bottom-6 left-0 right-0 flex justify-center">
          <button onClick={() => { setStep("analyzing"); setTimeout(startAnalysis, 100); }}
            className="px-10 py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-lg shadow-lg hover:opacity-90 active:scale-95 transition-all">
            Analyse My Style ✦
          </button>
        </div>
      )}
    </>
  );

  if (step === "analyzing") return <AnalyzingScreen progress="" />;

  if (step === "results" && session) return <Results data={session} />;

  return null;
}
