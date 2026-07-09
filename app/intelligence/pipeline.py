# app/intelligence/pipeline.py
import time
import hashlib
from app.intelligence.data_ingestion import fetch_all_sources
from app.intelligence.embedder import embed_documents
from app.intelligence.synthesizer import synthesize_report

# Below this document count, we still produce a report, but flag it as
# "partial" so a caller (human or paying agent) knows the analysis had
# less source material than usual — e.g. because Tavily or NewsAPI
# degraded/timed out, or the query is genuinely obscure.
MIN_DOCUMENTS_FOR_FULL_CONFIDENCE = 3


def make_query_hash(query: str, depth: str) -> str:
    return hashlib.md5(f"{query.lower().strip()}:{depth}".encode()).hexdigest()


async def run_pipeline(query: str, depth: str = "standard") -> dict:
    """
    Full SupplyMind pipeline:
    fetch → embed → rerank → synthesize → return structured report
    """
    start = time.time()
    print(f"\n[Pipeline] Starting for: '{query}' (depth={depth})")

    # 1. Fetch from all sources
    documents = await fetch_all_sources(query, depth=depth)

    if not documents:
        return {
            "query": query,
            "risk_level": "UNKNOWN",
            "risk_score": 0.0,
            "executive_summary": "No data sources returned results for this query.",
            "disruption_signals": [],
            "tariff_exposure": {},
            "alternative_suppliers": [],
            "action_items": ["Retry with a more specific query"],
            "confidence_score": 0.0,
            "data_sources": [],
            "data_availability": "unavailable",
            "processing_time_ms": int((time.time() - start) * 1000),
        }

    # 2. Embed + rerank
    top_chunks = await embed_documents(query, documents, top_k=8)

    # 3. Synthesize with Groq
    report = await synthesize_report(query, top_chunks, documents)

    # 4. Add metadata
    report["processing_time_ms"] = int((time.time() - start) * 1000)
    report["query_hash"] = make_query_hash(query, depth)
    report.setdefault(
        "data_availability",
        "full" if len(documents) >= MIN_DOCUMENTS_FOR_FULL_CONFIDENCE else "partial",
    )

    print(
        f"[Pipeline] Done in {report['processing_time_ms']}ms | "
        f"Risk: {report.get('risk_level')} | Data: {report['data_availability']}"
    )
    return report