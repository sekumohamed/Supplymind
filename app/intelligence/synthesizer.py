# app/intelligence/synthesizer.py
import json
import asyncio
from groq import Groq
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are SupplyMind, an expert supply chain intelligence analyst.
Given a query and retrieved web content, produce a structured JSON risk report.

Output ONLY valid JSON with this exact structure:
{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_score": 0.0,
  "executive_summary": "2-3 sentence summary",
  "disruption_signals": [
    {"source": "...", "signal": "...", "severity": "low|medium|high"}
  ],
  "tariff_exposure": {
    "current_rate": "...",
    "risk_scenario": "...",
    "estimated_annual_impact_usd": 0
  },
  "alternative_suppliers": [
    {"name": "...", "country": "...", "fit_score": 0.0, "lead_time_weeks": 0}
  ],
  "action_items": ["...", "..."],
  "confidence_score": 0.0
}

Be factual. Use only information from the provided context.
Output JSON only — no preamble, no markdown, no explanation."""


def _call_groq(query: str, context: str, sources: list[dict]) -> dict:
    client = Groq(api_key=settings.groq_api_key)

    source_list = "\n".join(
        f"[{i+1}] {s.get('url', '')} — {s.get('title', '')}"
        for i, s in enumerate(sources[:8])
    )

    user_prompt = f"""Query: {query}

Retrieved context:
{context}

Sources:
{source_list}

Produce the structured JSON supply chain intelligence report now."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "risk_level": "UNKNOWN",
            "risk_score": 0.0,
            "executive_summary": raw[:300],
            "disruption_signals": [],
            "tariff_exposure": {},
            "alternative_suppliers": [],
            "action_items": [],
            "confidence_score": 0.0,
        }


async def synthesize_report(
    query: str,
    top_chunks: list[str],
    sources: list[dict],
) -> dict:
    """Call Groq async to synthesize supply chain intelligence report."""
    context = "\n\n---\n\n".join(top_chunks)
    report = await asyncio.to_thread(_call_groq, query, context, sources)
    report["query"] = query
    report["data_sources"] = list({s.get("source", "") for s in sources if s.get("source")})
    return report