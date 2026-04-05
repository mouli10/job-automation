from typing import List, Dict
from src.scraper.base import BaseScraper
import logging
from apify_client import ApifyClient
from src.config import admin_config
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class ApifyScraper(BaseScraper):
    """
    LinkedIn Jobs Scraper using Apify (curious_coder/linkedin-jobs-scraper).
    Bypasses Cloud-IP blocks by using Residential Proxies via Apify.
    """
    
    def scrape(self, roles: List[str], locations: List[str], config: dict = None) -> List[Dict]:
        logger.info("🚀 Initializing Apify LinkedIn Scraper...")
        
        # Load API Token from config (Dashboard)
        conf = config if config else admin_config
        token = conf.get("apify_api_token", "").strip()
        
        if not token:
            logger.error("❌ APIFY_API_TOKEN is not set in Dashboard. Cannot use Apify.")
            return []
            
        client = ApifyClient(token)
        jobs = []
        
        # Prepare search logic (Zero-Waste Spam Shield)
        from src.scraper.linkedin import build_li_filters, build_combined_query
        
        # We search one role at a time to keep Apify results high-quality
        for location in locations:
            for role in roles:
                try:
                    # Construct search URL (Universal Translator 🦾)
                    # We use the existing engine to build the query and filters
                    query = build_combined_query([role])
                    filters = build_li_filters(conf.get("search", {}).get("filters", {}))
                    
                    full_url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={quote_plus(location)}&{filters}"
                    
                    logger.info(f"   [Apify] Searching via URL: {full_url[:120]}...")
                    
                    # Call Apify Actor: curious_coder/linkedin-jobs-scraper
                    run_input = {
                        "urls": [full_url],
                        "count": conf.get("limits", {}).get("scrape_limit", 50),
                        "proxyConfiguration": {"useApifyProxy": True}
                    }
                    
                    # Run the Actor and wait for it to finish
                    run = client.actor("curious_coder/linkedin-jobs-scraper").call(run_input=run_input)
                    
                    # Fetch results
                    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                        # Map Apify raw fields to our standard format
                        jobs.append({
                            "title": item.get("title", "Unknown Role"),
                            "company": item.get("companyName", "Unknown Company"),
                            "location": item.get("location", location),
                            "description": item.get("description", ""),
                            "skills": "Auto-extracted by Apify",
                            "experience_required": "N/A",
                            "salary": "N/A",
                            "link": item.get("jobUrl", ""),
                            "posting_date": item.get("postedAt", "Recent")
                        })
                        
                    logger.info(f"   [Apify] ✓ Found {len(jobs)} total jobs so far.")
                    
                except Exception as e:
                    logger.error(f"❌ Apify Actor failed for '{role}': {e}")
                    continue
                    
        logger.info(f"\n✅ Apify Scraping complete. {len(jobs)} jobs collected.")
        return jobs
