# app/cap/provider.py
import asyncio
import json
from croo import (
    AgentClient, Config, EventType,
    DeliverOrderRequest, DeliverableType, APIError
)
from app.config import get_settings
from app.intelligence.pipeline import run_pipeline

settings = get_settings()


def build_client() -> AgentClient:
    config = Config(
        base_url=settings.croo_api_url,
        ws_url=settings.croo_ws_url,
    )
    return AgentClient(config, settings.croo_sdk_key)


async def handle_negotiation(client: AgentClient, negotiation_id: str):
    """Accept incoming order negotiation."""
    try:
        result = await client.accept_negotiation(negotiation_id)
        print(f"[CAP] Accepted negotiation → order: {result.order_id}")
    except APIError as e:
        print(f"[CAP] Failed to accept negotiation {negotiation_id}: {e}")
    except Exception as e:
        print(f"[CAP] Unexpected error accepting negotiation: {e}")


async def handle_paid_order(client: AgentClient, order_id: str):
    """Order is paid — run pipeline and deliver result."""
    try:
        # Get order details
        order = await client.get_order(order_id)
        print(f"[CAP] Processing paid order: {order_id}")

        # Parse requirements
        try:
            payload = json.loads(order.requirements or "{}")
        except (json.JSONDecodeError, AttributeError):
            payload = {}

        query = payload.get("query", "").strip()
        depth = payload.get("depth", "standard")

        if not query:
            await client.reject_order(order_id, "No query provided in requirements.")
            print(f"[CAP] Rejected order {order_id} — no query")
            return

        print(f"[SupplyMind] Running pipeline: '{query}' (depth={depth})")

        # Run intelligence pipeline
        report = await run_pipeline(query, depth=depth)

        # Deliver result
        deliverable_text = json.dumps(report, ensure_ascii=False, indent=2)
        deliver_req = DeliverOrderRequest(
            deliverable_type=DeliverableType.TEXT,
            deliverable_text=deliverable_text,
        )
        result = await client.deliver_order(order_id, deliver_req)
        print(f"[CAP] ✓ Delivered order {order_id} | tx: {result.tx_hash}")

    except APIError as e:
        print(f"[CAP] APIError on order {order_id}: {e}")
        try:
            await client.reject_order(order_id, f"API error: {str(e)[:200]}")
        except Exception:
            pass
    except Exception as e:
        print(f"[CAP] Error on order {order_id}: {e}")
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
        negotiation_id = event.data.get("negotiation_id", "")
        print(f"[CAP] New negotiation: {negotiation_id}")
        asyncio.create_task(handle_negotiation(client, negotiation_id))

    def on_order_paid(event):
        order_id = event.data.get("order_id", "")
        print(f"[CAP] Order paid: {order_id}")
        asyncio.create_task(handle_paid_order(client, order_id))

    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation_created)
    stream.on(EventType.ORDER_PAID, on_order_paid)

    try:
        while True:
            await asyncio.sleep(10)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("[CAP] Shutting down provider...")