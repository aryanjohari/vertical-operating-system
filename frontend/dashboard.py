import streamlit as st
import requests
import json
import sys
import os
import time

# Allow importing backend modules (for local dev)
sys.path.append(os.getcwd())
from backend.core.registry import ModuleManifest
from backend.core.memory import memory # Direct DB access for Auth & Data View

# Config
API_URL = "http://localhost:8000"

st.set_page_config(page_title="Apex Sovereign OS", page_icon="⚡", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "step" not in st.session_state:
    st.session_state.step = "login" # Start at login
if "project_state" not in st.session_state:
    st.session_state.project_state = None

# ====================================================
# PHASE 0: THE GATEKEEPER (Login)
# ====================================================
if not st.session_state.user_id:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## ⚡ Apex Sovereign OS")
        st.warning("🔒 Secure Access Required")
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email / User ID")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    if memory.verify_user(email, password):
                        st.session_state.user_id = email
                        st.success("✅ Access Granted")
                        st.rerun()
                    else:
                        st.error("❌ Invalid Credentials")
        
        with tab2:
            with st.form("register_form"):
                new_email = st.text_input("New Email")
                new_pass = st.text_input("New Password", type="password")
                reg_submitted = st.form_submit_button("Create Account")
                
                if reg_submitted:
                    if memory.create_user(new_email, new_pass):
                        st.success("✅ Account Created. Please Login.")
                    else:
                        st.error("⚠️ User already exists.")
    
    st.stop() 

# ====================================================
# LOGIC: DETERMINE USER STATE
# ====================================================
# If we just logged in, check if they have a project
if st.session_state.step == "login":
    with st.spinner("🔄 Loading Neural Link..."):
        # We ask the Manager Agent to check our status
        try:
            payload = {
                "task": "manager",
                "user_id": st.session_state.user_id,
                "params": {} # Manager finds the project automatically
            }
            response = requests.post(f"{API_URL}/api/run", json=payload)
            result = response.json()
            
            if result['status'] == 'error' and "No active project" in result['message']:
                st.session_state.step = "init" # Go to Onboarding
            else:
                st.session_state.step = "operations" # Go to Dashboard
                st.session_state.project_state = result # Save the Manager's Report
        except Exception as e:
            st.error(f"Kernel Connection Failed: {e}")
            st.stop()

# ====================================================
# PHASE 4: OPERATIONS DASHBOARD (The Command Center)
# ====================================================
if st.session_state.step == "operations":
    # Refetch state on every reload to keep stats fresh
    if st.button("🔄 Refresh Status"):
        payload = {"task": "manager", "user_id": st.session_state.user_id, "params": {}}
        res = requests.post(f"{API_URL}/api/run", json=payload).json()
        st.session_state.project_state = res
        st.rerun()

    report = st.session_state.project_state
    data = report.get('data') or {}
    
    # --- HEADER ---
    st.title(f"⚡ Command Center: {st.session_state.user_id}")
    st.markdown("---")

    # --- STATUS CARDS ---
    if 'stats' in data:
        stats = data['stats']
        c1, c2, c3 = st.columns(3)
        # Handle inconsistent keys from Manager
        loc_count = stats.get("Locations", 0) if "Locations" in stats else stats.get("Found", 0)
        c1.metric("📍 Locations Found", loc_count)
        c2.metric("🔑 Keywords", stats.get("Keywords", 0))
        c3.metric("📄 Pages Drafted", stats.get("Pages", 0))

    # --- 📊 LIVE DATABASE VIEW (NEW) ---
    st.markdown("### 🗃️ Asset Database")
    
    # Create Tabs for visual cleanliness
    tab1, tab2, tab3 = st.tabs(["📍 Locations", "🔑 Keywords", "📄 Pages"])
    
    with tab1:
        # 1. Fetch Locations directly from DB
        locs = memory.get_entities(st.session_state.user_id, "anchor_location")
        if locs:
            # Flatten data for the table
            table_data = []
            for l in locs:
                table_data.append({
                    "Name": l['name'],
                    "Phone": l.get('primary_contact', 'N/A'),
                    "Address": l['metadata'].get('address', 'N/A'),
                    "Website": l['metadata'].get('website', 'N/A')
                })
            st.dataframe(table_data, use_container_width=True)
            st.caption(f"Total: {len(locs)}")
        else:
            st.info("No locations found. Waiting for Scout...")

    with tab2:
        # 2. Fetch Keywords directly from DB
        kws = memory.get_entities(st.session_state.user_id, "seo_keyword")
        if kws:
            table_data = []
            for k in kws:
                table_data.append({
                    "Keyword": k['name'],
                    "Target Location": k['metadata'].get('target_anchor', 'N/A'),
                    "City": k['metadata'].get('city', 'N/A'),
                    "Status": k['metadata'].get('status', 'Pending')
                })
            st.dataframe(table_data, use_container_width=True)
            st.caption(f"Total: {len(kws)}")
        else:
            st.info("No keywords found. Waiting for Strategist...")

    with tab3:
        # 3. Fetch Pages (Future Writer Agent)
        pages = memory.get_entities(st.session_state.user_id, "page_draft")
        if pages:
            st.dataframe(pages, use_container_width=True)
        else:
            st.info("No pages written yet.")
            
    st.markdown("---")
    
    st.markdown("### 🚦 Current Directive")
    
    # --- ACTION AREA ---
    if report['status'] == 'action_required':
        with st.container(border=True):
            st.warning(f"⚠️ {report['message']}")
            st.write(data.get('description'))
            
            # THE DYNAMIC BUTTON
            action_label = data.get('action_label', "Execute")
            if st.button(f"🚀 {action_label}", use_container_width=True):
                
                # EXECUTE THE NEXT TASK
                next_task = data.get('next_task')
                next_params = data.get('next_params', {})
                
                with st.status(f"🤖 Agent Active: {next_task}...", expanded=True) as status:
                    # Construct Payload
                    action_payload = {
                        "task": next_task,
                        "user_id": st.session_state.user_id,
                        "params": next_params
                    }
                    
                    # Call API
                    try:
                        # Note: In real life, for long tasks, we'd use a background queue.
                        # For now, we wait (Synchronous).
                        res = requests.post(f"{API_URL}/api/run", json=action_payload)
                        action_result = res.json()
                        
                        if action_result['status'] == 'success':
                            status.update(label="✅ Mission Complete!", state="complete", expanded=False)
                            st.success(action_result['message'])
                            time.sleep(2)
                            st.rerun() # Refresh to see new state
                        else:
                            status.update(label="❌ Mission Failed", state="error")
                            st.error(action_result.get('message'))
                            
                    except Exception as e:
                        st.error(f"Execution Error: {e}")

    elif report['status'] == 'complete':
        st.success("✅ All Systems Nominal. Campaign is Active.")
        st.info("The OS is monitoring for new leads automatically.")

    else:
        st.error(f"System Error: {report['message']}")

    # Stop here for Operations View
    st.stop()


# ====================================================
# PHASE 1-3: ONBOARDING WIZARD (For New Users)
# ====================================================

# --- SIDEBAR FOR WIZARD ---
with st.sidebar:
    st.header("⚡ Apex Setup")
    if st.button("Logout"):
        st.session_state.user_id = None
        st.session_state.step = "login"
        st.rerun()

# === PHASE 1: THE INPUT ===
if st.session_state.step == "init":
    st.title("🚀 New Project Launch")
    st.markdown("Enter the business website to begin auto-discovery.")
    
    col1, col2 = st.columns(2)
    with col1:
        # Default niche ID based on user to avoid collisions
        default_id = f"proj_{int(time.time())}"
        niche_id = st.text_input("Project ID", value=default_id)
    with col2:
        website_url = st.text_input("Website URL", value="https://")

    if st.button("Analyze Business"):
        if "http" not in website_url:
            st.error("Please enter a valid URL.")
        else:
            with st.spinner("🕵️ Scouting website..."):
                payload = {
                    "task": "scrape_site",
                    "user_id": st.session_state.user_id,
                    "params": {"url": website_url}
                }
                try:
                    response = requests.post(f"{API_URL}/api/run", json=payload)
                    result = response.json()
                    
                    if result['status'] == 'success':
                        st.session_state.scraped_data = result['data']
                        st.session_state.niche_id = niche_id
                        st.session_state.step = "modules"
                        st.rerun()
                    else:
                        st.error(f"Scout Failed: {result['message']}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# === PHASE 2: THE APP STORE ===
elif st.session_state.step == "modules":
    st.title("📦 Select Capabilities")
    
    title = st.session_state.scraped_data.get('title', 'Unknown Site')
    st.success(f"✅ Analyzed: **{title}**")
    
    menu = ModuleManifest.get_user_menu()
    
    with st.form("module_selector"):
        selections = []
        for mod_id, mod_name in menu.items():
            if st.checkbox(mod_name, key=mod_id):
                selections.append(mod_id)
        
        submitted = st.form_submit_button("Configure System")
        
        if submitted:
            if not selections:
                st.warning("Select at least one module.")
            else:
                st.session_state.selected_modules = selections
                
                # PRE-LOAD CONTEXT
                context_payload = {
                    "role": "system",
                    "content": json.dumps({
                        "system_event": "INIT_PHASE_3",
                        "scraped_data": st.session_state.scraped_data.get('content')[:2000],
                        "selected_modules": selections
                    })
                }
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                    
                st.session_state.messages.append(context_payload)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"I see you selected **{', '.join(selections)}**. I've analyzed the site. I have a few configuration questions."
                })
                
                st.session_state.step = "chat"
                st.rerun()

# === PHASE 3: GENESIS CHAT ===
elif st.session_state.step == "chat":
    st.title("🧠 Genesis Consultant")
    
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Answer Genesis..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
                
                payload = {
                    "task": "onboarding",
                    "user_id": st.session_state.user_id,
                    "params": {
                        "message": prompt,
                        "history": history_text,
                        "niche": st.session_state.niche_id
                    }
                }
                
                try:
                    response = requests.post(f"{API_URL}/api/run", json=payload)
                    result = response.json()
                    
                    if result.get('data') and 'reply' in result['data']:
                        ai_reply = result['data']['reply']
                        st.markdown(ai_reply)
                        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                        
                        if result['status'] == 'complete':
                            st.balloons()
                            st.success("✅ Project Registered!")
                            time.sleep(2)
                            st.session_state.step = "login" # Loop back to trigger auto-detection
                            st.rerun()
                    else:
                        st.error(f"Error: {result.get('message')}")

                except Exception as e:
                    st.error(f"API Failed: {e}")