"""
Tests for Agent Semantic Contracts (schemas/agent_contracts.py).

Covers:
1. ScoutOutput — construction, validation, defaults, evidence serialization
2. AnalystOutput — confidence decomposition, direction, evidence
3. StrategistOutput — guardrails, preference prior, direction validation, to_recommendation_kwargs
4. PipelineResult — end-to-end trace, store_evidence
5. Edge cases — missing data, boundary values, validator behavior

Place at: backend/tests/unit/test_agent_contracts.py
Run: pytest tests/unit/test_agent_contracts.py -v
"""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from schemas.agent_contracts import (
    ScoutOutput,
    CompetitorPrice,
    SentimentSnapshot,
    PriceHistoryPoint,
    AnalystOutput,
    ElasticityEstimate,
    ConfidenceDecomposition,
    StrategistOutput,
    GuardrailCheck,
    PipelineResult,
    PriceDirection,
    UrgencyLevel,
    DataSource,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def product_id():
    return uuid4()


@pytest.fixture
def now():
    return datetime.now()


@pytest.fixture
def sample_competitors():
    return [
        CompetitorPrice(
            competitor_name="Amazon",
            price=Decimal("29.99"),
            url="https://amazon.com/product/123",
            scraped_at=datetime.now(),
            is_on_sale=False,
        ),
        CompetitorPrice(
            competitor_name="Walmart",
            price=Decimal("27.50"),
            scraped_at=datetime.now(),
            is_on_sale=True,
            sale_price=Decimal("25.00"),
        ),
    ]


@pytest.fixture
def sample_sentiment():
    return SentimentSnapshot(
        overall_score=0.35,
        mention_count=127,
        positive_ratio=0.55,
        negative_ratio=0.15,
        neutral_ratio=0.30,
        trending_topics=["quality", "shipping"],
        crisis_detected=False,
        source_breakdown={"twitter": 80, "reddit": 47},
    )


@pytest.fixture
def scout_output(product_id, sample_competitors, sample_sentiment):
    return ScoutOutput(
        product_id=product_id,
        competitors=sample_competitors,
        competitor_count=2,
        our_price=Decimal("32.00"),
        our_position="above_median",
        competitive_position_index=0.75,
        sentiment=sample_sentiment,
        data_completeness=0.85,
        data_sources=[DataSource.COMPETITOR_SCRAPE, DataSource.SOCIAL_SENTIMENT],
        data_gaps=["no_price_history"],
    )


@pytest.fixture
def analyst_output(product_id, now):
    return AnalystOutput(
        product_id=product_id,
        scout_scouted_at=now,
        elasticity=ElasticityEstimate(
            point_estimate=-1.3,
            confidence_interval_low=-1.8,
            confidence_interval_high=-0.8,
            method="bayesian_hierarchical",
            prior_source="category_benchmark",
            sample_size=42,
        ),
        confidence=ConfidenceDecomposition(
            elasticity=0.72,
            position=0.85,
            urgency=0.60,
            data_quality=0.80,
        ),
        urgency_level=UrgencyLevel.MEDIUM,
        urgency_score=0.55,
        urgency_reasons=["competitor_undercut_15%"],
        sentiment_score=0.35,
        sentiment_impact="supports_increase",
        competitive_position_index=0.75,
        market_pressure="overpriced",
        recommended_direction=PriceDirection.DECREASE,
        direction_reasoning="Competitor undercut by 15% with stable demand; reducing price to protect market share.",
        data_completeness=0.85,
        competitor_count=2,
    )


@pytest.fixture
def strategist_output(product_id, now):
    return StrategistOutput(
        product_id=product_id,
        scout_scouted_at=now,
        analyst_analyzed_at=now,
        current_price=Decimal("32.00"),
        recommended_price=Decimal("29.49"),
        change_percent=Decimal("-7.84"),
        change_direction=PriceDirection.DECREASE,
        compare_at_price=Decimal("32.00"),
        confidence_score=0.74,
        confidence_decomposition=ConfidenceDecomposition(
            elasticity=0.72,
            position=0.85,
            urgency=0.60,
            data_quality=0.80,
        ),
        reasoning="Reducing price by 7.84% to match competitive pressure while maintaining margin above floor.",
        factors={
            "competitor_gap": -15.0,
            "sentiment_impact": "positive",
            "elasticity_estimate": -1.3,
        },
        guardrails_applied=[
            GuardrailCheck(
                name="max_change_percent",
                passed=True,
                original_value="-7.84",
                reason="Within 10% max change limit",
            ),
            GuardrailCheck(
                name="min_price_floor",
                passed=True,
                original_value="29.49",
                reason="Above minimum price of $25.00",
            ),
        ],
        was_clamped=False,
        preference_prior_applied=0.85,
        pre_calibration_change_percent=Decimal("-9.22"),
        pipeline_source="full_pipeline",
    )


# ══════════════════════════════════════════════════════════════════
# SCOUT OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════

class TestScoutOutput:

    def test_basic_construction(self, scout_output):
        assert scout_output.competitor_count == 2
        assert scout_output.our_price == Decimal("32.00")
        assert scout_output.data_completeness == 0.85
        assert len(scout_output.data_gaps) == 1

    def test_competitor_details(self, scout_output):
        amazon = scout_output.competitors[0]
        assert amazon.competitor_name == "Amazon"
        assert amazon.price == Decimal("29.99")
        assert amazon.is_on_sale is False

        walmart = scout_output.competitors[1]
        assert walmart.is_on_sale is True
        assert walmart.sale_price == Decimal("25.00")

    def test_sentiment_present(self, scout_output):
        assert scout_output.sentiment is not None
        assert scout_output.sentiment.overall_score == 0.35
        assert scout_output.sentiment.mention_count == 127
        assert not scout_output.sentiment.crisis_detected

    def test_sentiment_optional(self, product_id):
        """Scout should work without sentiment data."""
        scout = ScoutOutput(
            product_id=product_id,
            our_price=Decimal("10.00"),
            data_completeness=0.4,
        )
        assert scout.sentiment is None
        assert scout.competitor_count == 0
        assert scout.competitors == []

    def test_to_evidence_serializable(self, scout_output):
        """Evidence must be JSON-serializable for JSONB storage."""
        evidence = scout_output.to_evidence()
        assert isinstance(evidence, dict)
        assert evidence["competitor_count"] == 2
        assert evidence["data_completeness"] == 0.85
        # Decimal should be serialized
        assert isinstance(evidence["our_price"], str)

    def test_data_completeness_bounds(self, product_id):
        """data_completeness must be 0.0 to 1.0."""
        with pytest.raises(Exception):
            ScoutOutput(
                product_id=product_id,
                our_price=Decimal("10.00"),
                data_completeness=1.5,
            )

        with pytest.raises(Exception):
            ScoutOutput(
                product_id=product_id,
                our_price=Decimal("10.00"),
                data_completeness=-0.1,
            )

    def test_empty_competitors(self, product_id):
        """Scout should handle zero competitors gracefully."""
        scout = ScoutOutput(
            product_id=product_id,
            our_price=Decimal("50.00"),
            data_completeness=0.3,
            data_gaps=["no_competitor_prices", "no_social_data"],
        )
        assert scout.competitor_count == 0
        assert scout.competitors == []
        assert len(scout.data_gaps) == 2

    def test_crisis_sentiment(self, product_id):
        """Crisis detection flag should propagate."""
        crisis_sentiment = SentimentSnapshot(
            overall_score=-0.8,
            mention_count=500,
            positive_ratio=0.05,
            negative_ratio=0.85,
            neutral_ratio=0.10,
            crisis_detected=True,
            crisis_severity=0.9,
            source_breakdown={"twitter": 400, "reddit": 100},
        )
        scout = ScoutOutput(
            product_id=product_id,
            our_price=Decimal("10.00"),
            sentiment=crisis_sentiment,
            data_completeness=0.9,
        )
        assert scout.sentiment.crisis_detected is True
        assert scout.sentiment.crisis_severity == 0.9


# ══════════════════════════════════════════════════════════════════
# ANALYST OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════

class TestAnalystOutput:

    def test_basic_construction(self, analyst_output):
        assert analyst_output.urgency_level == UrgencyLevel.MEDIUM
        assert analyst_output.urgency_score == 0.55
        assert analyst_output.recommended_direction == PriceDirection.DECREASE

    def test_confidence_decomposition_overall(self, analyst_output):
        """Test weighted overall confidence calculation."""
        cd = analyst_output.confidence
        expected = (
            0.72 * 0.30  # elasticity
            + 0.85 * 0.25  # position
            + 0.60 * 0.20  # urgency
            + 0.80 * 0.25  # data_quality
        )
        assert abs(cd.overall - expected) < 0.0001

    def test_confidence_decomposition_bounds(self):
        """All components must be 0.0 to 1.0."""
        with pytest.raises(Exception):
            ConfidenceDecomposition(
                elasticity=1.5,
                position=0.5,
                urgency=0.5,
                data_quality=0.5,
            )

    def test_elasticity_estimate(self, analyst_output):
        e = analyst_output.elasticity
        assert e.point_estimate == -1.3
        assert e.method == "bayesian_hierarchical"
        assert e.sample_size == 42

    def test_no_sentiment(self, product_id, now):
        """Analyst should work when Scout had no sentiment."""
        analyst = AnalystOutput(
            product_id=product_id,
            scout_scouted_at=now,
            elasticity=ElasticityEstimate(point_estimate=-0.8),
            confidence=ConfidenceDecomposition(
                elasticity=0.5,
                position=0.6,
                urgency=0.3,
                data_quality=0.4,
            ),
            urgency_level=UrgencyLevel.LOW,
            urgency_score=0.2,
            competitive_position_index=0.5,
            recommended_direction=PriceDirection.HOLD,
            direction_reasoning="Insufficient data to recommend a change.",
            data_completeness=0.4,
            competitor_count=0,
        )
        assert analyst.sentiment_score is None
        assert analyst.sentiment_impact is None

    def test_to_evidence_serializable(self, analyst_output):
        evidence = analyst_output.to_evidence()
        assert isinstance(evidence, dict)
        assert evidence["recommended_direction"] == "decrease"
        assert evidence["confidence"]["elasticity"] == 0.72


# ══════════════════════════════════════════════════════════════════
# STRATEGIST OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════

class TestStrategistOutput:

    def test_basic_construction(self, strategist_output):
        assert strategist_output.recommended_price == Decimal("29.49")
        assert strategist_output.change_direction == PriceDirection.DECREASE
        assert strategist_output.confidence_score == 0.74

    def test_guardrails_documented(self, strategist_output):
        assert len(strategist_output.guardrails_applied) == 2
        assert all(g.passed for g in strategist_output.guardrails_applied)
        assert strategist_output.was_clamped is False

    def test_preference_prior(self, strategist_output):
        """Merchant preference prior should be applied."""
        assert strategist_output.preference_prior_applied == 0.85
        assert strategist_output.pre_calibration_change_percent == Decimal("-9.22")

    def test_direction_validation_increase_positive(self, product_id, now):
        """INCREASE direction must have positive change_percent."""
        strat = StrategistOutput(
            product_id=product_id,
            scout_scouted_at=now,
            analyst_analyzed_at=now,
            current_price=Decimal("30.00"),
            recommended_price=Decimal("33.00"),
            change_percent=Decimal("10.00"),
            change_direction=PriceDirection.INCREASE,
            confidence_score=0.8,
            confidence_decomposition=ConfidenceDecomposition(
                elasticity=0.8, position=0.8, urgency=0.8, data_quality=0.8,
            ),
            reasoning="Test increase",
            factors={},
        )
        assert strat.change_percent == Decimal("10.00")

    def test_direction_validation_increase_rejects_negative(self, product_id, now):
        """INCREASE direction with negative change_percent must fail."""
        with pytest.raises(Exception):
            StrategistOutput(
                product_id=product_id,
                scout_scouted_at=now,
                analyst_analyzed_at=now,
                current_price=Decimal("30.00"),
                recommended_price=Decimal("27.00"),
                change_percent=Decimal("-10.00"),
                change_direction=PriceDirection.INCREASE,
                confidence_score=0.8,
                confidence_decomposition=ConfidenceDecomposition(
                    elasticity=0.8, position=0.8, urgency=0.8, data_quality=0.8,
                ),
                reasoning="Should fail",
                factors={},
            )

    def test_direction_validation_decrease_rejects_positive(self, product_id, now):
        """DECREASE direction with positive change_percent must fail."""
        with pytest.raises(Exception):
            StrategistOutput(
                product_id=product_id,
                scout_scouted_at=now,
                analyst_analyzed_at=now,
                current_price=Decimal("30.00"),
                recommended_price=Decimal("33.00"),
                change_percent=Decimal("10.00"),
                change_direction=PriceDirection.DECREASE,
                confidence_score=0.8,
                confidence_decomposition=ConfidenceDecomposition(
                    elasticity=0.8, position=0.8, urgency=0.8, data_quality=0.8,
                ),
                reasoning="Should fail",
                factors={},
            )

    def test_hold_allows_small_change(self, product_id, now):
        """HOLD should allow change_percent near zero."""
        strat = StrategistOutput(
            product_id=product_id,
            scout_scouted_at=now,
            analyst_analyzed_at=now,
            current_price=Decimal("30.00"),
            recommended_price=Decimal("30.10"),
            change_percent=Decimal("0.33"),
            change_direction=PriceDirection.HOLD,
            confidence_score=0.5,
            confidence_decomposition=ConfidenceDecomposition(
                elasticity=0.5, position=0.5, urgency=0.5, data_quality=0.5,
            ),
            reasoning="Essentially holding",
            factors={},
        )
        assert strat.change_direction == PriceDirection.HOLD

    def test_hold_rejects_large_change(self, product_id, now):
        """HOLD should reject change_percent > 0.5."""
        with pytest.raises(Exception):
            StrategistOutput(
                product_id=product_id,
                scout_scouted_at=now,
                analyst_analyzed_at=now,
                current_price=Decimal("30.00"),
                recommended_price=Decimal("33.00"),
                change_percent=Decimal("10.00"),
                change_direction=PriceDirection.HOLD,
                confidence_score=0.8,
                confidence_decomposition=ConfidenceDecomposition(
                    elasticity=0.8, position=0.8, urgency=0.8, data_quality=0.8,
                ),
                reasoning="Should fail",
                factors={},
            )

    def test_to_recommendation_kwargs(self, strategist_output):
        """Should map cleanly to PriceRecommendation columns."""
        kwargs = strategist_output.to_recommendation_kwargs()
        assert kwargs["product_id"] == strategist_output.product_id
        assert kwargs["current_price"] == Decimal("32.00")
        assert kwargs["recommended_price"] == Decimal("29.49")
        assert kwargs["change_percent"] == Decimal("-7.84")
        assert isinstance(kwargs["confidence_score"], Decimal)
        assert kwargs["reasoning"] == strategist_output.reasoning
        assert isinstance(kwargs["factors"], dict)

    def test_to_evidence_serializable(self, strategist_output):
        evidence = strategist_output.to_evidence()
        assert isinstance(evidence, dict)
        assert evidence["was_clamped"] is False
        assert evidence["preference_prior_applied"] == 0.85

    def test_guardrail_clamped(self, product_id, now):
        """When a guardrail clamps, was_clamped and raw_recommended_price should reflect it."""
        strat = StrategistOutput(
            product_id=product_id,
            scout_scouted_at=now,
            analyst_analyzed_at=now,
            current_price=Decimal("30.00"),
            recommended_price=Decimal("27.00"),
            change_percent=Decimal("-10.00"),
            change_direction=PriceDirection.DECREASE,
            confidence_score=0.6,
            confidence_decomposition=ConfidenceDecomposition(
                elasticity=0.6, position=0.6, urgency=0.6, data_quality=0.6,
            ),
            reasoning="Clamped from -15% to -10%",
            factors={},
            guardrails_applied=[
                GuardrailCheck(
                    name="max_change_percent",
                    passed=False,
                    original_value="-15.00",
                    clamped_value="-10.00",
                    reason="Exceeded 10% max change",
                ),
            ],
            was_clamped=True,
            raw_recommended_price=Decimal("25.50"),
        )
        assert strat.was_clamped is True
        assert strat.raw_recommended_price == Decimal("25.50")
        assert not strat.guardrails_applied[0].passed


# ══════════════════════════════════════════════════════════════════
# PIPELINE RESULT TESTS
# ══════════════════════════════════════════════════════════════════

class TestPipelineResult:

    def test_end_to_end(self, scout_output, analyst_output, strategist_output, product_id, now):
        result = PipelineResult(
            product_id=product_id,
            scout=scout_output,
            analyst=analyst_output,
            strategist=strategist_output,
            pipeline_started_at=now,
            pipeline_completed_at=now,
            total_time_ms=450,
        )
        assert result.success is True
        assert result.total_time_ms == 450

    def test_store_evidence(self, scout_output, analyst_output, strategist_output, product_id, now):
        """store_evidence() should return three dicts ready for record_outcome()."""
        result = PipelineResult(
            product_id=product_id,
            scout=scout_output,
            analyst=analyst_output,
            strategist=strategist_output,
            pipeline_started_at=now,
            pipeline_completed_at=now,
            total_time_ms=450,
        )
        evidence = result.store_evidence()

        assert "scout" in evidence
        assert "analyst" in evidence
        assert "strategist" in evidence

        # Each should be a dict (JSON-serializable)
        assert isinstance(evidence["scout"], dict)
        assert isinstance(evidence["analyst"], dict)
        assert isinstance(evidence["strategist"], dict)

        # Scout evidence should have competitor data
        assert evidence["scout"]["competitor_count"] == 2

        # Analyst evidence should have confidence decomposition
        assert evidence["analyst"]["confidence"]["elasticity"] == 0.72

        # Strategist evidence should have guardrails
        assert len(evidence["strategist"]["guardrails_applied"]) == 2

    def test_failed_pipeline(self, scout_output, analyst_output, strategist_output, product_id, now):
        result = PipelineResult(
            product_id=product_id,
            scout=scout_output,
            analyst=analyst_output,
            strategist=strategist_output,
            pipeline_started_at=now,
            pipeline_completed_at=now,
            total_time_ms=200,
            success=False,
            error="Analyst model timeout after 30s",
        )
        assert result.success is False
        assert "timeout" in result.error


# ══════════════════════════════════════════════════════════════════
# EDGE CASES & BOUNDARY VALUES
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_sentiment_score_bounds(self):
        """Sentiment score must be -1.0 to 1.0."""
        with pytest.raises(Exception):
            SentimentSnapshot(
                overall_score=1.5,
                mention_count=10,
                positive_ratio=0.5,
                negative_ratio=0.3,
                neutral_ratio=0.2,
            )

    def test_confidence_score_bounds_strategist(self, product_id, now):
        """Strategist confidence_score must be 0.0 to 1.0."""
        with pytest.raises(Exception):
            StrategistOutput(
                product_id=product_id,
                scout_scouted_at=now,
                analyst_analyzed_at=now,
                current_price=Decimal("30.00"),
                recommended_price=Decimal("28.00"),
                change_percent=Decimal("-6.67"),
                change_direction=PriceDirection.DECREASE,
                confidence_score=1.5,
                confidence_decomposition=ConfidenceDecomposition(
                    elasticity=0.5, position=0.5, urgency=0.5, data_quality=0.5,
                ),
                reasoning="Test",
                factors={},
            )

    def test_urgency_score_bounds(self, product_id, now):
        """Urgency score must be 0.0 to 1.0."""
        with pytest.raises(Exception):
            AnalystOutput(
                product_id=product_id,
                scout_scouted_at=now,
                elasticity=ElasticityEstimate(point_estimate=-1.0),
                confidence=ConfidenceDecomposition(
                    elasticity=0.5, position=0.5, urgency=0.5, data_quality=0.5,
                ),
                urgency_level=UrgencyLevel.HIGH,
                urgency_score=1.5,
                competitive_position_index=0.5,
                recommended_direction=PriceDirection.HOLD,
                direction_reasoning="Test",
                data_completeness=0.5,
                competitor_count=0,
            )

    def test_zero_price_edge(self, product_id, now):
        """Zero current price should be valid (free product)."""
        strat = StrategistOutput(
            product_id=product_id,
            scout_scouted_at=now,
            analyst_analyzed_at=now,
            current_price=Decimal("0.00"),
            recommended_price=Decimal("9.99"),
            change_percent=Decimal("0.00"),
            change_direction=PriceDirection.INCREASE,
            confidence_score=0.5,
            confidence_decomposition=ConfidenceDecomposition(
                elasticity=0.5, position=0.5, urgency=0.5, data_quality=0.5,
            ),
            reasoning="Introducing price for free product",
            factors={},
        )
        assert strat.current_price == Decimal("0.00")

    def test_all_urgency_levels(self, product_id, now):
        """Every UrgencyLevel should be valid."""
        for level in UrgencyLevel:
            analyst = AnalystOutput(
                product_id=product_id,
                scout_scouted_at=now,
                elasticity=ElasticityEstimate(point_estimate=-1.0),
                confidence=ConfidenceDecomposition(
                    elasticity=0.5, position=0.5, urgency=0.5, data_quality=0.5,
                ),
                urgency_level=level,
                urgency_score=0.5,
                competitive_position_index=0.5,
                recommended_direction=PriceDirection.HOLD,
                direction_reasoning="Test",
                data_completeness=0.5,
                competitor_count=0,
            )
            assert analyst.urgency_level == level

    def test_all_data_sources(self, product_id):
        """Every DataSource should be valid in Scout."""
        scout = ScoutOutput(
            product_id=product_id,
            our_price=Decimal("10.00"),
            data_completeness=1.0,
            data_sources=list(DataSource),
        )
        assert len(scout.data_sources) == len(DataSource)


        