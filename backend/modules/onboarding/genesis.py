# backend/modules/onboarding/genesis.py
# Schema-driven profile + campaign compilers. YAML templates are single source of truth.
# Form data merged via schema_loader; no hardcoded field mappings.
import os
import yaml
import re
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.schema_loader import (
    load_yaml_template,
    merge_form_into_template,
    validate_required,
    yaml_to_form_schema,
)

load_dotenv()


def _build_config_from_form(template_name: str, form_data: dict) -> Tuple[dict | None, str | None]:
    """
    Build config from form data using YAML template. Returns (merged_config, error_message).
    None error means success.
    """
    try:
        template = load_yaml_template(template_name)
        schema = yaml_to_form_schema(template)
        merged = merge_form_into_template(template, form_data)
        ok, err = validate_required(schema, merged)
        if not ok:
            return None, err
        return merged, None
    except Exception as e:
        return None, str(e)


class OnboardingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Onboarding")
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "core",
            "templates",
            "profile_template.yaml",
        )
        self.model = "gemini-2.5-flash"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        action = input_data.params.get("action", "compile_profile")
        if action == "compile_profile":
            return await self._compile_profile(input_data)
        elif action == "create_campaign":
            return await self._create_campaign(input_data)
        return AgentOutput(status="error", message=f"Unknown action: {action}")

    async def _compile_profile(self, input_data: AgentInput) -> AgentOutput:
        """
        Schema-driven profile compiler. Form data merged into profile_template.yaml.
        No LLM, no scraping. YAML is single source of truth.
        """
        try:
            profile = input_data.params.get("profile")
            if not isinstance(profile, dict):
                return AgentOutput(status="error", message="Invalid profile data. Expected form object.")

            dna, err = _build_config_from_form("profile_template", profile)
            if err:
                return AgentOutput(status="error", message=err)

            project_id_raw = (dna.get("identity") or {}).get("project_id") or ""
            project_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(project_id_raw).lower().strip())
            if not project_id:
                return AgentOutput(status="error", message="Project ID (slug) is required.")

            dna["identity"]["project_id"] = project_id

            self.logger.info(f"Compiling profile from form for project: {project_id}, user: {input_data.user_id}")

            yaml_content = yaml.dump(dna, default_flow_style=False, sort_keys=False, allow_unicode=True)

            save_result = self._save_profile(project_id, yaml_content, input_data.user_id)
            if not save_result:
                return AgentOutput(status="error", message="Failed to save profile. Please try again.")

            self.logger.info(f"Successfully compiled and saved profile for project: {project_id}")
            return AgentOutput(
                status="complete",
                message="Profile Generated",
                data={"project_id": project_id, "path": f"data/profiles/{project_id}"},
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in _compile_profile: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to compile profile: {str(e)}")

    def _validate_dna_structure(self, parsed_yaml: dict) -> tuple[bool, str]:
        """Validate DNA has required fields."""
        if not isinstance(parsed_yaml, dict):
            return False, "DNA is not a valid dictionary"
        
        identity = parsed_yaml.get('identity', {})
        if not isinstance(identity, dict):
            return False, "Missing or invalid identity section"
        
        if not identity.get('project_id'):
            return False, "Missing identity.project_id (required by system)"
        if not identity.get('business_name'):
            return False, "Missing identity.business_name (required)"
        if not identity.get('niche'):
            return False, "Missing identity.niche (required)"
        
        return True, ""
    
    def _save_profile(self, project_id, content, user_id):
        """
        Save DNA profile with comprehensive error handling and validation.
        Returns True on success, False on failure.
        """
        try:
            # Validate project_id one more time before file operations
            if not project_id or not re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                self.logger.error(f"Invalid project_id before save: {project_id}")
                return False
            
            # Parse and validate YAML structure
            try:
                parsed = yaml.safe_load(content)
                if not parsed:
                    self.logger.error("YAML content is empty after parsing")
                    return False
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing failed: {e}")
                return False
            
            # Validate DNA structure
            is_valid, error_msg = self._validate_dna_structure(parsed)
            if not is_valid:
                self.logger.error(f"DNA validation failed: {error_msg}")
                return False
            
            # Ensure project_id in DNA matches provided project_id
            parsed['identity']['project_id'] = project_id

            # 1. Save DNA to disk via ConfigLoader (no direct file I/O in agent)
            try:
                from backend.core.config import ConfigLoader
                ConfigLoader().save_dna(project_id, parsed)
                self.logger.info(f"Saved DNA for project: {project_id}")
            except (IOError, OSError) as e:
                self.logger.error(f"Failed to save DNA for project {project_id}: {e}")
                return False

            # 2. Register in SQLite
            niche = parsed.get('identity', {}).get('niche', 'General')
            try:
                memory.register_project(user_id, project_id, niche)
                self.logger.info(f"Registered project in database: {project_id} for user {user_id}")
            except Exception as e:
                self.logger.error(f"Failed to register project in database: {e}", exc_info=True)
                # Continue anyway - file is saved, DB registration can be retried

            # --- 3. RAG INJECTION ---
            # Feed the "Brand Brain" into ChromaDB so agents can find it
            brand_brain = parsed.get('brand_brain', {})
            if not isinstance(brand_brain, dict):
                brand_brain = {}
            
            nugget_count = 0
            tip_count = 0
            
            # A. Index Knowledge Nuggets (if present)
            nuggets = brand_brain.get('knowledge_nuggets', [])
            if isinstance(nuggets, list):
                for nugget in nuggets:
                    if nugget and isinstance(nugget, str):
                        try:
                            memory.save_context(
                                tenant_id=user_id,
                                text=nugget,
                                metadata={"type": "wisdom", "source": "onboarding"},
                                project_id=project_id
                            )
                            nugget_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to save nugget to RAG: {e}")
                            # Continue with other nuggets

            # B. Index Insider Tips
            tips = brand_brain.get('insider_tips', [])
            if isinstance(tips, list):
                for tip in tips:
                    if tip and isinstance(tip, str):
                        try:
                            memory.save_context(
                                tenant_id=user_id,
                                text=f"Insider Tip: {tip}",
                                metadata={"type": "tip", "source": "onboarding"},
                                project_id=project_id
                            )
                            tip_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to save tip to RAG: {e}")
                            # Continue with other tips
            
            self.log(f"🧠 Injected {nugget_count + tip_count} wisdom nuggets into RAG Memory ({nugget_count} nuggets, {tip_count} tips).")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _save_profile: {e}", exc_info=True)
            return False

    async def _create_campaign(self, input_data: AgentInput) -> AgentOutput:
        """
        Form-based campaign creation. Accepts form_data (1:1 mapping to pseo_default or lead_gen_default).
        No LLM. Uses memory and ConfigLoader via kernel (no direct API-to-DB calls).
        """
        try:
            project_id = input_data.params.get("project_id")
            module = input_data.params.get("module")  # "pseo" or "lead_gen"
            name = (input_data.params.get("name") or "").strip()
            form_data = input_data.params.get("form_data") or {}

            if not project_id:
                return AgentOutput(status="error", message="project_id is required.")
            if module not in ("pseo", "lead_gen"):
                return AgentOutput(status="error", message="module must be 'pseo' or 'lead_gen'.")

            if not memory.verify_project_ownership(input_data.user_id, project_id):
                return AgentOutput(status="error", message="Project not found or access denied.")

            template_name = f"{module}_default"
            config, err = _build_config_from_form(template_name, form_data)
            if err:
                return AgentOutput(status="error", message=err)

            if not name:
                if module == "pseo":
                    sf = (config.get("targeting") or {}).get("service_focus") or ""
                    name = f"{sf.strip()} - Campaign" if sf else "pSEO Campaign"
                else:
                    name = "Lead Gen Campaign"

            from backend.core.config import ConfigLoader
            config_loader = ConfigLoader()

            campaign_id = memory.create_campaign(
                user_id=input_data.user_id,
                project_id=project_id,
                name=name,
                module=module,
                config=config,
            )
            try:
                config_loader.save_campaign(project_id, campaign_id, config)
            except Exception as e:
                self.logger.warning(f"Failed to save campaign config to disk: {e}")

            self.logger.info(f"Created campaign {campaign_id} for project {project_id}, module: {module}")
            return AgentOutput(
                status="complete",
                message="Campaign Created",
                data={"campaign_id": campaign_id, "project_id": project_id, "module": module, "name": name},
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in _create_campaign: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to create campaign: {str(e)}")
