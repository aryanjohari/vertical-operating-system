import asyncio
from dotenv import load_dotenv
load_dotenv()
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.models import AgentInput

async def get_page_now(project_id: str, campaign_id: str, user_id: str):
    print(f"🕵️ Searching for keywords owned by: {user_id}")
    
    # 1. Fetch using the EXACT user who owns the project
    all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
    target_kw = next((k for k in all_kws if k['metadata'].get('campaign_id') == campaign_id 
                      and k['metadata'].get('status') == 'pending'), None)
    
    if not target_kw:
        print(f"❌ ERROR: No pending keywords found for {user_id}. check if user_id is correct.")
        return

    print(f"✅ Found: '{target_kw['name']}' | Keyword ID: {target_kw['id']}")

    # 2. Build the packet
    packet = AgentInput(
        task="write_pages",
        user_id=user_id, # MUST match owner
        params={
            "project_id": project_id,
            "campaign_id": campaign_id,
            "keyword_id": target_kw['id']
        }
    )

    # 3. RUN
    print("🧠 Writer is thinking (Gemini 2.5 Flash)...")
    result = await kernel.dispatch(packet)

    if result.status == "success":
        print("\n--- FINAL HTML PREVIEW ---")
        print(result.data.get('html_content')) 
        print("\nSEO TITLE:", result.data.get('meta_title'))
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