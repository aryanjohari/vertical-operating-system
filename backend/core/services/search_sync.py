# backend/core/services/search_sync.py
import requests
import json
import logging
from backend.core.config import settings

logger = logging.getLogger("Apex.Search")

def run_search_sync(query_objects: list):
    """
    Uses Serper.dev API to find Competitors and Facts reliably.
    
    Args:
        query_objects: List of {"query": str, "type": str} dicts where type is "competitor" or "fact"
    
    Returns:
        List of result dicts with {"query": str, "title": str, "link": str, "snippet": str, "type": str}
    """
    url = "https://google.serper.dev/search"
    results = []
    
    # Validate API key
    if not settings.SERPER_API_KEY or len(settings.SERPER_API_KEY.strip()) == 0:
        logger.error("❌ SERPER_API_KEY not configured. Please set SERPER_API_KEY in environment variables.")
        return results
    
    # Count queries by type
    competitor_count = sum(1 for q in query_objects if isinstance(q, dict) and q.get("type") == "competitor")
    fact_count = len(query_objects) - competitor_count
    
    # Enhanced logging
    logger.info(f"Using API Key: {settings.SERPER_API_KEY[:4]}...")
    logger.info(f"Input: {len(query_objects)} queries ({competitor_count} competitors, {fact_count} facts)")
    
    headers = {
        'X-API-KEY': settings.SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    for idx, query_obj in enumerate(query_objects, 1):
        try:
            # Handle both old format (string) and new format (dict) for backward compatibility
            if isinstance(query_obj, dict):
                query = query_obj.get("query", "")
                query_type = query_obj.get("type", "fact")  # Default to fact if not specified
            else:
                # Legacy format: just a string
                query = str(query_obj)
                query_type = "fact"  # Default for legacy queries
                logger.warning(f"⚠️ Received legacy string query format, defaulting to 'fact' type")
            
            if not query:
                logger.warning(f"⚠️ Skipping empty query at index {idx}")
                continue
            
            logger.info(f"🔍 [{idx}/{len(query_objects)}] Processing query: {query[:60]}... (type: {query_type})")
            payload = json.dumps({"q": query, "num": 5, "gl": "nz"}) # gl=nz for New Zealand
            logger.debug(f"📤 Sending request to Serper API with payload: {payload}")
            
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            
            # Log raw API response status code
            logger.info(f"📡 API Response Status: {response.status_code} for query '{query[:50]}...'")
            
            if response.status_code == 200:
                data = response.json()
                organic = data.get("organic", [])
                logger.info(f"✅ Query '{query[:50]}...' returned {len(organic)} organic results")
                
                for item in organic:
                    result_item = {
                        "query": query,
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "snippet": item.get("snippet"),
                        "type": query_type  # Use preserved type from query object, not keyword guessing
                    }
                    results.append(result_item)
                    logger.debug(f"  ➕ Added: {result_item.get('title', 'No title')[:50]} (type: {query_type})")
            else:
                logger.error(f"❌ API Error {response.status_code} for query '{query}': {response.text[:200]}")
                
        except Exception as e:
            query_str = query_obj.get("query", str(query_obj)) if isinstance(query_obj, dict) else str(query_obj)
            logger.error(f"❌ Search Failed for query '{query_str}': {e}", exc_info=True)

    logger.info(f"📊 SEARCH SYNC COMPLETE: Processed {len(query_objects)} queries, collected {len(results)} total results")
    return results