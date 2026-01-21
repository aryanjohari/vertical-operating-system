# backend/modules/pseo/agents/strategist.py
import json
import os
import asyncio
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity
from backend.core.services.universal import UniversalScraper
from backend.core.services.llm_gateway import llm_gateway
from backend.core.config import ConfigLoader

class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Strategist")
        self.scraper = UniversalScraper()
        self.config_loader = ConfigLoader()
        # Negative keywords to filter out irrelevant businesses (e.g., "Carpet Court")
        self.negative_keywords = ['carpet', 'flooring', 'store', 'shop']
        # Model selection for strategy tasks (lightweight model for brainstorming)
        self.model = "gemini-2.5-flash-lite"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
        
        project_id = project['project_id']
        
        # 1. LOAD CONFIG (DNA)
        config = self.config_loader.load(project_id)
        
        # 2. DETERMINE STRATEGY SOURCE
        # Priority: Input Params > DNA Config > Fallback (Brainstorm)
        input_comps = input_data.params.get("competitors", [])
        dna_comps = config.get('modules', {}).get('local_seo', {}).get('competitor_urls', [])
        competitors = input_comps if input_comps else dna_comps
        
        # 3. EXECUTE STRATEGY
        if competitors:
            return await self._execute_competitor_analysis(user_id, project_id, competitors)
        else:
            return await self._execute_brainstorming(user_id, project_id, config)

    async def _execute_competitor_analysis(self, user_id, project_id, competitors):
        """Mode A: Steal Strategy from Rivals"""
        self.log(f"🕵️ Spying on {len(competitors)} rivals...")
        
        scraped_data = []
        for url in competitors:
            try:
                data = await self.scraper.scrape(url)
                if data.get('content'):
                    # Truncate to save context window
                    scraped_data.append(f"Source: {url}\nContent: {data['content'][:5000]}")
            except Exception as e:
                self.log(f"⚠️ Failed to scrape {url}: {e}")

        if not scraped_data:
             return AgentOutput(status="warning", message="Scraping failed. Defaulting to brainstorming.")

        context_str = "\n---\n".join(scraped_data)
        
        prompt = f"""
        Role: SEO Strategist.
        Task: Analyze these competitor pages. Find 5 "Topic Clusters" (High-level themes) we should cover.
        Output: JSON Array of objects: {{ "cluster": "Theme Name", "topic": "Specific Service Keyword" }}
        
        COMPETITOR DATA:
        {context_str}
        """
        return await self._generate_and_save(user_id, project_id, prompt, "competitor_gap")

    async def _execute_brainstorming(self, user_id, project_id, config):
        """Mode B: Generate Strategy from Niche Identity"""
        self.log("🧠 No competitors found. Switching to Brainstorm Mode.")
        
        niche = config.get('identity', {}).get('niche', 'General Service')
        services = config.get('identity', {}).get('services', [])
        wisdom = memory.query_context(tenant_id=user_id, query="core services", project_id=project_id)
        
        prompt = f"""
        Role: SEO Strategist for {niche}.
        Context: {wisdom}
        Known Services: {services}
        Task: Create 5 "Topic Clusters" for local SEO domination.
        Output: JSON Array of objects: {{ "cluster": "Theme Name", "topic": "Specific Service Keyword" }}
        """
        return await self._generate_and_save(user_id, project_id, prompt, "brainstorm")

    async def _generate_and_save(self, user_id, project_id, prompt, strategy_source):
        try:
            response_text = llm_gateway.generate_content(
                system_prompt="You are an SEO strategist. Always return valid JSON arrays.",
                user_prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_retries=3
            )
            # Robust JSON cleaning
            clean_json = response_text.replace('```json', '').replace('```', '').strip()
            if "[" not in clean_json: raise ValueError("AI did not return a list")
            
            topics = json.loads(clean_json)
        except Exception as e:
            return AgentOutput(status="error", message=f"AI Strategy Failed: {e}")

        # Map Topics to Anchors (scoped to project)
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        if not anchors:
            return AgentOutput(status="error", message="No Anchors found. Run Scout first.")

        created_count = 0
        
        # Generate actual keywords for each anchor + topic combination
        for anchor in anchors:
            anchor_name = anchor['name']
            address = anchor['metadata'].get('address', 'Auckland')
            city = address.split(',')[-1].strip() if address else "Auckland"
            
            # Filter topics for this anchor
            filtered_topics = []
            for item in topics:
                cluster_name = item.get('cluster', 'General')
                topic_name = item.get('topic', 'Service')
                
                # Filter out keywords containing negative keywords (e.g., "Carpet Court")
                if any(neg_kw.lower() in topic_name.lower() for neg_kw in self.negative_keywords):
                    self.log(f"⚠️ Filtered out topic containing negative keyword: {topic_name}")
                    continue
                
                filtered_topics.append((cluster_name, topic_name))
            
            if not filtered_topics:
                continue
            
            # Generate actual keywords using AI for this specific anchor
            topics_str = ", ".join([t[1] for t in filtered_topics])
            prompt = f"""
            Role: SEO Strategist generating keywords for local SEO.
            
            Business Context:
            - Services/Topics: {topics_str}
            - Location: {anchor_name} in {city}
            
            Task: Generate 5 high-intent SEO keywords that combine the services/topics with the specific location "{anchor_name}" in {city}.
            
            Requirements:
            - Each keyword must be a complete, ready-to-use search phrase
            - Include the location naturally (e.g., "Bail Support near {anchor_name}", "Emergency Bail Services {city}")
            - Focus on high-intent, conversion-focused phrases
            - NO placeholders like [city name] or {{variables}}
            - Each keyword should be specific to {anchor_name} in {city}
            
            Return ONLY a JSON array of strings (actual complete keywords).
            Example format: ["Bail Support near {anchor_name}", "Emergency Bail Services {city}", "Fast Bail Bonds near {anchor_name}", ...]
            """
            
            try:
                self.log(f"🧠 Generating keywords for {anchor_name}...")
                response_text = llm_gateway.generate_content(
                    system_prompt="You are an SEO keyword generator. Always return valid JSON arrays of strings.",
                    user_prompt=prompt,
                    model=self.model,
                    temperature=0.7,
                    max_retries=3
                )
                
                # Clean JSON response
                clean_json = response_text.replace('```json', '').replace('```', '').strip()
                if "[" not in clean_json:
                    self.log(f"⚠️ Invalid response format for {anchor_name}, skipping...")
                    continue
                
                keywords = json.loads(clean_json)
                
                if not isinstance(keywords, list):
                    self.log(f"⚠️ Invalid response type for {anchor_name}, skipping...")
                    continue
                
                # Save each keyword
                for kw in keywords:
                    if not kw or not isinstance(kw, str):
                        continue
                    
                    kw_name = kw.strip()
                    
                    # Find matching cluster for this keyword (map back to original topic)
                    # Use the first topic as default cluster, or try to match by topic name
                    cluster_name = filtered_topics[0][0]  # Default to first cluster
                    for cluster, topic in filtered_topics:
                        if topic.lower() in kw_name.lower():
                            cluster_name = cluster
                            break
                    
                    kw_id = f"kw_{hash(kw_name + str(anchor['id']))}"
                    entity = Entity(
                        id=kw_id,
                        tenant_id=user_id,
                        project_id=project_id,
                        entity_type="seo_keyword",
                        name=kw_name,
                        metadata={
                            "target_anchor": anchor_name,
                            "city": city,
                            "cluster": cluster_name,  # Critical for Librarian
                            "source_strategy": strategy_source,
                            "status": "pending"
                        },
                        created_at=datetime.now()
                    )
                    # Explicitly pass project_id for clarity and reliability
                    if memory.save_entity(entity, project_id=project_id):
                        created_count += 1
                
                self.log(f"✅ Generated {len(keywords)} keywords for {anchor_name}")
                
            except Exception as e:
                self.log(f"⚠️ Error generating keywords for {anchor_name}: {e}")
                continue
        
        return AgentOutput(
            status="success", 
            message=f"Strategy deployed ({strategy_source}). Generated {created_count} keywords across {len(topics)} clusters.",
            data={"clusters": [t['cluster'] for t in topics]}
        )