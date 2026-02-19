"""
Lead Gen analytics: deterministic, time-bound counts and rates.
No LLM. Used by GET /api/projects/{project_id}/analytics/lead_gen and by refetch background task.
"""
from typing import Any, Dict, List, Optional

from backend.core.memory import memory


def webhooks_received_count(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str],
    created_after: Optional[str],
    created_before: Optional[str],
) -> int:
    """Count lead entities in the time window (webhooks received)."""
    leads = memory.get_entities(
        tenant_id=tenant_id,
        entity_type="lead",
        project_id=project_id,
        campaign_id=campaign_id,
        limit=10_000,
        offset=0,
        created_after=created_after,
        created_before=created_before,
    )
    return len(leads)


def average_lead_score(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str],
    created_after: Optional[str],
    created_before: Optional[str],
) -> Optional[float]:
    """Mean of metadata.score for leads in the time window. None if no scored leads."""
    leads = memory.get_entities(
        tenant_id=tenant_id,
        entity_type="lead",
        project_id=project_id,
        campaign_id=campaign_id,
        limit=10_000,
        offset=0,
        created_after=created_after,
        created_before=created_before,
    )
    scores = [
        float(l.get("metadata", {}).get("score"))
        for l in leads
        if l.get("metadata", {}).get("score") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def scheduled_bridge_rate(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str],
    created_after: Optional[str],
    created_before: Optional[str],
) -> Dict[str, Any]:
    """Count and percentage of leads that triggered a scheduled bridge (metadata.scheduled_bridge_at set)."""
    leads = memory.get_entities(
        tenant_id=tenant_id,
        entity_type="lead",
        project_id=project_id,
        campaign_id=campaign_id,
        limit=10_000,
        offset=0,
        created_after=created_after,
        created_before=created_before,
    )
    total = len(leads)
    count = sum(
        1
        for l in leads
        if (l.get("metadata") or {}).get("scheduled_bridge_at")
    )
    pct = round((count / total * 100), 2) if total else 0.0
    return {"count": count, "total": total, "pct": pct}


def by_source_breakdown(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str],
    created_after: Optional[str],
    created_before: Optional[str],
) -> Dict[str, int]:
    """Count leads by metadata.source in the time window."""
    leads = memory.get_entities(
        tenant_id=tenant_id,
        entity_type="lead",
        project_id=project_id,
        campaign_id=campaign_id,
        limit=10_000,
        offset=0,
        created_after=created_after,
        created_before=created_before,
    )
    out: Dict[str, int] = {}
    for l in leads:
        src = (l.get("metadata") or {}).get("source") or "unknown"
        out[src] = out.get(src, 0) + 1
    return out


def get_lead_gen_analytics(
    tenant_id: str,
    project_id: str,
    campaign_id: Optional[str],
    from_date: str,
    to_date: str,
) -> Dict[str, Any]:
    """
    Aggregate Lead Gen analytics for the given project/campaign and time range.
    Returns dict matching LeadGenAnalytics frontend contract.
    """
    webhooks = webhooks_received_count(
        tenant_id, project_id, campaign_id, from_date, to_date
    )
    avg_score = average_lead_score(
        tenant_id, project_id, campaign_id, from_date, to_date
    )
    scheduled = scheduled_bridge_rate(
        tenant_id, project_id, campaign_id, from_date, to_date
    )
    by_source = by_source_breakdown(
        tenant_id, project_id, campaign_id, from_date, to_date
    )
    return {
        "from": from_date,
        "to": to_date,
        "webhooks_received": webhooks,
        "avg_lead_score": avg_score,
        "scheduled_bridge": scheduled,
        "by_source": by_source,
    }
