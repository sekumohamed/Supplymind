import asyncio
import json
from croo import (
    AgentClient, Config, EventType,
    DeliverOrderRequest, DeliverableType, APIError
)
from app.config import get_settings
from app.intelligence.pipeline import run_pipeline
from app.cap.activity_log import log_event

settings = get_settings()


def build_client() -> AgentClient:
    config = Config(
        base_url=settings.croo_api_url,
        ws_url=settings.croo_ws_url,
    )
    return AgentClient(config, settings.croo_sdk_key)


async def handle_negotiation(client: AgentClient, negotiation_id: str):
    """Accept incoming order negotiation."""
    await log_event(
        "negotiation_created",
        f"New negotiation received from CROO network",
        {"negotiation_id": negotiation_id},
    )
    try:
        result = await client.accept_negotiation(negotiation_id)
        print(f"[CAP] Accepted negotiation → order: {result.order.order_id}")
        await log_event(
            "negotiation_accepted",
            f"Accepted → order {result.order.order_id} created",
            {"negotiation_id": negotiation_id, "order_id": result.order.order_id},
)
    except APIError as e:
        print(f"[CAP] Failed to accept negotiation {negotiation_id}: {e}")
        await log_event(
            "negotiation_failed",
            f"Failed to accept negotiation: {str(e)[:150]}",
            {"negotiation_id": negotiation_id},
        )
    except Exception as e:
        print(f"[CAP] Unexpected error accepting negotiation: {e}")
        await log_event(
            "negotiation_error",
            f"Unexpected error: {str(e)[:150]}",
            {"negotiation_id": negotiation_id},
        )


async def handle_paid_order(client: AgentClient, order_id: str):
    """Order is paid — run pipeline and deliver result."""
    await log_event(
        "order_paid",
        f"Payment confirmed for order {order_id}",
        {"order_id": order_id},
    )
    try:
        order = await client.get_order(order_id)
        print(f"[CAP] Processing paid order: {order_id}")

        try:
            negotiation = await client.get_negotiation(order.negotiation_id)
            payload = json.loads(negotiation.requirements or "{}")
        except (json.JSONDecodeError, AttributeError, APIError) as e:
            print(f"[CAP] Failed to load negotiation requirements for order {order_id}: {e}")
            payload = {}

        query = payload.get("query", "").strip()
        depth = payload.get("depth", "standard")

        if not query:
            await client.reject_order(order_id, "No query provided in requirements.")
            print(f"[CAP] Rejected order {order_id} — no query")
            await log_event(
                "order_rejected",
                f"Order {order_id} rejected — no query in requirements",
                {"order_id": order_id},
            )
            return

        print(f"[SupplyMind] Running pipeline: '{query}' (depth={depth})")
        await log_event(
            "order_processing",
            f"Running intelligence pipeline: \"{query}\" (depth={depth})",
            {"order_id": order_id, "query": query, "depth": depth},
        )

        report = await run_pipeline(query, depth=depth)

        deliverable_text = json.dumps(report, ensure_ascii=False, indent=2)
        deliver_req = DeliverOrderRequest(
            deliverable_type=DeliverableType.TEXT,
            deliverable_text=deliverable_text,
        )
        result = await client.deliver_order(order_id, deliver_req)
        print(f"[CAP] ✓ Delivered order {order_id} | tx: {result.tx_hash}")
        await log_event(
            "order_delivered",
            f"Delivered — tx {result.tx_hash}",
            {"order_id": order_id, "tx_hash": result.tx_hash, "risk_level": report.get("risk_level")},
        )

    except APIError as e:
        print(f"[CAP] APIError on order {order_id}: {e}")
        await log_event(
            "order_error",
            f"API error on order {order_id}: {str(e)[:150]}",
            {"order_id": order_id},
        )
        try:
            await client.reject_order(order_id, f"API error: {str(e)[:200]}")
        except Exception:
            pass
    except Exception as e:
        print(f"[CAP] Error on order {order_id}: {e}")
        await log_event(
            "order_error",
            f"Internal error on order {order_id}: {str(e)[:150]}",
            {"order_id": order_id},
        )
        try:
            await client.reject_order(order_id, f"Internal error: {str(e)[:200]}")
        except Exception:
            pass


async def run_provider():
    """Main CAP provider loop — connect and listen for orders."""
    if not settings.croo_sdk_key:
        print("[CAP] CROO_SDK_KEY not set — skipping CAP provider")
        print("[CAP] Set CROO_SDK_KEY in .env after registering on agent.croo.network")
        return

    client = build_client()
    print("[CAP] Connecting to CROO WebSocket...")
    stream = await client.connect_websocket()
    print("[CAP] ✓ SupplyMind is ONLINE — waiting for orders")

    def on_negotiation_created(event):
        negotiation_id = event.negotiation_id
        print(f"[CAP] New negotiation: {negotiation_id}")
        asyncio.create_task(handle_negotiation(client, negotiation_id))

    def on_order_paid(event):
        order_id = event.order_id
        print(f"[CAP] Order paid: {order_id}")
        asyncio.create_task(handle_paid_order(client, order_id))

    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation_created)
    stream.on(EventType.ORDER_PAID, on_order_paid)

    try:
        while True:
            await asyncio.sleep(10)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("[CAP] Shutting down provider...")