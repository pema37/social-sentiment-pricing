"""
Tests for services.integration.shopify_service

Updated 2026-02-16: Migrated from REST to GraphQL response formats.
- _parse_product → _parse_graphql_product (GraphQL node format)
- _extract_next_cursor removed (GraphQL uses cursor-based pageInfo)
- Mock data uses edges/nodes/GID format
"""

import sys
import types
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

_needed = [
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "core",
    "core.config",
    "services.integration.base",
    "services.integration.schemas",
    "services.integration.retry",
    "services.integration.http_client",
    "services.integration.circuit_breaker",
]

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("core.config", "settings"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.schemas", "OAuthResult"),
    ("services.integration.schemas", "ExternalProduct"),
    ("services.integration.schemas", "ExternalProductVariant"),
    ("services.integration.schemas", "ProductSyncResult"),
    ("services.integration.schemas", "PriceUpdateRequest"),
    ("services.integration.schemas", "PriceUpdateResponse"),
    ("services.integration.schemas", "PriceUpdateResult"),
    ("services.integration.schemas", "WebhookRegistration"),
    ("services.integration.schemas", "ConnectionStatus"),
    ("services.integration.retry", "RetryConfig"),
    ("services.integration.retry", "execute_with_retry"),
    ("services.integration.http_client", "RetryableClient"),
    ("services.integration.circuit_breaker", "CircuitOpenError"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)

# Provide settings
_settings = MagicMock()
_settings.SHOPIFY_CLIENT_ID = "test-client-id"
_settings.SHOPIFY_CLIENT_SECRET = "test-client-secret"
sys.modules["core.config"].settings = _settings


# Provide base class
class _FakeEcommerceService:
    def __init__(self, retry_config=None):
        self.retry_config = retry_config

    @staticmethod
    def normalize_store_url(url):
        return url.rstrip("/")


sys.modules["services.integration.base"].EcommerceService = _FakeEcommerceService


# Provide schema classes
class _FakeExternalProduct:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeExternalProductVariant:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeProductSyncResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeOAuthResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakePriceUpdateResult:
    SUCCESS = "success"
    FAILED = "failed"
    UNAUTHORIZED = "unauthorized"
    PRODUCT_NOT_FOUND = "product_not_found"
    RATE_LIMITED = "rate_limited"


class _FakePriceUpdateResponse:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeWebhookRegistration:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeConnectionStatus:
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"


class _FakePriceUpdateRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_schemas = sys.modules["services.integration.schemas"]
_schemas.OAuthResult = _FakeOAuthResult
_schemas.ExternalProduct = _FakeExternalProduct
_schemas.ExternalProductVariant = _FakeExternalProductVariant
_schemas.ProductSyncResult = _FakeProductSyncResult
_schemas.PriceUpdateRequest = _FakePriceUpdateRequest
_schemas.PriceUpdateResponse = _FakePriceUpdateResponse
_schemas.PriceUpdateResult = _FakePriceUpdateResult
_schemas.WebhookRegistration = _FakeWebhookRegistration
_schemas.ConnectionStatus = _FakeConnectionStatus


# Provide retry
class _FakeRetryConfig:
    def __init__(self, **kw):
        self.max_retries = kw.get("max_retries", 3)
        self.base_delay = kw.get("base_delay", 1.0)
        self.max_delay = kw.get("max_delay", 30.0)


sys.modules["services.integration.retry"].RetryConfig = _FakeRetryConfig
sys.modules["services.integration.retry"].execute_with_retry = AsyncMock()


# Provide RetryableClient as a proper async context manager mock
class _FakeRetryableClient:
    """Mock RetryableClient that supports async with and has .post()"""

    def __init__(self, *args, **kwargs):
        self.post = AsyncMock()
        self.get = AsyncMock()
        self.put = AsyncMock()
        self.delete = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


sys.modules["services.integration.http_client"].RetryableClient = _FakeRetryableClient
sys.modules["services.integration.circuit_breaker"].CircuitOpenError = type("CircuitOpenError", (Exception,), {})

# Force-clean any MagicMock pollution from earlier tests
for _clean in ["services.integration.shopify_service", "services.integration.woocommerce_service"]:
    if _clean in sys.modules and not isinstance(sys.modules[_clean], types.ModuleType):
        del sys.modules[_clean]

# --- import under test ---
from services.integration.shopify_service import ShopifyService

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]
# Restore overwritten attributes on pre-existing modules
for (_mod_key, _attr_name), _orig_val in _saved_attrs.items():
    if _mod_key in sys.modules:
        if _orig_val is _SENTINEL:
            try:
                delattr(sys.modules[_mod_key], _attr_name)
            except AttributeError:
                pass
        else:
            setattr(sys.modules[_mod_key], _attr_name, _orig_val)


# ═══════════════════════════════════════════════════════════════════════════
# Helper: Build GraphQL product node (replaces REST format)
# ═══════════════════════════════════════════════════════════════════════════


def _gql_product_node(
    product_id=123,
    title="Test Widget",
    body_html="<p>Nice</p>",
    product_type="Gadget",
    vendor="TestCo",
    tags=None,
    status="ACTIVE",
    variants=None,
    images=None,
    created_at="2024-01-15T10:30:00Z",
    updated_at="2024-01-16T10:30:00Z",
):
    """Build a GraphQL product node in Shopify's edges/node format."""
    if tags is None:
        tags = ["tag1", "tag2"]
    if variants is None:
        variants = [
            {
                "id": "gid://shopify/ProductVariant/456",
                "title": "Default",
                "price": "19.99",
                "sku": "W-001",
                "compareAtPrice": None,
                "inventoryQuantity": 10,
            }
        ]
    if images is None:
        images = [{"url": "https://img.jpg"}]

    return {
        "id": f"gid://shopify/Product/{product_id}",
        "title": title,
        "bodyHtml": body_html,
        "productType": product_type,
        "vendor": vendor,
        "tags": tags,
        "status": status,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "variants": {"edges": [{"node": v} for v in variants]},
        "images": {"edges": [{"node": img} for img in images]},
    }


def _gql_response(data: dict) -> dict:
    """Wrap data in a standard GraphQL response envelope."""
    return {"data": data}


def _mock_httpx_response(data, status_code=200):
    mock = MagicMock()  # NOT AsyncMock
    mock.json = MagicMock(return_value=data)  # sync, like real httpx
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_platform_name(self):
        svc = ShopifyService()
        assert svc.platform_name == "shopify"

    def test_api_version(self):
        assert ShopifyService.API_VERSION == "2025-10"

    def test_default_retry_config(self):
        svc = ShopifyService()
        assert svc.retry_config.max_retries == 3

    def test_custom_retry_config(self):
        cfg = _FakeRetryConfig(max_retries=5)
        svc = ShopifyService(retry_config=cfg)
        assert svc.retry_config.max_retries == 5

    def test_price_verification_tolerance(self):
        assert ShopifyService.PRICE_VERIFICATION_TOLERANCE == Decimal("0.02")


class TestGetShopDomain:
    def test_plain_name(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("myshop") == "myshop.myshopify.com"

    def test_full_domain(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("myshop.myshopify.com") == "myshop.myshopify.com"

    def test_with_https(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("https://myshop.myshopify.com") == "myshop.myshopify.com"

    def test_strips_trailing_slash(self):
        svc = ShopifyService()
        result = svc._get_shop_domain("https://myshop.myshopify.com/")
        assert not result.endswith("/")

    def test_custom_domain_preserved(self):
        svc = ShopifyService()
        result = svc._get_shop_domain("shop.example.com")
        # Has a dot, so should NOT append .myshopify.com
        assert result == "shop.example.com"


class TestAuthHeaders:
    def test_contains_access_token(self):
        svc = ShopifyService()
        headers = svc._auth_headers("shpat_abc123")
        assert headers["X-Shopify-Access-Token"] == "shpat_abc123"

    def test_contains_content_type(self):
        svc = ShopifyService()
        headers = svc._auth_headers("token")
        assert headers["Content-Type"] == "application/json"


class TestGenerateOauthUrl:
    def test_contains_client_id(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop.myshopify.com", "state123", "https://callback.com")
        assert "test-client-id" in url

    def test_contains_redirect_uri(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop", "state123", "https://callback.com")
        assert "callback.com" in url

    def test_contains_state(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop", "state123", "https://cb.com")
        assert "state123" in url


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_returns_failure(self):
        svc = ShopifyService()
        result = await svc.refresh_access_token("url", "token")
        assert result.success is False
        assert "expire" in result.error.lower()


class TestGidHelpers:
    """Test the new GraphQL ID helper methods."""

    def test_gid_builds_product_id(self):
        assert ShopifyService._gid("Product", "123") == "gid://shopify/Product/123"

    def test_gid_builds_variant_id(self):
        assert ShopifyService._gid("ProductVariant", "456") == "gid://shopify/ProductVariant/456"

    def test_gid_builds_webhook_id(self):
        assert ShopifyService._gid("WebhookSubscription", "789") == "gid://shopify/WebhookSubscription/789"

    def test_numeric_id_extracts_from_gid(self):
        assert ShopifyService._numeric_id("gid://shopify/Product/123") == "123"

    def test_numeric_id_extracts_from_variant_gid(self):
        assert ShopifyService._numeric_id("gid://shopify/ProductVariant/456") == "456"

    def test_numeric_id_handles_empty(self):
        assert ShopifyService._numeric_id("") == ""

    def test_numeric_id_handles_none(self):
        assert ShopifyService._numeric_id(None) is None

    def test_numeric_id_passthrough_plain_number(self):
        # If already a plain number string, rsplit("/") returns the whole string
        assert ShopifyService._numeric_id("123") == "123"


class TestGraphqlUrl:
    def test_builds_correct_url(self):
        svc = ShopifyService()
        url = svc._graphql_url("myshop.myshopify.com")
        assert url == "https://myshop.myshopify.com/admin/api/2025-10/graphql.json"


class TestParseGraphqlProduct:
    """Tests for _parse_graphql_product (was _parse_product for REST)."""

    def test_basic_product(self):
        svc = ShopifyService()
        node = _gql_product_node()
        product = svc._parse_graphql_product(node)

        assert product.id == "123"
        assert product.title == "Test Widget"
        assert product.price == 19.99
        assert product.sku == "W-001"
        assert product.description == "<p>Nice</p>"
        assert product.product_type == "Gadget"
        assert product.vendor == "TestCo"
        assert len(product.tags) == 2
        assert "tag1" in product.tags
        assert "tag2" in product.tags
        assert len(product.images) == 1
        assert product.images[0] == "https://img.jpg"

    def test_no_variants(self):
        svc = ShopifyService()
        node = _gql_product_node(variants=[], images=[])
        product = svc._parse_graphql_product(node)

        assert product.price is None
        assert product.sku is None
        assert product.compare_at_price is None
        assert product.inventory_quantity is None

    def test_compare_at_price(self):
        svc = ShopifyService()
        node = _gql_product_node(
            variants=[
                {
                    "id": "gid://shopify/ProductVariant/2",
                    "title": "Default",
                    "price": "15.00",
                    "sku": "S-001",
                    "compareAtPrice": "20.00",
                    "inventoryQuantity": 5,
                }
            ],
            images=[],
        )
        product = svc._parse_graphql_product(node)
        assert product.compare_at_price == 20.00
        assert product.price == 15.00

    def test_extracts_numeric_id_from_gid(self):
        svc = ShopifyService()
        node = _gql_product_node(product_id=99887766)
        product = svc._parse_graphql_product(node)
        assert product.id == "99887766"

    def test_variant_ids_are_numeric(self):
        svc = ShopifyService()
        node = _gql_product_node(
            variants=[
                {
                    "id": "gid://shopify/ProductVariant/777",
                    "title": "Default",
                    "price": "10.00",
                    "sku": None,
                    "compareAtPrice": None,
                    "inventoryQuantity": 0,
                }
            ]
        )
        product = svc._parse_graphql_product(node)
        assert product.variants[0].id == "777"

    def test_multiple_variants(self):
        svc = ShopifyService()
        node = _gql_product_node(
            variants=[
                {
                    "id": "gid://shopify/ProductVariant/1",
                    "title": "Small",
                    "price": "10.00",
                    "sku": "SM",
                    "compareAtPrice": None,
                    "inventoryQuantity": 5,
                },
                {
                    "id": "gid://shopify/ProductVariant/2",
                    "title": "Large",
                    "price": "15.00",
                    "sku": "LG",
                    "compareAtPrice": "18.00",
                    "inventoryQuantity": 3,
                },
            ]
        )
        product = svc._parse_graphql_product(node)
        # Price/sku come from first variant
        assert product.price == 10.00
        assert product.sku == "SM"
        assert len(product.variants) == 2
        assert product.variants[1].price == 15.00

    def test_tags_as_list(self):
        """GraphQL returns tags as a list of strings."""
        svc = ShopifyService()
        node = _gql_product_node(tags=["summer", "sale", "new-arrival"])
        product = svc._parse_graphql_product(node)
        assert product.tags == ["summer", "sale", "new-arrival"]

    def test_tags_as_comma_string_fallback(self):
        """Handle edge case where tags might still be comma-separated."""
        svc = ShopifyService()
        node = _gql_product_node(tags="tag1, tag2, tag3")
        product = svc._parse_graphql_product(node)
        assert product.tags == ["tag1", "tag2", "tag3"]

    def test_multiple_images(self):
        svc = ShopifyService()
        node = _gql_product_node(
            images=[
                {"url": "https://img1.jpg"},
                {"url": "https://img2.jpg"},
                {"url": "https://img3.jpg"},
            ]
        )
        product = svc._parse_graphql_product(node)
        assert len(product.images) == 3
        assert product.images[0] == "https://img1.jpg"

    def test_empty_images(self):
        svc = ShopifyService()
        node = _gql_product_node(images=[])
        product = svc._parse_graphql_product(node)
        assert product.images == []

    def test_created_at_parsed(self):
        svc = ShopifyService()
        node = _gql_product_node(created_at="2024-06-15T08:00:00Z")
        product = svc._parse_graphql_product(node)
        assert isinstance(product.created_at, datetime)
        assert product.created_at.year == 2024
        assert product.created_at.month == 6

    def test_null_price_variant(self):
        svc = ShopifyService()
        node = _gql_product_node(
            variants=[
                {
                    "id": "gid://shopify/ProductVariant/1",
                    "title": "Default",
                    "price": None,
                    "sku": None,
                    "compareAtPrice": None,
                    "inventoryQuantity": None,
                }
            ]
        )
        product = svc._parse_graphql_product(node)
        assert product.price == 0  # Falls back to 0 when price is None


class TestParseDatetime:
    def test_valid_iso(self):
        svc = ShopifyService()
        result = svc._parse_datetime("2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_none_input(self):
        svc = ShopifyService()
        assert svc._parse_datetime(None) is None

    def test_invalid_string(self):
        svc = ShopifyService()
        assert svc._parse_datetime("not-a-date") is None

    def test_iso_with_timezone(self):
        svc = ShopifyService()
        result = svc._parse_datetime("2024-01-15T10:30:00+05:00")
        assert isinstance(result, datetime)

    def test_z_replaced_with_utc(self):
        svc = ShopifyService()
        result = svc._parse_datetime("2024-01-15T10:30:00Z")
        assert result.tzinfo is not None


class TestVerifyWebhookSignature:
    def test_valid_signature(self):
        import base64
        import hashlib
        import hmac as _hmac

        svc = ShopifyService()
        secret = "test-secret"
        payload = b'{"id": 123}'
        sig = base64.b64encode(_hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()

        assert svc.verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        svc = ShopifyService()
        assert svc.verify_webhook_signature(b"data", "bad-sig", "secret") is False


class TestWebhookTopics:
    """Verify GraphQL webhook topic mapping."""

    def test_gql_topics_match_rest_topics(self):
        assert len(ShopifyService.WEBHOOK_TOPICS_GQL) == len(ShopifyService.WEBHOOK_TOPICS)

    def test_gql_topics_are_screaming_snake(self):
        for topic in ShopifyService.WEBHOOK_TOPICS_GQL:
            assert topic == topic.upper()
            assert "/" not in topic

    def test_rest_topics_are_slash_format(self):
        for topic in ShopifyService.WEBHOOK_TOPICS:
            assert "/" in topic


class TestVerifyCredentials:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_service.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            # rc.post() returns a response with {"data": {"shop": {"name": "Test"}}}
            mock_rc.post.return_value = _mock_httpx_response({"data": {"shop": {"name": "Test Shop"}}})
            MockRC.return_value = mock_rc

            result = await svc.verify_credentials("myshop.myshopify.com", "token123")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_service.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.side_effect = ValueError("GraphQL error: Unauthorized")
            MockRC.return_value = mock_rc

            result = await svc.verify_credentials("myshop.myshopify.com", "bad-token")
            assert result is False


class TestFetchProducts:
    @pytest.mark.asyncio
    async def test_returns_products(self):
        svc = ShopifyService()
        node = _gql_product_node(product_id=100, title="Widget A")

        gql_data = {
            "data": {
                "products": {"edges": [{"node": node, "cursor": "cursor_abc"}], "pageInfo": {"hasNextPage": False}}
            }
        }

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            result = await svc.fetch_products("myshop.myshopify.com", "token")

        assert result.success is True
        assert len(result.products) == 1
        assert result.products[0].id == "100"
        assert result.products[0].title == "Widget A"
        assert result.has_more is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    async def test_pagination_cursor(self):
        svc = ShopifyService()
        node = _gql_product_node(product_id=200)

        gql_data = {
            "data": {"products": {"edges": [{"node": node, "cursor": "cursor_xyz"}], "pageInfo": {"hasNextPage": True}}}
        }

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            result = await svc.fetch_products("myshop.myshopify.com", "token")

        assert result.has_more is True
        assert result.next_cursor == "cursor_xyz"

    @pytest.mark.asyncio
    async def test_empty_store(self):
        svc = ShopifyService()

        gql_data = {"data": {"products": {"edges": [], "pageInfo": {"hasNextPage": False}}}}

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            result = await svc.fetch_products("myshop.myshopify.com", "token")

        assert result.success is True
        assert len(result.products) == 0
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_graphql_error_returns_failure(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response({"errors": [{"message": "Throttled"}]})
            MockRC.return_value = mock_rc

            result = await svc.fetch_products("myshop.myshopify.com", "token")

        assert result.success is False
        assert "Throttled" in result.error


class TestFetchSingleProduct:
    @pytest.mark.asyncio
    async def test_returns_product(self):
        svc = ShopifyService()
        node = _gql_product_node(product_id=555, title="Single Item")

        gql_data = {"data": {"product": node}}

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            product = await svc.fetch_single_product("myshop.myshopify.com", "token", "555")

        assert product is not None
        assert product.id == "555"
        assert product.title == "Single Item"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        svc = ShopifyService()

        gql_data = {"data": {"product": None}}

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            product = await svc.fetch_single_product("myshop.myshopify.com", "token", "999")

        assert product is None

    @pytest.mark.asyncio
    async def test_sends_gid_format(self):
        """Verify the query uses gid://shopify/Product/123 format."""
        svc = ShopifyService()

        gql_data = {"data": {"product": _gql_product_node(product_id=123)}}

        with patch("services.integration.shopify_products.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(gql_data)
            MockRC.return_value = mock_rc

            await svc.fetch_single_product("myshop.myshopify.com", "token", "123")

            # Check that the variables passed to rc.post() contain the GID
            call_kwargs = mock_rc.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
            assert payload.get("variables", {}).get("id") == "gid://shopify/Product/123"


class TestFetchProductSalesData:
    """Tests for ShopifyOrdersMixin.fetch_product_sales_data (GraphQL 2025-10)."""

    def _orders_response(self, line_items, has_next=False, cursor="cur1"):
        """Build a minimal GraphQL orders response for one order."""
        return {
            "data": {
                "orders": {
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Order/1",
                                "lineItems": {
                                    "edges": [
                                        {"node": li}
                                        for li in line_items
                                    ]
                                },
                            },
                            "cursor": cursor,
                        }
                    ],
                    "pageInfo": {"hasNextPage": has_next},
                }
            }
        }

    @pytest.mark.asyncio
    async def test_aggregates_revenue_and_units(self):
        svc = ShopifyService()
        product_gid = "gid://shopify/Product/42"

        li = {
            "product": {"id": product_gid},
            "quantity": 3,
            "originalTotalSet": {"shopMoney": {"amount": "59.97"}},
        }

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(self._orders_response([li]))
            MockRC.return_value = mock_rc

            result = await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

        assert result is not None
        assert result["units"] == 3
        assert result["revenue"] == Decimal("59.97")

    @pytest.mark.asyncio
    async def test_skips_line_items_for_other_products(self):
        svc = ShopifyService()

        li_match = {
            "product": {"id": "gid://shopify/Product/42"},
            "quantity": 2,
            "originalTotalSet": {"shopMoney": {"amount": "20.00"}},
        }
        li_other = {
            "product": {"id": "gid://shopify/Product/99"},
            "quantity": 5,
            "originalTotalSet": {"shopMoney": {"amount": "50.00"}},
        }

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(
                self._orders_response([li_match, li_other])
            )
            MockRC.return_value = mock_rc

            result = await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

        assert result["units"] == 2
        assert result["revenue"] == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_skips_line_items_with_no_product(self):
        svc = ShopifyService()

        li_no_product = {
            "product": None,
            "quantity": 1,
            "originalTotalSet": {"shopMoney": {"amount": "10.00"}},
        }

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(
                self._orders_response([li_no_product])
            )
            MockRC.return_value = mock_rc

            result = await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

        assert result["units"] == 0
        assert result["revenue"] == Decimal("0")

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.side_effect = ValueError("GraphQL error: Throttled")
            MockRC.return_value = mock_rc

            result = await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_date_filter_uses_created_at_syntax(self):
        """Verify GraphQL query uses created_at:>='...' AND created_at:<='...' format."""
        svc = ShopifyService()

        empty_resp = {
            "data": {
                "orders": {
                    "edges": [],
                    "pageInfo": {"hasNextPage": False},
                }
            }
        }

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(empty_resp)
            MockRC.return_value = mock_rc

            await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

            call_kwargs = mock_rc.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
            query_var = payload.get("variables", {}).get("query", "")
            assert "created_at:>=" in query_var
            assert "created_at:<=" in query_var
            assert "2025-01-01T00:00:00Z" in query_var

    @pytest.mark.asyncio
    async def test_zero_results_for_no_matching_orders(self):
        svc = ShopifyService()

        empty_resp = {
            "data": {
                "orders": {
                    "edges": [],
                    "pageInfo": {"hasNextPage": False},
                }
            }
        }

        with patch("services.integration.shopify_orders.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response(empty_resp)
            MockRC.return_value = mock_rc

            result = await svc.fetch_product_sales_data(
                "myshop.myshopify.com", "token", "42",
                "2025-01-01T00:00:00Z", "2025-01-31T23:59:59Z",
            )

        assert result is not None
        assert result["units"] == 0
        assert result["revenue"] == Decimal("0")


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_service.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.return_value = _mock_httpx_response({"data": {"shop": {"name": "Test"}}})
            MockRC.return_value = mock_rc

            status = await svc.health_check("myshop.myshopify.com", "token")
            assert status == _FakeConnectionStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_unhealthy_on_value_error(self):
        svc = ShopifyService()

        with patch("services.integration.shopify_service.RetryableClient") as MockRC:
            mock_rc = _FakeRetryableClient()
            mock_rc.post.side_effect = ValueError("GraphQL error")
            MockRC.return_value = mock_rc

            status = await svc.health_check("myshop.myshopify.com", "token")
            assert status == _FakeConnectionStatus.UNHEALTHY
