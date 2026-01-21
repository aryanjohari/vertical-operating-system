# backend/core/services/universal.py
import asyncio
import logging
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

logger = logging.getLogger("Apex.UniversalScraper")

class UniversalScraper:
    """
    The Universal Scraper Service with Deep Scraping.
    Wraps Playwright (Async) to crawl multiple pages from a website.
    """
    
    def __init__(self, max_pages: int = 10, max_depth: int = 2):
        """
        Initialize scraper with crawling limits.
        
        Args:
            max_pages: Maximum number of pages to scrape (default: 10)
            max_depth: Maximum crawl depth from homepage (default: 2)
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.logger = logging.getLogger("Apex.UniversalScraper")
    
    async def scrape(self, url: str):
        """
        Deep scraping: Crawls multiple pages from the website.
        Returns combined content from all crawled pages.
        """
        self.logger.info(f"Starting deep scrape for URL: {url}")
        # Parse base URL
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        data = {
            "url": url, 
            "content": "", 
            "title": "", 
            "error": None,
            "pages_scraped": 0,
            "pages_visited": []
        }
        
        visited = set()
        to_visit = [(url, 0)]  # (url, depth)
        all_content = []
        homepage_title = ""
        
        try:
            async with async_playwright() as p:
                # Launch Browser
                browser = await p.chromium.launch(
                    headless=True, 
                    args=[
                        '--disable-http2', 
                        '--no-sandbox', 
                        '--disable-setuid-sandbox'
                    ]
                )
                
                # Context (User Agent Spoofing)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080}
                )
                
                # Crawl pages
                while to_visit and len(visited) < self.max_pages:
                    current_url, depth = to_visit.pop(0)
                    
                    # Skip if already visited or too deep
                    if current_url in visited or depth > self.max_depth:
                        continue
                    
                    # Skip external links
                    if not current_url.startswith(base_domain):
                        continue
                    
                    visited.add(current_url)
                    
                    try:
                        page = await context.new_page()
                        
                        # Navigate with timeout
                        try:
                            await page.goto(current_url, wait_until="networkidle", timeout=30000)
                        except Exception as nav_e:
                            # Fallback if networkidle times out
                            self.logger.debug(f"networkidle timeout for {current_url}, retrying with basic navigation: {nav_e}")
                            await page.goto(current_url, timeout=30000)
                        
                        # Extract title (use homepage title)
                        if not homepage_title:
                            homepage_title = await page.title()
                            data["title"] = homepage_title
                        
                        # Extract content
                        page_content = await page.evaluate("() => document.body.innerText")
                        if page_content:
                            all_content.append(f"\n\n=== Page: {current_url} ===\n{page_content}")
                            data["pages_visited"].append(current_url)
                        
                        # If this is the homepage (depth 0), collect internal links
                        if depth < self.max_depth:
                            links = await page.evaluate("""
                                () => {
                                    const links = Array.from(document.querySelectorAll('a[href]'));
                                    return links.map(a => a.href).filter(href => href);
                                }
                            """)
                            
                            # Add new internal links to queue
                            for link in links:
                                # Normalize URL
                                absolute_link = urljoin(current_url, link)
                                parsed_link = urlparse(absolute_link)
                                
                                # Only add same-domain links
                                if parsed_link.netloc == parsed.netloc:
                                    # Remove fragments and query params for deduplication
                                    clean_link = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
                                    if clean_link not in visited and (clean_link, depth + 1) not in to_visit:
                                        to_visit.append((clean_link, depth + 1))
                        
                        await page.close()
                        
                        # Small delay to be respectful
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        # Log but continue crawling other pages
                        self.logger.warning(f"Error scraping {current_url}: {e}", exc_info=True)
                        continue
                
                await browser.close()
                
                # Combine all content
                data["content"] = "\n".join(all_content)
                data["pages_scraped"] = len(visited)
                self.logger.info(f"Completed scraping {data['pages_scraped']} pages from {url}")
                
        except Exception as e:
            self.logger.error(f"Critical error during scraping of {url}: {e}", exc_info=True)
            data["error"] = str(e)
        
        # Truncate to save tokens, strip whitespace
        if data["content"]:
            # Limit total content to 50000 chars (up from 15000 for deep scraping)
            data["content"] = data["content"][:50000].strip()
            
        return data
    
    def log(self, message: str):
        """Logging method using proper logger."""
        self.logger.info(message)

# Standalone function for backward compatibility (optional)
async def scrape_website(url: str):
    scraper = UniversalScraper()
    return await scraper.scrape(url)