# backend/scrapers/maps_sync.py
import time
import random
import re
from playwright.sync_api import sync_playwright

def run_scout_sync(queries: list, allow_kws: list = None, block_kws: list = None):
    """
    YOUR ORIGINAL LOGIC (Synchronous)
    """
    try:
        # Normalize filters
        allow_kws = [k.lower() for k in (allow_kws or [])]
        block_kws = [k.lower() for k in (block_kws or [])]
        
        print(f"🕵️ SCOUT SYNC: Initializing for {len(queries)} queries...")
        
        master_data = []
        seen_ids = set()
        errors = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                for query in queries:
                    try:
                        print(f"\n   🔎 Scouting: {query}...")
                        url = f"https://www.google.co.nz/maps/search/{query.replace(' ', '+')}"
                        page.goto(url, timeout=60000)
                        
                        try: page.locator('button[aria-label="Accept all"]').first.click(timeout=3000)
                        except: pass

                        # --- LIST DETECTION ---
                        is_list = False
                        try:
                            page.wait_for_selector("div[role='feed'], h1", timeout=5000)
                            if page.locator("div[role='feed']").count() > 0:
                                is_list = True
                        except: pass

                        if is_list:
                            # 1. INFINITE SCROLL
                            print("      📜 Scrolling...")
                            last_count = 0
                            no_change_ticks = 0
                            
                            while True:
                                page.hover("div[role='feed']")
                                page.mouse.wheel(0, 5000)
                                time.sleep(1.5)
                                
                                current_count = page.locator("a[href*='/maps/place/']").count()
                                if current_count == last_count:
                                    no_change_ticks += 1
                                else:
                                    no_change_ticks = 0
                                
                                last_count = current_count
                                if no_change_ticks >= 3 or current_count > 50:
                                    break
                            
                            print(f"      📍 Found {last_count} targets.")

                            # 2. DRILL DOWN LOOP
                            for i in range(last_count):
                                try:
                                    links = page.locator("a[href*='/maps/place/']")
                                    if i >= links.count(): break
                                    target = links.nth(i)
                                    
                                    href = target.get_attribute("href")
                                    raw_name = target.get_attribute("aria-label")
                                    if not raw_name or "Search" in raw_name: continue

                                    # --- BOUNCER ---
                                    if allow_kws and not any(k in raw_name.lower() for k in allow_kws): continue
                                    if block_kws and any(k in raw_name.lower() for k in block_kws): continue
                                    
                                    # --- CLICK ---
                                    # print(f"      ⛏️  Drilling: {raw_name}...")
                                    target.click()
                                    time.sleep(2)  # Ensure phone number loads before extraction
                                    
                                    # Extract
                                    data = extract_details(page, query, raw_name, href)
                                    
                                    # Deduplicate
                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        print(f"      ✅ Captured: {raw_name} | 📞 {data['phone']}")

                                    # Back
                                    if page.locator('button[aria-label="Back"]').count() > 0:
                                        page.locator('button[aria-label="Back"]').click()
                                    else:
                                        page.goto(url); page.wait_for_selector("div[role='feed']")
                                    time.sleep(1)

                                except Exception as e:
                                    continue
                        
                        else:
                            # SINGLE RESULT
                            if page.locator("h1").count() > 0:
                                raw_name = page.locator("h1").first.inner_text()
                                
                                valid = True
                                if allow_kws and not any(k in raw_name.lower() for k in allow_kws): valid = False
                                if block_kws and any(k in raw_name.lower() for k in block_kws): valid = False
                                
                                if valid:
                                    print(f"      📍 Single Result: {raw_name}")
                                    # Wait for details to load
                                    time.sleep(2)
                                    data = extract_details(page, query, raw_name, page.url)
                                    
                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        print(f"      ✅ Captured: {raw_name} | 📞 {data.get('phone', 'N/A')}")

                    except Exception as e:
                        print(f"❌ Error on {query}: {e}")
                        continue
                    
            except Exception as main_e:
                try:
                    browser.close()
                except:
                    pass
                return {
                    "success": False,
                    "agent_name": "scout_anchors",
                    "message": str(main_e),
                    "data": None
                }
            finally:
                try:
                    browser.close()
                except:
                    pass

        return {
            "success": True,
            "agent_name": "scout_anchors",
            "message": f"Captured {len(master_data)} entities.",
            "data": master_data
        }
    except Exception as outer_e:
        # Catch any exception that happens before browser initialization
        return {
            "success": False,
            "agent_name": "scout_anchors",
            "message": f"Scraper initialization failed: {str(outer_e)}",
            "data": None
        }

def extract_details(page, source_query, name, source_url):
    data = {"name": name, "source_query": source_query, "google_maps_url": source_url, "address": None, "phone": None, "website": None}
    
    try:
        if page.locator('button[data-item-id="address"]').count() > 0:
            data["address"] = page.locator('button[data-item-id="address"]').first.get_attribute("aria-label").replace("Address: ", "").strip()
        if page.locator('button[data-item-id*="phone"]').count() > 0:
            data["phone"] = page.locator('button[data-item-id*="phone"]').first.get_attribute("aria-label").replace("Phone: ", "").strip()
        if page.locator('a[data-item-id="authority"]').count() > 0:
            data["website"] = page.locator('a[data-item-id="authority"]').first.get_attribute("href")
    except: pass
    
    return data