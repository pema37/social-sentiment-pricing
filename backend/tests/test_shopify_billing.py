"""
Unit tests for Shopify Billing schema configuration.

Covers SHOPIFY_PLANS structure/prices/trial/interval, ShopifySubscribeRequest
validation, and price alignment with TIER_LIMITS_STR.
"""

import sys
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Isolate SQLAlchemy/SQLModel so schemas.shopify_billing can be imported
# cleanly in environments that lack a live DB connection.
# ---------------------------------------------------------------------------

_MOCK_MODULES = [
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlmodel",
]

_originals: dict = {m: sys.modules.get(m) for m in _MOCK_MODULES}
for _m in _MOCK_MODULES:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Force fresh import of the schemas under test
for _mod in list(sys.modules.keys()):
    if _mod.startswith("schemas.shopify_billing") or _mod.startswith("models.subscription"):
        sys.modules.pop(_mod, None)

from schemas.shopify_billing import SHOPIFY_PLANS, ShopifySubscribeRequest  # noqa: E402

# Restore mocked modules
for _m in _MOCK_MODULES:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

# ---------------------------------------------------------------------------
# TIER_LIMITS_STR — import with real modules; fall back to known values if
# DB deps are unavailable (e.g. CI without PostgreSQL driver installed).
# ---------------------------------------------------------------------------

try:
    sys.modules.pop("models.subscription", None)
    from models.subscription import TIER_LIMITS_STR as _TIER_LIMITS_STR
except Exception:  # pragma: no cover
    _TIER_LIMITS_STR = {
        "free": {"price": "0.00"},
        "starter": {"price": "29.00"},
        "professional": {"price": "99.00"},
        "enterprise": {"price": "299.00"},
    }


# =============================================================================
# SHOPIFY_PLANS — structure and keys
# =============================================================================


class TestShopifyPlansKeys:
    def test_shopify_plans_keys(self):
        """Only starter and professional — enterprise must be absent."""
        assert set(SHOPIFY_PLANS.keys()) == {"starter", "professional"}

    def test_no_enterprise_key(self):
        assert "enterprise" not in SHOPIFY_PLANS

    def test_no_free_key(self):
        """Free tier has no Shopify charge and must not appear in SHOPIFY_PLANS."""
        assert "free" not in SHOPIFY_PLANS

    def test_plan_count(self):
        assert len(SHOPIFY_PLANS) == 2


# =============================================================================
# SHOPIFY_PLANS — prices
# =============================================================================


class TestShopifyPlanPrices:
    def test_shopify_plans_have_correct_prices(self):
        assert SHOPIFY_PLANS["starter"].price_amount == "29.00"
        assert SHOPIFY_PLANS["professional"].price_amount == "99.00"


# =============================================================================
# SHOPIFY_PLANS — trial days
# =============================================================================


class TestShopifyPlanTrialDays:
    def test_shopify_plans_have_trial_days(self):
        """All paid plans must offer a 14-day free trial."""
        for tier, plan in SHOPIFY_PLANS.items():
            assert plan.trial_days == 14, f"{tier} plan trial_days should be 14, got {plan.trial_days}"


# =============================================================================
# SHOPIFY_PLANS — billing interval
# =============================================================================


class TestShopifyPlanInterval:
    def test_shopify_plans_interval(self):
        """All plans must bill monthly (EVERY_30_DAYS)."""
        for tier, plan in SHOPIFY_PLANS.items():
            assert plan.interval == "EVERY_30_DAYS", (
                f"{tier} plan interval should be EVERY_30_DAYS, got {plan.interval}"
            )


# =============================================================================
# SHOPIFY_PLANS — currency
# =============================================================================


class TestShopifyPlanCurrency:
    def test_all_plans_usd(self):
        for tier, plan in SHOPIFY_PLANS.items():
            assert plan.currency_code == "USD", f"{tier} should be USD"


# =============================================================================
# ShopifySubscribeRequest — validation
# =============================================================================


class TestShopifySubscribeRequestValidTiers:
    def test_shopify_subscribe_request_valid_tiers(self):
        """starter and professional are valid tier values."""
        req_starter = ShopifySubscribeRequest(tier="starter", shop_domain=None)
        assert req_starter.tier == "starter"

        req_pro = ShopifySubscribeRequest(tier="professional", shop_domain=None)
        assert req_pro.tier == "professional"

    def test_starter_no_shop_domain(self):
        req = ShopifySubscribeRequest(tier="starter")
        assert req.shop_domain is None

    def test_professional_with_shop_domain(self):
        req = ShopifySubscribeRequest(tier="professional", shop_domain="mystore.myshopify.com")
        assert req.shop_domain == "mystore.myshopify.com"


class TestShopifySubscribeRequestRejectsEnterprise:
    def test_shopify_subscribe_request_rejects_enterprise(self):
        """enterprise is no longer a valid tier — Pydantic must reject it."""
        with pytest.raises(ValidationError):
            ShopifySubscribeRequest(tier="enterprise", shop_domain=None)

    def test_rejects_free_tier(self):
        """free has no Shopify charge and must not be accepted as a subscribe tier."""
        with pytest.raises(ValidationError):
            ShopifySubscribeRequest(tier="free", shop_domain=None)

    def test_rejects_unknown_tier(self):
        with pytest.raises(ValidationError):
            ShopifySubscribeRequest(tier="unknown", shop_domain=None)

    def test_rejects_empty_tier(self):
        with pytest.raises(ValidationError):
            ShopifySubscribeRequest(tier="", shop_domain=None)


# =============================================================================
# SHOPIFY_PLANS — price alignment with TIER_LIMITS_STR
# =============================================================================


class TestShopifyPlansAlignWithTierLimits:
    def test_shopify_plans_align_with_tier_limits(self):
        """SHOPIFY_PLANS prices must match TIER_LIMITS_STR so the two sources of truth never drift apart."""
        assert SHOPIFY_PLANS["starter"].price_amount == _TIER_LIMITS_STR["starter"]["price"]
        assert SHOPIFY_PLANS["professional"].price_amount == _TIER_LIMITS_STR["professional"]["price"]
