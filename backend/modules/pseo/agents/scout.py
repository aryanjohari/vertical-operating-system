# backend/modules/pseo/agents/scout.py
import asyncio
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.services.maps_sync import run_scout_sync  # The Heavy Lifter
from backend.core.memory import memory
from backend.core.config import ConfigLoader

class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Scout")
        self.config_loader = ConfigLoader()

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Task: 'scout_anchors'
        Purpose: Find physical locations (Anchors) to ground the SEO strategy.
        Input: user_id, project_id (implicit via memory), queries (optional override)
        """
        task = input_data.task
        user_id = input_data.user_id

        # 1. GET PROJECT CONTEXT
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found for user.")
        
        project_id = project['project_id']
        
        # 2. LOAD DNA CONFIG
        # We need the specific rules for this client (e.g. Block "Youth Prison")
        config = self.config_loader.load(project_id)
        scout_rules = config.get('modules', {}).get('local_seo', {}).get('scout_settings', {})
        
        # 3. DETERMINE QUERIES
        # Priority: Direct Input > DNA Config > Default
        queries = input_data.params.get("queries", [])
        if not queries:
            # Generate from DNA: "Court in Auckland", "Prison in Auckland"
            anchors = scout_rules.get('anchor_entities', [])
            cities = scout_rules.get('geo_scope', {}).get('cities', ["Auckland"])
            for anchor in anchors:
                for city in cities:
                    queries.append(f"{anchor} in {city}")

        if not queries:
            return AgentOutput(status="error", message="No queries defined in DNA or Input.")

        # 4. PREPARE FILTERS
        # We auto-whitelist the search terms to prevent over-filtering
        allow_kws = scout_rules.get('allow_keywords', [])
        # If searching for "Court", allow "Court" in result names
        for q in queries:
            term = q.split(" in ")[0]
            allow_kws.append(term) 
            if term.endswith('s'): allow_kws.append(term[:-1]) # "Courts" -> "Court"
            
        block_kws = scout_rules.get('block_keywords', [])

        self.log(f"📍 Launching Sync Scraper for {len(queries)} queries (Project: {project_id})...")

        # 5. EXECUTE SCRAPER (Threaded)
        # We use asyncio.to_thread because Playwright Sync is blocking
        try:
            response = await asyncio.to_thread(
                run_scout_sync, 
                queries, 
                allow_kws, 
                block_kws
            )
        except Exception as e:
            self.logger.error(f"Scraper Critical Fail: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Sync Scraper Failed: {e}")

        # 6. VALIDATE RESPONSE
        if not isinstance(response, dict) or not response.get("success"):
            msg = response.get("message", "Unknown Scraper Error") if isinstance(response, dict) else "Invalid Response"
            return AgentOutput(status="error", message=msg)

        # 7. SAVE ENTITIES (Scoped to Project)
        results = response.get("data", []) or []
        saved_count = 0
        
        for item in results:
            if not isinstance(item, dict): continue
            
            # Create Unique ID based on URL or Name+Address
            uid_source = item.get('google_maps_url') or f"{item.get('name')}-{item.get('address')}"
            entity_id = f"loc_{hash(uid_source)}"
            
            entity_obj = Entity(
                id=entity_id,
                tenant_id=user_id,
                project_id=project_id,  # <--- CRITICAL: Links to this specific campaign
                entity_type="anchor_location",
                name=item.get('name', 'Unknown'),
                primary_contact=item.get('phone'),
                metadata={
                    **item, 
                    "source_query": queries  # Traceability
                },
                created_at=datetime.now()
            )
            
            # Explicitly pass project_id for clarity and reliability
            if memory.save_entity(entity_obj, project_id=project_id):
                saved_count += 1
        
        # 8. RETURN STATUS
        # Manager logic: If we found 0, something is wrong. If >0, success.
        if saved_count == 0 and len(results) == 0:
             return AgentOutput(status="warning", message="Scout finished but found NO locations. Check queries/filters.")
             
        return AgentOutput(
            status="success", 
            message=f"Scout Mission Complete. Secured {saved_count} Anchor Locations.", 
            data={"count": saved_count, "locations": [r.get('name') for r in results[:5]]}
        )