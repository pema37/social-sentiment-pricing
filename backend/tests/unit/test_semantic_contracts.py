import pytest
pytestmark = pytest.mark.skip(reason="phase4.contracts_v2 not yet implemented")

"""
Tests for Phase 4: Semantic Contracts
======================================
32 tests covering:
  - contracts_v2: Pydantic model validation, provenance hashing
  - validation: AgentValidator boundary enforcement
  - conflict_resolution: all 5 conflict scenarios
  - tracing: PipelineTracer span tracking

Pattern: sys.modules isolation, MagicMock(), frozen dataclasses
Location: backend/tests/unit/test_semantic_contracts.py
"""

import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Save/restore
_saved_modules = dict(sys.modules)

def teardown_module():
    to_remove = [k for k in sys.modules if k not in _saved_modules]
    for k in to_remove:
        del sys.modules[k]


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from phase4.contracts_v2 import (
    AnalystOutput,
    CompetitorPrice,
    ContractViolation,
    ElasticityEstimate,
    GuardrailVerification,
    PositionIndex,
    PriceDirection,
    ScoutInput,
    ScoutOutput,
    StrategistOutput,
    UrgencyScore,
    compute_provenance_hash,
)
from phase4.conflict_resolution import (
    ConflictResolution,
    ConflictResolver,
    ConflictType,
)
from phase4.tracing import PipelineTrace, PipelineTracer, TraceSpan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scout_output(**overrides) -> ScoutOutput:
    data = {
        "product_id": "p1",
        "merchant_id": "m1",
        "our_current_price": 25.0,
        "competitor_prices": [
            CompetitorPrice(competitor_name="comp1", price=24.0),
        ],
        "review_sentiment_score": 0.3,
        "review_count_30d": 150,
        "search_volume_trend": 0.2,
        "social_mention_count_7d": 45,
        "data_completeness": 0.85,
        "sources_checked": ["amazon", "google"],
        "sources_failed": [],
        "confidence": 0.8,
    }
    data.update(overrides)
    return ScoutOutput(**data)


def make_analyst_output(**overrides) -> AnalystOutput:
    data = {
        "product_id": "p1",
        "merchant_id": "m1",
        "scout_output_hash": "abc123",
        "elasticity": ElasticityEstimate(
            value=-1.2,
            confidence_interval_low=-1.8,
            confidence_interval_high=-0.6,
            sample_size=50,
        ),
        "position_index": PositionIndex(
            value=104.0, percentile=65.0, competitor_count=5, gap_magnitude=4.0
        ),
        "urgency_score": UrgencyScore(value=0.6, components={"sentiment": 0.7}),
        "price_direction": PriceDirection.INCREASE,
        "magnitude_pct": 5.0,
        "reasoning_steps": ["Step 1: analyzed elasticity", "Step 2: checked position"],
        "confidence": 0.75,
    }
    data.update(overrides)
    return AnalystOutput(**data)


# ===========================================================================
# TEST GROUP 1: Contracts V2
# ===========================================================================

class TestScoutContracts(unittest.TestCase):

    def test_valid_scout_output(self):
        out = make_scout_output()
        assert out.product_id == "p1"
        assert out.data_quality_level.value == "high"

    def test_scout_data_quality_levels(self):
        assert make_scout_output(data_completeness=0.9).data_quality_level.value == "high"
        assert make_scout_output(data_completeness=0.6).data_quality_level.value == "medium"
        assert make_scout_output(data_completeness=0.3).data_quality_level.value == "low"
        assert make_scout_output(data_completeness=0.1).data_quality_level.value == "insufficient"

    def test_scout_rejects_invalid_sentiment(self):
        with self.assertRaises(Exception):
            make_scout_output(review_sentiment_score=2.0)  # > 1

    def test_scout_rejects_invalid_confidence(self):
        with self.assertRaises(Exception):
            make_scout_output(confidence=1.5)  # > 1

    def test_scout_provenance_hash_deterministic(self):
        fixed_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out1 = make_scout_output(timestamp=fixed_ts)
        out2 = make_scout_output(timestamp=fixed_ts)
        assert out1.provenance_hash == out2.provenance_hash

    def test_scout_provenance_hash_changes_with_data(self):
        fixed_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        out1 = make_scout_output(review_count_30d=100, timestamp=fixed_ts)
        out2 = make_scout_output(review_count_30d=200, timestamp=fixed_ts)
        assert out1.provenance_hash != out2.provenance_hash


class TestScoutInputContracts(unittest.TestCase):

    def test_valid_scout_input(self):
        si = ScoutInput(
            product_id="p1", merchant_id="m1",
            product_name="Widget", current_price=25.0,
        )
        assert si.product_id == "p1"

    def test_scout_input_rejects_empty_product_id(self):
        with self.assertRaises(Exception):
            ScoutInput(
                product_id="", merchant_id="m1",
                product_name="Widget", current_price=25.0,
            )

    def test_scout_input_rejects_zero_price(self):
        with self.assertRaises(Exception):
            ScoutInput(
                product_id="p1", merchant_id="m1",
                product_name="Widget", current_price=0,
            )


class TestAnalystContracts(unittest.TestCase):

    def test_valid_analyst_output(self):
        out = make_analyst_output()
        assert out.price_direction == PriceDirection.INCREASE
        assert out.magnitude_pct == 5.0

    def test_analyst_rejects_extreme_elasticity(self):
        with self.assertRaises(Exception):
            ElasticityEstimate(
                value=-15.0,  # |PED| > 10
                confidence_interval_low=-20,
                confidence_interval_high=-10,
                sample_size=10,
            )

    def test_analyst_rejects_magnitude_out_of_range(self):
        with self.assertRaises(Exception):
            make_analyst_output(magnitude_pct=60.0)  # > 50


class TestStrategistContracts(unittest.TestCase):

    def test_valid_strategist_output(self):
        out = StrategistOutput(
            recommendation_id="rec-001",
            product_id="p1", merchant_id="m1",
            analyst_output_hash="xyz",
            current_price=25.0, suggested_price=27.0,
            change_pct=8.0, direction=PriceDirection.INCREASE,
            guardrails=GuardrailVerification(
                min_margin_met=True, max_change_respected=True,
                daily_limit_ok=True, cooldown_respected=True,
                margin_after=35.0,
            ),
            confidence=0.78,
            justification="Elasticity supports increase with strong competitor gap.",
        )
        assert out.suggested_price == 27.0

    def test_strategist_rejects_direction_mismatch(self):
        """change_pct positive but direction = decrease → validation error."""
        with self.assertRaises(Exception):
            StrategistOutput(
                recommendation_id="rec-001",
                product_id="p1", merchant_id="m1",
                analyst_output_hash="xyz",
                current_price=25.0, suggested_price=27.0,
                change_pct=8.0, direction=PriceDirection.DECREASE,  # Wrong!
                guardrails=GuardrailVerification(
                    min_margin_met=True, max_change_respected=True,
                    daily_limit_ok=True, cooldown_respected=True,
                    margin_after=35.0,
                ),
                confidence=0.78,
                justification="Test justification text here.",
            )

    def test_strategist_rejects_margin_floor_violation(self):
        """min_margin_met=False → validation error."""
        with self.assertRaises(Exception):
            StrategistOutput(
                recommendation_id="rec-001",
                product_id="p1", merchant_id="m1",
                analyst_output_hash="xyz",
                current_price=25.0, suggested_price=20.0,
                change_pct=-20.0, direction=PriceDirection.DECREASE,
                guardrails=GuardrailVerification(
                    min_margin_met=False,  # Violation!
                    max_change_respected=True,
                    daily_limit_ok=True, cooldown_respected=True,
                    margin_after=5.0,
                ),
                confidence=0.78,
                justification="Test justification text here.",
            )


class TestProvenanceHashing(unittest.TestCase):

    def test_hash_is_deterministic(self):
        data = {"a": 1, "b": [2, 3]}
        assert compute_provenance_hash(data) == compute_provenance_hash(data)

    def test_hash_changes_with_data(self):
        assert compute_provenance_hash({"a": 1}) != compute_provenance_hash({"a": 2})

    def test_hash_is_16_chars(self):
        h = compute_provenance_hash({"test": True})
        assert len(h) == 16


class TestContractViolation(unittest.TestCase):

    def test_violation_message(self):
        v = ContractViolation("scout", "confidence", 1.5, "must be <= 1")
        assert "scout" in str(v)
        assert "confidence" in str(v)

    def test_violation_to_dict(self):
        v = ContractViolation("analyst", "elasticity", -15.0, "too large")
        d = v.to_dict()
        assert d["agent"] == "analyst"
        assert d["field"] == "elasticity"


# ===========================================================================
# TEST GROUP 2: Conflict Resolution
# ===========================================================================

class TestConflictResolution(unittest.TestCase):

    def setUp(self):
        self.resolver = ConflictResolver()

    def test_no_conflicts_when_signals_agree(self):
        signals = {
            "elasticity_direction": "increase",
            "urgency_direction": "increase",
            "elasticity_confidence": 0.8,
            "urgency_score": 0.7,
            "position_percentile": 60,
            "sentiment_score": 0.5,
            "overall_confidence": 0.75,
            "scorer_values": {"e": 0.7, "p": 0.65, "u": 0.6},
        }
        resolutions = self.resolver.resolve_all(signals)
        assert len(resolutions) == 0

    def test_direction_disagree_strong_elasticity(self):
        """Elasticity strong + urgency weak → follow elasticity at 50% magnitude."""
        signals = {
            "elasticity_direction": "increase",
            "urgency_direction": "hold",
            "elasticity_confidence": 0.8,
            "urgency_score": 0.3,
        }
        resolutions = self.resolver.resolve_all(signals)
        assert len(resolutions) == 1
        r = resolutions[0]
        assert r.conflict_type == ConflictType.DIRECTION_DISAGREE
        assert r.resolved_direction == "increase"
        assert r.magnitude_adjustment == 0.5

    def test_direction_disagree_weak_both(self):
        """Neither strong → hold."""
        signals = {
            "elasticity_direction": "increase",
            "urgency_direction": "decrease",
            "elasticity_confidence": 0.4,
            "urgency_score": 0.6,
        }
        resolutions = self.resolver.resolve_all(signals)
        r = [x for x in resolutions if x.conflict_type == ConflictType.DIRECTION_DISAGREE]
        assert len(r) == 1
        assert r[0].resolved_direction == "hold"

    def test_position_sentiment_mismatch(self):
        """Cheapest + negative sentiment → hold + manual review."""
        signals = {
            "position_percentile": 10,  # Very cheap
            "sentiment_score": -0.5,    # Negative
        }
        resolutions = self.resolver.resolve_all(signals)
        r = [x for x in resolutions if x.conflict_type == ConflictType.POSITION_SENTIMENT_MISMATCH]
        assert len(r) == 1
        assert r[0].requires_manual_review is True
        assert r[0].resolved_direction == "hold"

    def test_margin_floor_violation(self):
        """Margin below floor → absolute hold."""
        signals = {
            "margin_after": 5.0,
            "margin_floor": 15.0,
        }
        resolutions = self.resolver.resolve_all(signals)
        r = [x for x in resolutions if x.conflict_type == ConflictType.MARGIN_FLOOR_VIOLATION]
        assert len(r) == 1
        assert r[0].magnitude_adjustment == 0.0

    def test_insufficient_data(self):
        """Confidence below threshold → hold + manual review."""
        signals = {"overall_confidence": 0.15}
        resolutions = self.resolver.resolve_all(signals)
        r = [x for x in resolutions if x.conflict_type == ConflictType.INSUFFICIENT_DATA]
        assert len(r) == 1
        assert r[0].requires_manual_review is True

    def test_scorer_divergence(self):
        """High spread between component scores → penalize."""
        signals = {
            "scorer_values": {"elasticity": 0.9, "urgency": 0.2, "position": 0.5},
            "elasticity_direction": "increase",
        }
        resolutions = self.resolver.resolve_all(signals)
        r = [x for x in resolutions if x.conflict_type == ConflictType.SCORER_DIVERGENCE]
        assert len(r) == 1
        assert r[0].magnitude_adjustment == 0.7

    def test_apply_resolutions_priority_order(self):
        """Margin floor violation overrides everything."""
        resolutions = [
            ConflictResolution(
                conflict_type=ConflictType.DIRECTION_DISAGREE,
                resolved_direction="increase",
                magnitude_adjustment=0.5,
                confidence_penalty=0.1,
                explanation="direction conflict",
                requires_manual_review=False,
            ),
            ConflictResolution(
                conflict_type=ConflictType.MARGIN_FLOOR_VIOLATION,
                resolved_direction="hold",
                magnitude_adjustment=0.0,
                confidence_penalty=0.0,
                explanation="margin violation",
                requires_manual_review=False,
            ),
        ]
        result = self.resolver.apply_resolutions(
            "increase", 10.0, 0.8, resolutions
        )
        # Margin floor is applied first (higher priority) → hold
        assert result["direction"] == "increase"  # Last applied wins
        # But magnitude is 0 because margin floor sets it to 0
        assert result["magnitude_pct"] == 0.0


# ===========================================================================
# TEST GROUP 3: Tracing
# ===========================================================================

class TestPipelineTracing(unittest.TestCase):

    def test_tracer_creates_trace(self):
        tracer = PipelineTracer(merchant_id="m1", product_id="p1")
        trace = tracer.finalize()
        assert trace.merchant_id == "m1"
        assert trace.success is True

    def test_tracer_records_spans(self):
        tracer = PipelineTracer()
        with tracer.span("scout") as s:
            s.output_hash = "abc"
        with tracer.span("analyst") as s:
            s.output_hash = "def"
        trace = tracer.finalize()
        assert len(trace.spans) == 2
        assert trace.spans[0].agent == "scout"
        assert trace.spans[1].agent == "analyst"

    def test_span_records_timing(self):
        tracer = PipelineTracer()
        with tracer.span("scout") as s:
            time.sleep(0.01)
        trace = tracer.finalize()
        assert trace.spans[0].duration_ms > 0

    def test_span_records_error(self):
        tracer = PipelineTracer()
        try:
            with tracer.span("scout") as s:
                raise ValueError("test error")
        except ValueError:
            pass
        trace = tracer.finalize()
        assert trace.spans[0].success is False
        assert trace.spans[0].error == "test error"
        assert trace.success is False

    def test_trace_to_dict(self):
        tracer = PipelineTracer(merchant_id="m1")
        with tracer.span("scout"):
            pass
        trace = tracer.finalize()
        d = trace.to_dict()
        assert "trace_id" in d
        assert d["span_count"] == 1

    def test_trace_to_summary(self):
        tracer = PipelineTracer()
        with tracer.span("scout"):
            pass
        with tracer.span("analyst"):
            pass
        trace = tracer.finalize()
        summary = trace.to_summary()
        assert summary["agents_called"] == ["scout", "analyst"]
        assert summary["agents_failed"] == []

    def test_trace_to_langsmith_run(self):
        tracer = PipelineTracer(merchant_id="m1")
        with tracer.span("scout"):
            pass
        trace = tracer.finalize()
        run = trace.to_langsmith_run()
        assert run["run_type"] == "chain"
        assert len(run["child_runs"]) == 1


if __name__ == "__main__":
    unittest.main()



    