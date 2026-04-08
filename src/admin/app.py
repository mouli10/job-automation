import streamlit as st
import sys
import importlib
from pathlib import Path
import pandas as pd

# Add src to the path so we can import modules
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))




from src.config_manager import ConfigManager
from src.config import admin_config, DATABASE_URL

# Load current config into session state for persistence
if 'config' not in st.session_state:
    st.session_state.config = ConfigManager.load_config()
config = st.session_state.config

st.set_page_config(page_title="AI Job Scraper Admin", layout="wide", page_icon="🤖")
st.title("🤖 AI Job Pipeline Admin")

def save_state():
    ConfigManager.save_config(config)
    st.toast("Configuration Saved Successfully!", icon="✅")

# ── SIDEBAR NAVIGATION ──
page = st.sidebar.radio("Navigation", [
    "Search & Filters",
    "Limits & Scheduler",
    "Blacklists & Priorities",
    "Jobs Database",
    "AI Document Optimization",
    "Application Assistant",
    "Prompt Management",
    "Weekly Market Trends",
    "Resume Management",
    "Manual Run Control"
])

st.sidebar.divider()
st.sidebar.subheader("⚙️ Quick Settings")

# ── GLOBAL TIME FILTER (Sidebar) ──
time_options_sidebar = ["Last 24 hours", "Past Week", "Past Month", "Any Time"]
curr_time_sb = config["search"]["filters"].get("time_filter", "Last 24 hours")
idx_sb = time_options_sidebar.index(curr_time_sb) if curr_time_sb in time_options_sidebar else 0
config["search"]["filters"]["time_filter"] = st.sidebar.selectbox(
    "Global Date Posted", time_options_sidebar, index=idx_sb, key="global_time_filter"
)

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

# ── EMERGENCY STOP ──
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
        except Exception:
            pass
        lf.unlink(missing_ok=True)
    st.sidebar.success("🛑 Process Killed and Lock Removed!")

# ═══════════════════════════════════════════════════
# PAGE: SEARCH & FILTERS
# ═══════════════════════════════════════════════════
if page == "Search & Filters":
    st.header("🔍 Search & Filters Configuration")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Job Roles")
        roles_text = st.text_area("Keywords / Roles (one per line)", "\n".join(config["search"]["roles"]), height=200)
        config["search"]["roles"] = [r.strip() for r in roles_text.split("\n") if r.strip()]

        st.subheader("Locations")
        locations_text = st.text_area("Search Locations (one per line)", "\n".join(config["search"]["locations"]), height=150)
        config["search"]["locations"] = [l.strip() for l in locations_text.split("\n") if l.strip()]

    with col2:
        st.subheader("Time & Sort")
        time_options = ["Last 24 hours", "Past Week", "Past Month", "Any Time"]
        curr_time = config["search"]["filters"].get("time_filter", "Last 24 hours")
        t_idx = time_options.index(curr_time) if curr_time in time_options else 0
        new_time = st.selectbox("⏱️ Time Filter", time_options, index=t_idx)
        config["search"]["filters"]["time_filter"] = new_time

        sort_options = ["Most Recent", "Most Relevant"]
        curr_sort = config["search"]["filters"].get("sort_by", "Most Recent")
        s_idx = sort_options.index(curr_sort) if curr_sort in sort_options else 0
        new_sort = st.selectbox("🔃 Sort By", sort_options, index=s_idx)
        config["search"]["filters"]["sort_by"] = new_sort

        st.subheader("🎯 Experience Level")
        st.caption("Select which LinkedIn experience levels to include in search.")
        f = config["search"]["filters"]
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            f["internship"]  = st.checkbox("Internship",       value=f.get("internship", False))
            f["entry_level"] = st.checkbox("Entry Level",      value=f.get("entry_level", False))
            f["associate"]   = st.checkbox("Associate",        value=f.get("associate", False))
        with exp_col2:
            f["mid_senior"]  = st.checkbox("Mid-Senior Level", value=f.get("mid_senior", True))
            f["director"]    = st.checkbox("Director",         value=f.get("director", False))
            f["executive"]   = st.checkbox("Executive",        value=f.get("executive", False))
        config["search"]["filters"] = f

        st.subheader("Work Type")
        wt_col1, wt_col2, wt_col3 = st.columns(3)
        with wt_col1:
            f["onsite"] = st.checkbox("Onsite", value=f.get("onsite", False))
        with wt_col2:
            f["remote"] = st.checkbox("Remote", value=f.get("remote", False))
        with wt_col3:
            f["hybrid"] = st.checkbox("Hybrid", value=f.get("hybrid", False))

    st.button("💾 Save Search Settings", on_click=save_state, key="save_search", type="primary")

# ═══════════════════════════════════════════════════
# PAGE: LIMITS & SCHEDULER
# ═══════════════════════════════════════════════════
elif page == "Limits & Scheduler":
    st.header("⚖️ Limits & Scheduler")
    st.markdown("Set constraints for how many jobs the scraper extracts and evaluates.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Job Volume Limits")

        config["limits"]["scrape_limit"] = st.number_input(
            "Max Jobs to Scrape per Run",
            min_value=1, max_value=2000,
            value=config["limits"]["scrape_limit"],
            help="🔢 Hard stop — scraper will collect exactly this many jobs and stop. Higher = more Apify credits used."
        )
        config["limits"]["email_limit"] = st.number_input(
            "Top Jobs in Email Report",
            min_value=1, max_value=2000,
            value=config["limits"]["email_limit"],
            help="📧 After scoring all jobs by ATS match, only the top N best matches will appear in your email Excel report."
        )
        config["limits"]["db_retention_days"] = st.number_input(
            "Data Retention (days)",
            min_value=7, max_value=365,
            value=int(config["limits"].get("db_retention_days", 60)),
            help="🗑️ Jobs older than this many days are automatically deleted from your Supabase database to save space. You get a warning email 7 days before the purge happens. Default: 60 days."
        )

        st.divider()
        st.subheader("🛡️ Anti-Detection Safety (Playwright only)")
        st.caption("These control how human-like the LinkedIn browser scraper behaves. Too fast = LinkedIn blocks you. Too slow = takes a long time.")

        delay_col1, delay_col2 = st.columns(2)
        with delay_col1:
            config["limits"]["scraper_min_delay"] = st.number_input(
                "Min Click Delay (seconds)",
                min_value=1, max_value=30,
                value=int(config["limits"].get("scraper_min_delay", 3)),
                help="⏱️ Minimum seconds the scraper waits between clicking on job cards. Keeps LinkedIn from detecting robotic speed. Recommended: 3s"
            )
        with delay_col2:
            config["limits"]["scraper_max_delay"] = st.number_input(
                "Max Click Delay (seconds)",
                min_value=1, max_value=60,
                value=int(config["limits"].get("scraper_max_delay", 8)),
                help="⏱️ Maximum seconds the scraper waits between clicks. The actual delay is a random number between Min and Max, making it look human. Recommended: 8s"
            )

        config["limits"]["scraper_max_pages"] = st.number_input(
            "Max LinkedIn Pages per Search",
            min_value=1, max_value=20,
            value=int(config["limits"].get("scraper_max_pages", 5)),
            help="📄 LinkedIn shows 25 jobs per page. Setting this to 5 means the scraper reads 5 pages × 25 = up to 125 jobs per search. Only applies to Playwright engine — Apify uses the job limit directly."
        )

    with col2:
        st.subheader("🗓️ Scheduler")

        config["scheduler"]["enabled"] = st.toggle(
            "Enable Daily Scheduler",
            value=config["scheduler"]["enabled"],
            help="⏰ When ON, the pipeline runs automatically every day at the times you set below. When OFF, you must click 'Start Pipeline' manually from the Manual Run Control page."
        )
        times_text = st.text_area(
            "Scheduled Run Times (HH:MM, one per line)",
            value="\n".join(config["scheduler"].get("run_times", ["07:00"])),
            help="🕐 Enter times in 24-hour format. E.g., 07:00 means 7 AM. You can add multiple times (one per line) to run the pipeline more than once a day."
        )
        valid_times = []
        for line in times_text.split("\n"):
            t = line.strip()
            if not t:
                continue
            if ":" in t and len(t) == 5:
                valid_times.append(t)
            else:
                st.error(f"Invalid time format: '{t}'. Use HH:MM (e.g. 07:00).")
        config["scheduler"]["run_times"] = valid_times

        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        config["scheduler"]["run_days"] = st.multiselect(
            "Active Reporting Days",
            options=all_days,
            default=config["scheduler"].get("run_days", all_days),
            help="📅 Uncheck days when you don't want the pipeline to run automatically. E.g., uncheck Saturday & Sunday if you only want weekday reports."
        )
        if valid_times:
            st.info(f"🗓️ Active: {', '.join(valid_times)} on {len(config['scheduler']['run_days'])} day(s)/week")

    st.button("💾 Save Schedule Settings", on_click=save_state, key="save_limits", type="primary")


# ═══════════════════════════════════════════════════
# PAGE: BLACKLISTS & PRIORITIES
# ═══════════════════════════════════════════════════
elif page == "Blacklists & Priorities":
    st.header("🚫 Blacklists & Priorities")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Blacklists (Skip entire job)")
        companies_text = st.text_area(
            "Blacklisted Companies (one per line)",
            "\n".join(config["blacklist"]["companies"]),
            help="If seen, immediately skip job before any API call.",
            height=150
        )
        config["blacklist"]["companies"] = [c.strip() for c in companies_text.split("\n") if c.strip()]

        keywords_text = st.text_area(
            "Blacklisted Keywords in Title (one per line)",
            "\n".join(config["blacklist"]["keywords"]),
            help="Skip jobs whose title contains any of these words.",
            height=150
        )
        config["blacklist"]["keywords"] = [k.strip() for k in keywords_text.split("\n") if k.strip()]

    with col2:
        st.subheader("Scoring Priorities")
        config["optional_filters"]["min_ats_score"] = st.slider(
            "Absolute Minimum ATS Score in Report",
            min_value=0.0, max_value=10.0,
            value=config["optional_filters"].get("min_ats_score", 5.0),
            step=0.1
        )

        priority_companies = st.text_area(
            "Priority Companies (one per line)",
            "\n".join(config["optional_filters"].get("priority_companies", [])),
            help="These companies get a ranking boost.",
            height=100
        )
        config["optional_filters"]["priority_companies"] = [p.strip() for p in priority_companies.split("\n") if p.strip()]

        config["optional_filters"]["keyword_priority_boost"] = st.checkbox(
            "Enable Keyword Priority Boost (+2.0 points)",
            value=config["optional_filters"].get("keyword_priority_boost", False)
        )
        if "priority_keywords" not in config["optional_filters"]:
            config["optional_filters"]["priority_keywords"] = []
        priority_keywords = st.text_area(
            "Priority Keywords (+2 pts if found in title)",
            "\n".join(config["optional_filters"]["priority_keywords"]),
            height=100
        )
        config["optional_filters"]["priority_keywords"] = [k.strip() for k in priority_keywords.split("\n") if k.strip()]

    st.button("💾 Save Blacklist Settings", on_click=save_state, key="save_lists", type="primary")

# ═══════════════════════════════════════════════════
# PAGE: JOBS DATABASE
# ═══════════════════════════════════════════════════
elif page == "Jobs Database":
    st.header("📂 Jobs Database")
    try:
        from sqlalchemy import create_engine
        db_engine = create_engine(DATABASE_URL)
        df = pd.read_sql_query(
            "SELECT title, company, location, ats_score, scraped_date, link FROM jobs ORDER BY id DESC",
            db_engine
        )
        st.dataframe(df, use_container_width=True)
        st.caption(f"Total jobs in cloud: {len(df)}")
    except Exception as e:
        st.info(f"📊 Database status: Waiting for migration or first run. ({e})")

# ═══════════════════════════════════════════════════
# PAGE: AI DOCUMENT OPTIMIZATION
# ═══════════════════════════════════════════════════
elif page == "AI Document Optimization":
    st.header("📄 AI Document Optimization")
    st.markdown("Control when and how the AI automatically tailors your resume to match job descriptions.")

    if "optimization" not in config:
        config["optimization"] = {"enabled": False, "min_ats": 5.0, "max_ats": 8.0}

    config["optimization"]["enabled"] = st.toggle(
        "Enable Strict Inline Optimization",
        value=config["optimization"]["enabled"]
    )

    st.write("Only run the optimization prompt if the baseline ATS score falls within this range:")
    col1, col2 = st.columns(2)
    with col1:
        config["optimization"]["min_ats"] = st.number_input(
            "Minimum ATS Score Threshold",
            min_value=0.0, max_value=10.0,
            value=float(config["optimization"].get("min_ats", 5.0)),
            step=0.5
        )
    with col2:
        config["optimization"]["max_ats"] = st.number_input(
            "Maximum ATS Score Threshold",
            min_value=0.0, max_value=10.0,
            value=float(config["optimization"].get("max_ats", 8.0)),
            step=0.5
        )

    st.button("💾 Save Optimization Settings", on_click=save_state, key="save_opt", type="primary")

# ═══════════════════════════════════════════════════
# PAGE: APPLICATION ASSISTANT
# ═══════════════════════════════════════════════════
elif page == "Application Assistant":
    st.header("✍️ Application Assistant")
    st.markdown("Instantly generate short application summaries and tailored `.docx` cover letters for matched jobs.")

    if "application_assistant" not in config:
        config["application_assistant"] = {"enabled": False, "generate_cover_letter": False}

    config["application_assistant"]["enabled"] = st.toggle(
        "Enable Application Assistant (Generates 'Why Good Fit' in Excel)",
        value=config["application_assistant"]["enabled"]
    )

    st.divider()
    st.subheader("Cover Letter Generation")
    st.markdown("Builds a custom 3–5 paragraph targeted cover letter `.docx` saved to your `data/cover_letters` directory and uploaded to Google Drive.")
    config["application_assistant"]["generate_cover_letter"] = st.toggle(
        "Generate Cover Letter File",
        value=config["application_assistant"]["generate_cover_letter"]
    )

    st.button("💾 Save Assistant Settings", on_click=save_state, key="save_app_assist", type="primary")

# ═══════════════════════════════════════════════════
# PAGE: PROMPT MANAGEMENT
# ═══════════════════════════════════════════════════
elif page == "Prompt Management":
    st.header("🧠 Prompt Management")
    st.markdown("Directly tweak the intelligence core of the underlying AI. Use variables `{job_desc}` and `{resume_text}`.")

    new_prompt = st.text_area(
        "Active ATS Scoring Prompt",
        value=config["prompt"]["active_prompt"],
        height=400
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Save Custom Prompt", use_container_width=True, type="primary"):
            if "{job_desc}" not in new_prompt or "{resume_text}" not in new_prompt:
                st.error("Prompt MUST contain `{job_desc}` and `{resume_text}`!")
            else:
                if new_prompt != config["prompt"]["active_prompt"]:
                    config["prompt"]["prompt_history"].append(config["prompt"]["active_prompt"])
                    if len(config["prompt"]["prompt_history"]) > 10:
                        config["prompt"]["prompt_history"].pop(0)
                config["prompt"]["active_prompt"] = new_prompt
                save_state()
                st.success("Prompt saved!")

    with col2:
        if st.button("🔄 Reset to Default Template", use_container_width=True):
            config["prompt"]["active_prompt"] = config["prompt"]["default_prompt"]
            save_state()
            st.rerun()

    with col3:
        if len(config["prompt"].get("prompt_history", [])) > 0:
            if st.button("⏪ Undo (Revert to Previous)", use_container_width=True):
                config["prompt"]["active_prompt"] = config["prompt"]["prompt_history"].pop()
                save_state()
                st.rerun()

# ═══════════════════════════════════════════════════
# PAGE: WEEKLY MARKET TRENDS
# ═══════════════════════════════════════════════════
elif page == "Weekly Market Trends":
    st.header("📊 Weekly Market Trends")
    st.markdown(
        "Every **Sunday morning**, the pipeline will mine the jobs it collected that week "
        "and email you an interactive chart showing the most in-demand tools and keywords."
    )

    if "weekly_trends" not in config:
        config["weekly_trends"] = {"enabled": True, "analysis_window_days": 7, "top_n_keywords": 20}

    config["weekly_trends"]["enabled"] = st.toggle(
        "Enable Weekly Trends Email (fires every Sunday)",
        value=config["weekly_trends"]["enabled"]
    )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        window_opts = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}
        current_window = config["weekly_trends"].get("analysis_window_days", 7)
        current_label = next((k for k, v in window_opts.items() if v == current_window), "Last 7 days")
        chosen = st.selectbox("Analysis Window", list(window_opts.keys()),
                              index=list(window_opts.keys()).index(current_label))
        config["weekly_trends"]["analysis_window_days"] = window_opts[chosen]

    with col2:
        config["weekly_trends"]["top_n_keywords"] = st.selectbox(
            "Top N Keywords to Show",
            [10, 15, 20, 25],
            index=[10, 15, 20, 25].index(config["weekly_trends"].get("top_n_keywords", 20))
        )

    st.divider()
    st.subheader("🧪 Run Now (Test Mode)")
    st.caption("Generate and email the trends chart immediately without waiting for Sunday.")
    if st.button("📤 Generate & Send Trends Report Now", use_container_width=True):
        with st.spinner("Analysing jobs database and generating chart..."):
            try:
                from src.analytics.market_trends import get_keyword_frequencies
                from src.analytics.chart_generator import generate_trends_chart
                from src.reporting.email_sender import send_weekly_trends_report

                win = config["weekly_trends"]["analysis_window_days"]
                top_n = config["weekly_trends"]["top_n_keywords"]
                ranked = get_keyword_frequencies(window_days=win, top_n=top_n)
                if not ranked:
                    st.warning("No job data found. Run the pipeline first to collect jobs.")
                else:
                    chart_path = generate_trends_chart(ranked, window_days=win)
                    if chart_path:
                        send_weekly_trends_report(chart_path, ranked, window_days=win)
                        st.success(f"✅ Emailed! Top keyword: **{ranked[0][0]}** ({ranked[0][1]} mentions)")
                    else:
                        st.error("Chart generation failed. Check if kaleido is installed.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.button("💾 Save Trends Settings", on_click=save_state, key="save_trends", type="primary")

# ═══════════════════════════════════════════════════
# PAGE: MANUAL RUN CONTROL
# ═══════════════════════════════════════════════════
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
            st.info("Check your terminal logs for current status.")
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
        with st.spinner("🚀 Running Pipeline..."):
            import src.main
            orig_limit = config["limits"]["scrape_limit"]
            config["limits"]["scrape_limit"] = temp_limit
            src.main.run_pipeline(config_override=config)
            config["limits"]["scrape_limit"] = orig_limit
            st.success("Done!")

elif page == "Resume Management":
    st.header("📄 Resume Management")
    st.markdown(
        "Upload your resume files here. They are stored securely in **Supabase Storage** "
        "and downloaded automatically each time the pipeline runs to score your resumes against jobs."
    )
    st.info("💡 Google Drive is used only for **outputting** optimized resumes and cover letters — not for storing your base resumes.")

    # ── Upload Section ─────────────────────────────────────────────────────
    st.subheader("⬆️ Upload New Resume")
    uploaded_file = st.file_uploader(
        "Choose your resume file",
        type=["pdf", "docx"],
        help="PDF is recommended. DOCX is also supported. Your file will be stored in Supabase Storage."
    )

    if uploaded_file:
        col_prev, col_upload = st.columns([3, 1])
        with col_prev:
            st.caption(f"📎 {uploaded_file.name} ({round(uploaded_file.size / 1024, 1)} KB)")
        with col_upload:
            if st.button("☁️ Upload to Cloud", type="primary", use_container_width=True):
                from src.storage import upload_resume_to_storage
                from src.db.database import SessionLocal
                from src.resume.manager import ResumeManager
                with st.spinner(f"Uploading {uploaded_file.name} to Supabase Storage..."):
                    try:
                        file_bytes = uploaded_file.read()
                        storage_path = upload_resume_to_storage(file_bytes, uploaded_file.name)
                        db_session = SessionLocal()
                        rm = ResumeManager(db_session)
                        rm.ingest_resume_from_storage(uploaded_file.name, storage_path)
                        db_session.close()
                        st.success(f"✅ **{uploaded_file.name}** uploaded and registered for scoring!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

    st.divider()

    # ── Active Resumes Table ────────────────────────────────────────────────
    st.subheader("📋 Active Resumes")
    from src.db.database import SessionLocal
    from src.db.models import Resume as ResumeModel
    _db = SessionLocal()
    active_resumes = _db.query(ResumeModel).filter(ResumeModel.is_active == True).all()

    if not active_resumes:
        st.warning("No resumes uploaded yet. Upload a PDF or DOCX above to get started.")
    else:
        for r in active_resumes:
            c1, c2, c3 = st.columns([4, 3, 1])
            with c1:
                st.markdown(f"**📄 {r.filename}**")
            with c2:
                if str(r.filepath).startswith("supabase-storage://"):
                    st.caption("☁️ Supabase Storage")
                else:
                    st.caption(f"💾 Local: `{r.filepath}`")
            with c3:
                if st.button("🗑️", key=f"del_resume_{r.id}", help="Remove this resume"):
                    from src.storage import delete_resume_from_storage
                    if str(r.filepath).startswith("supabase-storage://"):
                        delete_resume_from_storage(r.filename)
                    r.is_active = False
                    _db.commit()
                    st.success(f"Removed {r.filename}")
                    st.rerun()
    _db.close()

    st.divider()
    st.caption("ℹ️ Resumes marked as active here will be scored against every scraped job in the pipeline.")

else:
    st.info("Select a page from the sidebar to continue.")
