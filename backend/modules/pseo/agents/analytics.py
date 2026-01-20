import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.config import ConfigLoader

class AnalyticsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="DataScientist")
        self.scopes = ['https://www.googleapis.com/auth/webmasters.readonly']
        # This file must exist on your server
        self.service_account_file = 'service_account.json' 
        self.config_loader = ConfigLoader()

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        project = memory.get_user_project(user_id)
        if not project: return AgentOutput(status="error", message="No project.")
        
        project_id = project['project_id']
        
        # 1. LOAD CONFIG (Dynamic Site URL)
        config = self.config_loader.load(project_id)
        site_url = config.get('identity', {}).get('website')
        
        if not site_url:
            return AgentOutput(status="skipped", message="No website URL in config.")

        # 2. CONNECT TO GSC
        if not os.path.exists(self.service_account_file):
            return AgentOutput(status="skipped", message="No GSC Credentials (service_account.json).")

        try:
            creds = service_account.Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
            service = build('searchconsole', 'v1', credentials=creds)
        except Exception as e:
            return AgentOutput(status="error", message=f"GSC Auth Failed: {e}")

        # 3. QUERY PERFORMANCE (Last 30 Days)
        date_30_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        request_body = {
            'startDate': date_30_days_ago,
            'endDate': datetime.datetime.now().strftime('%Y-%m-%d'),
            'dimensions': ['page'],
            'rowLimit': 50
        }
        
        try:
            response = service.searchanalytics().query(siteUrl=site_url, body=request_body).execute()
        except Exception as e:
             return AgentOutput(status="error", message=f"GSC Query Failed for {site_url}: {e}")

        rows = response.get('rows', [])
        # Rules: High Impressions (>100), Zero Clicks = Bad Content/Title
        bad_pages = [r for r in rows if r['clicks'] == 0 and r['impressions'] > 100]

        if not bad_pages:
            return AgentOutput(status="success", message="All pages performing well.")

        # 4. CLOSE THE LOOP (Trigger Rewrites)
        actions = 0
        
        # Get all live pages to match URLs
        live_pages = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        
        for bad_page in bad_pages:
            url = bad_page['keys'][0] # e.g., https://site.com/bail-support
            slug = url.strip('/').split('/')[-1] # bail-support
            
            # Find the matching entity
            match = next((p for p in live_pages if p['metadata'].get('slug') == slug), None)
            
            if match:
                self.log(f"♻️ RECYCLING: {slug} failed market test. Resetting to 'pending'.")
                
                new_meta = match['metadata'].copy()
                new_meta['status'] = 'pending' # Send back to Writer!
                new_meta['rewrite_reason'] = "low_ctr_high_impressions"
                new_meta['quality_score'] = 0 # Force re-evaluation
                
                memory.update_entity(match['id'], new_meta)
                
                # Also reset the keyword so the Writer picks it up
                kw_id = match['metadata'].get('keyword_id')
                if kw_id:
                    memory.update_entity(kw_id, {"status": "pending"})
                    
                actions += 1

        return AgentOutput(
            status="success", 
            message=f"Feedback Loop Complete. Sent {actions} pages back to the Writer for improvement.",
            data={"rewrites": actions}
        )