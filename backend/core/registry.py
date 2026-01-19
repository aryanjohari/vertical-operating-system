# backend/core/registry.py

# --- 1. THE CODE REGISTRY (For the Kernel) ---
class AgentRegistry:
    """
    Defines WHERE the code lives for each agent.
    Format: "key": ("module_path", "ClassName")
    """
    DIRECTORY = {
        # --- MODULE: ONBOARDING ---
        "onboarding": ("backend.modules.onboarding.genesis", "OnboardingAgent"),

        # --- MODULE: APEX GROWTH (pSEO) ---
        # The Manager (Orchestrator)
        "manager": ("backend.modules.pseo.manager", "ManagerAgent"),
        # The Workers
        "scout": ("backend.modules.pseo.agents.scout", "ScoutAgent"),
        "seo_keyword": ("backend.modules.pseo.agents.keyword", "SeoKeywordAgent"),
        "seo_writer": ("backend.modules.pseo.agents.writer", "SeoWriterAgent"),
        "media": ("backend.modules.pseo.agents.media", "MediaAgent"),
        "publisher": ("backend.modules.pseo.agents.publisher", "PublisherAgent"),

        # --- MODULE: APEX CONNECT (Lead Gen) ---
        "utility": ("backend.modules.lead_gen.agents.utility", "UtilityAgent"),
        "twilio": ("backend.modules.lead_gen.agents.twilio", "TwilioAgent"),
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
            "agents": ["scout", "seo_writer", "publisher"], 
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