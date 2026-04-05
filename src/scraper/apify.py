from typing import List, Dict
from src.scraper.base import BaseScraper
import logging
from apify_client import ApifyClient
from src.config import admin_config
from urllib.parse import quote_plus
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ApifyScraper(BaseScraper):
    """
    LinkedIn Jobs Scraper using Apify (curious_coder/linkedin-jobs-scraper).
    Optimized for Cost: Bundles all roles into a single high-efficiency task.
    Optimized for Data: Deep-cleans HTML descriptions for AI scoring.
    """
    
    def _clean_html(self, html_content: str) -> str:
        """Cleans LinkedIn HTML job descriptions into readable text for the AI."""
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=' ')
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception:
            # Fallback to simple regex if BS4 fails
            return re.sub('<[^<]+?>', '', html_content)

    def scrape(self, roles: List[str], locations: List[str], config: dict = None) -> List[Dict]:
        logger.info("🚀 Initializing Optimized Apify LinkedIn Scraper...")
        
        conf = config if config else admin_config
        token = conf.get("apify_api_token", "").strip()
        
        if not token:
            logger.error("❌ APIFY_API_TOKEN is not set. Cannot use Apify.")
            return []
            
        client = ApifyClient(token)
        jobs = []
        
        from src.scraper.linkedin import build_li_filters, build_combined_query
        
        # ── MONEY-SAVER 💰 ──
        # Instead of looping and calling the Actor 5 times, we build ALL URLs first
        # and run them in ONE SINGLE actor run. This saves 80% on overhead costs.
        all_search_urls = []
        for location in locations:
            for role in roles:
                query = build_combined_query([role])
                filters = build_li_filters(conf.get("search", {}).get("filters", {}))
                url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={quote_plus(location)}&{filters}"
                all_search_urls.append(url)
        
        if not all_search_urls:
            return []

        try:
            total_limit = conf.get("limits", {}).get("scrape_limit", 50)
            logger.info(f"   [Apify] Bundling {len(all_search_urls)} role searches into ONE task (Limit: {total_limit} total).")
            
            # Call Apify Actor: curious_coder/linkedin-jobs-scraper
            run_input = {
                "urls": all_search_urls,
                "count": max(10, total_limit), # Must be at least 10 for this actor
                "proxyConfiguration": {"useApifyProxy": True}
            }
            
            # Run the Actor once
            run = client.actor("curious_coder/linkedin-jobs-scraper").call(run_input=run_input)
            dataset_id = run["defaultDatasetId"]
            
            # Fetch and Map results
            raw_items = list(client.dataset(dataset_id).iterate_items())
            logger.info(f"   [Apify] Handshake complete. Received {len(raw_items)} raw job items.")
            
            for i, item in enumerate(raw_items):
                # Robust Description Discovery 🕵️‍♂️
                # We check multiple fields that curious_coder uses for the full text
                raw_desc = item.get("descriptionText") or item.get("description") or item.get("descriptionHtml") or ""
                clean_desc = self._clean_html(raw_desc)
                
                # DATA AUDIT LOG: Only log for the first job to avoid spamming
                if i == 0:
                    keys = list(item.keys())
                    desc_len = len(clean_desc)
                    logger.info(f"   [Apify] Data Audit (Job 1): Found {desc_len} chars in description. Available fields: {keys[:10]}...")

                jobs.append({
                    "title": item.get("title", "Unknown Role"),
                    "company": item.get("companyName", item.get("company", "Unknown")),
                    "location": item.get("location", "Remote/USA"),
                    "description": clean_desc,
                    "link": item.get("jobUrl", item.get("url", "")),
                    "posting_date": item.get("postedAt", "Recent")
                })
                
                # Respect the user's hard limit
                if len(jobs) >= total_limit:
                    break

        except Exception as e:
            logger.error(f"❌ Optimized Apify Task Failed: {e}")
            
        logger.info(f"\n✅ Apify Scraping complete. {len(jobs)} jobs recovered and cleaned.")
        return jobs
