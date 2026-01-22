# backend/modules/lead_gen/agents/sniper.py
import json
import logging
import urllib.parse
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway
from backend.core.services.universal import UniversalScraper
from backend.core.models import Entity

class SniperAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SniperAgent")
        self.logger = logging.getLogger("Apex.Sniper")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Input params:
          - mode: "aggressive" (optional)
        """
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # 1. Use injected config (loaded by kernel)
        config = self.config
        lead_gen_config = config.get('modules', {}).get('lead_gen', {})
        sniper_config = lead_gen_config.get('sniper', {})
        
        if not sniper_config.get('enabled', False):
            return AgentOutput(status="skipped", message="Sniper is disabled in Project DNA.")

        keywords = sniper_config.get('keywords', [])
        geo_filter = sniper_config.get('geo_filter', ["Auckland"])
        platforms = sniper_config.get('platforms', ["trademe_jobs"])

        self.logger.info(f"🔫 Sniper starting hunt for {project_id}. Keywords: {keywords}")
        
        total_leads_found = 0

        # 2. The Hunt Loop
        for platform in platforms:
            for keyword in keywords:
                try:
                    # A. Construct Search URL
                    search_url = self._get_search_url(platform, keyword, geo_filter)
                    if not search_url:
                        continue

                    # B. Scrape the Listing Page
                    self.logger.info(f"👀 Scanning {platform}: {keyword}")
                    scraper = UniversalScraper()
                    scrape_result = await scraper.scrape(search_url)
                    
                    if scrape_result.get("error"):
                        self.logger.warning(f"⚠️ Scrape failed for {search_url}")
                        continue

                    # C. The Brain: Extract Leads from HTML
                    # We pass the raw HTML text to Gemini to parse out the jobs
                    leads_data = self._extract_leads_with_ai(scrape_result['content'], geo_filter)
                    
                    # D. Save Leads to DB
                    saved_count = self._save_leads(leads_data, user_id, project_id, platform, keyword)
                    total_leads_found += saved_count
                    
                except Exception as e:
                    self.logger.error(f"❌ Sniper Error on {keyword}: {e}", exc_info=True)
                    continue

        return AgentOutput(
            status="success", 
            message=f"Hunt complete. Found {total_leads_found} new leads.", 
            data={"count": total_leads_found}
        )

    def _get_search_url(self, platform, keyword, geo_filter):
        """
        Maps platform names to real search URLs.
        """
        q = urllib.parse.quote(keyword)
        
        # TradeMe Jobs (Service/Trades)
        if platform == "trademe_jobs":
            # This is a generic TradeMe search URL structure
            return f"https://www.trademe.co.nz/a/jobs/search?search_string={q}"
        
        # Add other platforms (e.g. Neighborly) here
        return None

    def _extract_leads_with_ai(self, html_content, geo_filter):
        """
        Uses LLM Gateway to parse dirty HTML into clean JSON leads.
        """
        prompt = f"""
        You are a Lead Scraper. Analyze this raw text from a job/service listing site.
        
        Task: Extract valid job leads where someone is looking for a service.
        Context: We are looking for leads in: {', '.join(geo_filter)}.
        Ignore listings that are clearly outside this region.
        
        Return a JSON list of objects:
        [{{
            "title": "Need a plumber",
            "url": "full_link_to_post",
            "location": "City/Suburb",
            "description": "Brief summary",
            "urgency": "High/Medium/Low"
        }}]
        
        If no leads found, return [].
        
        RAW CONTENT:
        {html_content[:15000]}  # Limit content to avoid token limits
        """
        
        try:
            # Use LLM Gateway with proper API
            response_text = llm_gateway.generate_content(
                system_prompt="You are a Lead Scraper. Extract job leads from HTML content and return valid JSON only.",
                user_prompt=prompt,
                model="gemini-2.5-flash",  # Use cheap model for scraping
                temperature=0.3
            )
            
            # Clean formatting (remove markdown ```json ... ```)
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            self.logger.warning(f"⚠️ AI Parse Failed: {e}")
            return []

    def _save_leads(self, leads_data, user_id, project_id, platform, keyword):
        count = 0
        
        # Query existing leads for deduplication
        # Fetch existing leads to check for duplicates
        existing_leads = memory.get_entities(
            tenant_id=user_id,
            entity_type="lead",
            project_id=project_id,
            limit=1000
        )
        
        if len(existing_leads) >= 1000:
            self.logger.warning(f"⚠️ Approaching lead limit (1000). Consider pagination optimization.")
        
        # Create set of existing URLs for fast lookup
        existing_urls = {lead.get('primary_contact', '') for lead in existing_leads}
        
        for item in leads_data:
            lead_url = item.get('url', '')
            
            # Deduplication: Check if URL already exists
            if lead_url in existing_urls:
                self.logger.info(f"🔄 Duplicate ignored: {lead_url}")
                continue
            
            lead_entity = Entity(
                tenant_id=user_id,
                entity_type="lead",
                name=item.get('title', 'Unknown Lead'),
                primary_contact=lead_url, # For Sniper, the 'contact' is the URL to reply to
                metadata={
                    "source": "sniper",
                    "platform": platform,
                    "keyword": keyword,
                    "location": item.get('location'),
                    "urgency": item.get('urgency'),
                    "description": item.get('description'),
                    "status": "new",
                    "project_id": project_id
                },
                created_at=datetime.now()
            )
            
            if memory.save_entity(lead_entity, project_id=project_id):
                count += 1
                # Add to set to prevent duplicates within this batch
                existing_urls.add(lead_url)
                
        return count