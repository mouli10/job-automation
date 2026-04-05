import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to the path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from src.db.models import Base, Job, Resume, Score, Report, AppSetting
from src.config import DATABASE_URL, admin_config

# Force basic logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def migrate():
    # ── 1. THE SETUP (THE CLOUD SCAN) ───────────────────────────────────────
    if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
        logger.error("❌ No Supabase DATABASE_URL found in your secrets/env!")
        logger.error("Please add the connection string to your secrets before running this.")
        return

    logger.info("🛰️ Initializing Cloud Database Schema...")
    cloud_engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=cloud_engine)
    logger.info("✅ Schema synchronized with Supabase.")

    # ── 2. THE LOCAL SOURCE ──────────────────────────────────────────────────
    local_db_path = BASE_DIR / "data" / "jobs.db"
    if not local_db_path.exists():
        logger.warning(f"⚠️ No local database found at {local_db_path}. Transitioning settings only.")
        local_engine = None
    else:
        local_db_url = f"sqlite:///{local_db_path}"
        local_engine = create_engine(local_db_url)

    # ── 3. DATA TELEPORTATION ────────────────────────────────────────────────
    CloudSession = sessionmaker(bind=cloud_engine)
    cloud_db = CloudSession()

    try:
        # STEP A: SETTINGS (Fix the Amnesia!) 🧠💾
        from src.config_manager import ConfigManager
        logger.info("📤 Migrating Dashboard Settings (Engine, Tokens, etc)...")
        ConfigManager.save_config(admin_config) # This now writes to Supabase by default!
        logger.info("✅ Settings permanently locked into Supabase.")

        if local_engine:
            LocalSession = sessionmaker(bind=local_engine)
            local_db = LocalSession()

            # STEP B: RESUMES
            logger.info("📤 Migrating Resumes...")
            resumes = local_db.query(Resume).all()
            for r in resumes:
                cloud_db.merge(r) # merge prevents duplicates if run multiple times
            logger.info(f"✅ {len(resumes)} Resumes transferred.")

            # STEP C: JOBS
            logger.info("📤 Migrating Jobs (This may take a moment)...")
            jobs = local_db.query(Job).all()
            for j in jobs:
                cloud_db.merge(j)
            logger.info(f"✅ {len(jobs)} Jobs transferred.")

            # STEP D: SCORES
            logger.info("📤 Migrating AI Scores...")
            scores = local_db.query(Score).all()
            for s in scores:
                cloud_db.merge(s)
            logger.info(f"✅ {len(scores)} AI Scores transferred.")

            local_db.close()

        cloud_db.commit()
        logger.info("\n" + "="*50)
        logger.info("🚀 MIGRATION SUCCESSFUL!")
        logger.info("Your robot now lives in the cloud (Supabase).")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        cloud_db.rollback()
    finally:
        cloud_db.close()

if __name__ == "__main__":
    migrate()
