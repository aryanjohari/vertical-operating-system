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
        # Model selection for onboarding tasks (balanced speed/quality)
        self.model = "gemini-2.5-flash"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        State Machine Routing:
        Step 1: 'analyze' -> Scrape URL & Extract Identity
        Step 2: 'interview_start' -> Generate Questions based on Modules
        Step 3: 'interview_loop' -> Chat until Wisdom is extracted
        """
        step = input_data.params.get("step", "analyze")
        
        if step == "analyze":
            return await self._phase_1_analyze(input_data)
        elif step == "interview_start":
            return await self._phase_2_start(input_data)
        elif step == "interview_loop":
            return await self._phase_3_loop(input_data)
        else:
            return AgentOutput(status="error", message=f"Unknown step: {step}")

    # --- PHASE 1: THE COLD READ ---
    async def _phase_1_analyze(self, packet):
        url = packet.params.get("url")
        if not url:
            self.logger.warning("Phase 1 analyze called without URL parameter")
            return AgentOutput(status="error", message="URL required for analysis.")

        # 1. Scrape the Site
        self.log(f"Scraping {url}...")
        try:
            scraper = UniversalScraper()
            raw_data = await scraper.scrape(url)
            
            if not raw_data or not raw_data.get('content'):
                self.logger.warning(f"Scraping returned no content for URL: {url}")
                return AgentOutput(status="error", message="Failed to scrape website content. Please check the URL.")
        except Exception as e:
            self.logger.error(f"Scraping failed for {url}: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to scrape website: {str(e)}")
        
        # 2. AI Extraction
        prompt = f"""
        Analyze this raw website text. Extract the Core Identity.
        JSON Output ONLY.
        Keys: business_name, niche (2-3 words), phone, email, address, key_services (list).
        
        TEXT:
        {raw_data.get('content', '')[:10000]}
        """
        try:
            response_text = llm_gateway.generate_content(
                system_prompt="You are an AI assistant that extracts business identity from website content. Always return valid JSON.",
                user_prompt=prompt,
                model=self.model,
                temperature=0.5,
                max_retries=3
            )
        except Exception as e:
            self.logger.error(f"LLM generation failed in phase 1: {e}", exc_info=True)
            return AgentOutput(status="error", message="Failed to extract identity. Please try again.")
        
        try:
            # Clean generic markdown
            json_str = response_text.replace("```json", "").replace("```", "").strip()
            identity_data = json.loads(json_str)
            
            # Validate extracted identity has minimum required fields
            if not isinstance(identity_data, dict):
                raise ValueError("Identity data is not a dictionary")
            
            if not identity_data.get('business_name'):
                self.logger.warning("Extracted identity missing business_name")
            
            identity_data['website'] = url
            
            self.logger.info(f"Successfully extracted identity for: {identity_data.get('business_name', 'Unknown')}")
            
            return AgentOutput(
                status="success",
                message="Analysis Complete",
                data={"identity": identity_data} # Send back to UI for User Confirmation
            )
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed in phase 1: {e}\nResponse preview: {response_text[:200]}")
            return AgentOutput(status="error", message="Failed to parse identity data. Please try again.")
        except ValueError as e:
            self.logger.error(f"Identity validation failed: {e}")
            return AgentOutput(status="error", message="Invalid identity data format. Please try again.")
        except Exception as e:
            self.logger.error(f"Unexpected error in phase 1 identity extraction: {e}", exc_info=True)
            return AgentOutput(status="error", message="Failed to extract identity. Please try again.")

    # --- PHASE 2: THE STRATEGY SELECTOR ---
    async def _phase_2_start(self, packet):
        """
        Input: Confirmed Identity + Selected Modules List
        Output: The "First Question" to start the Deep Dive.
        """
        identity_raw = packet.params.get("identity", {})
        modules = packet.params.get("modules", []) # e.g. ['local_seo', 'lead_gen']
        
        # Handle nested identity structure (from phase 1 response: {identity: {...}})
        if isinstance(identity_raw, dict) and "identity" in identity_raw and len(identity_raw) == 1:
            identity = identity_raw.get("identity", {})
        else:
            identity = identity_raw
        
        # Validate inputs
        if not isinstance(identity, dict):
            self.logger.warning("Phase 2 called with invalid identity format")
            return AgentOutput(status="error", message="Invalid identity data provided.")
        
        if not isinstance(modules, list):
            self.logger.warning("Phase 2 called with invalid modules format")
            return AgentOutput(status="error", message="Invalid modules list provided.")
        
        # Validate modules are known/valid
        valid_modules = ["local_seo", "lead_gen", "social_media"]
        invalid_modules = [m for m in modules if m not in valid_modules]
        if invalid_modules:
            self.logger.warning(f"Unknown modules requested: {invalid_modules}")
            # Continue with valid modules only
        
        # Build the "Wisdom Agenda"
        agenda = []
        if "local_seo" in modules:
            agenda.append("I need to know your 'Anchor Locations' (e.g. Courts, Suppliers).")
            agenda.append("What is a common mistake your customers make that you fix?")
        if "lead_gen" in modules:
            agenda.append("Do you have a specific phone number for forwarding calls?")
            
        start_msg = (
            f"Great. I've set up the project for **{identity.get('business_name')}**.\n\n"
            f"To activate the **{', '.join(modules)}** modules, I need to extract some expert knowledge.\n\n"
            f"First: {agenda[0] if agenda else 'Tell me about your business.'}"
        )
        
        self.logger.info(f"Starting interview for: {identity.get('business_name', 'Unknown')}, modules: {modules}")
        
        return AgentOutput(
            status="continue",
            message="Starting Interview",
            data={"reply": start_msg, "context": {"modules": modules, "identity": identity}}
        )

    # --- PHASE 3: THE DEEP DIVE (Chat Loop) ---
    async def _phase_3_loop(self, packet):
        history_raw = packet.params.get("history", "")
        user_msg = packet.params.get("message", "")
        context_raw = packet.params.get("context", {}) # Passed back and forth
        
        # Handle history as string (from frontend) - keep as string for prompt
        if isinstance(history_raw, list):
            # Convert list to string format
            history = "\n".join(str(item) for item in history_raw)
        else:
            history = str(history_raw) if history_raw else ""
        
        # Handle context as string (from frontend) or dict
        if isinstance(context_raw, str):
            if context_raw:
                try:
                    import json
                    context = json.loads(context_raw)
                except:
                    context = {}
            else:
                context = {}
        else:
            context = context_raw if isinstance(context_raw, dict) else {}
        
        # Handle nested identity structure if passed directly in params
        identity_raw = packet.params.get("identity")
        if identity_raw and isinstance(identity_raw, dict) and "identity" in identity_raw and len(identity_raw) == 1:
            identity = identity_raw.get("identity", {})
            # Update context with correct identity if not already set
            if not context.get("identity"):
                context["identity"] = identity
        
        # Validate context
        if not isinstance(context, dict):
            self.logger.warning("Phase 3 called with invalid context format")
            context = {}  # Use empty dict instead of error
        
        # Load Template
        try:
            if not os.path.exists(self.template_path):
                self.logger.error(f"Template file not found: {self.template_path}")
                return AgentOutput(status="error", message="Template file not found. System error.")
            
            with open(self.template_path, 'r') as f:
                template = f.read()
            
            if not template:
                self.logger.error("Template file is empty")
                return AgentOutput(status="error", message="Template file is empty. System error.")
        except PermissionError as e:
            self.logger.error(f"Permission denied reading template: {e}")
            return AgentOutput(status="error", message="Cannot read template file. System error.")
        except Exception as e:
            self.logger.error(f"Failed to load template: {e}", exc_info=True)
            return AgentOutput(status="error", message="Failed to load template. System error.")

        prompt = f"""
        ROLE: You are Genesis, the Apex Consultant.
        GOAL: Fill the YAML Template based on the User's inputs.
        
        CONTEXT:
        - Business: {context.get('identity')}
        - Modules Active: {context.get('modules')}
        
        TEMPLATE TO FILL:
        {template}
        
        INSTRUCTIONS:
        1. Check if we have enough info to fill the 'identity', 'brand_brain', and ACTIVE 'modules'.
        2. IF MISSING INFO: Ask the next logical question. Focus on "Expert Nuggets" (insider tips, specific guarantees).
        3. IF COMPLETE: Output the full VALID YAML inside ```yaml``` tags.
        
        CHAT HISTORY:
        {history}
        """
        
        try:
            response_text = llm_gateway.generate_content(
                system_prompt="You are Genesis, the Apex Consultant. Help users configure their business profile.",
                user_prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_retries=3
            )
        except Exception as e:
            self.logger.error(f"LLM generation failed in phase 3: {e}", exc_info=True)
            return AgentOutput(status="error", message="Failed to generate response. Please try again.")
        
        reply = response_text
        
        if "```yaml" in reply:
            # We are done. Save and Register.
            try:
                yaml_content = reply.split("```yaml")[1].split("```")[0].strip()
                
                # Validate YAML can be parsed before saving
                try:
                    parsed_yaml = yaml.safe_load(yaml_content)
                    if not parsed_yaml:
                        raise ValueError("YAML is empty or invalid")
                except yaml.YAMLError as e:
                    self.logger.error(f"Generated YAML is invalid: {e}")
                    return AgentOutput(
                        status="error",
                        message="Generated configuration is invalid. Please continue the interview."
                    )
                
                # Get project_id with validation
                project_id = context.get('identity', {}).get('project_id')
                if not project_id:
                    # Fallback to generating from business name
                    business_name = context.get('identity', {}).get('business_name', 'new_project')
                    project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', business_name.lower())[:50]
                    self.logger.info(f"Generated project_id from business name: {project_id}")
                
                # Validate project_id format for safety
                if not re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                    self.logger.error(f"Invalid project_id format: {project_id}")
                    return AgentOutput(status="error", message="Invalid project identifier. Please try again.")
                
                # Save profile (with error handling)
                save_result = self._save_profile(project_id, yaml_content, packet.user_id)
                if not save_result:
                    return AgentOutput(status="error", message="Failed to save profile. Please try again.")
                
                self.logger.info(f"Successfully completed onboarding for project: {project_id}, user: {packet.user_id}")
                
                return AgentOutput(
                    status="complete",
                    message="Profile Generated",
                    data={
                        "reply": "Configuration saved. System ready.", 
                        "path": f"data/profiles/{project_id}",
                        "project_id": project_id
                    }
                )
            except Exception as e:
                self.logger.error(f"Failed to process completed YAML: {e}", exc_info=True)
                return AgentOutput(status="error", message="Failed to save configuration. Please try again.")
        else:
            return AgentOutput(
                status="continue",
                message="Interviewing",
                data={"reply": reply, "context": context}
            )

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

            # --- 3. THE MISSING RAG INJECTION ---
            # We must feed the "Brand Brain" into ChromaDB so the Writer can find it.
            brand_brain = parsed.get('brand_brain', {})
            if not isinstance(brand_brain, dict):
                brand_brain = {}
            
            nugget_count = 0
            tip_count = 0
            
            # A. Index Knowledge Nuggets
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