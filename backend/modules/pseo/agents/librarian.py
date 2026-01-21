# backend/modules/pseo/agents/librarian.py
import random
import re
import html
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class LibrarianAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Librarian")

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
        
        # 1. FETCH CANDIDATES
        # Pipeline: Writer -> Critic (Sets 'validated') -> Librarian -> Media
        drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        targets = [d for d in drafts if d['metadata'].get('status') == 'validated']
        
        if not targets:
            return AgentOutput(status="complete", message="No validated pages need linking.")

        linked_count = 0
        
        for page in targets:
            current_cluster = page['metadata'].get('cluster')
            current_city = page['metadata'].get('city')
            
            # 2. STRATEGIC LINKING LOGIC
            # Priority A: Same Cluster (Topical Authority)
            cluster_siblings = [
                d for d in drafts 
                if d['metadata'].get('cluster') == current_cluster 
                and d['id'] != page['id'] 
                and d['metadata'].get('slug') # Must have slug
            ]
            
            # Priority B: Same City (Local Relevance - Fallback)
            city_siblings = [
                d for d in drafts 
                if d['metadata'].get('city') == current_city 
                and d['id'] != page['id'] 
                and d['metadata'].get('slug')
            ]
            
            # Mix: 2 Cluster links + 1 Local link
            picks = []
            if len(cluster_siblings) >= 2:
                picks.extend(random.sample(cluster_siblings, 2))
            else:
                picks.extend(cluster_siblings)
                
            remaining_slots = 3 - len(picks)
            if remaining_slots > 0 and city_siblings:
                # Avoid duplicates
                available_city = [s for s in city_siblings if s not in picks]
                if available_city:
                    picks.extend(random.sample(available_city, min(remaining_slots, len(available_city))))
            
            if not picks:
                # If no links possible, still pass it forward so it doesn't get stuck
                self._promote(page)
                continue

            # 3. GENERATE HTML (With SEO Slugs and sanitization)
            def sanitize_slug(slug: str) -> str:
                """Remove any non-alphanumeric except hyphens/underscores"""
                if not slug:
                    return ""
                return re.sub(r'[^a-z0-9_-]', '', slug.lower())
            
            links_list = "".join([
                f'<li><a href="/{sanitize_slug(p["metadata"].get("slug", ""))}">{html.escape(p["name"])}</a></li>' 
                for p in picks
            ])
            
            link_box = f"""
            <div class="apex-related-links" style="margin: 2rem 0; padding: 1.5rem; background: #f8f9fa; border-left: 4px solid #2563eb; border-radius: 4px;">
                <h3 style="margin-top:0; font-size: 1.2rem;">Related Resources</h3>
                <ul style="margin-bottom:0; padding-left: 1.2rem;">
                    {links_list}
                </ul>
            </div>
            """
            
            # 4. INJECT & PROMOTE
            new_content = page['metadata'].get('content', '') + "\n" + link_box
            
            new_meta = page['metadata'].copy()
            new_meta['content'] = new_content
            new_meta['status'] = 'ready_for_media' # Hand off to Media Agent
            new_meta['linked_to'] = [p['metadata']['slug'] for p in picks] # Tracking
            
            memory.update_entity(page['id'], new_meta)
            linked_count += 1

        return AgentOutput(status="success", message=f"Interlinked {linked_count} pages with Topic Clusters.")

    def _promote(self, page):
        """Pass page to next stage even if no links found (don't block pipeline)"""
        new_meta = page['metadata'].copy()
        new_meta['status'] = 'ready_for_media'
        memory.update_entity(page['id'], new_meta)