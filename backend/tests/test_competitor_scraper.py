# backend/tests/test_competitor_scraper.py
"""
Comprehensive tests for CompetitorScraperService — fetches competitor prices
from websites via CSS selectors, JSON-LD, meta tags, with price anomaly detection.

Tests cover:
- ScrapeResult dataclass
- CompetitorScraperService initialization & constants
- _parse_price (regex patterns)
- _validate_price (anomaly detection)
- _check_availability (out-of-stock detection)
- _extract_from_meta (OG/meta tag extraction)
- _extract_from_json_ld (structured data extraction)
- _extract_price (orchestration of extraction methods)
- _fetch_page (HTTP fetch with retries)
- scrape_price (full orchestration)
- create_price_history_record (change detection)

Total: ~68 tests
"""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.competitor",
    "models.competitor_product",
    "models.competitor_price_history",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest


# Replace mocked CompetitorPriceHistory with a real class that stores kwargs
class _FakePriceHistory:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


sys.modules["models.competitor_price_history"].CompetitorPriceHistory = _FakePriceHistory

from services.competitor_scraper import (
    CompetitorScraperService,
    ScrapeResult,
)

SERVICE_PATH = "services.competitor_scraper"


# ============================================================
# Helpers
# ============================================================


def make_competitor_product(
    url="https://example.com/product",
    current_price=Decimal("39.99"),
    price_available=True,
):
    cp = MagicMock()
    cp.id = uuid4()
    cp.competitor_product_url = url
    cp.current_price = current_price
    cp.price_available = price_available
    return cp


def make_competitor(scraping_config=None):
    c = MagicMock()
    c.scraping_config = scraping_config or {}
    return c


# ============================================================
# 1. ScrapeResult dataclass
# ============================================================


class TestScrapeResult:
    def test_defaults(self):
        r = ScrapeResult(success=True)
        assert r.price is None
        assert r.currency == "USD"
        assert r.is_available is True
        assert r.error is None
        assert r.scraped_at is not None

    def test_success_with_price(self):
        r = ScrapeResult(success=True, price=Decimal("29.99"))
        assert r.success is True
        assert r.price == Decimal("29.99")

    def test_failure_with_error(self):
        r = ScrapeResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_scraped_at_auto_set(self):
        before = datetime.now(UTC)
        r = ScrapeResult(success=True)
        assert r.scraped_at >= before


# ============================================================
# 2. Initialization & Constants
# ============================================================


class TestCompetitorScraperServiceInit:
    def test_default_params(self):
        svc = CompetitorScraperService()
        assert svc.timeout == 30.0
        assert svc.max_retries == 3
        assert svc.respect_robots is True

    def test_custom_params(self):
        svc = CompetitorScraperService(timeout=10.0, max_retries=1, respect_robots=False)
        assert svc.timeout == 10.0
        assert svc.max_retries == 1
        assert svc.respect_robots is False

    def test_price_validation_constants(self):
        assert CompetitorScraperService.MAX_PRICE_INCREASE_RATIO == Decimal("5.0")
        assert CompetitorScraperService.MIN_PRICE_DECREASE_RATIO == Decimal("0.1")
        assert CompetitorScraperService.MAX_COMPETITOR_VS_OUR_PRICE_RATIO == Decimal("20.0")

    def test_has_price_patterns(self):
        assert len(CompetitorScraperService.PRICE_PATTERNS) >= 4

    def test_has_default_headers(self):
        assert "User-Agent" in CompetitorScraperService.DEFAULT_HEADERS


# ============================================================
# 3. _parse_price
# ============================================================


class TestParsePrice:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def test_dollar_sign(self):
        assert self.svc._parse_price("$29.99") == Decimal("29.99")

    def test_dollar_with_commas(self):
        assert self.svc._parse_price("$1,234.56") == Decimal("1234.56")

    def test_usd_suffix(self):
        assert self.svc._parse_price("29.99 USD") == Decimal("29.99")

    def test_usd_prefix(self):
        assert self.svc._parse_price("USD 29.99") == Decimal("29.99")

    def test_plain_number(self):
        assert self.svc._parse_price("29.99") == Decimal("29.99")

    def test_empty_string(self):
        assert self.svc._parse_price("") is None

    def test_none_returns_none(self):
        assert self.svc._parse_price(None) is None

    def test_no_match(self):
        assert self.svc._parse_price("no price here") is None

    def test_large_price(self):
        assert self.svc._parse_price("$12,345,678.90") == Decimal("12345678.90")

    def test_whole_number(self):
        assert self.svc._parse_price("$50") == Decimal("50")


# ============================================================
# 4. _validate_price (anomaly detection)
# ============================================================


class TestValidatePrice:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def test_valid_price(self):
        result = self.svc._validate_price(
            price=Decimal("42.00"),
            last_price=Decimal("39.99"),
        )
        assert result["valid"] is True

    def test_zero_price_rejected(self):
        result = self.svc._validate_price(price=Decimal("0"), last_price=None)
        assert result["valid"] is False
        assert "zero or negative" in result["reason"]

    def test_negative_price_rejected(self):
        result = self.svc._validate_price(price=Decimal("-5"), last_price=None)
        assert result["valid"] is False

    def test_massive_increase_rejected(self):
        # 53x increase (e.g., $39 → $2095)
        result = self.svc._validate_price(
            price=Decimal("2095"),
            last_price=Decimal("39.99"),
        )
        assert result["valid"] is False
        assert "Max allowed increase" in result["reason"]

    def test_within_increase_ratio_accepted(self):
        # 4x increase — within 5x limit
        result = self.svc._validate_price(
            price=Decimal("160"),
            last_price=Decimal("40"),
        )
        assert result["valid"] is True

    def test_at_max_increase_ratio_rejected(self):
        # Exactly 5x — ratio > threshold
        result = self.svc._validate_price(
            price=Decimal("200.01"),
            last_price=Decimal("40"),
        )
        assert result["valid"] is False

    def test_massive_decrease_rejected(self):
        # 0.01x decrease (e.g., $39 → $0.39)
        result = self.svc._validate_price(
            price=Decimal("0.39"),
            last_price=Decimal("39.99"),
        )
        assert result["valid"] is False
        assert "Min allowed" in result["reason"]

    def test_within_decrease_ratio_accepted(self):
        # 0.5x decrease — within 0.1x limit
        result = self.svc._validate_price(
            price=Decimal("20"),
            last_price=Decimal("40"),
        )
        assert result["valid"] is True

    def test_no_last_price_skips_ratio_check(self):
        result = self.svc._validate_price(
            price=Decimal("9999"),
            last_price=None,
        )
        assert result["valid"] is True

    def test_zero_last_price_skips_ratio_check(self):
        result = self.svc._validate_price(
            price=Decimal("50"),
            last_price=Decimal("0"),
        )
        assert result["valid"] is True

    def test_competitor_vs_our_price_rejected(self):
        # 25x our price
        result = self.svc._validate_price(
            price=Decimal("500"),
            last_price=None,
            our_product_price=Decimal("20"),
        )
        assert result["valid"] is False
        assert "scraping error" in result["reason"]

    def test_competitor_vs_our_price_within_ratio(self):
        # 5x our price — within 20x limit
        result = self.svc._validate_price(
            price=Decimal("100"),
            last_price=None,
            our_product_price=Decimal("20"),
        )
        assert result["valid"] is True

    def test_no_our_price_skips_check(self):
        result = self.svc._validate_price(
            price=Decimal("9999"),
            last_price=None,
            our_product_price=None,
        )
        assert result["valid"] is True

    def test_first_scrape_valid(self):
        """First scrape with no last price or our price."""
        result = self.svc._validate_price(
            price=Decimal("49.99"),
            last_price=None,
            our_product_price=None,
        )
        assert result["valid"] is True


# ============================================================
# 5. _check_availability
# ============================================================


class TestCheckAvailability:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def _make_soup(self, html):
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser")

    def test_available_by_default(self):
        soup = self._make_soup("<html><body><p>Buy now!</p></body></html>")
        assert self.svc._check_availability(soup, {}) is True

    def test_out_of_stock_text(self):
        soup = self._make_soup("<html><body><p>This item is out of stock</p></body></html>")
        assert self.svc._check_availability(soup, {}) is False

    def test_sold_out_text(self):
        soup = self._make_soup("<html><body><p>Sold Out</p></body></html>")
        assert self.svc._check_availability(soup, {}) is False

    def test_custom_oos_selector(self):
        soup = self._make_soup('<html><body><div class="oos-banner">Unavailable</div></body></html>')
        config = {"out_of_stock_selector": ".oos-banner"}
        assert self.svc._check_availability(soup, config) is False

    def test_currently_unavailable(self):
        soup = self._make_soup("<html><body><p>Currently unavailable</p></body></html>")
        assert self.svc._check_availability(soup, {}) is False


# ============================================================
# 6. _extract_from_meta
# ============================================================


class TestExtractFromMeta:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def _make_soup(self, html):
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser")

    def test_og_price(self):
        soup = self._make_soup('<html><head><meta property="og:price:amount" content="29.99"></head></html>')
        price, raw = self.svc._extract_from_meta(soup)
        assert price == Decimal("29.99")

    def test_product_price(self):
        soup = self._make_soup('<html><head><meta property="product:price:amount" content="49.99"></head></html>')
        price, raw = self.svc._extract_from_meta(soup)
        assert price == Decimal("49.99")

    def test_no_meta_returns_none(self):
        soup = self._make_soup("<html><head></head></html>")
        price, raw = self.svc._extract_from_meta(soup)
        assert price is None


# ============================================================
# 7. _extract_from_json_ld
# ============================================================


class TestExtractFromJsonLd:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def _make_soup(self, json_ld):
        from bs4 import BeautifulSoup

        html = f'<html><head><script type="application/ld+json">{json_ld}</script></head></html>'
        return BeautifulSoup(html, "html.parser")

    def test_single_offer(self):
        soup = self._make_soup('{"@type": "Product", "offers": {"price": "29.99"}}')
        price, raw = self.svc._extract_from_json_ld(soup)
        assert price == Decimal("29.99")

    def test_multiple_offers_takes_lowest(self):
        soup = self._make_soup(
            '{"@type": "Product", "offers": [{"price": "49.99"}, {"price": "29.99"}, {"price": "39.99"}]}'
        )
        price, raw = self.svc._extract_from_json_ld(soup)
        assert price == Decimal("29.99")

    def test_no_product_type(self):
        soup = self._make_soup('{"@type": "Organization", "name": "Test"}')
        price, raw = self.svc._extract_from_json_ld(soup)
        assert price is None

    def test_invalid_json(self):
        from bs4 import BeautifulSoup

        html = '<html><head><script type="application/ld+json">{invalid json}</script></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        price, raw = self.svc._extract_from_json_ld(soup)
        assert price is None

    def test_array_wrapper(self):
        soup = self._make_soup('[{"@type": "Product", "offers": {"price": "19.99"}}]')
        price, raw = self.svc._extract_from_json_ld(soup)
        assert price == Decimal("19.99")


# ============================================================
# 8. _extract_price (orchestration)
# ============================================================


class TestExtractPrice:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    @pytest.mark.asyncio
    async def test_css_selector_first(self):
        from bs4 import BeautifulSoup

        html = '<html><body><span class="my-price">$42.00</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        config = {"price_selector": ".my-price"}
        price, raw = await self.svc._extract_price(soup, config)
        assert price == Decimal("42.00")

    @pytest.mark.asyncio
    async def test_falls_through_to_json_ld(self):
        from bs4 import BeautifulSoup

        html = '<html><head><script type="application/ld+json">{"@type": "Product", "offers": {"price": "33.00"}}</script></head><body></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        price, raw = await self.svc._extract_price(soup, {})
        assert price == Decimal("33.00")

    @pytest.mark.asyncio
    async def test_falls_through_to_meta(self):
        from bs4 import BeautifulSoup

        html = '<html><head><meta property="og:price:amount" content="55.00"></head><body></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        price, raw = await self.svc._extract_price(soup, {})
        assert price == Decimal("55.00")

    @pytest.mark.asyncio
    async def test_common_selector_fallback(self):
        from bs4 import BeautifulSoup

        html = '<html><body><span class="price">$19.99</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        price, raw = await self.svc._extract_price(soup, {})
        assert price == Decimal("19.99")

    @pytest.mark.asyncio
    async def test_data_price_attribute(self):
        from bs4 import BeautifulSoup

        html = '<html><body><span data-price="24.99">some text</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        price, raw = await self.svc._extract_price(soup, {})
        assert price == Decimal("24.99")

    @pytest.mark.asyncio
    async def test_no_price_found(self):
        from bs4 import BeautifulSoup

        html = "<html><body><p>No prices here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        price, raw = await self.svc._extract_price(soup, {})
        assert price is None


# ============================================================
# 9. scrape_price (full orchestration)
# ============================================================


class TestScrapePrice:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    @pytest.mark.asyncio
    async def test_successful_scrape(self):
        cp = make_competitor_product()
        comp = make_competitor()

        self.svc._fetch_page = AsyncMock(return_value='<html><body><span class="price">$45.00</span></body></html>')
        result = await self.svc.scrape_price(cp, comp)
        assert result.success is True
        assert result.price == Decimal("45.00")

    @pytest.mark.asyncio
    async def test_fetch_failure(self):
        cp = make_competitor_product()
        comp = make_competitor()
        self.svc._fetch_page = AsyncMock(return_value=None)

        result = await self.svc.scrape_price(cp, comp)
        assert result.success is False
        assert "Failed to fetch" in result.error

    @pytest.mark.asyncio
    async def test_no_price_extracted(self):
        cp = make_competitor_product()
        comp = make_competitor()
        self.svc._fetch_page = AsyncMock(return_value="<html><body><p>No price</p></body></html>")

        result = await self.svc.scrape_price(cp, comp)
        assert result.success is False
        assert "Could not extract" in result.error

    @pytest.mark.asyncio
    async def test_anomaly_rejected(self):
        cp = make_competitor_product(current_price=Decimal("39.99"))
        comp = make_competitor()
        # Price that's 50x the last known — triggers anomaly
        self.svc._fetch_page = AsyncMock(return_value='<html><body><span class="price">$2000.00</span></body></html>')

        result = await self.svc.scrape_price(cp, comp)
        assert result.success is False
        assert "anomaly" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        import httpx

        cp = make_competitor_product()
        comp = make_competitor()
        self.svc._fetch_page = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await self.svc.scrape_price(cp, comp)
        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_error(self):
        import httpx

        cp = make_competitor_product()
        comp = make_competitor()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        self.svc._fetch_page = AsyncMock(
            side_effect=httpx.HTTPStatusError("forbidden", request=MagicMock(), response=mock_resp)
        )

        result = await self.svc.scrape_price(cp, comp)
        assert result.success is False
        assert "403" in result.error


# ============================================================
# 10. create_price_history_record
# ============================================================


class TestCreatePriceHistoryRecord:
    def setup_method(self):
        self.svc = CompetitorScraperService()

    def test_failed_scrape_returns_none(self):
        cp = make_competitor_product()
        sr = ScrapeResult(success=False, error="timeout")
        assert self.svc.create_price_history_record(cp, sr) is None

    def test_no_price_returns_none(self):
        cp = make_competitor_product()
        sr = ScrapeResult(success=True, price=None)
        assert self.svc.create_price_history_record(cp, sr) is None

    def test_same_price_returns_none(self):
        cp = make_competitor_product(current_price=Decimal("39.99"))
        sr = ScrapeResult(success=True, price=Decimal("39.99"))
        assert self.svc.create_price_history_record(cp, sr) is None

    def test_within_tolerance_returns_none(self):
        cp = make_competitor_product(current_price=Decimal("39.99"))
        sr = ScrapeResult(success=True, price=Decimal("39.995"))
        assert self.svc.create_price_history_record(cp, sr) is None

    def test_increase_detected(self):
        cp = make_competitor_product(current_price=Decimal("39.99"))
        sr = ScrapeResult(success=True, price=Decimal("44.99"))
        record = self.svc.create_price_history_record(cp, sr)
        assert record is not None
        assert record.change_type == "increase"
        assert record.new_price == Decimal("44.99")

    def test_decrease_detected(self):
        cp = make_competitor_product(current_price=Decimal("39.99"))
        sr = ScrapeResult(success=True, price=Decimal("35.99"))
        record = self.svc.create_price_history_record(cp, sr)
        assert record is not None
        assert record.change_type == "decrease"

    def test_promotion_detected_over_10_percent_drop(self):
        cp = make_competitor_product(current_price=Decimal("100.00"))
        sr = ScrapeResult(success=True, price=Decimal("85.00"))
        record = self.svc.create_price_history_record(cp, sr)
        assert record is not None
        assert record.change_type == "promotion"
        assert record.detected_promotion is True

    def test_initial_price(self):
        cp = make_competitor_product(current_price=None)
        sr = ScrapeResult(success=True, price=Decimal("29.99"))
        record = self.svc.create_price_history_record(cp, sr)
        assert record is not None
        assert record.change_type == "initial"
        assert record.change_amount is None
        assert record.change_percent is None

    def test_restock_detected(self):
        cp = make_competitor_product(current_price=Decimal("39.99"), price_available=False)
        sr = ScrapeResult(success=True, price=Decimal("42.00"), is_available=True)
        record = self.svc.create_price_history_record(cp, sr)
        assert record is not None
        assert record.change_type == "restock"

    def test_change_percent_calculated(self):
        cp = make_competitor_product(current_price=Decimal("100.00"))
        sr = ScrapeResult(success=True, price=Decimal("110.00"))
        record = self.svc.create_price_history_record(cp, sr)
        assert record.change_percent == Decimal("10.00")

    def test_record_has_correct_metadata(self):
        cp = make_competitor_product(current_price=Decimal("50.00"))
        sr = ScrapeResult(success=True, price=Decimal("55.00"), currency="EUR")
        record = self.svc.create_price_history_record(cp, sr)
        assert record.currency == "EUR"
        assert record.scrape_method == "http"
        assert record.competitor_product_id == cp.id
