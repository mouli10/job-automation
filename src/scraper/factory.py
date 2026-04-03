from src.config import SCRAPER_ENGINE
from src.scraper.linkedin import LinkedInCookieScraper
from src.scraper.apify import ApifyScraper
import logging

logger = logging.getLogger(__name__)

def get_scraper():
    """Factory to retrieve the appropriate configured job scraper instance."""
    if SCRAPER_ENGINE.lower() == "apify":
        logger.info("Initializing Apify Third-Party API Engine")
        return ApifyScraper()
        
    logger.info("Initializing Live LinkedIn Authenticated Playwright Engine")
    return LinkedInCookieScraper()
