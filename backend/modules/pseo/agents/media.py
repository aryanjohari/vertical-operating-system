# backend/modules/pseo/agents/media.py
import os
import re
import requests
import html
from urllib.parse import urlparse
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class MediaAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Media")
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # 1. FETCH TARGETS (Pipeline Scoped)
        # Input: Librarian sets status to 'ready_for_media'
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        targets = [p for p in pages if p['metadata'].get('status') == 'ready_for_media']
        
        if not targets:
            return AgentOutput(status="complete", message="No pages need images.")
            
        batch = targets[:5] # Process in small batches
        self.logger.info(f"🖼️ Finding images for {len(batch)} pages...")

        success_count = 0

        for page in batch:
            try:
                # 2. CONSTRUCT SMART QUERY
                raw_city = page['metadata'].get('city', 'Auckland')
                # "The Zip Code Killer" - Remove numbers: "Auckland 1010" -> "Auckland"
                clean_city = re.sub(r'\d+', '', raw_city).strip()
                
                # "Universal Vibe" Query: guarantees professional results
                query = f"{clean_city} city architecture"
                
                # 3. SEARCH UNSPLASH
                img_url = ""
                credit = ""
                fallback_img = "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b"
                
                if not self.unsplash_key:
                    img_url = fallback_img
                    credit = "Unsplash"
                else:
                    try:
                        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=1&orientation=landscape&client_id={self.unsplash_key}"
                        res = requests.get(url, timeout=5)
                        
                        if res.status_code == 200:
                            data = res.json()
                            if data['results']:
                                img_url = data['results'][0]['urls']['regular']
                                credit = f"Photo by {data['results'][0]['user']['name']} on Unsplash"
                            else:
                                img_url = fallback_img
                                credit = "Unsplash"
                        else:
                            img_url = fallback_img
                            credit = "Unsplash"
                    except:
                        img_url = fallback_img
                        credit = "Unsplash"

                # 3.5 VALIDATE URL (security: prevent XSS)
                def validate_url(url: str) -> bool:
                    try:
                        result = urlparse(url)
                        return result.scheme in ['http', 'https'] and result.netloc
                    except:
                        return False
                
                if not validate_url(img_url):
                    img_url = fallback_img
                
                # 4. INJECT HTML (with sanitization)
                clean_city_escaped = html.escape(clean_city)
                img_url_escaped = html.escape(img_url)
                credit_escaped = html.escape(credit)
                
                img_html = f'''
                <div class="featured-image" style="margin-bottom: 2rem;">
                    <img src="{img_url_escaped}" alt="{clean_city_escaped} Cityscape" style="width:100%; height: auto; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <small style="color: #666; font-size: 0.8rem;">{credit_escaped}</small>
                </div>
                '''
                
                # 5. UPDATE ENTITY & ADVANCE PIPELINE
                new_meta = page['metadata'].copy()
                new_meta['image_url'] = img_url
                # Prepend image to content
                new_meta['content'] = img_html + "\n" + new_meta['content']
                
                # CRITICAL: Advance status to next agent (Utility)
                new_meta['status'] = 'ready_for_utility'
                
                if memory.update_entity(page['id'], new_meta):
                    success_count += 1
                
            except Exception as e:
                self.logger.error(f"❌ Media Agent Critical Fail on '{page['name']}': {e}")
                continue

        return AgentOutput(
            status="success", 
            message=f"Enhanced {success_count} pages with visuals.",
            data={"count": success_count}
        )