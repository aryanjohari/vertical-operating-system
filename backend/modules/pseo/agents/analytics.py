import os
import datetime
from typing import Any, Dict, List, Optional, Set

from google.oauth2 import service_account
from googleapiclient.discovery import build

from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.config import ConfigLoader

# Default GSC credentials path (used by gsc_connected, fetch_gsc_*, and AnalyticsAgent)
DEFAULT_GSC_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "secrets",
    "gcp-sercret.json",
)


def gsc_connected(credentials_path: str = DEFAULT_GSC_CREDENTIALS_PATH) -> bool:
    """Return True if GSC credentials file exists and can be loaded."""
    if not credentials_path or not os.path.exists(credentials_path):
        return False
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        return creds is not None
    except Exception:
        return False


def get_gsc_site_url_from_config(config: Dict[str, Any]) -> str:
    """Resolve GSC property from config: identity.gsc_site_url (e.g. sc-domain:example.com) or identity.website."""
    identity = config.get("identity") or {}
    return (identity.get("gsc_site_url") or identity.get("website") or "").strip() or ""


def get_live_urls_for_project(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str] = None,
) -> List[str]:
    """Return list of live_url from published page_drafts for the project (optional campaign)."""
    drafts = memory.get_entities(
        tenant_id=tenant_id,
        entity_type="page_draft",
        project_id=project_id,
        campaign_id=campaign_id,
        limit=5000,
        offset=0,
    )
    urls = []
    for d in drafts:
        meta = d.get("metadata") or {}
        if meta.get("status") != "published":
            continue
        live = meta.get("live_url")
        if live:
            urls.append(live)
    return urls


def fetch_gsc_analytics_filtered_by_live_urls(
    site_url: str,
    live_url_set: Set[str],
    from_date: str,
    to_date: str,
    credentials_path: str = DEFAULT_GSC_CREDENTIALS_PATH,
) -> Dict[str, Any]:
    """
    Query GSC by page, keep only rows whose URL is in live_url_set.
    Return organic_clicks, organic_impressions, ctr, filtered_pages_count, per_page.
    """
    if not live_url_set or not os.path.exists(credentials_path):
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)
    except Exception:
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    request_body = {
        "startDate": from_date,
        "endDate": to_date,
        "dimensions": ["page"],
        "rowLimit": 25000,
    }
    try:
        response = service.searchanalytics().query(
            siteUrl=site_url.strip("/"), body=request_body
        ).execute()
    except Exception:
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    rows = response.get("rows", [])
    total_clicks = 0
    total_impressions = 0
    per_page: List[Dict[str, Any]] = []
    for r in rows:
        url = (r.get("keys") or [""])[0]
        url_norm = url.rstrip("/")
        if url_norm not in live_url_set:
            continue
        clicks = int(r.get("clicks", 0))
        impressions = int(r.get("impressions", 0))
        total_clicks += clicks
        total_impressions += impressions
        ctr = (clicks / impressions * 100) if impressions else 0.0
        per_page.append({"url": url, "clicks": clicks, "impressions": impressions, "ctr": round(ctr, 2)})
    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    return {
        "organic_clicks": total_clicks,
        "organic_impressions": total_impressions,
        "ctr": round(ctr, 2),
        "filtered_pages_count": len(per_page),
        "per_page": per_page,
    }


def fetch_gsc_analytics_whole_site(
    site_url: str,
    from_date: str,
    to_date: str,
    credentials_path: str = DEFAULT_GSC_CREDENTIALS_PATH,
) -> Dict[str, Any]:
    """
    Query GSC for the whole site (no filtering by our DB). Returns all organic data
    from the Search Console API for the date range (e.g. monthly overall metrics).
    Same return shape as fetch_gsc_analytics_filtered_by_live_urls: organic_clicks,
    organic_impressions, ctr, filtered_pages_count (total pages in GSC), per_page.
    """
    if not os.path.exists(credentials_path):
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)
    except Exception:
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    request_body = {
        "startDate": from_date,
        "endDate": to_date,
        "dimensions": ["page"],
        "rowLimit": 25000,
    }
    try:
        response = service.searchanalytics().query(
            siteUrl=site_url.strip("/"), body=request_body
        ).execute()
    except Exception:
        return {
            "organic_clicks": 0,
            "organic_impressions": 0,
            "ctr": 0.0,
            "filtered_pages_count": 0,
            "per_page": [],
        }
    rows = response.get("rows", [])
    total_clicks = 0
    total_impressions = 0
    per_page: List[Dict[str, Any]] = []
    for r in rows:
        url = (r.get("keys") or [""])[0]
        clicks = int(r.get("clicks", 0))
        impressions = int(r.get("impressions", 0))
        total_clicks += clicks
        total_impressions += impressions
        ctr = (clicks / impressions * 100) if impressions else 0.0
        per_page.append({"url": url, "clicks": clicks, "impressions": impressions, "ctr": round(ctr, 2)})
    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    return {
        "organic_clicks": total_clicks,
        "organic_impressions": total_impressions,
        "ctr": round(ctr, 2),
        "filtered_pages_count": len(per_page),
        "per_page": per_page,
    }


class AnalyticsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="DataScientist")
        self.scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        self.service_account_file = os.environ.get("GSC_SERVICE_ACCOUNT_FILE") or DEFAULT_GSC_CREDENTIALS_PATH
        self.config_loader = ConfigLoader()

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        project = memory.get_user_project(user_id)
        if not project: return AgentOutput(status="error", message="No project.")
        
        project_id = project['project_id']
        
        # 1. LOAD CONFIG (GSC property: gsc_site_url e.g. sc-domain:example.com, or website)
        config = self.config_loader.load(project_id)
        site_url = get_gsc_site_url_from_config(config)
        if not site_url:
            return AgentOutput(status="skipped", message="No GSC site URL in config (set identity.gsc_site_url or identity.website).")

        # 2. CONNECT TO GSC
        if not os.path.exists(self.service_account_file):
            return AgentOutput(status="skipped", message="No GSC Credentials.")

        try:
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=self.scopes
            )
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