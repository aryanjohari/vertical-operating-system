# backend/modules/pseo/agents/utility.py
"""Pure Python helpers for pSEO (no LLM, no agent)."""

from typing import Any, Dict, Optional


def _is_informational_schema(kw_meta: Dict[str, Any]) -> bool:
    """True if intent suggests Article (guide/how-to); else Service/LocalBusiness."""
    intent_role = (kw_meta.get("intent_role") or "").strip().lower()
    cluster_id = (kw_meta.get("cluster_id") or kw_meta.get("intent") or "").strip().lower()
    if "informational" in intent_role:
        return True
    if "guide" in cluster_id or "how-to" in cluster_id or "howto" in cluster_id:
        return True
    return False


def generate_schema(
    kw_meta: Dict[str, Any],
    anchor_data: Optional[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a JSON-LD schema dict (deterministic, no I/O).
    - Informational intent -> @type "Article" (headline, description, author).
    - Transactional intent -> @type "Service" with provider LocalBusiness, areaServed.
    """
    ctx = "https://schema.org"
    headline = (kw_meta.get("meta_title") or kw_meta.get("keyword") or kw_meta.get("h1_title") or "Page").strip()
    description = (kw_meta.get("meta_description") or "").strip()
    modules = config.get("modules") or {}
    brand_brain = config.get("brand_brain", {})
    identity = config.get("identity", {})
    brand_name = identity.get("business_name") or brand_brain.get("business_name") or config.get("brand_name") or "Our Business"
    targeting = config.get("targeting", {}) or {}
    geo = targeting.get("geo_targets") or {}
    cities = geo.get("cities") if isinstance(geo.get("cities"), list) else []
    if not cities and geo.get("cities"):
        cities = [geo["cities"]]
    service_focus = (targeting.get("service_focus") or config.get("service_focus") or "Service").strip()

    if _is_informational_schema(kw_meta):
        schema = {
            "@context": ctx,
            "@type": "Article",
            "headline": headline[:110],
            "description": description[:200] if description else headline[:160],
        }
        if brand_name:
            schema["author"] = {"@type": "Organization", "name": brand_name}
        if anchor_data and (anchor_data.get("name") or anchor_data.get("address")):
            schema["about"] = {"@type": "Place", "name": anchor_data.get("name", ""), "address": {"@type": "PostalAddress", "streetAddress": anchor_data.get("address", "")}}
        return schema

    # Transactional: Service with provider LocalBusiness, areaServed
    area_served = []
    if anchor_data and anchor_data.get("name"):
        locality = cities[0] if cities else "New Zealand"
        area_served.append({
            "@type": "Place",
            "name": f"Area near {anchor_data.get('name', '')}",
            "address": {"@type": "PostalAddress", "addressLocality": locality},
        })
    else:
        for c in (cities or [])[:5]:
            if c:
                area_served.append({"@type": "City", "name": str(c).strip()})
        if not area_served:
            area_served.append({"@type": "Country", "name": "New Zealand"})

    provider = {"@type": "LocalBusiness", "name": brand_name}
    if anchor_data:
        if anchor_data.get("address"):
            provider["address"] = {"@type": "PostalAddress", "streetAddress": anchor_data.get("address")}
        if anchor_data.get("phone"):
            provider["telephone"] = anchor_data.get("phone")

    schema = {
        "@context": ctx,
        "@type": "Service",
        "serviceType": service_focus,
        "provider": provider,
        "areaServed": area_served,
        "name": headline,
        "description": description[:200] if description else None,
    }
    return {k: v for k, v in schema.items() if v is not None}


def get_local_blurb(city: str, distance: str, anchor: str) -> str:
    """
    Generate a single local-context sentence for the page.

    Returns: "We serve clients throughout {city}, located just {distance} from {anchor}."
    If anchor is empty, returns: "We serve clients throughout {city}."
    """
    city = (city or "").strip()
    distance = (distance or "minutes").strip()
    anchor = (anchor or "").strip()

    if not city:
        return ""
    if not anchor:
        return f"We serve clients throughout {city}."
    return f"We serve clients throughout {city}, located just {distance} from {anchor}."
