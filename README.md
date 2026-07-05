---
title: SupplyMind
emoji: 🏭
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# SupplyMind — Real-Time Supply Chain Intelligence Agent on CROO

[![Live Demo](https://img.shields.io/badge/Live-HuggingFace-yellow)](https://sekumohamed-supplymind.hf.space)
[![CROO Store](https://img.shields.io/badge/CROO-Agent%20Store-green)](https://agent.croo.network)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)

> The first AI-powered supply chain intelligence agent on CROO Agent Protocol (CAP). Submit a natural language query — get real-time risk scores, disruption signals, tariff exposure analysis, and alternative supplier recommendations. Every call is a paid on-chain transaction in USDC.

---

## The Problem

Supply chain managers today lose millions to blind spots:
- **Tariff volatility** — US-China tariffs hit 145% in 2025, changing weekly
- **Geopolitical disruptions** — Taiwan semiconductor risk, Red Sea shipping crisis
- **Analyst bottleneck** — senior planners cost $80K+/year and can only handle a few queries/day
- **No real-time intelligence** — existing tools (Kinaxis, Blue Yonder) cost $100K–$500K/year

**SupplyMind delivers per-query intelligence at $2 USDC** — 1000x cheaper than hiring an analyst.

---

## Market Opportunity

| Metric | Value |
|--------|-------|
| Agentic AI in supply chain (2025) | $8.67B |
| Market size (2030 projected) | $16.84B |
| CAGR | 14.2% |
| Companies investing in agentic AI by 2026 | 75% (Deloitte) |
| Revenue uplift from AI-driven supply chain | 61% greater (IBM) |

---

## Live Deployment

| Resource | URL |
|----------|-----|
| Production API | https://sekumohamed-supplymind.hf.space |
| Health Check | https://sekumohamed-supplymind.hf.space/health |
| API Documentation | https://sekumohamed-supplymind.hf.space/docs |
| CROO Agent Store | https://agent.croo.network |
| GitHub Repository | https://github.com/sekumohamed/Supplymind |

---

## CROO CAP Integration

### Services Listed on CROO Agent Store

| Service Name | Price | SLA | Deliverable |
|-------------|-------|-----|-------------|
| Supply Chain Analysis | 2 USDC | 5 min | JSON Report |

### SDK Methods Used

```python
from croo import AgentClient, Config, EventType, DeliverOrderRequest, DeliverableType

# Provider side (SupplyMind)
client = AgentClient(config, sdk_key)
stream = await client.connect_websocket()
stream.on(EventType.NEGOTIATION_CREATED, on_negotiation)
stream.on(EventType.ORDER_PAID, on_order_paid)
await client.accept_negotiation(negotiation_id)
await client.deliver_order(order_id, DeliverOrderRequest(
    deliverable_type=DeliverableType.TEXT,
    deliverable_text=json_report
))
```

### Payment Flow
Caller → negotiate_order() → CAP
CAP → NEGOTIATION_CREATED → SupplyMind
SupplyMind → accept_negotiation() → CAP
Caller → pay_order() → CAPVault [USDC locked in escrow]
CAP → ORDER_PAID → SupplyMind
SupplyMind → run_pipeline() → deliver_order()
CAPVault → release USDC → SupplyMind wallet

---

## System Architecture
'''
┌─────────────────────────────────────────────────────────┐
│                    EXTERNAL CALLERS                     │
│  Human User        Orchestrator Agent    Other Agents   │
└──────────────────────────┬──────────────────────────────┘
│ CAP (CROO Agent Protocol)
▼
┌─────────────────────────────────────────────────────────┐
│                  SUPPLYMIND CORE                        │
│                                                         │
│  ┌─────────────┐    ┌──────────────────────────────┐    │
│  │ CAP Provider │    │     Intelligence Engine      │   │
│  │  (WebSocket) │───►│                              │   │
│  └─────────────┘     │  1. Data Ingestion           │   │
│                      │     - Tavily Web Search      │   │
│                      │     - NewsAPI Business News  │   │
│                      │                              │   │
│                      │  2. Vector Processing        │   │
│                      │     - Text chunking          │   │
│                      │     - FAISS embedding        │   │
│                      │     - Cosine reranking       │   │
│                      │                              │   │
│                      │  3. LLM Synthesis            │   │
│                      │     - Groq LLaMA 3.3 70B     │   │
│                      │     - Structured JSON output │   │
│                      └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
│
▼
USDC Settlement via CAPVault '''

### A2A Composability (MarketOrchestrator)
'''User Query: "Semiconductor supply chain risk 2025"
│
▼
MarketOrchestrator Agent
│
├──► SupplyMind: "Current state and key players..."
│         └──► Risk Report 1
│
├──► SupplyMind: "Risk factors and disruption signals..."
│         └──► Risk Report 2
│
└──► SupplyMind: "Alternative suppliers and mitigation..."
└──► Risk Report 3
│
▼
Merged Intelligence Report'''

---

## API Reference

### POST /analyze

**Request:**
```json
{
  "query": "semiconductor supply chain risk Taiwan 2025",
  "depth": "standard"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | Natural language supply chain query |
| depth | string | No | "standard" (5 sources) or "deep" (10 sources) |

**Response:**
```json
{
  "risk_level": "HIGH",
  "risk_score": 7.8,
  "executive_summary": "Taiwan's semiconductor industry faces significant geopolitical risks due to its strategic position in global supply chains...",
  "disruption_signals": [
    {
      "source": "Reuters",
      "signal": "Rising US-China tensions affecting Taiwan Strait",
      "severity": "high"
    },
    {
      "source": "GDELT",
      "signal": "Increasing military exercises near Taiwan",
      "severity": "high"
    }
  ],
  "tariff_exposure": {
    "current_rate": "0%",
    "risk_scenario": "25% if export controls expand",
    "estimated_annual_impact_usd": 1250000
  },
  "alternative_suppliers": [
    {
      "name": "Samsung Foundry",
      "country": "South Korea",
      "fit_score": 8.1,
      "lead_time_weeks": 20
    },
    {
      "name": "GlobalFoundries",
      "country": "United States",
      "fit_score": 7.3,
      "lead_time_weeks": 18
    }
  ],
  "action_items": [
    "Diversify 30% of semiconductor orders to Samsung Foundry within 60 days",
    "Negotiate dual-sourcing agreement with TSMC and GlobalFoundries",
    "Increase safety stock buffer from 6 weeks to 12 weeks"
  ],
  "data_sources": ["Tavily", "NewsAPI", "GlobeNewswire"],
  "confidence_score": 0.87,
  "processing_time_ms": 14536,
  "query_hash": "6957c4cd1fd78c98de7d035f59f90822"
}
```

### GET /health
```json
{"status": "ok", "agent": "SupplyMind", "version": "1.0.0"}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Web Framework | FastAPI + uvicorn |
| CROO Integration | croo-sdk 0.2.1 |
| LLM Provider | Groq (LLaMA 3.3 70B) |
| Web Search | Tavily (advanced search + raw content) |
| News | NewsAPI (business news) |
| Vector Search | sentence-transformers + FAISS |
| Database | SQLite + SQLAlchemy (async) |
| Deployment | HuggingFace Spaces (Docker) |
| CI/CD | GitHub Actions |

---

## Project Structure

'''supplymind/
├── app/
│   ├── cap/
│   │   └── provider.py          # CROO WebSocket listener + order handler
│   ├── intelligence/
│   │   ├── data_ingestion.py    # Tavily + NewsAPI fetchers
│   │   ├── embedder.py          # FAISS embedding + reranking
│   │   ├── synthesizer.py       # Groq LLaMA synthesis
│   │   └── pipeline.py          # Main orchestration pipeline
│   ├── models/
│   │   ├── order.py             # SQLAlchemy Order model
│   │   └── cache.py             # Query cache model
│   ├── config.py                # Pydantic settings
│   ├── database.py              # Async SQLAlchemy engine
│   └── main.py                  # FastAPI app + lifespan
├── orchestrator/
│   └── orchestrator.py          # MarketOrchestrator (A2A demo)
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md'''

---

## Local Setup (10 minutes)

### Prerequisites
- Python 3.11+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/sekumohamed/Supplymind
cd Supplymind

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt


# Start the server
uvicorn app.main:app --reload --port 8000
```

### Test the pipeline

```bash
# Test the intelligence engine
python -c "
import asyncio
from app.intelligence.pipeline import run_pipeline

async def test():
    report = await run_pipeline('semiconductor supply chain risk Taiwan 2025')
    print('Risk Level:', report.get('risk_level'))
    print('Summary:', report.get('executive_summary', '')[:150])

asyncio.run(test())
"
```

### Run the A2A Orchestrator

```bash
# Terminal 1: Start SupplyMind
uvicorn app.main:app --reload --port 8000

# Terminal 2: Run Orchestrator
python -m orchestrator.orchestrator --query "AI chip market risk 2025"
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| CROO_SDK_KEY | CROO Agent SDK key | Yes |
| CROO_API_URL | CROO API endpoint | Yes |
| CROO_WS_URL | CROO WebSocket URL | Yes |
| GROQ_API_KEY | Groq LLM API key | Yes |
| TAVILY_API_KEY | Tavily search API key | Yes |
| NEWS_API_KEY | NewsAPI key | Yes |
| DATABASE_URL | SQLite connection string | Yes |
| ENVIRONMENT | development/production | No |

---

## Hackathon Tracks

- **Research & Intelligence** — paid research with verifiable sources
- **Open A2A Agents** — proves agent-to-agent composability

## Why SupplyMind Wins

1. **Real domain pain** — supply chain AI is a proven $8.67B market
2. **True A2A** — MarketOrchestrator hires SupplyMind autonomously
3. **Dual-track** — qualifies for both Research & Intelligence and Open A2A
4. **Production quality** — deployed, tested, documented
5. **Commercial viability** — $2 USDC vs $300/hr analyst — obvious ROI

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

