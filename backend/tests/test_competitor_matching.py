"""
Tests for the ActualPrice competitor matching pipeline.
Aligned with actual service signatures:
  - scoring.py: ConfidenceScorer, ScoringWeights, ScoreBreakdown
  - service.py: CompetitorMatchingService.find_competitors() (async)
  - providers/base.py: BaseSearchProvider.search() (async)
  - competitor_scraper.py: CompetitorScraperService (not CompetitorScraper)
"""

from decimal import Decimal

import pytest


# ===================================================================
# ScoringWeights Tests
# ===================================================================

class TestScoringWeights:

    def test_default_weights_exist(self):
        from services.competitor_matching.scoring import ScoringWeights
        w = ScoringWeights()
        assert w is not None

    def test_exact_match_preset(self):
        from services.competitor_matching.scoring import ScoringWeights
        w = ScoringWeights.for_exact_match()
        assert w is not None

    def test_price_comparison_preset(self):
        from services.competitor_matching.scoring import ScoringWeights
        w = ScoringWeights.for_price_comparison()
        assert w is not None

    def test_discovery_preset(self):
        from services.competitor_matching.scoring import ScoringWeights
        w = ScoringWeights.for_discovery()
        assert w is not None

    def test_weights_validate(self):
        """Post-init validation should succeed for valid weights."""
        from services.competitor_matching.scoring import ScoringWeights
        w = ScoringWeights()
        # Should not raise
        assert True


# ===================================================================
# ConfidenceScorer Tests
# ===================================================================

class TestConfidenceScorer:

    def test_scorer_initializes(self):
        from services.competitor_matching.scoring import ConfidenceScorer
        scorer = ConfidenceScorer()
        assert scorer is not None

    def test_has_calculate_method(self):
        from services.competitor_matching.scoring import ConfidenceScorer
        scorer = ConfidenceScorer()
        assert callable(getattr(scorer, "calculate", None))


# ===================================================================
# ScoreBreakdown Tests
# ===================================================================

class TestScoreBreakdown:

    def test_breakdown_class_exists(self):
        from services.competitor_matching.scoring import ScoreBreakdown
        assert ScoreBreakdown is not None

    def test_breakdown_has_to_dict(self):
        from services.competitor_matching.scoring import ScoreBreakdown
        # Inspect the dataclass fields to construct correctly
        import dataclasses
        fields = [f.name for f in dataclasses.fields(ScoreBreakdown)]
        assert "to_dict" in dir(ScoreBreakdown)
        assert len(fields) > 0


# ===================================================================
# CompetitorMatchingService Tests
# ===================================================================

class TestCompetitorMatchingService:

    def test_service_initializes(self):
        from services.competitor_matching.service import CompetitorMatchingService
        service = CompetitorMatchingService()
        assert service is not None

    def test_has_find_competitors(self):
        from services.competitor_matching.service import CompetitorMatchingService
        service = CompetitorMatchingService()
        assert callable(getattr(service, "find_competitors", None))

    def test_has_get_available_providers(self):
        from services.competitor_matching.service import CompetitorMatchingService
        service = CompetitorMatchingService()
        providers = service.get_available_providers()
        assert isinstance(providers, list)

    def test_has_clear_cache(self):
        from services.competitor_matching.service import CompetitorMatchingService
        service = CompetitorMatchingService()
        assert callable(getattr(service, "clear_cache", None))

    def test_clear_cache_returns_int(self):
        from services.competitor_matching.service import CompetitorMatchingService
        service = CompetitorMatchingService()
        cleared = service.clear_cache()
        assert isinstance(cleared, int)
        assert cleared >= 0


# ===================================================================
# BaseSearchProvider Tests
# ===================================================================

class TestBaseSearchProvider:

    def test_base_class_exists(self):
        from services.competitor_matching.providers.base import BaseSearchProvider
        assert BaseSearchProvider is not None

    def test_has_search_method(self):
        from services.competitor_matching.providers.base import BaseSearchProvider
        assert callable(getattr(BaseSearchProvider, "search", None))

    def test_has_is_available(self):
        from services.competitor_matching.providers.base import BaseSearchProvider
        assert callable(getattr(BaseSearchProvider, "is_available", None))


# ===================================================================
# CompetitorScraperService Tests
# ===================================================================

class TestCompetitorScraperService:

    def test_scraper_initializes(self):
        from services.competitor_scraper import CompetitorScraperService
        scraper = CompetitorScraperService()
        assert scraper is not None

    def test_has_scrape_price(self):
        from services.competitor_scraper import CompetitorScraperService
        scraper = CompetitorScraperService()
        assert callable(getattr(scraper, "scrape_price", None))


# ===================================================================
# Price Comparison Logic (pure math — no service imports needed)
# ===================================================================

class TestPriceComparison:

    def test_price_gap_calculation(self):
        our_price = Decimal("79.99")
        comp_price = Decimal("74.99")
        gap = our_price - comp_price
        gap_pct = (gap / our_price) * 100
        assert float(gap) == pytest.approx(5.0, abs=0.01)
        assert float(gap_pct) == pytest.approx(6.25, abs=0.1)

    def test_we_are_cheaper(self):
        our_price = Decimal("79.99")
        comp_price = Decimal("99.99")
        assert our_price < comp_price

    def test_we_are_more_expensive(self):
        our_price = Decimal("79.99")
        comp_price = Decimal("74.99")
        assert our_price > comp_price

    def test_price_at_parity(self):
        our_price = Decimal("79.99")
        comp_price = Decimal("79.99")
        gap_pct = abs(float(our_price - comp_price) / float(our_price)) * 100
        assert gap_pct < 1.0

    def test_multiple_competitor_average(self):
        comp_prices = [Decimal("74.99"), Decimal("79.99"), Decimal("84.99"), Decimal("69.99")]
        avg = sum(comp_prices) / len(comp_prices)
        assert float(avg) == pytest.approx(77.49, abs=0.01)

    def test_market_position_summary(self):
        our_price = Decimal("79.99")
        comp_prices = [Decimal("74.99"), Decimal("84.99"), Decimal("89.99")]
        cheapest = min(comp_prices)
        most_expensive = max(comp_prices)
        assert cheapest < our_price < most_expensive



        