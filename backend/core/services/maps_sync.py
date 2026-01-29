# backend/core/services/maps_sync.py
import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright

logger = logging.getLogger("Apex.Scout")


async def run_scout_async(
    queries: list,
    allow_kws: Optional[List[str]] = None,
    block_kws: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Async Maps scout using playwright.async_api.
    Same return shape: {"success", "agent_name", "message", "data"}.
    """
    from playwright.async_api import async_playwright

    allow_kws = [k.lower() for k in (allow_kws or [])]
    block_kws = [k.lower() for k in (block_kws or [])]
    logger.info(f"SCOUT ASYNC: Initializing for {len(queries)} queries...")
    master_data = []
    seen_ids = set()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            try:
                for query in queries:
                    try:
                        logger.info(f"Scouting: {query}...")
                        url = f"https://www.google.co.nz/maps/search/{query.replace(' ', '+')}"
                        await page.goto(url, timeout=60000)
                        try:
                            await page.locator('button[aria-label="Accept all"]').first.click(timeout=3000)
                        except Exception as e:
                            logger.debug(f"Could not click accept button for {query}: {e}")

                        is_list = False
                        try:
                            await page.wait_for_selector("div[role='feed'], h1", timeout=5000)
                            if await page.locator("div[role='feed']").count() > 0:
                                is_list = True
                        except Exception as e:
                            logger.debug(f"Could not detect list for {query}: {e}")

                        if is_list:
                            logger.debug(f"Scrolling for query: {query}")
                            last_count = 0
                            no_change_ticks = 0
                            while True:
                                await page.hover("div[role='feed']")
                                await page.mouse.wheel(0, 5000)
                                await asyncio.sleep(1.5)
                                current_count = await page.locator("a[href*='/maps/place/']").count()
                                if current_count == last_count:
                                    no_change_ticks += 1
                                else:
                                    no_change_ticks = 0
                                last_count = current_count
                                if no_change_ticks >= 3 or current_count > 50:
                                    break
                            logger.info(f"Found {last_count} targets for query: {query}")

                            for i in range(last_count):
                                try:
                                    links = page.locator("a[href*='/maps/place/']")
                                    link_count = await links.count()
                                    if i >= link_count:
                                        break
                                    target = links.nth(i)
                                    href = await target.get_attribute("href")
                                    raw_name = await target.get_attribute("aria-label")
                                    if not raw_name or "Search" in raw_name:
                                        continue
                                    if allow_kws and not any(k in raw_name.lower() for k in allow_kws):
                                        continue
                                    if block_kws and any(k in raw_name.lower() for k in block_kws):
                                        continue
                                    await target.click()
                                    await asyncio.sleep(2)
                                    data = await extract_details_async(page, query, raw_name, href)
                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        logger.info(f"Captured: {raw_name} | Phone: {data['phone']}")
                                    if await page.locator('button[aria-label="Back"]').count() > 0:
                                        await page.locator('button[aria-label="Back"]').click()
                                    else:
                                        await page.goto(url)
                                        await page.wait_for_selector("div[role='feed']")
                                    await asyncio.sleep(1)
                                except Exception as e:
                                    logger.warning(f"Error processing item {i} for query {query}: {e}")
                                    continue
                        else:
                            if await page.locator("h1").count() > 0:
                                raw_name = await page.locator("h1").first.inner_text()
                                valid = True
                                if allow_kws and not any(k in raw_name.lower() for k in allow_kws):
                                    valid = False
                                if block_kws and any(k in raw_name.lower() for k in block_kws):
                                    valid = False
                                if valid:
                                    logger.info(f"Single Result: {raw_name}")
                                    await asyncio.sleep(2)
                                    data = await extract_details_async(page, query, raw_name, page.url)
                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        logger.info(f"Captured: {raw_name} | Phone: {data.get('phone', 'N/A')}")
                    except Exception as e:
                        logger.error(f"Error processing query {query}: {e}", exc_info=True)
                        continue
            finally:
                await browser.close()
                logger.debug("Browser closed successfully")

        return {
            "success": True,
            "agent_name": "scout_anchors",
            "message": f"Captured {len(master_data)} entities.",
            "data": master_data,
        }
    except Exception as outer_e:
        logger.error(f"Scraper initialization failed: {outer_e}", exc_info=True)
        return {
            "success": False,
            "agent_name": "scout_anchors",
            "message": f"Scraper initialization failed: {str(outer_e)}",
            "data": None,
        }


async def extract_details_async(page, source_query: str, name: str, source_url: str) -> Dict[str, Any]:
    """Async extraction for use with playwright async_api page."""
    data = {
        "name": name,
        "source_query": source_query,
        "google_maps_url": source_url,
        "address": None,
        "phone": None,
        "website": None,
        "working_hours": None,
    }
    try:
        if await page.locator('button[data-item-id="address"]').count() > 0:
            addr = await page.locator('button[data-item-id="address"]').first.get_attribute("aria-label")
            if addr:
                data["address"] = addr.replace("Address: ", "").strip()
        if await page.locator('button[data-item-id*="phone"]').count() > 0:
            ph = await page.locator('button[data-item-id*="phone"]').first.get_attribute("aria-label")
            if ph:
                data["phone"] = ph.replace("Phone: ", "").strip()
        if await page.locator('a[data-item-id="authority"]').count() > 0:
            data["website"] = await page.locator('a[data-item-id="authority"]').first.get_attribute("href")
        try:
            if await page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').count() > 0:
                hours_button = page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').first
                working_hours_text = await hours_button.get_attribute("aria-label")
                if working_hours_text:
                    data["working_hours"] = working_hours_text.replace("Hours: ", "").replace("Opening hours: ", "").strip()
            if not data.get("working_hours"):
                for selector in ['div[data-value*="hours"]', 'div:has-text("Open")', 'span:has-text("AM")']:
                    if await page.locator(selector).count() > 0:
                        working_hours_text = await page.locator(selector).first.inner_text()
                        if working_hours_text and len(working_hours_text) < 200:
                            data["working_hours"] = working_hours_text
                            break
        except Exception as hours_e:
            logger.debug(f"Could not extract working hours for {name}: {hours_e}")
    except Exception as e:
        logger.debug(f"Error extracting details for {name}: {e}")
    return data


# --- Synchronous API (backward compatibility) ---
import time


def run_scout_sync(
    queries: list,
    allow_kws: Optional[List[str]] = None,
    block_kws: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Sync wrapper: runs run_scout_async via anyio.run or asyncio.run."""
    try:
        import anyio
        return anyio.run(run_scout_async, queries, allow_kws, block_kws)
    except ImportError:
        return asyncio.run(run_scout_async(queries, allow_kws, block_kws))


def extract_details(page, source_query: str, name: str, source_url: str) -> Dict[str, Any]:
    """Sync extraction for sync_playwright page (backward compatibility)."""
    data = {"name": name, "source_query": source_query, "google_maps_url": source_url, "address": None, "phone": None, "website": None, "working_hours": None}
    try:
        if page.locator('button[data-item-id="address"]').count() > 0:
            data["address"] = page.locator('button[data-item-id="address"]').first.get_attribute("aria-label").replace("Address: ", "").strip()
        if page.locator('button[data-item-id*="phone"]').count() > 0:
            data["phone"] = page.locator('button[data-item-id*="phone"]').first.get_attribute("aria-label").replace("Phone: ", "").strip()
        if page.locator('a[data-item-id="authority"]').count() > 0:
            data["website"] = page.locator('a[data-item-id="authority"]').first.get_attribute("href")
        try:
            if page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').count() > 0:
                hours_button = page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').first
                working_hours_text = hours_button.get_attribute("aria-label")
                if working_hours_text:
                    data["working_hours"] = working_hours_text.replace("Hours: ", "").replace("Opening hours: ", "").strip()
            if not data.get("working_hours"):
                for selector in ['div[data-value*="hours"]', 'div:has-text("Open")', 'span:has-text("AM")']:
                    if page.locator(selector).count() > 0:
                        working_hours_text = page.locator(selector).first.inner_text()
                        if working_hours_text and len(working_hours_text) < 200:
                            data["working_hours"] = working_hours_text
                            break
        except Exception as hours_e:
            logger.debug(f"Could not extract working hours for {name}: {hours_e}")
    except Exception as e:
        logger.debug(f"Error extracting details for {name}: {e}")
    return data
