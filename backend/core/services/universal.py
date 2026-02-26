# backend/core/services/universal.py
import asyncio
import logging
from urllib.parse import urljoin, urlparse

import httpx
from backend.core.config import settings

logger = logging.getLogger("Apex.UniversalScraper")

JINA_READER_BASE = "https://r.jina.ai/"


class UniversalScraper:
    """
    Universal Scraper Service using Jina Reader API (r.jina.ai).
    Fetches multiple pages via HTTP and returns combined content (no browser).
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
        Deep scraping: Fetches multiple pages from the website via Jina Reader API.
        Returns combined content from all fetched pages.
        """
        self.logger.info(f"Starting deep scrape for URL: {url}")
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        data = {
            "url": url,
            "content": "",
            "title": "",
            "error": None,
            "pages_scraped": 0,
            "pages_visited": [],
        }

        headers = {}
        if settings.JINJA_API_KEY and settings.JINJA_API_KEY.strip():
            headers["Authorization"] = f"Bearer {settings.JINJA_API_KEY.strip()}"

        priority_paths = [
            "",
            "/about",
            "/about-us",
            "/services",
            "/service",
            "/practice-areas",
            "/our-services",
            "/contact",
        ]

        to_visit = []
        seen_candidates = set()
        for path in priority_paths:
            candidate = urljoin(base_domain, path)
            if candidate not in seen_candidates:
                to_visit.append((candidate, 0))
                seen_candidates.add(candidate)

        visited = set()
        all_content = []
        homepage_title = ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while to_visit and len(visited) < self.max_pages:
                    current_url, depth = to_visit.pop(0)

                    if current_url in visited or depth > self.max_depth:
                        continue
                    if not current_url.startswith(base_domain):
                        continue

                    visited.add(current_url)

                    try:
                        reader_url = f"{JINA_READER_BASE}{current_url}"
                        response = await client.get(reader_url, headers=headers or None)

                        if response.status_code != 200:
                            self.logger.warning(f"Jina Reader {response.status_code} for {current_url}")
                            continue

                        page_content = response.text
                        if not homepage_title and page_content:
                            for line in page_content.splitlines():
                                line = line.strip()
                                if line.startswith("# "):
                                    homepage_title = line.lstrip("# ").strip()[:200]
                                    data["title"] = homepage_title
                                    break
                            if not homepage_title:
                                data["title"] = parsed.netloc or url

                        if page_content:
                            all_content.append(f"\n\n=== Page: {current_url} ===\n{page_content}")
                            data["pages_visited"].append(current_url)

                        await asyncio.sleep(0.3)
                    except Exception as e:
                        self.logger.warning(f"Error fetching {current_url}: {e}", exc_info=True)
                        continue

                data["content"] = "\n".join(all_content)
                data["pages_scraped"] = len(visited)
                self.logger.info(f"Completed scraping {data['pages_scraped']} pages from {url}")

        except Exception as e:
            self.logger.error(f"Critical error during scraping of {url}: {e}", exc_info=True)
            data["error"] = str(e)

        if data["content"]:
            data["content"] = data["content"][:50000].strip()

        return data

    def log(self, message: str):
        """Logging method using proper logger."""
        self.logger.info(message)


async def scrape_website(url: str):
    """Standalone function for backward compatibility."""
    scraper = UniversalScraper()
    return await scraper.scrape(url)
