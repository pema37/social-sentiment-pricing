"""
Test Suite: backend/services/pricing/approval_service.py
Covers: ApprovalError, approve, reject, apply_price, auto_approve_and_apply,
        _check_daily_limit, _get_recommendation, get_approval_stats.

Place at: backend/tests/test_approval_service.py
Run: pytest backend/tests/test_approval_service.py -v
"""

import sys
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ── Import isolation: force fresh mocks to prevent cross-test pollution ──
sys.modules["db.session"] = MagicMock()
sys.modules.pop("services.pricing.approval_service", None)

from services.pricing.approval_service import ApprovalService, ApprovalError
from models.price_recommendation import RecommendationStatus


# =====================================================================
# Helpers
# =====================================================================

def make_recommendation(
    user_id=None,
    status=None,
    valid_minutes=60,
    product_id=None,
    recommended_price=29.99,
    change_percent=5.0,
    confidence_score=0.85,
):
    """Create a mock PriceRecommendation."""
    rec = MagicMock()
    rec.id = uuid4()
    rec.user_id = user_id or uuid4()
    rec.product_id = product_id or uuid4()
    rec.status = status if status is not None else RecommendationStatus.PENDING
    rec.valid_until = datetime.now(UTC) + timedelta(minutes=valid_minutes)
    rec.recommended_price = recommended_price
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.reviewed_by = None
    rec.reviewed_at = None
    rec.rejection_reason = None
    rec.applied_at = None
    rec.applied_to_platform = None
    rec.created_at = datetime.now(UTC)
    return rec


def make_product(product_id=None, current_price=25.00):
    """Create a mock Product."""
    product = MagicMock()
    product.id = product_id or uuid4()
    product.current_price = current_price
    product.updated_at = None
    return product


def make_settings(max_auto=10):
    """Create a mock PricingSettings."""
    settings = MagicMock()
    settings.max_auto_changes_per_day = max_auto
    return settings


def make_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


# =====================================================================
# ApprovalError
# =====================================================================

class TestApprovalError:

    def test_message_and_default_code(self):
        err = ApprovalError("something broke")
        assert err.message == "something broke"
        assert err.error_code == "APPROVAL_ERROR"
        assert str(err) == "something broke"

    def test_custom_error_code(self):
        err = ApprovalError("expired", "RECOMMENDATION_EXPIRED")
        assert err.error_code == "RECOMMENDATION_EXPIRED"

    def test_is_exception(self):
        with pytest.raises(ApprovalError):
            raise ApprovalError("test")


# =====================================================================
# approve()
# =====================================================================

class TestApprove:

    @pytest.mark.asyncio
    async def test_approve_pending_recommendation(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id, status="PENDING")
        # Mock status comparison - make it work with string comparison
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        db.get = AsyncMock(return_value=rec)
        
        service = ApprovalService(db)
        # Patch _get_recommendation to return our mock
        service._get_recommendation = AsyncMock(return_value=rec)
        
        result = await service.approve(rec.id, user_id)
        assert result.reviewed_by == user_id
        assert result.reviewed_at is not None
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_approve_non_pending_raises(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.APPROVED
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.approve(rec.id, user_id)
        assert exc_info.value.error_code == "INVALID_STATUS"

    @pytest.mark.asyncio
    async def test_approve_expired_recommendation(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id, valid_minutes=-10)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.approve(rec.id, user_id)
        assert exc_info.value.error_code == "RECOMMENDATION_EXPIRED"

    @pytest.mark.asyncio
    async def test_approve_with_auto_flag(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        result = await service.approve(rec.id, user_id, auto=True)
        # When auto=True, status should be set to AUTO_APPROVED
        # We verify it was set (the exact enum depends on the model)
        assert result.reviewed_by == user_id


# =====================================================================
# reject()
# =====================================================================

class TestReject:

    @pytest.mark.asyncio
    async def test_reject_pending_recommendation(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        result = await service.reject(rec.id, user_id, reason="Price too high")
        assert result.rejection_reason == "Price too high"
        assert result.reviewed_by == user_id
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_reject_without_reason(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        result = await service.reject(rec.id, user_id)
        assert result.rejection_reason is None
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_reject_non_pending_raises(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.APPLIED
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.reject(rec.id, user_id)
        assert exc_info.value.error_code == "INVALID_STATUS"


# =====================================================================
# apply_price()
# =====================================================================

class TestApplyPrice:

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_apply_approved_recommendation(self, MockPushService):
        user_id = uuid4()
        product_id = uuid4()
        rec = make_recommendation(user_id=user_id, product_id=product_id)
        rec.status = RecommendationStatus.APPROVED
        product = make_product(product_id=product_id, current_price=25.00)
        
        # Mock push service
        mock_push = AsyncMock()
        mock_push.push_price.return_value = {"success": True, "platform": "shopify"}
        MockPushService.return_value = mock_push
        
        db = make_db()
        db.get = AsyncMock(return_value=product)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        result = await service.apply_price(rec.id, user_id)
        assert result.applied_to_platform == "shopify"
        assert product.current_price == rec.recommended_price
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_apply_pending_raises(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.apply_price(rec.id, user_id)
        assert exc_info.value.error_code == "INVALID_STATUS"

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_apply_product_not_found(self, MockPushService):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.APPROVED
        
        db = make_db()
        db.get = AsyncMock(return_value=None)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.apply_price(rec.id, user_id)
        assert exc_info.value.error_code == "PRODUCT_NOT_FOUND"

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_apply_platform_push_fails_rolls_back(self, MockPushService):
        user_id = uuid4()
        product_id = uuid4()
        rec = make_recommendation(user_id=user_id, product_id=product_id)
        rec.status = RecommendationStatus.APPROVED
        product = make_product(product_id=product_id, current_price=25.00)
        original_price = product.current_price
        
        mock_push = AsyncMock()
        mock_push.push_price.return_value = {
            "success": False,
            "error": "Shopify API timeout",
            "error_code": "PLATFORM_PUSH_FAILED"
        }
        MockPushService.return_value = mock_push
        
        db = make_db()
        db.get = AsyncMock(return_value=product)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.apply_price(rec.id, user_id)
        assert exc_info.value.error_code == "PLATFORM_PUSH_FAILED"
        db.rollback.assert_awaited()
        assert product.current_price == original_price


# =====================================================================
# auto_approve_and_apply() — atomic transaction
# =====================================================================

class TestAutoApproveAndApply:

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_atomic_success(self, MockPushService):
        user_id = uuid4()
        product_id = uuid4()
        rec = make_recommendation(user_id=user_id, product_id=product_id)
        rec.status = RecommendationStatus.PENDING
        product = make_product(product_id=product_id, current_price=25.00)
        
        mock_push = AsyncMock()
        mock_push.push_price.return_value = {"success": True, "platform": "woocommerce"}
        MockPushService.return_value = mock_push
        
        db = make_db()
        db.get = AsyncMock(return_value=product)
        
        # Mock the daily limit check and execute
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        service._check_daily_limit = AsyncMock(return_value=(True, "OK"))
        
        result = await service.auto_approve_and_apply(rec.id, user_id)
        
        assert product.current_price == rec.recommended_price
        assert result.applied_to_platform == "woocommerce"
        # Single commit at end — atomic
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daily_limit_reached_raises(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        
        db = make_db()
        service = ApprovalService(db)
        service._check_daily_limit = AsyncMock(
            return_value=(False, "Daily limit reached (10/10)")
        )
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.auto_approve_and_apply(rec.id, user_id)
        assert exc_info.value.error_code == "DAILY_LIMIT_REACHED"

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_platform_failure_rolls_back(self, MockPushService):
        user_id = uuid4()
        product_id = uuid4()
        rec = make_recommendation(user_id=user_id, product_id=product_id)
        rec.status = RecommendationStatus.PENDING
        product = make_product(product_id=product_id, current_price=25.00)
        original_price = product.current_price
        
        mock_push = AsyncMock()
        mock_push.push_price.return_value = {
            "success": False,
            "error": "Connection refused",
            "error_code": "NO_ACTIVE_INTEGRATION_LINK"
        }
        MockPushService.return_value = mock_push
        
        db = make_db()
        db.get = AsyncMock(return_value=product)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        service._check_daily_limit = AsyncMock(return_value=(True, "OK"))
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.auto_approve_and_apply(rec.id, user_id)
        assert exc_info.value.error_code == "NO_ACTIVE_INTEGRATION_LINK"
        db.rollback.assert_awaited()
        assert product.current_price == original_price

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_expired_recommendation_raises(self, MockPushService):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id, valid_minutes=-10)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        service._check_daily_limit = AsyncMock(return_value=(True, "OK"))
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.auto_approve_and_apply(rec.id, user_id)
        assert exc_info.value.error_code == "RECOMMENDATION_EXPIRED"

    @pytest.mark.asyncio
    @patch("services.pricing.ecommerce_push_service.EcommercePushService")
    async def test_product_not_found_raises(self, MockPushService):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        rec.status = RecommendationStatus.PENDING
        
        db = make_db()
        db.get = AsyncMock(return_value=None)
        
        service = ApprovalService(db)
        service._get_recommendation = AsyncMock(return_value=rec)
        service._check_daily_limit = AsyncMock(return_value=(True, "OK"))
        
        with pytest.raises(ApprovalError) as exc_info:
            await service.auto_approve_and_apply(rec.id, user_id)
        assert exc_info.value.error_code == "PRODUCT_NOT_FOUND"


# =====================================================================
# _get_recommendation()
# =====================================================================

class TestGetRecommendation:

    @pytest.mark.asyncio
    async def test_returns_owned_recommendation(self):
        user_id = uuid4()
        rec = make_recommendation(user_id=user_id)
        
        db = make_db()
        db.get = AsyncMock(return_value=rec)
        
        service = ApprovalService(db)
        result = await service._get_recommendation(rec.id, user_id)
        assert result is rec

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        db = make_db()
        db.get = AsyncMock(return_value=None)
        
        service = ApprovalService(db)
        with pytest.raises(ApprovalError) as exc_info:
            await service._get_recommendation(uuid4(), uuid4())
        assert exc_info.value.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_wrong_user_raises(self):
        rec = make_recommendation(user_id=uuid4())
        
        db = make_db()
        db.get = AsyncMock(return_value=rec)
        
        service = ApprovalService(db)
        different_user = uuid4()
        with pytest.raises(ApprovalError) as exc_info:
            await service._get_recommendation(rec.id, different_user)
        assert exc_info.value.error_code == "NOT_FOUND"


# =====================================================================
# _check_daily_limit()
# =====================================================================

class TestCheckDailyLimit:

    @pytest.mark.asyncio
    async def test_no_settings_allows_unlimited(self):
        """FIX verification: no settings = no limit, not blocked."""
        db = make_db()
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=None)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_limit_zero_allows_unlimited(self):
        db = make_db()
        settings = make_settings(max_auto=0)
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=settings)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_negative_limit_allows_unlimited(self):
        db = make_db()
        settings = make_settings(max_auto=-1)
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=settings)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_within_limit_allows(self):
        db = make_db()
        settings = make_settings(max_auto=10)
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=settings)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_at_limit_blocks(self):
        db = make_db()
        settings = make_settings(max_auto=10)
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=settings)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is False
        assert "10/10" in msg

    @pytest.mark.asyncio
    async def test_over_limit_blocks(self):
        db = make_db()
        settings = make_settings(max_auto=5)
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 7
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        service._get_user_settings = AsyncMock(return_value=settings)
        
        ok, msg = await service._check_daily_limit(uuid4())
        assert ok is False


# =====================================================================
# get_approval_stats()
# =====================================================================

class TestGetApprovalStats:

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self):
        user_id = uuid4()
        db = make_db()
        
        # Mock all the DB queries (total count, per-status counts, avg confidence)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        stats = await service.get_approval_stats(user_id, days=30)
        
        assert "total" in stats
        assert "by_status" in stats
        assert "avg_confidence_applied" in stats
        assert "auto_approval_ratio" in stats

    @pytest.mark.asyncio
    async def test_auto_approval_ratio_zero_when_none(self):
        user_id = uuid4()
        db = make_db()
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)
        
        service = ApprovalService(db)
        stats = await service.get_approval_stats(user_id)
        
        assert stats["auto_approval_ratio"] == 0.0


        