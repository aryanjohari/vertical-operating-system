# backend/modules/onboarding/genesis.py
import os
import json
import yaml
import re
from dotenv import load_dotenv
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.universal import UniversalScraper
from backend.core.services.llm_gateway import llm_gateway

load_dotenv()

class OnboardingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Onboarding")
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "core",
            "profile_template.yaml"
        )
        # Model selection for onboarding tasks (fast and cost-effective)
        self.model = "gemini-2.5-flash"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Single-shot compiler: Takes form data and generates DNA profile.
        Action: 'compile_profile'
        """
        action = input_data.params.get("action", "compile_profile")
        
        if action == "compile_profile":
            return await self._compile_profile(input_data)
        else:
            return AgentOutput(status="error", message=f"Unknown action: {action}")

    async def _compile_profile(self, input_data: AgentInput) -> AgentOutput:
        """
        Single-shot profile compiler.
        Steps: Scrape (optional) → Compile → Save → RAG
        """
        try:
            # Extract input data
            identity = input_data.params.get("identity", {})
            modules = input_data.params.get("modules", [])
            
            # Validate required fields
            if not isinstance(identity, dict):
                return AgentOutput(status="error", message="Invalid identity data format.")
            
            if not identity.get("business_name"):
                return AgentOutput(status="error", message="Business name is required.")
            
            if not identity.get("niche"):
                return AgentOutput(status="error", message="Niche is required.")
            
            if not isinstance(modules, list) or len(modules) == 0:
                return AgentOutput(status="error", message="At least one module must be selected.")
            
            # Validate modules
            valid_modules = ["local_seo", "lead_gen", "admin"]
            modules = [m for m in modules if m in valid_modules]
            if len(modules) == 0:
                return AgentOutput(status="error", message="No valid modules selected.")
            
            self.logger.info(f"Compiling profile for: {identity.get('business_name')}, modules: {modules}")
            
            # --- STEP A: SCRAPE (Optional) ---
            context_bio = ""
            website = identity.get("website", "").strip()
            
            if website:
                self.log(f"Scraping {website}...")
                try:
                    scraper = UniversalScraper()
                    raw_data = await scraper.scrape(website)
                    
                    if raw_data and raw_data.get('content'):
                        # Extract bio/context from scraped content
                        content = raw_data.get('content', '')[:20000]  # Limit to 20k chars
                        context_bio = f"Website Content:\n{content}"
                        self.logger.info(f"Successfully scraped {len(content)} characters from website")
                    else:
                        self.logger.warning(f"Scraping returned no content for URL: {website}")
                        # Fall back to description if available
                        if identity.get("description"):
                            context_bio = f"Business Description: {identity.get('description')}"
                except Exception as e:
                    self.logger.warning(f"Scraping failed for {website}: {e}")
                    # Fall back to description if available
                    if identity.get("description"):
                        context_bio = f"Business Description: {identity.get('description')}"
            else:
                # Use description if no website
                if identity.get("description"):
                    context_bio = f"Business Description: {identity.get('description')}"
            
            # --- STEP B: COMPILE ---
            self.log("Compiling DNA profile...")
            
            # Load template
            try:
                if not os.path.exists(self.template_path):
                    return AgentOutput(status="error", message="Template file not found. System error.")
                
                with open(self.template_path, 'r') as f:
                    template = f.read()
                
                if not template:
                    return AgentOutput(status="error", message="Template file is empty. System error.")
            except Exception as e:
                self.logger.error(f"Failed to load template: {e}", exc_info=True)
                return AgentOutput(status="error", message="Failed to load template. System error.")
            
            # Build compilation prompt
            modules_list = ", ".join(modules)
            enable_instructions = []
            if "local_seo" in modules:
                enable_instructions.append("- Enable 'local_seo' module (set enabled: true)")
            if "lead_gen" in modules:
                enable_instructions.append("- Enable 'lead_gen' module (set enabled: true)")
            if "admin" in modules:
                enable_instructions.append("- Enable 'admin' module (set enabled: true)")
            
            compilation_prompt = f"""
You are Genesis, the Apex Profile Compiler. Your task is to fill the YAML template with the provided business data.

INPUT DATA:
- Business Name: {identity.get('business_name')}
- Niche: {identity.get('niche')}
- Phone: {identity.get('phone', '')}
- Email: {identity.get('email', '')}
- Website: {identity.get('website', '')}
- Address: {identity.get('address', '')}
- Description: {identity.get('description', '')}

SELECTED MODULES: {modules_list}

{context_bio}

TEMPLATE TO FILL:
{template}

INSTRUCTIONS:
1. Fill the 'identity' section with the provided business data.
2. Generate a valid 'project_id' from the business name (lowercase, alphanumeric + underscores/hyphens only).
3. Fill 'brand_brain' section based on the niche and context:
   - Set appropriate 'voice_tone' for the niche
   - Generate 3-5 'key_differentiators' relevant to the business
   - Generate 3-5 'insider_tips' based on the niche and context
   - Generate 2-3 'common_objections' customers might have
   - Set appropriate 'forbidden_topics' for the niche
4. Module Configuration:
{chr(10).join(enable_instructions)}
   - For modules NOT in the selected list, set enabled: false
5. If 'local_seo' is enabled, set reasonable default anchor_entities and geo_scope based on niche.
6. If 'lead_gen' is enabled, leave sales_bridge settings as template defaults (user will configure later).

OUTPUT: Return ONLY the complete, valid YAML inside ```yaml``` tags. Do not include any other text.
"""
            
            try:
                response_text = llm_gateway.generate_content(
                    system_prompt="You are Genesis, the Apex Profile Compiler. Generate valid YAML configuration files.",
                    user_prompt=compilation_prompt,
                    model=self.model,
                    temperature=0.5,
                    max_retries=3
                )
            except Exception as e:
                self.logger.error(f"LLM generation failed: {e}", exc_info=True)
                return AgentOutput(status="error", message="Failed to compile profile. Please try again.")
            
            # Extract YAML from response
            if "```yaml" in response_text:
                yaml_content = response_text.split("```yaml")[1].split("```")[0].strip()
            elif "```" in response_text:
                # Fallback: try to extract any code block
                parts = response_text.split("```")
                if len(parts) >= 2:
                    yaml_content = parts[1].strip()
                    if yaml_content.startswith("yaml"):
                        yaml_content = yaml_content[4:].strip()
                else:
                    yaml_content = response_text.strip()
            else:
                yaml_content = response_text.strip()
            
            # Validate YAML can be parsed
            try:
                parsed_yaml = yaml.safe_load(yaml_content)
                if not parsed_yaml:
                    raise ValueError("YAML is empty or invalid")
            except yaml.YAMLError as e:
                self.logger.error(f"Generated YAML is invalid: {e}\nYAML preview: {yaml_content[:500]}")
                return AgentOutput(status="error", message="Generated configuration is invalid. Please try again.")
            
            # --- STEP C: SAVE ---
            self.log("Saving profile...")
            
            # Generate and sanitize project_id
            business_name = identity.get('business_name', 'new_project')
            project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', business_name.lower())[:50]
            
            # Ensure project_id in DNA matches
            parsed_yaml['identity']['project_id'] = project_id
            
            # Save profile
            save_result = self._save_profile(project_id, yaml_content, input_data.user_id)
            if not save_result:
                return AgentOutput(status="error", message="Failed to save profile. Please try again.")
            
            self.logger.info(f"Successfully compiled and saved profile for project: {project_id}, user: {input_data.user_id}")
            
            return AgentOutput(
                status="complete",
                message="Profile Generated",
                data={
                    "project_id": project_id,
                    "path": f"data/profiles/{project_id}"
                }
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
            
            # 1. Save File to Disk
            # Use absolute path from project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            path = os.path.join(base_dir, "data", "profiles", project_id)
            
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                self.logger.error(f"Failed to create profile directory {path}: {e}")
                return False
            
            file_path = os.path.join(path, "dna.generated.yaml")
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    # Write validated/updated YAML
                    yaml.dump(parsed, f, default_flow_style=False, allow_unicode=True)
                self.logger.info(f"Saved DNA file: {file_path}")
            except IOError as e:
                self.logger.error(f"Failed to write DNA file {file_path}: {e}")
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
