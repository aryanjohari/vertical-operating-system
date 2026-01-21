# backend/core/registry.py

# --- 1. THE CODE REGISTRY (For the Kernel) ---
class AgentRegistry:
    """
    Defines WHERE the code lives for each agent.
    Format: "key": ("module_path", "ClassName")
    
    CRITICAL NOTE: 
    The 'key' should match the task name exactly for clarity.
    System agents (like onboarding) bypass DNA loading because they create the config.
    """
    DIRECTORY = {
        # --- MODULE: ONBOARDING (System Agent - Creates DNA) ---
        "onboarding": ("backend.modules.onboarding.genesis", "OnboardingAgent"),

        # --- MODULE: APEX GROWTH (pSEO) ---
        # The Manager (Orchestrator)
        "manager": ("backend.modules.pseo.manager", "ManagerAgent"),
        
        # The Workers (Task names match Manager's _execute_task calls)
        "scout_anchors": ("backend.modules.pseo.agents.scout", "ScoutAgent"),
        "strategist_run": ("backend.modules.pseo.agents.strategist", "StrategistAgent"),
        "write_pages": ("backend.modules.pseo.agents.writer", "SeoWriterAgent"),
        "critic_review": ("backend.modules.pseo.agents.critic", "CriticAgent"),
        "librarian_link": ("backend.modules.pseo.agents.librarian", "LibrarianAgent"),
        "enhance_media": ("backend.modules.pseo.agents.media", "MediaAgent"),
        "enhance_utility": ("backend.modules.lead_gen.agents.utility", "UtilityAgent"),
        "publish": ("backend.modules.pseo.agents.publisher", "PublisherAgent"),
        "analytics_audit": ("backend.modules.pseo.agents.analytics", "AnalyticsAgent"),

        # --- MODULE: APEX CONNECT (Lead Gen) - COMMENTED OUT ---
        # "twilio": ("backend.modules.lead_gen.agents.twilio", "TwilioAgent"),
    }

# --- 2. THE FEATURE REGISTRY (For the Frontend) ---
class ModuleManifest:
    """
    The App Store Catalog.
    """
    CATALOG = {
        "local_seo": {
            "name": "Apex Growth (pSEO)",
            "description": "Dominate Google Maps with auto-generated location pages.",
            # Updated Agent List
            "agents": ["scout", "strategist", "writer", "critic", "librarian", "media", "publisher", "analytics"], 
            "config_required": [
                "anchor_entities",       
                "geo_scope"
            ]
        },
        "lead_gen": {
            "name": "Apex Connect (Lead Gen)",
            "description": "24/7 Lead Capture & Voice Routing.",
            "agents": ["utility", "twilio"],
            "config_required": [
                "operations.voice_agent.forwarding_number"          
            ]
        }
    }

    @staticmethod
    def get_user_menu():
        return {key: data['name'] for key, data in ModuleManifest.CATALOG.items()}