from src.config import SCRAPER_ENGINE
from src.scraper.linkedin import LinkedInCookieScraper
from src.scraper.apify import ApifyScraper
import logging

logger = logging.getLogger(__name__)

def get_scraper():
    """Factory to retrieve the appropriate configured job scraper instance."""
    from src.config import admin_config, SCRAPER_ENGINE
    
    # Check Dashboard config first, then fallback to .env
    engine_type = admin_config.get("scraper_engine", SCRAPER_ENGINE).lower()
    
    if engine_type == "apify":
        logger.info("Initializing Apify Third-Party API Engine (Residential Proxy)")
        return ApifyScraper()
        
    logger.info("Initializing Live LinkedIn Authenticated Playwright Engine")
    return LinkedInCookieScraper()
