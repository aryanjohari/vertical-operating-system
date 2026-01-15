# backend/core/config.py
import yaml
import os
from typing import Dict, Any

class ConfigLoader:
    def __init__(self, profiles_dir="data/profiles"):
        self.profiles_dir = profiles_dir

    def load(self, niche: str) -> Dict[str, Any]:
        """
        Merges: Defaults -> Generated DNA -> Custom Overrides
        """
        # 1. System Defaults
        config = {"system_currency": "NZD", "timezone": "Pacific/Auckland"}
        
        profile_path = os.path.join(self.profiles_dir, niche)
        
        # 2. Safety Check
        if not os.path.exists(profile_path):
            return {"error": "Profile not found", "niche": niche}

        # 3. Load AI Generated DNA (The Strategist's work)
        gen_path = os.path.join(profile_path, "dna.generated.yaml")
        if os.path.exists(gen_path):
            with open(gen_path, 'r') as f:
                config.update(yaml.safe_load(f) or {})

        # 4. Load Human Overrides (Your Custom Settings) - These win.
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        if os.path.exists(custom_path):
            with open(custom_path, 'r') as f:
                config.update(yaml.safe_load(f) or {})
                
        return config