import os
import re
import requests
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class MediaAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Media")
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. FETCH DRAFTS
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft")
        # Filter: Drafts that need images
        targets = [p for p in pages if p['metadata'].get('status') == 'draft' and 'image_url' not in p['metadata']]
        
        if not targets:
            return AgentOutput(status="complete", message="No pages need images.")
            
        batch = targets[:5]
        self.logger.info(f"🖼️ Finding images for {len(batch)} pages...")

        success_count = 0

        for page in batch:
            try:
                # 2. CONSTRUCT SMART QUERY
                # Step A: Get the raw city (e.g., "Auckland 1010")
                raw_city = page['metadata'].get('city', 'Auckland')
                
                # Step B: "The Zip Code Killer" - Remove all numbers
                # "Auckland 1010" -> "Auckland"
                clean_city = re.sub(r'\d+', '', raw_city).strip()
                
                # Step C: The "Universal Vibe" Query
                # We use "City Architecture" because it works for Lawyers, Plumbers, and Cafes.
                # It guarantees a professional result (no "zero results" errors).
                query = f"{clean_city} city architecture"
                
                self.logger.info(f"Searching Unsplash for: '{query}'")

                # 3. SEARCH UNSPLASH
                img_url = ""
                credit = ""
                
                # Generic City Fallback Image (in case of API failure)
                fallback_img = "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b"
                
                if not self.unsplash_key:
                    self.logger.warning("No Unsplash Key found. Using fallback placeholder.")
                    img_url = fallback_img
                    credit = "Unsplash"
                else:
                    # Real API Call
                    url = f"https://api.unsplash.com/search/photos?query={query}&per_page=1&orientation=landscape&client_id={self.unsplash_key}"
                    res = requests.get(url)
                    
                    if res.status_code == 200:
                        data = res.json()
                        if data['results']:
                            img_url = data['results'][0]['urls']['regular']
                            credit = f"Photo by {data['results'][0]['user']['name']} on Unsplash"
                            self.logger.info(f"✅ Found image for {page['name']}")
                        else:
                            self.logger.warning(f"⚠️ Zero results for '{query}'. Using fallback.")
                            img_url = fallback_img
                            credit = "Unsplash"
                    else:
                        self.logger.error(f"❌ Unsplash API Error: {res.status_code} - {res.text}")
                        img_url = fallback_img
                        credit = "Unsplash"

                # 4. UPDATE PAGE ENTITY
                # Create the HTML for the image
                img_html = f'''
                <div class="featured-image" style="margin-bottom: 2rem;">
                    <img src="{img_url}" alt="{clean_city} Cityscape" style="width:100%; height: auto; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <small style="color: #666; font-size: 0.8rem;">{credit}</small>
                </div>
                '''
                
                # Update Metadata
                new_meta = page['metadata'].copy()
                new_meta['image_url'] = img_url
                new_meta['content'] = img_html + "\n" + new_meta['content'] # Prepend image
                
                if memory.update_entity(page['id'], new_meta):
                    success_count += 1
                
            except Exception as e:
                self.logger.error(f"❌ Media Agent Critical Fail on '{page['name']}': {e}", exc_info=True)
                continue

        return AgentOutput(
            status="success", 
            message=f"Enhanced {success_count} pages with visuals.",
            data={"count": success_count}
        )