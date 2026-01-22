import os
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.config import ConfigLoader

class UtilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Utility")
        self.config_loader = ConfigLoader()
        # API URL for the form to POST data to (e.g., https://api.yourdomain.com)
        self.api_base_url = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
        
        project_id = project['project_id']

        # 1. LOAD CONFIG (The Gatekeeper)
        # We need to know: Is Lead Gen enabled? What is the phone number?
        config = self.config_loader.load(project_id)
        lead_gen_config = config.get('modules', {}).get('lead_gen', {})
        module_enabled = lead_gen_config.get('enabled', False)
        
        # 2. FETCH PIPELINE CANDIDATES
        # Input: Pages that have been validated, linked, and imaged (Status: 'ready_for_utility')
        pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        candidates = [p for p in pages if p['metadata'].get('status') == 'ready_for_utility']
        
        if not candidates:
            return AgentOutput(status="complete", message="No pages waiting for tools.")

        # Process a small batch to avoid timeouts
        batch = candidates[:5]
        self.logger.info(f"🔧 Processing tools for {len(batch)} pages (Module Enabled: {module_enabled})...")

        processed_count = 0

        for page in batch:
            try:
                current_html = page['metadata'].get('content', '')
                new_html = current_html
                tool_type = "None"
                has_tool = False

                # 3. INJECT TOOL (Only if Enabled)
                if module_enabled:
                    keyword = page['name']
                    # Priority: Check if Manager passed a specific type, else default
                    requested_type = input_data.params.get("tool_type", "Smart Enquiry Form")
                    
                    # Generate the Tool HTML (hardcoded template, no AI)
                    tool_html = self._generate_tool_html(user_id, project_id, keyword, requested_type)
                    
                    # Validation: If tool_html is empty, return error
                    if not tool_html or tool_html.strip() == "":
                        return AgentOutput(
                            status="error",
                            message=f"Failed to generate tool HTML for page '{page['name']}'. Tool HTML is empty."
                        )
                    
                    # Smart Injection: Place before FAQs for higher conversion
                    if "<h2>Frequently Asked Questions" in new_html:
                        new_html = new_html.replace(
                            "<h2>Frequently Asked Questions", 
                            f"<hr class='apex-divider'>{tool_html}<hr class='apex-divider'>\n<h2>Frequently Asked Questions"
                        )
                    else:
                        new_html = new_html + f"\n<div class='apex-tool-wrapper'>{tool_html}</div>"
                    
                    tool_type = requested_type
                    has_tool = True

                # 4. ADVANCE PIPELINE (Critical Step)
                # Regardless of whether we added a tool, the page is now ready for the Publisher.
                new_meta = page['metadata'].copy()
                new_meta['content'] = new_html
                new_meta['status'] = 'ready_to_publish'  # <--- Hand off to PublisherAgent
                new_meta['has_tool'] = has_tool
                new_meta['tool_type'] = tool_type
                
                if memory.update_entity(page['id'], new_meta):
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"❌ Utility Fail on '{page['name']}': {e}")
                continue

        return AgentOutput(
            status="success", 
            message=f"Processed {processed_count} pages. Ready for publishing.",
            data={"count": processed_count}
        )

    def _generate_tool_html(self, user_id, project_id, keyword, tool_type):
        """
        Generates a hardcoded, robust HTML/JS Contact Us form template.
        No AI generation - this is a reliable, tested template.
        """
        # Label for the Analytics Dashboard (e.g. "Smart Form - Auckland")
        location = keyword.split(" in ")[-1].strip() if " in " in keyword else "General"
        source_label = f"{tool_type} - {location}"
        
        # Hardcoded, robust HTML/JS template
        tool_html = f"""
<div class="apex-contact-form" id="apex-form-{hash(keyword) % 10000}">
    <style>
        .apex-contact-form {{
            max-width: 500px;
            margin: 30px auto;
            padding: 25px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            background: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        .apex-contact-form h3 {{
            margin-top: 0;
            margin-bottom: 20px;
            color: #333;
            font-size: 1.5em;
        }}
        .apex-form-group {{
            margin-bottom: 15px;
        }}
        .apex-form-group label {{
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }}
        .apex-form-group input,
        .apex-form-group textarea {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }}
        .apex-form-group input:focus,
        .apex-form-group textarea:focus {{
            outline: none;
            border-color: #4a90e2;
        }}
        .apex-submit-btn {{
            width: 100%;
            padding: 12px;
            background: #4a90e2;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }}
        .apex-submit-btn:hover {{
            background: #357abd;
        }}
        .apex-submit-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .apex-success-box {{
            padding: 20px;
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 4px;
            color: #155724;
            text-align: center;
            font-weight: 500;
        }}
        .apex-error-box {{
            padding: 15px;
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 4px;
            color: #721c24;
            margin-bottom: 15px;
            display: none;
        }}
    </style>
    
    <h3>Get in Touch</h3>
    <div class="apex-error-box" id="apex-error-{hash(keyword) % 10000}"></div>
    
    <form id="apex-form-element-{hash(keyword) % 10000}">
        <div class="apex-form-group">
            <label for="apex-name-{hash(keyword) % 10000}">Name *</label>
            <input type="text" id="apex-name-{hash(keyword) % 10000}" name="name" required>
        </div>
        
        <div class="apex-form-group">
            <label for="apex-phone-{hash(keyword) % 10000}">Phone *</label>
            <input type="tel" id="apex-phone-{hash(keyword) % 10000}" name="phone" required>
        </div>
        
        <div class="apex-form-group">
            <label for="apex-message-{hash(keyword) % 10000}">Message</label>
            <textarea id="apex-message-{hash(keyword) % 10000}" name="message" rows="4" placeholder="Tell us how we can help..."></textarea>
        </div>
        
        <button type="submit" class="apex-submit-btn" id="apex-submit-{hash(keyword) % 10000}">Submit</button>
    </form>
    
    <script>
        (function() {{
            const formId = 'apex-form-element-{hash(keyword) % 10000}';
            const form = document.getElementById(formId);
            const errorBox = document.getElementById('apex-error-{hash(keyword) % 10000}');
            const submitBtn = document.getElementById('apex-submit-{hash(keyword) % 10000}');
            const formContainer = document.getElementById('apex-form-{hash(keyword) % 10000}');
            
            if (!form) return;
            
            form.addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                // Disable submit button
                submitBtn.disabled = true;
                submitBtn.textContent = 'Submitting...';
                errorBox.style.display = 'none';
                
                // Collect form data
                const formData = {{
                    name: document.getElementById('apex-name-{hash(keyword) % 10000}').value.trim(),
                    phone: document.getElementById('apex-phone-{hash(keyword) % 10000}').value.trim(),
                    message: document.getElementById('apex-message-{hash(keyword) % 10000}').value.trim()
                }};
                
                // Validate required fields
                if (!formData.name || !formData.phone) {{
                    errorBox.textContent = 'Please fill in all required fields.';
                    errorBox.style.display = 'block';
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
                    return;
                }}
                
                try {{
                    // POST to webhook endpoint (no JWT required - works from WordPress/public sites)
                    const response = await fetch('{self.api_base_url}/api/webhooks/wordpress?project_id={project_id}', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            name: formData.name,
                            phone: formData.phone,
                            message: formData.message
                        }})
                    }});
                    
                    if (!response.ok) {{
                        throw new Error('Server error');
                    }}
                    
                    const result = await response.json();
                    
                    if (result.success) {{
                        // Success: Replace form with success message
                        formContainer.innerHTML = '<div class="apex-success-box">Thanks! We will call you shortly.</div>';
                    }} else {{
                        throw new Error(result.message || 'Submission failed');
                    }}
                }} catch (error) {{
                    // Error: Show error message
                    errorBox.textContent = 'Connection error. Please call us directly.';
                    errorBox.style.display = 'block';
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
                }}
            }});
        }})();
    </script>
</div>
"""
        return tool_html.strip()