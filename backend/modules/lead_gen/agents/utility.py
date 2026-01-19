import os
from google import genai
from google.genai import types
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'
        # Allow overriding the API URL for production (e.g. https://apex.railway.app)
        self.api_base_url = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        params = input_data.params or {}
        
        # 1. LOAD PROJECT (Context Awareness)
        user_project = memory.get_user_project(user_id)
        if not user_project:
            return AgentOutput(status="error", message="No active project found for user.")
        
        project_id = user_project['project_id']

        # 2. FETCH DRAFTS (Scoped to Project)
        # We only touch drafts that belong to this specific client project
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        
        # Filter: Drafts that have images (Media done) but no tools yet
        targets = [p for p in pages if 'image_url' in p['metadata'] and 'has_tool' not in p['metadata']]
        
        batch = targets[:5]
        self.logger.info(f"Building tools for {len(batch)} pages in project '{project_id}'...")

        for page in batch:
            keyword = page['name']
            
            # 3. DECIDE TOOL TYPE (Generalization Fix)
            # Priority 1: Manager explicitly requested a type (e.g. "Calculator")
            # Priority 2: Default to "Smart Enquiry Form" (AI adapts fields to context)
            tool_type = params.get("tool_type", "Smart Enquiry Form")

            # Extract location for labeling
            location = keyword.split(" in ")[-1].strip() if " in " in keyword else "Unknown"
            source_label = f"{tool_type} - {location}"
            
            # 4. GENERATE JS CODE (With Project ID Payload)
            prompt = f"""
            Create a functional, modern HTML/JS widget for a "{tool_type}".
            Context: The user is on a landing page for "{keyword}".
            
            Requirements:
            1. Clean, trustworthy CSS styling (embedded in <style>).
            2. Inputs: ADAPT the fields to the keyword "{keyword}". 
               - ALWAYS include: Name, Phone.
               - IF keyword implies cost (e.g. 'Price', 'Cost'), add a 'Budget' or 'Estimate' field.
               - IF keyword implies urgency (e.g. 'Emergency', 'Bail'), add an 'Urgency' dropdown.
            3. A "Submit" or "Check" button.
            4. **CRITICAL**: On form submit, you MUST:
               - Prevent default form submission.
               - Collect all inputs.
               - Perform a fetch() POST request to "{self.api_base_url}/api/leads" with JSON:
                 {{
                   "user_id": "{user_id}",
                   "project_id": "{project_id}", 
                   "source": "{source_label}",
                   "data": {{ <form_inputs> }}
                 }}
               - Include header: {{ "Content-Type": "application/json" }}
               - Handle Success: Replace form with "Thanks! We will call you shortly."
               - Handle Error: Show "Error sending. Please call us."
            5. Return ONLY the HTML string (no markdown).
            """
            
            try:
                res = self.client.models.generate_content(model=self.model_id, contents=prompt)
                tool_html = res.text.replace("```html", "").replace("```", "").strip()
                
                # 5. INJECT INTO PAGE
                # Place before FAQs for high conversion
                current_html = page['metadata']['content']
                if "<h2>Frequently Asked Questions" in current_html:
                    new_html = current_html.replace("<h2>Frequently Asked Questions", f"<hr>{tool_html}<hr>\n<h2>Frequently Asked Questions")
                else:
                    new_html = current_html + f"\n<div class='tool-section'>{tool_html}</div>"
                
                # 6. UPDATE DATABASE
                new_meta = page['metadata'].copy()
                new_meta['content'] = new_html
                new_meta['has_tool'] = True
                new_meta['tool_type'] = tool_type # Audit trail
                
                # Save using memory (which handles project_id automatically via update)
                memory.update_entity(page['id'], new_meta)
                self.logger.info(f"✅ Added {tool_type} to: {keyword}")
                
            except Exception as e:
                self.logger.error(f"❌ Tool Error on '{keyword}': {e}")
                continue

        return AgentOutput(status="success", message=f"Enhanced {len(batch)} pages with tools.")