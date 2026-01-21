# backend/core/config.py
import yaml
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("Apex.Config")

class ConfigLoader:
    def __init__(self, profiles_dir="data/profiles"):
        self.profiles_dir = profiles_dir
        self.logger = logging.getLogger("Apex.Config")

    def load(self, niche: str) -> Dict[str, Any]:
        """
        Merges: Defaults -> Generated DNA -> Custom Overrides
        """
        self.logger.debug(f"Loading config for niche: {niche}")
        
        # 1. System Defaults
        config = {"system_currency": "NZD", "timezone": "Pacific/Auckland"}
        
        profile_path = os.path.join(self.profiles_dir, niche)
        
        # 2. Safety Check
        if not os.path.exists(profile_path):
            self.logger.warning(f"Profile path not found: {profile_path} for niche: {niche}")
            return {"error": "Profile not found", "niche": niche}

        # 3. Load AI Generated DNA (The Strategist's work)
        gen_path = os.path.join(profile_path, "dna.generated.yaml")
        if os.path.exists(gen_path):
            try:
                with open(gen_path, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    config.update(loaded_config)
                    self.logger.debug(f"Successfully loaded generated DNA from {gen_path}")
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing error in {gen_path}: {e}")
            except FileNotFoundError as e:
                self.logger.error(f"File not found when trying to read {gen_path}: {e}")
            except PermissionError as e:
                self.logger.error(f"Permission denied when reading {gen_path}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error reading {gen_path}: {e}")

        # 4. Load Human Overrides (Your Custom Settings) - These win.
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        if os.path.exists(custom_path):
            try:
                with open(custom_path, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    config.update(loaded_config)
                    self.logger.debug(f"Successfully loaded custom overrides from {custom_path}")
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing error in {custom_path}: {e}")
            except FileNotFoundError as e:
                self.logger.error(f"File not found when trying to read {custom_path}: {e}")
            except PermissionError as e:
                self.logger.error(f"Permission denied when reading {custom_path}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error reading {custom_path}: {e}")
        
        self.logger.debug(f"Config loaded successfully for niche: {niche}")
        return config