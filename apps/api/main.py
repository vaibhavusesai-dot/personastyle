"""PersonaStyle — FastAPI entry point. Run from apps/api/: uvicorn main:app --reload --port 8000"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyze, session, tryon

app = FastAPI(title="PersonaStyle API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["Analysis"])
app.include_router(session.router, prefix="/api/v1/session", tags=["Session"])
app.include_router(tryon.router,   prefix="/api/v1/tryon",   tags=["Try-On"])

@app.get("/health")
async def health():
    return {"status": "ok"}
