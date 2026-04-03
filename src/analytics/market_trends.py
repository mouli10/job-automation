"""
Market Trends Analytics Engine
Scans jobs.db for the past N days and computes keyword demand frequencies.

Two data sources:
  1. Score.missing_keywords  → "skills the market wants that you're missing"
  2. Job.description (regex) → "raw tool mentions across all job descriptions"
"""
import re
import logging
from collections import Counter
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─── Master Keyword Dictionary ────────────────────────────────────────────────
# Curated list of Data / Analytics tools & skills to track across job postings
TRACKED_KEYWORDS = [
    # Cloud
    "AWS", "Azure", "GCP", "Google Cloud", "Databricks",
    # Data Engineering
    "Spark", "PySpark", "Kafka", "Airflow", "dbt", "ETL", "ELT",
    "Hadoop", "Flink", "Luigi", "Prefect", "Dagster",
    # Databases
    "Snowflake", "BigQuery", "Redshift", "PostgreSQL", "MySQL",
    "SQL Server", "Oracle", "MongoDB", "Cosmos DB", "DynamoDB",
    # BI & Visualization
    "Power BI", "Tableau", "Looker", "Qlik", "MicroStrategy", "Grafana",
    # Languages
    "Python", "SQL", "Scala", "Java", "R", "Bash", "Rust",
    # ML / AI
    "Machine Learning", "ML", "TensorFlow", "PyTorch", "Scikit-learn",
    "LLM", "LangChain", "NLP", "Deep Learning",
    # DevOps / Infra
    "Docker", "Kubernetes", "Terraform", "CI/CD", "GitHub Actions",
    # Analytics
    "Excel", "Pandas", "NumPy", "SciPy", "Statsmodels",
    "A/B Testing", "Statistics",
    # Methodologies
    "Agile", "Scrum", "Data Modeling", "Data Warehousing", "Data Lakehouse",
]


def get_keyword_frequencies(window_days: int = 7, top_n: int = 20) -> list[tuple[str, int]]:
    """
    Queries jobs.db for jobs scraped in the last `window_days` days.
    Returns a ranked list of (keyword, count) tuples.
    
    Strategy:
      - Mine Score.missing_keywords (high signal: exactly what you're missing)
      - Mine Job.description with regex (broad signal: raw market demand)
    Combine and deduplicate counts.
    """
    from src.db.database import SessionLocal
    from src.db.models import Job, Score

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=window_days)

        # Fetch jobs from the window
        jobs = db.query(Job).filter(Job.extracted_at >= cutoff).all()
        job_ids = {j.id for j in jobs}
        
        if not jobs:
            logger.warning(f"No jobs found in the last {window_days} days for trend analysis.")
            return []

        logger.info(f"📊 Analysing {len(jobs)} jobs from the last {window_days} days...")

        counter = Counter()

        # ── Pass 1: Missing keywords from scores (most intentional signal) ──
        scores = db.query(Score).filter(Score.job_id.in_(job_ids)).all()
        for s in scores:
            if not s.missing_keywords:
                continue
            for raw_kw in s.missing_keywords.split(","):
                kw = raw_kw.strip()
                # Match against master list (case-insensitive)
                for tracked in TRACKED_KEYWORDS:
                    if tracked.lower() == kw.lower():
                        counter[tracked] += 2  # Weight: missing keywords = double signal
                        break

        # ── Pass 2: Raw description mentions ──
        for job in jobs:
            desc = (job.description or "") + " " + (job.skills or "")
            desc_lower = desc.lower()
            for tracked in TRACKED_KEYWORDS:
                # Use word-boundary regex for multi-word terms too
                pattern = r'\b' + re.escape(tracked.lower()) + r'\b'
                if re.search(pattern, desc_lower):
                    counter[tracked] += 1

        # Sort by count descending, take top N
        ranked = counter.most_common(top_n)
        logger.info(f"✅ Top keyword: '{ranked[0][0]}' mentioned {ranked[0][1]} times" if ranked else "No keywords found.")
        return ranked

    finally:
        db.close()
