import streamlit as st
import sys
from pathlib import Path

# Add src to the path so we can import modules
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config_manager import ConfigManager

# Load current config into session state for persistence across UI interactions
if 'config' not in st.session_state:
    st.session_state.config = ConfigManager.load_config()
config = st.session_state.config

# --- CLOUD SYNC AT STARTUP ---
if "Streamlit" in str(st.session_state): 
    try:
        from src.storage import sync_db_from_drive
        if not Path(BASE_DIR / "data/jobs.db").exists():
            with st.spinner("☁️ Syncing initial database from Google Drive..."):
                sync_db_from_drive()
    except Exception:
        pass

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
    "AI Document Optimization",
    "Application Assistant",
    "Weekly Market Trends",
    "Prompt Management",
    "Manual Run Control"
])

# ── GLOBAL CONFIG SYNC (SIDEBAR) ──
st.sidebar.divider()
st.sidebar.subheader("⚙️ Quick Settings")

# Date Posted (Shared across all pages)
time_options = ["Last 24 hours", "Past Week", "Past Month", "Any Time"]
curr_time = config["search"]["filters"].get("time_filter", "Last 24 hours")
idx = time_options.index(curr_time) if curr_time in time_options else 0
config["search"]["filters"]["time_filter"] = st.sidebar.selectbox("Global Date Posted", time_options, index=idx, key="global_time_filter")

# --- PAGE LOGIC ---

if page == "Search & Filters":
    st.header("Search & Filters Configuration")
    st.markdown("Control the unified query search constraints.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Job Roles")
        roles_text = st.text_area("Keywords/Roles (one per line)", "\n".join(config["search"]["roles"]), height=200)
        config["search"]["roles"] = [r.strip() for r in roles_text.split("\n") if r.strip()]
        
    with col2:
        st.subheader("Locations")
        locations_text = st.text_area("Search Locations (one per line)", "\n".join(config["search"]["locations"]), height=200)
        config["search"]["locations"] = [l.strip() for l in locations_text.split("\n") if l.strip()]

    st.subheader("LinkedIn URL Filters")
    col3, col4, col5 = st.columns(3)
    
    with col3:
        st.write("**Remote Type**")
        config["search"]["filters"]["remote"] = st.checkbox("Remote", value=config["search"]["filters"]["remote"])
        config["search"]["filters"]["hybrid"] = st.checkbox("Hybrid", value=config["search"]["filters"]["hybrid"])
        config["search"]["filters"]["onsite"] = st.checkbox("Onsite", value=config["search"]["filters"]["onsite"])
        
    with col4:
        st.write("**Experience Level**")
        config["search"]["filters"]["entry_level"] = st.checkbox("Entry level", value=config["search"]["filters"]["entry_level"])
        config["search"]["filters"]["associate"] = st.checkbox("Associate", value=config["search"]["filters"]["associate"])
        config["search"]["filters"]["mid_senior"] = st.checkbox("Mid-Senior level", value=config["search"]["filters"]["mid_senior"])
        
    with col5:
        st.write("**Active Time Filter**")
        st.info(f"Using: {config['search']['filters']['time_filter']} (Select in Sidebar)")
        
    st.button("Save Changes Forever", on_click=save_state, key="save_search")

elif page == "Limits & Scheduler":
    st.header("Limits & Scheduler")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Global Limits")
        config["limits"]["scrape_limit"] = st.number_input("Max Jobs to Scrape", min_value=1, max_value=2000, value=config["limits"]["scrape_limit"])
        config["limits"]["email_limit"] = st.number_input("Email Report Limit", min_value=1, max_value=2000, value=config["limits"]["email_limit"])
    with col2:
        st.subheader("Scheduler")
        config["scheduler"]["enabled"] = st.toggle("Enable Daily Scheduler", value=config["scheduler"]["enabled"])
        times_text = st.text_area("Run Times (HH:MM)", value="\n".join(config["scheduler"].get("run_times", ["07:00"])))
        config["scheduler"]["run_times"] = [t.strip() for t in times_text.split("\n") if t.strip()]
    st.button("Save Changes", on_click=save_state, key="save_limits")

elif page == "Blacklists & Priorities":
    st.header("Blacklists & Priorities")
    col1, col2 = st.columns(2)
    with col1:
        companies_text = st.text_area("Blacklisted Companies", "\n".join(config["blacklist"]["companies"]))
        config["blacklist"]["companies"] = [c.strip() for c in companies_text.split("\n") if c.strip()]
    with col2:
        priority_companies = st.text_area("Priority Companies", "\n".join(config["optional_filters"]["priority_companies"]))
        config["optional_filters"]["priority_companies"] = [p.strip() for p in priority_companies.split("\n") if p.strip()]
    st.button("Save Changes", on_click=save_state, key="save_lists")

elif page == "Jobs Database":
    st.header("📂 Jobs Database")
    st.markdown("View and filter the jobs currently stored in your persistent cloud database.")
    
    import pandas as pd
    import sqlite3
    
    db_path = BASE_DIR / "data/jobs.db"
    if not db_path.exists():
        st.warning("No database found. Run the pipeline or Sync from Drive first.")
    else:
        try:
            conn = sqlite3.connect(db_path)
            # Fetch latest jobs
            df = pd.read_sql_query("SELECT * FROM jobs ORDER BY date_scraped DESC", conn)
            conn.close()
            
            if df.empty:
                st.info("Database is empty. No jobs found yet.")
            else:
                # --- ADVANCED FILTERS ---
                col1, col2 = st.columns(2)
                with col1:
                    search_query = st.text_input("Search Jobs (Company, Title, or URL)", "")
                with col2:
                    min_score = st.slider("Min ATS Score", 0.0, 10.0, 0.0)
                
                if search_query:
                    df = df[df['company'].str.contains(search_query, case=False, na=False) | 
                            df['title'].str.contains(search_query, case=False, na=False)]
                
                df = df[df['ats_score'] >= min_score]
                
                # Display DataFrame
                st.dataframe(
                    df[['title', 'company', 'location', 'ats_score', 'date_scraped', 'job_url']],
                    use_container_width=True,
                    column_config={"job_url": st.column_config.LinkColumn("Job Link")}
                )
                
                st.write("---")
                st.subheader("Selection Details")
                selected_job = st.selectbox("Select a job for full analysis", df['company'] + " - " + df['title'])
                if selected_job:
                    row = df[df['company'] + " - " + df['title'] == selected_job].iloc[0]
                    st.write(f"**ATS Analysis:** {row['match_reason']}")
                        
        except Exception:
            st.info("📊 The database is initialized but the 'Jobs' table is currently empty. Run your first pipeline to see results here!")

elif page == "AI Document Optimization":
    st.header("AI Document Optimization")
    config["optimization"]["enabled"] = st.toggle("Enable Optimization", value=config["optimization"].get("enabled", False))
    st.button("Save Changes", on_click=save_state, key="save_opt")

elif page == "Application Assistant":
    st.header("Application Assistant")
    config["application_assistant"]["enabled"] = st.toggle("Enable Assistant", value=config["application_assistant"].get("enabled", False))
    st.button("Save Changes", on_click=save_state, key="save_app_assist")

elif page == "Prompt Management":
    st.header("Prompt Management")
    new_prompt = st.text_area("Active Prompt", value=config["prompt"]["active_prompt"], height=400)
    if st.button("Save Prompt"):
        config["prompt"]["active_prompt"] = new_prompt
        save_state()

elif page == "Manual Run Control":
    st.header("🚀 Manual Control & Sync")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Download from Drive Now", use_container_width=True):
            from src.storage import sync_db_from_drive
            sync_db_from_drive()
            st.success("Synced!")
    with col_b:
        if st.button("Upload to Drive Now", use_container_width=True):
            from src.storage import sync_db_to_drive
            sync_db_to_drive()
            st.success("Backed up!")

    # ── LIVE VISION EXPLORER ──
    st.divider()
    st.subheader("🕵️‍♂️ Live Vision Evidence (Last Run)")
    from src.config import DATA_DIR
    shot_dir = DATA_DIR / "screenshots"
    if shot_dir.exists():
        shots = sorted(list(shot_dir.glob("*.png")), key=lambda x: x.stat().st_mtime, reverse=True)
        if shots:
            for shot_path in shots[:2]: # Show last 2 evidence photos
                st.image(str(shot_path), use_container_width=True, caption=shot_path.name)
        else:
            st.info("No vision evidence found yet.")
    else:
        st.info("No vision folder detected.")

    st.divider()
    temp_limit = st.number_input("Jobs to Scrape for this run", min_value=1, value=config["limits"]["scrape_limit"])
    if st.button("🔥 Start Pipeline Now", type="primary", use_container_width=True):
        import subprocess
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        orig = config["limits"]["scrape_limit"]
        config["limits"]["scrape_limit"] = temp_limit
        from src.main import run_pipeline
        run_pipeline(config_override=config)
        config["limits"]["scrape_limit"] = orig
        st.success("Done!")
