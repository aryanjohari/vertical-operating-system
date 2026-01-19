# backend/scrapers/universal.py
import asyncio
from playwright.async_api import async_playwright

async def scrape_website(url: str):
    data = {"url": url, "content": "", "title": "", "error": None}
    
    try:
        async with async_playwright() as p:
            # 1. Launch with flags to bypass Protocol Errors
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    '--disable-http2', 
                    '--no-sandbox', 
                    '--disable-setuid-sandbox'
                ]
            )
            
            # 2. Emulate a real Desktop Browser
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            # 3. Use 'networkidle' to ensure the protocol connection is stable
            # SSS.net.nz might have a slow handshake; 30s is fine.
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 4. Extract Data
            data["title"] = await page.title()
            
            # Extract clean text
            data["content"] = await page.evaluate("() => document.body.innerText")
            
            await browser.close()
            
    except Exception as e:
        data["error"] = str(e)
    
    data["content"] = data["content"][:15000].strip()
    return data