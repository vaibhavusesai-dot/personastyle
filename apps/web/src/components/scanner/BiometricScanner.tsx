"use client";

/**
 * BiometricScanner
 * ----------------
 * Guides the user to capture a neutral frontal selfie with balanced lighting.
 * Uses the MediaDevices API for camera access and canvas for frame capture.
 * Runs a client-side heuristic (brightness + symmetry probe) to surface
 * real-time quality hints before the image is submitted to the API.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalyzeRequest, Gender } from "../types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ScanStep = "idle" | "permissions" | "preview" | "quality_check" | "captured" | "error";

interface ScanHint {
  type: "warning" | "error" | "success";
  message: string;
}

interface BiometricScannerProps {
  onCapture: (selfieBase64: string) => void;
  onError?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Sample average brightness from a greyscale canvas frame [0, 255]. */
function sampleBrightness(ctx: CanvasRenderingContext2D, w: number, h: number): number {
  const data = ctx.getImageData(0, 0, w, h).data;
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) {
    sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  return sum / (data.length / 4);
}

/** Very rough left/right half-frame brightness symmetry check. */
function measureSymmetry(ctx: CanvasRenderingContext2D, w: number, h: number): number {
  const left  = ctx.getImageData(0, 0, w / 2, h).data;
  const right = ctx.getImageData(w / 2, 0, w / 2, h).data;
  let diff = 0;
  for (let i = 0; i < left.length; i += 4) {
    const gl = 0.299 * left[i]  + 0.587 * left[i + 1]  + 0.114 * left[i + 2];
    const gr = 0.299 * right[i] + 0.587 * right[i + 1] + 0.114 * right[i + 2];
    diff += Math.abs(gl - gr);
  }
  return 1 - diff / (left.length / 4) / 255;  // 0 (no symmetry) → 1 (perfect)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BiometricScanner({ onCapture, onError }: BiometricScannerProps) {
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef    = useRef<number>(0);

  const [step, setStep]   = useState<ScanStep>("idle");
  const [hints, setHints] = useState<ScanHint[]>([]);
  const [capturedSrc, setCapturedSrc] = useState<string | null>(null);
  const [readyToCapture, setReadyToCapture] = useState(false);

  // --- Camera lifecycle ---
  const startCamera = useCallback(async () => {
    setStep("permissions");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width:  { ideal: 1280 },
          height: { ideal: 960 },
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStep("preview");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Camera access denied";
      setStep("error");
      onError?.(msg);
    }
  }, [onError]);

  const stopCamera = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  // --- Real-time quality analysis loop ---
  useEffect(() => {
    if (step !== "preview") return;

    const analyse = () => {
      const video  = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) {
        rafRef.current = requestAnimationFrame(analyse);
        return;
      }

      const w = video.videoWidth;
      const h = video.videoHeight;
      canvas.width  = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(video, 0, 0, w, h);

      const brightness = sampleBrightness(ctx, w, h);
      const symmetry   = measureSymmetry(ctx, w, h);

      const newHints: ScanHint[] = [];

      if (brightness < 60) {
        newHints.push({ type: "error", message: "Too dark — move to a brighter area or face a light source." });
      } else if (brightness > 210) {
        newHints.push({ type: "warning", message: "Too bright — reduce direct light to avoid overexposure." });
      } else {
        newHints.push({ type: "success", message: "Lighting looks good." });
      }

      if (symmetry < 0.75) {
        newHints.push({ type: "warning", message: "Face appears off-centre — look straight at the camera." });
      } else {
        newHints.push({ type: "success", message: "Face position looks centred." });
      }

      setHints(newHints);
      setReadyToCapture(newHints.every((h) => h.type !== "error"));

      rafRef.current = requestAnimationFrame(analyse);
    };

    rafRef.current = requestAnimationFrame(analyse);
    return () => cancelAnimationFrame(rafRef.current);
  }, [step]);

  // --- Capture ---
  const capture = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    setStep("quality_check");
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d")!;
    // Mirror the image (selfie convention)
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    const base64  = dataUrl.split(",")[1];

    stopCamera();
    setCapturedSrc(dataUrl);
    setStep("captured");
    onCapture(base64);
  }, [onCapture, stopCamera]);

  const retake = useCallback(() => {
    setCapturedSrc(null);
    setHints([]);
    startCamera();
  }, [startCamera]);

  // Cleanup on unmount
  useEffect(() => () => stopCamera(), [stopCamera]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="relative flex flex-col items-center gap-4 w-full max-w-md mx-auto select-none">
      {/* --- Oval face guide overlay --- */}
      <div className="relative w-full aspect-[3/4] bg-black rounded-2xl overflow-hidden shadow-2xl">
        {step !== "captured" ? (
          <>
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              style={{ transform: "scaleX(-1)" }}  // mirror
              muted
              playsInline
            />
            {/* SVG oval guide */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              viewBox="0 0 300 400"
            >
              <defs>
                <mask id="face-mask">
                  <rect width="300" height="400" fill="white" />
                  <ellipse cx="150" cy="185" rx="95" ry="125" fill="black" />
                </mask>
              </defs>
              <rect
                width="300"
                height="400"
                fill="rgba(0,0,0,0.45)"
                mask="url(#face-mask)"
              />
              <ellipse
                cx="150"
                cy="185"
                rx="95"
                ry="125"
                fill="none"
                stroke={readyToCapture ? "#22c55e" : "#facc15"}
                strokeWidth="3"
                strokeDasharray={readyToCapture ? "0" : "8 4"}
              />
              {/* Rule-of-thirds guide lines */}
              <line x1="0" y1="133" x2="300" y2="133" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
              <line x1="0" y1="266" x2="300" y2="266" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
            </svg>
          </>
        ) : (
          <img src={capturedSrc!} alt="Captured selfie" className="w-full h-full object-cover" />
        )}
      </div>

      {/* Hidden canvas used for analysis and capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* --- Quality hints --- */}
      {step === "preview" && hints.length > 0 && (
        <ul className="w-full space-y-1 text-sm">
          {hints.map((h, i) => (
            <li
              key={i}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium ${
                h.type === "error"   ? "bg-red-900/60 text-red-200" :
                h.type === "warning" ? "bg-yellow-900/60 text-yellow-200" :
                                       "bg-green-900/60 text-green-200"
              }`}
            >
              <span>
                {h.type === "error" ? "✗" : h.type === "warning" ? "⚠" : "✓"}
              </span>
              {h.message}
            </li>
          ))}
        </ul>
      )}

      {/* --- CTA buttons --- */}
      <div className="flex gap-3 w-full">
        {step === "idle" && (
          <button
            onClick={startCamera}
            className="flex-1 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
          >
            Open Camera
          </button>
        )}

        {step === "preview" && (
          <button
            onClick={capture}
            disabled={!readyToCapture}
            className="flex-1 py-3 rounded-xl font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-green-600 hover:bg-green-500 text-white"
          >
            {readyToCapture ? "Capture" : "Adjust Position…"}
          </button>
        )}

        {step === "captured" && (
          <>
            <button
              onClick={retake}
              className="flex-1 py-3 rounded-xl bg-zinc-700 hover:bg-zinc-600 text-white font-semibold transition-colors"
            >
              Retake
            </button>
            <button
              className="flex-1 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
            >
              Use Photo
            </button>
          </>
        )}

        {step === "error" && (
          <p className="text-red-400 text-sm text-center w-full">
            Camera access failed. Please allow camera permissions and refresh.
          </p>
        )}
      </div>

      {/* Instruction copy */}
      {step === "preview" && (
        <p className="text-zinc-400 text-xs text-center leading-relaxed">
          Position your face within the oval. Look straight ahead with a neutral expression.
          Ensure even lighting — avoid strong backlighting.
        </p>
      )}
    </div>
  );
}
