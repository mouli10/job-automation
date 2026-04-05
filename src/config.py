import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- BLOCK 1: PRIMITIVES & PATHS (NO IMPORTS ALLOWED) --- 🦾🏗️
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Database (Prioritize Cloud over Local)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/jobs.db").strip().strip('"\'')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# API Keys & Secrets
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().strip('"\'')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"\'')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip().strip('"\'')
GMAIL_USER = os.getenv("GMAIL_USER", "").strip().strip('"\'')
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "").strip().strip('"\'')
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().strip('"\'')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip().strip('"\'')
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1X4Q4P3we0SeZemb48zuoHkELbxIu6jPS").strip().strip('"\'')

# --- BLOCK 2: DIRECTORIES & HANDOFFS --- 📂🏗️
RESUMES_DIR = DATA_DIR / "resumes"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
CHROME_PROFILE_DIR = DATA_DIR / "chrome_profile"
ORIGINAL_RESUMES_DIR = RESUMES_DIR / "original"
OPTIMIZED_RESUMES_DIR = RESUMES_DIR / "optimized"
GDRIVE_CREDENTIALS_PATH = str(BASE_DIR / "credentials.json")

for d in [DATA_DIR, RESUMES_DIR, ORIGINAL_RESUMES_DIR, OPTIMIZED_RESUMES_DIR, REPORTS_DIR, LOGS_DIR, CHROME_PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- BLOCK 3: DYNAMIC CONFIG (AFTER PATHS ARE READY) --- 🧠💾
# This is where we break the circular import by importing ConfigManager LATE
from src.config_manager import ConfigManager
admin_config = ConfigManager.load_config()

# Derived Settings
SEARCH_ROLES = admin_config["search"]["roles"]
SEARCH_LOCATIONS = admin_config["search"]["locations"]
SCRAPER_MAX_JOBS_DAY = admin_config["limits"]["scrape_limit"]
MAX_REPORT_JOBS = admin_config["limits"]["email_limit"]
DB_RETENTION_DAYS = int(os.getenv("DB_RETENTION_DAYS", 60))
SCHEDULE_TIME = admin_config["scheduler"].get("run_times", ["07:00"])[0]
SCRAPER_ENGINE = os.getenv("SCRAPER_ENGINE", "linkedin_cookie").strip().strip('"\'')
LINKEDIN_LI_AT_COOKIE = os.getenv("LINKEDIN_LI_AT_COOKIE", "").strip().strip('"\'')

# Scraping Delays (Constants)
SCRAPER_MIN_DELAY = int(os.getenv("SCRAPER_MIN_DELAY", 3))
SCRAPER_MAX_DELAY = int(os.getenv("SCRAPER_MAX_DELAY", 8))
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", 5))
