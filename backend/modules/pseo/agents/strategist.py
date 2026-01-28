# backend/modules/pseo/agents/strategist.py
import json
import logging
import asyncio
import requests
import hashlib
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory
from backend.core.services.llm_gateway import llm_gateway

# Simple Google Autocomplete Tool (Undocumented free API)
def get_autocomplete_suggestions(query: str) -> List[str]:
    """
    Queries Google's Autocomplete API to validate if a keyword has search volume.
    Returns a list of suggestions. If list is empty, demand is low/zero.
    """
    try:
        url = f"http://google.com/complete/search?client=chrome&q={query}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return json.loads(response.text)[1] # Format: [query, [suggestions...], ...]
    except Exception:
        return []
    return []

class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Strategist")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute strategist agent to generate revenue-ready SEO keywords.
        
        Returns:
            AgentOutput with status, message, and data containing keyword generation results
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
            service_focus = targeting.get('service_focus', config.get('service_focus'))
            cities = targeting.get('geo_targets', {}).get('cities', [])
            
            # Validate service_focus
            if not service_focus:
                error_msg = "service_focus not configured in campaign"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )
            
            # Validate cities
            if not isinstance(cities, list) or len(cities) == 0:
                error_msg = "No geo_targets (cities) configured in campaign"
                self.logger.warning(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # Load Scraped Assets (The "Real World" Data)
            all_anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
            # Filter for this campaign and exclude anchors the user has explicitly excluded
            campaign_anchors = [
                a
                for a in all_anchors
                if a.get("metadata", {}).get("campaign_id") == campaign_id
                and not a.get("metadata", {}).get("excluded")
            ]
            
            self.logger.info(f"🧠 STRATEGIST: Initializing for '{service_focus}' with {len(campaign_anchors)} Anchors")

            # 2. PHASE 1: ROOT EXTRACTION (LLM)
            # We ask LLM for "Search Intent Roots" ONLY. Not full keywords.
            # e.g., "bail accommodation", "parole housing", "place to stay on bail"
            root_intents = await self._get_intent_roots(service_focus)
            self.logger.info(f"🔍 Identified {len(root_intents)} Intent Roots: {root_intents}")

            # 3. PHASE 2: PERMUTATION (The "Sniper" Logic)
            # We mechanically generate keywords to ensure coverage.
            raw_keywords = []

            for root in root_intents:
                # A. Geo-Modifiers (City Level) -> "Bail housing Hamilton"
                for city in cities:
                    kw = f"{root} {city}"
                    raw_keywords.append({"term": kw, "type": "geo_city", "parent": root})
                    
                    # Variations
                    raw_keywords.append({"term": f"{root} in {city}", "type": "geo_city", "parent": root})

                # B. Anchor-Modifiers (Hyper-Local) -> "Bail housing near Court"
                # This is your "Rank #1" secret weapon.
                for anchor in campaign_anchors:
                    anchor_name = anchor.get('name')
                    # Clean name: "Hamilton District Court" -> "Hamilton Court" (User speak)
                    simple_name = anchor_name.replace("District", "").replace("Central", "").strip()
                    
                    kw = f"{root} near {simple_name}"
                    raw_keywords.append({"term": kw, "type": "geo_anchor", "parent": root, "anchor_id": anchor.get('id')})

            self.logger.info(f"⚡ Generated {len(raw_keywords)} raw permutations.")

            # 4. PHASE 3: VALIDATION (Autocomplete Check)
            # We check which ones actually exist in Google's database.
            # Note: We batch this or sample to avoid 429s. For V4, we validate 'Geo-City' strictly,
            # but we trust 'Geo-Anchor' (Long Tail) even if volume is low.
            
            validated_keywords = []
            for kw_obj in raw_keywords:
                term = kw_obj['term']
                
                # SCORING LOGIC
                score = 0
                
                # Check 1: Is it a hyper-local anchor? (Automatic pass - High Value)
                if kw_obj['type'] == 'geo_anchor':
                    score += 80 # We want these even if volume is hidden
                
                # Check 2: Google Autocomplete (The "Truth")
                # Only check "City" keywords to verify the Root is valid
                if kw_obj['type'] == 'geo_city':
                    suggestions = await asyncio.to_thread(get_autocomplete_suggestions, term)
                    if suggestions:
                        score += 90 # High demand confirmed
                        kw_obj['suggestions'] = suggestions[:3] # Save related terms
                    else:
                        score += 10 # Might be zero volume
                
                if score > 50:
                    kw_obj['score'] = score
                    validated_keywords.append(kw_obj)

            self.logger.info(f"✅ Validated {len(validated_keywords)} high-intent keywords.")

            # 5. PHASE 4: CLUSTERING & SAVING
            # We group by "Parent" (Intent Root) to prevent cannibalization.
            saved_count = 0
            
            for kw_data in validated_keywords:
                # Create Unique ID
                uid = hashlib.md5(kw_data['term'].encode()).hexdigest()[:12]
                
                entity = Entity(
                    id=f"kw_{uid}",
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="seo_keyword",
                    name=kw_data['term'],
                    metadata={
                        "campaign_id": campaign_id,
                        "status": "pending",        # Ready for Writer
                        "intent": kw_data['parent'], # The Cluster Name
                        "type": kw_data['type'],    # City vs Anchor
                        "score": kw_data.get('score', 0),
                        "related_terms": kw_data.get('suggestions', []),
                        "anchor_reference": kw_data.get('anchor_id') # Link to the physical location
                    }
                )
                memory.save_entity(entity, project_id=project_id)
                saved_count += 1

            return AgentOutput(
                status="success",
                message=f"Strategy Complete. Generated {saved_count} revenue-ready keywords.",
                data={
                    "keywords_generated": saved_count,
                    "clusters": root_intents,
                    "next_step": "Ready for Writer"
                }
            )
            
        except Exception as e:
            error_msg = f"Strategist execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return AgentOutput(
                status="error",
                message=error_msg,
                data={}
            )

    async def _get_intent_roots(self, service: str) -> List[str]:
        """
        Uses LLM to brainstorm 5-10 distinct ways users ask for this service.
        Does NOT generate full keywords (no cities), just the 'Service' part.
        """
        system_prompt = "You are a Search Intent Analyst. Generate valid JSON lists of search intent roots."
        user_prompt = f"""
        We are targeting the service: "{service}".
        
        List 6 distinct "Search Intent Roots" (phrases users type) for this service.
        
        Rules:
        1. NO Location names (e.g., do not say "in Hamilton").
        2. Focus on "Problem Aware" terms (e.g., "emergency", "urgent", "cost").
        3. Include synonyms (e.g., for "Bail", use "Parole", "Home Detention", "EM Bail").
        4. Return ONLY a JSON list of strings.
        
        Example Output for 'Plumber': ["emergency plumber", "hot water cylinder repair", "blocked drain fix", "24/7 plumbing"]
        """
        
        try:
            # Use llm_gateway with asyncio.to_thread since generate_content is synchronous
            response_text = await asyncio.to_thread(
                llm_gateway.generate_content,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="gemini-2.5-flash",
                temperature=0.7,
                max_retries=3
            )
            
            # Clean and parse JSON
            content = response_text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                # Handle case where it's just ``` without json
                content = content.split("```")[1].split("```")[0]
            
            roots = json.loads(content)
            return roots if isinstance(roots, list) else [service]
        except Exception as e:
            self.logger.error(f"LLM Intent Generation Failed: {e}", exc_info=True)
            return [service, f"emergency {service}", f"cheap {service}"]