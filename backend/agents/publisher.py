import requests
import base64
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class PublisherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Publisher")
        # Default target is WordPress (can be changed per client in future)
        self.target = "wordpress"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # Get WordPress credentials from database
        secrets = memory.get_client_secrets(user_id)
        if not secrets:
            return AgentOutput(status="error", message="No WordPress credentials found for this client.")
        
        # Get ready pages (have image + tool)
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft")
        ready_pages = [p for p in pages if p['metadata'].get('has_tool') == True
        and p['metadata'].get('status') not in ['published', 'live'] ]
        
        if not ready_pages:
             return AgentOutput(status="complete", message="No pages ready for publishing.")

        print(f"🚀 Publishing {len(ready_pages)} pages to {self.target.upper()}...")
        
        published_count = 0
        for page in ready_pages:
            success = False
            
            if self.target == "wordpress":
                success = self.publish_to_wordpress(page, secrets['wp_url'], secrets['wp_user'], secrets['wp_password'])
            elif self.target == "vercel":
                success = self.publish_to_github(page)
                
            if success:
    # Mark as live/published in database
                new_meta = page['metadata'].copy()
                new_meta['status'] = 'published'  # or 'live'
                memory.update_entity(page['id'], new_meta)
                published_count += 1
                
        return AgentOutput(status="success", message=f"Published {published_count} pages.")

    def publish_to_wordpress(self, page, wp_url: str, wp_user: str, wp_password: str):
        """Publish a page to WordPress using provided credentials."""
        # Base64 encode credentials for Basic Auth
        creds = base64.b64encode(f"{wp_user}:{wp_password}".encode()).decode()
        
        post_data = {
            "title": page['name'],
            "content": page['metadata']['content'],
            "status": "draft", # Publish as draft first to be safe
            "categories": [1] # Default category
        }
        
        try:
            res = requests.post(
                wp_url, 
                json=post_data, 
                headers={"Authorization": f"Basic {creds}"}
            )
            return res.status_code == 201
        except Exception as e:
            print(f"WP Error: {e}")
            return False

    def publish_to_github(self, page):
        # 1. Git Config (For Vercel)
        # This commits a new .md file to your Next.js repo "content" folder
        # Vercel detects the commit and rebuilds the site.
        print("Committing to GitHub...")
        # (Requires GitHub API Token logic here)
        return True