# backend/core/registry.py

# --- 1. THE CODE REGISTRY (For the Kernel) ---
class AgentRegistry:
    """
    Defines WHERE the code lives for each agent.
    Format: "key": ("module_path", "ClassName")
    """
    DIRECTORY = {
        "onboarding": ("backend.agents.onboarding", "OnboardingAgent"),
        "scout": ("backend.agents.scout", "ScoutAgent"),
        "manager": ("backend.agents.manager", "ManagerAgent"),
        "seo_keyword": ("backend.agents.seo_keyword", "SeoKeywordAgent"),
        "seo_writer": ("backend.agents.seo_writer", "SeoWriterAgent"),
        "media": ("backend.agents.media", "MediaAgent"),
        "utility": ("backend.agents.utility", "UtilityAgent"),
        "publisher": ("backend.agents.publisher", "PublisherAgent"),
        # Future Agents (Commented out until created)
        # "voice_worker": ("backend.agents.voice", "VoiceAgent"),
    }

# --- 2. THE FEATURE REGISTRY (For the Frontend) ---
class ModuleManifest:
    """
    The App Store Catalog.
    - Frontend uses this to show Checkboxes.
    - Genesis uses this to know what questions to ask.
    """
    CATALOG = {
        "local_seo": {
            "name": "Local Dominator (pSEO)",
            "description": "Dominate Google Maps with auto-generated location pages.",
            "agents": ["scout", "writer"], 
            "config_required": [
                "anchor_entities",       
                "geo_scope",             
                "cms_settings.url",      
                "cms_settings.username", 
                "cms_settings.password"  
            ]
        },
        "voice_assistant": {
            "name": "24/7 Voice Guard",
            "description": "AI Receptionist to answer calls.",
            "agents": ["voice_worker"],
            "config_required": [
                "operations.voice_agent.forwarding_number",
                "operations.voice_agent.greeting"          
            ]
        }
    }

    @staticmethod
    def get_user_menu():
        return {key: data['name'] for key, data in ModuleManifest.CATALOG.items()}