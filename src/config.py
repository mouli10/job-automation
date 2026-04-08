import os
import json
import logging
from pathlib import Path
from src.shared_constants import BASE_DIR, DATA_DIR, DATABASE_URL, RESUMES_DIR, REPORTS_DIR, LOGS_DIR, CHROME_PROFILE_DIR, ORIGINAL_RESUMES_DIR, OPTIMIZED_RESUMES_DIR

# --- BLOCK 1: CORE API KEYS --- 🦾🏗️
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().strip('"\'')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"\'')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip().strip('"\'')
GMAIL_USER = os.getenv("GMAIL_USER", "").strip().strip('"\'')
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "").strip().strip('"\'')
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().strip('"\'')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip().strip('"\'')
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1X4Q4P3we0SeZemb48zuoHkELbxIu6jPS").strip().strip('"\'')
GDRIVE_CREDENTIALS_PATH = str(BASE_DIR / "credentials.json")

# --- BLOCK 2: DYNAMIC CONFIG --- 🧠💾
# We can now safely import ConfigManager because database.py no longer looks at src.config
from src.config_manager import ConfigManager
admin_config = ConfigManager.load_config()

# Derived Settings
SEARCH_ROLES = admin_config["search"]["roles"]
SEARCH_LOCATIONS = admin_config["search"]["locations"]
SCRAPER_MAX_JOBS_DAY = admin_config["limits"]["scrape_limit"]
MAX_REPORT_JOBS = admin_config["limits"]["email_limit"]
DB_RETENTION_DAYS = int(admin_config.get("limits", {}).get("db_retention_days", os.getenv("DB_RETENTION_DAYS", 60)))
SCHEDULE_TIME = admin_config["scheduler"].get("run_times", ["07:00"])[0]
SCRAPER_ENGINE = os.getenv("SCRAPER_ENGINE", "linkedin_cookie").strip().strip('"\'')
LINKEDIN_LI_AT_COOKIE = os.getenv("LINKEDIN_LI_AT_COOKIE", "").strip().strip('"\'')

# Scraping Safety Delays — read from admin portal first, .env as fallback
SCRAPER_MIN_DELAY = int(admin_config.get("limits", {}).get("scraper_min_delay", os.getenv("SCRAPER_MIN_DELAY", 3)))
SCRAPER_MAX_DELAY = int(admin_config.get("limits", {}).get("scraper_max_delay", os.getenv("SCRAPER_MAX_DELAY", 8)))
SCRAPER_MAX_PAGES = int(admin_config.get("limits", {}).get("scraper_max_pages", os.getenv("SCRAPER_MAX_PAGES", 5)))
