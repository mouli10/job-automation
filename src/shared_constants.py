import os
from pathlib import Path
from dotenv import load_dotenv

# --- ULTIMATE BASE (ZERO IMPORTS ALLOWED) --- 🦾🏗️🏛️
# This file is the "Engine Room" that breaks the circular import cycle.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Database (Prioritize Cloud over Local)
# These MUST be primitive to avoid triggering any further imports.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/jobs.db").strip().strip('"\'')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Essential Folders
RESUMES_DIR = DATA_DIR / "resumes"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
CHROME_PROFILE_DIR = DATA_DIR / "chrome_profile"
ORIGINAL_RESUMES_DIR = RESUMES_DIR / "original"
OPTIMIZED_RESUMES_DIR = RESUMES_DIR / "optimized"

# Ensure directories exist (Low-level side effect)
for d in [DATA_DIR, RESUMES_DIR, ORIGINAL_RESUMES_DIR, OPTIMIZED_RESUMES_DIR, REPORTS_DIR, LOGS_DIR, CHROME_PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)
