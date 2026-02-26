# backend/core/config.py
import time
import yaml
import os
import logging
from typing import Dict, Any, Optional, Tuple
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

logger = logging.getLogger("Apex.Config")

# Environment Variables Settings (using Pydantic BaseSettings)
# Calculate project root (three levels up from backend/core/config.py) for .env file path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILE_PATH = os.path.join(_BASE_DIR, ".env")

# Ensure .env is loaded into environment before Pydantic Settings reads it
# This is critical when called from threads (asyncio.to_thread)
load_dotenv(dotenv_path=_ENV_FILE_PATH, override=True)

# Debug: Verify .env was loaded
_env_key = os.getenv("SERPER_API_KEY")
if _env_key:
    logger.debug(f"✅ .env loaded: SERPER_API_KEY found in os.environ (length: {len(_env_key)})")
else:
    logger.warning(f"⚠️ .env not loaded: SERPER_API_KEY not in os.environ. .env path: {_ENV_FILE_PATH}, exists: {os.path.exists(_ENV_FILE_PATH)}")

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic BaseSettings for automatic .env file loading.
    """
    SERPER_API_KEY: str = ""
    JINJA_API_KEY: str = ""  # Jina Reader API (r.jina.ai) for universal scraper
    # Billing: prices (USD) and default project limit; overridable via .env
    BILLING_TWILIO_VOICE: float = 0.05
    BILLING_GEMINI_TOKEN: float = 0.001
    BILLING_DEFAULT_PROJECT_LIMIT: float = 50.0

    model_config = ConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from .env that aren't defined in this class
    )

    @property
    def BILLING_PRICE_LIST(self) -> Dict[str, float]:
        """Price list for usage billing (USD per unit). Keys: twilio_voice, gemini_token."""
        return {
            "twilio_voice": self.BILLING_TWILIO_VOICE,
            "gemini_token": self.BILLING_GEMINI_TOKEN,
        }

    @property
    def DEFAULT_PROJECT_LIMIT(self) -> float:
        """Default monthly spend limit per project (USD)."""
        return self.BILLING_DEFAULT_PROJECT_LIMIT

# Singleton settings instance
settings = Settings()

# Fallback: If Pydantic didn't load it, manually parse .env file and set os.environ
if not settings.SERPER_API_KEY:
    # Manual .env parser as ultimate fallback
    _manual_value = None
    if os.path.exists(_ENV_FILE_PATH):
        try:
            with open(_ENV_FILE_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        # Set in os.environ
                        os.environ[key] = value
                        if key == "SERPER_API_KEY":
                            _manual_value = value
                            logger.info(f"✅ Manually loaded SERPER_API_KEY from .env file (length: {len(value)})")
        except Exception as e:
            logger.error(f"❌ Error manually parsing .env file: {e}")
    
    # Now recreate Settings (should pick up from os.environ)
    if _manual_value:
        settings = Settings()
        # If still empty, create with explicit value
        if not settings.SERPER_API_KEY:
            settings = Settings(SERPER_API_KEY=_manual_value)
            logger.info(f"✅ Settings: SERPER_API_KEY loaded via manual parser (length: {len(_manual_value)})")
    else:
        logger.error(f"❌ SERPER_API_KEY not found in .env file! .env path: {_ENV_FILE_PATH}, exists: {os.path.exists(_ENV_FILE_PATH)}")

if settings.SERPER_API_KEY:
    logger.debug(f"✅ Settings: SERPER_API_KEY loaded (length: {len(settings.SERPER_API_KEY)})")
else:
    logger.warning(f"⚠️ Settings: SERPER_API_KEY is empty! .env path: {_ENV_FILE_PATH}, exists: {os.path.exists(_ENV_FILE_PATH)}")

class ConfigLoader:
    _cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
    _cache_ttl: int = 300

    def __init__(self, profiles_dir="data/profiles"):
        self.profiles_dir = profiles_dir
        self.logger = logging.getLogger("Apex.Config")

    def load(self, project_id: str, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads DNA + campaign config (if campaign_id provided) and merges them.
        Caches result in RAM for _cache_ttl seconds (300s).
        Merges: Defaults -> Generated DNA -> Custom Overrides -> Campaign Config
        
        Args:
            project_id: The project identifier
            campaign_id: Optional campaign identifier. If provided, loads and merges campaign config.
        
        Returns:
            Merged configuration dictionary
        """
        k = (project_id, campaign_id)
        if k in ConfigLoader._cache and time.time() < ConfigLoader._cache[k]["expires_at"]:
            self.logger.debug(f"Config cache hit for project {project_id}, campaign {campaign_id}")
            return ConfigLoader._cache[k]["data"]

        self.logger.debug(f"Loading config for project {project_id}, campaign {campaign_id}")
        
        # 1. Load DNA (base configuration)
        dna = self.load_dna(project_id)
        if dna.get("error"):
            ConfigLoader._cache[k] = {"data": dna, "expires_at": time.time() + ConfigLoader._cache_ttl}
            return dna
        
        # 2. If campaign_id provided, load and merge campaign config
        if campaign_id:
            campaign_config = self.load_campaign_config(campaign_id)
            if campaign_config:
                merged = self.merge_config(dna, campaign_config)
                self.logger.debug(f"Successfully merged DNA + campaign config for campaign {campaign_id}")
                ConfigLoader._cache[k] = {"data": merged, "expires_at": time.time() + ConfigLoader._cache_ttl}
                return merged
            else:
                self.logger.warning(f"Campaign {campaign_id} not found, returning DNA only")
        
        ConfigLoader._cache[k] = {"data": dna, "expires_at": time.time() + ConfigLoader._cache_ttl}
        return dna

    def load_dna(self, project_id: str) -> Dict[str, Any]:
        """
        Loads only the DNA (project-level configuration).
        Merges: Defaults -> Generated DNA -> Custom Overrides
        
        Args:
            project_id: The project identifier
        
        Returns:
            DNA configuration dictionary
        """
        self.logger.debug(f"Loading DNA for project: {project_id}")
        
        # 1. System Defaults
        config = {"system_currency": "NZD", "timezone": "Pacific/Auckland"}
        
        profile_path = os.path.join(self.profiles_dir, project_id)
        
        # 2. Safety Check
        if not os.path.exists(profile_path):
            self.logger.warning(f"Profile path not found: {profile_path} for project: {project_id}")
            return {"error": "Profile not found", "project_id": project_id}

        # 3. Load AI Generated DNA
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

        # 4. Load Human Overrides (Custom Settings) - These win.
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
        
        self.logger.debug(f"DNA loaded successfully for project: {project_id}")
        return config

    def save_dna_custom(self, project_id: str, config: Dict[str, Any]) -> None:
        """
        Saves DNA overrides to dna.custom.yaml for the project. Creates profile dir if needed.
        Invalidates cache for (project_id, None).
        """
        profile_path = os.path.join(self.profiles_dir, project_id)
        os.makedirs(profile_path, exist_ok=True)
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        with open(custom_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        k = (project_id, None)
        if k in ConfigLoader._cache:
            del ConfigLoader._cache[k]
        self.logger.debug(f"Saved DNA custom config for project {project_id}")

    def save_dna(self, project_id: str, dna: Dict[str, Any]) -> None:
        """
        Saves generated DNA to dna.generated.yaml for the project. Creates profile dir if needed.
        Invalidates cache for (project_id, None).
        """
        profile_path = os.path.join(self.profiles_dir, project_id)
        os.makedirs(profile_path, exist_ok=True)
        gen_path = os.path.join(profile_path, "dna.generated.yaml")
        with open(gen_path, "w", encoding="utf-8") as f:
            yaml.dump(dna, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        k = (project_id, None)
        if k in ConfigLoader._cache:
            del ConfigLoader._cache[k]
        self.logger.debug(f"Saved DNA generated config for project {project_id}")

    def save_campaign(self, project_id: str, campaign_id: str, config: Dict[str, Any]) -> None:
        """
        Saves campaign config to profiles_dir/project_id/campaigns/{campaign_id}.yaml.
        Creates campaign dir if needed. Invalidates cache for (project_id, campaign_id).
        """
        campaign_dir = os.path.join(self.profiles_dir, project_id, "campaigns")
        os.makedirs(campaign_dir, exist_ok=True)
        campaign_path = os.path.join(campaign_dir, f"{campaign_id}.yaml")
        with open(campaign_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        k = (project_id, campaign_id)
        if k in ConfigLoader._cache:
            del ConfigLoader._cache[k]
        self.logger.debug(f"Saved campaign config for {campaign_id} in project {project_id}")

    def load_campaign_config(self, campaign_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Loads campaign configuration from database (and disk backup if available).
        
        Args:
            campaign_id: The campaign identifier
            user_id: Optional user_id for RLS check. If None, loads without RLS (internal use only).
        
        Returns:
            Campaign configuration dictionary, or None if not found
        """
        self.logger.debug(f"Loading campaign config for campaign: {campaign_id}")
        
        try:
            from backend.core.memory import memory
            
            # Try to get campaign from DB
            if user_id:
                campaign = memory.get_campaign(campaign_id, user_id)
            else:
                # Internal use: query directly (bypass RLS)
                # This is safe because we're only reading config, not modifying
                placeholder = memory.db_factory.get_placeholder()
                with memory.db_factory.get_cursor(commit=False) as cursor:
                    cursor.execute(f"SELECT project_id, config FROM campaigns WHERE id = {placeholder}", (campaign_id,))
                    row = cursor.fetchone()
                    if row:
                        project_id, config_json = row
                        import json
                        config = json.loads(config_json) if isinstance(config_json, str) else config_json
                        campaign = {"project_id": project_id, "config": config}
                    else:
                        campaign = None
            
            if campaign:
                config = campaign.get('config', {})
                project_id = campaign.get('project_id')
                
                # Also try to load from disk backup
                if project_id:
                    campaign_path = os.path.join(self.profiles_dir, project_id, "campaigns", f"{campaign_id}.yaml")
                    if os.path.exists(campaign_path):
                        try:
                            with open(campaign_path, 'r') as f:
                                disk_config = yaml.safe_load(f) or {}
                                # Merge: DB config takes precedence, but disk can have additional fields
                                config = {**disk_config, **config}
                                self.logger.debug(f"Loaded campaign config from disk backup: {campaign_path}")
                        except Exception as e:
                            self.logger.warning(f"Failed to load campaign config from disk: {e}")
                
                self.logger.debug(f"Successfully loaded campaign config for campaign: {campaign_id}")
                return config
            else:
                self.logger.warning(f"Campaign {campaign_id} not found in database")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading campaign config for {campaign_id}: {e}")
            return None

    def merge_config(self, dna: Dict[str, Any], campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges DNA (base config) with campaign-specific config.
        Campaign config takes precedence for module-specific settings.
        
        Args:
            dna: Base DNA configuration
            campaign_config: Campaign-specific configuration
        
        Returns:
            Merged configuration dictionary
        """
        self.logger.debug("Merging DNA + campaign config")
        
        # Start with DNA as base
        merged = dna.copy()
        
        # Campaign config provides module-specific settings
        # Structure: campaign_config contains module config (e.g., targeting, mining_requirements, etc.)
        # We merge it into the appropriate module section
        
        # Get the module from campaign config (if available) or infer from structure
        module = campaign_config.get('module') or campaign_config.get('_module')
        
        if module:
            # Ensure modules section exists
            if 'modules' not in merged:
                merged['modules'] = {}
            if module not in merged['modules']:
                merged['modules'][module] = {}
            
            # Merge campaign config into module section
            # Campaign config structure matches the template (e.g., targeting, mining_requirements, etc.)
            # We merge it into modules.{module}
            merged['modules'][module].update(campaign_config)
        else:
            # If no module specified, merge at top level (campaign config should be module-specific)
            # For safety, merge into a 'campaign' key
            merged['campaign'] = campaign_config
        
        self.logger.debug("Successfully merged DNA + campaign config")
        return merged
