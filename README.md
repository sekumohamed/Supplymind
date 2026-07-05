---
title: SupplyMind
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# SupplyMind — Real-Time Supply Chain Intelligence Agent

A2A-callable AI agent on CROO. Submit a supply chain query, get risk scores, disruption signals, tariff exposure, and alternative suppliers.

## API Endpoints
- `GET /health` — Health check
- `POST /analyze` — Run supply chain intelligence analysis

## Usage
```json
{
  "query": "semiconductor supply chain risk Taiwan 2025",
  "depth": "standard"
}
```
