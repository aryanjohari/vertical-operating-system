# backend/modules/pseo/agents/scout.py
import asyncio
import hashlib
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.services.maps_sync import run_scout_sync  # The Heavy Lifter
from backend.core.memory import memory

class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Scout")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Task: 'scout_anchors'
        Purpose: Find physical locations (Anchors) to ground the SEO strategy.
        Input: user_id, project_id (injected by kernel), queries (optional override)
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
        
        # 2. USE INJECTED DNA CONFIG (loaded by kernel)
        scout_rules = self.config.get('modules', {}).get('local_seo', {}).get('scout_settings', {})
        
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

        self.logger.info(f"📍 Launching Sync Scraper for {len(queries)} queries (Project: {project_id})...")

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

        # 7. SAVE ENTITIES (Scoped to Project) with Deduplication
        results = response.get("data", []) or []
        saved_count = 0
        skipped_count = 0
        
        # Get existing entities to check for duplicates
        existing_entities = memory.get_entities(
            tenant_id=user_id,
            entity_type="anchor_location",
            project_id=project_id,
            limit=1000
        )
        existing_ids = {e.get('id') for e in existing_entities if e.get('id')}
        existing_urls = {
            e.get('metadata', {}).get('google_maps_url') 
            for e in existing_entities 
            if isinstance(e.get('metadata'), dict) and e.get('metadata', {}).get('google_maps_url')
        }
        existing_names_addresses = {
            f"{e.get('name', '')}-{e.get('metadata', {}).get('address', '')}" 
            for e in existing_entities
            if e.get('name') and isinstance(e.get('metadata'), dict) and e.get('metadata', {}).get('address')
        }
        
        for item in results:
            if not isinstance(item, dict): continue
            
            # Create Unique ID based on URL or Name+Address (using SHA256 to prevent collisions)
            uid_source = item.get('google_maps_url') or f"{item.get('name')}-{item.get('address')}"
            uid_hash = hashlib.sha256(uid_source.encode()).hexdigest()[:16]
            entity_id = f"loc_{uid_hash}"
            
            # Deduplication check: Skip if entity already exists
            google_url = item.get('google_maps_url')
            name_address = f"{item.get('name', '')}-{item.get('address', '')}"
            
            if entity_id in existing_ids:
                skipped_count += 1
                self.logger.debug(f"Skipping duplicate entity (ID): {item.get('name')}")
                continue
            
            if google_url and google_url in existing_urls:
                skipped_count += 1
                self.logger.debug(f"Skipping duplicate entity (URL): {item.get('name')}")
                continue
            
            if name_address in existing_names_addresses:
                skipped_count += 1
                self.logger.debug(f"Skipping duplicate entity (Name+Address): {item.get('name')}")
                continue
            
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
                # Update tracking sets for subsequent items in this batch
                existing_ids.add(entity_id)
                if google_url:
                    existing_urls.add(google_url)
                existing_names_addresses.add(name_address)
        
        # 8. RETURN STATUS
        # Manager logic: If we found 0, something is wrong. If >0, success.
        if saved_count == 0 and len(results) == 0:
             return AgentOutput(status="warning", message="Scout finished but found NO locations. Check queries/filters.")
        
        message = f"Scout Mission Complete. Secured {saved_count} new Anchor Locations."
        if skipped_count > 0:
            message += f" Skipped {skipped_count} duplicates."
             
        return AgentOutput(
            status="success", 
            message=message, 
            data={
                "count": saved_count,
                "skipped": skipped_count,
                "locations": [r.get('name') for r in results[:5]]
            }
        )