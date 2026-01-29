# backend/modules/pseo/agents/scout.py
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory

# Import async entrypoints to avoid blocking the thread pool
from backend.core.services.maps_sync import run_scout_async
from backend.core.services.search_sync import run_search_async

class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Scout")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute scout agent to gather anchor locations and intel (competitors/facts).
        
        Returns:
            AgentOutput with status, message, and data containing counts of saved entities
        """
        try:
            # 1. VALIDATE INPUTS & SETUP CONTEXT
            project_id = self.project_id
            user_id = self.user_id
            campaign_id = input_data.params.get("campaign_id") or self.campaign_id

            # Validate required context
            if not project_id:
                error_msg = "Missing project_id in agent context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )
            
            if not user_id:
                error_msg = "Missing user_id in agent context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )
            
            if not campaign_id:
                error_msg = "Missing campaign_id in params or context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # Load Campaign Config (The source of truth)
            try:
                campaign = memory.get_campaign(campaign_id, user_id)
                if not campaign:
                    error_msg = f"Campaign {campaign_id} not found or access denied"
                    self.logger.error(error_msg)
                    return AgentOutput(
                        status="error",
                        message=error_msg,
                        data={}
                    )
            except Exception as e:
                error_msg = f"Failed to load campaign {campaign_id}: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )
            
            config = campaign.get('config', {})
            
            if not isinstance(config, dict):
                error_msg = "Invalid campaign config format"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )
            
            # Extract from targeting section (campaign config structure)
            targeting = config.get('targeting', {})
            service = targeting.get('service_focus', config.get('service_focus', 'Service'))
            geo_targets = targeting.get('geo_targets', {}).get('cities', [])
            mining_rules = config.get('mining_requirements', {})

            # Validate geo_targets
            if not isinstance(geo_targets, list) or len(geo_targets) == 0:
                error_msg = "No geo_targets (cities) configured in campaign"
                self.logger.warning(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            self.logger.info(f"🕵️ SCOUT STARTED: {service} in {geo_targets}")

            # 2. PREPARE MISSION LISTS
            map_queries = []    # For Scout (Locations)
            search_queries = [] # For Miner (Competitors/Facts) - will contain {"query": str, "type": str} dicts

            # A. Build Map Queries (Anchors)
            # e.g., "District Court in Manukau", "Police Station in Manukau"
            try:
                target_anchors = mining_rules.get('geo_context', {}).get('target_anchors', ["Landmarks"])
                if not isinstance(target_anchors, list):
                    target_anchors = ["Landmarks"]
                    self.logger.warning("Invalid target_anchors format, using default")
                
                for city in geo_targets:
                    if not isinstance(city, str) or not city.strip():
                        continue
                    for anchor in target_anchors:
                        if isinstance(anchor, str) and anchor.strip():
                            map_queries.append(f"{anchor.strip()} in {city.strip()}")
            except Exception as e:
                self.logger.warning(f"Error building map queries: {e}", exc_info=True)

            # B. Build Search Queries (Intel)
            # e.g., "Bail lawyer cost Manukau", "Filing fee Manukau court"
            try:
                competitor_count = 0
                regulatory_count = 0
                
                # 1. Competitor Queries
                competitor_config = mining_rules.get('competitor', {})
                if competitor_config.get('enabled', False):
                    base_qs = competitor_config.get('queries', [])
                    self.logger.info(f"🔍 Competitor mining enabled - found {len(base_qs) if isinstance(base_qs, list) else 0} query templates")
                    if isinstance(base_qs, list) and len(base_qs) > 0:
                        for q in base_qs:
                            if isinstance(q, str) and q.strip():
                                # If query has placeholders, expand for each city
                                if "{city}" in q or "{service}" in q:
                                    for city in geo_targets:
                                        if isinstance(city, str) and city.strip():
                                            final_query = q.replace("{service}", service).replace("{city}", city.strip())
                                            search_queries.append({
                                                "query": final_query,
                                                "type": "competitor"
                                            })
                                            competitor_count += 1
                                else:
                                    # Query is already complete, use as-is (no placeholders)
                                    search_queries.append({
                                        "query": q.strip(),
                                        "type": "competitor"
                                    })
                                    competitor_count += 1
                
                # 2. Regulatory Queries (marked as "fact" type)
                regulatory_config = mining_rules.get('regulatory', {})
                if regulatory_config.get('enabled', False):
                    base_qs = regulatory_config.get('queries', [])
                    self.logger.info(f"🔍 Regulatory mining enabled - found {len(base_qs) if isinstance(base_qs, list) else 0} query templates")
                    if isinstance(base_qs, list) and len(base_qs) > 0:
                        for q in base_qs:
                            if isinstance(q, str) and q.strip():
                                # If query has placeholders, expand for each city
                                if "{city}" in q or "{service}" in q:
                                    for city in geo_targets:
                                        if isinstance(city, str) and city.strip():
                                            final_query = q.replace("{service}", service).replace("{city}", city.strip())
                                            search_queries.append({
                                                "query": final_query,
                                                "type": "fact"
                                            })
                                            regulatory_count += 1
                                else:
                                    # Query is already complete, use as-is (no placeholders)
                                    search_queries.append({
                                        "query": q.strip(),
                                        "type": "fact"
                                    })
                                    regulatory_count += 1
                
                self.logger.info(f"✅ Built {len(search_queries)} search queries for intel gathering ({competitor_count} competitors, {regulatory_count} facts)")
            except Exception as e:
                self.logger.error(f"❌ Error building search queries: {e}", exc_info=True)

            # Validate we have at least some queries
            if len(map_queries) == 0 and len(search_queries) == 0:
                error_msg = "No queries generated from campaign config"
                self.logger.warning(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # 3. EXECUTE SERIAL MISSIONS (Sequential for debugging)
            self.logger.info(f"🚀 Launching Serial Missions: {len(map_queries)} Map Scans, {len(search_queries)} Google Searches")
            
            map_results_raw = None
            search_results_raw = None
            map_error = None
            search_error = None
            
            try:
                # STEP 1: Run Map Sync (Anchor Locations)
                if map_queries:
                    self.logger.info(f"📍 STEP 1/2: Running map_sync for {len(map_queries)} anchor queries...")
                    self.logger.info(f"📍 Map queries: {map_queries[:3]}{'...' if len(map_queries) > 3 else ''}")
                    try:
                        map_results_raw = await run_scout_async(map_queries)
                        self.logger.info(f"✅ Map sync completed: {map_results_raw.get('message', 'Unknown status')}")
                    except Exception as e:
                        map_error = str(e)
                        self.logger.error(f"❌ Map sync failed: {e}", exc_info=True)
                        map_results_raw = {"success": False, "data": [], "message": map_error}
                else:
                    self.logger.info("📍 STEP 1/2: No map queries - skipping map_sync")
                    map_results_raw = {"success": True, "data": [], "message": "No map queries"}
                
                # STEP 2: Run Search Sync (Intel/Competitors/Facts)
                if search_queries:
                    competitor_count = sum(1 for q in search_queries if isinstance(q, dict) and q.get("type") == "competitor")
                    fact_count = len(search_queries) - competitor_count
                    self.logger.info(f"🔎 STEP 2/2: Executing search_sync with {len(search_queries)} queries via Serper API ({competitor_count} competitors, {fact_count} facts)...")
                    # Log sample queries (first 3)
                    sample_queries = [q.get("query", q) if isinstance(q, dict) else q for q in search_queries[:3]]
                    self.logger.info(f"🔎 Sample queries: {sample_queries}{'...' if len(search_queries) > 3 else ''}")
                    try:
                        search_results_raw = await run_search_async(search_queries)
                        self.logger.info(f"📊 Search sync completed - received {len(search_results_raw) if isinstance(search_results_raw, list) else 0} results")
                        if not isinstance(search_results_raw, list):
                            self.logger.warning(f"⚠️ Search sync returned non-list result: {type(search_results_raw)}")
                            search_results_raw = []
                        elif len(search_results_raw) == 0:
                            self.logger.warning("⚠️ Search sync returned empty results - check API key and query validity")
                            self.logger.info(f"🔍 Debug: Queries sent were: {search_queries}")
                        else:
                            self.logger.info(f"✅ Successfully collected {len(search_results_raw)} search results")
                    except Exception as e:
                        search_error = str(e)
                        self.logger.error(f"❌ Search sync failed: {e}", exc_info=True)
                        self.logger.error(f"🔍 Debug: Queries that failed: {search_queries}")
                        search_results_raw = []
                else:
                    self.logger.warning("⚠️ STEP 2/2: No search queries generated - skipping search_sync")
                    self.logger.info(f"🔍 Debug: competitor.enabled={mining_rules.get('competitor', {}).get('enabled')}, regulatory.enabled={mining_rules.get('regulatory', {}).get('enabled')}")
                    search_results_raw = []
                    
            except Exception as e:
                error_msg = f"Failed to execute parallel missions: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # 4. PROCESS & SAVE DATA
            saved_anchors = 0
            saved_intel = 0
            save_errors = []
            
            try:
                # Process map results (anchor locations)
                if map_results_raw and map_results_raw.get('success', False):
                    anchor_data = map_results_raw.get('data', [])
                    if isinstance(anchor_data, list):
                        saved_anchors = self._save_anchors(anchor_data, user_id, project_id, campaign_id)
                    else:
                        self.logger.warning(f"Invalid anchor data format: {type(anchor_data)}")
                else:
                    self.logger.warning(f"Map sync failed or returned no data: {map_results_raw.get('message', 'Unknown error')}")
                
                # Process search results (intel)
                if isinstance(search_results_raw, list):
                    if len(search_results_raw) > 0:
                        self.logger.info(f"💾 Processing {len(search_results_raw)} search results for intel entities...")
                        saved_intel = self._save_intel(search_results_raw, user_id, project_id, campaign_id)
                        self.logger.info(f"✅ Saved {saved_intel} intel entities (competitors/facts)")
                    else:
                        self.logger.warning("⚠️ Search results list is empty - no intel to save")
                        saved_intel = 0
                else:
                    self.logger.warning(f"❌ Invalid search results format: {type(search_results_raw)}")
                    saved_intel = 0
                    
            except Exception as e:
                error_msg = f"Error saving entities: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                save_errors.append(error_msg)

            # 5. REPORT
            status = "success"
            message_parts = [f"Intel Gathered: {saved_anchors} Locations, {saved_intel} Intel Fragments."]
            
            if map_error:
                message_parts.append(f"Map sync errors: {map_error}")
            if search_error:
                message_parts.append(f"Search sync errors: {search_error}")
            if save_errors:
                message_parts.append(f"Save errors: {', '.join(save_errors)}")
                status = "partial"  # Partial success if some saves failed
            
            if saved_anchors == 0 and saved_intel == 0:
                status = "error"
                message_parts.append("No entities were saved.")
            
            return AgentOutput(
                status=status,
                message=" ".join(message_parts),
                data={
                    "anchors": saved_anchors,
                    "intel": saved_intel,
                    "next_step": "Ready for Strategist" if saved_anchors > 0 or saved_intel > 0 else "Check configuration"
                }
            )
            
        except Exception as e:
            error_msg = f"Unexpected error in scout agent: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return AgentOutput(
                status="error",
                message=error_msg,
                data={}
            )

    def _save_anchors(self, results: List[Dict[str, Any]], user_id: str, project_id: str, campaign_id: str) -> int:
        """
        Save anchor location entities with RLS enforcement.
        
        Args:
            results: List of anchor location data dicts from maps_sync
            user_id: Tenant ID for RLS
            project_id: Project ID for scoping
            campaign_id: Campaign ID for scoping
            
        Returns:
            Count of successfully saved entities
        """
        if not results or not isinstance(results, list):
            self.logger.warning("No anchor results to save or invalid format")
            return 0
        
        count = 0
        seen_ids = set()
        
        for item in results:
            try:
                # Validate item structure
                if not isinstance(item, dict):
                    self.logger.warning(f"Invalid anchor item format: {type(item)}")
                    continue
                
                name = item.get('name')
                if not name or not isinstance(name, str) or not name.strip():
                    self.logger.warning("Skipping anchor with missing/invalid name")
                    continue
                
                # Create unique ID based on name and address
                address = item.get('address', '')[:10] if item.get('address') else ''
                unique_str = f"{name.strip()}-{address}"
                unique_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]
                
                # Deduplicate
                if unique_id in seen_ids:
                    self.logger.debug(f"Skipping duplicate anchor: {name}")
                    continue
                seen_ids.add(unique_id)
                
                # Build entity
                entity = Entity(
                    id=f"anchor_{unique_id}",
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="anchor_location",
                    name=name.strip()[:200],  # Limit name length
                    primary_contact=item.get('phone'),  # Phone as primary contact
                    metadata={
                        "campaign_id": campaign_id,
                        "address": item.get('address'),
                        "google_maps_url": item.get('google_maps_url'),
                        "source_query": item.get('source_query'),
                        "working_hours": item.get('working_hours'),  # If available from maps_sync
                        "website": item.get('website')
                    }
                )
                
                # Save entity
                success = memory.save_entity(entity, project_id=project_id)
                if success:
                    count += 1
                    self.logger.debug(f"Saved anchor: {name}")
                else:
                    self.logger.warning(f"Failed to save anchor: {name}")
                    
            except Exception as e:
                self.logger.warning(f"Error saving anchor entity: {e}", exc_info=True)
                continue
        
        self.logger.info(f"Saved {count} anchor locations")
        return count

    def _save_intel(self, results: List[Dict[str, Any]], user_id: str, project_id: str, campaign_id: str) -> int:
        """
        Save knowledge fragment entities (competitors/facts) with RLS enforcement.
        
        Args:
            results: List of search result dicts from search_sync
            user_id: Tenant ID for RLS
            project_id: Project ID for scoping
            campaign_id: Campaign ID for scoping
            
        Returns:
            Count of successfully saved entities
        """
        if not results or not isinstance(results, list):
            self.logger.warning("No intel results to save or invalid format")
            return 0
        
        count = 0
        seen_ids = set()
        
        for item in results:
            try:
                # Validate item structure
                if not isinstance(item, dict):
                    self.logger.warning(f"Invalid intel item format: {type(item)}")
                    continue
                
                # Validate required fields
                required_fields = ['title', 'link', 'type', 'query']
                if not all(field in item for field in required_fields):
                    self.logger.warning(f"Skipping intel item with missing fields: {item.keys()}")
                    continue
                
                title = item.get('title', '').strip()
                link = item.get('link', '').strip()
                
                if not title or not link:
                    self.logger.warning("Skipping intel with missing title or link")
                    continue
                
                # Create unique ID based on link
                uid = hashlib.sha256(link.encode()).hexdigest()[:16]
                
                # Deduplicate
                if uid in seen_ids:
                    self.logger.debug(f"Skipping duplicate intel: {title[:50]}")
                    continue
                seen_ids.add(uid)
                
                # Validate type
                intel_type = item.get('type', 'fact')
                if intel_type not in ['competitor', 'fact']:
                    intel_type = 'fact'  # Default to fact if invalid
                    self.logger.debug(f"Invalid type '{item.get('type')}', defaulting to 'fact'")
                
                # Build entity
                entity = Entity(
                    id=f"intel_{uid}",
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="knowledge_fragment",
                    name=title[:200],  # Limit name length
                    primary_contact=link,  # URL as primary contact
                    metadata={
                        "campaign_id": campaign_id,
                        "type": intel_type,  # 'competitor' or 'fact'
                        "url": link,
                        "snippet": item.get('snippet', ''),
                        "query": item.get('query', '')
                    }
                )
                
                # Save entity to SQL DB
                success = memory.save_entity(entity, project_id=project_id)
                if success:
                    count += 1
                    self.logger.debug(f"Saved intel: {title[:50]} ({intel_type})")
                    
                    # Also store in ChromaDB for semantic search (RAG)
                    # Create a rich text representation for embedding
                    snippet = item.get('snippet', '')
                    text_content = f"{title}. {snippet}"
                    if link:
                        text_content += f" Source: {link}"
                    
                    # Store in vector DB with campaign scoping
                    memory.save_context(
                        tenant_id=user_id,
                        text=text_content,
                        metadata={
                            "type": "knowledge_fragment",
                            "entity_id": f"intel_{uid}",
                            "fragment_type": intel_type,  # 'competitor' or 'fact'
                            "title": title,
                            "url": link,
                            "query": item.get('query', '')
                        },
                        project_id=project_id,
                        campaign_id=campaign_id
                    )
                    self.logger.debug(f"Stored knowledge fragment in ChromaDB: {title[:50]}")
                else:
                    self.logger.warning(f"Failed to save intel: {title[:50]}")
                    
            except Exception as e:
                self.logger.warning(f"Error saving intel entity: {e}", exc_info=True)
                continue
        
        self.logger.info(f"Saved {count} knowledge fragments")
        return count