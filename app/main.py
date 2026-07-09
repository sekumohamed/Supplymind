import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from app.database import init_db, AsyncSessionLocal
from app.intelligence.pipeline import run_pipeline, make_query_hash
from app.cap.provider import run_provider
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc
from app.models.history import QueryHistory
from app.models.cache import QueryCache
from app.cap.activity_log import get_events
from app.utils.rate_limit import enforce_rate_limit

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
async def analyze(req: QueryRequest, _: None = Depends(enforce_rate_limit)):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if req.depth not in ("standard", "deep"):
        raise HTTPException(status_code=400, detail="depth must be standard or deep")

    query_hash = make_query_hash(req.query, req.depth)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(QueryCache).where(QueryCache.query_hash == query_hash)
        )
        cached = result.scalar_one_or_none()
        if cached and cached.expires_at:
            expires = cached.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > now:
                print(f"[Cache] HIT for '{req.query}' ({req.depth})")
                return cached.result_json

    report = await run_pipeline(req.query, depth=req.depth)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(QueryCache).where(QueryCache.query_hash == query_hash)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.result_json = report
                existing.created_at = now
                existing.expires_at = now + timedelta(minutes=30)
            else:
                session.add(QueryCache(
                    id=query_hash,
                    query_hash=query_hash,
                    result_json=report,
                ))
            await session.commit()
    except Exception as e:
        print(f"[Cache] Failed to store: {e}")

    try:
        async with AsyncSessionLocal() as session:
            session.add(QueryHistory(
                query=req.query,
                query_hash=report.get("query_hash"),
                depth=req.depth,
                risk_level=report.get("risk_level"),
                risk_score=report.get("risk_score"),
                executive_summary=report.get("executive_summary"),
                disruption_signals=report.get("disruption_signals"),
                tariff_exposure=report.get("tariff_exposure"),
                confidence_score=report.get("confidence_score"),
                processing_time_ms=report.get("processing_time_ms"),
            ))
            await session.commit()
    except Exception as e:
        print(f"[History] Failed to log query: {e}")

    return report


@app.get("/history")
async def get_history(query: str | None = None, limit: int = 20):
    async with AsyncSessionLocal() as session:
        stmt = select(QueryHistory).order_by(desc(QueryHistory.created_at)).limit(limit)
        if query:
            stmt = stmt.where(QueryHistory.query.ilike(f"%{query}%"))
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "query": r.query,
                "depth": r.depth,
                "risk_level": r.risk_level,
                "risk_score": r.risk_score,
                "executive_summary": r.executive_summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


@app.get("/info")
def info():
    return {
        "name": "SupplyMind",
        "description": "A2A-callable supply chain intelligence agent on CROO",
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/cap/activity")
async def cap_activity(limit: int = 20):
    return get_events(limit)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")