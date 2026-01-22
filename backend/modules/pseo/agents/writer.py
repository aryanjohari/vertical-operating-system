# backend/modules/pseo/agents/writer.py
import json
import re
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.models import Entity
from backend.core.services.llm_gateway import llm_gateway

class SeoWriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SEOWriter")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        if not self.config:
            self.logger.error("Missing injected config")
            return AgentOutput(status="error", message="Configuration not loaded.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # Use injected config (loaded by kernel)
        config = self.config
        contact = config['identity']['contact']
        phone_number = contact.get('phone', '')
        
        # 1. FETCH PENDING KEYWORDS
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        # Sort by cluster so we write related topics in batches (helps caching)
        pending = sorted(
            [k for k in all_kws if k['metadata'].get('status') == 'pending'],
            key=lambda x: x['metadata'].get('cluster', '')
        )
        
        if not pending: return AgentOutput(status="complete", message="No pending keywords.")
        
        target_kw = pending[0]
        
        # 1. EXTRACT CLUSTER DATA
        cluster_data = target_kw['metadata'].get('cluster_data')
        if not cluster_data:
            return AgentOutput(status="error", message=f"Keyword {target_kw['name']} missing cluster_data. Please regenerate keywords using the Strategist.")
        
        primary_keyword = cluster_data.get('primary', target_kw['name'])
        context_keywords = cluster_data.get('safety', [])
        slug = cluster_data.get('slug', '')
        
        if not primary_keyword:
            return AgentOutput(status="error", message="Missing primary keyword in cluster_data.")
        
        if not context_keywords or len(context_keywords) < 3:
            return AgentOutput(status="error", message="Missing or insufficient context keywords in cluster_data.")
        
        # Generate slug if not provided
        if not slug:
            slug = primary_keyword.lower().replace(' ', '-').replace('near', '').replace('--', '-')
        
        # Retrieve map_embed_url from anchor_location metadata
        anchor_name = target_kw['metadata'].get('target_anchor', '')
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        matching_anchor = [a for a in anchors if a['name'] == anchor_name]
        map_embed_url = matching_anchor[0]['metadata'].get('map_embed_url', '') if matching_anchor else ''
        
        # 2. RAG RETRIEVAL (The Brain)
        # We query the vector DB for specific wisdom related to this keyword
        rag_hits = memory.query_context(tenant_id=user_id, query=primary_keyword, project_id=project_id)
        client_wisdom = rag_hits if rag_hits else "Focus on trust, speed, and reliability."
        
        # 3. GET SEO RULES FROM CONFIG
        seo_rules = config.get('modules', {}).get('local_seo', {}).get('seo_rules', {})
        title_format = seo_rules.get('structure', {}).get('title_format', "{Keyword} {City} | {Business_Name}")
        business_name = config['identity']['business_name']
        city = target_kw['metadata'].get('city', '')
        
        # Format title using template
        title = title_format.replace("{Keyword}", primary_keyword).replace("{City}", city).replace("{Business_Name}", business_name)
        
        # 4. GENERATE STRUCTURED SEO CONTENT
        context_kw_str = ", ".join(context_keywords[:3])  # Use first 3 context keywords
        
        system_prompt = f"""
        Role: SEO Expert and Expert Copywriter for {business_name}.
        Voice: {config['brand_brain'].get('voice_tone', 'Professional')}
        
        Context (Client Wisdom):
        {client_wisdom}
        
        Forbidden Topics: {config['brand_brain'].get('forbidden_topics', [])}
        
        CRITICAL SEO REQUIREMENTS:
        1. Use the PRIMARY keyword "{primary_keyword}" in the H1 tag
        2. Use the CONTEXT keywords ({context_kw_str}) naturally in H2 section headings
        3. Write a 600-word HTML article with proper structure
        
        Structure:
        1. <h1>{primary_keyword}</h1> (MUST contain the primary keyword exactly)
        2. <h2>Introduction</h2> with opening paragraph
        3. <h2>Section using one context keyword</h2> - Why specific local factors (near {anchor_name}) matter
        4. <h2>Section using another context keyword</h2> - How we help
        5. <h2>Section using third context keyword</h2> - Additional value
        6. <h2>FAQ Section</h2> - 3 relevant questions
        7. <h2>Call to Action</h2> - Call {phone_number} immediately
        
        Important: 
        - Include the phone number {phone_number} in the CTA section
        - Use context keywords naturally in H2 tags (don't force them)
        - If map_embed_url is provided ({map_embed_url}), you may reference the location map
        
        Format: HTML only. No Markdown blocks. Use proper <h1>, <h2>, and <h3> tags.
        """
        
        user_prompt = f"""
        Primary Keyword (for H1): {primary_keyword}
        Context Keywords (for H2): {context_kw_str}
        Location Context: {city}
        Target Anchor: {anchor_name}
        """

        # 5. GENERATE STRUCTURED OUTPUT WITH VALIDATION AND RETRY
        max_retries = 3
        min_content_length = 500  # Minimum characters for valid content
        model = "gemini-2.5-flash"
        structured_output = None
        
        for attempt in range(max_retries):
            try:
                self.log(f"Generating structured SEO content (attempt {attempt + 1}/{max_retries}) for: {primary_keyword}")
                
                response_text = llm_gateway.generate_content(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=0.7,
                    max_retries=2,  # inner retries per attempt
                )
                
                # Clean JSON response
                clean_json = response_text.replace('```json', '').replace('```', '').strip()
                
                # Try to parse as JSON first
                try:
                    structured_output = json.loads(clean_json)
                    if not isinstance(structured_output, dict):
                        raise ValueError("Response is not a JSON object")
                except json.JSONDecodeError:
                    # If not JSON, treat as HTML content and wrap it
                    html_content = clean_json.replace("```html", "").replace("```", "").strip()
                    structured_output = {
                        "content": html_content,
                        "meta_description": ""
                    }
                
                # Extract content
                content = structured_output.get('content', '')
                meta_description = structured_output.get('meta_description', '')
                
                # Validate content
                if not content:
                    self.log(f"❌ Empty content on attempt {attempt + 1}")
                    continue
                
                # Check minimum length
                if len(content) < min_content_length:
                    self.log(f"❌ Content too short ({len(content)} chars) on attempt {attempt + 1}, minimum: {min_content_length}")
                    continue
                
                # Validate primary keyword in H1
                h1_pattern = r'<h1[^>]*>(.*?)</h1>'
                h1_matches = re.findall(h1_pattern, content, re.IGNORECASE | re.DOTALL)
                if not h1_matches:
                    self.log(f"❌ Missing H1 tag on attempt {attempt + 1}")
                    continue
                
                h1_text = h1_matches[0].strip()
                if primary_keyword.lower() not in h1_text.lower():
                    self.log(f"❌ Primary keyword '{primary_keyword}' not found in H1 '{h1_text}' on attempt {attempt + 1}")
                    continue
                
                # Validate context keywords in H2 tags
                h2_pattern = r'<h2[^>]*>(.*?)</h2>'
                h2_matches = re.findall(h2_pattern, content, re.IGNORECASE | re.DOTALL)
                context_found = 0
                for h2_text in h2_matches:
                    h2_lower = h2_text.lower()
                    for ctx_kw in context_keywords[:3]:
                        if ctx_kw.lower() in h2_lower:
                            context_found += 1
                            break
                
                if context_found < 2:  # At least 2 context keywords should appear in H2
                    self.log(f"⚠️ Only {context_found} context keywords found in H2 tags, but continuing...")
                
                # Generate meta description if not provided
                if not meta_description:
                    # Extract first paragraph or generate from primary keyword
                    p_pattern = r'<p[^>]*>(.*?)</p>'
                    p_matches = re.findall(p_pattern, content, re.IGNORECASE | re.DOTALL)
                    if p_matches:
                        first_p = re.sub(r'<[^>]+>', '', p_matches[0]).strip()[:155]
                        meta_description = first_p + "..." if len(first_p) > 150 else first_p
                    else:
                        meta_description = f"{primary_keyword} in {city}. {business_name} provides expert services. Call {phone_number} today."
                
                # Content is valid
                self.log(f"✅ Generated valid structured content ({len(content)} chars)")
                break
                
            except Exception as e:
                self.log(f"❌ Generation error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return AgentOutput(
                        status="error", 
                        message=f"Writing Failed after {max_retries} attempts: {str(e)}"
                    )
                continue
        
        # Final validation check
        if not structured_output or not structured_output.get('content'):
            return AgentOutput(
                status="error",
                message=f"Generated content is empty. Failed after {max_retries} attempts."
            )
        
        content = structured_output.get('content', '')
        meta_description = structured_output.get('meta_description', '')
        
        if len(content) < min_content_length:
            return AgentOutput(
                status="error",
                message=f"Generated content is too short (length: {len(content)}, minimum: {min_content_length}). Failed after {max_retries} attempts."
            )
        
        # 6. GENERATE JSON-LD SCHEMA
        schema_type = config.get('identity', {}).get('schema_type', 'LocalBusiness')
        schema_json = self._generate_schema(config, primary_keyword, city, anchor_name, schema_type)
        
        # 7. SAVE DRAFT WITH STRUCTURED DATA
        page_id = f"page_{target_kw['id']}" # Stable ID linking back to keyword
        
        page = Entity(
            id=page_id,
            tenant_id=user_id,
            project_id=project_id,
            entity_type="page_draft",
            name=primary_keyword,  # Use primary keyword as name
            metadata={
                "title": title,
                "meta_description": meta_description,
                "content": content,
                "schema_json": schema_json,
                "slug": slug,          # Save the slug for the Librarian/Publisher
                "status": "draft",     # Hand off to Critic
                "city": target_kw['metadata']['city'],
                "cluster": target_kw['metadata'].get('cluster'), # Keep cluster for Librarian
                "keyword_id": target_kw['id'],
                "primary_keyword": primary_keyword,
                "context_keywords": context_keywords,
                "quality_score": 0
            },
            created_at=datetime.now()
        )
        # Explicitly pass project_id for clarity and reliability
        memory.save_entity(page, project_id=project_id)
        
        # Update Keyword to 'drafted'
        memory.update_entity(target_kw['id'], {"status": "drafted"})
        
        return AgentOutput(status="success", message=f"Drafted: {primary_keyword}")
    
    def _generate_schema(self, config, primary_keyword, city, anchor_name, schema_type):
        """Generate JSON-LD schema based on schema_type."""
        business_name = config['identity']['business_name']
        contact = config['identity']['contact']
        phone = contact.get('phone', '')
        address = contact.get('address', '')
        website = config['identity'].get('website', '')
        
        # Base LocalBusiness schema
        schema = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "name": business_name,
            "description": f"{business_name} provides {primary_keyword} services in {city}.",
        }
        
        if address:
            schema["address"] = {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": "NZ"
            }
            # Try to parse address
            if "," in address:
                parts = [p.strip() for p in address.split(",")]
                if len(parts) >= 2:
                    schema["address"]["streetAddress"] = parts[0]
                    schema["address"]["addressLocality"] = parts[-1] if parts[-1] else city
        
        if phone:
            schema["telephone"] = phone
        
        if website:
            schema["url"] = website
        
        # Add service area if anchor is provided
        if anchor_name:
            schema["areaServed"] = {
                "@type": "City",
                "name": city
            }
        
        return schema