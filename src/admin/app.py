import streamlit as st
import sys
import importlib
from pathlib import Path
import sqlite3
import pandas as pd

# Add src to the path so we can import modules
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

# --- NUCLEAR CACHE BUSTER (IMMEDIATE) --- 🦾🔄
# We purge the modules BEFORE the first imports to ensure we load the fresh versions
for k in list(sys.modules.keys()):
    if k.startswith("src.") or k in ["migrate_now", "config"]:
        del sys.modules[k]

from src.config_manager import ConfigManager
from src.config import admin_config, DATABASE_URL

# Load current config into session state for persistence
if 'config' not in st.session_state:
    st.session_state.config = ConfigManager.load_config()
config = st.session_state.config

st.set_page_config(page_title="AI Job Scraper Admin", layout="wide", page_icon="🤖")
st.title("🤖 AI Job Pipeline Admin")

# Create a save function
def save_state():
    ConfigManager.save_config(config)
    st.toast("Configuration Saved Successfully!", icon="✅")

# Sidebar Navigation
page = st.sidebar.radio("Navigation", [
    "Search & Filters",
    "Limits & Scheduler",
    "Blacklists & Priorities",
    "Jobs Database",
    "Manual Run Control"
])

# ── LOGIC FOR ALL PAGES ──
engines = ["Playwright (Local)", "Apify (Cloud/Reliable)"]
curr_engine = config.get("scraper_engine", "Playwright").split(" ")[0]
e_idx = 0 if "Playwright" in curr_engine else 1
selected_engine = st.sidebar.selectbox("Active Engine", engines, index=e_idx)
engine_choice = selected_engine.split(" ")[0]

if engine_choice != config.get("scraper_engine", ""):
    config["scraper_engine"] = engine_choice
    save_state()
    st.rerun()

if "Apify" in selected_engine:
    new_token = st.sidebar.text_input("Apify API Token", value=config.get("apify_api_token", ""), type="password")
    if new_token != config.get("apify_api_token", ""):
        config["apify_api_token"] = new_token
        save_state()

# ── PAGE RENDERING ──
if page == "Search & Filters":
    st.header("🔍 Search Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        roles_text = st.text_area("Job Roles (one per line)", value="\n".join(config["search"]["roles"]))
        config["search"]["roles"] = [r.strip() for r in roles_text.split("\n") if r.strip()]
        
        locations_text = st.text_area("Locations (one per line)", value="\n".join(config["search"]["locations"]))
        config["search"]["locations"] = [l.strip() for l in locations_text.split("\n") if l.strip()]

    with col2:
        time_options = ["Past 24 hours", "Past week", "Past month"]
        curr_time = config["search"]["filters"].get("time_filter", "Past 24 hours")
        t_idx = time_options.index(curr_time) if curr_time in time_options else 0
        new_time = st.selectbox("Time Filter", time_options, index=t_idx)
        config["search"]["filters"]["time_filter"] = new_time
        
        # Immediate sync for global state
        st.session_state.global_time_filter = new_time

    if st.button("Save Search Settings"):
        save_state()

elif page == "Limits & Scheduler":
    st.header("⚖️ Scraping Limits & Schedule")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Limits")
        config["limits"]["scrape_limit"] = st.number_input("Max Jobs per Run", value=config["limits"]["scrape_limit"], min_value=1)
        config["limits"]["email_limit"] = st.number_input("Max Jobs in Report", value=config["limits"]["email_limit"], min_value=1)

    with col2:
        st.subheader("Daily Schedule")
        times_text = st.text_input("Run Time (24h, comma separated)", value=",".join(config["scheduler"]["run_times"]))
        config["scheduler"]["run_times"] = [t.strip() for t in times_text.split(",") if t.strip()]

    if st.button("Save Schedule Settings"):
        save_state()

elif page == "Blacklists & Priorities":
    st.header("🚫 Blacklists & Priorities")
    
    col1, col2 = st.columns(2)
    with col1:
        bl_text = st.text_area("Blacklisted Companies (one per line)", value="\n".join(config.get("blacklist", {}).get("companies", [])))
        if "blacklist" not in config: config["blacklist"] = {"companies": []}
        config["blacklist"]["companies"] = [c.strip() for c in bl_text.split("\n") if c.strip()]
        
    if st.button("Save Blacklist Settings"):
        save_state()

elif page == "Jobs Database":
    st.header("📂 Jobs Database")
    
    # Database Display from current DATABASE_URL (Supports Cloud vs Local automatically)
    try:
        from sqlalchemy import create_engine
        engine = create_engine(DATABASE_URL)
        df = pd.read_sql_query("SELECT title, company, location, ats_score, scraped_date, link FROM jobs ORDER BY id DESC", engine)
        st.dataframe(df, use_column_width=True)
    except Exception as e:
        st.info(f"📊 Database status: Waiting for migration or first run. ({e})")

elif page == "Manual Run Control":
    st.header("🚀 Manual Control & Migration")
    
    ca, cb, cc, cd = st.columns(4)
    with ca:
        if st.button("Download Drive ⬇️", use_container_width=True):
            from src.storage import sync_db_from_drive
            sync_db_from_drive()
            st.success("Synced!")
    with cb:
        if st.button("Backup Drive ⬆️", use_container_width=True):
            from src.storage import sync_db_to_drive
            sync_db_to_drive()
            st.success("Backed up!")
    with cc:
        if st.button("🧪 Diagnostics", use_container_width=True):
            st.info("Check your logs for current vision status.")
            
    with cd:
        if st.button("MIGRATE TO CLOUD 🛰️", type="primary", use_container_width=True):
            with st.spinner("🚀 BEAMING DATA TO SUPABASE..."):
                try:
                    import migrate_now
                    migrate_now.migrate()
                    st.success("✅ MIGRATION SUCCESSFUL! The cloud brain is live.")
                    st.session_state.config = ConfigManager.load_config()
                    st.rerun()
                except Exception as e:
                    st.error(f"Migration Failed: {e}")

    st.divider()
    temp_limit = st.number_input("Jobs for THIS run only", min_value=1, value=config["limits"]["scrape_limit"])
    if st.button("🔥 Start Pipeline Now", type="primary"):
        with st.spinner("🚀 Running Optimized Apify Pipeline..."):
            import src.main
            orig_limit = config["limits"]["scrape_limit"]
            config["limits"]["scrape_limit"] = temp_limit
            src.main.run_pipeline(config_override=config)
            config["limits"]["scrape_limit"] = orig_limit
            st.success("Done!")

else:
    st.info("Select a page from the sidebar to continue.")
