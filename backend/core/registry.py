# backend/core/registry.py

# --- 1. THE CODE REGISTRY (For the Kernel) ---
class AgentRegistry:
    """
    Defines WHERE the code lives for each agent.
    Format: "key": ("module_path", "ClassName")
    
    CRITICAL NOTE: 
    The 'key' must be a substring of the tasks sent by the Manager.
    Example: key "writer" matches task "write_pages".
    """
    DIRECTORY = {
        # --- MODULE: ONBOARDING ---
        "onboarding": ("backend.modules.onboarding.genesis", "OnboardingAgent"),

        # --- MODULE: APEX GROWTH (pSEO) ---
        # The Manager (Orchestrator)
        "manager": ("backend.modules.pseo.manager", "ManagerAgent"),
        
        # The Workers
        "scout": ("backend.modules.pseo.agents.scout", "ScoutAgent"),
        "strategist": ("backend.modules.pseo.agents.strategist", "StrategistAgent"), # NEW
        "write": ("backend.modules.pseo.agents.writer", "SeoWriterAgent"),
        "critic": ("backend.modules.pseo.agents.critic", "CriticAgent"),             # NEW
        "librarian": ("backend.modules.pseo.agents.librarian", "LibrarianAgent"),    # NEW
        "media": ("backend.modules.pseo.agents.media", "MediaAgent"),
        "utility": ("backend.modules.lead_gen.agents.utility", "UtilityAgent"),      # Cross-module logic
        "publish": ("backend.modules.pseo.agents.publisher", "PublisherAgent"),
        "analytics": ("backend.modules.pseo.agents.analytics", "AnalyticsAgent"),    # NEW

        # --- MODULE: APEX CONNECT (Lead Gen) ---
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