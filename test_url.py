from src.scraper.linkedin import build_combined_query, build_li_filters
from urllib.parse import unquote

roles = ["Data Analyst", "Analytics Engineer", "Data Engineer", "Product Analyst", "BI Engineer"]
filters = {
    "time_filter": "Past Week",
    "remote": True,
    "hybrid": True,
    "onsite": False,
    "entry_level": True,
    "associate": True,
    "mid_senior": False
}

query = build_combined_query(roles)
params = build_li_filters(filters)
url = f"https://www.linkedin.com/jobs/search?keywords={query}&location=United+States&{params}"

print(f"TEST URL: {unquote(url)}")
