# app/intelligence/data_ingestion.py
import asyncio
import httpx
from tavily import TavilyClient
from app.config import get_settings
from app.utils.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

TAVILY_TIMEOUT_SECONDS = 15
NEWS_TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5


async def fetch_tavily(query: str, max_results: int = 5) -> list[dict]:
    client = TavilyClient(api_key=settings.tavily_api_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.search,
                    query=query,
                    search_depth="advanced",
                    max_results=max_results,
                    include_raw_content=True,
                ),
                timeout=TAVILY_TIMEOUT_SECONDS,
            )
            results = response.get("results", [])
            logger.info(f"[Tavily] Fetched {len(results)} results for: {query[:50]}")
            return results

        except asyncio.TimeoutError:
            logger.warning(f"[Tavily] Timeout after {TAVILY_TIMEOUT_SECONDS}s (attempt {attempt}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"[Tavily] Error (attempt {attempt}/{MAX_RETRIES}): {e}", exc_info=True)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    logger.warning("[Tavily] All retries exhausted — degrading to no results")
    return []


async def fetch_news(query: str, max_results: int = 5) -> list[dict]:
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "apiKey": settings.news_api_key,
        "pageSize": max_results,
        "sortBy": "publishedAt",
        "language": "en",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=NEWS_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
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
            logger.info(f"[NewsAPI] Fetched {len(results)} articles")
            return results

        except httpx.TimeoutException:
            logger.warning(f"[NewsAPI] Timeout after {NEWS_TIMEOUT_SECONDS}s (attempt {attempt}/{MAX_RETRIES})")
        except httpx.HTTPStatusError as e:
            logger.warning(f"[NewsAPI] HTTP error {e.response.status_code} (attempt {attempt}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"[NewsAPI] Error (attempt {attempt}/{MAX_RETRIES}): {e}", exc_info=True)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    logger.warning("[NewsAPI] All retries exhausted — degrading to no results")
    return []


async def fetch_all_sources(query: str, depth: str = "standard") -> list[dict]:
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

    logger.info(f"[DataIngestion] Total {len(all_results)} documents fetched")
    return all_results