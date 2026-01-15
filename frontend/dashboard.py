# frontend/dashboard.py
import streamlit as st
import requests
import json

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(page_title="Apex OS Console", page_icon="⚡", layout="wide")

# Header
st.title("⚡ Apex Sovereign OS")
st.markdown("---")

# Sidebar: System Status
st.sidebar.header("System Status")
try:
    status = requests.get(f"{API_URL}/").json()
    st.sidebar.success(f"🟢 Online")
    st.sidebar.json(status)
except:
    st.sidebar.error("🔴 Offline")
    st.stop()

# Main Area: Command Center
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📡 Dispatch Command")
    
    # Inputs
    task_name = st.selectbox("Select Task", ["scrape_leads", "generate_strategy", "write_content", "custom"])
    if task_name == "custom":
        task_name = st.text_input("Enter Custom Task Name")
        
    target_niche = st.text_input("Target Niche", value="plumber")
    target_city = st.text_input("Target City", value="Auckland")
    
    # Execute Button
    if st.button("🚀 Execute Agent", type="primary"):
        with st.spinner("Dispatching to Kernel..."):
            payload = {
                "task": task_name,
                "user_id": "admin",
                "params": {
                    "niche": target_niche,
                    "city": target_city
                }
            }
            
            try:
                response = requests.post(f"{API_URL}/api/run", json=payload)
                st.session_state['last_result'] = response.json()
            except Exception as e:
                st.error(f"Connection Error: {e}")

with col2:
    st.subheader("🖥️ Kernel Output")
    
    if 'last_result' in st.session_state:
        result = st.session_state['last_result']
        
        # Status Badge
        if result['status'] == 'success':
            st.success(f"✅ {result['message']}")
        else:
            st.error(f"❌ {result['message']}")
            
        # Data Viewer
        st.markdown("### Payload Data")
        st.json(result['data'])
        
        st.markdown("### Metadata")
        st.caption(f"Timestamp: {result['timestamp']}")
    else:
        st.info("Waiting for command...")