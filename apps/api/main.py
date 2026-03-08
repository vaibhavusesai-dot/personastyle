"""PersonaStyle — FastAPI entry point. Run from apps/api/: uvicorn main:app --reload --port 8000"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from routers import analyze, session, tryon

# ── Structured logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("personastyle")

# ── Rate limiter (shared limiter instance attached to app.state) ─────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── CORS origins from env var — never wildcard in production ─────────────────
_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]

app = FastAPI(title="PersonaStyle API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# FIX #10 — CORS: restrict methods and headers; no credentials (tokens in headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-Token"],
)

# FIX #15 — Security headers on every response
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]   = "nosniff"
    response.headers["X-Frame-Options"]           = "DENY"
    response.headers["X-XSS-Protection"]          = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"]   = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers.pop("server", None)           # suppress server fingerprinting
    return response

# FIX #3 — Hard request-body size cap before any parsing (10 MB)
MAX_REQUEST_BYTES = 10 * 1024 * 1024

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_REQUEST_BYTES:
        log.warning("Rejected oversized request from %s (%s bytes)", request.client, cl)
        return JSONResponse(status_code=413, content={"detail": "Payload too large (max 10 MB)"})
    return await call_next(request)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["Analysis"])
app.include_router(session.router, prefix="/api/v1/session", tags=["Session"])
app.include_router(tryon.router,   prefix="/api/v1/tryon",   tags=["Try-On"])

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
