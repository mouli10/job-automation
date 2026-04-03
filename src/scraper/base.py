from abc import ABC, abstractmethod
from typing import List, Dict

class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""
    
    @abstractmethod
    def scrape(self, roles: List[str], locations: List[str], config: dict = None) -> List[Dict]:
        """
        Scrape jobs based on roles and locations.
        config: Dictionary containing scraper limits and filters.
        """
        pass
