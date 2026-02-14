# backend/tests/test_competitor_matching_scoring.py
"""
Tests for competitor_matching/scoring.py — confidence scoring system
with weighted signals, bonuses, penalties, and convenience functions.

Tests cover:
- ScoringWeights (validation, presets)
- ScoreBreakdown (serialization)
- ConfidenceScorer initialization
- Individual scoring components (title, keyword, price, merchant, completeness)
- Bonuses and penalties
- calculate (orchestration, detailed mode)
- calculate_batch
- score_products (convenience function)

Total: ~55 tests
"""

import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

# === Import isolation ===
for mod in [
    "db.session",
    "models.competitor",
    "models.competitor_product",
    "models.competitor_price_history",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.competitor_matching.schemas import MatchedProduct, SearchProvider
from services.competitor_matching.scoring import (
    ScoringWeights,
    ScoreBreakdown,
    ConfidenceScorer,
    score_products,
)

SCORING_PATH = "services.competitor_matching.scoring"


# ============================================================
# Helpers
# ============================================================

def make_product(
    title="Apple iPhone 15 Pro 256GB Black",
    url="https://example.com/iphone",
    price=Decimal("999.99"),
    merchant="Amazon",
    merchant_domain="amazon.com",
    image_url="https://example.com/img.jpg",
    rating=4.5,
    reviews_count=150,
    in_stock=True,
    confidence_score=0.0,
):
    return MatchedProduct(
        title=title, url=url, price=price,
        merchant=merchant, merchant_domain=merchant_domain,
        image_url=image_url, rating=rating,
        reviews_count=reviews_count, in_stock=in_stock,
        confidence_score=confidence_score,
    )


# ============================================================
# 1. ScoringWeights
# ============================================================

class TestScoringWeights:

    def test_defaults_sum_to_one(self):
        w = ScoringWeights()
        total = (
            w.title_similarity + w.keyword_match + w.price_proximity
            + w.merchant_reliability + w.data_completeness
        )
        assert 0.99 <= total <= 1.01

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            ScoringWeights(title_similarity=0.5, keyword_match=0.5,
                           price_proximity=0.5, merchant_reliability=0.5,
                           data_completeness=0.5)

    def test_for_exact_match(self):
        w = ScoringWeights.for_exact_match()
        assert w.title_similarity == 0.45
        total = (
            w.title_similarity + w.keyword_match + w.price_proximity
            + w.merchant_reliability + w.data_completeness
        )
        assert 0.99 <= total <= 1.01

    def test_for_price_comparison(self):
        w = ScoringWeights.for_price_comparison()
        assert w.price_proximity == 0.35

    def test_for_discovery(self):
        w = ScoringWeights.for_discovery()
        assert w.keyword_match == 0.30


# ============================================================
# 2. ScoreBreakdown
# ============================================================

class TestScoreBreakdown:

    def test_to_dict(self):
        b = ScoreBreakdown(
            final_score=0.756,
            title_score=0.8, keyword_score=0.6,
            price_score=0.9, merchant_score=0.7,
            completeness_score=0.5,
            penalties_applied=["short_title"],
            bonuses_applied=["high_rating"],
        )
        d = b.to_dict()
        assert d["final_score"] == 0.756
        assert d["components"]["title_similarity"] == 0.8
        assert d["penalties"] == ["short_title"]
        assert d["bonuses"] == ["high_rating"]

    def test_defaults(self):
        b = ScoreBreakdown(final_score=0.0)
        assert b.penalties_applied == []
        assert b.bonuses_applied == []


# ============================================================
# 3. ConfidenceScorer Init
# ============================================================

class TestConfidenceScorerInit:

    def test_default_weights(self):
        scorer = ConfidenceScorer()
        assert isinstance(scorer.weights, ScoringWeights)

    def test_custom_weights(self):
        w = ScoringWeights.for_exact_match()
        scorer = ConfidenceScorer(weights=w)
        assert scorer.weights.title_similarity == 0.45

    def test_custom_min_max(self):
        scorer = ConfidenceScorer(min_score=0.1, max_score=0.9)
        assert scorer.min_score == 0.1
        assert scorer.max_score == 0.9


# ============================================================
# 4. _score_title_similarity
# ============================================================

class TestScoreTitleSimilarity:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.85)
    def test_delegates_to_utility(self, mock_sim):
        result = self.scorer._score_title_similarity("Product A", "Product B")
        assert result == 0.85
        mock_sim.assert_called_once_with("Product A", "Product B")

    @patch(f"{SCORING_PATH}.calculate_text_similarity")
    def test_empty_title_returns_zero(self, mock_sim):
        result = self.scorer._score_title_similarity("", "search")
        assert result == 0.0
        mock_sim.assert_not_called()

    @patch(f"{SCORING_PATH}.calculate_text_similarity")
    def test_empty_search_returns_zero(self, mock_sim):
        result = self.scorer._score_title_similarity("title", "")
        assert result == 0.0


# ============================================================
# 5. _score_keyword_match
# ============================================================

class TestScoreKeywordMatch:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.75)
    def test_delegates_to_utility(self, mock_km):
        result = self.scorer._score_keyword_match("iPhone 15 Pro", ["apple", "256gb"])
        assert result == 0.75

    def test_no_keywords_returns_neutral(self):
        result = self.scorer._score_keyword_match("iPhone 15", None)
        assert result == 0.5

    def test_empty_keywords_returns_neutral(self):
        result = self.scorer._score_keyword_match("iPhone 15", [])
        assert result == 0.5


# ============================================================
# 6. _score_price_proximity
# ============================================================

class TestScorePriceProximity:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_exact_match(self):
        result = self.scorer._score_price_proximity(Decimal("100"), Decimal("100"))
        assert result == 1.0

    def test_within_10_percent(self):
        result = self.scorer._score_price_proximity(Decimal("105"), Decimal("100"))
        assert result == 1.0

    def test_within_30_percent(self):
        result = self.scorer._score_price_proximity(Decimal("120"), Decimal("100"))
        assert 0.5 < result < 1.0

    def test_within_50_percent(self):
        result = self.scorer._score_price_proximity(Decimal("140"), Decimal("100"))
        assert 0.1 < result < 0.7

    def test_beyond_50_percent(self):
        result = self.scorer._score_price_proximity(Decimal("200"), Decimal("100"))
        assert result == 0.1

    def test_no_product_price(self):
        result = self.scorer._score_price_proximity(None, Decimal("100"))
        assert result == 0.5

    def test_no_our_price(self):
        result = self.scorer._score_price_proximity(Decimal("100"), None)
        assert result == 0.5

    def test_zero_our_price(self):
        result = self.scorer._score_price_proximity(Decimal("100"), Decimal("0"))
        assert result == 0.5


# ============================================================
# 7. _score_merchant_reliability
# ============================================================

class TestScoreMerchantReliability:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.95)
    def test_delegates_to_utility(self, mock_mr):
        result = self.scorer._score_merchant_reliability("amazon.com")
        assert result == 0.95
        mock_mr.assert_called_once_with("amazon.com")


# ============================================================
# 8. _score_data_completeness
# ============================================================

class TestScoreDataCompleteness:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_fully_complete(self):
        p = make_product()  # Has price, image, merchant, rating, reviews
        result = self.scorer._score_data_completeness(p)
        assert result == 1.0

    def test_minimal_data(self):
        p = make_product(
            price=None, image_url=None, merchant="",
            rating=None, reviews_count=None,
        )
        result = self.scorer._score_data_completeness(p)
        assert result == 0.0

    def test_partial_data(self):
        p = make_product(image_url=None, rating=None, reviews_count=None)
        result = self.scorer._score_data_completeness(p)
        assert 0.0 < result < 1.0

    def test_zero_reviews_not_counted(self):
        p = make_product(reviews_count=0)
        result = self.scorer._score_data_completeness(p)
        # 4 out of 5 checks pass (reviews_count=0 doesn't count)
        assert result == 0.8


# ============================================================
# 9. Bonuses
# ============================================================

class TestApplyBonuses:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_high_review_count_bonus(self):
        p = make_product(reviews_count=200)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_bonuses(0.5, p, breakdown)
        assert result > 0.5
        assert "high_review_count" in breakdown.bonuses_applied

    def test_high_rating_bonus(self):
        p = make_product(rating=4.8)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_bonuses(0.5, p, breakdown)
        assert result > 0.5
        assert "high_rating" in breakdown.bonuses_applied

    def test_in_stock_bonus(self):
        p = make_product(in_stock=True)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_bonuses(0.5, p, breakdown)
        assert "in_stock" in breakdown.bonuses_applied

    def test_no_bonuses_for_minimal_product(self):
        p = make_product(reviews_count=5, rating=3.0, in_stock=False)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_bonuses(0.5, p, breakdown)
        assert result == 0.5
        assert breakdown.bonuses_applied == []


# ============================================================
# 10. Penalties
# ============================================================

class TestApplyPenalties:

    def setup_method(self):
        self.scorer = ConfidenceScorer()

    def test_out_of_stock_penalty(self):
        p = make_product(in_stock=False)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_penalties(0.5, p, "search", breakdown)
        assert result < 0.5
        assert "out_of_stock" in breakdown.penalties_applied

    def test_no_price_penalty(self):
        p = make_product(price=None)
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_penalties(0.5, p, "search", breakdown)
        assert "no_price" in breakdown.penalties_applied

    def test_short_title_penalty(self):
        p = make_product(title="iPhone")  # < 20 chars
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_penalties(0.5, p, "search", breakdown)
        assert "short_title" in breakdown.penalties_applied

    def test_category_page_penalty(self):
        p = make_product(title="Shop Now")  # category indicator + < 5 words
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_penalties(0.5, p, "search", breakdown)
        assert "category_page_suspected" in breakdown.penalties_applied

    def test_no_penalties_for_good_product(self):
        p = make_product()  # Full data, in stock, long title
        breakdown = ScoreBreakdown(final_score=0.0)
        result = self.scorer._apply_penalties(0.5, p, "search", breakdown)
        assert breakdown.penalties_applied == []


# ============================================================
# 11. calculate (full orchestration)
# ============================================================

class TestCalculate:

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.9)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.7)
    def test_returns_float_by_default(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer()
        p = make_product()
        result = scorer.calculate(p, "iPhone 15 Pro", ["apple"])
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.9)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.7)
    def test_returns_breakdown_when_detailed(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer()
        p = make_product()
        result = scorer.calculate(p, "iPhone 15 Pro", ["apple"], detailed=True)
        assert isinstance(result, ScoreBreakdown)
        assert result.final_score > 0

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.9)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.7)
    def test_clamped_to_max(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer(max_score=0.5)
        p = make_product()
        result = scorer.calculate(p, "iPhone 15 Pro", ["apple"])
        assert result <= 0.5

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.0)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.0)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.0)
    def test_clamped_to_min(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer(min_score=0.1)
        p = make_product(
            price=None, in_stock=False, reviews_count=None,
            rating=None, image_url=None, merchant="",
            title="Shop",
        )
        result = scorer.calculate(p, "iPhone")
        assert result >= 0.1


# ============================================================
# 12. calculate_batch
# ============================================================

class TestCalculateBatch:

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.7)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.6)
    def test_updates_all_products(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer()
        products = [make_product(), make_product(title="Other Widget")]
        result = scorer.calculate_batch(products, "iPhone 15")
        assert len(result) == 2
        assert all(p.confidence_score > 0 for p in result)

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.7)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.6)
    def test_returns_same_list(self, mock_ts, mock_km, mock_mr):
        scorer = ConfidenceScorer()
        products = [make_product()]
        result = scorer.calculate_batch(products, "test")
        assert result is products


# ============================================================
# 13. score_products (convenience)
# ============================================================

class TestScoreProducts:

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.7)
    @patch(f"{SCORING_PATH}.calculate_text_similarity")
    def test_sorted_by_confidence_desc(self, mock_ts, mock_km, mock_mr):
        # First product gets higher title similarity
        mock_ts.side_effect = [0.9, 0.3]
        products = [
            make_product(title="Low match widget"),
            make_product(title="High match iPhone 15 Pro"),
        ]
        result = score_products(products, "iPhone 15 Pro")
        assert result[0].confidence_score >= result[1].confidence_score

    @patch(f"{SCORING_PATH}.get_merchant_reliability", return_value=0.8)
    @patch(f"{SCORING_PATH}.calculate_keyword_match", return_value=0.7)
    @patch(f"{SCORING_PATH}.calculate_text_similarity", return_value=0.5)
    def test_accepts_custom_weights(self, mock_ts, mock_km, mock_mr):
        products = [make_product()]
        w = ScoringWeights.for_price_comparison()
        result = score_products(products, "test", weights=w)
        assert len(result) == 1


        