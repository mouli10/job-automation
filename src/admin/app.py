import streamlit as st
import sys
from pathlib import Path

# Add src to the path so we can import modules
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config_manager import ConfigManager

# Load current config
config = ConfigManager.load_config()

# --- CLOUD SYNC AT STARTUP ---
# If running in Streamlit Cloud, we want to start with the latest data
if "Streamlit" in str(st.session_state): # Simple check for cloud context
    try:
        from src.storage import sync_db_from_drive
        # Periodically sync if the file doesn't exist or is old
        if not Path(BASE_DIR / "data/jobs.db").exists():
            with st.spinner("☁️ Syncing initial database from Google Drive..."):
                sync_db_from_drive()
    except Exception as e:
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
        st.write("**Time Filter**")
        time_options = ["Last 24 hours", "Past Week", "Past Month", "Any Time"]
        curr_time = config["search"]["filters"].get("time_filter", "Last 24 hours")
        idx = time_options.index(curr_time) if curr_time in time_options else 0
        config["search"]["filters"]["time_filter"] = st.selectbox("Date Posted", time_options, index=idx)
        
    st.button("Save Changes", on_click=save_state, key="save_search")

elif page == "Limits & Scheduler":
    st.header("Limits & Scheduler")
    st.markdown("Set constraints for how many jobs the scraper extracts and evaluates.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Global Limits")
        config["limits"]["scrape_limit"] = st.number_input("Max Jobs to Scrape per Run", min_value=1, max_value=2000, value=config["limits"]["scrape_limit"], help="Maximum number of job cards to extract overall.")
        config["limits"]["email_limit"] = st.number_input("Top Jobs limit for Email Report", min_value=1, max_value=2000, value=config["limits"]["email_limit"], help="Only the Top N jobs evaluated will be returned in the Excel email sheet.")
        
    with col2:
        st.subheader("Scheduler")
        config["scheduler"]["enabled"] = st.toggle("Enable Daily Scheduler", value=config["scheduler"]["enabled"])
        
        times_text = st.text_area(
            "Scheduled Run Times (HH:MM, one per line)", 
            value="\n".join(config["scheduler"].get("run_times", ["07:00"])),
            help="Enter times in 24-hour format (e.g., 07:00, 19:30). The watchdog will trigger if the current time is within 15 mins of any of these."
        )
        # Parse and validate times
        valid_times = []
        for line in times_text.split("\n"):
            t = line.strip()
            if not t: continue
            if ":" in t and len(t) == 5:
                valid_times.append(t)
            else:
                st.error(f"Invalid time format: {t}. Use HH:MM.")
        
        config["scheduler"]["run_times"] = valid_times
        
        # Day of week filter
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        config["scheduler"]["run_days"] = st.multiselect(
            "Active Reporting Days", 
            options=all_days, 
            default=config["scheduler"].get("run_days", all_days),
            help="Uncheck days where you don't want reports (e.g. weekends)."
        )
        
        st.info(f"Active Schedules: {', '.join(valid_times)} on {len(config['scheduler']['run_days'])} days")

    st.button("Save Changes", on_click=save_state, key="save_limits")

elif page == "Blacklists & Priorities":
    st.header("Blacklists & Priorities")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Blacklists (Skip entire job)")
        companies_text = st.text_area("Blacklisted Companies", "\n".join(config["blacklist"]["companies"]), help="If seen, immediately block job before extracting API.")
        config["blacklist"]["companies"] = [c.strip() for c in companies_text.split("\n") if c.strip()]
        
        keywords_text = st.text_area("Blacklisted Keywords", "\n".join(config["blacklist"]["keywords"]), help="If title explicitly contains this keyword (e.g., 'Sr.', 'Manager').")
        config["blacklist"]["keywords"] = [k.strip() for k in keywords_text.split("\n") if k.strip()]

    with col2:
        st.subheader("Optional Filters")
        config["optional_filters"]["min_ats_score"] = st.slider("Absolute Minimum ATS Score allowed in Report", min_value=0.0, max_value=10.0, value=config["optional_filters"]["min_ats_score"], step=0.1)
        
        priority_companies = st.text_area("Priority Companies List", "\n".join(config["optional_filters"]["priority_companies"]), help="List companies you highly desire to boost their ranking.")
        config["optional_filters"]["priority_companies"] = [p.strip() for p in priority_companies.split("\n") if p.strip()]

        config["optional_filters"]["keyword_priority_boost"] = st.checkbox("Enable Keyword Priority Boost (+2.0 points)", value=config["optional_filters"]["keyword_priority_boost"])
        if "priority_keywords" not in config["optional_filters"]:
            config["optional_filters"]["priority_keywords"] = []
            
        priority_keywords = st.text_area("Priority Keywords List", "\n".join(config["optional_filters"]["priority_keywords"]), help="Title keywords that artificially boost rankings (e.g. 'Senior', 'Manager').")
        config["optional_filters"]["priority_keywords"] = [k.strip() for k in priority_keywords.split("\n") if k.strip()]

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
                st.write(f"Showing **{len(df)}** jobs.")
                
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    search_query = st.text_input("Search Jobs (Company, Title, or URL)", "")
                with col2:
                    min_score = st.slider("Min ATS Score", 0.0, 10.0, 0.0)
                
                if search_query:
                    df = df[df['company'].str.contains(search_query, case=False, na=False) | 
                            df['title'].str.contains(search_query, case=False, na=False) |
                            df['job_url'].str.contains(search_query, case=False, na=False)]
                
                df = df[df['ats_score'] >= min_score]
                
                # Display DataFrame
                st.dataframe(
                    df[['title', 'company', 'location', 'ats_score', 'date_scraped', 'job_url']],
                    use_container_width=True,
                    column_config={
                        "job_url": st.column_config.LinkColumn("Job Link")
                    }
                )
                
                st.write("---")
                st.subheader("Selection Details")
                selected_job = st.selectbox("Select a job to view full AI analysis", df['title'] + " @ " + df['company'])
                if selected_job:
                    job_row = df[df['title'] + " @ " + df['company'] == selected_job].iloc[0]
                    st.write(f"**ATS Analysis Score:** {job_row['ats_score']}/10")
                    st.write(f"**Why Good Fit:** {job_row['match_reason']}")
                    with st.expander("Show Full Job Description"):
                        st.write(job_row['description'])
                        
        except Exception as e:
            st.error(f"Error loading database: {e}")
elif page == "AI Document Optimization":
    st.header("AI Document Optimization")
    st.markdown("Safely inject customized keywords inline into your resumed `.docx` files without breaking original XML formatting limits.")
    
    if "optimization" not in config:
        config["optimization"] = {"enabled": False, "min_ats": 5.0, "max_ats": 8.0}
        
    config["optimization"]["enabled"] = st.toggle("Enable Strict Inline Optimization", value=config["optimization"]["enabled"])
    
    st.write("Only run the optimization prompt if the baseline ATS score falls within this range:")
    col1, col2 = st.columns(2)
    with col1:
        config["optimization"]["min_ats"] = st.number_input("Minimum ATS Score Threshold", min_value=0.0, max_value=10.0, value=config["optimization"]["min_ats"], step=0.5)
    with col2:
        config["optimization"]["max_ats"] = st.number_input("Maximum ATS Score Threshold", min_value=0.0, max_value=10.0, value=config["optimization"]["max_ats"], step=0.5)
        
    st.button("Save Changes", on_click=save_state, key="save_opt")

elif page == "Application Assistant":
    st.header("Application Assistant")
    st.markdown("Instantly generate short application summaries and optional tailored `.docx` cover letters based on the matched jobs.")
    
    if "application_assistant" not in config:
        config["application_assistant"] = {"enabled": False, "generate_cover_letter": False}
        
    config["application_assistant"]["enabled"] = st.toggle("Enable Application Assistant (Generates 'Why Good Fit' in Excel)", value=config["application_assistant"]["enabled"])
    
    st.write("---")
    st.write("### Cover Letter Generation")
    st.markdown("If enabled, builds a custom 3-5 paragraph targeted cover letter `.docx` deposited to your `data/cover_letters` directory.")
    config["application_assistant"]["generate_cover_letter"] = st.toggle("Generate Cover Letter File", value=config["application_assistant"]["generate_cover_letter"])
    
    st.button("Save Changes", on_click=save_state, key="save_app_assist")

elif page == "Prompt Management":
    st.header("Prompt Management")
    st.markdown("Directly tweak the intelligence core of the underlying model. Use variables `{job_desc}` and `{resume_text}`.")
    
    new_prompt = st.text_area("Active ATS Prompt Code", value=config["prompt"]["active_prompt"], height=400)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Save Custom Prompt", use_container_width=True):
            if "{job_desc}" not in new_prompt or "{resume_text}" not in new_prompt:
                st.error("Prompt MUST contain `{job_desc}` and `{resume_text}`!")
            else:
                # Add to history if changed
                if new_prompt != config["prompt"]["active_prompt"]:
                    config["prompt"]["prompt_history"].append(config["prompt"]["active_prompt"])
                    # Keep history max elements
                    if len(config["prompt"]["prompt_history"]) > 10:
                        config["prompt"]["prompt_history"].pop(0)
                        
                config["prompt"]["active_prompt"] = new_prompt
                save_state()
    
    with col2:
        if st.button("🔄 Reset to Default Template", use_container_width=True):
            config["prompt"]["active_prompt"] = config["prompt"]["default_prompt"]
            save_state()
            st.rerun()

    with col3:
        if len(config["prompt"]["prompt_history"]) > 0:
            if st.button("⏪ Undo (Revert to Previous)", use_container_width=True):
                config["prompt"]["active_prompt"] = config["prompt"]["prompt_history"].pop()
                save_state()
                st.rerun()

elif page == "Weekly Market Trends":
    st.header("📊 Weekly Market Trends")
    st.markdown(
        "Every **Sunday morning**, the pipeline will mine the jobs it collected that week "
        "and email you an interactive Plotly chart showing the most in-demand tools and keywords "
        "in your target market."
    )

    if "weekly_trends" not in config:
        config["weekly_trends"] = {"enabled": True, "analysis_window_days": 7, "top_n_keywords": 20}

    config["weekly_trends"]["enabled"] = st.toggle(
        "Enable Weekly Trends Email (fires every Sunday)",
        value=config["weekly_trends"]["enabled"]
    )

    st.write("---")
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
            index=[10, 15, 20, 25].index(
                config["weekly_trends"].get("top_n_keywords", 20)
            )
        )

    st.write("---")
    st.subheader("🧪 Run Now (Test Mode)")
    st.caption("Generate and email the trends chart immediately without waiting for Sunday.")
    if st.button("📤 Generate & Send Trends Report Now", use_container_width=True):
        with st.spinner("Analysing jobs database and generating chart..."):
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
                from src.analytics.market_trends import get_keyword_frequencies
                from src.analytics.chart_generator import generate_trends_chart
                from src.reporting.email_sender import send_weekly_trends_report

                win = config["weekly_trends"]["analysis_window_days"]
                top_n = config["weekly_trends"]["top_n_keywords"]
                ranked = get_keyword_frequencies(window_days=win, top_n=top_n)
                if not ranked:
                    st.warning("No job data found for the selected window. Run the pipeline first to collect jobs.")
                else:
                    chart_path = generate_trends_chart(ranked, window_days=win)
                    if chart_path:
                        send_weekly_trends_report(chart_path, ranked, window_days=win)
                        st.success(f"✅ Trends chart generated and emailed! Top keyword: **{ranked[0][0]}** ({ranked[0][1]} mentions)")
                    else:
                        st.error("Chart generation failed. Is Plotly installed?")
            except Exception as e:
                st.error(f"Error: {e}")

    st.button("Save Settings", on_click=save_state, key="save_trends")

elif page == "Manual Run Control":
    st.header("🚀 Manual Control & Sync")
    st.markdown("Trigger cloud synchronization or start the pipeline manually.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🔄 Database Sync")
        st.write("Force the dashboard to pull the latest results from Google Drive.")
        if st.button("Download from Drive Now", use_container_width=True):
            try:
                from src.storage import sync_db_from_drive
                with st.spinner("Syncing..."):
                    sync_db_from_drive()
                st.success("✅ Database updated from Drive!")
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed: {e}")
    
    with col_b:
        st.subheader("☁️ Database Backup")
        st.write("Force an immediate upload of the current local state back to Drive.")
        if st.button("Upload to Drive Now", use_container_width=True):
            try:
                from src.storage import sync_db_to_drive
                with st.spinner("Syncing..."):
                    sync_db_to_drive()
                st.success("✅ Local database backed up to Drive!")
            except Exception as e:
                st.error(f"Backup failed: {e}")

    st.write("---")
    st.subheader("🔥 Manual Pipeline Trigger")
    st.markdown("Run the full job search pipeline **instantly**, bypassing all schedules.")
    
    st.warning("⚠️ Running the pipeline manually will launch a Chrome browser and consume Gemini API credits.")
    
    col1, col2 = st.columns(2)
    with col1:
        temp_limit = st.number_input("Jobs to Scrape for this run", min_value=1, max_value=2000, value=config["limits"]["scrape_limit"])
        
    if st.button("🔥 Start Pipeline Now", type="primary", use_container_width=True):
        # Temporarily override config for this runtime
        original_limit = config["limits"]["scrape_limit"]
        config["limits"]["scrape_limit"] = temp_limit
        
        try:
            with st.status("Pipeline in Progress...", expanded=True) as status:
                st.write("Initializing Scraper...")
                from src.main import run_pipeline
                run_pipeline(config_override=config)
                status.update(label="✅ Pipeline Completed!", state="complete", expanded=False)
            st.success("Report generated and emailed successfully!")
        except Exception as e:
            st.error(f"Manual run failed: {e}")
        finally:
            config["limits"]["scrape_limit"] = original_limit
