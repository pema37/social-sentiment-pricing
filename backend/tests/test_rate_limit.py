"""
Tests for services/integration/rate_limit.py

Rate limit tracking — RateLimitState dataclass, RateLimitTracker, global instance.
Pure async logic, no DB dependencies.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from services.integration.rate_limit import (
    RateLimitState,
    RateLimitTracker,
    rate_limit_tracker,
)


# ──────────────────────────────────────────────
# RateLimitState — init / defaults
# ──────────────────────────────────────────────
class TestRateLimitStateInit:

    def test_defaults(self):
        s = RateLimitState()
        assert s.remaining is None
        assert s.limit is None
        assert s.reset_at is None
        assert s.is_limited is False
        assert s.last_request_at is None

    def test_custom_values(self):
        now = datetime.now(UTC)
        s = RateLimitState(
            remaining=10,
            limit=40,
            reset_at=now,
            is_limited=True,
            last_request_at=now,
        )
        assert s.remaining == 10
        assert s.limit == 40
        assert s.reset_at == now
        assert s.is_limited is True
        assert s.last_request_at == now

    def test_partial_override(self):
        s = RateLimitState(remaining=5)
        assert s.remaining == 5
        assert s.limit is None


# ──────────────────────────────────────────────
# RateLimitState — update_from_shopify_headers
# ──────────────────────────────────────────────
class TestUpdateFromShopifyHeaders:

    def test_parses_call_limit_header(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "10/40"
        })
        assert s.remaining == 30  # 40 - 10
        assert s.limit == 40
        assert s.is_limited is False

    def test_near_limit_marks_limited(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "38/40"
        })
        assert s.remaining == 2  # 40 - 38
        assert s.is_limited is True  # remaining <= 2

    def test_at_limit_marks_limited(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "39/40"
        })
        assert s.remaining == 1
        assert s.is_limited is True

    def test_exact_threshold_marks_limited(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "38/40"
        })
        assert s.remaining == 2
        assert s.is_limited is True  # <= 2

    def test_above_threshold_not_limited(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "37/40"
        })
        assert s.remaining == 3
        assert s.is_limited is False

    def test_sets_last_request_at(self):
        s = RateLimitState()
        assert s.last_request_at is None

        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "5/40"
        })
        assert s.last_request_at is not None
        assert isinstance(s.last_request_at, datetime)

    def test_missing_header_no_crash(self):
        s = RateLimitState()
        s.update_from_shopify_headers({})
        assert s.remaining is None
        assert s.limit is None
        assert s.last_request_at is not None  # still set

    def test_header_without_slash_ignored(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "noslash"
        })
        assert s.remaining is None
        assert s.limit is None

    def test_zero_current_calls(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "0/40"
        })
        assert s.remaining == 40
        assert s.limit == 40
        assert s.is_limited is False

    def test_full_limit_hit(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "40/40"
        })
        assert s.remaining == 0
        assert s.is_limited is True

    def test_updates_overwrite_previous(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "38/40"
        })
        assert s.is_limited is True

        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "5/40"
        })
        assert s.remaining == 35
        assert s.is_limited is False


# ──────────────────────────────────────────────
# RateLimitState — update_from_woocommerce_headers
# ──────────────────────────────────────────────
class TestUpdateFromWooCommerceHeaders:

    def test_sets_last_request_at(self):
        s = RateLimitState()
        s.update_from_woocommerce_headers({})
        assert s.last_request_at is not None

    def test_no_rate_limit_fields_set(self):
        s = RateLimitState()
        s.update_from_woocommerce_headers({"some-header": "value"})
        assert s.remaining is None
        assert s.limit is None
        assert s.is_limited is False


# ──────────────────────────────────────────────
# RateLimitState — mark_rate_limited
# ──────────────────────────────────────────────
class TestMarkRateLimited:

    def test_sets_is_limited(self):
        s = RateLimitState()
        s.mark_rate_limited()
        assert s.is_limited is True

    def test_with_retry_after_sets_reset_at(self):
        s = RateLimitState()
        s.mark_rate_limited(retry_after=30)
        assert s.is_limited is True
        assert s.reset_at is not None

    def test_without_retry_after_no_reset_at(self):
        s = RateLimitState()
        s.mark_rate_limited()
        assert s.reset_at is None

    def test_retry_after_zero(self):
        """retry_after=0 is falsy, so reset_at should not be set"""
        s = RateLimitState()
        s.mark_rate_limited(retry_after=0)
        assert s.is_limited is True
        assert s.reset_at is None  # 0 is falsy

    def test_retry_after_none(self):
        s = RateLimitState()
        s.mark_rate_limited(retry_after=None)
        assert s.reset_at is None


# ──────────────────────────────────────────────
# RateLimitState — should_wait
# ──────────────────────────────────────────────
class TestShouldWait:

    def test_not_limited_returns_false(self):
        s = RateLimitState()
        assert s.should_wait() is False

    def test_limited_no_reset_returns_true(self):
        s = RateLimitState(is_limited=True)
        assert s.should_wait() is True

    def test_limited_future_reset_returns_true(self):
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC) + timedelta(seconds=30),
        )
        assert s.should_wait() is True

    def test_limited_past_reset_returns_false_and_clears(self):
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC) - timedelta(seconds=10),
        )
        assert s.should_wait() is False
        assert s.is_limited is False  # auto-cleared

    def test_not_limited_with_reset_at_returns_false(self):
        s = RateLimitState(
            is_limited=False,
            reset_at=datetime.now(UTC) + timedelta(seconds=30),
        )
        assert s.should_wait() is False


# ──────────────────────────────────────────────
# RateLimitState — get_wait_time
# ──────────────────────────────────────────────
class TestGetWaitTime:

    def test_not_limited_returns_zero(self):
        s = RateLimitState()
        assert s.get_wait_time() == 0.0

    def test_limited_no_reset_returns_one(self):
        s = RateLimitState(is_limited=True)
        assert s.get_wait_time() == 1.0

    def test_limited_future_reset_returns_positive(self):
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC) + timedelta(seconds=10),
        )
        wait = s.get_wait_time()
        assert 9.0 <= wait <= 11.0  # allow clock drift

    def test_limited_past_reset_returns_zero(self):
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC) - timedelta(seconds=10),
        )
        assert s.get_wait_time() == 0.0

    def test_limited_reset_at_now_returns_near_zero(self):
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC),
        )
        assert s.get_wait_time() <= 0.1


# ──────────────────────────────────────────────
# RateLimitTracker — init
# ──────────────────────────────────────────────
class TestRateLimitTrackerInit:

    def test_empty_states(self):
        t = RateLimitTracker()
        assert t._states == {}

    def test_has_lock(self):
        t = RateLimitTracker()
        assert isinstance(t._lock, asyncio.Lock)


# ──────────────────────────────────────────────
# RateLimitTracker — get_state
# ──────────────────────────────────────────────
class TestGetState:

    @pytest.mark.asyncio
    async def test_creates_new_state(self):
        t = RateLimitTracker()
        state = await t.get_state("store-1")
        assert isinstance(state, RateLimitState)

    @pytest.mark.asyncio
    async def test_returns_same_instance(self):
        t = RateLimitTracker()
        s1 = await t.get_state("store-1")
        s2 = await t.get_state("store-1")
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_different_stores_different_states(self):
        t = RateLimitTracker()
        s1 = await t.get_state("store-1")
        s2 = await t.get_state("store-2")
        assert s1 is not s2


# ──────────────────────────────────────────────
# RateLimitTracker — update_from_response
# ──────────────────────────────────────────────
class TestUpdateFromResponse:

    @pytest.mark.asyncio
    async def test_shopify_update(self):
        t = RateLimitTracker()
        await t.update_from_response(
            "store-1",
            {"X-Shopify-Shop-Api-Call-Limit": "10/40"},
            platform="shopify",
        )
        state = await t.get_state("store-1")
        assert state.remaining == 30
        assert state.limit == 40

    @pytest.mark.asyncio
    async def test_woocommerce_update(self):
        t = RateLimitTracker()
        await t.update_from_response(
            "woo-store",
            {},
            platform="woocommerce",
        )
        state = await t.get_state("woo-store")
        assert state.last_request_at is not None

    @pytest.mark.asyncio
    async def test_default_platform_is_shopify(self):
        t = RateLimitTracker()
        await t.update_from_response(
            "store-1",
            {"X-Shopify-Shop-Api-Call-Limit": "5/40"},
        )
        state = await t.get_state("store-1")
        assert state.remaining == 35

    @pytest.mark.asyncio
    async def test_unknown_platform_no_crash(self):
        t = RateLimitTracker()
        # Unknown platform — should not update rate limit fields
        await t.update_from_response(
            "store-1",
            {"some": "header"},
            platform="bigcommerce",
        )
        state = await t.get_state("store-1")
        assert state.remaining is None


# ──────────────────────────────────────────────
# RateLimitTracker — mark_rate_limited
# ──────────────────────────────────────────────
class TestTrackerMarkRateLimited:

    @pytest.mark.asyncio
    async def test_marks_store_limited(self):
        t = RateLimitTracker()
        await t.mark_rate_limited("store-1")
        state = await t.get_state("store-1")
        assert state.is_limited is True

    @pytest.mark.asyncio
    async def test_with_retry_after(self):
        t = RateLimitTracker()
        await t.mark_rate_limited("store-1", retry_after=60)
        state = await t.get_state("store-1")
        assert state.is_limited is True
        assert state.reset_at is not None

    @pytest.mark.asyncio
    async def test_creates_state_if_needed(self):
        t = RateLimitTracker()
        await t.mark_rate_limited("new-store")
        assert "new-store" in t._states


# ──────────────────────────────────────────────
# RateLimitTracker — wait_if_needed
# ──────────────────────────────────────────────
class TestWaitIfNeeded:

    @pytest.mark.asyncio
    async def test_no_wait_when_not_limited(self):
        t = RateLimitTracker()
        wait = await t.wait_if_needed("store-1")
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_waits_when_limited_with_reset(self):
        t = RateLimitTracker()
        state = await t.get_state("store-1")
        state.is_limited = True
        state.reset_at = datetime.now(UTC) + timedelta(seconds=0.1)

        with patch("services.integration.rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            wait = await t.wait_if_needed("store-1")
            mock_sleep.assert_called_once()
            assert wait > 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_limited_but_past_reset(self):
        t = RateLimitTracker()
        state = await t.get_state("store-1")
        state.is_limited = True
        state.reset_at = datetime.now(UTC) - timedelta(seconds=10)

        wait = await t.wait_if_needed("store-1")
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_limited_no_reset_waits_default(self):
        t = RateLimitTracker()
        state = await t.get_state("store-1")
        state.is_limited = True
        # No reset_at, get_wait_time returns 1.0

        with patch("services.integration.rate_limit.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            wait = await t.wait_if_needed("store-1")
            mock_sleep.assert_called_once()
            assert wait == 1.0


# ──────────────────────────────────────────────
# RateLimitTracker — clear
# ──────────────────────────────────────────────
class TestClear:

    @pytest.mark.asyncio
    async def test_clears_state(self):
        t = RateLimitTracker()
        await t.get_state("store-1")
        assert "store-1" in t._states

        await t.clear("store-1")
        assert "store-1" not in t._states

    @pytest.mark.asyncio
    async def test_clear_nonexistent_no_error(self):
        t = RateLimitTracker()
        await t.clear("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_clear_one_keeps_others(self):
        t = RateLimitTracker()
        await t.get_state("store-1")
        await t.get_state("store-2")

        await t.clear("store-1")
        assert "store-1" not in t._states
        assert "store-2" in t._states


# ──────────────────────────────────────────────
# Global instance
# ──────────────────────────────────────────────
class TestGlobalInstance:

    def test_exists(self):
        assert rate_limit_tracker is not None

    def test_is_tracker(self):
        assert isinstance(rate_limit_tracker, RateLimitTracker)


# ──────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────
class TestEdgeCases:

    def test_shopify_header_large_numbers(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "999/1000"
        })
        assert s.remaining == 1
        assert s.limit == 1000
        assert s.is_limited is True

    def test_shopify_header_single_call(self):
        s = RateLimitState()
        s.update_from_shopify_headers({
            "X-Shopify-Shop-Api-Call-Limit": "1/40"
        })
        assert s.remaining == 39

    @pytest.mark.asyncio
    async def test_concurrent_state_access(self):
        """Multiple coroutines accessing the same store state"""
        t = RateLimitTracker()

        async def access_state(store: str):
            return await t.get_state(store)

        results = await asyncio.gather(
            access_state("store-1"),
            access_state("store-1"),
            access_state("store-1"),
        )

        # All should return the same instance
        assert results[0] is results[1]
        assert results[1] is results[2]

    def test_should_wait_then_get_wait_time_consistency(self):
        """If should_wait returns True, get_wait_time should return > 0"""
        s = RateLimitState(
            is_limited=True,
            reset_at=datetime.now(UTC) + timedelta(seconds=5),
        )
        assert s.should_wait() is True
        assert s.get_wait_time() > 0

    def test_should_wait_false_get_wait_time_zero(self):
        s = RateLimitState()
        assert s.should_wait() is False
        assert s.get_wait_time() == 0.0

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Simulate: normal → rate limited → wait → cleared"""
        t = RateLimitTracker()

        # 1. Normal requests
        await t.update_from_response(
            "shop-1",
            {"X-Shopify-Shop-Api-Call-Limit": "5/40"},
        )
        state = await t.get_state("shop-1")
        assert state.is_limited is False
        assert await t.wait_if_needed("shop-1") == 0.0

        # 2. Approaching limit
        await t.update_from_response(
            "shop-1",
            {"X-Shopify-Shop-Api-Call-Limit": "38/40"},
        )
        assert state.is_limited is True

        # 3. Hit 429 response
        await t.mark_rate_limited("shop-1", retry_after=1)

        # 4. Clear
        await t.clear("shop-1")
        assert "shop-1" not in t._states


        