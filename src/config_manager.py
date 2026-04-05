import json
import logging
from pathlib import Path
from src.db.database import SessionLocal
from src.db.models import AppSetting

logger = logging.getLogger(__name__)

# Path to the old config.json file (still used as a default/fallback)
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "data" / "config.json"

class ConfigManager:
    @staticmethod
    def load_config() -> dict:
        """
        Loads the configuration. 
        Always tries to pull from the 'Ironclad' Supabase Database first.
        Falls back to local config.json if Supabase is unavailable.
        """
        # --- 1. START WITH LOCAL DEFAULTS ---
        config = {}
        if DEFAULT_CONFIG_PATH.exists():
            try:
                with open(DEFAULT_CONFIG_PATH, "r") as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load local config.json: {e}")

        # --- 2. OVERWRITE WITH CLOUD PERMANENCE 🛰️ ---
        try:
            db = SessionLocal()
            try:
                # We store individual settings as rows for maximum flexibility
                settings = db.query(AppSetting).all()
                if settings:
                    for s in settings:
                        try:
                            val = json.loads(s.value)
                            # Deep merge or key replacement
                            if isinstance(val, dict) and s.key in config and isinstance(config[s.key], dict):
                                config[s.key].update(val)
                            else:
                                config[s.key] = val
                        except Exception:
                            config[s.key] = s.value # Fallback for non-JSON strings
                
                # Check for specific persistence fixes (Engine, Token, etc)
                # These ensure that dashboard choices don't reset
            except Exception as db_e:
                logger.warning(f"Cloud settings fetch skipped/failed (using disk): {db_e}")
            finally:
                db.close()
        except Exception as conn_e:
             logger.warning(f"Database connection failed for config load: {conn_e}")

        return config

    @staticmethod
    def save_config(config: dict):
        """
        Saves the configuration to BOTH Supabase (Main Home) and config.json (Backup).
        """
        # --- 1. SAVE TO DISK (BACKUP) ---
        try:
            DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEFAULT_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save local backup config.json: {e}")

        # --- 2. SAVE TO CLOUD (IRONCLAD) 🛰️ ---
        try:
            db = SessionLocal()
            try:
                for key, value in config.items():
                    # Upsert each top-level key into the database 🦾
                    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
                    json_val = json.dumps(value)
                    
                    if setting:
                        setting.value = json_val
                    else:
                        db.add(AppSetting(key=key, value=json_val))
                
                db.commit()
                logger.info("✅ Ironclad Sync: All settings backed up to Supabase Cloud.")
            except Exception as db_e:
                db.rollback()
                logger.error(f"Failed to save settings to Supabase: {db_e}")
            finally:
                db.close()
        except Exception as conn_e:
             logger.warning(f"Database connection failed for config save: {conn_e}")
