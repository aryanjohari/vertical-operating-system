# backend/core/registry.py
from typing import Any, Dict, List

# --- 1. THE CODE REGISTRY (For the Kernel) ---
def _entry(module_path: str, class_name: str, *, is_system_agent: bool = False, is_heavy: bool = False, is_system_agent_needs_context: bool = False) -> Dict[str, Any]:
    """Build a registry entry with metadata."""
    return {
        "module_path": module_path,
        "class_name": class_name,
        "is_system_agent": is_system_agent,
        "is_heavy": is_heavy,
        "is_system_agent_needs_context": is_system_agent_needs_context,
    }


class AgentRegistry:
    """
    Defines WHERE the code lives for each agent and metadata (system/heavy).
    Format: "key": {"module_path", "class_name", "is_system_agent", "is_heavy", "is_system_agent_needs_context"}
    """
    DIRECTORY = {
        "onboarding": _entry("backend.modules.onboarding.genesis", "OnboardingAgent", is_system_agent=True),
        "manager": _entry("backend.modules.pseo.manager", "ManagerAgent"),
        "scout_anchors": _entry("backend.modules.pseo.agents.scout", "ScoutAgent", is_heavy=True),
        "strategist_run": _entry("backend.modules.pseo.agents.strategist", "StrategistAgent", is_heavy=True),
        "write_pages": _entry("backend.modules.pseo.agents.writer", "WriterAgent", is_heavy=True),
        "critic_review": _entry("backend.modules.pseo.agents.critic", "CriticAgent", is_heavy=True),
        "librarian_link": _entry("backend.modules.pseo.agents.librarian", "LibrarianAgent", is_heavy=True),
        "enhance_media": _entry("backend.modules.pseo.agents.media", "MediaAgent", is_heavy=True),
        "enhance_utility": _entry("backend.modules.lead_gen.agents.utility", "UtilityAgent"),
        "publish": _entry("backend.modules.pseo.agents.publisher", "PublisherAgent", is_heavy=True),
        "analytics_audit": _entry("backend.modules.pseo.agents.analytics", "AnalyticsAgent"),
        "lead_gen_manager": _entry("backend.modules.lead_gen.manager", "LeadGenManager"),
        "sales_agent": _entry("backend.modules.lead_gen.agents.sales", "SalesAgent", is_heavy=True),
        "reactivator_agent": _entry("backend.modules.lead_gen.agents.reactivator", "ReactivatorAgent", is_heavy=True),
        "lead_scorer": _entry("backend.modules.lead_gen.agents.scorer", "LeadScorerAgent"),
        "system_ops_manager": _entry("backend.modules.system_ops.manager", "SystemOpsManager"),
        "health_check": _entry("backend.modules.system_ops.agents.sentinel", "SentinelAgent", is_system_agent=True),
        "log_usage": _entry("backend.modules.system_ops.agents.accountant", "AccountantAgent", is_system_agent=True, is_system_agent_needs_context=True),
        "cleanup": _entry("backend.modules.system_ops.agents.janitor", "JanitorAgent", is_system_agent=True),
    }

    # Manager actions that should run as heavy (background); key = task name, value = list of action strings
    HEAVY_ACTIONS_BY_TASK: Dict[str, List[str]] = {
        "lead_gen_manager": ["lead_received", "ignite_reactivation", "instant_call", "process_scheduled_bridges"],
    }


# --- 2. THE FEATURE REGISTRY (For the Frontend) ---
class ModuleManifest:
    """The App Store Catalog."""
    CATALOG = {
        "local_seo": {
            "name": "Apex Growth (pSEO)",
            "description": "Dominate Google Maps with auto-generated location pages.",
            "agents": ["scout", "strategist", "writer", "critic", "librarian", "media", "publisher", "analytics"],
            "config_required": ["anchor_entities", "geo_scope"],
        },
        "lead_gen": {
            "name": "Apex Connect (Lead Gen)",
            "description": "24/7 Lead Capture & Voice Routing.",
            "agents": ["utility", "twilio"],
            "config_required": ["operations.voice_agent.forwarding_number"],
        },
    }

    @staticmethod
    def get_user_menu():
        return {key: data["name"] for key, data in ModuleManifest.CATALOG.items()}
