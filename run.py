"""
run.py — Watchdog Entry Point for Windows Task Scheduler

How it works:
  - Windows Task Scheduler fires this script every 30 minutes
  - This script checks if current time matches the schedule set in the Admin Portal (±14 mins tolerance)
  - If it's time → run the full pipeline
  - If it already ran today → skip (prevents double-runs)
  - If it's not the right time → exit silently (0.1s overhead, no cost)

Windows Task Scheduler setup:
  Program:   C:\\path\\to\\automation\\venv\\Scripts\\python.exe
  Arguments: run.py
  Start in:  C:\\path\\to\\automation
  Frequency: Every 30 minutes, all day
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Bootstrap path so src imports work ──────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.config import LOGS_DIR, DATA_DIR

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = LOGS_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("watchdog")

# ── State file: tracks the last date the pipeline ran ─────────────────────────
LAST_RUN_FILE = DATA_DIR / "last_run_date.txt"

# ── Lock file: prevents two instances running at the same time ────────────────
LOCK_FILE = DATA_DIR / "pipeline.lock"

TOLERANCE_MINUTES = 14   # ±14 min window works for a 30-min trigger interval


def _is_pipeline_running() -> bool:
    """
    Returns True if another pipeline instance is actively running.
    Checks the PID stored in the lockfile against the OS process list.
    """
    if not LOCK_FILE.exists():
        return False
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
        import psutil
        if psutil.pid_exists(pid):
            logger.warning(f"🔒 Pipeline already running (PID {pid}). Skipping this trigger.")
            return True
        else:
            # Stale lock from a crashed run — clean it up
            logger.info(f"🧹 Stale lock found (PID {pid} no longer exists). Clearing.")
            LOCK_FILE.unlink(missing_ok=True)
            return False
    except Exception as e:
        logger.warning(f"Could not read lock file: {e}. Assuming no lock.")
        LOCK_FILE.unlink(missing_ok=True)
        return False


def _acquire_lock():
    """Writes current process PID to the lock file."""
    import os
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _release_lock():
    """Removes the lock file when the pipeline finishes."""
    LOCK_FILE.unlink(missing_ok=True)



def _already_ran(scheduled_time: str) -> bool:
    """Returns True if this specific scheduled run already completed successfully today."""
    if not LAST_RUN_FILE.exists():
        return False
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        stamp = f"{today} {scheduled_time}"
        history = LAST_RUN_FILE.read_text(encoding="utf-8").splitlines()
        return stamp in [line.strip() for line in history]
    except Exception:
        return False


def _mark_ran(scheduled_time: str):
    """Appends today's date + scheduled time into the state file."""
    today = datetime.now().strftime("%Y-%m-%d")
    stamp = f"{today} {scheduled_time}\n"
    with open(LAST_RUN_FILE, "a", encoding="utf-8") as f:
        f.write(stamp)


def _get_matched_schedule() -> str:
    """
    Checks if today is an active day and if current time matches any run_times.
    Returns the first matched time string, or None.
    """
    from src.config_manager import ConfigManager
    config = ConfigManager.load_config()
    sched_cfg = config.get("scheduler", {})
    run_times = sched_cfg.get("run_times", ["07:00"])
    run_days  = sched_cfg.get("run_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])

    now = datetime.now()
    day_name = now.strftime("%A")

    if day_name not in run_days:
        logger.info(f"⏸  Today is {day_name}, which is NOT an active reporting day. Skipping.")
        return None

    for scheduled_str in run_times:
        try:
            sched_h, sched_m = map(int, scheduled_str.split(":"))
            sched_dt = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
            delta = abs((now - sched_dt).total_seconds()) / 60
            if delta <= TOLERANCE_MINUTES:
                logger.info(f"⏱  Match Found! Scheduled: {scheduled_str} | Now: {now.strftime('%H:%M')} | Δ {delta:.1f} min")
                return scheduled_str
        except Exception as e:
            logger.error(f"Could not parse scheduled time '{scheduled_str}': {e}")
    
    return None


def main():
    logger.info("=" * 50)
    logger.info("🔔 Watchdog triggered by Task Scheduler")

    matched_time = _get_matched_schedule()
    if not matched_time:
        logger.info("⏸  Not the right time for any scheduled run. Standing by.")
        return

    if _already_ran(matched_time):
        logger.info(f"✅ Pipeline already ran for the {matched_time} slot today. Exiting.")
        return

    try:
        from src.main import run_pipeline
        from src.config_manager import ConfigManager
        config = ConfigManager.load_config()
        run_pipeline(config_override=config)
        _mark_ran(matched_time)
        logger.info(f"✅ Pipeline task finished for {matched_time} slot.")
    except Exception as e:
        # Note: Collision errors (RuntimeError) from main.py will be caught here silently if needed
        if "already running" in str(e):
             logger.info("⏸  Skipping: Pipeline is already active.")
        else:
             logger.error(f"❌ Watchdog task failed: {e}")



if __name__ == "__main__":
    main()
