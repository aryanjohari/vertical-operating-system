import requests
import base64
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class PublisherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Publisher")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
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
        
        # 1. USE INJECTED CONFIG & SECRETS (loaded by kernel)
        config = self.config
        pub_settings = config.get('modules', {}).get('local_seo', {}).get('publisher_settings', {})
        
        # Validate Credentials
        wp_url = pub_settings.get('url')
        wp_user = pub_settings.get('username')
        # In production, password should come from a secure vault (memory.get_client_secrets)
        # For this architecture, we check the DB secrets first
        try:
            secrets = memory.get_client_secrets(user_id)
            wp_password = secrets.get('wp_password') if secrets else None
            if not wp_password:
                return AgentOutput(status="error", message="WordPress password not found in secrets.")
        except Exception as e:
            self.logger.error(f"Failed to retrieve/decrypt WordPress password: {e}", exc_info=True)
            return AgentOutput(status="error", message="Credential retrieval failed.")

        if not wp_url or not wp_user:
             return AgentOutput(status="error", message="Missing WordPress URL or username in Config.")

        # 2. FETCH READY PAGES (Pipeline Scoped)
        # Input: Utility sets status to 'ready_to_publish'
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        ready_pages = [p for p in pages if p['metadata'].get('status') == 'ready_to_publish']
        
        if not ready_pages:
             return AgentOutput(status="complete", message="No pages ready to publish.")

        # 3. APPLY DRIP FEED LIMIT
        # Manager controls the speed (e.g. 2 per run) to avoid Google penalties
        limit = input_data.params.get("limit", 2)
        batch = ready_pages[:limit]
        
        self.log(f"🚀 Publishing {len(batch)} pages to {wp_url}...")
        
        published_count = 0
        for page in batch:
            success = self.publish_to_wordpress(page, wp_url, wp_user, wp_password)
                
            if success:
                # 4. UPDATE STATUS TO LIVE
                new_meta = page['metadata'].copy()
                new_meta['status'] = 'published'
                new_meta['published_at'] = str(input_data.created_at)
                new_meta['live_url'] = f"{wp_url}/{new_meta.get('slug')}"
                
                memory.update_entity(page['id'], new_meta)
                published_count += 1
            else:
                self.log(f"❌ Failed to publish {page['name']}")

        return AgentOutput(
            status="success", 
            message=f"Published {published_count} pages (Drip Limit: {limit}).",
            data={"count": published_count}
        )

    def publish_to_wordpress(self, page, wp_url: str, wp_user: str, wp_password: str):
        """Publish a page to WordPress using proper Slug and Content."""
        # Ensure URL ends with endpoint
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        
        creds = base64.b64encode(f"{wp_user}:{wp_password}".encode()).decode()
        
        # WordPress Payload
        post_data = {
            "title": page['name'],
            "content": page['metadata']['content'],
            "slug": page['metadata'].get('slug'), # CRITICAL for SEO
            "status": "publish", 
            "categories": [1] # Default category, can be smarter later
        }
        
        try:
            res = requests.post(
                endpoint, 
                json=post_data, 
                headers={"Authorization": f"Basic {creds}"},
                timeout=10
            )
            if res.status_code in [200, 201]:
                return True
            else:
                print(f"WP Error {res.status_code}: {res.text}")
                return False
        except Exception as e:
            print(f"WP Connection Failed: {e}")
            return False