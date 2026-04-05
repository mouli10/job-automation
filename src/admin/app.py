import streamlit as st
import sys
import importlib
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
        # Force a sync at startup to ensure we aren't using an empty Github placeholder
        with st.spinner("☁️ Syncing latest database from Google Drive..."):
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

# Date Posted (Standardized Spelling)
time_options = ["Last 24 hours", "Past Week", "Past Month", "Any Time"]
curr_time = config["search"]["filters"].get("time_filter", "Last 24 hours")
idx = time_options.index(curr_time) if curr_time in time_options else 0
config["search"]["filters"]["time_filter"] = st.sidebar.selectbox("Global Date Posted", time_options, index=idx, key="global_time_filter")

# ── ENGINE SELECTOR ──
st.sidebar.divider()
st.sidebar.subheader("🚀 Scraper Engine")
engines = ["Playwright (Local/Free)", "Apify (Cloud/Reliable)"]
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

# ── COOKIE WIZARD ──
st.sidebar.divider()
st.sidebar.subheader("🗝️ Authentication")
new_li_at = st.sidebar.text_input("Refresh LI_AT Cookie", value="", type="password", key="li_at_input")
if st.sidebar.button("Update Login Session"):
    if new_li_at:
        config["linkedin"] = config.get("linkedin", {})
        config["linkedin"]["li_at_cookie"] = new_li_at
        save_state()
        st.sidebar.success("Session Updated!")

st.sidebar.divider()
st.sidebar.subheader("🛑 Emergency Stop")
if st.sidebar.button("Force Unlock & Stop Background Pipeline"):
    from src.config import DATA_DIR
    lf = DATA_DIR / "pipeline.lock"
    if lf.exists():
        try:
            pid = int(lf.read_text().strip())
            import psutil
            p = psutil.Process(pid)
            p.terminate()
        except:
            pass
        lf.unlink(missing_ok=True)
    st.sidebar.success("🛑 Process Killed and Lock Removed! You can start again.")

# --- PAGE LOGIC ---


if page == "Search & Filters":
    st.header("Search & Filters Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Job Roles")
        roles_text = st.text_area("Keywords/Roles", "\n".join(config["search"]["roles"]), height=200)
        config["search"]["roles"] = [r.strip() for r in roles_text.split("\n") if r.strip()]
    with col2:
        st.subheader("Locations")
        locations_text = st.text_area("Search Locations", "\n".join(config["search"]["locations"]), height=200)
        config["search"]["locations"] = [l.strip() for l in locations_text.split("\n") if l.strip()]
    st.button("Save Changes Forever", on_click=save_state, key="save_search")

elif page == "Blacklists & Priorities":
    st.header("🚫 Blacklists & Exclusion Filters")
    st.info("Jobs from these companies or with these keywords will be hidden automatically by your 'Zero-Waste Shield'.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Blacklisted Companies")
        companies_text = st.text_area("Target companies to exclude (one per line)", 
                                      "\n".join(config["blacklist"]["companies"]), height=250)
        config["blacklist"]["companies"] = [c.strip() for c in companies_text.split("\n") if c.strip()]
        
    with col2:
        st.subheader("Blacklisted Keywords")
        keywords_text = st.text_area("Avoid jobs with these words in title (one per line)", 
                                     "\n".join(config["blacklist"]["keywords"]), height=110)
        config["blacklist"]["keywords"] = [k.strip() for k in keywords_text.split("\n") if k.strip()]
        
        st.subheader("Blacklisted Roles")
        roles_text = st.text_area("Exclude these exact job titles (one per line)", 
                                  "\n".join(config["blacklist"]["roles"]), height=110)
        config["blacklist"]["roles"] = [r.strip() for r in roles_text.split("\n") if r.strip()]
        
    st.button("Save Blacklist Settings Forever", on_click=save_state, key="save_blacklist")

elif page == "Jobs Database":
    st.header("📂 Jobs Database")
    import pandas as pd
    import sqlite3
    db_path = BASE_DIR / "data/jobs.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT * FROM jobs ORDER BY scraped_date DESC", conn)
            conn.close()
            st.dataframe(df[['title', 'company', 'location', 'ats_score', 'scraped_date', 'job_url']], use_column_width=True)
        except Exception:
            st.info("📊 Database ready, but the Jobs table is currently empty.")

elif page == "Manual Run Control":
    st.header("🚀 Manual Control & Sync")
    
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("Download Drive ⬇️", use_container_width=True):
            from src.storage import sync_db_from_drive
            sync_db_from_drive()
            st.success("Synced!")
    with col_b:
        if st.button("Backup Drive ⬆️", use_container_width=True):
            from src.storage import sync_db_to_drive
            sync_db_to_drive()
            st.success("Backed up!")
    with col_c:
        sub1, sub2 = st.columns(2)
        with sub1:
            if st.button("🧪 Feed Selfie", use_container_width=True):
                with st.spinner("Taking Feed Selfie..."):
                    try:
                        import subprocess, asyncio
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                        from src.scraper.vision import capture_screenshot
                        from src.storage import sync_screenshots_to_drive
                        from playwright.async_api import async_playwright
                        from src.config import CHROME_PROFILE_DIR
                        async def run_vision_test():
                            async with async_playwright() as p:
                                context = await p.chromium.launch_persistent_context(user_data_dir=str(CHROME_PROFILE_DIR), headless=True)
                                if config and "linkedin" in config and "li_at_cookie" in config["linkedin"]:
                                    await context.add_cookies([{"name": "li_at", "value": config["linkedin"]["li_at_cookie"], "domain": ".www.linkedin.com", "path": "/"}])
                                page = await context.new_page()
                                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                                await capture_screenshot(page, "DIAGNOSTIC_FEED_SELFIE")
                                await context.close()
                        asyncio.run(run_vision_test())
                        sync_screenshots_to_drive()
                        st.success("📸 Check Drive!")
                    except Exception as e: st.error(f"Failed: {e}")
        with sub2:
            if st.button("🧪 Search Selfie", use_container_width=True):
                with st.spinner("Visiting Search Page..."):
                    try:
                        import subprocess, asyncio
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                        from src.scraper.vision import capture_screenshot
                        from src.storage import sync_screenshots_to_drive
                        from src.scraper.linkedin import build_combined_query, build_li_filters
                        from playwright.async_api import async_playwright
                        from src.config import CHROME_PROFILE_DIR
                        async def run_search_test():
                            async with async_playwright() as p:
                                context = await p.chromium.launch_persistent_context(user_data_dir=str(CHROME_PROFILE_DIR), headless=True)
                                if config and "linkedin" in config and "li_at_cookie" in config["linkedin"]:
                                    await context.add_cookies([{"name": "li_at", "value": config["linkedin"]["li_at_cookie"], "domain": ".www.linkedin.com", "path": "/"}])
                                page = await context.new_page()
                                q = build_combined_query(config["search"]["roles"])
                                f = build_li_filters(config["search"]["filters"])
                                loc = config["search"]["locations"][0] if config["search"]["locations"] else "United States"
                                url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}&{f}"
                                await page.goto(url, wait_until="domcontentloaded")
                                await capture_screenshot(page, "DIAGNOSTIC_SEARCH_SELFIE")
                                await context.close()
                        asyncio.run(run_search_test())
                        sync_screenshots_to_drive()
                        st.success("📸 Check Drive!")
                    except Exception as e: st.error(f"Failed: {e}")
        if st.button("MIGRATE TO CLOUD 🛰️", type="primary", use_container_width=True):
            with st.spinner("🚀 Porting to Supabase..."):
                try:
                    # --- NUCLEAR CACHE BUSTER --- 🦾🔄
                    import sys
                    for k in list(sys.modules.keys()):
                        if k.startswith("src.") or k == "migrate_now":
                            del sys.modules[k]
                    
                    import migrate_now
                    importlib.reload(migrate_now)  # Extra safety 🤝
                    migrate_now.migrate()
                    st.success("✅ MIGRATION SUCCESSFUL! The cloud brain is live.")
                    # Force a refresh to load cloud settings
                    st.session_state.config = ConfigManager.load_config()
                    st.rerun()
                except Exception as e:
                    st.error(f"Migration Failed: {e}")
                with st.spinner("Visiting Search Page..."):
                    try:
                        import subprocess, asyncio
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                        from src.scraper.vision import capture_screenshot
                        from src.storage import sync_screenshots_to_drive
                        from src.scraper.linkedin import build_combined_query, build_li_filters
                        from playwright.async_api import async_playwright
                        from src.config import CHROME_PROFILE_DIR
                        async def run_search_test():
                            async with async_playwright() as p:
                                context = await p.chromium.launch_persistent_context(user_data_dir=str(CHROME_PROFILE_DIR), headless=True)
                                if config and "linkedin" in config and "li_at_cookie" in config["linkedin"]:
                                    await context.add_cookies([{"name": "li_at", "value": config["linkedin"]["li_at_cookie"], "domain": ".www.linkedin.com", "path": "/"}])
                                page = await context.new_page()
                                q = build_combined_query(config["search"]["roles"])
                                f = build_li_filters(config["search"]["filters"])
                                loc = config["search"]["locations"][0] if config["search"]["locations"] else "United States"
                                url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}&{f}"
                                await page.goto(url, wait_until="domcontentloaded")
                                await capture_screenshot(page, "DIAGNOSTIC_SEARCH_SELFIE")
                                await context.close()
                        asyncio.run(run_search_test())
                        sync_screenshots_to_drive()
                        st.success("📸 Check Drive!")
                    except Exception as e: st.error(f"Failed: {e}")

    # ── LIVE VISION EXPLORER ──
    st.divider()
    st.subheader("🕵️‍♂️ Live Vision Evidence (Last Run)")
    from src.config import DATA_DIR
    shot_dir = DATA_DIR / "screenshots"
    if shot_dir.exists():
        shots = sorted(list(shot_dir.glob("*.png")), key=lambda x: x.stat().st_mtime, reverse=True)
        if shots:
            for shot_path in shots[:2]: 
                st.image(str(shot_path), use_column_width=True, caption=shot_path.name)
        else: st.info("No vision evidence found yet.")
    else: st.info("No vision folder detected.")

    st.divider()
    temp_limit = st.number_input("Jobs to Scrape for this run", min_value=1, value=config["limits"]["scrape_limit"])
    if st.button("🔥 Start Pipeline Now", type="primary", use_container_width=True):
        import subprocess
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        
        # --- NUCLEAR CACHE BUSTER ---
        # Streamlit relentlessly caches old modules. We must obliterate them.
        import sys
        for k in list(sys.modules.keys()):
            if k.startswith("src."):
                del sys.modules[k]
        
        # --- IRONCLAD PERSISTENCE ---
        config["search"]["filters"]["time_filter"] = st.session_state.global_time_filter
        st.write(f"🚀 ATOMIC SYNC: Filter forced to **{config['search']['filters']['time_filter']}**")
        
        orig_limit = config["limits"]["scrape_limit"]
        config["limits"]["scrape_limit"] = temp_limit
        import src.main
        src.main.run_pipeline(config_override=config)
        config["limits"]["scrape_limit"] = orig_limit
        st.success("Done!")

else:
    st.info("Select a page from the sidebar to continue.")
