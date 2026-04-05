import os
from pathlib import Path
from dotenv import load_dotenv
import urllib.parse

# --- ULTIMATE BASE (ZERO IMPORTS ALLOWED) --- 🦾🏗️🏛️
# This file is the "Engine Room" that breaks the circular import cycle.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Database (Prioritize Cloud over Local)
# These MUST be primitive to avoid triggering any further imports.
RAW_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/jobs.db").strip().strip('"\'')

# --- PASSWORD ARMOR --- 🦾🛡️
# We must URL-encode the password part of the string if it contains special chars like '@'
if RAW_DATABASE_URL.startswith("postgres"):
    try:
        # Standard format: postgresql://user:password@host:port/dbname
        if RAW_DATABASE_URL.startswith("postgres://"):
            RAW_DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # Split into prefix and the rest
        prefix = "postgresql://"
        rest = RAW_DATABASE_URL[len(prefix):]
        
        # Now find the LAST '@' which separates user:pass from host:port/db
        at_split = rest.rsplit("@", 1)
        if len(at_split) == 2:
            auth_part = at_split[0]
            host_part = at_split[1]
            
            # Split auth into user and pass
            user_pass = auth_part.split(":", 1)
            if len(user_pass) == 2:
                user = user_pass[0]
                password = user_pass[1]
                # SHIELD THE PASSWORD 🦾🛡️
                safe_password = urllib.parse.quote_plus(password)
                DATABASE_URL = f"{prefix}{user}:{safe_password}@{host_part}"
            else:
                DATABASE_URL = RAW_DATABASE_URL
        else:
            DATABASE_URL = RAW_DATABASE_URL
    except Exception:
        DATABASE_URL = RAW_DATABASE_URL
else:
    DATABASE_URL = RAW_DATABASE_URL

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
