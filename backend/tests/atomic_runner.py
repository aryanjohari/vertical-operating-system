#!/usr/bin/env python3
"""
Atomic Test Loop: Run write_pages -> critic_review -> librarian_link for a single keyword
and write the final HTML to preview_final.html.

Run from project root with the same environment as the backend (e.g. .env, PYTHONPATH).
Example:
  python -m backend.tests.atomic_runner --keyword-id kw_xxx --campaign-id cmp_xxx --user-id user@example.com
"""
import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure backend is on path when run as script
if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.models import AgentInput


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREVIEW_PATH = os.path.join(PROJECT_ROOT, "preview_final.html")


async def run(keyword_id: str, campaign_id: str, user_id: str) -> None:
    campaign = memory.get_campaign(campaign_id, user_id)
    if not campaign:
        print("Error: Campaign not found or access denied.", file=sys.stderr)
        sys.exit(1)
    project_id = campaign.get("project_id")
    if not project_id:
        print("Error: Campaign has no project_id.", file=sys.stderr)
        sys.exit(1)

    base_params = {"project_id": project_id, "user_id": user_id, "campaign_id": campaign_id}
    write_params = {**base_params, "keyword_id": keyword_id}

    # 1. write_pages
    task_input = AgentInput(task="write_pages", user_id=user_id, params=write_params)
    res = await kernel.dispatch(task_input)
    if res.status == "error":
        print(f"Error (write_pages): {res.message}", file=sys.stderr)
        sys.exit(1)
    page_id = (res.data or {}).get("page_id")
    if not page_id:
        print("Error: write_pages did not return page_id.", file=sys.stderr)
        sys.exit(1)

    # 2. critic_review
    task_input = AgentInput(task="critic_review", user_id=user_id, params=base_params)
    res = await kernel.dispatch(task_input)
    if res.status == "error":
        print(f"Error (critic_review): {res.message}", file=sys.stderr)
        sys.exit(1)

    # 3. librarian_link
    task_input = AgentInput(task="librarian_link", user_id=user_id, params=base_params)
    res = await kernel.dispatch(task_input)
    if res.status == "error":
        print(f"Error (librarian_link): {res.message}", file=sys.stderr)
        sys.exit(1)

    # 4. enhance_media (sets status ready_for_utility)
    task_input = AgentInput(task="enhance_media", user_id=user_id, params=base_params)
    res = await kernel.dispatch(task_input)
    if res.status == "error":
        print(f"Error (enhance_media): {res.message}", file=sys.stderr)
        sys.exit(1)

    # 5. enhance_utility (final HTML: form_capture, schema, status ready_to_publish)
    task_input = AgentInput(task="enhance_utility", user_id=user_id, params=base_params)
    res = await kernel.dispatch(task_input)
    if res.status == "error":
        print(f"Error (enhance_utility): {res.message}", file=sys.stderr)
        sys.exit(1)
    if res.status == "complete":
        print("Warning: enhance_utility had no work (draft may not be in ready_for_utility).", file=sys.stderr)

    # 6. Load draft and write final HTML (after utility so we get form + schema updates)
    draft = memory.get_entity(page_id, user_id)
    if not draft:
        print("Error: Draft not found after pipeline.", file=sys.stderr)
        sys.exit(1)
    meta = draft.get("metadata") or {}
    html_content = meta.get("content") or meta.get("html_content") or ""
    if not html_content:
        print("Warning: Draft has no content.", file=sys.stderr)

    with open(PREVIEW_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Success. Output written to {PREVIEW_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run write_pages -> critic_review -> librarian_link for one keyword and save HTML to preview_final.html."
    )
    parser.add_argument("--keyword-id", required=True, help="ID of the seo_keyword entity to write")
    parser.add_argument("--campaign-id", required=True, help="Campaign ID")
    parser.add_argument("--user-id", required=True, help="Tenant/user ID")
    args = parser.parse_args()
    asyncio.run(run(args.keyword_id, args.campaign_id, args.user_id))


if __name__ == "__main__":
    main()
