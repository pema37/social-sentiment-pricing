# backend/tests/test_competitor_matching_utils.py
"""
Tests for competitor_matching/utils.py — pure utility functions.

Covers:
- extract_domain, get_merchant_name, get_merchant_reliability, is_marketplace, is_skip_domain
- parse_price, extract_price_from_text, _is_valid_price
- calculate_text_similarity, calculate_keyword_match, _tokenize
- build_shopping_query, clean_product_title

Total: ~55 tests
"""

import sys
from decimal import Decimal
from unittest.mock import MagicMock

for mod in ["db.session", "core.logging"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

import pytest

from services.competitor_matching.utils import (
    extract_domain,
    get_merchant_name,
    get_merchant_reliability,
    is_marketplace,
    is_skip_domain,
    parse_price,
    extract_price_from_text,
    _is_valid_price,
    calculate_text_similarity,
    calculate_keyword_match,
    _tokenize,
    build_shopping_query,
    clean_product_title,
    KNOWN_MERCHANTS,
    SKIP_DOMAINS,
)


# ============================================================
# 1. extract_domain
# ============================================================

class TestExtractDomain:

    def test_simple_url(self):
        assert extract_domain("https://amazon.com/dp/B09V3KXJPB") == "amazon.com"

    def test_strips_www(self):
        assert extract_domain("https://www.amazon.com/product") == "amazon.com"

    def test_preserves_subdomain(self):
        assert extract_domain("http://shop.walmart.com/product/123") == "shop.walmart.com"

    def test_lowercases(self):
        assert extract_domain("https://WWW.Amazon.COM/path") == "amazon.com"

    def test_empty_url(self):
        assert extract_domain("") == ""

    def test_none_safe(self):
        # None should return empty or handle gracefully
        assert extract_domain(None) == ""

    def test_invalid_url(self):
        assert extract_domain("not-a-url") == ""


# ============================================================
# 2. get_merchant_name
# ============================================================

class TestGetMerchantName:

    def test_known_merchant(self):
        assert get_merchant_name("amazon.com") == "Amazon"

    def test_known_merchant_walmart(self):
        assert get_merchant_name("walmart.com") == "Walmart"

    def test_unknown_merchant_formatted(self):
        result = get_merchant_name("cool-gadgets.com")
        assert result == "Cool Gadgets"

    def test_empty_domain(self):
        assert get_merchant_name("") == "Unknown"


# ============================================================
# 3. get_merchant_reliability
# ============================================================

class TestGetMerchantReliability:

    def test_known_high_reliability(self):
        assert get_merchant_reliability("amazon.com") == 0.95

    def test_known_lower_reliability(self):
        assert get_merchant_reliability("wish.com") == 0.60

    def test_unknown_merchant(self):
        assert get_merchant_reliability("randomshop.com") == 0.5

    def test_empty_domain(self):
        assert get_merchant_reliability("") == 0.3


# ============================================================
# 4. is_marketplace
# ============================================================

class TestIsMarketplace:

    def test_marketplace_true(self):
        assert is_marketplace("amazon.com") is True
        assert is_marketplace("ebay.com") is True

    def test_marketplace_false(self):
        assert is_marketplace("walmart.com") is False
        assert is_marketplace("bestbuy.com") is False

    def test_unknown_merchant(self):
        assert is_marketplace("randomshop.com") is False


# ============================================================
# 5. is_skip_domain
# ============================================================

class TestIsSkipDomain:

    def test_search_engines(self):
        assert is_skip_domain("google.com") is True
        assert is_skip_domain("bing.com") is True

    def test_social_media(self):
        assert is_skip_domain("facebook.com") is True
        assert is_skip_domain("reddit.com") is True

    def test_valid_merchant(self):
        assert is_skip_domain("amazon.com") is False

    def test_unknown_domain(self):
        assert is_skip_domain("myshop.com") is False


# ============================================================
# 6. parse_price
# ============================================================

class TestParsePrice:

    def test_integer(self):
        assert parse_price(100) == Decimal("100")

    def test_float(self):
        assert parse_price(99.99) == Decimal("99.99")

    def test_string_dollar(self):
        assert parse_price("$1,234.56") == Decimal("1234.56")

    def test_string_plain(self):
        assert parse_price("49.99") == Decimal("49.99")

    def test_decimal_passthrough(self):
        assert parse_price(Decimal("29.99")) == Decimal("29.99")

    def test_none(self):
        assert parse_price(None) is None

    def test_invalid_string(self):
        assert parse_price("invalid") is None

    def test_zero_price_rejected(self):
        assert parse_price(0) is None

    def test_negative_price_rejected(self):
        assert parse_price(-10) is None

    def test_too_high_price_rejected(self):
        assert parse_price(200000) is None


# ============================================================
# 7. extract_price_from_text
# ============================================================

class TestExtractPriceFromText:

    def test_dollar_sign(self):
        assert extract_price_from_text("$49.99") == Decimal("49.99")

    def test_dollar_with_comma(self):
        assert extract_price_from_text("$1,299.00") == Decimal("1299.00")

    def test_dollar_with_space(self):
        assert extract_price_from_text("$ 29.99") == Decimal("29.99")

    def test_usd_suffix(self):
        assert extract_price_from_text("199.99 USD") == Decimal("199.99")

    def test_euro_format(self):
        result = extract_price_from_text("€1.234,56")
        assert result == Decimal("1234.56")

    def test_gbp(self):
        assert extract_price_from_text("£49.99") == Decimal("49.99")

    def test_price_label(self):
        assert extract_price_from_text("Price: $99.99") == Decimal("99.99")

    def test_empty_string(self):
        assert extract_price_from_text("") is None

    def test_none(self):
        assert extract_price_from_text(None) is None

    def test_no_price_found(self):
        assert extract_price_from_text("no price here") is None


# ============================================================
# 8. _is_valid_price
# ============================================================

class TestIsValidPrice:

    def test_valid_range(self):
        assert _is_valid_price(Decimal("0.01")) is True
        assert _is_valid_price(Decimal("100000")) is True
        assert _is_valid_price(Decimal("49.99")) is True

    def test_below_minimum(self):
        assert _is_valid_price(Decimal("0.00")) is False
        assert _is_valid_price(Decimal("-1")) is False

    def test_above_maximum(self):
        assert _is_valid_price(Decimal("100001")) is False


# ============================================================
# 9. calculate_text_similarity
# ============================================================

class TestCalculateTextSimilarity:

    def test_identical_texts(self):
        assert calculate_text_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert calculate_text_similarity("apple banana", "cherry grape") == 0.0

    def test_partial_overlap(self):
        result = calculate_text_similarity("apple banana cherry", "apple cherry grape")
        assert 0.0 < result < 1.0

    def test_empty_text1(self):
        assert calculate_text_similarity("", "hello") == 0.0

    def test_empty_text2(self):
        assert calculate_text_similarity("hello", "") == 0.0

    def test_case_insensitive(self):
        assert calculate_text_similarity("Hello World", "hello world") == 1.0


# ============================================================
# 10. calculate_keyword_match
# ============================================================

class TestCalculateKeywordMatch:

    def test_all_keywords_match(self):
        assert calculate_keyword_match("apple banana cherry", ["apple", "banana"]) == 1.0

    def test_no_keywords_match(self):
        assert calculate_keyword_match("apple banana", ["cherry", "grape"]) == 0.0

    def test_partial_match(self):
        assert calculate_keyword_match("apple banana", ["apple", "grape"]) == 0.5

    def test_empty_text(self):
        assert calculate_keyword_match("", ["apple"]) == 0.0

    def test_empty_keywords(self):
        assert calculate_keyword_match("apple", []) == 0.0

    def test_case_insensitive(self):
        assert calculate_keyword_match("Apple Banana", ["apple", "banana"]) == 1.0


# ============================================================
# 11. _tokenize
# ============================================================

class TestTokenize:

    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World 2024")
        assert "hello" in tokens
        assert "world" in tokens
        assert "2024" in tokens

    def test_removes_stop_words(self):
        tokens = _tokenize("the quick fox and the lazy dog")
        assert "the" not in tokens
        assert "and" not in tokens

    def test_removes_single_char(self):
        tokens = _tokenize("I am a test")
        # "I" and "a" are single chars, removed
        assert "am" in tokens
        assert "test" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []


# ============================================================
# 12. build_shopping_query
# ============================================================

class TestBuildShoppingQuery:

    def test_name_only(self):
        assert build_shopping_query("iPhone 15 Pro") == "iPhone 15 Pro"

    def test_with_keywords(self):
        result = build_shopping_query("iPhone 15", keywords=["case", "cover"])
        assert "iPhone 15" in result
        assert "case" in result
        assert "cover" in result

    def test_dedupes_keywords_in_name(self):
        result = build_shopping_query("iPhone 15 Pro", keywords=["iphone", "case"])
        assert result.count("iphone") <= 1 or "iphone" not in result.lower().split()
        assert "case" in result

    def test_max_3_extra_keywords(self):
        result = build_shopping_query("Widget", keywords=["a", "b", "c", "d", "e"])
        parts = result.split()
        # Widget + max 3 keywords = 4 parts max
        assert len(parts) <= 4

    def test_include_buy(self):
        result = build_shopping_query("Widget", include_buy=True)
        assert "buy" in result

    def test_strips_whitespace(self):
        result = build_shopping_query("  iPhone 15  ")
        assert result == "iPhone 15"


# ============================================================
# 13. clean_product_title
# ============================================================

class TestCleanProductTitle:

    def test_removes_free_shipping(self):
        assert "FREE SHIPPING" not in clean_product_title("Widget Pro FREE SHIPPING")

    def test_removes_sale(self):
        assert "SALE" not in clean_product_title("Widget Pro SALE Now")

    def test_removes_percent_off(self):
        assert "50% OFF" not in clean_product_title("Widget Pro 50% OFF")

    def test_removes_pipe_suffix(self):
        result = clean_product_title("Widget Pro | Best Deals Store")
        assert "|" not in result
        assert "Best Deals" not in result

    def test_empty_string(self):
        assert clean_product_title("") == ""

    def test_cleans_whitespace(self):
        result = clean_product_title("Widget   Pro    Max")
        assert "  " not in result


        