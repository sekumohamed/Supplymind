# app/intelligence/data_ingestion.py
import os
import asyncio
import httpx
from tavily import TavilyClient
from app.config import get_settings

settings = get_settings()


async def fetch_tavily(query: str, max_results: int = 5) -> list[dict]:
    """Fetch web search results with raw content via Tavily."""
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = await asyncio.to_thread(
            client.search,
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_raw_content=True,
        )
        results = response.get("results", [])
        print(f"[Tavily] Fetched {len(results)} results for: {query[:50]}")
        return results
    except Exception as e:
        print(f"[Tavily] Error: {e}")
        return []


async def fetch_news(query: str, max_results: int = 5) -> list[dict]:
    """Fetch business news via NewsAPI."""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "apiKey": settings.news_api_key,
            "pageSize": max_results,
            "sortBy": "publishedAt",
            "language": "en",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            articles = data.get("articles", [])
            results = [
                {
                    "title": a.get("title", ""),
                    "content": a.get("description", "") + " " + (a.get("content") or ""),
                    "url": a.get("url", ""),
                    "source": a.get("source", {}).get("name", "NewsAPI"),
                }
                for a in articles
            ]
            print(f"[NewsAPI] Fetched {len(results)} articles")
            return results
    except Exception as e:
        print(f"[NewsAPI] Error: {e}")
        return []


async def fetch_all_sources(query: str, depth: str = "standard") -> list[dict]:
    """
    Fetch from all sources in parallel.
    depth = 'standard' (5 results) | 'deep' (10 results)
    """
    max_results = 10 if depth == "deep" else 5

    tavily_results, news_results = await asyncio.gather(
        fetch_tavily(query, max_results=max_results),
        fetch_news(query, max_results=3),
    )

    all_results = []

    for r in tavily_results:
        all_results.append({
            "title": r.get("title", ""),
            "content": r.get("raw_content") or r.get("content") or "",
            "url": r.get("url", ""),
            "source": "Tavily",
        })

    for r in news_results:
        all_results.append(r)

    print(f"[DataIngestion] Total {len(all_results)} documents fetched")
    return all_results