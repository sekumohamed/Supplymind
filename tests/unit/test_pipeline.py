# tests/unit/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch
from app.intelligence.pipeline import run_pipeline, make_query_hash


class TestMakeQueryHash:
    def test_deterministic(self):
        h1 = make_query_hash("port congestion in Shanghai", "standard")
        h2 = make_query_hash("port congestion in Shanghai", "standard")
        assert h1 == h2

    def test_case_and_whitespace_insensitive(self):
        h1 = make_query_hash("  Shanghai Port  ", "standard")
        h2 = make_query_hash("shanghai port", "standard")
        assert h1 == h2

    def test_different_depth_gives_different_hash(self):
        h1 = make_query_hash("shanghai port", "standard")
        h2 = make_query_hash("shanghai port", "deep")
        assert h1 != h2

    def test_different_query_gives_different_hash(self):
        h1 = make_query_hash("shanghai port", "standard")
        h2 = make_query_hash("suez canal", "standard")
        assert h1 != h2


class TestRunPipelineNoDocuments:
    @pytest.mark.asyncio
    async def test_returns_unknown_fallback_when_no_sources(self):
        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=[]),
        ):
            report = await run_pipeline("some obscure query", depth="standard")

        assert report["risk_level"] == "UNKNOWN"
        assert report["risk_score"] == 0.0
        assert report["confidence_score"] == 0.0
        assert report["disruption_signals"] == []
        assert report["data_sources"] == []
        assert "processing_time_ms" in report
        assert isinstance(report["processing_time_ms"], int)
        assert report["query_hash"] == make_query_hash("some obscure query", "standard")
    


class TestRunPipelineHappyPath:
    @pytest.mark.asyncio
    async def test_full_pipeline_wires_metadata_onto_synthesizer_output(self):
        fake_documents = [{"source": "reuters", "content": "tariffs rising"}]
        fake_chunks = [{"text": "tariffs rising", "score": 0.9}]
        fake_report = {
            "risk_level": "HIGH",
            "risk_score": 0.82,
            "executive_summary": "Elevated tariff risk detected.",
            "disruption_signals": ["tariff hike"],
            "tariff_exposure": {"category": "electronics"},
            "alternative_suppliers": [],
            "action_items": ["Diversify supplier base"],
            "confidence_score": 0.75,
            "data_sources": ["reuters"],
        }

        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=fake_documents),
        ), patch(
            "app.intelligence.pipeline.embed_documents",
            new=AsyncMock(return_value=fake_chunks),
        ), patch(
            "app.intelligence.pipeline.synthesize_report",
            new=AsyncMock(return_value=fake_report),
        ):
            report = await run_pipeline("Shanghai port congestion", depth="deep")

        assert report["risk_level"] == "HIGH"
        assert "processing_time_ms" in report
        assert isinstance(report["processing_time_ms"], int)
        assert report["query_hash"] == make_query_hash(
            "Shanghai port congestion", "deep"
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_stages_in_order_with_correct_args(self):
        fake_documents = [{"source": "tavily", "content": "x"}]
        fake_chunks = [{"text": "x"}]
        fake_report = {"risk_level": "LOW", "risk_score": 0.1, "confidence_score": 0.5}

        mock_fetch = AsyncMock(return_value=fake_documents)
        mock_embed = AsyncMock(return_value=fake_chunks)
        mock_synth = AsyncMock(return_value=fake_report)

        with patch("app.intelligence.pipeline.fetch_all_sources", new=mock_fetch), \
             patch("app.intelligence.pipeline.embed_documents", new=mock_embed), \
             patch("app.intelligence.pipeline.synthesize_report", new=mock_synth):
            await run_pipeline("test query", depth="standard")

        mock_fetch.assert_awaited_once_with("test query", depth="standard")
        mock_embed.assert_awaited_once_with("test query", fake_documents, top_k=8)
        mock_synth.assert_awaited_once_with("test query", fake_chunks, fake_documents)


class TestDataAvailability:
    @pytest.mark.asyncio
    async def test_marks_unavailable_when_no_documents(self):
        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=[]),
        ):
            report = await run_pipeline("some obscure query", depth="standard")

        assert report["data_availability"] == "unavailable"

    @pytest.mark.asyncio
    async def test_marks_partial_when_below_threshold(self):
        fake_documents = [{"source": "reuters", "content": "tariffs rising"}]
        fake_chunks = [{"text": "tariffs rising", "score": 0.9}]
        fake_report = {"risk_level": "HIGH", "risk_score": 0.8, "confidence_score": 0.5}

        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=fake_documents),
        ), patch(
            "app.intelligence.pipeline.embed_documents",
            new=AsyncMock(return_value=fake_chunks),
        ), patch(
            "app.intelligence.pipeline.synthesize_report",
            new=AsyncMock(return_value=fake_report),
        ):
            report = await run_pipeline("Shanghai port congestion", depth="standard")

        assert report["data_availability"] == "partial"

    @pytest.mark.asyncio
    async def test_marks_full_when_at_or_above_threshold(self):
        fake_documents = [
            {"source": "reuters", "content": "tariffs rising"},
            {"source": "tavily", "content": "port delays"},
            {"source": "newsapi", "content": "shipping costs up"},
        ]
        fake_chunks = [{"text": "tariffs rising", "score": 0.9}]
        fake_report = {"risk_level": "HIGH", "risk_score": 0.8, "confidence_score": 0.9}

        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=fake_documents),
        ), patch(
            "app.intelligence.pipeline.embed_documents",
            new=AsyncMock(return_value=fake_chunks),
        ), patch(
            "app.intelligence.pipeline.synthesize_report",
            new=AsyncMock(return_value=fake_report),
        ):
            report = await run_pipeline("Shanghai port congestion", depth="standard")

        assert report["data_availability"] == "full"

    @pytest.mark.asyncio
    async def test_does_not_override_if_synthesizer_already_set_it(self):
        fake_documents = [
            {"source": "reuters", "content": "tariffs rising"},
            {"source": "tavily", "content": "port delays"},
            {"source": "newsapi", "content": "shipping costs up"},
        ]
        fake_chunks = [{"text": "tariffs rising", "score": 0.9}]
        fake_report = {
            "risk_level": "HIGH",
            "risk_score": 0.8,
            "confidence_score": 0.9,
            "data_availability": "custom_value_from_synthesizer",
        }

        with patch(
            "app.intelligence.pipeline.fetch_all_sources",
            new=AsyncMock(return_value=fake_documents),
        ), patch(
            "app.intelligence.pipeline.embed_documents",
            new=AsyncMock(return_value=fake_chunks),
        ), patch(
            "app.intelligence.pipeline.synthesize_report",
            new=AsyncMock(return_value=fake_report),
        ):
            report = await run_pipeline("Shanghai port congestion", depth="standard")

        assert report["data_availability"] == "custom_value_from_synthesizer"