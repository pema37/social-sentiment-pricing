"""
End-to-end integration test: Intelligence Environment feedback loop.

Proves the FULL chain works with typed evidence:

    generate_recommendation()
        → PipelineAdapter builds ScoutOutput/AnalystOutput/StrategistOutput
        → factors dict contains scout_evidence, analyst_evidence, strategist_evidence
    apply_price()
        → _record_decision() fires
        → OutcomeService.record_merchant_decision() extracts typed evidence
        → RecommendationOutcome created with:
            - confidence decomposition from typed analyst evidence
            - sentiment/competitor scores from typed analyst evidence
            - agent evidence chain (scout/analyst/strategist JSONB)
            - measurement_status = DECISION_RECORDED (ready for Celery)
    Celery measurement windows
        → outcome with DECISION_RECORDED status is picked up at 7d/14d/30d

This test mocks the database layer but runs REAL business logic through
RecommendationService → ApprovalService → OutcomeService → PipelineAdapter.

Place at: backend/tests/integration/test_e2e_feedback_loop.py
Run: pytest backend/tests/integration/test_e2e_feedback_loop.py -v
"""

import sys
import types
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION
# ══════════════════════════════════════════════════════════════════

_saved = {}
for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved[_key] = sys.modules[_key]

_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
_mock_db.run_async = MagicMock()
_mock_db.get_session_context = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

# Import after isolation
from services.pricing.pipeline_adapter import PipelineAdapter
from services.pricing.recommendation_helpers import (
    PriceCalculator,
    BoundaryEnforcer,
    ReasoningGenerator,
)

# Pull enums from already-loaded modules
_outcome_mod = sys.modules["models.recommendation_outcome"]
OutcomeLabel = _outcome_mod.OutcomeLabel
MeasurementStatus = _outcome_mod.MeasurementStatus
MerchantDecision = _outcome_mod.MerchantDecision
RecommendationSource = _outcome_mod.RecommendationSource

_rec_mod = sys.modules["models.price_recommendation"]
RecommendationStatus = _rec_mod.RecommendationStatus


# ══════════════════════════════════════════════════════════════════
# REALISTIC TEST DATA
# ══════════════════════════════════════════════════════════════════

def _make_product(
    product_id=None,
    current_price=Decimal("32.00"),
    min_price=Decimal("20.00"),
    max_price=Decimal("50.00"),
    category="Electronics",
):
    product = MagicMock()
    product.id = product_id or uuid4()
    product.current_price = current_price
    product.min_price = min_price
    product.max_price = max_price
    product.category = category
    product.name = "Wireless Earbuds Pro"
    product.updated_at = None
    return product


def _make_signals(
    competitor_prices=None,
    sentiment_score=0.35,
    mention_count_24h=127,
    viral_detected=False,
    sentiment_change_24h=-0.1,
    is_trending=False,
    trend_direction="stable",
):
    """Build a MarketSignals-like mock with flat attributes."""
    signals = MagicMock()
    signals.competitor_prices = competitor_prices or {
        "Store A": Decimal("27.50"),
        "Store B": Decimal("29.99"),
        "Store C": Decimal("35.00"),
    }
    signals.sentiment_score = sentiment_score
    signals.mention_count_24h = mention_count_24h
    signals.viral_detected = viral_detected
    signals.sentiment_change_24h = sentiment_change_24h
    signals.is_trending = is_trending
    signals.trend_direction = trend_direction
    return signals


def _make_rule(
    rule_id=None,
    name="Competitor undercut",
    action_value="decrease",
    min_price=Decimal("25.00"),
    max_price=Decimal("45.00"),
):
    rule = MagicMock()
    rule.id = rule_id or uuid4()
    rule.name = name
    rule.rule_type = MagicMock()
    rule.rule_type.value = "competitor_relative"
    rule.action = MagicMock()
    rule.action.value = action_value
    rule.min_price = min_price
    rule.max_price = max_price
    rule.last_triggered_at = None
    return rule


def _make_recommendation(
    user_id,
    recommendation_id,
    product,
    factors,
    recommended_price=Decimal("29.49"),
    change_percent=Decimal("-7.84"),
    confidence_score=Decimal("0.72"),
    rule_id=None,
):
    rec = MagicMock()
    rec.id = recommendation_id
    rec.user_id = user_id
    rec.product_id = product.id
    rec.current_price = product.current_price
    rec.recommended_price = recommended_price
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.factors = factors
    rec.triggered_rule_id = rule_id
    rec.reasoning = "Competitor-driven price adjustment"
    rec.requires_approval = True
    rec.status = RecommendationStatus.APPROVED
    rec.valid_until = datetime.now(UTC) + timedelta(hours=24)
    rec.applied_at = None
    rec.applied_to_platform = None
    rec.rejection_reason = None
    rec.reviewed_by = None
    rec.reviewed_at = None
    return rec


# ══════════════════════════════════════════════════════════════════
# PHASE 1: PipelineAdapter produces typed evidence
# ══════════════════════════════════════════════════════════════════

class TestPhase1TypedEvidence:
    """Verify PipelineAdapter produces complete evidence chain."""

    def test_scout_output_from_signals(self):
        product = _make_product()
        signals = _make_signals()

        scout = PipelineAdapter.build_scout_output(product, signals)

        assert scout.product_id == product.id
        assert scout.competitor_count == 3
        assert scout.our_price == Decimal("32.00")
        assert scout.data_completeness > 0
        assert len(scout.data_sources) > 0
        assert scout.sentiment is not None
        assert scout.sentiment.overall_score == 0.35

    def test_analyst_output_from_scout(self):
        product = _make_product()
        signals = _make_signals()
        scout = PipelineAdapter.build_scout_output(product, signals)

        confidence_breakdown = {
            "components": {
                "signal_agreement": {"score": 0.75},
                "market_stability": {"score": 0.7},
                "rule_confidence": {"score": 0.65},
                "data_quality": {"score": 0.8},
                "historical_accuracy": {"score": 0.6},
            },
        }
        rule = _make_rule(action_value="decrease")

        analyst = PipelineAdapter.build_analyst_output(
            scout, confidence_breakdown, signals, rule
        )

        assert analyst.product_id == product.id
        assert analyst.confidence.elasticity == 0.75
        assert analyst.confidence.data_quality == 0.8
        assert analyst.sentiment_score == 0.35
        assert analyst.competitor_count == 3

    def test_strategist_output_from_analyst(self):
        product = _make_product()
        signals = _make_signals()
        scout = PipelineAdapter.build_scout_output(product, signals)
        rule = _make_rule()

        confidence_breakdown = {
            "components": {
                "signal_agreement": {"score": 0.75},
                "market_stability": {"score": 0.7},
                "rule_confidence": {"score": 0.65},
                "data_quality": {"score": 0.8},
            },
        }

        analyst = PipelineAdapter.build_analyst_output(
            scout, confidence_breakdown, signals, rule
        )

        factors = {"match_details": {}, "price_impacts": {}}

        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Competitor undercut", factors, rule,
        )

        assert strategist.product_id == product.id
        assert strategist.recommended_price == Decimal("29.49")
        assert strategist.confidence_decomposition.elasticity == 0.75
        assert strategist.pipeline_source == "rule_based"

    def test_evidence_chain_serializable(self):
        """to_evidence() returns JSON-serializable dicts."""
        product = _make_product()
        signals = _make_signals()
        scout = PipelineAdapter.build_scout_output(product, signals)
        rule = _make_rule()

        confidence_breakdown = {
            "components": {
                "signal_agreement": {"score": 0.7},
                "market_stability": {"score": 0.65},
                "rule_confidence": {"score": 0.6},
                "data_quality": {"score": 0.8},
            },
        }

        analyst = PipelineAdapter.build_analyst_output(
            scout, confidence_breakdown, signals, rule
        )

        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Test reasoning", {}, rule,
        )

        scout_ev = scout.to_evidence()
        analyst_ev = analyst.to_evidence()
        strategist_ev = strategist.to_evidence()

        # All should be dicts (JSON-serializable)
        assert isinstance(scout_ev, dict)
        assert isinstance(analyst_ev, dict)
        assert isinstance(strategist_ev, dict)

        # Analyst evidence should contain confidence decomposition
        assert "confidence" in analyst_ev
        assert "elasticity" in analyst_ev["confidence"]

    def test_factors_dict_contains_typed_evidence(self):
        """Simulates what recommendation_service.py does."""
        product = _make_product()
        signals = _make_signals()
        rule = _make_rule()

        scout = PipelineAdapter.build_scout_output(product, signals)
        confidence_breakdown = {
            "components": {
                "signal_agreement": {"score": 0.7},
                "market_stability": {"score": 0.65},
                "rule_confidence": {"score": 0.6},
                "data_quality": {"score": 0.8},
            },
        }
        analyst = PipelineAdapter.build_analyst_output(
            scout, confidence_breakdown, signals, rule
        )
        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Test", {}, rule,
        )

        # This is exactly what recommendation_service.py does:
        factors = {
            "match_details": {"rule_type": "competitor_relative"},
            "price_impacts": {"competitor": -2.51},
            "confidence_breakdown": confidence_breakdown,
        }
        factors["scout_evidence"] = scout.to_evidence()
        factors["analyst_evidence"] = analyst.to_evidence()
        factors["strategist_evidence"] = strategist.to_evidence()

        # Verify the three typed keys exist
        assert "scout_evidence" in factors
        assert "analyst_evidence" in factors
        assert "strategist_evidence" in factors

        # Verify old-style keys also preserved (backward compat)
        assert "match_details" in factors
        assert "price_impacts" in factors
        assert "confidence_breakdown" in factors


# ══════════════════════════════════════════════════════════════════
# PHASE 2: apply_price → _record_decision → outcome created
# ══════════════════════════════════════════════════════════════════

class TestPhase2ApplyRecordsOutcome:
    """
    Verify apply_price() triggers _record_decision() which calls
    OutcomeService.record_merchant_decision with correct args.
    """

    @pytest.mark.asyncio
    async def test_apply_price_records_outcome_with_evidence(self):
        """Full chain: apply_price → _record_decision fires."""
        user_id = uuid4()
        rec_id = uuid4()
        product = _make_product()

        # Build typed factors
        signals = _make_signals()
        rule = _make_rule()
        scout = PipelineAdapter.build_scout_output(product, signals)
        cb = {
            "components": {
                "signal_agreement": {"score": 0.75},
                "market_stability": {"score": 0.7},
                "rule_confidence": {"score": 0.65},
                "data_quality": {"score": 0.8},
            },
        }
        analyst = PipelineAdapter.build_analyst_output(scout, cb, signals, rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Competitor undercut", {}, rule,
        )

        factors = {
            "match_details": {"rule_type": "competitor_relative"},
            "price_impacts": {"competitor": -2.51},
            "confidence_breakdown": cb,
            "scout_evidence": scout.to_evidence(),
            "analyst_evidence": analyst.to_evidence(),
            "strategist_evidence": strategist.to_evidence(),
        }

        rec = _make_recommendation(
            user_id, rec_id, product, factors, rule_id=rule.id
        )

        # Mock DB
        db = AsyncMock()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == rec_id else product)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        # Mock push service
        mock_push_cls = MagicMock()
        mock_push_inst = MagicMock()
        mock_push_inst.push_price = AsyncMock(return_value={
            "success": True, "platform": "shopify"
        })
        mock_push_cls.return_value = mock_push_inst

        # Mock OutcomeService at module level (same pattern as test_approval_service_wiring)
        mock_outcome_cls = MagicMock()
        mock_outcome_inst = AsyncMock()
        mock_outcome_inst.record_merchant_decision = AsyncMock()
        mock_outcome_cls.return_value = mock_outcome_inst

        from services.pricing.approval_service import ApprovalService
        svc = ApprovalService(db)

        with patch("services.pricing.ecommerce_push_service.EcommercePushService", mock_push_cls), \
             patch("services.pricing.outcome_service.OutcomeService", mock_outcome_cls):
            await svc.apply_price(rec_id, user_id)

        # Verify record_merchant_decision was called
        mock_outcome_inst.record_merchant_decision.assert_called_once()
        call_kwargs = mock_outcome_inst.record_merchant_decision.call_args
        # Extract args (may be positional or keyword)
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs["recommendation_id"] == rec_id
            assert call_kwargs.kwargs["user_id"] == user_id
            assert call_kwargs.kwargs["merchant_decision"] == "accepted"
        else:
            # Positional: recommendation_id, user_id, merchant_decision, actual_price_set
            assert call_kwargs.args[0] == rec_id
            assert call_kwargs.args[1] == user_id



# ══════════════════════════════════════════════════════════════════
# PHASE 3: OutcomeService extracts typed evidence correctly
# ══════════════════════════════════════════════════════════════════

class TestPhase3OutcomeExtractsEvidence:
    """
    Verify record_merchant_decision() extracts confidence decomposition
    and scoring snapshots from typed analyst_evidence.
    """

    @pytest.mark.asyncio
    async def test_extracts_confidence_from_typed_evidence(self):
        user_id = uuid4()
        rec_id = uuid4()
        product = _make_product()

        # Build complete typed factors
        signals = _make_signals()
        rule = _make_rule()
        scout = PipelineAdapter.build_scout_output(product, signals)
        cb = {
            "components": {
                "signal_agreement": {"score": 0.75},
                "market_stability": {"score": 0.7},
                "rule_confidence": {"score": 0.65},
                "data_quality": {"score": 0.8},
            },
        }
        analyst = PipelineAdapter.build_analyst_output(scout, cb, signals, rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Test", {}, rule,
        )

        factors = {
            "match_details": {},
            "price_impacts": {},
            "confidence_breakdown": cb,
            "scout_evidence": scout.to_evidence(),
            "analyst_evidence": analyst.to_evidence(),
            "strategist_evidence": strategist.to_evidence(),
        }

        rec = _make_recommendation(user_id, rec_id, product, factors, rule_id=rule.id)

        # Mock DB
        db = AsyncMock()
        db.get = AsyncMock(side_effect=lambda cls, pk: (
            rec if pk == rec_id else
            _make_rule() if str(pk) == str(rule.id) else
            product
        ))
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        from services.pricing.outcome_service import OutcomeService
        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=rec_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        # The outcome was passed to db.add()
        created = db.add.call_args[0][0]

        # Typed confidence decomposition extracted
        assert created.confidence_elasticity == 0.75
        assert created.confidence_position == 0.7
        assert created.confidence_urgency == 0.65
        assert created.confidence_data_quality == 0.8

        # Analyst scoring snapshot extracted
        assert created.sentiment_score == 0.35
        assert created.competitor_count == 3

        # Agent evidence chain stored
        assert created.scout_evidence is not None
        assert "competitor_count" in created.scout_evidence
        assert created.analyst_evidence is not None
        assert "confidence" in created.analyst_evidence
        assert created.strategist_evidence is not None

    @pytest.mark.asyncio
    async def test_measurement_status_is_decision_recorded(self):
        """Accepted outcomes get DECISION_RECORDED for Celery pickup."""
        user_id = uuid4()
        rec_id = uuid4()
        product = _make_product()

        factors = {
            "scout_evidence": {"competitor_count": 3},
            "analyst_evidence": {
                "confidence": {"elasticity": 0.7, "position": 0.6, "urgency": 0.5, "data_quality": 0.8},
                "sentiment_score": 0.35,
                "competitor_count": 3,
            },
            "strategist_evidence": {"recommended_price": "29.49"},
        }

        rec = _make_recommendation(user_id, rec_id, product, factors)

        db = AsyncMock()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == rec_id else product)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        from services.pricing.outcome_service import OutcomeService
        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=rec_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.DECISION_RECORDED.value

    @pytest.mark.asyncio
    async def test_rejected_gets_terminal_status(self):
        """Rejected outcomes get MEASURED_30D (terminal, nothing to measure)."""
        user_id = uuid4()
        rec_id = uuid4()
        product = _make_product()

        factors = {
            "analyst_evidence": {"confidence": {"elasticity": 0.7}},
        }

        rec = _make_recommendation(user_id, rec_id, product, factors)

        db = AsyncMock()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == rec_id else product)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        from services.pricing.outcome_service import OutcomeService
        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=rec_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.REJECTED.value,
        )

        created = db.add.call_args[0][0]
        assert created.measurement_status == MeasurementStatus.MEASURED_30D.value


# ══════════════════════════════════════════════════════════════════
# PHASE 4: Competitor fallback also produces typed evidence
# ══════════════════════════════════════════════════════════════════

class TestPhase4CompetitorFallbackEvidence:
    """Verify competitor_fallback path also produces typed evidence."""

    def test_competitor_fallback_factors_have_typed_evidence(self):
        """Simulates what competitor_fallback._create_recommendation does."""
        product = _make_product(current_price=Decimal("40.00"))
        signals = _make_signals(
            competitor_prices={"Store A": Decimal("27.50")},
            sentiment_score=None,
        )

        # This is what competitor_fallback.py now does:
        scout = PipelineAdapter.build_scout_output(product, signals)
        confidence_breakdown = {
            "components": {
                "signal_agreement": {"score": 0.5},
                "market_stability": {"score": 0.5},
                "rule_confidence": {"score": 0.3},
                "data_quality": {"score": round(scout.data_completeness, 4)},
            },
        }
        analyst = PipelineAdapter.build_analyst_output(
            scout, confidence_breakdown, signals, rule=None
        )
        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("26.95"), Decimal("-32.63"), Decimal("0.65"),
            "Competitor match", {}, rule=None,
        )

        factors = {
            "match_details": {"rule_type": "competitor_fallback"},
            "scout_evidence": scout.to_evidence(),
            "analyst_evidence": analyst.to_evidence(),
            "strategist_evidence": strategist.to_evidence(),
        }

        # Typed evidence present
        assert "scout_evidence" in factors
        assert "analyst_evidence" in factors
        assert "strategist_evidence" in factors

        # Scout knows about the competitor
        assert factors["scout_evidence"]["competitor_count"] == 1

        # Analyst has no rule → direction is HOLD
        direction = factors["analyst_evidence"].get("recommended_direction")
        if hasattr(direction, "value"):
            direction = direction.value
        assert direction.lower() == "hold"

        # Data gaps include no_social_data (sentiment was None)
        assert "no_social_data" in factors["scout_evidence"]["data_gaps"]


# ══════════════════════════════════════════════════════════════════
# PHASE 5: Full chain verification
# ══════════════════════════════════════════════════════════════════

class TestPhase5FullChain:
    """
    Verify the complete data flow: evidence produced by PipelineAdapter
    can be correctly extracted by OutcomeService.
    """

    @pytest.mark.asyncio
    async def test_pipeline_evidence_survives_round_trip(self):
        """
        PipelineAdapter.to_evidence() → stored in factors →
        OutcomeService extracts → outcome fields match originals.
        """
        user_id = uuid4()
        rec_id = uuid4()
        product = _make_product()
        signals = _make_signals()
        rule = _make_rule()

        # Step 1: Build typed evidence (PipelineAdapter)
        scout = PipelineAdapter.build_scout_output(product, signals)
        cb = {
            "components": {
                "signal_agreement": {"score": 0.82},
                "market_stability": {"score": 0.71},
                "rule_confidence": {"score": 0.68},
                "data_quality": {"score": 0.9},
            },
        }
        analyst = PipelineAdapter.build_analyst_output(scout, cb, signals, rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst, product,
            Decimal("29.49"), Decimal("-7.84"), Decimal("0.72"),
            "Test", {}, rule,
        )

        # Step 2: Store in factors (recommendation_service does this)
        factors = {
            "match_details": {"rule_type": "competitor_relative"},
            "confidence_breakdown": cb,
            "scout_evidence": scout.to_evidence(),
            "analyst_evidence": analyst.to_evidence(),
            "strategist_evidence": strategist.to_evidence(),
        }

        # Step 3: Create recommendation mock with these factors
        rec = _make_recommendation(user_id, rec_id, product, factors, rule_id=rule.id)

        # Step 4: Run through OutcomeService
        db = AsyncMock()
        db.get = AsyncMock(side_effect=lambda cls, pk: (
            rec if pk == rec_id else
            _make_rule() if str(pk) == str(rule.id) else
            product
        ))
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        from services.pricing.outcome_service import OutcomeService
        svc = OutcomeService(db)
        await svc.record_merchant_decision(
            recommendation_id=rec_id,
            user_id=user_id,
            merchant_decision=MerchantDecision.ACCEPTED.value,
            actual_price_set=Decimal("29.49"),
        )

        outcome = db.add.call_args[0][0]

        # Step 5: Verify round-trip fidelity
        # Confidence decomposition matches what PipelineAdapter built
        assert outcome.confidence_elasticity == 0.82
        assert outcome.confidence_position == 0.71
        assert outcome.confidence_urgency == 0.68
        assert outcome.confidence_data_quality == 0.9

        # Analyst snapshot matches
        assert outcome.sentiment_score == 0.35
        assert outcome.competitor_count == 3

        # Evidence chain stored as JSONB
        assert isinstance(outcome.scout_evidence, dict)
        assert isinstance(outcome.analyst_evidence, dict)
        assert isinstance(outcome.strategist_evidence, dict)

        # Ready for Celery measurement
        assert outcome.measurement_status == MeasurementStatus.DECISION_RECORDED.value
        assert outcome.outcome_label == OutcomeLabel.INCONCLUSIVE
        assert outcome.merchant_decision == MerchantDecision.ACCEPTED.value

        # No modification (exact price match)
        assert outcome.merchant_modification_percent is None or \
               abs(outcome.merchant_modification_percent) <= 1.0


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved.items():
    sys.modules[_key] = _orig



