import pytest
import pytest_asyncio  
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

FAKE_REPORT = {
    "risk_level": "HIGH",
    "risk_score": 0.7,
    "executive_summary": "Test summary",
    "disruption_signals": ["strike risk"],
    "tariff_exposure": {"category": "steel"},
    "alternative_suppliers": [],
    "action_items": ["diversify"],
    "confidence_score": 0.8,
    "data_sources": ["reuters"],
    "processing_time_ms": 42,
    "query_hash": "irrelevant-will-be-overwritten",
}


@pytest_asyncio.fixture  
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["agent"] == "SupplyMind"


class TestAnalyzeValidation:
    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, client):
        resp = await client.post("/analyze", json={"query": "   ", "depth": "standard"})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_depth_rejected(self, client):
        resp = await client.post("/analyze", json={"query": "shanghai port", "depth": "ultra"})
        assert resp.status_code == 400
        assert "depth" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_missing_query_field_422(self, client):
        resp = await client.post("/analyze", json={"depth": "standard"})
        assert resp.status_code == 422  # pydantic validation, not our HTTPException


class TestAnalyzeHappyPathAndCache:
    @pytest.mark.asyncio
    async def test_analyze_returns_report_and_caches_it(self, client):
        with patch(
            "app.main.run_pipeline",
            new=AsyncMock(return_value=dict(FAKE_REPORT)),
        ) as mock_pipeline:
            resp1 = await client.post(
                "/analyze", json={"query": "Shanghai port strike", "depth": "standard"}
            )
            assert resp1.status_code == 200
            body1 = resp1.json()
            assert body1["risk_level"] == "HIGH"
            mock_pipeline.assert_awaited_once()

            # second identical call should hit cache, NOT call run_pipeline again
            resp2 = await client.post(
                "/analyze", json={"query": "Shanghai port strike", "depth": "standard"}
            )
            assert resp2.status_code == 200
            assert resp2.json() == body1
            mock_pipeline.assert_awaited_once()  # still just once

    @pytest.mark.asyncio
    async def test_different_depth_is_not_a_cache_hit(self, client):
        with patch(
            "app.main.run_pipeline",
            new=AsyncMock(return_value=dict(FAKE_REPORT)),
        ) as mock_pipeline:
            await client.post("/analyze", json={"query": "Suez canal", "depth": "standard"})
            await client.post("/analyze", json={"query": "Suez canal", "depth": "deep"})
            assert mock_pipeline.await_count == 2


class TestHistory:
    @pytest.mark.asyncio
    async def test_history_empty_returns_list(self, client):
        resp = await client.get("/history")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_history_populated_after_analyze(self, client):
        with patch(
            "app.main.run_pipeline",
            new=AsyncMock(return_value=dict(FAKE_REPORT)),
        ):
            await client.post("/analyze", json={"query": "Panama canal drought", "depth": "standard"})

        resp = await client.get("/history")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["query"] == "Panama canal drought"
        assert rows[0]["risk_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_history_query_filter(self, client):
        with patch(
            "app.main.run_pipeline",
            new=AsyncMock(return_value=dict(FAKE_REPORT)),
        ):
            await client.post("/analyze", json={"query": "Red Sea shipping", "depth": "standard"})
            await client.post("/analyze", json={"query": "Suez canal delays", "depth": "standard"})

        resp = await client.get("/history", params={"query": "suez"})
        rows = resp.json()
        assert len(rows) == 1
        assert "suez" in rows[0]["query"].lower()