import argparse
import logging
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db.database import Base, engine, SessionLocal
from src.db.models import Job, Resume, Score
from src.config import (
    SEARCH_ROLES, SEARCH_LOCATIONS, SCHEDULE_TIME, LOGS_DIR,
    MAX_REPORT_JOBS, DB_RETENTION_DAYS
)
from src.scraper.factory import get_scraper
from src.resume.manager import ResumeManager
from src.resume.parser import extract_text_from_file
from src.matching.ats_scorer import calculate_ats_score
from src.reporting.excel_gen import generate_daily_report
from src.reporting.email_sender import send_daily_report, send_email

# --- Logging Setup ---
log_file_path = LOGS_DIR / f"automation_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ── Safety Lock ──────────────────────────────────────────────────────────────
from src.config import DATA_DIR
LOCK_FILE = DATA_DIR / "pipeline.lock"

def _is_pipeline_running() -> bool:
    if not LOCK_FILE.exists():
        return False
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
        import psutil
        return psutil.pid_exists(pid)
    except:
        return False

def _acquire_lock():
    import os
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")

def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized.")


def purge_old_jobs(db):
    """Deletes jobs older than DB_RETENTION_DAYS, sends warning email 7 days before."""
    cutoff = datetime.utcnow() - timedelta(days=DB_RETENTION_DAYS)
    warning_cutoff = datetime.utcnow() - timedelta(days=DB_RETENTION_DAYS - 7)

    expiring_soon = db.query(Job).filter(
        Job.extracted_at <= warning_cutoff,
        Job.extracted_at > cutoff
    ).count()

    if expiring_soon > 0:
        logger.warning(f"⚠️  {expiring_soon} jobs expiring in 7 days.")
        try:
            send_email(
                subject=f"⚠️ Job Database Purge Warning — {expiring_soon} records expiring in 7 days",
                body=(
                    f"This is an automated warning from your Job Automation System.\n\n"
                    f"{expiring_soon} job records are approaching the {DB_RETENTION_DAYS}-day retention limit "
                    f"and will be permanently deleted in approximately 7 days.\n\n"
                    f"Export any records you need to keep before they are deleted.\n\n"
                    f"— AI Job Pipeline 🤖"
                )
            )
        except Exception as e:
            logger.error(f"Failed to send purge warning: {e}")

    expired = db.query(Job).filter(Job.extracted_at <= cutoff).all()
    if expired:
        expired_ids = [j.id for j in expired]
        db.query(Score).filter(Score.job_id.in_(expired_ids)).delete(synchronize_session=False)
        db.query(Job).filter(Job.id.in_(expired_ids)).delete(synchronize_session=False)
        db.commit()
        logger.info(f"🗑️  Purged {len(expired)} records older than {DB_RETENTION_DAYS} days.")


def run_pipeline(config_override: dict = None):
    # Determine the configuration to use for this run
    if config_override:
        admin_config = config_override
        logger.info("ℹ️ Using configuration override from caller.")
    else:
        from src.config_manager import ConfigManager
        admin_config = ConfigManager.load_config()
        logger.info("ℹ️ Loading configuration from disk.")

    roles = admin_config["search"]["roles"]
    locations = admin_config["search"]["locations"]
    scrape_limit = admin_config["limits"]["scrape_limit"]

    if _is_pipeline_running():
        msg = "🔒 Pipeline is already running in another process. Aborting to prevent collision."
        logger.warning(msg)
        raise RuntimeError(msg)

    _acquire_lock()
    try:
        logger.info("=" * 60)
        logger.info(f"=== Starting Daily Pipeline | {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        logger.info(f"=== {len(roles)} roles | Location: {locations} | Limit: {scrape_limit} ===")
        logger.info("=" * 60)
        init_db()
        db = SessionLocal()

        # STEP 0: Purge old data
        purge_old_jobs(db)

        # STEP 1: Scrape jobs
        scraper = get_scraper()
        jobs_data = scraper.scrape(roles, locations, config=admin_config)

        import gc
        gc.collect() # Trigger immediate cleanup

        new_jobs = []
        for data in jobs_data:
            title = (data.get("title") or "").strip()
            company = (data.get("company") or "").strip()
            link = data.get("link")

            if not title or not company:
                continue

            if link:
                exists = db.query(Job).filter(Job.link == link).first()
            else:
                exists = db.query(Job).filter(
                    Job.title == title, Job.company == company
                ).first()

            if not exists:
                job = Job(**data)
                db.add(job)
                new_jobs.append(job)

        db.commit()
        for j in new_jobs:
            db.refresh(j)
        logger.info(f"\n📥 Scraped and saved {len(new_jobs)} new jobs.\n")
        
        import gc
        gc.collect() # Trigger immediate cleanup

        if not new_jobs:
            logger.info("No new jobs today. Exiting pipeline.")
            return

        # STEP 2: Load all active resumes
        resume_manager = ResumeManager(db)
        
        # Sync immediately with Google Drive Original folder
        from src.storage import sync_original_resumes
        sync_original_resumes(resume_manager)
        
        resumes = resume_manager.get_all_active_resumes()

        if not resumes:
            logger.warning("No active resumes found. Add .docx files to data/resumes/original/")
            return

        logger.info(f"📄 Loaded {len(resumes)} active resumes: {[r.filename for r in resumes]}")

        # Parse resume text for all resumes
        resume_texts = {}
        for r in resumes:
            try:
                text = extract_text_from_file(r.filepath)
                if text and text.strip():
                    resume_texts[r.id] = text
                    logger.info(f"  ✅ Parsed resume: {r.filename} ({len(text)} chars)")
                else:
                    logger.warning(f"  ⚠️  Empty text from resume: {r.filename}")
            except Exception as e:
                logger.error(f"  ❌ Failed to parse {r.filepath}: {e}")

        if not resume_texts:
            logger.error("Could not parse any resume. Check resume files.")
            return

        # STEP 3: Score ALL resumes against EVERY job
        logger.info(f"\n🤖 Scoring {len(new_jobs)} jobs against {len(resume_texts)} resumes using Gemini 2.5 Flash...\n")

        # scored_jobs: list of (best_ats_score, job, best_resume, best_result)
        scored_jobs = []

        for job_idx, job in enumerate(new_jobs, 1):
            logger.info(f"[{job_idx}/{len(new_jobs)}] Scoring: {job.title} @ {job.company}")

            best_score = -1.0
            best_resume = None
            best_result = None
            score_records = []

            for r in resumes:
                if r.id not in resume_texts:
                    continue

                result = calculate_ats_score(job, resume_texts[r.id])
                ats = result.get("ats_score", 0.0)

                score_rec = Score(
                    job_id=job.id,
                    resume_id=r.id,
                    ats_score=ats,
                    match_level=result.get("match_level", "Low"),
                    missing_keywords=",".join(result.get("missing_keywords", [])),
                    review=result.get("review", "No review provided."),
                    resume_type="Original"
                )
                db.add(score_rec)
                score_records.append((score_rec, r, result, ats))

                if ats > best_score:
                    best_score = ats
                    best_resume = r
                    best_result = result

            db.commit()
            # Refresh score records to get IDs
            for rec, _, _, _ in score_records:
                db.refresh(rec)

            if best_resume:
                scored_jobs.append((best_score, job, best_resume, best_result))

        logger.info(f"\n✅ Scoring complete. {len(scored_jobs)} jobs scored.\n")

        # STEP 4: Sort by ATS score, take top N
        scored_jobs.sort(key=lambda x: x[0], reverse=True)
        top_jobs = scored_jobs[:MAX_REPORT_JOBS]
        logger.info(f"🏆 Top {len(top_jobs)} jobs selected (sorted by ATS score).\n")




        # STEP 5: Inline AI Resume Optimization
        from src.config import admin_config
        opt_config = admin_config.get("optimization", {})
        
        if opt_config.get("enabled", False):
            from src.matching.optimizer import ResumeOptimizer
            optimizer = ResumeOptimizer()
            logger.info("\n🤖 Running Strict Inline Resume Optimization...")
            
            for (best_score, job, best_resume, best_result) in top_jobs:
                if opt_config.get("min_ats", 5.0) <= (best_score or 0.0) <= opt_config.get("max_ats", 8.0):
                    out_path = optimizer.optimize(best_resume.filepath, job.id, job.title, job.description)
                    if out_path:
                        # Repurpose gdrive_link column to store the optimized local path securely
                        score_rec = db.query(Score).filter(Score.job_id == job.id, Score.resume_id == best_resume.id).first()
                        if score_rec:
                            from pathlib import Path
                            from src.storage import upload_resume
                            final_link = upload_resume(out_path, Path(out_path).name)
                            score_rec.gdrive_link = final_link
                            db.commit()

        # STEP 6: Application Assistant
        app_assist_data = {}
        app_config = admin_config.get("application_assistant", {})
        if app_config.get("enabled", False):
            from src.matching.application_assistant import ApplicationAssistant
            assistant = ApplicationAssistant()
            logger.info("\n🤖 Running Application Assistant...")
            
            for (best_score, job, best_resume, best_result) in top_jobs:
                target_path = best_resume.filepath
                # If optimized file was generated, prioritize it logically
                import os
                score_rec = db.query(Score).filter(Score.job_id == job.id, Score.resume_id == best_resume.id).first()
                if score_rec and score_rec.gdrive_link:
                    from pathlib import Path
                    from src.config import DATA_DIR
                    expected_opt_name = f"{Path(best_resume.filepath).stem}_opt_{job.id}.docx"
                    opt_path = DATA_DIR / "resumes" / "optimized" / expected_opt_name
                    if opt_path.exists():
                        target_path = str(opt_path)
                        
                opt_config = admin_config.get("optimization", {})
                min_threshold = opt_config.get("min_ats", 5.0)
                res = assistant.process(job, target_path, best_score, min_threshold)
                app_assist_data[job.id] = res

        # STEP 7: Generate report + send email
        logger.info("\n📊 Generating Excel report...")
        report_path = generate_daily_report(app_assist_data=app_assist_data)

        logger.info("📧 Sending email report...")
        send_daily_report(report_path)

        # STEP 8: Weekly Market Trends (Sundays only)
        from datetime import datetime as _dt
        if _dt.utcnow().weekday() == 6:  # 6 = Sunday
            trends_config = admin_config.get("weekly_trends", {})
            if trends_config.get("enabled", True):
                logger.info("\n📊 Sunday detected — running Weekly Market Trends analysis...")
                try:
                    from src.analytics.market_trends import get_keyword_frequencies
                    from src.analytics.chart_generator import generate_trends_chart
                    from src.reporting.email_sender import send_weekly_trends_report

                    win  = trends_config.get("analysis_window_days", 7)
                    topn = trends_config.get("top_n_keywords", 20)
                    ranked = get_keyword_frequencies(window_days=win, top_n=topn)
                    if ranked:
                        chart_path = generate_trends_chart(ranked, window_days=win)
                        if chart_path:
                            send_weekly_trends_report(chart_path, ranked, window_days=win)
                except Exception as e:
                    logger.error(f"Weekly Trends step failed (non-fatal): {e}")

        logger.info("=" * 60)
        logger.info("=== ✅ Pipeline Completed Successfully ===")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        if 'db' in locals(): db.rollback()
    finally:
        if 'db' in locals(): db.close()
        _release_lock()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Job Pipeline")
    parser.add_argument("--run-now", action="store_true", help="Run pipeline immediately")
    args = parser.parse_args()

    if args.run_now:
        run_pipeline()
    else:
        logger.info(f"Starting Scheduler — daily run at {SCHEDULE_TIME}.")
        scheduler = BlockingScheduler()
        try:
            hour, minute = map(int, SCHEDULE_TIME.split(":"))
            scheduler.add_job(run_pipeline, CronTrigger(hour=hour, minute=minute), id="daily_pipeline")
            logger.info(f"✅ Scheduler active. Next run at {SCHEDULE_TIME} every day.")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
