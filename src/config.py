import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Cloud Secret Reconstruction ─────────────────────────────────────────────
# In GitHub Actions, we store JSON files as base64 or raw strings in Secrets.
# We must recreate the physical files for Google Auth to work.
import json
for env_key, filename in [("GDRIVE_CREDENTIALS_JSON", "credentials.json"), 
                          ("GDRIVE_TOKEN_JSON", "token.json")]:
    val = os.getenv(env_key)
    if val:
        try:
            # Try to parse as JSON to ensure it's valid before writing
            data = json.loads(val)
            with open(Path(__file__).resolve().parent.parent / filename, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Failed to reconstruct {filename} from env: {e}")

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/jobs.db")
DB_RETENTION_DAYS = int(os.getenv("DB_RETENTION_DAYS", 60))

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().strip('"\'')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"\'')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip().strip('"\'')

# Email
GMAIL_USER = os.getenv("GMAIL_USER", "").strip().strip('"\'')
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "").strip().strip('"\'')


from src.config_manager import ConfigManager

# Load dynamic JSON config
admin_config = ConfigManager.load_config()

# Scraping
SEARCH_ROLES = admin_config["search"]["roles"]
SEARCH_LOCATIONS = admin_config["search"]["locations"]

SCRAPER_ENGINE = os.getenv("SCRAPER_ENGINE", "linkedin_cookie").strip().strip('"\'')
LINKEDIN_LI_AT_COOKIE = os.getenv("LINKEDIN_LI_AT_COOKIE", "").strip().strip('"\'')
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
# Using the confirmed actual ID as fallback in case the GitHub secret is mangled
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1RjH6A-y8c7_hU8eF5c9vXmY9_sDtfQxw").strip().strip('"\'')
if not GDRIVE_FOLDER_ID or GDRIVE_FOLDER_ID == "1RjH6A-y8c7_hU8eF5c9vXmY9_sDtfQxw":
    GDRIVE_FOLDER_ID = "1X4Q4P3we0SeZemb48zuoHkELbxIu6jPS"

# Create all required directories
for d in [DATA_DIR, RESUMES_DIR, ORIGINAL_RESUMES_DIR, OPTIMIZED_RESUMES_DIR, REPORTS_DIR, LOGS_DIR, CHROME_PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)
