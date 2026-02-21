# backend/services/competitor_matching/scoring.py

"""
Confidence Scoring Module

Calculates how confident we are that a search result
matches the user's product. Uses multiple signals:

1. Title similarity (word overlap)
2. Keyword presence
3. Price proximity
4. Merchant reliability
5. Data completeness

Each signal has a configurable weight, allowing
fine-tuning for different use cases.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .schemas import MatchedProduct
from .utils import (
    calculate_text_similarity,
    calculate_keyword_match,
    get_merchant_reliability,
)


@dataclass
class ScoringWeights:
    """
    Configurable weights for scoring signals.
    
    Weights should sum to 1.0 for normalized scores.
    """
    title_similarity: float = 0.35
    keyword_match: float = 0.20
    price_proximity: float = 0.20
    merchant_reliability: float = 0.15
    data_completeness: float = 0.10

    def __post_init__(self):
        """Validate weights sum to ~1.0."""
        total = (
            self.title_similarity +
            self.keyword_match +
            self.price_proximity +
            self.merchant_reliability +
            self.data_completeness
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    @classmethod
    def for_exact_match(cls) -> "ScoringWeights":
        """Weights optimized for finding exact product matches."""
        return cls(
            title_similarity=0.45,
            keyword_match=0.25,
            price_proximity=0.15,
            merchant_reliability=0.10,
            data_completeness=0.05,
        )

    @classmethod
    def for_price_comparison(cls) -> "ScoringWeights":
        """Weights optimized for price comparison."""
        return cls(
            title_similarity=0.25,
            keyword_match=0.15,
            price_proximity=0.35,
            merchant_reliability=0.15,
            data_completeness=0.10,
        )

    @classmethod
    def for_discovery(cls) -> "ScoringWeights":
        """Weights optimized for discovering similar products."""
        return cls(
            title_similarity=0.30,
            keyword_match=0.30,
            price_proximity=0.10,
            merchant_reliability=0.20,
            data_completeness=0.10,
        )


@dataclass
class ScoreBreakdown:
    """
    Detailed breakdown of how a score was calculated.
    
    Useful for debugging and explaining results to users.
    """
    final_score: float
    title_score: float = 0.0
    keyword_score: float = 0.0
    price_score: float = 0.0
    merchant_score: float = 0.0
    completeness_score: float = 0.0
    penalties_applied: List[str] = field(default_factory=list)
    bonuses_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "final_score": round(self.final_score, 3),
            "components": {
                "title_similarity": round(self.title_score, 3),
                "keyword_match": round(self.keyword_score, 3),
                "price_proximity": round(self.price_score, 3),
                "merchant_reliability": round(self.merchant_score, 3),
                "data_completeness": round(self.completeness_score, 3),
            },
            "penalties": self.penalties_applied,
            "bonuses": self.bonuses_applied,
        }


class ConfidenceScorer:
    """
    Calculates confidence scores for matched products.
    
    Usage:
        scorer = ConfidenceScorer()
        score = scorer.calculate(
            product=matched_product,
            search_name="iPhone 15 Pro",
            keywords=["apple", "256gb"],
            our_price=Decimal("999.99"),
        )
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        min_score: float = 0.0,
        max_score: float = 1.0,
    ):
        """
        Initialize scorer.
        
        Args:
            weights: Scoring weights (uses default if None)
            min_score: Minimum possible score
            max_score: Maximum possible score
        """
        self.weights = weights or ScoringWeights()
        self.min_score = min_score
        self.max_score = max_score

    def calculate(
        self,
        product: MatchedProduct,
        search_name: str,
        keywords: Optional[List[str]] = None,
        our_price: Optional[Decimal] = None,
        detailed: bool = False,
    ) -> float | ScoreBreakdown:
        """
        Calculate confidence score for a matched product.
        
        Args:
            product: The matched product to score
            search_name: Original product name we searched for
            keywords: Keywords that should appear in match
            our_price: Our product's price for comparison
            detailed: If True, return ScoreBreakdown instead of float
            
        Returns:
            Confidence score (0-1) or ScoreBreakdown if detailed=True
        """
        breakdown = ScoreBreakdown(final_score=0.0)

        # 1. Title similarity
        title_score = self._score_title_similarity(product.title, search_name)
        breakdown.title_score = title_score

        # 2. Keyword match
        keyword_score = self._score_keyword_match(product.title, keywords)
        breakdown.keyword_score = keyword_score

        # 3. Price proximity
        price_score = self._score_price_proximity(product.price, our_price)
        breakdown.price_score = price_score

        # 4. Merchant reliability
        merchant_score = self._score_merchant_reliability(product.merchant_domain)
        breakdown.merchant_score = merchant_score

        # 5. Data completeness
        completeness_score = self._score_data_completeness(product)
        breakdown.completeness_score = completeness_score

        # Calculate weighted sum
        weighted_score = (
            title_score * self.weights.title_similarity +
            keyword_score * self.weights.keyword_match +
            price_score * self.weights.price_proximity +
            merchant_score * self.weights.merchant_reliability +
            completeness_score * self.weights.data_completeness
        )

        # Apply bonuses
        weighted_score = self._apply_bonuses(
            weighted_score, product, breakdown
        )

        # Apply penalties
        weighted_score = self._apply_penalties(
            weighted_score, product, search_name, breakdown
        )

        # Clamp to valid range
        final_score = max(self.min_score, min(self.max_score, weighted_score))
        breakdown.final_score = round(final_score, 3)

        if detailed:
            return breakdown
        return breakdown.final_score

    def calculate_batch(
        self,
        products: List[MatchedProduct],
        search_name: str,
        keywords: Optional[List[str]] = None,
        our_price: Optional[Decimal] = None,
    ) -> List[MatchedProduct]:
        """
        Calculate scores for multiple products and update them in place.
        
        Args:
            products: List of products to score
            search_name: Original search term
            keywords: Keywords to match
            our_price: Our price for comparison
            
        Returns:
            Same list with confidence_score updated
        """
        for product in products:
            product.confidence_score = self.calculate(
                product=product,
                search_name=search_name,
                keywords=keywords,
                our_price=our_price,
            )
        return products

    # ─────────────────────────────────────────────────────────────────────────
    # Individual Scoring Components
    # ─────────────────────────────────────────────────────────────────────────

    def _score_title_similarity(
        self, 
        product_title: str, 
        search_name: str
    ) -> float:
        """
        Score based on title similarity.
        
        Uses word overlap (Jaccard similarity).
        """
        if not product_title or not search_name:
            return 0.0

        return calculate_text_similarity(product_title, search_name)

    def _score_keyword_match(
        self,
        product_title: str,
        keywords: Optional[List[str]],
    ) -> float:
        """
        Score based on keyword presence in title.
        """
        if not keywords:
            return 0.5  # Neutral score if no keywords provided

        return calculate_keyword_match(product_title, keywords)

    def _score_price_proximity(
        self,
        product_price: Optional[Decimal],
        our_price: Optional[Decimal],
    ) -> float:
        """
        Score based on how close the price is to ours.
        
        Products within 30% of our price score highest.
        """
        if not product_price or not our_price:
            return 0.5  # Neutral score if no price comparison possible

        if our_price <= 0:
            return 0.5

        # Calculate ratio
        ratio = float(product_price / our_price)

        # Perfect match = 1.0
        # Within 30% = 0.7+
        # Within 50% = 0.5+
        # Beyond 100% difference = low score

        if 0.9 <= ratio <= 1.1:
            # Within 10% - excellent
            return 1.0
        elif 0.7 <= ratio <= 1.3:
            # Within 30% - good
            deviation = abs(1.0 - ratio)
            return 1.0 - (deviation * 1.5)  # 0.7 - 1.0
        elif 0.5 <= ratio <= 1.5:
            # Within 50% - acceptable
            deviation = abs(1.0 - ratio)
            return 0.7 - (deviation * 0.8)  # 0.3 - 0.7
        else:
            # More than 50% off - suspicious
            return 0.1

    def _score_merchant_reliability(self, domain: str) -> float:
        """
        Score based on merchant trustworthiness.
        """
        return get_merchant_reliability(domain)

    def _score_data_completeness(self, product: MatchedProduct) -> float:
        """
        Score based on how much data we have about the product.
        
        More complete data = higher confidence.
        """
        score = 0.0
        checks = 0

        # Has price
        checks += 1
        if product.price is not None:
            score += 1.0

        # Has image
        checks += 1
        if product.image_url:
            score += 1.0

        # Has merchant info
        checks += 1
        if product.merchant:
            score += 1.0

        # Has rating
        checks += 1
        if product.rating is not None:
            score += 1.0

        # Has reviews
        checks += 1
        if product.reviews_count is not None and product.reviews_count > 0:
            score += 1.0

        return score / checks if checks > 0 else 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Bonuses and Penalties
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_bonuses(
        self,
        score: float,
        product: MatchedProduct,
        breakdown: ScoreBreakdown,
    ) -> float:
        """Apply bonus points for positive signals."""
        
        # Bonus for high review count (social proof)
        if product.reviews_count and product.reviews_count > 100:
            score += 0.05
            breakdown.bonuses_applied.append("high_review_count")

        # Bonus for high rating
        if product.rating and product.rating >= 4.5:
            score += 0.03
            breakdown.bonuses_applied.append("high_rating")

        # Bonus for in-stock
        if product.in_stock:
            score += 0.02
            breakdown.bonuses_applied.append("in_stock")

        return score

    def _apply_penalties(
        self,
        score: float,
        product: MatchedProduct,
        search_name: str,
        breakdown: ScoreBreakdown,
    ) -> float:
        """Apply penalties for negative signals."""
        
        # Penalty for out of stock
        if not product.in_stock:
            score -= 0.1
            breakdown.penalties_applied.append("out_of_stock")

        # Penalty for missing price
        if product.price is None:
            score -= 0.05
            breakdown.penalties_applied.append("no_price")

        # Penalty for very short title (might be wrong product)
        if len(product.title) < 20:
            score -= 0.05
            breakdown.penalties_applied.append("short_title")

        # Penalty for title that looks like a category, not product
        category_indicators = ["shop", "buy", "store", "category", "collection"]
        title_lower = product.title.lower()
        if any(ind in title_lower for ind in category_indicators):
            if len(product.title.split()) < 5:
                score -= 0.1
                breakdown.penalties_applied.append("category_page_suspected")

        return score


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

def score_products(
    products: List[MatchedProduct],
    search_name: str,
    keywords: Optional[List[str]] = None,
    our_price: Optional[Decimal] = None,
    weights: Optional[ScoringWeights] = None,
) -> List[MatchedProduct]:
    """
    Score a list of products and return sorted by confidence.
    
    Convenience function for common use case.
    
    Args:
        products: Products to score
        search_name: What we searched for
        keywords: Keywords to match
        our_price: Our product's price
        weights: Custom scoring weights
        
    Returns:
        Products sorted by confidence (highest first)
    """
    scorer = ConfidenceScorer(weights=weights)
    scored = scorer.calculate_batch(
        products=products,
        search_name=search_name,
        keywords=keywords,
        our_price=our_price,
    )
    return sorted(scored, key=lambda p: p.confidence_score, reverse=True)


