import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "data" / "config.json"

DEFAULT_ATS_PROMPT = """You are a strict and highly accurate ATS (Applicant Tracking System) expert.

Carefully read the Job Description and Resume below. Evaluate how well the resume matches the job.

Your scoring criteria:
- Keyword match (skills, tools, technologies mentioned in JD vs resume): 40%
- Experience level and relevance: 30%  
- Education and certifications: 15%
- Achievements and impact quantification: 15%

Be strict and realistic. A perfect match (10.0) means the resume is virtually tailored for this role.

Job Description:
{job_desc}

Resume:
{resume_text}

Return ONLY a valid JSON object with NO markdown, NO extra text:
{{"ats_score": <float 0.0 to 10.0>, "missing_keywords": ["keyword1", "keyword2"], "review": "A brief 2-3 sentence review of the resume highlighting strengths and gaps based on the criteria."}}"""


DEFAULT_CONFIG = {
    "search": {
        "roles": [
            "Data Analyst",
            "Analytics Engineer",
            "Data Engineer",
            "Product Analyst",
            "BI Engineer"
        ],
        "locations": ["United States"],
        "filters": {
            "remote": False,
            "hybrid": False,
            "onsite": False,
            "entry_level": False,
            "associate": False,
            "mid_senior": False,
            "time_filter": "Last 24 hours"  # Options: "Last 24 hours", "Past Week", "Past Month", "Any Time"
        }
    },
    "limits": {
        "scrape_limit": 200,
        "email_limit": 120
    },
    "scheduler": {
        "enabled": False,
        "run_times": ["07:00"],
        "run_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    },
    "blacklist": {
        "companies": ["Revature", "Tata Consultancy", "CyberCoders", "SynergisticIT"],
        "keywords": [],
        "roles": []
    },
    "optimization": {
        "enabled": False,
        "min_ats": 5.0,
        "max_ats": 8.0
    },
    "application_assistant": {
        "enabled": False,
        "generate_cover_letter": False
    },
    "weekly_trends": {
        "enabled": True,
        "analysis_window_days": 7,
        "top_n_keywords": 20
    },
    "optional_filters": {
        "min_ats_score": 0.0,
        "priority_companies": [],
        "keyword_priority_boost": False
    },
    "prompt": {
        "active_prompt": DEFAULT_ATS_PROMPT,
        "default_prompt": DEFAULT_ATS_PROMPT,
        "prompt_history": []
    }
}

class ConfigManager:
    @staticmethod
    def load_config() -> dict:
        """Loads configuration from JSON. If it doesn't exist or is invalid, creates and returns defaults."""
        if not CONFIG_FILE.exists():
            # Create data dir if missing
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            ConfigManager.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
            
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return ConfigManager._merge_with_defaults(data)
        except Exception as e:
            logger.error(f"Failed to load config.json (returning defaults): {e}")
            return DEFAULT_CONFIG

    @staticmethod
    def save_config(config_data: dict):
        """Saves configuration dict back to JSON file safely."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config.json: {e}")

    @staticmethod
    def _merge_with_defaults(loaded: dict) -> dict:
        """Recursively merges loaded config with defaults to ensure missing keys are populated."""
        import copy
        merged = copy.deepcopy(DEFAULT_CONFIG)

        # ── Migration: run_time (str) -> run_times (list) ─────────────────────
        sched = loaded.get("scheduler", {})
        if "run_time" in sched and "run_times" not in sched:
            sched["run_times"] = [sched.pop("run_time")]

        def recurse(d1, d2):
            for k, v in d2.items():
                if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                    recurse(d1[k], v)
                else:
                    d1[k] = v

        recurse(merged, loaded)
        return merged
