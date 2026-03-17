"""
Tests for OutcomeService.record_merchant_decision().

Covers:
1. Typed evidence extraction (factors with scout/analyst/strategist_evidence)
2. Old-style evidence extraction (factors with match_details/price_impacts)
3. Backward compatibility (mixed or missing evidence)
4. Idempotency (double-call returns existing record)
5. Measurement status routing (accepted→DECISION_RECORDED, rejected→MEASURED_30D)
6. Merchant modification detection (auto-detect >1% diff)
7. Confidence decomposition extraction from typed vs old-style

sys.modules isolation: db.session mocked before import to prevent
asyncpg engine creation at import time.

NOTE: Do NOT use MagicMock(spec=ModelClass) — Python 3.13 rejects speccing
against Mock objects. Use plain MagicMock() instead.

NOTE: Do NOT import from models.* directly — the module is already
loaded as models.* by OutcomeService. Importing via backend.models.* creates
a second module entry that re-runs the SQLModel table=True class, crashing
with "Table already defined".

Place at: backend/tests/unit/test_record_merchant_decision.py
Run: pytest backend/tests/unit/test_record_merchant_decision.py -v
"""

import sys
import types
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION — must happen BEFORE importing OutcomeService
# ══════════════════════════════════════════════════════════════════

_saved = {}
for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved[_key] = sys.modules[_key]

_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

# ── Import the service under test ──
from services.pricing.outcome_service import OutcomeService

# ── Pull enums from the ALREADY-LOADED module (same path the source used) ──
# Do NOT do `from models.recommendation_outcome import ...`
# because that triggers a second table registration.
_outcome_mod = sys.modules["models.recommendation_outcome"]
OutcomeLabel = _outcome_mod.OutcomeLabel
MeasurementStatus = _outcome_mod.MeasurementStatus
MerchantDecision = _outcome_mod.MerchantDecision
RecommendationSource = _outcome_mod.RecommendationSource

_rec_mod = sys.modules["models.price_recommendation"]
RecommendationStatus = _rec_mod.RecommendationStatus


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _make_db(existing_outcome=None, rule=None, product=None):
    """Build a mock AsyncSession that returns the right objects."""
    db = AsyncMock()

    # db.get() dispatch: PriceRecommendation, PricingRule, Product
    # We'll configure per-test via the recommendation fixture
    async def _get(model_cls, pk):
        name = model_cls.__name__ if hasattr(model_cls, "__name__") else str(model_cls)
        if "PricingRule" in name:
            return rule
        if "Product" in name:
            return product
        # Default: PriceRecommendation — set per test
        return db._recommendation

    db.get = AsyncMock(side_effect=_get)

    # db.execute() → result.scalars().first() → existing_outcome or None
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = existing_outcome
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    # db.add / commit / refresh are no-ops
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    return db


def _make_recommendation(
    user_id,
    recommendation_id,
    factors=None,
    current_price=Decimal("32.00"),
    recommended_price=Decimal("29.49"),
    change_percent=Decimal("-7.84"),
    confidence_score=Decimal("0.72"),
    triggered_rule_id=None,
    applied_at=None,
    applied_to_platform="shopify",
):
    rec = MagicMock()
    rec.id = recommendation_id
    rec.user_id = user_id
    rec.product_id = uuid4()
    rec.current_price = current_price
    rec.recommended_price = recommended_price
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.factors = factors or {}
    rec.triggered_rule_id = triggered_rule_id
    rec.reasoning = "Test reasoning"
    rec.requires_approval = True
    rec.applied_at = applied_at or datetime.now(UTC)
    rec.applied_to_platform = applied_to_platform
    rec.status = RecommendationStatus.APPLIED
    return rec


def _typed_factors():
    """Factors dict as produced by PipelineAdapter (post-2026-02-17)."""
    return {
        "scout_evidence": {
            "competitor_count": 3,
            "our_price": "32.00",
            "data_completeness": 0.85,
            "competitors": [
                {"competitor_name": "Store A", "price": "27.50"},
                {"competitor_name": "Store B", "price": "29.99"},
            ],
        },
        "analyst_evidence": {
            "confidence": {
                "elasticity": 0.75,
                "position": 0.7,
                "urgency": 0.65,
                "data_quality": 0.8,
            },
            "sentiment_score": 0.35,
            "competitor_count": 3,
            "urgency_score": 0.4,
            "data_completeness": 0.85,
            "competitive_position_index": 0.6,
            "elasticity": {
                "point_estimate": -1.2,
                "method": "category_prior",
            },
        },
        "strategist_evidence": {
            "recommended_price": "29.49",
            "change_percent": "-7.84",
            "reasoning": "Price aligned to competition",
            "pipeline_source": "rule_based",
        },
    }


def _old_style_factors():
    """Factors dict as produced pre-2026-02-17 (unstructured)."""
    return {
        "match_details": {
            "rule_name": "Competitor undercut",
            "matched_competitors": ["Store A", "Store B"],
        },
        "price_impacts": {
            "sentiment_score": 0.25,
            "competitor_count": 2,
        },
        "confidence_breakdown": {
            "overall": 0.68,
            "components": {
                "signal_agreement": {"score": 0.7},
                "market_stability": {"score": 0.65},
                "rule_confidence": {"score": 0.6},
                "data_quality": {"score": 0.75},
            },
        },
    }


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def recommendation_id():
    return uuid4()


@pytest.fixture
def rule_id():
    return uuid4()


@pytest.fixture
def mock_rule(rule_id):
    rule = MagicMock()
    rule.id = rule_id
    rule.name = "Competitor undercut"
    rule.rule_type = MagicMock()
    rule.rule_type.value = "competitor_relative"
    return rule


@pytest.fixture
def mock_product():
    product = MagicMock()
    product.id = uuid4()
    product.category = "Electronics"
    return product


# ══════════════════════════════════════════════════════════════════
# 1. TYPED EVIDENCE EXTRACTION
# ══════════════════════════════════════════════════════════════════


class TestTypedEvidenceExtraction:
    @pytest.mark.asyncio
    async def test_extracts_scout_evidence(self, user_id, recommendation_id, mock_product):
        factors = _typed_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        outcome = await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        # db.add was called with the outcome
        db.add.assert_called_once()
        created = db.add.call_args[0][0]
        assert created.scout_evidence == factors["scout_evidence"]

    @pytest.mark.asyncio
    async def test_extracts_analyst_evidence(self, user_id, recommendation_id, mock_product):
        factors = _typed_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        outcome = await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.analyst_evidence == factors["analyst_evidence"]

    @pytest.mark.asyncio
    async def test_extracts_strategist_evidence(self, user_id, recommendation_id, mock_product):
        factors = _typed_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        outcome = await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.strategist_evidence["pipeline_source"] == "rule_based"

    @pytest.mark.asyncio
    async def test_typed_confidence_decomposition(self, user_id, recommendation_id, mock_product):
        factors = _typed_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.confidence_elasticity == 0.75
        assert created.confidence_position == 0.7
        assert created.confidence_urgency == 0.65
        assert created.confidence_data_quality == 0.8

    @pytest.mark.asyncio
    async def test_typed_analyst_snapshot(self, user_id, recommendation_id, mock_product):
        factors = _typed_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.sentiment_score == 0.35
        assert created.competitor_count == 3
        assert created.urgency_score == 0.4
        assert created.data_completeness == 0.85
        assert created.competitive_position_index == 0.6


# ══════════════════════════════════════════════════════════════════
# 2. OLD-STYLE EVIDENCE EXTRACTION
# ══════════════════════════════════════════════════════════════════


class TestOldStyleEvidenceExtraction:
    @pytest.mark.asyncio
    async def test_falls_back_to_match_details(self, user_id, recommendation_id, mock_product):
        factors = _old_style_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.scout_evidence == factors["match_details"]

    @pytest.mark.asyncio
    async def test_falls_back_to_price_impacts(self, user_id, recommendation_id, mock_product):
        factors = _old_style_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.analyst_evidence == factors["price_impacts"]

    @pytest.mark.asyncio
    async def test_old_style_confidence_from_components(self, user_id, recommendation_id, mock_product):
        factors = _old_style_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.confidence_elasticity == 0.7  # signal_agreement.score
        assert created.confidence_position == 0.65  # market_stability.score
        assert created.confidence_urgency == 0.6  # rule_confidence.score
        assert created.confidence_data_quality == 0.75  # data_quality.score

    @pytest.mark.asyncio
    async def test_old_style_sentiment_from_price_impacts(self, user_id, recommendation_id, mock_product):
        factors = _old_style_factors()
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.sentiment_score == 0.25
        assert created.competitor_count == 2


# ══════════════════════════════════════════════════════════════════
# 3. BACKWARD COMPATIBILITY (empty / missing factors)
# ══════════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_empty_factors(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id, factors={})
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.scout_evidence is None
        assert created.analyst_evidence is None
        # strategist_evidence gets a manual fallback build
        assert created.strategist_evidence is not None
        assert created.strategist_evidence["recommended_price"] == "29.49"

    @pytest.mark.asyncio
    async def test_none_factors(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id, factors=None)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.confidence_elasticity is None
        assert created.confidence_position is None

    @pytest.mark.asyncio
    async def test_mixed_typed_and_old(self, user_id, recommendation_id, mock_product):
        """Has typed scout_evidence but old-style confidence_breakdown."""
        factors = {
            "scout_evidence": {"competitor_count": 2, "our_price": "32.00"},
            "confidence_breakdown": {
                "components": {
                    "signal_agreement": {"score": 0.7},
                    "data_quality": {"score": 0.8},
                },
            },
        }
        rec = _make_recommendation(user_id, recommendation_id, factors=factors)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.scout_evidence == factors["scout_evidence"]
        # Falls back to old-style for confidence since no typed analyst
        assert created.confidence_elasticity == 0.7
        assert created.confidence_data_quality == 0.8


# ══════════════════════════════════════════════════════════════════
# 4. IDEMPOTENCY
# ══════════════════════════════════════════════════════════════════


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_returns_existing_outcome(self, user_id, recommendation_id, mock_product):
        existing = MagicMock()
        existing.id = uuid4()
        existing.measurement_status = MeasurementStatus.DECISION_RECORDED.value

        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(existing_outcome=existing, product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        result = await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        # Returns existing, doesn't create new
        assert result.id == existing.id
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_awaiting_decision(self, user_id, recommendation_id, mock_product):
        existing = MagicMock()
        existing.id = uuid4()
        existing.measurement_status = MeasurementStatus.AWAITING_DECISION.value

        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(existing_outcome=existing, product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        result = await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        # Updates existing record
        assert result.merchant_decision == MerchantDecision.ACCEPTED.value
        assert result.measurement_status == MeasurementStatus.DECISION_RECORDED.value


# ══════════════════════════════════════════════════════════════════
# 5. MEASUREMENT STATUS ROUTING
# ══════════════════════════════════════════════════════════════════


class TestMeasurementStatus:
    @pytest.mark.asyncio
    async def test_accepted_gets_decision_recorded(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.DECISION_RECORDED.value

    @pytest.mark.asyncio
    async def test_rejected_gets_measured_30d(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.REJECTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.MEASURED_30D.value

    @pytest.mark.asyncio
    async def test_auto_applied_gets_decision_recorded(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.AUTO_APPLIED.value,
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.DECISION_RECORDED.value

    @pytest.mark.asyncio
    async def test_modified_gets_decision_recorded(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.MODIFIED.value,
            actual_price_set=Decimal("30.00"),
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.DECISION_RECORDED.value


# ══════════════════════════════════════════════════════════════════
# 6. MERCHANT MODIFICATION DETECTION
# ══════════════════════════════════════════════════════════════════


class TestModificationDetection:
    @pytest.mark.asyncio
    async def test_auto_detects_modification_over_1pct(self, user_id, recommendation_id, mock_product):
        """'accepted' with >1% price diff auto-upgrades to 'modified'."""
        rec = _make_recommendation(
            user_id,
            recommendation_id,
            recommended_price=Decimal("29.49"),
        )
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
            actual_price_set=Decimal("31.00"),  # >1% diff from 29.49
        )

        created = db.add.call_args[0][0]
        assert created.merchant_decision == MerchantDecision.MODIFIED.value
        assert created.merchant_modification_percent is not None
        assert abs(created.merchant_modification_percent) > 1.0

    @pytest.mark.asyncio
    async def test_no_modification_under_1pct(self, user_id, recommendation_id, mock_product):
        """'accepted' with <1% price diff stays 'accepted'."""
        rec = _make_recommendation(
            user_id,
            recommendation_id,
            recommended_price=Decimal("29.49"),
        )
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
            actual_price_set=Decimal("29.49"),  # Exact match
        )

        created = db.add.call_args[0][0]
        assert created.merchant_decision == MerchantDecision.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_no_actual_price_uses_recommended(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(
            user_id,
            recommendation_id,
            recommended_price=Decimal("29.49"),
        )
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
            actual_price_set=None,
        )

        created = db.add.call_args[0][0]
        assert created.actual_price_set == Decimal("29.49")
        assert created.merchant_modification_percent is None


# ══════════════════════════════════════════════════════════════════
# 7. PRICE AND PRODUCT FIELDS
# ══════════════════════════════════════════════════════════════════


class TestPriceAndProductFields:
    @pytest.mark.asyncio
    async def test_price_fields_from_recommendation(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(
            user_id,
            recommendation_id,
            current_price=Decimal("32.00"),
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
        )
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.price_before == Decimal("32.00")
        assert created.price_after == Decimal("29.49")
        assert created.price_change_percent == Decimal("-7.84")

    @pytest.mark.asyncio
    async def test_product_category_extracted(self, user_id, recommendation_id, mock_product):
        mock_product.category = "Electronics"
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.product_category == "Electronics"

    @pytest.mark.asyncio
    async def test_store_platform_from_recommendation(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id, applied_to_platform="shopify")
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.store_platform == "shopify"

    @pytest.mark.asyncio
    async def test_sales_data_starts_at_zero(self, user_id, recommendation_id, mock_product):
        """Sales data should be zero — Celery fills it at 7d/14d/30d."""
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.units_sold_before == 0
        assert created.units_sold_after == 0
        assert created.revenue_before == Decimal("0")
        assert created.revenue_after == Decimal("0")

    @pytest.mark.asyncio
    async def test_outcome_starts_inconclusive(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.outcome_label == OutcomeLabel.INCONCLUSIVE
        assert created.outcome_score == Decimal("0")


# ══════════════════════════════════════════════════════════════════
# 8. VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestValidation:
    @pytest.mark.asyncio
    async def test_recommendation_not_found_raises(self, user_id, recommendation_id):
        db = _make_db()
        db._recommendation = None  # db.get returns None

        svc = OutcomeService(db)
        with pytest.raises(ValueError, match="Recommendation not found"):
            await svc.record_merchant_decision(
                recommendation_id=recommendation_id,
                user_id=user_id,
                merchant_decision=MerchantDecision.ACCEPTED.value,
            )

    @pytest.mark.asyncio
    async def test_wrong_user_raises(self, user_id, recommendation_id):
        other_user = uuid4()
        rec = _make_recommendation(other_user, recommendation_id)  # Different user
        db = _make_db()
        db._recommendation = rec

        svc = OutcomeService(db)
        with pytest.raises(ValueError, match="Recommendation not found"):
            await svc.record_merchant_decision(
                recommendation_id=recommendation_id,
                user_id=user_id,
                merchant_decision=MerchantDecision.ACCEPTED.value,
            )


# ══════════════════════════════════════════════════════════════════
# 9. RULE TYPE EXTRACTION
# ══════════════════════════════════════════════════════════════════


class TestRuleTypeExtraction:
    @pytest.mark.asyncio
    async def test_extracts_rule_type(self, user_id, recommendation_id, mock_product, mock_rule, rule_id):
        rec = _make_recommendation(user_id, recommendation_id, triggered_rule_id=rule_id)
        db = _make_db(rule=mock_rule, product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.rule_type == "competitor_relative"

    @pytest.mark.asyncio
    async def test_no_rule_leaves_none(self, user_id, recommendation_id, mock_product):
        rec = _make_recommendation(user_id, recommendation_id, triggered_rule_id=None)
        db = _make_db(product=mock_product)
        db._recommendation = rec

        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=recommendation_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.rule_type is None


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved.items():
    sys.modules[_key] = _orig
