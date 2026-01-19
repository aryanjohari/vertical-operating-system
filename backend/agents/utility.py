import os
from google import genai
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")
        api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. Fetch Drafts needing tools
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft")
        # Filter: Drafts that have images (Media done) but no tools yet
        targets = [p for p in pages if 'image_url' in p['metadata'] and 'has_tool' not in p['metadata']]
        
        batch = targets[:5]
        print(f"🧰 Building tools for {len(batch)} pages...")

        for page in batch:
            keyword = page['name']
            
            # 2. Decide Tool Type
            # Simple heuristic: If "Bail" -> Calculator. If "Legal Aid" -> Eligibility Checker.
            tool_type = "Simple Contact Form"
            if "bail" in keyword.lower():
                tool_type = "Bail Cost Estimator"
            elif "aid" in keyword.lower():
                tool_type = "Legal Aid Eligibility Quiz"

            # 3. Generate JS Code with Lead Capture
            # Extract location from keyword if possible (e.g., "Bail Accommodation in Auckland" -> "Auckland")
            location = keyword.split(" in ")[-1].strip() if " in " in keyword else "Unknown"
            source_label = f"{tool_type} - {location}"
            
            prompt = f"""
            Create a functional, simple HTML/JS widget for a "{tool_type}".
            Context: Local SEO page for "{keyword}".
            
            Requirements:
            1. Clean styling (CSS inside <style> tags).
            2. Inputs relevant to the topic (e.g., name, phone, email, charges, etc.).
            3. A "Calculate" or "Check" button.
            4. **CRITICAL**: On form submit, you MUST:
               - Prevent default form submission
               - Collect all form input values into a JavaScript object
               - Perform a fetch() POST request to "http://localhost:8000/api/leads" with the following JSON payload:
                 {{
                   "user_id": "{user_id}",
                   "source": "{source_label}",
                   "data": {{ <all_form_inputs_as_key_value_pairs> }}
                 }}
               - Include proper headers: {{ "Content-Type": "application/json" }}
               - Handle the response (show success message or error)
               - Log to console.log for debugging
            5. Return ONLY the HTML string (including <script> and <style>). No markdown.
            
            Example JavaScript structure for submit handler:
            ```javascript
            document.getElementById('calc-form').addEventListener('submit', async function(e) {{
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                
                try {{
                    const response = await fetch('http://localhost:8000/api/leads', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            user_id: '{user_id}',
                            source: '{source_label}',
                            data: data
                        }})
                    }});
                    const result = await response.json();
                    console.log('Lead captured:', result);
                    // Show success message to user
                }} catch (error) {{
                    console.error('Error capturing lead:', error);
                }}
            }});
            ```
            """
            
            try:
                res = self.client.models.generate_content(model=self.model_id, contents=prompt)
                tool_html = res.text.replace("```html", "").replace("```", "").strip()
                
                # 4. Inject into Page
                # Append tool BEFORE the FAQs (usually a good spot)
                current_html = page['metadata']['content']
                if "<h2>Frequently Asked Questions" in current_html:
                    new_html = current_html.replace("<h2>Frequently Asked Questions", f"<hr>{tool_html}<hr>\n<h2>Frequently Asked Questions")
                else:
                    new_html = current_html + f"\n<div class='tool-section'>{tool_html}</div>"
                
                # Update DB
                new_meta = page['metadata'].copy()
                new_meta['content'] = new_html
                new_meta['has_tool'] = True
                
                memory.update_entity(page['id'], new_meta)
                print(f"✅ Added {tool_type} to: {page['name']}")
                
            except Exception as e:
                print(f"❌ Tool Error: {e}")

        return AgentOutput(status="success", message=f"Added interactive tools to {len(batch)} pages.")