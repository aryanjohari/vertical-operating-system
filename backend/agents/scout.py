# backend/agents/scout.py
import asyncio
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.scrapers.universal import scrape_website
from backend.scrapers.maps_sync import run_scout_sync # <--- USE THE SYNC WRAPPER
from backend.core.memory import memory

class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Scout")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        task = input_data.task
        user_id = input_data.user_id

        if task == "scrape_site":
            # ... (keep existing logic) ...
            return AgentOutput(status="success", message="Scrape Complete", data={})

        elif task == "scout_anchors":
            queries = input_data.params.get("queries", [])
            
            # Config Rules
            scout_rules = self.config.get('scout_rules', {})
            allow_kws = scout_rules.get('allow_keywords', [])
            block_kws = scout_rules.get('block_keywords', [])

            # Smart Filter Append (Ensure "Court" is allowed if searching for "Courts")
            if allow_kws:
                for q in queries:
                    term = q.split(" in ")[0]
                    allow_kws.append(term)
                    if term.endswith('s'): allow_kws.append(term[:-1])

            self.log(f"📍 Launching Sync Scraper for {len(queries)} queries...")

            # --- RUN SYNC CODE IN THREAD (Non-Blocking) ---
            try:
                response = await asyncio.to_thread(
                    run_scout_sync, 
                    queries, 
                    allow_kws, 
                    block_kws
                )
            except Exception as e:
                return AgentOutput(status="error", message=f"Sync Scraper Failed: {e}")

            # SAFE RESPONSE HANDLING - Check if response is a dict
            if not isinstance(response, dict):
                return AgentOutput(
                    status="error", 
                    message=f"Invalid response type from scraper: {type(response)}"
                )

            if not response.get("success", False):
                return AgentOutput(
                    status="error", 
                    message=response.get("message", "Unknown error")
                )

            # SAVE RESULTS
            results = response.get("data", []) or []  # Ensure it's a list, not None
            saved_count = 0
            for item in results:
                if not isinstance(item, dict):
                    continue  # Skip invalid items
                    
                entity_obj = Entity(
                    id=f"loc_{hash(item.get('google_maps_url', ''))}",
                    tenant_id=user_id,
                    entity_type="anchor_location",
                    name=item.get('name', 'Unknown'),
                    primary_contact=item.get('phone'),
                    metadata=item, # Contains address, phone, website
                    created_at=datetime.now()
                )
                if memory.save_entity(entity_obj):
                    saved_count += 1
            
            return AgentOutput(
                status="success", 
                message=f"Found {len(results)} locations. Saved {saved_count}.", 
                data={"count": saved_count}
            )

        return AgentOutput(status="error", message=f"Unknown Task: {task}")