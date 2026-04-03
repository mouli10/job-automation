import asyncio
import random
import logging
from src.config import SCRAPER_MIN_DELAY, SCRAPER_MAX_DELAY, SCRAPER_MAX_JOBS_DAY

logger = logging.getLogger(__name__)

class SafetyController:
    """Handles evasion techniques to mask Playwright scraper behavior as a human user."""
    
    def __init__(self):
        self.jobs_scraped_today = 0
        self.captcha_hit = False

    async def random_delay(self):
        """Pause execution randomly between MIN_DELAY and MAX_DELAY"""
        delay = random.uniform(SCRAPER_MIN_DELAY, SCRAPER_MAX_DELAY)
        logger.debug(f"Safety pause: {delay:.2f} seconds")
        await asyncio.sleep(delay)

    async def human_scroll(self, page):
        """Scroll slowly in random pixel increments to simulate reading limits"""
        scroll_height = await page.evaluate("document.body.scrollHeight")
        current_scroll = 0
        
        while current_scroll < scroll_height:
            step = random.randint(100, 400)
            current_scroll += step
            await page.mouse.wheel(0, step)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            if random.random() > 0.8:
                # Randomly scroll up slightly to simulate reading re-checks
                up_step = random.randint(50, 150)
                await page.mouse.wheel(0, -up_step)
                await asyncio.sleep(random.uniform(0.5, 1.0))

    async def random_mouse_move(self, page):
        """Move cursor aggressively across screen using splines"""
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        # Sequence of steps mimics non-robotic sliding transitions
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await asyncio.sleep(random.uniform(0.2, 0.8))

    async def detect_captcha(self, page) -> bool:
        """Inspect DOM for known LinkedIn block indicators to abort safely"""
        try:
            challenge = await page.locator('#captcha-internal').count()
            if challenge > 0:
                logger.error("CAPTCHA detected by SafetyController!")
                self.captcha_hit = True
                return True
                
            if "checkpoint/challenge" in page.url:
                logger.error("LinkedIn hit a security checkpoint/challenge limit.")
                self.captcha_hit = True
                return True
                
        except Exception:
            pass
        return False

    def check_limit(self, max_jobs: int = None) -> bool:
        """Enforce maximum safe daily scrapes per run"""
        limit = max_jobs if max_jobs is not None else SCRAPER_MAX_JOBS_DAY
        if self.jobs_scraped_today >= limit:
            logger.warning(f"Safety controller hit definitive ceiling of {limit} jobs. Halting further scrapes.")
            return False
        return True
