"""
Tests for services/integration/models.py

Enums and dataclasses for e-commerce integrations.
Pure data models — no async, no DB.
"""

from datetime import datetime, UTC
from dataclasses import fields

import pytest

from services.integration.schemas import (
    PriceUpdateResult,
    ConnectionStatus,
    OAuthResult,
    ExternalProductVariant,
    ExternalProduct,
    ProductSyncResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    WebhookRegistration,
)


# ──────────────────────────────────────────────
# PriceUpdateResult enum
# ──────────────────────────────────────────────
class TestPriceUpdateResult:

    def test_success_value(self):
        assert PriceUpdateResult.SUCCESS.value == "success"

    def test_failed_value(self):
        assert PriceUpdateResult.FAILED.value == "failed"

    def test_rate_limited_value(self):
        assert PriceUpdateResult.RATE_LIMITED.value == "rate_limited"

    def test_product_not_found_value(self):
        assert PriceUpdateResult.PRODUCT_NOT_FOUND.value == "product_not_found"

    def test_unauthorized_value(self):
        assert PriceUpdateResult.UNAUTHORIZED.value == "unauthorized"

    def test_member_count(self):
        assert len(PriceUpdateResult) == 5

    def test_is_str_enum(self):
        assert isinstance(PriceUpdateResult.SUCCESS, str)
        assert PriceUpdateResult.SUCCESS == "success"

    def test_unique_values(self):
        vals = [m.value for m in PriceUpdateResult]
        assert len(vals) == len(set(vals))

    def test_from_value(self):
        assert PriceUpdateResult("success") == PriceUpdateResult.SUCCESS

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PriceUpdateResult("nonexistent")


# ──────────────────────────────────────────────
# ConnectionStatus enum
# ──────────────────────────────────────────────
class TestConnectionStatus:

    def test_healthy_value(self):
        assert ConnectionStatus.HEALTHY.value == "healthy"

    def test_unhealthy_value(self):
        assert ConnectionStatus.UNHEALTHY.value == "unhealthy"

    def test_rate_limited_value(self):
        assert ConnectionStatus.RATE_LIMITED.value == "rate_limited"

    def test_unauthorized_value(self):
        assert ConnectionStatus.UNAUTHORIZED.value == "unauthorized"

    def test_member_count(self):
        assert len(ConnectionStatus) == 4

    def test_is_str_enum(self):
        assert isinstance(ConnectionStatus.HEALTHY, str)
        assert ConnectionStatus.HEALTHY == "healthy"

    def test_unique_values(self):
        vals = [m.value for m in ConnectionStatus]
        assert len(vals) == len(set(vals))

    def test_from_value(self):
        assert ConnectionStatus("unhealthy") == ConnectionStatus.UNHEALTHY


# ──────────────────────────────────────────────
# OAuthResult
# ──────────────────────────────────────────────
class TestOAuthResult:

    def test_required_field_success(self):
        r = OAuthResult(success=True)
        assert r.success is True

    def test_defaults(self):
        r = OAuthResult(success=False)
        assert r.access_token is None
        assert r.refresh_token is None
        assert r.expires_at is None
        assert r.scope is None
        assert r.error is None

    def test_full_construction(self):
        now = datetime.now(UTC)
        r = OAuthResult(
            success=True,
            access_token="tok-123",
            refresh_token="ref-456",
            expires_at=now,
            scope="read_products,write_products",
            error=None,
        )
        assert r.access_token == "tok-123"
        assert r.refresh_token == "ref-456"
        assert r.expires_at == now
        assert r.scope == "read_products,write_products"

    def test_error_case(self):
        r = OAuthResult(success=False, error="invalid_grant")
        assert r.success is False
        assert r.error == "invalid_grant"

    def test_field_count(self):
        assert len(fields(OAuthResult)) == 6


# ──────────────────────────────────────────────
# ExternalProductVariant
# ──────────────────────────────────────────────
class TestExternalProductVariant:

    def test_required_fields(self):
        v = ExternalProductVariant(id="v-1", title="Default")
        assert v.id == "v-1"
        assert v.title == "Default"

    def test_defaults(self):
        v = ExternalProductVariant(id="v-1", title="Default")
        assert v.price is None
        assert v.sku is None
        assert v.inventory_quantity is None
        assert v.compare_at_price is None

    def test_full_construction(self):
        v = ExternalProductVariant(
            id="v-1",
            title="Large",
            price=29.99,
            sku="SKU-001",
            inventory_quantity=50,
            compare_at_price=39.99,
        )
        assert v.price == 29.99
        assert v.sku == "SKU-001"
        assert v.inventory_quantity == 50
        assert v.compare_at_price == 39.99

    def test_field_count(self):
        assert len(fields(ExternalProductVariant)) == 6


# ──────────────────────────────────────────────
# ExternalProduct
# ──────────────────────────────────────────────
class TestExternalProduct:

    def test_required_fields(self):
        p = ExternalProduct(id="p-1", title="Widget")
        assert p.id == "p-1"
        assert p.title == "Widget"

    def test_defaults(self):
        p = ExternalProduct(id="p-1", title="Widget")
        assert p.price is None
        assert p.compare_at_price is None
        assert p.sku is None
        assert p.description is None
        assert p.inventory_quantity is None
        assert p.product_type is None
        assert p.vendor is None
        assert p.tags is None
        assert p.images is None
        assert p.variants is None
        assert p.created_at is None
        assert p.updated_at is None

    def test_full_construction(self):
        now = datetime.now(UTC)
        variant = ExternalProductVariant(id="v-1", title="Default")
        p = ExternalProduct(
            id="p-1",
            title="Widget",
            price=19.99,
            compare_at_price=24.99,
            sku="WDG-001",
            description="A fine widget",
            inventory_quantity=100,
            product_type="Electronics",
            vendor="WidgetCo",
            tags=["sale", "new"],
            images=["https://img.com/1.jpg"],
            variants=[variant],
            created_at=now,
            updated_at=now,
        )
        assert p.price == 19.99
        assert p.tags == ["sale", "new"]
        assert len(p.variants) == 1
        assert p.variants[0].id == "v-1"

    def test_field_count(self):
        assert len(fields(ExternalProduct)) == 14

    def test_empty_lists(self):
        p = ExternalProduct(id="p-1", title="Widget", tags=[], images=[], variants=[])
        assert p.tags == []
        assert p.images == []
        assert p.variants == []


# ──────────────────────────────────────────────
# ProductSyncResult
# ──────────────────────────────────────────────
class TestProductSyncResult:

    def test_required_field_success(self):
        r = ProductSyncResult(success=True)
        assert r.success is True

    def test_defaults(self):
        r = ProductSyncResult(success=True)
        assert r.products is None
        assert r.has_more is False
        assert r.next_cursor is None
        assert r.error is None
        assert r.retries_used == 0

    def test_with_products(self):
        prods = [ExternalProduct(id="p-1", title="A")]
        r = ProductSyncResult(
            success=True,
            products=prods,
            has_more=True,
            next_cursor="cursor-abc",
        )
        assert len(r.products) == 1
        assert r.has_more is True
        assert r.next_cursor == "cursor-abc"

    def test_error_case(self):
        r = ProductSyncResult(success=False, error="timeout")
        assert r.error == "timeout"
        assert r.retries_used == 0

    def test_retries_used(self):
        r = ProductSyncResult(success=True, retries_used=3)
        assert r.retries_used == 3

    def test_field_count(self):
        assert len(fields(ProductSyncResult)) == 6


# ──────────────────────────────────────────────
# PriceUpdateRequest
# ──────────────────────────────────────────────
class TestPriceUpdateRequest:

    def test_required_field(self):
        r = PriceUpdateRequest(external_product_id="p-1")
        assert r.external_product_id == "p-1"

    def test_defaults(self):
        r = PriceUpdateRequest(external_product_id="p-1")
        assert r.external_variant_id is None
        assert r.new_price == 0.0
        assert r.compare_at_price is None

    def test_full_construction(self):
        r = PriceUpdateRequest(
            external_product_id="p-1",
            external_variant_id="v-1",
            new_price=29.99,
            compare_at_price=39.99,
        )
        assert r.external_variant_id == "v-1"
        assert r.new_price == 29.99
        assert r.compare_at_price == 39.99

    def test_field_count(self):
        assert len(fields(PriceUpdateRequest)) == 4

    def test_zero_price(self):
        r = PriceUpdateRequest(external_product_id="p-1", new_price=0.0)
        assert r.new_price == 0.0


# ──────────────────────────────────────────────
# PriceUpdateResponse
# ──────────────────────────────────────────────
class TestPriceUpdateResponse:

    def test_required_fields(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.SUCCESS,
            external_product_id="p-1",
        )
        assert r.result == PriceUpdateResult.SUCCESS
        assert r.external_product_id == "p-1"

    def test_defaults(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.FAILED,
            external_product_id="p-1",
        )
        assert r.old_price is None
        assert r.new_price is None
        assert r.error is None
        assert r.retries_used == 0

    def test_full_construction(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.SUCCESS,
            external_product_id="p-1",
            old_price=19.99,
            new_price=24.99,
            error=None,
            retries_used=1,
        )
        assert r.old_price == 19.99
        assert r.new_price == 24.99
        assert r.retries_used == 1

    def test_error_case(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.PRODUCT_NOT_FOUND,
            external_product_id="p-1",
            error="Product not found",
        )
        assert r.result == PriceUpdateResult.PRODUCT_NOT_FOUND
        assert r.error == "Product not found"

    def test_rate_limited_case(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.RATE_LIMITED,
            external_product_id="p-1",
            retries_used=3,
        )
        assert r.result == PriceUpdateResult.RATE_LIMITED

    def test_field_count(self):
        assert len(fields(PriceUpdateResponse)) == 6

    def test_result_is_enum(self):
        r = PriceUpdateResponse(
            result=PriceUpdateResult.SUCCESS,
            external_product_id="p-1",
        )
        assert isinstance(r.result, PriceUpdateResult)


# ──────────────────────────────────────────────
# WebhookRegistration
# ──────────────────────────────────────────────
class TestWebhookRegistration:

    def test_required_field_success(self):
        w = WebhookRegistration(success=True)
        assert w.success is True

    def test_defaults(self):
        w = WebhookRegistration(success=True)
        assert w.webhook_id is None
        assert w.topic is None
        assert w.error is None

    def test_full_construction(self):
        w = WebhookRegistration(
            success=True,
            webhook_id="wh-123",
            topic="products/update",
            error=None,
        )
        assert w.webhook_id == "wh-123"
        assert w.topic == "products/update"

    def test_error_case(self):
        w = WebhookRegistration(
            success=False,
            error="Permission denied",
        )
        assert w.success is False
        assert w.error == "Permission denied"

    def test_field_count(self):
        assert len(fields(WebhookRegistration)) == 4


# ──────────────────────────────────────────────
# Cross-model integration
# ──────────────────────────────────────────────
class TestCrossModel:

    def test_product_with_variants(self):
        v1 = ExternalProductVariant(id="v-1", title="Small", price=10.0)
        v2 = ExternalProductVariant(id="v-2", title="Large", price=20.0)
        p = ExternalProduct(id="p-1", title="Shirt", variants=[v1, v2])
        assert len(p.variants) == 2
        assert p.variants[0].price == 10.0
        assert p.variants[1].price == 20.0

    def test_sync_result_with_products(self):
        p = ExternalProduct(id="p-1", title="Widget")
        r = ProductSyncResult(success=True, products=[p])
        assert r.products[0].title == "Widget"

    def test_price_update_flow(self):
        req = PriceUpdateRequest(
            external_product_id="p-1",
            new_price=29.99,
        )
        resp = PriceUpdateResponse(
            result=PriceUpdateResult.SUCCESS,
            external_product_id=req.external_product_id,
            old_price=19.99,
            new_price=req.new_price,
        )
        assert resp.external_product_id == req.external_product_id
        assert resp.new_price == req.new_price

    def test_enum_str_comparison(self):
        assert PriceUpdateResult.SUCCESS == "success"
        assert ConnectionStatus.HEALTHY == "healthy"

    def test_enum_in_string_formatting(self):
        status = ConnectionStatus.UNHEALTHY
        msg = f"Store is {status.value}"
        assert "unhealthy" in msg

        