import time
import asyncio
import logging
from src.config import DATA_DIR

logger = logging.getLogger(__name__)

async def capture_screenshot(page, name: str):
    """
    Stand-alone Cloud Vision utility to capture debug screenshots.
    Decoupled from the Scraper class to avoid caching/import issues.
    """
    shot_dir = DATA_DIR / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}_{int(time.time())}.png"
    path = shot_dir / filename
    
    try:
        await page.screenshot(path=str(path), full_page=False)
        logger.info(f"📸 Cloud Vision: Captured {name} -> {filename}")
        return path
    except Exception as e:
        logger.warning(f"❌ Cloud Vision failed for {name}: {e}")
        return None
