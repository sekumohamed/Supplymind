# app/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.database import init_db
from app.intelligence.pipeline import run_pipeline
from app.cap.provider import run_provider
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    provider_task = asyncio.create_task(run_provider())
    print("[Startup] SupplyMind is ready")
    yield
    provider_task.cancel()
    try:
        await provider_task
    except asyncio.CancelledError:
        pass
    print("[Shutdown] SupplyMind stopped")


app = FastAPI(
    title="SupplyMind",
    description="Real-time Supply Chain Intelligence Agent on CROO",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(                                  
    CORSMiddleware,                                   
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    depth: str = "standard"


@app.get("/health")
def health():
    return {"status": "ok", "agent": "SupplyMind", "version": "1.0.0"}


@app.post("/analyze")
async def analyze(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if req.depth not in ("standard", "deep"):
        raise HTTPException(status_code=400, detail="depth must be standard or deep")
    report = await run_pipeline(req.query, depth=req.depth)
    return report


@app.get("/info")
def info():
    return {
        "name": "SupplyMind",
        "description": "A2A-callable supply chain intelligence agent on CROO",
        "docs": "/docs",
        "health": "/health",
    }
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")