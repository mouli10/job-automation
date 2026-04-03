import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/jobs.db")
DB_RETENTION_DAYS = int(os.getenv("DB_RETENTION_DAYS", 60))

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Email
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")

from src.config_manager import ConfigManager

# Load dynamic JSON config
admin_config = ConfigManager.load_config()

# Scraping
SEARCH_ROLES = admin_config["search"]["roles"]
SEARCH_LOCATIONS = admin_config["search"]["locations"]

SCRAPER_ENGINE = os.getenv("SCRAPER_ENGINE", "linkedin_cookie")
LINKEDIN_LI_AT_COOKIE = os.getenv("LINKEDIN_LI_AT_COOKIE", "")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# Scraping Limits
SCRAPER_MIN_DELAY = int(os.getenv("SCRAPER_MIN_DELAY", 3))
SCRAPER_MAX_DELAY = int(os.getenv("SCRAPER_MAX_DELAY", 8))
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", 5))

SCRAPER_MAX_JOBS_DAY = admin_config["limits"]["scrape_limit"]
MAX_REPORT_JOBS     = admin_config["limits"]["email_limit"]

# Handle run_time vs run_times migration
SCHEDULE_TIME = admin_config["scheduler"].get("run_times", ["07:00"])[0]

# Directories
DATA_DIR = BASE_DIR / "data"
RESUMES_DIR = DATA_DIR / "resumes"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
CHROME_PROFILE_DIR = DATA_DIR / "chrome_profile"
ORIGINAL_RESUMES_DIR = RESUMES_DIR / "original"
OPTIMIZED_RESUMES_DIR = RESUMES_DIR / "optimized"

# Google Drive Constants
GDRIVE_CREDENTIALS_PATH = str(BASE_DIR / "credentials.json")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1RjH6A-y8c7_hU8eF5c9vXmY9_sDtfQxw")  # Fallback dummy ID

# Create all required directories
for d in [DATA_DIR, RESUMES_DIR, ORIGINAL_RESUMES_DIR, OPTIMIZED_RESUMES_DIR, REPORTS_DIR, LOGS_DIR, CHROME_PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)
