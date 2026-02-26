# backend/core/services/maps_sync.py
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from backend.core.config import settings

logger = logging.getLogger("Apex.Scout")

PLACES_URL = "https://google.serper.dev/places"


def _map_place_to_item(place: Dict[str, Any], source_query: str) -> Dict[str, Any]:
    """Map a Serper place object to our standard shape: name, address, phoneNumber, website (+ optional fields for scout)."""
    name = place.get("title") or place.get("name") or ""
    address = place.get("address")
    phone = place.get("phone")
    website = place.get("link") or place.get("website") or place.get("url")
    hours = place.get("hours")
    # Serper may return a maps link or place_id link
    google_maps_url = place.get("link") or place.get("place_id")
    if google_maps_url and not google_maps_url.startswith("http"):
        google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{google_maps_url}" if place.get("place_id") else None

    return {
        "name": name,
        "address": address,
        "phoneNumber": phone,
        "website": website,
        "phone": phone,
        "source_query": source_query,
        "google_maps_url": google_maps_url,
        "working_hours": hours,
    }


def _filter_by_keywords(item: Dict[str, Any], allow_kws: List[str], block_kws: List[str]) -> bool:
    """Return True if item passes allow/block keyword filters (by name)."""
    name = (item.get("name") or "").lower()
    if allow_kws and not any(k in name for k in allow_kws):
        return False
    if block_kws and any(k in name for k in block_kws):
        return False
    return True


async def run_scout_async(
    queries: list,
    allow_kws: Optional[List[str]] = None,
    block_kws: Optional[List[str]] = None,
    geo_suffix: str = "New Zealand",
) -> Dict[str, Any]:
    """
    Async Maps scout using Serper Places API (httpx).
    Same return shape: {"success", "agent_name", "message", "data"}.
    Appends ", {geo_suffix}" to each query for geolocation (from profile identity.geo_target.city).
    """
    allow_kws = [k.lower() for k in (allow_kws or [])]
    block_kws = [k.lower() for k in (block_kws or [])]

    if not settings.SERPER_API_KEY or not settings.SERPER_API_KEY.strip():
        logger.error("SERPER_API_KEY not configured.")
        return {
            "success": False,
            "agent_name": "scout_anchors",
            "message": "SERPER_API_KEY not configured",
            "data": None,
        }

    logger.info(f"SCOUT ASYNC: Initializing for {len(queries)} queries (geo_suffix={geo_suffix})...")
    master_data: List[Dict[str, Any]] = []
    seen_ids: set = set()

    headers = {
        "X-API-KEY": settings.SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for idx, query in enumerate(queries, 1):
                try:
                    query_str = str(query).strip() if not isinstance(query, dict) else (query.get("query") or query.get("q") or "").strip()
                    if not query_str:
                        logger.warning(f"Skipping empty query at index {idx}")
                        continue

                    query_with_geo = f"{query_str}, {geo_suffix}"
                    logger.info(f"Scouting [{idx}/{len(queries)}]: {query_with_geo}...")

                    payload = {"q": query_with_geo, "gl": "nz"}
                    response = await client.post(PLACES_URL, headers=headers, json=payload)

                    if response.status_code != 200:
                        logger.error(f"Places API error {response.status_code} for '{query_str}': {response.text[:200]}")
                        continue

                    data = response.json()
                    # Serper may return "places" or "place_results" (single object with list inside)
                    places = data.get("places") or data.get("place_results")
                    if isinstance(places, dict):
                        places = places.get("places", places.get("results", []) if isinstance(places.get("results"), list) else [])
                    if not isinstance(places, list):
                        places = []

                    logger.info(f"Query '{query_str}' returned {len(places)} places")

                    for place in places:
                        if not isinstance(place, dict):
                            continue
                        item = _map_place_to_item(place, source_query=query_str)
                        if not item.get("name") or (item.get("name") or "").strip() == "":
                            continue
                        if not _filter_by_keywords(item, allow_kws, block_kws):
                            continue
                        unique_id = f"{item['name']}-{(item.get('address') or '')[:10]}"
                        if unique_id in seen_ids:
                            continue
                        seen_ids.add(unique_id)
                        master_data.append(item)
                        logger.info(f"Captured: {item['name']} | Phone: {item.get('phone') or item.get('phoneNumber') or 'N/A'}")

                except Exception as e:
                    logger.error(f"Error processing query {query}: {e}", exc_info=True)
                    continue

        return {
            "success": True,
            "agent_name": "scout_anchors",
            "message": f"Captured {len(master_data)} entities.",
            "data": master_data,
        }
    except Exception as outer_e:
        logger.error(f"Scout failed: {outer_e}", exc_info=True)
        return {
            "success": False,
            "agent_name": "scout_anchors",
            "message": f"Scout failed: {str(outer_e)}",
            "data": None,
        }


def run_scout_sync(
    queries: list,
    allow_kws: Optional[List[str]] = None,
    block_kws: Optional[List[str]] = None,
    geo_suffix: str = "New Zealand",
) -> Dict[str, Any]:
    """Sync wrapper: runs run_scout_async via anyio.run or asyncio.run."""
    try:
        import anyio
        return anyio.run(run_scout_async, queries, allow_kws, block_kws, geo_suffix)
    except ImportError:
        return asyncio.run(run_scout_async(queries, allow_kws, block_kws, geo_suffix))
