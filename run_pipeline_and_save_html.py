#!/usr/bin/env python3
"""
Run the pSEO pipeline for a keyword (Writer -> Critic -> Librarian -> Media -> Utility)
and save the final HTML to the project root.

Usage:
  python run_pipeline_and_save_html.py <keyword_id> [project_id] [campaign_id] [user_id]

Example:
  python run_pipeline_and_save_html.py kw_8cd6441f3863
  python run_pipeline_and_save_html.py kw_8cd6441f3863 specialist_support_services cmp_1cbf011019 admin@admin.com
"""

import asyncio
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.models import AgentInput

# Defaults (override via args)
DEFAULT_PROJECT_ID = "specialist_support_services"
DEFAULT_CAMPAIGN_ID = "cmp_1cbf011019"
DEFAULT_USER_ID = "admin@admin.com"

PIPELINE_STEPS = [
    "write_pages",
    "critic_review",
    "librarian_link",
    "enhance_media",
    "enhance_utility",
]


def safe_filename(keyword: str) -> str:
    """Turn keyword into a safe filename (no path, no special chars)."""
    s = re.sub(r'[^\w\s-]', '', keyword).strip()
    s = re.sub(r'[-\s]+', '_', s)[:80]
    return s or "page"


async def run_pipeline_and_save(
    keyword_id: str,
    project_id: str,
    campaign_id: str,
    user_id: str,
) -> None:
    base_params = {
        "project_id": project_id,
        "campaign_id": campaign_id,
        "user_id": user_id,
    }

    # Resolve keyword and ensure pending
    kw = memory.get_entity(keyword_id, user_id)
    if not kw:
        print(f"❌ Keyword {keyword_id} not found.")
        return
    keyword_name = kw.get("name", keyword_id)
    if (kw.get("metadata") or {}).get("status") != "pending":
        memory.update_entity(keyword_id, {"status": "pending"}, user_id)
        print("   Set keyword status to 'pending' for Writer")

    print(f"Keyword: {keyword_name} ({keyword_id})")
    print(f"Project: {project_id} | Campaign: {campaign_id}\n")

    page_id = None
    for step in PIPELINE_STEPS:
        params = {**base_params}
        if step == "write_pages":
            params["keyword_id"] = keyword_id
        print(f"▶ {step}...", end=" ", flush=True)
        try:
            result = await asyncio.wait_for(
                kernel.dispatch(AgentInput(task=step, user_id=user_id, params=params)),
                timeout=300,
            )
        except asyncio.TimeoutError:
            print("TIMEOUT")
            return
        if result.status == "error":
            print(f"FAILED: {result.message}")
            return
        if result.status == "complete":
            print("(nothing to do)")
            continue
        if step == "write_pages" and result.data:
            page_id = (result.data or {}).get("page_id")
        print("OK")
    if not page_id:
        # Fallback: find draft by keyword in metadata
        drafts = memory.get_entities(
            tenant_id=user_id,
            entity_type="page_draft",
            project_id=project_id,
        )
        for d in drafts:
            if d.get("metadata", {}).get("keyword_id") == keyword_id or d.get("metadata", {}).get("keyword") == keyword_name:
                page_id = d.get("id")
                break
        if not page_id and drafts:
            page_id = drafts[0].get("id")
    if not page_id:
        print("❌ Could not find draft page_id.")
        return
    draft = memory.get_entity(page_id, user_id)
    if not draft:
        print(f"❌ Draft {page_id} not found.")
        return
    html_content = (draft.get("metadata") or {}).get("content", "")
    if not html_content:
        print("❌ Draft has no content.")
        return
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    filename = safe_filename(keyword_name) + ".html"
    out_path = os.path.join(root_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\n✅ Saved final HTML to: {out_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    keyword_id = sys.argv[1].strip()
    project_id = (sys.argv[2] if len(sys.argv) > 2 else None) or DEFAULT_PROJECT_ID
    campaign_id = (sys.argv[3] if len(sys.argv) > 3 else None) or DEFAULT_CAMPAIGN_ID
    user_id = (sys.argv[4] if len(sys.argv) > 4 else None) or DEFAULT_USER_ID
    asyncio.run(run_pipeline_and_save(keyword_id, project_id, campaign_id, user_id))


if __name__ == "__main__":
    main()
