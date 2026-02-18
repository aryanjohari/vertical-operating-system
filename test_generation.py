import asyncio
import csv
import os
from dotenv import load_dotenv
load_dotenv()
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.models import AgentInput

DUMP_DIR = "data_dumps"
KEYWORDS_CSV = os.path.join(DUMP_DIR, "entities_seo_keyword.csv")
DRAFTS_CSV = os.path.join(DUMP_DIR, "entities_page_draft.csv")

# Keyword to use: emergency parole housing near Hamilton City Council
USE_KEYWORD_ID = "kw_8cd6441f3863"


def get_unused_keyword_from_dumps(project_id: str, campaign_id: str):
    """
    Read dumps: pick a keyword that has no page_draft yet (not used).
    Returns (keyword_id, keyword_name) or (None, None).
    """
    if not os.path.exists(KEYWORDS_CSV):
        print(f"❌ {KEYWORDS_CSV} not found. Run scripts/system_dump.py first.")
        return None, None
    used_keyword_ids = set()
    if os.path.exists(DRAFTS_CSV):
        with open(DRAFTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kid = row.get("keyword_id", "").strip()
                if kid:
                    used_keyword_ids.add(kid)
    with open(KEYWORDS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw_id = row.get("id", "").strip()
            if not kw_id or kw_id in used_keyword_ids:
                continue
            if row.get("project_id") != project_id or row.get("campaign_id") != campaign_id:
                continue
            return kw_id, row.get("name", "").strip()
    return None, None


async def get_page_now(project_id: str, campaign_id: str, user_id: str):
    keyword_id = USE_KEYWORD_ID
    print(f"🕵️ Using keyword: {keyword_id}")

    target_kw = memory.get_entity(keyword_id, user_id)
    if not target_kw:
        print(f"❌ Keyword {keyword_id} not found in DB.")
        return

    keyword_name = target_kw.get("name", keyword_id)
    print(f"✅ '{keyword_name}' | Keyword ID: {keyword_id}")

    # Writer only accepts keywords with status "pending". Ensure it so the backend accepts this keyword.
    if (target_kw.get("metadata") or {}).get("status") != "pending":
        memory.update_entity(keyword_id, {"status": "pending"}, user_id)
        print("   (set keyword status to 'pending' for Writer)")

    # 2. Build the packet
    packet = AgentInput(
        task="write_pages",
        user_id=user_id,
        params={
            "project_id": project_id,
            "campaign_id": campaign_id,
            "keyword_id": keyword_id,
        },
    )

    # 3. RUN
    print("🧠 Writer is thinking (Gemini 2.5 Flash)...")
    result = await kernel.dispatch(packet)

    if result.status == "success":
        print("\n--- RESULT ---")
        print("SEO TITLE:", result.data.get("meta_title"))
        print("KEYWORD:", result.data.get("keyword"))
        print("NEXT STEP:", result.data.get("next_step"))
        print("------------------------------")
    else:
        print(f"❌ LOGIC FAILED: {result.message}")

if __name__ == "__main__":
    # 🚨 REPLACE 'your_email@example.com' WITH YOUR ACTUAL LOGIN EMAIL 🚨
    asyncio.run(get_page_now(
        project_id="specialist_support_services", 
        campaign_id="cmp_1cbf011019", 
        user_id="admin@admin.com" 
    ))