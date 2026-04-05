from typing import List, Dict
from src.scraper.base import BaseScraper
import logging
from apify_client import ApifyClient
from src.config import admin_config

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
        # We search one role at a time to keep Apify results high-quality
        for location in locations:
            for role in roles:
                try:
                    # Construct search query with NOT filters (Spam Shield 🛡️)
                    blacklist_companies = conf.get("blacklist", {}).get("companies", [])
                    query = f'"{role}"'
                    if blacklist_companies:
                        not_string = " ".join([f'NOT "{c}"' for c in blacklist_companies[:5]]) # Cap to 5 to avoid query too long
                        query = f'({query}) {not_string}'
                    
                    logger.info(f"   [Apify] Searching: {query} in {location}")
                    
                    # Call Apify Actor: curious_coder/linkedin-jobs-scraper
                    # This is the most reliable actor for $5/mo free credit tier.
                    run_input = {
                        "searchQueries": [query],
                        "location": location,
                        "maxItems": conf.get("limits", {}).get("scrape_limit", 50),
                        "publishedAt": "past-week",
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
