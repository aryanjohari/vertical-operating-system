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
            "templates",
            "profile_template.yaml"
        )
        # Model selection for onboarding tasks (fast and cost-effective)
        self.model = "gemini-2.5-flash"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Single-shot compiler: Takes form data and generates DNA profile.
        Actions: 'compile_profile', 'create_campaign'
        """
        action = input_data.params.get("action", "compile_profile")
        
        if action == "compile_profile":
            return await self._compile_profile(input_data)
        elif action == "create_campaign":
            return await self._create_campaign(input_data)
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

IMPORTANT: This is the simplified DNA template. It only contains:
- identity: Business information
- brand_brain: Voice, differentiators, knowledge nuggets, objections, forbidden topics
- modules: Simple toggles (enabled: true/false) - NO module-specific configuration

Module-specific configurations will be created separately as campaigns.

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
   - Generate 3-5 'knowledge_nuggets' (insider secrets) based on the niche and context
   - Generate 2-3 'common_objections' customers might have
   - Set appropriate 'forbidden_topics' for the niche
4. Module Toggles Only:
{chr(10).join(enable_instructions)}
   - For modules NOT in the selected list, set enabled: false
   - DO NOT add any module-specific configuration (no scout_settings, sniper, sales_bridge, etc.)
   - Module-specific configs will be created later as campaigns

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

    async def _create_campaign(self, input_data: AgentInput) -> AgentOutput:
        """
        Creates a campaign for a module (pseo or lead_gen) with interview flow.
        Steps: interview_start → interview_loop → finalize (create campaign)
        """
        try:
            # Extract input data
            project_id = input_data.params.get("project_id")
            module = input_data.params.get("module")  # "pseo" or "lead_gen"
            name = input_data.params.get("name", "")  # Friendly campaign name
            step = input_data.params.get("step", "finalize")  # interview_start, interview_loop, finalize
            form_data = input_data.params.get("form_data", {})  # Optional form data
            history = input_data.params.get("history", "")  # Chat history for iterative filling
            context = input_data.params.get("context", {})  # Context from previous steps
            
            # Validate required fields
            if not project_id:
                return AgentOutput(status="error", message="project_id is required.")
            
            if not module or module not in ["pseo", "lead_gen"]:
                return AgentOutput(status="error", message="module must be 'pseo' or 'lead_gen'.")
            
            # Verify project ownership
            if not memory.verify_project_ownership(input_data.user_id, project_id):
                return AgentOutput(status="error", message="Project not found or access denied.")
            
            # Load DNA for context (needed for all steps)
            from backend.core.config import ConfigLoader
            config_loader = ConfigLoader()
            dna = config_loader.load_dna(project_id)
            if dna.get("error"):
                return AgentOutput(status="error", message=f"Failed to load DNA: {dna.get('error')}")
            
            identity = dna.get('identity', {})
            brand_brain = dna.get('brand_brain', {})
            
            # ===== INTERVIEW FLOW =====
            if step == "interview_start":
                # Start interview - ask first question
                if module == "pseo":
                    question = f"Great! Let's set up your pSEO campaign. First, which service or area should this campaign focus on? (e.g., 'Emergency Bail', 'Criminal Defense', 'Hot Water Cylinder')"
                else:  # lead_gen
                    question = f"Great! Let's set up your Lead Gen campaign. What type of leads are you looking for? (e.g., 'Emergency Bail Clients', 'Criminal Defense Cases')"
                
                return AgentOutput(
                    status="continue",
                    message=question,
                    data={
                        "reply": question,
                        "question": question,
                        "context": {"step": 0, "module": module, "answers": {}}
                    }
                )
            
            elif step == "interview_loop":
                # Continue interview - collect answers and ask next question
                if not isinstance(context, dict):
                    context = {}
                
                answers = context.get("answers", {})
                current_step = context.get("step", 0)
                
                # Parse user's latest answer from history
                user_answer = ""
                if history:
                    lines = history.split("\n")
                    for line in reversed(lines):
                        if line.startswith("User:"):
                            user_answer = line.replace("User:", "").strip()
                            break
                
                # Store answer and ask next question
                if module == "pseo":
                    if current_step == 0:
                        answers["service_focus"] = user_answer
                        current_step = 1
                        question = "Which geographic areas should we target? (e.g., 'Auckland', 'Manukau, Henderson, Albany', or 'All of New Zealand')"
                    elif current_step == 1:
                        answers["geo_targets"] = user_answer
                        current_step = 2
                        question = "What specific keywords or search terms should we prioritize? (e.g., 'emergency bail lawyer', '24/7 criminal defense', or leave blank for auto-generation)"
                    elif current_step == 2:
                        answers["keywords"] = user_answer
                        # Ready to finalize
                        question = "Perfect! I have all the information I need. Should I create the campaign now? (yes/no)"
                    else:
                        question = "Ready to create your campaign? (yes/no)"
                else:  # lead_gen
                    if current_step == 0:
                        answers["lead_type"] = user_answer
                        current_step = 1
                        question = "What geographic areas should we target for leads? (e.g., 'Auckland', 'Manukau, North Shore')"
                    elif current_step == 1:
                        answers["geo_targets"] = user_answer
                        current_step = 2
                        question = "What search terms or keywords should the sniper use to find leads? (e.g., 'need bail lawyer', 'arrested need help', or leave blank for auto-generation)"
                    elif current_step == 2:
                        answers["search_terms"] = user_answer
                        question = "Perfect! I have all the information I need. Should I create the campaign now? (yes/no)"
                    else:
                        question = "Ready to create your campaign? (yes/no)"
                
                # Check if user confirmed creation
                if "yes" in user_answer.lower() and current_step >= 2:
                    # User confirmed - update context and proceed to finalize
                    context["answers"] = answers
                    context["step"] = current_step
                    # Set step to finalize so the finalize block executes
                    step = "finalize"
                else:
                    # Continue interview
                    context["answers"] = answers
                    context["step"] = current_step
                    return AgentOutput(
                        status="continue",
                        message=question,
                        data={
                            "reply": question,
                            "question": question,
                            "context": context
                        }
                    )
            
            # ===== FINALIZE: CREATE CAMPAIGN =====
            if step == "finalize":
                # Load appropriate template
                template_name = f"{module}_default.yaml"
                template_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "core",
                    "templates",
                    template_name
                )
                
                if not os.path.exists(template_path):
                    return AgentOutput(status="error", message=f"Template not found: {template_name}")
                
                with open(template_path, 'r') as f:
                    template = f.read()
                
                # Get answers from context
                if isinstance(context, dict):
                    answers = context.get("answers", {})
                else:
                    answers = {}
                
                # Build compilation prompt with interview answers
                compilation_prompt = f"""
You are Genesis, the Apex Campaign Creator. Fill the campaign YAML template based on the project DNA and user interview answers.

PROJECT DNA (Context):
- Business Name: {identity.get('business_name', '')}
- Niche: {identity.get('niche', '')}
- Voice Tone: {brand_brain.get('voice_tone', '')}
- Key Differentiators: {', '.join(brand_brain.get('key_differentiators', []))}

CAMPAIGN MODULE: {module.upper()}
CAMPAIGN NAME: {name}

USER INTERVIEW ANSWERS:
{json.dumps(answers, indent=2) if answers else 'No specific answers provided - use DNA context and reasonable defaults.'}

CONVERSATION HISTORY:
{history if history else 'No conversation history.'}

TEMPLATE TO FILL:
{template}

INSTRUCTIONS:
1. Fill all REQUIRED fields in the template.
2. Use the interview answers to populate:
   - For pseo: targeting.service_focus (from answers.service_focus), targeting.geo_targets (parse cities/suburbs from answers.geo_targets), mining_requirements.queries (use answers.keywords or generate based on service_focus)
   - For lead_gen: sniper.search_terms (from answers.search_terms or generate from answers.lead_type), sniper.geo_filter (parse from answers.geo_targets)
3. Use project DNA context to inform other choices.
4. For lead_gen: Use identity.phone for bridge.destination_phone if available.
5. Make the configuration practical and actionable.

OUTPUT: Return ONLY the complete, valid YAML inside ```yaml``` tags. Do not include any other text.
"""
                
                try:
                    response_text = llm_gateway.generate_content(
                        system_prompt="You are Genesis, the Apex Campaign Creator. Generate valid YAML configuration files for campaigns.",
                        user_prompt=compilation_prompt,
                        model=self.model,
                        temperature=0.5,
                        max_retries=3
                    )
                except Exception as e:
                    self.logger.error(f"LLM generation failed: {e}", exc_info=True)
                    return AgentOutput(status="error", message="Failed to generate campaign config. Please try again.")
                
                # Extract YAML from response
                if "```yaml" in response_text:
                    yaml_content = response_text.split("```yaml")[1].split("```")[0].strip()
                elif "```" in response_text:
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
                    return AgentOutput(status="error", message="Generated campaign configuration is invalid. Please try again.")
                
                # Generate campaign name if not provided
                if not name:
                    service_focus = answers.get("service_focus") or parsed_yaml.get('targeting', {}).get('service_focus', '') if module == 'pseo' else answers.get("lead_type") or parsed_yaml.get('sniper', {}).get('search_terms', [''])[0] if parsed_yaml.get('sniper') else ''
                    name = f"{service_focus} - {identity.get('business_name', 'Campaign')}" if service_focus else f"{module.upper()} Campaign - {identity.get('business_name', 'Project')}"
                
                # Create campaign in database
                self.log("Creating campaign in database...")
                try:
                    campaign_id = memory.create_campaign(
                        user_id=input_data.user_id,
                        project_id=project_id,
                        name=name,
                        module=module,
                        config=parsed_yaml
                    )
                except Exception as e:
                    self.logger.error(f"Failed to create campaign in database: {e}", exc_info=True)
                    return AgentOutput(status="error", message="Failed to create campaign. Please try again.")
                
                # Save campaign YAML to disk (backup)
                self.log("Saving campaign config to disk...")
                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    campaign_dir = os.path.join(base_dir, "data", "profiles", project_id, "campaigns")
                    os.makedirs(campaign_dir, exist_ok=True)
                    
                    campaign_file = os.path.join(campaign_dir, f"{campaign_id}.yaml")
                    with open(campaign_file, "w", encoding="utf-8") as f:
                        yaml.dump(parsed_yaml, f, default_flow_style=False, allow_unicode=True)
                    self.logger.info(f"Saved campaign config to: {campaign_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to save campaign config to disk: {e}")
                    # Continue anyway - DB is the source of truth
                
                self.logger.info(f"Successfully created campaign {campaign_id} for project: {project_id}, module: {module}")
                
                return AgentOutput(
                    status="complete",
                    message="Campaign Created",
                    data={
                        "campaign_id": campaign_id,
                        "complete": True,
                        "project_id": project_id,
                        "module": module,
                        "name": name,
                        "config": parsed_yaml
                    }
                )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _create_campaign: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to create campaign: {str(e)}")
