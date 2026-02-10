# backend/tests/test_settings_service.py
"""
Comprehensive tests for SettingsService — manages user pricing settings.

Tests cover:
- Initialization
- DEFAULT_SETTINGS constant
- get_or_create (fetch existing, create defaults)
- get_settings (deprecated path)
- _create_default_settings (DB creation)
- update_settings (partial updates, unknown fields)
- check_requires_approval (all approval gates)
- _is_blackout_period (normal + overnight ranges)

Total: ~50 tests
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
    "models.pricing_settings",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Fix comparison operators on PricingSettings columns
from models.pricing_settings import PricingSettings
for _col in ['user_id']:
    _c = getattr(PricingSettings, _col)
    try:
        _c.__eq__ = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

import pytest

from services.pricing.settings_service import SettingsService, DEFAULT_SETTINGS

SERVICE_PATH = "services.pricing.settings_service"

# ============================================================
# Helpers
# ============================================================

USER_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def make_product(current_price=Decimal("100.00")):
    p = MagicMock()
    p.current_price = current_price
    return p


def make_settings(
    auto_approve_enabled=True,
    auto_approve_min_confidence=Decimal("0.70"),
    auto_approve_max_increase=Decimal("5.0"),
    auto_approve_max_decrease=Decimal("10.0"),
    require_approval_above_price=None,
    blackout_hours_start=0,
    blackout_hours_end=6,
):
    s = MagicMock()
    s.auto_approve_enabled = auto_approve_enabled
    s.auto_approve_min_confidence = auto_approve_min_confidence
    s.auto_approve_max_increase = auto_approve_max_increase
    s.auto_approve_max_decrease = auto_approve_max_decrease
    s.require_approval_above_price = require_approval_above_price
    s.blackout_hours_start = blackout_hours_start
    s.blackout_hours_end = blackout_hours_end
    return s


# ============================================================
# 1. DEFAULT_SETTINGS constant
# ============================================================

class TestDefaultSettings:

    def test_auto_approve_enabled(self):
        assert DEFAULT_SETTINGS["auto_approve_enabled"] is True

    def test_min_confidence(self):
        assert DEFAULT_SETTINGS["auto_approve_min_confidence"] == Decimal("0.70")

    def test_max_increase(self):
        assert DEFAULT_SETTINGS["auto_approve_max_increase"] == Decimal("5.0")

    def test_max_decrease(self):
        assert DEFAULT_SETTINGS["auto_approve_max_decrease"] == Decimal("10.0")

    def test_min_margin(self):
        assert DEFAULT_SETTINGS["min_margin_percent"] == Decimal("10.0")

    def test_max_auto_changes(self):
        assert DEFAULT_SETTINGS["max_auto_changes_per_day"] == 3

    def test_cooldown_hours(self):
        assert DEFAULT_SETTINGS["global_cooldown_hours"] == 24

    def test_require_approval_above_price_is_none(self):
        assert DEFAULT_SETTINGS["require_approval_above_price"] is None

    def test_recommendation_valid_hours(self):
        assert DEFAULT_SETTINGS["recommendation_valid_hours"] == 48

    def test_blackout_hours(self):
        assert DEFAULT_SETTINGS["blackout_hours_start"] == 0
        assert DEFAULT_SETTINGS["blackout_hours_end"] == 6

    def test_notification_defaults(self):
        assert DEFAULT_SETTINGS["notify_on_auto_apply"] is True
        assert DEFAULT_SETTINGS["notify_on_pending"] is True


# ============================================================
# 2. Initialization
# ============================================================

class TestSettingsServiceInit:

    def test_stores_db(self):
        db = make_mock_db()
        svc = SettingsService(db)
        assert svc.db is db


# ============================================================
# 3. get_or_create
# ============================================================

class TestGetOrCreate:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_existing_settings(self, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        existing = make_settings()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing
        db.execute.return_value = mock_result

        svc = SettingsService(db)
        result = await svc.get_or_create(USER_ID)
        assert result is existing

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_creates_defaults_when_none_exist(self, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        new_settings = make_settings()
        svc = SettingsService(db)
        svc._create_default_settings = AsyncMock(return_value=new_settings)

        result = await svc.get_or_create(USER_ID)
        assert result is new_settings
        svc._create_default_settings.assert_awaited_once_with(USER_ID)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_never_returns_none(self, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        svc = SettingsService(db)
        svc._create_default_settings = AsyncMock(return_value=make_settings())

        result = await svc.get_or_create(USER_ID)
        assert result is not None


# ============================================================
# 4. get_settings (deprecated)
# ============================================================

class TestGetSettings:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_existing(self, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        existing = make_settings()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing
        db.execute.return_value = mock_result

        svc = SettingsService(db)
        result = await svc.get_settings(USER_ID)
        assert result is existing

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_none_when_not_found(self, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        svc = SettingsService(db)
        result = await svc.get_settings(USER_ID)
        assert result is None


# ============================================================
# 5. _create_default_settings
# ============================================================

class TestCreateDefaultSettings:

    @pytest.mark.asyncio
    async def test_adds_and_commits(self):
        db = make_mock_db()
        svc = SettingsService(db)

        await svc._create_default_settings(USER_ID)
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_pricing_settings_instance(self):
        db = make_mock_db()
        svc = SettingsService(db)

        result = await svc._create_default_settings(USER_ID)
        # Since PricingSettings is mocked, it returns a MagicMock,
        # but it should have been called with user_id and defaults
        assert result is not None


# ============================================================
# 6. update_settings
# ============================================================

class TestUpdateSettings:

    @pytest.mark.asyncio
    async def test_updates_provided_fields(self):
        db = make_mock_db()
        svc = SettingsService(db)

        existing = make_settings()
        existing.auto_approve_max_increase = Decimal("5.0")
        svc.get_or_create = AsyncMock(return_value=existing)

        result = await svc.update_settings(
            USER_ID,
            auto_approve_max_increase=Decimal("8.0")
        )
        assert result.auto_approve_max_increase == Decimal("8.0")

    @pytest.mark.asyncio
    async def test_commits_changes(self):
        db = make_mock_db()
        svc = SettingsService(db)
        svc.get_or_create = AsyncMock(return_value=make_settings())

        await svc.update_settings(USER_ID, auto_approve_enabled=False)
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ignores_unknown_fields(self):
        db = make_mock_db()
        svc = SettingsService(db)

        existing = make_settings()
        # MagicMock has all attrs, so test that unknown fields don't crash
        existing_spec = MagicMock(spec=["auto_approve_enabled", "updated_at"])
        existing_spec.auto_approve_enabled = True
        existing_spec.updated_at = None
        svc.get_or_create = AsyncMock(return_value=existing_spec)

        # "nonexistent_field" doesn't exist on spec'd mock
        result = await svc.update_settings(USER_ID, nonexistent_field="xyz")
        # Should complete without error
        assert result is not None

    @pytest.mark.asyncio
    async def test_sets_updated_at(self):
        db = make_mock_db()
        svc = SettingsService(db)

        existing = make_settings()
        existing.updated_at = None
        svc.get_or_create = AsyncMock(return_value=existing)

        await svc.update_settings(USER_ID, auto_approve_enabled=False)
        assert existing.updated_at is not None

    @pytest.mark.asyncio
    async def test_creates_settings_if_none_exist(self):
        db = make_mock_db()
        svc = SettingsService(db)
        svc.get_or_create = AsyncMock(return_value=make_settings())

        result = await svc.update_settings(USER_ID, auto_approve_enabled=False)
        svc.get_or_create.assert_awaited_once_with(USER_ID)
        assert result is not None


# ============================================================
# 7. check_requires_approval
# ============================================================

class TestCheckRequiresApproval:

    def setup_method(self):
        self.svc = SettingsService(make_mock_db())
        self.product = make_product()

    def test_none_settings_requires_approval(self):
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.8"), None
        )
        assert result is True

    def test_auto_approve_disabled(self):
        settings = make_settings(auto_approve_enabled=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.8"), settings
        )
        assert result is True

    def test_low_confidence_requires_approval(self):
        settings = make_settings(auto_approve_min_confidence=Decimal("0.80"))
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.70"), settings
        )
        assert result is True

    def test_confidence_at_threshold_passes(self):
        settings = make_settings(auto_approve_min_confidence=Decimal("0.70"))
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.70"), settings
        )
        assert result is False

    def test_increase_exceeds_threshold(self):
        settings = make_settings(auto_approve_max_increase=Decimal("5.0"))
        result = self.svc.check_requires_approval(
            self.product, Decimal("6.0"), Decimal("0.9"), settings
        )
        assert result is True

    def test_increase_within_threshold(self):
        settings = make_settings(auto_approve_max_increase=Decimal("5.0"))
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("4.0"), Decimal("0.9"), settings
        )
        assert result is False

    def test_decrease_exceeds_threshold(self):
        settings = make_settings(auto_approve_max_decrease=Decimal("10.0"))
        result = self.svc.check_requires_approval(
            self.product, Decimal("-11.0"), Decimal("0.9"), settings
        )
        assert result is True

    def test_decrease_within_threshold(self):
        settings = make_settings(auto_approve_max_decrease=Decimal("10.0"))
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("-9.0"), Decimal("0.9"), settings
        )
        assert result is False

    def test_high_value_product_requires_approval(self):
        settings = make_settings(require_approval_above_price=Decimal("50"))
        product = make_product(current_price=Decimal("100"))
        result = self.svc.check_requires_approval(
            product, Decimal("3"), Decimal("0.9"), settings
        )
        assert result is True

    def test_low_value_product_auto_approves(self):
        settings = make_settings(require_approval_above_price=Decimal("200"))
        self.svc._is_blackout_period = MagicMock(return_value=False)
        product = make_product(current_price=Decimal("100"))
        result = self.svc.check_requires_approval(
            product, Decimal("3"), Decimal("0.9"), settings
        )
        assert result is False

    def test_no_price_threshold_skips_check(self):
        settings = make_settings(require_approval_above_price=None)
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.9"), settings
        )
        assert result is False

    def test_blackout_period_requires_approval(self):
        settings = make_settings()
        self.svc._is_blackout_period = MagicMock(return_value=True)
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.9"), settings
        )
        assert result is True

    def test_outside_blackout_auto_approves(self):
        settings = make_settings()
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("3"), Decimal("0.9"), settings
        )
        assert result is False

    def test_zero_change_auto_approves(self):
        settings = make_settings()
        self.svc._is_blackout_period = MagicMock(return_value=False)
        result = self.svc.check_requires_approval(
            self.product, Decimal("0"), Decimal("0.9"), settings
        )
        assert result is False


# ============================================================
# 8. _is_blackout_period
# ============================================================

class TestIsBlackoutPeriod:

    def setup_method(self):
        self.svc = SettingsService(make_mock_db())

    def test_none_start_returns_false(self):
        settings = make_settings(blackout_hours_start=None, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is False

    def test_none_end_returns_false(self):
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=None)
        assert self.svc._is_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_within_normal_blackout(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 3, 0)  # 3am
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_outside_normal_blackout(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 12, 0)  # noon
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_late_night(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 23, 0)  # 11pm
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_early_morning(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 3, 0)  # 3am
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_overnight_blackout_midday_outside(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 12, 0)  # noon
        settings = make_settings(blackout_hours_start=22, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is False

    @patch(f"{SERVICE_PATH}.datetime")
    def test_exactly_at_start_is_blackout(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 0, 0)  # midnight
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is True

    @patch(f"{SERVICE_PATH}.datetime")
    def test_exactly_at_end_is_not_blackout(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 1, 1, 6, 0)  # 6am
        settings = make_settings(blackout_hours_start=0, blackout_hours_end=6)
        assert self.svc._is_blackout_period(settings) is False


        