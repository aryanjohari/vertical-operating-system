# backend/modules/pseo/agents/strategist.py
import json
import os
import asyncio
import yaml
from datetime import datetime
from urllib.parse import urlparse, quote_plus
from playwright.async_api import async_playwright
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity
from backend.core.services.universal import UniversalScraper
from backend.core.services.llm_gateway import llm_gateway

class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Strategist")
        self.scraper = UniversalScraper()
        # Negative keywords to filter out irrelevant businesses (e.g., "Carpet Court")
        self.negative_keywords = ['carpet', 'flooring', 'store', 'shop']
        # Model selection for strategy tasks (lightweight model for brainstorming)
        self.model = "gemini-2.5-flash-lite"

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
        
        # 1. USE INJECTED CONFIG (DNA loaded by kernel)
        config = self.config
        
        # 2. DETERMINE STRATEGY SOURCE
        # Priority: Input Params > DNA Config > Auto-Discover > Fallback (Brainstorm)
        input_comps = input_data.params.get("competitors", [])
        dna_comps = config.get('modules', {}).get('local_seo', {}).get('competitor_urls', [])
        competitors = input_comps if input_comps else dna_comps
        
        # 3. HYBRID STRATEGY: Auto-discover if no competitors found
        if not competitors:
            self.log("🔍 No competitors found. Attempting auto-discovery via Google search...")
            discovered = await self._discover_competitors(config, project_id)
            if discovered:
                competitors = discovered
                # Save discovered competitors to DNA config for future runs
                await self._save_competitors_to_dna(project_id, competitors)
                self.log(f"✅ Discovered {len(competitors)} competitors and saved to DNA config")
        
        # 4. EXECUTE STRATEGY
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

        # Filter topics once (remove negative keywords)
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
            return AgentOutput(status="error", message="No valid topics after filtering negative keywords.")
        
        # Read services from config to get primary_keywords and context_keywords
        config = self.config
        # Services are at root level, not under identity
        services = config.get('services', [])
        
        # Extract all primary_keywords and context_keywords into pools
        primary_keywords_pool = []
        context_keywords_pool = []
        
        for service in services:
            # Support both old format (keywords) and new format (primary_keywords/context_keywords)
            if 'primary_keywords' in service:
                primary_keywords_pool.extend(service.get('primary_keywords', []))
            elif 'keywords' in service:
                # Legacy support: use first 2 as primary, rest as context
                keywords = service.get('keywords', [])
                if keywords:
                    primary_keywords_pool.extend(keywords[:2])
                    context_keywords_pool.extend(keywords[2:])
            
            if 'context_keywords' in service:
                context_keywords_pool.extend(service.get('context_keywords', []))
        
        if not primary_keywords_pool:
            return AgentOutput(status="error", message="No primary_keywords found in services. Please configure services with primary_keywords and context_keywords.")
        
        if not context_keywords_pool:
            self.log("⚠️ No context_keywords found. Using primary_keywords as fallback.")
            context_keywords_pool = primary_keywords_pool.copy()
        
        # Prepare anchor contexts for batch processing
        anchor_contexts = []
        for anchor in anchors:
            anchor_name = anchor['name']
            address = anchor['metadata'].get('address', 'Auckland')
            city = address.split(',')[-1].strip() if address else "Auckland"
            anchor_contexts.append({
                'name': anchor_name,
                'city': city,
                'anchor': anchor
            })
        
        # BATCH: Generate cluster objects for ALL anchors in one API call
        primary_kw_list = ", ".join(primary_keywords_pool[:20])  # Limit to avoid token overflow
        context_kw_list = ", ".join(context_keywords_pool[:30])
        locations_list = "\n".join([f"- {ctx['name']} in {ctx['city']}" for ctx in anchor_contexts])
        
        batch_prompt = f"""
        Role: SEO Strategist generating keyword clusters for local SEO.
        
        Business Context:
        - Primary Keywords (for H1/Title): {primary_kw_list}
        - Context Keywords (for Body/H2): {context_kw_list}
        - Number of Locations: {len(anchor_contexts)}
        
        Task: For each location below, generate a keyword cluster. Pick 1 primary keyword and 3 context keywords from the provided lists that best fit the location.
        
        Locations:
        {locations_list}
        
        Requirements:
        - Primary keyword must be a high-intent, conversion-focused phrase that includes the location
        - Context keywords should be semantically related and include the location naturally
        - Generate a SEO-friendly slug from the primary keyword
        - NO placeholders like [city name] or {{variables}}
        
        Return a JSON object where keys are EXACT location names (must match exactly) and values are cluster objects with this structure:
        {{
            "primary": "Complete primary keyword phrase with location",
            "safety": ["Context keyword 1 with location", "Context keyword 2 with location", "Context keyword 3 with location"],
            "slug": "seo-friendly-slug-from-primary-keyword"
        }}
        
        CRITICAL: Use the EXACT location names from the list above as JSON keys. Do not modify, shorten, or change the location names.
        
        Example format: {{
            "{anchor_contexts[0]['name']}": {{
                "primary": "Bail Support near {anchor_contexts[0]['name']}",
                "safety": ["Emergency Bail Services {anchor_contexts[0]['city']}", "Weekend Court Lawyer {anchor_contexts[0]['name']}", "Urgent Bail Help {anchor_contexts[0]['city']}"],
                "slug": "bail-support-{anchor_contexts[0]['name'].lower().replace(' ', '-')}"
            }}
        }}
        """
        
        try:
            self.log(f"🧠 Generating keyword clusters for {len(anchor_contexts)} anchors in one batch call...")
            response_text = llm_gateway.generate_content(
                system_prompt="You are an SEO keyword cluster generator. Always return valid JSON objects with location names as keys and cluster objects as values. Each cluster must have 'primary' (string), 'safety' (array of 3 strings), and 'slug' (string) fields.",
                user_prompt=batch_prompt,
                model=self.model,
                temperature=0.7,
                max_retries=3
            )
            
            # Clean JSON response
            clean_json = response_text.replace('```json', '').replace('```', '').strip()
            if "{" not in clean_json:
                raise ValueError("AI did not return a JSON object")
            
            clusters_by_location = json.loads(clean_json)
            
            if not isinstance(clusters_by_location, dict):
                raise ValueError("Response is not a JSON object")
            
            # Log what keys the LLM returned for debugging
            llm_keys = list(clusters_by_location.keys())
            self.log(f"📋 LLM returned clusters for {len(llm_keys)} locations: {llm_keys[:5]}...")
            
            created_count = 0
            
            # Process clusters for each anchor
            for anchor_ctx in anchor_contexts:
                anchor_name = anchor_ctx['name']
                anchor = anchor_ctx['anchor']
                city = anchor_ctx['city']
                
                # Get cluster for this anchor with flexible matching
                cluster_data = clusters_by_location.get(anchor_name)
                
                # Try case-insensitive exact match
                if not cluster_data:
                    for key in clusters_by_location.keys():
                        if key.lower() == anchor_name.lower():
                            cluster_data = clusters_by_location[key]
                            self.log(f"✅ Matched '{anchor_name}' to LLM key '{key}' (case-insensitive)")
                            break
                
                # Try partial match (anchor name contains key or vice versa)
                if not cluster_data:
                    anchor_lower = anchor_name.lower()
                    for key in clusters_by_location.keys():
                        key_lower = key.lower()
                        # Check if anchor name contains key or key contains anchor name
                        if anchor_lower in key_lower or key_lower in anchor_lower:
                            cluster_data = clusters_by_location[key]
                            self.log(f"✅ Matched '{anchor_name}' to LLM key '{key}' (partial match)")
                            break
                
                # Try matching by removing common suffixes/prefixes
                if not cluster_data:
                    anchor_clean = anchor_name.lower().replace('old ', '').replace('new ', '').strip()
                    for key in clusters_by_location.keys():
                        key_clean = key.lower().replace('old ', '').replace('new ', '').strip()
                        if anchor_clean == key_clean or anchor_clean in key_clean or key_clean in anchor_clean:
                            cluster_data = clusters_by_location[key]
                            self.log(f"✅ Matched '{anchor_name}' to LLM key '{key}' (normalized match)")
                            break
                
                if not cluster_data:
                    self.log(f"⚠️ No cluster returned for '{anchor_name}'. Available keys: {llm_keys}")
                    continue
                
                # Validate cluster structure
                if not isinstance(cluster_data, dict):
                    self.log(f"⚠️ Invalid cluster format for {anchor_name}, skipping...")
                    continue
                
                primary = cluster_data.get('primary', '').strip()
                safety = cluster_data.get('safety', [])
                slug = cluster_data.get('slug', '').strip()
                
                if not primary:
                    self.log(f"⚠️ Missing primary keyword for {anchor_name}, skipping...")
                    continue
                
                if not isinstance(safety, list) or len(safety) < 3:
                    self.log(f"⚠️ Invalid safety keywords for {anchor_name}, skipping...")
                    continue
                
                # Generate slug if not provided
                if not slug:
                    slug = primary.lower().replace(' ', '-').replace('near', '').replace('--', '-')
                
                # Find matching cluster name for this keyword
                cluster_name = filtered_topics[0][0]  # Default to first cluster
                for cluster, topic in filtered_topics:
                    if topic.lower() in primary.lower():
                        cluster_name = cluster
                        break
                
                # Store cluster object in seo_keyword entity
                kw_id = f"kw_{hash(primary + str(anchor['id']))}"
                entity = Entity(
                    id=kw_id,
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="seo_keyword",
                    name=primary,  # Use primary keyword as the name
                    metadata={
                        "target_anchor": anchor_name,
                        "city": city,
                        "cluster": cluster_name,  # Critical for Librarian
                        "source_strategy": strategy_source,
                        "status": "pending",
                        "cluster_data": {
                            "primary": primary,
                            "safety": safety,
                            "slug": slug
                        }
                    },
                    created_at=datetime.now()
                )
                # Explicitly pass project_id for clarity and reliability
                if memory.save_entity(entity, project_id=project_id):
                    created_count += 1
                
                self.log(f"✅ Generated cluster for {anchor_name}: primary='{primary}', safety={len(safety)} keywords")
        
        except Exception as e:
            self.log(f"⚠️ Error generating keyword clusters in batch: {e}")
            return AgentOutput(status="error", message=f"Keyword cluster generation failed: {e}")
        
        return AgentOutput(
            status="success", 
            message=f"Strategy deployed ({strategy_source}). Generated {created_count} keywords across {len(topics)} clusters.",
            data={"clusters": [t['cluster'] for t in topics]}
        )

    def _filter_government_sites(self, url: str) -> bool:
        """Filter out government and educational sites."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Government domain patterns
            gov_patterns = [
                '.gov',
                '.govt.nz',
                '.ac.nz',  # Academic institutions
                'nzta.govt.nz',
                'justice.govt.nz',
                'police.govt.nz',
                'courts.govt.nz',
                'parliament.nz',
            ]
            
            for pattern in gov_patterns:
                if pattern in domain:
                    return False  # Filter out government sites
            
            return True  # Keep non-government sites
        except Exception:
            return True  # If parsing fails, keep it (better safe than sorry)

    async def _discover_competitors(self, config: dict, project_id: str) -> list:
        """
        Auto-discover competitors via Google search.
        Uses niche + location to find top-ranking competitors.
        """
        try:
            # Build search query from config
            niche = config.get('identity', {}).get('niche', '')
            business_name = config.get('identity', {}).get('business_name', '')
            
            # Get location from anchor locations or config
            anchors = memory.get_entities(
                tenant_id=self.user_id,
                entity_type="anchor_location",
                project_id=project_id,
                limit=1
            )
            city = "Auckland"  # Default
            if anchors:
                address = anchors[0].get('metadata', {}).get('address', '')
                if address:
                    city = address.split(',')[-1].strip()
            
            # Build search query: "niche + city" (e.g., "bail lawyer Auckland")
            if niche:
                search_query = f"{niche} {city}"
            elif business_name:
                # Extract service type from business name if niche not available
                search_query = f"{business_name} {city}"
            else:
                self.log("⚠️ Cannot build search query: missing niche and business_name")
                return []
            
            self.log(f"🔍 Searching Google for: '{search_query}'")
            
            # Search Google using Playwright
            competitor_urls = []
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-http2', '--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080}
                )
                page = await context.new_page()
                
                # Search Google
                search_url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=10"
                try:
                    await page.goto(search_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)  # Wait for results to load
                    
                    # Extract search result URLs
                    # Google search results are in <a> tags with href starting with /url?q=
                    links = await page.evaluate("""
                        () => {
                            const results = [];
                            // Get organic search results (not ads)
                            const resultLinks = document.querySelectorAll('div[data-sokoban-container] a[href*="/url?q="], div.g a[href*="/url?q="]');
                            for (let link of resultLinks) {
                                const href = link.getAttribute('href');
                                if (href && href.includes('/url?q=')) {
                                    // Extract actual URL from Google redirect
                                    const urlMatch = href.match(/[?&]q=([^&]+)/);
                                    if (urlMatch) {
                                        try {
                                            const decodedUrl = decodeURIComponent(urlMatch[1]);
                                            // Filter out Google's own pages
                                            if (!decodedUrl.includes('google.com') && 
                                                !decodedUrl.includes('youtube.com/watch') &&
                                                decodedUrl.startsWith('http')) {
                                                results.push(decodedUrl);
                                            }
                                        } catch (e) {
                                            // Skip invalid URLs
                                        }
                                    }
                                }
                            }
                            return results;
                        }
                    """)
                    
                    # Filter and deduplicate
                    seen = set()
                    for url in links:
                        if url and url not in seen:
                            # Filter out government sites
                            if self._filter_government_sites(url):
                                competitor_urls.append(url)
                                seen.add(url)
                                if len(competitor_urls) >= 10:  # Limit to top 10
                                    break
                    
                    await browser.close()
                    
                except Exception as e:
                    self.log(f"⚠️ Error during Google search: {e}")
                    await browser.close()
                    return []
            
            self.log(f"✅ Discovered {len(competitor_urls)} competitor URLs")
            return competitor_urls[:10]  # Return top 10
            
        except Exception as e:
            self.log(f"⚠️ Competitor discovery failed: {e}")
            return []

    async def _save_competitors_to_dna(self, project_id: str, competitors: list):
        """Save discovered competitors to dna.custom.yaml for future runs."""
        try:
            from backend.core.config import ConfigLoader
            config_loader = ConfigLoader()
            profile_path = os.path.join(config_loader.profiles_dir, project_id)
            
            # Ensure directory exists
            os.makedirs(profile_path, exist_ok=True)
            
            # Load existing custom config if it exists
            custom_path = os.path.join(profile_path, "dna.custom.yaml")
            existing_config = {}
            if os.path.exists(custom_path):
                try:
                    with open(custom_path, 'r') as f:
                        existing_config = yaml.safe_load(f) or {}
                except Exception as e:
                    self.log(f"⚠️ Error reading existing custom config: {e}")
            
            # Update competitor URLs in config
            if 'modules' not in existing_config:
                existing_config['modules'] = {}
            if 'local_seo' not in existing_config['modules']:
                existing_config['modules']['local_seo'] = {}
            
            existing_config['modules']['local_seo']['competitor_urls'] = competitors
            
            # Write updated config
            with open(custom_path, 'w') as f:
                yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)
            
            self.log(f"✅ Saved {len(competitors)} competitors to DNA config")
            
        except Exception as e:
            self.log(f"⚠️ Failed to save competitors to DNA config: {e}")
            # Don't fail the whole operation if saving fails