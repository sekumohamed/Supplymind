import time
import hashlib
from app.intelligence.data_ingestion import fetch_all_sources
from app.intelligence.embedder import embed_documents
from app.intelligence.synthesizer import synthesize_report
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

MIN_DOCUMENTS_FOR_FULL_CONFIDENCE = 3


def make_query_hash(query: str, depth: str) -> str:
    return hashlib.md5(f"{query.lower().strip()}:{depth}".encode()).hexdigest()


async def run_pipeline(query: str, depth: str = "standard") -> dict:
    start = time.time()
    logger.info(f"[Pipeline] Starting for: '{query}' (depth={depth})")

    documents = await fetch_all_sources(query, depth=depth)
    if not documents:
        logger.warning(f"[Pipeline] No documents found for: '{query}'")
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
            "query_hash": make_query_hash(query, depth),
            "processing_time_ms": int((time.time() - start) * 1000),
        }

    top_chunks = await embed_documents(query, documents, top_k=8)
    report = await synthesize_report(query, top_chunks, documents)

    report["processing_time_ms"] = int((time.time() - start) * 1000)
    report["query_hash"] = make_query_hash(query, depth)
    report.setdefault(
        "data_availability",
        "full" if len(documents) >= MIN_DOCUMENTS_FOR_FULL_CONFIDENCE else "partial",
    )
    logger.info(
        f"[Pipeline] Done in {report['processing_time_ms']}ms | "
        f"Risk: {report.get('risk_level')} | Data: {report['data_availability']}"
    )
    return report