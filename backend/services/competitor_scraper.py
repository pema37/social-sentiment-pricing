# backend/services/competitor_scraper.py

"""
Competitor Price Scraping Service

This service handles fetching competitor prices from their websites.
In Phase 2, we implement a basic HTTP scraper with CSS selector support.
Future phases will add:
- Headless browser support (Playwright/Selenium) for JS-rendered pages
- API integrations for partners
- Proxy rotation for rate limiting
- ML-based price extraction
"""

import uuid as uuid_lib
import re
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from models.competitor import Competitor
from models.competitor_product import CompetitorProduct
from models.competitor_price_history import CompetitorPriceHistory


logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result of a price scrape attempt."""
    success: bool
    price: Optional[Decimal] = None
    currency: str = "USD"
    is_available: bool = True
    error: Optional[str] = None
    raw_price_text: Optional[str] = None
    scraped_at: datetime = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now(timezone.utc)


class CompetitorScraperService:
    """
    Service for scraping competitor product prices.
    
    Supports multiple extraction methods:
    - CSS selectors (default)
    - XPath (future)
    - JSON-LD structured data
    - Open Graph meta tags
    """

    # Common price patterns
    PRICE_PATTERNS = [
        r'\$[\d,]+\.?\d*',           # $1,234.56
        r'[\d,]+\.?\d*\s*(?:USD|usd)',  # 1234.56 USD
        r'USD\s*[\d,]+\.?\d*',       # USD 1234.56
        r'[\d,]+\.?\d*',             # 1234.56 (fallback)
    ]

    # Default request headers
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        respect_robots: bool = True
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.respect_robots = respect_robots

    async def scrape_price(
        self,
        competitor_product: CompetitorProduct,
        competitor: Competitor
    ) -> ScrapeResult:
        """
        Scrape the current price for a competitor product.
        
        Args:
            competitor_product: The competitor product mapping
            competitor: The competitor entity (contains scraping config)
            
        Returns:
            ScrapeResult with price or error
        """
        url = competitor_product.competitor_product_url
        config = competitor.scraping_config or {}

        try:
            # Fetch the page
            html = await self._fetch_page(url, config)
            if html is None:
                return ScrapeResult(
                    success=False,
                    error="Failed to fetch page after retries"
                )

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Try extraction methods in order of preference
            price, raw_text = await self._extract_price(soup, config)

            if price is None:
                return ScrapeResult(
                    success=False,
                    error="Could not extract price from page",
                    raw_price_text=raw_text
                )

            # Check availability
            is_available = self._check_availability(soup, config)

            return ScrapeResult(
                success=True,
                price=price,
                currency=config.get("currency", "USD"),
                is_available=is_available,
                raw_price_text=raw_text
            )

        except httpx.TimeoutException:
            return ScrapeResult(success=False, error="Request timeout")
        except httpx.HTTPStatusError as e:
            return ScrapeResult(success=False, error=f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.exception(f"Scraping error for {url}")
            return ScrapeResult(success=False, error=str(e))

    async def _fetch_page(
        self,
        url: str,
        config: Dict
    ) -> Optional[str]:
        """Fetch page HTML with retries."""
        headers = {**self.DEFAULT_HEADERS}
        if config.get("headers"):
            headers.update(config["headers"])

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                    response.raise_for_status()
                    return response.text
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
        return None

    async def _extract_price(
        self,
        soup: BeautifulSoup,
        config: Dict
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Extract price from parsed HTML.
        
        Tries methods in order:
        1. Configured CSS selector
        2. JSON-LD structured data
        3. Open Graph meta tags
        4. Common price selectors
        """
        raw_text = None

        # Method 1: Configured CSS selector
        if config.get("price_selector"):
            element = soup.select_one(config["price_selector"])
            if element:
                raw_text = element.get_text(strip=True)
                price = self._parse_price(raw_text)
                if price:
                    return price, raw_text

        # Method 2: JSON-LD structured data
        price, raw = self._extract_from_json_ld(soup)
        if price:
            return price, raw

        # Method 3: Open Graph / meta tags
        price, raw = self._extract_from_meta(soup)
        if price:
            return price, raw

        # Method 4: Common selectors fallback
        common_selectors = [
            '[data-price]',
            '.price',
            '.product-price',
            '.current-price',
            '#price',
            '[itemprop="price"]',
            '.a-price .a-offscreen',  # Amazon
            '.price-current',         # Newegg
            '.priceView-hero-price span', # Best Buy
        ]

        for selector in common_selectors:
            element = soup.select_one(selector)
            if element:
                # Check for data attribute first
                if element.get('data-price'):
                    raw_text = element.get('data-price')
                elif element.get('content'):
                    raw_text = element.get('content')
                else:
                    raw_text = element.get_text(strip=True)

                price = self._parse_price(raw_text)
                if price:
                    return price, raw_text

        return None, raw_text

    def _extract_from_json_ld(
        self,
        soup: BeautifulSoup
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Extract price from JSON-LD structured data."""
        import json

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Handle array of items
                if isinstance(data, list):
                    data = data[0] if data else {}

                # Look for Product schema
                if data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    
                    price_str = str(offers.get('price', ''))
                    if price_str:
                        price = self._parse_price(price_str)
                        if price:
                            return price, price_str
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

        return None, None

    def _extract_from_meta(
        self,
        soup: BeautifulSoup
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Extract price from meta tags."""
        meta_properties = [
            'og:price:amount',
            'product:price:amount',
            'price',
        ]

        for prop in meta_properties:
            meta = soup.find('meta', property=prop) or soup.find('meta', attrs={'name': prop})
            if meta and meta.get('content'):
                raw_text = meta.get('content')
                price = self._parse_price(raw_text)
                if price:
                    return price, raw_text

        return None, None

    def _parse_price(self, text: str) -> Optional[Decimal]:
        """Parse a price string into a Decimal."""
        if not text:
            return None

        text = text.strip()

        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                price_str = match.group()
                # Remove currency symbols and whitespace
                price_str = re.sub(r'[^\d.,]', '', price_str)
                # Handle comma as thousands separator
                price_str = price_str.replace(',', '')

                try:
                    return Decimal(price_str)
                except InvalidOperation:
                    continue

        return None

    def _check_availability(self, soup: BeautifulSoup, config: Dict) -> bool:
        """Check if product is in stock."""
        # Check configured selector
        if config.get("out_of_stock_selector"):
            if soup.select_one(config["out_of_stock_selector"]):
                return False

        # Common out of stock indicators
        out_of_stock_indicators = [
            'out of stock',
            'sold out',
            'currently unavailable',
            'not available',
            'out-of-stock',
        ]

        page_text = soup.get_text().lower()
        for indicator in out_of_stock_indicators:
            if indicator in page_text:
                # Could be false positive, so check nearby price element
                return False

        return True

    def create_price_history_record(
        self,
        competitor_product: CompetitorProduct,
        scrape_result: ScrapeResult,
    ) -> Optional[CompetitorPriceHistory]:
        """
        Create a price history record if price changed.
        
        Returns None if price hasn't changed.
        """
        if not scrape_result.success or scrape_result.price is None:
            return None

        old_price = competitor_product.current_price
        new_price = scrape_result.price

        # Skip if price hasn't changed (within small tolerance)
        if old_price is not None:
            if abs(new_price - old_price) < Decimal("0.01"):
                return None

        # Calculate change
        change_amount = None
        change_percent = None
        change_type = "initial"

        if old_price is not None and old_price > 0:
            change_amount = new_price - old_price
            change_percent = (change_amount / old_price) * 100
            change_percent = change_percent.quantize(Decimal("0.01"))

            if change_amount > 0:
                change_type = "increase"
            elif change_amount < 0:
                change_type = "decrease"
                # Check if it looks like a promotion (>10% drop)
                if change_percent < Decimal("-10"):
                    change_type = "promotion"

        # Detect restock
        was_available = competitor_product.price_available
        if not was_available and scrape_result.is_available:
            change_type = "restock"

        return CompetitorPriceHistory(
            competitor_product_id=competitor_product.id,
            old_price=old_price,
            new_price=new_price,
            currency=scrape_result.currency,
            change_amount=change_amount,
            change_percent=change_percent,
            change_type=change_type,
            detected_promotion=(change_type == "promotion"),
            was_available=was_available,
            is_available=scrape_result.is_available,
            scraped_url=competitor_product.competitor_product_url,
            scrape_method="http",
            observed_at=scrape_result.scraped_at,
        )


# Singleton instance
competitor_scraper = CompetitorScraperService()

