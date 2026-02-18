# backend/core/services/search_sync.py
import json
import logging
from typing import List

import httpx
from backend.core.config import settings

logger = logging.getLogger("Apex.Search")

URL = "https://google.serper.dev/search"


async def run_search_async(query_objects: list) -> List[dict]:
    """
    Async Serper.dev API. Same return shape as run_search_sync.
    List of {"query", "title", "link", "snippet", "type"} dicts.
    """
    results = []
    if not settings.SERPER_API_KEY or len(settings.SERPER_API_KEY.strip()) == 0:
        logger.error("SERPER_API_KEY not configured.")
        return results

    competitor_count = sum(
        1 for q in query_objects if isinstance(q, dict) and q.get("type") == "competitor"
    )
    fact_count = len(query_objects) - competitor_count
    logger.info(f"Input: {len(query_objects)} queries ({competitor_count} competitors, {fact_count} facts)")

    headers = {
        "X-API-KEY": settings.SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, query_obj in enumerate(query_objects, 1):
            try:
                if isinstance(query_obj, dict):
                    query = query_obj.get("query", "")
                    query_type = query_obj.get("type", "fact")
                else:
                    query = str(query_obj)
                    query_type = "fact"
                    logger.warning("Legacy string query format, defaulting to 'fact'")

                if not query:
                    logger.warning(f"Skipping empty query at index {idx}")
                    continue

                logger.info(f"[{idx}/{len(query_objects)}] Processing query: {query[:60]}... (type: {query_type})")
                payload = {"q": query, "num": 5, "gl": "nz"}

                response = await client.post(URL, headers=headers, json=payload)
                logger.info(f"API Response Status: {response.status_code} for query '{query[:50]}...'")

                if response.status_code == 200:
                    data = response.json()
                    organic = data.get("organic", [])
                    logger.info(f"Query '{query[:50]}...' returned {len(organic)} organic results")
                    for item in organic:
                        result_item = {
                            "query": query,
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "snippet": item.get("snippet"),
                            "type": query_type,
                        }
                        results.append(result_item)
                        logger.debug(f"  Added: {result_item.get('title', 'No title')[:50]} (type: {query_type})")
                else:
                    logger.error(f"API Error {response.status_code} for query '{query}': {response.text[:200]}")
            except Exception as e:
                query_str = query_obj.get("query", str(query_obj)) if isinstance(query_obj, dict) else str(query_obj)
                logger.error(f"Search failed for query '{query_str}': {e}", exc_info=True)

    logger.info(f"SEARCH ASYNC COMPLETE: {len(query_objects)} queries, {len(results)} results")
    return results


def run_search_sync(query_objects: list) -> List[dict]:
    """
    Sync wrapper for callers that need blocking API.
    Uses anyio.run to drive run_search_async from sync context.
    """
    try:
        import anyio
        return anyio.run(run_search_async, query_objects)
    except ImportError:
        import asyncio
        return asyncio.run(run_search_async(query_objects))
