# backend/tests/test_competitor_matching_google_custom.py
"""
Tests for competitor_matching/providers/google_custom.py

Covers:
- Provider properties (name, api_key, rate_limit, cost)
- is_available (api_key + search_engine_id)
- _parse_results / _parse_item
- _extract_image (cse_thumbnail, cse_image, og:image)
- _extract_rating (aggregaterating, product schema)
- _check_daily_reset
- get_usage_stats, get_remaining_free_searches
- cost_per_request (free vs paid tier)

Total: ~30 tests
"""

import sys
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch

for mod in ["db.session", "core.logging"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

import pytest

from services.competitor_matching.schemas import SearchProvider, ProviderResult
from services.competitor_matching.providers.google_custom import GoogleCustomSearchProvider


# ============================================================
# 1. Provider Properties
# ============================================================

class TestGoogleCustomProperties:

    def test_provider_name(self):
        p = GoogleCustomSearchProvider(api_key="key", search_engine_id="cx")
        assert p.provider_name == SearchProvider.GOOGLE_CUSTOM_SEARCH

    def test_requires_api_key(self):
        p = GoogleCustomSearchProvider()
        assert p.requires_api_key is True

    def test_rate_limit(self):
        p = GoogleCustomSearchProvider()
        assert p.rate_limit_per_minute == 60

    def test_daily_free_limit(self):
        p = GoogleCustomSearchProvider()
        assert p.daily_free_limit == 100

    def test_cost_free_tier(self):
        p = GoogleCustomSearchProvider()
        p._daily_requests = 50
        assert p.cost_per_request == 0.0

    def test_cost_paid_tier(self):
        p = GoogleCustomSearchProvider()
        p._daily_requests = 150
        assert p.cost_per_request == 0.005


# ============================================================
# 2. is_available
# ============================================================

class TestIsAvailable:

    def test_available_with_both_keys(self):
        p = GoogleCustomSearchProvider(api_key="key", search_engine_id="cx")
        assert p.is_available() is True

    def test_unavailable_no_api_key(self):
        p = GoogleCustomSearchProvider(api_key=None, search_engine_id="cx")
        assert p.is_available() is False

    def test_unavailable_no_search_engine_id(self):
        p = GoogleCustomSearchProvider(api_key="key", search_engine_id=None)
        assert p.is_available() is False

    def test_unavailable_both_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            p = GoogleCustomSearchProvider(api_key=None, search_engine_id=None)
            assert p.is_available() is False


# ============================================================
# 3. _extract_image
# ============================================================

class TestExtractImage:

    def setup_method(self):
        self.p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")

    def test_cse_thumbnail(self):
        item = {"pagemap": {"cse_thumbnail": [{"src": "https://img.com/thumb.jpg"}]}}
        assert self.p._extract_image(item) == "https://img.com/thumb.jpg"

    def test_cse_image(self):
        item = {"pagemap": {"cse_image": [{"src": "https://img.com/full.jpg"}]}}
        assert self.p._extract_image(item) == "https://img.com/full.jpg"

    def test_og_image(self):
        item = {"pagemap": {"metatags": [{"og:image": "https://img.com/og.jpg"}]}}
        assert self.p._extract_image(item) == "https://img.com/og.jpg"

    def test_no_pagemap(self):
        assert self.p._extract_image({}) is None

    def test_empty_pagemap(self):
        assert self.p._extract_image({"pagemap": {}}) is None

    def test_priority_order(self):
        # cse_thumbnail takes priority over cse_image
        item = {"pagemap": {
            "cse_thumbnail": [{"src": "https://thumb.jpg"}],
            "cse_image": [{"src": "https://full.jpg"}],
        }}
        assert self.p._extract_image(item) == "https://thumb.jpg"


# ============================================================
# 4. _extract_rating
# ============================================================

class TestExtractRating:

    def setup_method(self):
        self.p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")

    def test_aggregate_rating(self):
        item = {"pagemap": {"aggregaterating": [{"ratingvalue": "4.5"}]}}
        assert self.p._extract_rating(item) == 4.5

    def test_product_rating(self):
        item = {"pagemap": {"product": [{"ratingvalue": "3.8"}]}}
        assert self.p._extract_rating(item) == 3.8

    def test_no_rating(self):
        assert self.p._extract_rating({}) is None

    def test_invalid_rating_value(self):
        item = {"pagemap": {"aggregaterating": [{"ratingvalue": "not-a-number"}]}}
        assert self.p._extract_rating(item) is None


# ============================================================
# 5. _check_daily_reset
# ============================================================

class TestCheckDailyReset:

    def test_resets_on_new_day(self):
        p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")
        p._daily_requests = 50
        p._last_reset_date = "2020-01-01"
        p._check_daily_reset()
        assert p._daily_requests == 0
        assert p._last_reset_date == date.today().isoformat()

    def test_no_reset_same_day(self):
        p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")
        p._daily_requests = 50
        p._last_reset_date = date.today().isoformat()
        p._check_daily_reset()
        assert p._daily_requests == 50


# ============================================================
# 6. get_usage_stats / get_remaining_free_searches
# ============================================================

class TestUsageStats:

    def test_usage_stats(self):
        p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")
        p._daily_requests = 30
        p._last_reset_date = date.today().isoformat()
        stats = p.get_usage_stats()
        assert stats["daily_requests"] == 30
        assert stats["daily_limit"] == 100
        assert stats["remaining_free"] == 70

    def test_remaining_free_searches(self):
        p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")
        p._daily_requests = 90
        p._last_reset_date = date.today().isoformat()
        assert p.get_remaining_free_searches() == 10

    def test_remaining_never_negative(self):
        p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")
        p._daily_requests = 200
        p._last_reset_date = date.today().isoformat()
        assert p.get_remaining_free_searches() == 0


# ============================================================
# 7. _parse_results / _parse_item
# ============================================================

class TestParseResults:

    def setup_method(self):
        self.p = GoogleCustomSearchProvider(api_key="k", search_engine_id="cx")

    def test_empty_results(self):
        assert self.p._parse_results({}) == []
        assert self.p._parse_results({"items": []}) == []

    def test_valid_item(self):
        data = {"items": [{
            "title": "Widget Pro",
            "link": "https://www.amazon.com/widget-pro",
            "snippet": "Only $49.99 - Great widget",
        }]}
        products = self.p._parse_results(data)
        assert len(products) == 1
        assert products[0].merchant == "Amazon"

    def test_item_missing_title(self):
        data = {"items": [{"link": "https://amazon.com/test"}]}
        products = self.p._parse_results(data)
        assert len(products) == 0

    def test_item_missing_url(self):
        data = {"items": [{"title": "Widget"}]}
        products = self.p._parse_results(data)
        assert len(products) == 0


        