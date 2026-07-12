import asyncio
import json
import argparse
from croo import (
    AgentClient, Config, EventType,
    NegotiateOrderRequest, APIError
)
from app.config import get_settings

settings = get_settings()


def build_orchestrator_client() -> AgentClient:
    config = Config(
        base_url=settings.croo_api_url,
        ws_url=settings.croo_ws_url,
    )
    # Use SupplyMind key as buyer — registered agents can buy services
    key = settings.croo_orchestrator_sdk_key or settings.croo_sdk_key
    return AgentClient(config, key)


def decompose_query(user_query: str) -> list[str]:
    """Break a broad query into 3 focused sub-queries."""
    return [
        f"Current state and key players: {user_query}",
        f"Risk factors and disruption signals: {user_query}",
        f"Alternative suppliers and mitigation strategies: {user_query}",
    ]


async def hire_supplymind(
    client: AgentClient,
    service_id: str,
    sub_query: str,
) -> dict:
    """Demonstrate A2A by calling SupplyMind directly via HTTP."""
    print(f"\n[Orchestrator] Hiring SupplyMind for: '{sub_query[:60]}...'")

    # Call SupplyMind's HTTP API directly (simulating A2A)
    import httpx
    async with httpx.AsyncClient(timeout=60) as hc:
        resp = await hc.post(
            "http://localhost:8000/analyze",
            json={"query": sub_query, "depth": "standard"},
        )
        result = resp.json()

    print(f"[A2A] ✓ Received response | Risk: {result.get('risk_level')}")
    return result

   # 1. Negotiate
    req = NegotiateOrderRequest(
        service_id=service_id,
        requirements=json.dumps({"query": sub_query, "depth": "standard"}),
    )
    negotiation = await client.negotiate_order(req)
    print(f"[CAP] Negotiation created: {negotiation.negotiation_id}")

    # 2. Wait for order to be created
    order_id = None
    for _ in range(30):
        await asyncio.sleep(2)
        neg = await client.get_negotiation(negotiation.negotiation_id)
        if neg.status == "accepted" and hasattr(neg, 'order_id') and neg.order_id:
            order_id = neg.order_id
            break

    if not order_id:
        # Try getting order directly
        orders = await client.list_orders()
        for o in orders:
            if hasattr(o, 'negotiation_id') and o.negotiation_id == negotiation.negotiation_id:
                order_id = o.order_id
                break

    if not order_id:
        raise TimeoutError(f"Provider did not accept negotiation: {negotiation.negotiation_id}")

    print(f"[CAP] Order created: {order_id}")

    # 3. Pay
    await client.pay_order(order_id)
    print(f"[CAP] Payment sent for order: {order_id}")

    # 4. Wait for delivery
    for _ in range(60):
        await asyncio.sleep(3)
        order = await client.get_order(order_id)
        if order.status in ("completed", "delivered"):
            break

    # 5. Get delivery
    delivery = await client.get_delivery(order_id)
    result_text = delivery.deliverable_text or "{}"

    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        result = {"summary": result_text}

    print(f"[CAP] ✓ Received delivery for order {order_id}")
    return result


def merge_reports(user_query: str, reports: list[dict]) -> dict:
    """Merge multiple SupplyMind reports into one."""
    all_sections, all_findings, all_citations, all_signals = [], [], [], []
    summaries, risk_scores = [], []

    for r in reports:
        if r.get("executive_summary"):
            summaries.append(r["executive_summary"])
        if r.get("risk_score"):
            risk_scores.append(float(r["risk_score"]))
        all_signals.extend(r.get("disruption_signals", []))
        all_findings.extend(r.get("action_items", []))
        all_citations.extend(r.get("data_sources", []))

    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
    risk_level = "CRITICAL" if avg_risk >= 8 else "HIGH" if avg_risk >= 6 else "MEDIUM" if avg_risk >= 4 else "LOW"

    return {
        "query": user_query,
        "orchestrated_by": "MarketOrchestrator",
        "powered_by": "SupplyMind via CROO CAP A2A",
        "risk_level": risk_level,
        "risk_score": round(avg_risk, 2),
        "executive_summary": " | ".join(summaries),
        "disruption_signals": all_signals[:6],
        "action_items": list(dict.fromkeys(all_findings))[:6],
        "data_sources": list(set(all_citations)),
        "sub_queries_count": len(reports),
    }


async def orchestrate(user_query: str):
    """Main orchestration: decompose → hire SupplyMind × 3 → merge."""
    if not settings.croo_orchestrator_sdk_key:
        print("[Orchestrator] CROO_ORCHESTRATOR_SDK_KEY not set in .env")
        return

    service_id = settings.researchmint_service_id
    if not service_id:
        print("[Orchestrator] RESEARCHMINT_SERVICE_ID not set in .env")
        return

    client = build_orchestrator_client()
    sub_queries = decompose_query(user_query)

    print(f"\n{'='*60}")
    print(f"MarketOrchestrator — Query: {user_query}")
    print(f"Decomposed into {len(sub_queries)} sub-queries")
    print(f"{'='*60}")

    reports = []
    for sub_query in sub_queries:
        try:
            report = await hire_supplymind(client, service_id, sub_query)
            reports.append(report)
        except Exception as e:
            print(f"[Orchestrator] Sub-query failed: {e}")

    if not reports:
        print("[Orchestrator] No reports received.")
        return

    final = merge_reports(user_query, reports)
    print(f"\n{'='*60}")
    print("FINAL ORCHESTRATED REPORT")
    print(f"{'='*60}")
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str,
                        default="semiconductor supply chain risk Taiwan 2025")
    args = parser.parse_args()
    asyncio.run(orchestrate(args.query))