# backend/modules/pseo/agents/utility.py
"""Pure Python helpers for pSEO (no LLM, no agent)."""


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
