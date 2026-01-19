import yaml
import asyncio
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Manager")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        The Brain of the Operation.
        Monitors the entire pipeline from Scout -> Publish.
        """
        user_id = input_data.user_id
        
        # 1. GET ALL ASSETS (The State of the World)
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location")
        keywords = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword")
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft")

        # 2. ANALYZE PAGE STATES
        # Check metadata to see which stage of assembly the pages are in
        pages_with_images = len([p for p in pages if 'image_url' in p['metadata']])
        pages_with_tools = len([p for p in pages if 'has_tool' in p['metadata']])
        # Assuming the Publisher agent updates status to 'published' or 'live'
        pages_published = len([p for p in pages if p['metadata'].get('status') in ['published', 'live']])

        # Comprehensive Stats for Dashboard
        stats = {
            "Locations": len(anchors),
            "Keywords": len(keywords),
            "Drafts": len(pages),
            "Enhanced (Img)": pages_with_images,
            "Interactive (JS)": pages_with_tools,
            "Live": pages_published
        }
        
        # 3. LOAD DNA
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
            
        try:
            with open(project['dna_path'], 'r') as f:
                dna = yaml.safe_load(f)
        except Exception:
            return AgentOutput(status="error", message="Corrupt DNA file.")

        # 4. DECIDE NEXT STEP
        return await self.execute_pseo_strategy(user_id, dna, stats)

    async def execute_pseo_strategy(self, user_id, dna, stats):
        """
        The 5-Step Production Pipeline
        """
        
        # --- PHASE 1: SCOUT (Find Locations) ---
        if stats["Locations"] == 0:
            queries = self._generate_search_queries(dna)
            return AgentOutput(
                status="action_required",
                message="Phase 1: Location Scouting",
                data={
                    "step": "1_scout",
                    "description": "I need to find target locations (Courts, Prisons) to build the database.",
                    "stats": stats,
                    "action_label": "Launch Scout",
                    "next_task": "scout_anchors", 
                    "next_params": {"queries": queries}
                }
            )

        # --- PHASE 2: KEYWORDS (Generate Topics) ---
        # If we have locations but few keywords
        if stats["Keywords"] < (stats["Locations"] * 2): 
            return AgentOutput(
                status="action_required",
                message="Phase 2: Keyword Research",
                data={
                    "step": "2_keywords",
                    "description": "Generating intent-based keywords for our locations.",
                    "stats": stats,
                    "action_label": "Generate Keywords",
                    "next_task": "seo_keyword", # Check your Kernel routing key!
                    "next_params": {}
                }
            )

        # --- PHASE 3: WRITING (Create Text Drafts) ---
        # If we have keywords but they aren't written yet
        # (Lenient check: If we have < 1 draft, let's start writing)
        if stats["Drafts"] < 1: 
            return AgentOutput(
                status="action_required",
                message="Phase 3: Content Production",
                data={
                    "step": "3_writing",
                    "description": "Writing high-converting HTML landing page drafts.",
                    "stats": stats,
                    "action_label": "Start Writer",
                    "next_task": "write_pages", # Routes to SeoWriterAgent
                    "next_params": {}
                }
            )

        # --- PHASE 4: ENHANCEMENT (Images & Tools) ---
        
        # Step A: Images (Media Agent)
        # If we have drafts, but some lack images
        if stats["Drafts"] > stats["Enhanced (Img)"]:
            return AgentOutput(
                status="action_required",
                message="Phase 4a: Visual Enhancement",
                data={
                    "step": "4a_media",
                    "description": "Fetching relevant images from Unsplash for our pages.",
                    "stats": stats,
                    "action_label": "Fetch Images",
                    "next_task": "enhance_media", # Routes to MediaAgent
                    "next_params": {}
                }
            )
            
        # Step B: Lead Magnets (Utility Agent)
        # If we have images, but they lack calculators/tools
        if stats["Enhanced (Img)"] > stats["Interactive (JS)"]:
            return AgentOutput(
                status="action_required",
                message="Phase 4b: Lead Magnets",
                data={
                    "step": "4b_utility",
                    "description": "Coding custom JavaScript calculators to capture leads.",
                    "stats": stats,
                    "action_label": "Build Tools",
                    "next_task": "enhance_utility", # Routes to UtilityAgent
                    "next_params": {}
                }
            )

        # --- PHASE 5: PUBLISHING (WordPress/Vercel) ---
        # If we have fully enhanced pages that aren't live yet
        if stats["Interactive (JS)"] > stats["Live"]:
            return AgentOutput(
                status="action_required",
                message="Phase 5: Publishing",
                data={
                    "step": "5_publish",
                    "description": "Pushing production-ready assets to the CMS.",
                    "stats": stats,
                    "action_label": "Publish to WordPress",
                    "next_task": "publish", # Routes to PublisherAgent
                    "next_params": {}
                }
            )

        # --- ALL SYSTEMS GO ---
        return AgentOutput(
            status="complete", 
            message="All Systems Live. Monitoring for new opportunities.", 
            data={"step": "active", "stats": stats}
        )

    def _generate_search_queries(self, dna):
        """Helper to read DNA and make search strings"""
        try:
            anchors = dna['scout_rules']['anchor_entities']
            cities = dna['scout_rules']['geo_scope']['cities']
            queries = []
            for city in cities:
                for anchor in anchors:
                    queries.append(f"{anchor} in {city}")
            return queries
        except KeyError:
            return ["court in auckland"]