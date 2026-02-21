# backend/tests/test_auto_approval_service.py
"""
Comprehensive tests for AutoApprovalService — handles auto-approval
eligibility and batch processing of pending recommendations.

Tests cover:
- Initialization
- process_pending (orchestration, settings, blackout, daily limits)
- _is_eligible (all eligibility gates)
- _check_daily_limit (daily count vs limit)
- _in_blackout_period (normal + overnight ranges)

Total: ~45 tests
"""

import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.price_recommendation",
    "models.pricing_settings",
    "services.pricing.approval_service",
    "services.pricing.settings_service",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Fix comparison operators on mocked model columns (Python 3.13)
from models.price_recommendation import PriceRecommendation, RecommendationStatus
for _col in ['user_id', 'status', 'valid_until', 'applied_at', 'id']:
    _c = getattr(PriceRecommendation, _col)
    try:
        _c.__eq__ = MagicMock(return_value=MagicMock())
        _c.__gt__ = MagicMock(return_value=MagicMock())
        _c.__ge__ = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

import pytest

from services.pricing.auto_approval_service import AutoApprovalService

SERVICE_PATH = "services.pricing.auto_approval_service"

# ============================================================
# Helpers
# ============================================================

USER_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def make_settings(
    auto_approve_enabled=True,
    auto_approve_max_increase=Decimal("5.0"),
    auto_approve_max_decrease=Decimal("10.0"),
    auto_approve_min_confidence=Decimal("0.70"),
    require_approval_above_price=None,
    max_auto_changes_per_day=3,
    blackout_hours_start=0,
    blackout_hours_end=6,
):
    s = MagicMock()
    s.auto_approve_enabled = auto_approve_enabled
    s.auto_approve_max_increase = auto_approve_max_increase
    s.auto_approve_max_decrease = auto_approve_max_decrease
    s.auto_approve_min_confidence = auto_approve_min_confidence
    s.require_approval_above_price = require_approval_above_price
    s.max_auto_changes_per_day = max_auto_changes_per_day
    s.blackout_hours_start = blackout_hours_start
    s.blackout_hours_end = blackout_hours_end
    return s


def make_recommendation(
    id=None,
    change_percent=Decimal("3.0"),
    confidence_score=Decimal("0.80"),
    current_price=Decimal("100.00"),
    status=None,
):
    rec = MagicMock()
    rec.id = id or uuid4()
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.current_price = current_price
    rec.status = status or RecommendationStatus.PENDING
    rec.user_id = USER_ID
    return rec


# ============================================================
# 1. Initialization
# ============================================================

class TestAutoApprovalServiceInit:

    def test_stores_db(self):
        db = make_mock_db()
        svc = AutoApprovalService(db)
        assert svc.db is db


# ============================================================
# 2. process_pending (orchestration)
# ============================================================

class TestProcessPending:

    @pytest.mark.asyncio
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_when_auto_approve_disabled(self, mock_select, MockSS):
        db = make_mock_db()
        settings = make_settings(auto_approve_enabled=False)
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        svc = AutoApprovalService(db)
        result = await svc.process_pending(USER_ID)

        assert result == []

    @pytest.mark.asyncio
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_in_blackout_period(self, mock_select, MockSS):
        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=True)

        result = await svc.process_pending(USER_ID)
        assert result == []

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_when_no_pending(self, mock_select, MockSS, MockAS):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=False)

        result = await svc.process_pending(USER_ID)
        assert result == []

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_applies_eligible_recommendations(self, mock_select, MockSS, MockAS):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        rec = make_recommendation()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec]
        db.execute.return_value = mock_result

        mock_as_instance = AsyncMock()
        applied_rec = MagicMock()
        mock_as_instance.auto_approve_and_apply.return_value = applied_rec
        MockAS.return_value = mock_as_instance

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=False)
        svc._check_daily_limit = AsyncMock(return_value=True)
        svc._is_eligible = MagicMock(return_value=True)

        result = await svc.process_pending(USER_ID)
        assert len(result) == 1
        assert result[0] is applied_rec

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_skips_ineligible_recommendations(self, mock_select, MockSS, MockAS):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        rec = make_recommendation()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec]
        db.execute.return_value = mock_result

        MockAS.return_value = AsyncMock()

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=False)
        svc._check_daily_limit = AsyncMock(return_value=True)
        svc._is_eligible = MagicMock(return_value=False)

        result = await svc.process_pending(USER_ID)
        assert result == []

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_stops_when_daily_limit_hit(self, mock_select, MockSS, MockAS):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        rec1 = make_recommendation()
        rec2 = make_recommendation()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec1, rec2]
        db.execute.return_value = mock_result

        MockAS.return_value = AsyncMock()

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=False)
        # First check passes, second check hits limit
        svc._check_daily_limit = AsyncMock(side_effect=[True, False])
        svc._is_eligible = MagicMock(return_value=True)

        mock_as_instance = AsyncMock()
        mock_as_instance.auto_approve_and_apply.return_value = MagicMock()
        MockAS.return_value = mock_as_instance

        result = await svc.process_pending(USER_ID)
        # Only the first one should be applied before limit hit
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("services.pricing.approval_service.ApprovalService")
    @patch("services.pricing.settings_service.SettingsService")
    @patch(f"{SERVICE_PATH}.select")
    async def test_continues_on_apply_failure(self, mock_select, MockSS, MockAS):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        settings = make_settings()
        mock_ss_instance = AsyncMock()
        mock_ss_instance.get_or_create.return_value = settings
        MockSS.return_value = mock_ss_instance

        rec1 = make_recommendation()
        rec2 = make_recommendation()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec1, rec2]
        db.execute.return_value = mock_result

        mock_as_instance = AsyncMock()
        applied_rec = MagicMock()
        # First fails, second succeeds
        mock_as_instance.auto_approve_and_apply.side_effect = [
            Exception("failed"), applied_rec
        ]
        MockAS.return_value = mock_as_instance

        svc = AutoApprovalService(db)
        svc._in_blackout_period = MagicMock(return_value=False)
        svc._check_daily_limit = AsyncMock(return_value=True)
        svc._is_eligible = MagicMock(return_value=True)

        result = await svc.process_pending(USER_ID)
        assert len(result) == 1
        assert result[0] is applied_rec


# ============================================================
# 3. _is_eligible
# ============================================================

class TestIsEligible:

    def setup_method(self):
        self.svc = AutoApprovalService(make_mock_db())

    def test_eligible_within_all_thresholds(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True

    def test_low_confidence_not_eligible(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.60,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is False

    def test_confidence_at_threshold_is_eligible(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.70,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True

    def test_increase_exceeds_max(self):
        rec_data = {
            "change_percent": 6.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is False

    def test_increase_at_threshold_is_eligible(self):
        rec_data = {
            "change_percent": 5.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True

    def test_decrease_exceeds_max(self):
        rec_data = {
            "change_percent": -11.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is False

    def test_decrease_at_threshold_is_eligible(self):
        rec_data = {
            "change_percent": -10.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True

    def test_high_value_product_not_eligible(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.80,
            "current_price": 200.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, 150.0) is False

    def test_below_price_threshold_is_eligible(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, 150.0) is True

    def test_no_price_threshold_allows_all(self):
        rec_data = {
            "change_percent": 3.0,
            "confidence_score": 0.80,
            "current_price": 5000.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True

    def test_zero_change_is_eligible(self):
        rec_data = {
            "change_percent": 0.0,
            "confidence_score": 0.80,
            "current_price": 100.0,
        }
        assert self.svc._is_eligible(rec_data, 5.0, 10.0, 0.70, None) is True


# ============================================================
# 4. _check_daily_limit
# ============================================================

class TestCheckDailyLimit:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_within_limit(self, mock_func, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        db.execute.return_value = mock_result

        settings = make_settings(max_auto_changes_per_day=3)
        svc = AutoApprovalService(db)

        result = await svc._check_daily_limit(USER_ID, settings)
        assert result is True

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_at_limit(self, mock_func, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        db.execute.return_value = mock_result

        settings = make_settings(max_auto_changes_per_day=3)
        svc = AutoApprovalService(db)

        result = await svc._check_daily_limit(USER_ID, settings)
        assert result is False

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_none_count_treated_as_zero(self, mock_func, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        db.execute.return_value = mock_result

        settings = make_settings(max_auto_changes_per_day=3)
        svc = AutoApprovalService(db)

        result = await svc._check_daily_limit(USER_ID, settings)
        assert result is True


# ============================================================
# 5. _in_blackout_period
# ============================================================

class TestInBlackoutPeriod:

    def setup_method(self):
        self.svc = AutoApprovalService(make_mock_db())

    def test_none_start_returns_false(self):
        settings = make_settings(blackout_hours_start=None, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is False

    def test_none_end_returns_false(self):
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=None)
        assert self.svc._in_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_within_normal_blackout(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 3, 0)
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_outside_normal_blackout(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 12, 0)
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_late_night(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 23, 0)
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_early_morning(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 3, 0)
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_midday_outside(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 12, 0)
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_exactly_at_start_is_blackout(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 0, 0)
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_exactly_at_end_is_not_blackout(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 1, 6, 0)
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._in_blackout_period(settings) is False


        