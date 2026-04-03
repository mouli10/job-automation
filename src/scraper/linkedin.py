import asyncio
from typing import List, Dict
from playwright.async_api import async_playwright
from src.scraper.base import BaseScraper
import logging
from src.config import SCRAPER_MAX_PAGES, CHROME_PROFILE_DIR, SEARCH_ROLES
from src.scraper.safety import SafetyController
from urllib.parse import quote_plus

from src.scraper.vision import capture_screenshot
logger = logging.getLogger(__name__)

from src.config import admin_config

def build_li_filters(filters_config: dict) -> str:
    """Dynamically builds the LinkedIn URL parameter string based on Admin config toggles."""
    params = []
    
    # Time Filters
    tf = filters_config.get("time_filter", "Last 24 hours")
    if tf == "Last 24 hours":
        params.append("f_TPR=r86400")
    elif tf == "Past Week":
        params.append("f_TPR=r604800")
    elif tf == "Past Month":
        params.append("f_TPR=r2592000")
        
    # Remote/Hybrid Filters
    wt = []
    if filters_config.get("onsite"): wt.append("1")
    if filters_config.get("remote"): wt.append("2")
    if filters_config.get("hybrid"): wt.append("3")
    if wt:
        params.append(f"f_WT={('%2C'.join(wt))}")
        
    # Experience Level Filters
    exp = []
    if filters_config.get("entry_level"): exp.append("1")
    if filters_config.get("associate"): exp.append("2")
    if filters_config.get("mid_senior"): exp.append("4")
    if exp:
        params.append(f"f_E={('%2C'.join(exp))}")
        
    params.append("sortBy=DD")
    return "&".join(params)


def build_combined_query(roles: List[str]) -> str:
    """Builds a single LinkedIn Boolean OR query from all roles."""
    combined = " OR ".join(f'"{role}"' for role in roles)
    logger.info(f"Combined search query: {combined[:120]}...")
    return quote_plus(combined)


class LinkedInCookieScraper(BaseScraper):
    """
    Single combined-query LinkedIn scraper.
    Searches ALL roles at once using Boolean OR, sorted by latest posted.
    """

    def __init__(self):
        self.safety = SafetyController()


    async def _async_scrape(self, roles: List[str], locations: List[str], config: dict = None) -> List[Dict]:
        if config is None:
            from src.config import admin_config
            config = admin_config

        jobs = []
        seen_keys = set()   # In-run deduplication: (title.lower(), company.lower())

        # Build single combined OR query for all roles
        combined_query = build_combined_query(roles)
        location = locations[0] if locations else "United States"
        encoded_location = quote_plus(location)

        async with async_playwright() as p:
            logger.info(f"Booting persistent Chrome Profile at {CHROME_PROFILE_DIR}...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(CHROME_PROFILE_DIR),
                headless=True,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800},
                args=["--disable-blink-features=AutomationControlled"]
            )

            page = context.pages[0] if context.pages else await context.new_page()

            # --- COOKIE INJECTION ---
            if config and "linkedin" in config and "li_at_cookie" in config["linkedin"]:
                logger.info("🍪 Injecting fresh LI_AT cookie from dashboard wizard...")
                await context.add_cookies([{
                    "name": "li_at",
                    "value": config["linkedin"]["li_at_cookie"],
                    "domain": ".www.linkedin.com",
                    "path": "/"
                }])
            async def block_media(route):
                if route.request.resource_type in ["image", "media", "font"]:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", block_media)

            # --- AUTH CHECK ---
            logger.info("Auditing Chrome authentication status on LinkedIn Feed...")
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await asyncio.sleep(4)

            logged_in = (
                "feed" in page.url or
                "m/in" in page.url or
                await page.locator('.global-nav').count() > 0
            )

            if not logged_in:
                logger.warning("\n=======================================================")
                logger.warning("⚠️  MANUAL LOGIN REQUIRED ⚠️")
                logger.warning("You have 90 seconds to log into LinkedIn manually.")
                logger.warning("=======================================================\n")
                await asyncio.sleep(90)
                logged_in = (
                    "feed" in page.url or
                    await page.locator('.global-nav').count() > 0
                )
                if not logged_in:
                    logger.error("Authentication failed within 90 seconds. Aborting.")
                    # ── Cookie Expiry Email Alert ─────────────────────────────
                    try:
                        from src.reporting.email_sender import send_email
                        send_email(
                            subject="🚨 LinkedIn Cookie Expired — Action Required",
                            body=(
                                "Hi,\n\n"
                                "Your AI Job Pipeline tried to run today but could NOT authenticate with LinkedIn.\n\n"
                                "This means your LinkedIn session cookie (li_at) has expired.\n\n"
                                "To fix this:\n"
                                "  1. Open Chrome and go to linkedin.com\n"
                                "  2. Log in manually\n"
                                "  3. Press F12 → Application → Cookies → linkedin.com\n"
                                "  4. Copy the value of the 'li_at' cookie\n"
                                "  5. Paste it into your .env file under LINKEDIN_LI_AT_COOKIE=\n"
                                "  6. Save the file and re-run the pipeline\n\n"
                                "No jobs were scraped today. The pipeline will retry tomorrow.\n\n"
                                "— AI Job Pipeline 🤖"
                            )
                        )
                        logger.info("📧 Cookie expiry alert sent to your email.")
                    except Exception as mail_err:
                        logger.error(f"Failed to send cookie alert email: {mail_err}")
                    # ─────────────────────────────────────────────────────────
                    await context.close()
                    return jobs

            # --- DYNAMIC LOGGING ---
            await capture_screenshot(page, "login_success_feed")
            filters = config['search']['filters']
            time_label = filters.get('time_filter', 'Last 24 hours')
            
            # Build Location/Type label
            loc_types = []
            if filters.get('onsite'): loc_types.append("Onsite")
            if filters.get('remote'): loc_types.append("Remote")
            if filters.get('hybrid'): loc_types.append("Hybrid")
            loc_label = "+".join(loc_types) if loc_types else "All Types"
            
            # Build Exp label
            exp_lvls = []
            if filters.get('entry_level'): exp_lvls.append("Entry")
            if filters.get('associate'): exp_lvls.append("Associate")
            if filters.get('mid_senior'): exp_lvls.append("Mid-Senior")
            exp_label = "+".join(exp_lvls) if exp_lvls else "All Levels"
            
            logger.info(f"🔍 Single combined query | {len(roles)} roles | {location}")
            logger.info(f"   Filters: {time_label} | {loc_label} | {exp_label} | Sorted: Latest First")
            # --- END DYNAMIC LOGGING ---

            limit_hit = False
            scrape_limit = config["limits"]["scrape_limit"]

            for page_num in range(SCRAPER_MAX_PAGES):
                if limit_hit:
                    break

                offset = page_num * 25
                url = (
                    f"https://www.linkedin.com/jobs/search"
                    f"?keywords={combined_query}"
                    f"&location={encoded_location}"
                    f"&{build_li_filters(config['search']['filters'])}"
                    f"&start={offset}"
                )

                logger.info(f"📄 Page {page_num + 1} (offset {offset})...")

                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await self.safety.random_delay()
                    if page_num == 0:
                        await capture_screenshot(page, "search_results_page_1")
                    await self.safety.random_mouse_move(page)

                    is_captcha = await self.safety.detect_captcha(page)
                    if is_captcha:
                        logger.error("🚨 CAPTCHA detected! Pausing 30 mins.")
                        await context.close()
                        await asyncio.sleep(1800)
                        return jobs

                    try:
                        await page.wait_for_selector(
                            '.jobs-search-results-list__list-item, .job-card-container, .job-card-list, .base-card, .job-search-card',
                            timeout=15000
                        )
                    except Exception:
                        logger.info(f"  No job cards found on page {page_num + 1} with current selectors.")
                        break

                    await self.safety.human_scroll(page)
                    cards = await page.locator('.jobs-search-results-list__list-item, .job-card-container, .job-card-list, .base-card, .job-search-card').all()

                    if not cards:
                        logger.info("  No cards found. End of results.")
                        break

                    for card in cards:
                        if not self.safety.check_limit(scrape_limit):
                            logger.info(f"✅ Daily limit reached ({self.safety.jobs_scraped_today} jobs). Stopping.")
                            limit_hit = True
                            break

                        try:
                            await self.safety.random_delay()

                            # --- LINK + TITLE EXTRACTION ---
                            link = None
                            title = ""

                            anchors = await card.locator('a[href*="/jobs/view/"]').all()
                            if anchors:
                                link = await anchors[0].get_attribute("href")
                                if link and not link.startswith("http"):
                                    link = "https://www.linkedin.com" + link.split("?")[0]
                                try:
                                    title = await anchors[0].inner_text()
                                except Exception:
                                    pass

                            if not title:
                                for sel in [
                                    '.job-card-list__title',
                                    '.artdeco-entity-lockup__title',
                                    '.job-card-container__link'
                                ]:
                                    try:
                                        loc = card.locator(sel).first
                                        if await loc.count() > 0:
                                            title = await loc.inner_text()
                                            if not link:
                                                href = await loc.get_attribute("href")
                                                if href:
                                                    link = "https://www.linkedin.com" + href.split("?")[0] if not href.startswith("http") else href
                                            break
                                    except Exception:
                                        continue

                            title = title.strip().split("\n")[0]
                            if not title:
                                continue

                            # --- COMPANY EXTRACTION ---
                            company = ""
                            for sel in [
                                '.job-card-container__primary-description',
                                '.artdeco-entity-lockup__subtitle',
                                '.job-card-list__company-name'
                            ]:
                                try:
                                    loc = card.locator(sel).first
                                    if await loc.count() > 0:
                                        company = (await loc.inner_text()).strip().split("\n")[0]
                                        break
                                except Exception:
                                    continue

                            # --- PRE-SCRAPE BLACKLIST CHECK ---
                            blacklisted = False
                            
                            # Check company blacklist
                            for bc in config["blacklist"]["companies"]:
                                if bc.lower() in company.lower():
                                    blacklisted = True
                                    logger.debug(f"  ❌ Blacklisted Company skipped: {company}")
                                    break
                                    
                            # Check keywords blacklist
                            if not blacklisted:
                                for bk in config["blacklist"]["keywords"]:
                                    if bk.lower() in title.lower():
                                        blacklisted = True
                                        logger.debug(f"  ❌ Blacklisted Keyword skipped: '{bk}' in '{title}'")
                                        break
                                        
                            if blacklisted:
                                continue

                            # --- IN-RUN DEDUPLICATION ---
                            dedup_key = (title.lower(), company.lower())
                            if dedup_key in seen_keys:
                                logger.debug(f"  Duplicate skipped: {title} @ {company}")
                                continue
                            seen_keys.add(dedup_key)

                            # --- DEEP CLICK: fetch full job description ---
                            await card.click()
                            await asyncio.sleep(2.0)

                            description = ""
                            try:
                                desc_loc = page.locator(
                                    '.jobs-description__content, #job-details, '
                                    '.jobs-search__job-details--container, .job-view-layout'
                                )
                                description = await desc_loc.first.inner_text()
                            except Exception:
                                pass

                            # --- POSTING DATE EXTRACTION ---
                            posting_date = "Recent (24h)"
                            try:
                                card_text = await card.inner_text()
                                import re
                                
                                # Try standard "X hours/minutes/days ago"
                                match1 = re.search(r'(\d+)\s+(minute|hour|day)s?\s+ago', card_text, re.IGNORECASE)
                                if match1:
                                    posting_date = match1.group(0)
                                else:
                                    # Fallback to LinkedIn shorthand like "4h", "12m", "1d"
                                    # We look for a standalone number followed by m/h/d near the job title
                                    match2 = re.search(r'\b(\d+)\s*(m|h|d)\b', card_text, re.IGNORECASE)
                                    if match2:
                                        val = match2.group(1)
                                        unit = match2.group(2).lower()
                                        if unit == 'm': posting_date = f"{val} minutes ago"
                                        elif unit == 'h': posting_date = f"{val} hours ago"
                                        elif unit == 'd': posting_date = f"{val} days ago"
                            except Exception:
                                pass

                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "description": description.strip() if len(description) > 50
                                              else f"See LinkedIn listing for {title}.",
                                "skills": "Extracted from Description",
                                "experience_required": "Entry/Associate/Mid-Senior",
                                "salary": "N/A",
                                "link": link,
                                "posting_date": posting_date
                            })
                            self.safety.jobs_scraped_today += 1
                            logger.info(f"  ✓ [{self.safety.jobs_scraped_today}] {title} @ {company}")

                        except Exception as e:
                            logger.debug(f"  Card skipped: {e}")

                except Exception as e:
                    logger.error(f"Error on page {page_num + 1}: {e}")

            await context.close()

        logger.info(f"\n✅ Scraping complete. {len(jobs)} jobs collected from combined search.")
        return jobs

    def scrape(self, roles: List[str], locations: List[str], config: dict = None) -> List[Dict]:
        return asyncio.run(self._async_scrape(roles, locations, config))
