"""
Elasticity Calculator — Bayesian hierarchical model for Price Elasticity of Demand.

This is the Analyst's core computation for elasticity. It replaces the
hardcoded `point_estimate=-1.0, method="category_prior", prior_source="default"`
placeholder in the current PipelineAdapter.

How it works:
  1. Load category prior from CategoryPriorStore (research-based starting point).
  2. If historical price+sales data exists, compute observed PED from each
     price change event: PED = (ΔQ/Q) / (ΔP/P).
  3. Run Normal-Normal conjugate Bayesian update: combine prior with observations.
  4. Compute confidence from posterior width relative to prior width.
  5. Return ElasticityEstimate matching the analyst.py contract.

When there's no sales data (early merchants), the calculator returns
the category prior with low confidence. As outcome data accumulates
through Tier 2 learning, the prior tightens and confidence rises.
This is the system learning from real merchant outcomes.

Phase 2 Scoring Engine — Component 1.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/elasticity_calculator.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from .category_priors import CategoryPrior, CategoryPriorStore

# ──────────────────────────────────────────────────────────
# INPUT TYPES
# ──────────────────────────────────────────────────────────


@dataclass
class PriceChangeEvent:
    """
    A historical price change with corresponding sales volume data.

    The elasticity calculator needs BOTH price and volume to compute PED.
    ScoutOutput provides price_history but not sales. The orchestrator
    (engine.py) is responsible for joining price changes with Shopify
    order data to produce these events.

    When no sales data is available, the calculator falls back to the
    category prior — which is exactly the right behavior for new merchants.
    """

    old_price: float
    new_price: float
    price_changed_at: datetime

    # Volume data (from Shopify orders or similar)
    avg_daily_units_before: float  # Average daily units sold BEFORE change
    avg_daily_units_after: float  # Average daily units sold AFTER change

    # Quality indicators
    days_before_measured: int = 7  # How many days of pre-change data
    days_after_measured: int = 7  # How many days of post-change data
    confounders_noted: bool = False  # Holiday, promotion, stockout, etc.

    @property
    def price_change_pct(self) -> float:
        """Percentage change in price. Positive = price went up."""
        if self.old_price == 0:
            return 0.0
        return (self.new_price - self.old_price) / self.old_price

    @property
    def quantity_change_pct(self) -> float:
        """Percentage change in quantity demanded. Negative = demand fell."""
        if self.avg_daily_units_before == 0:
            return 0.0
        return (self.avg_daily_units_after - self.avg_daily_units_before) / self.avg_daily_units_before

    @property
    def observed_ped(self) -> float | None:
        """
        Point estimate of PED from this event.

        PED = (% change in quantity) / (% change in price)

        Returns None if price didn't change enough to measure.
        For normal goods, this should be negative (price up → demand down).
        """
        pct_price = self.price_change_pct
        if abs(pct_price) < 0.02:  # Less than 2% price change — too noisy
            return None
        pct_qty = self.quantity_change_pct
        return pct_qty / pct_price


# ──────────────────────────────────────────────────────────
# RESULT TYPE
# ──────────────────────────────────────────────────────────


@dataclass
class ElasticityResult:
    """
    Internal result from the elasticity calculator.

    Maps directly to schemas.agent_contracts.analyst.ElasticityEstimate:
      point_estimate      → estimate
      confidence_interval_low → ci_lower
      confidence_interval_high → ci_upper
      method              → method
      prior_source        → prior_source
      sample_size         → n_observations
      (confidence)        → confidence (0-1 score for ConfidenceDecomposition)
    """

    estimate: float  # Posterior mean PED (negative for normal goods)
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    confidence: float  # 0-1 confidence score
    method: str  # "bayesian_hierarchical", "category_prior", etc.
    prior_source: str  # "category_benchmark", "merchant_history", "default"
    n_observations: int  # Number of valid price change events used
    prior_mu: float  # The prior mean that was used
    prior_sigma: float  # The prior sigma that was used
    posterior_sigma: float  # The posterior sigma (tighter = more data)


# ──────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────

# Minimum price change to consider an observation valid
MIN_PRICE_CHANGE_PCT: float = 0.02  # 2%

# Minimum days of post-change data to trust the observation
MIN_POST_CHANGE_DAYS: int = 3

# Clamp observed PED to this range (extreme values are likely noise)
PED_CLAMP_MIN: float = -10.0  # Extremely elastic
PED_CLAMP_MAX: float = 0.5  # Slight Giffen/Veblen effect allowed

# Default observation noise — how much we trust a single observation
# Lower = trust more. 0.5 = moderately noisy (single merchant, limited data)
DEFAULT_OBSERVATION_NOISE: float = 0.5

# Noise adjustment for high-quality observations
HIGH_QUALITY_NOISE: float = 0.3  # 7+ days before AND after, no confounders
LOW_QUALITY_NOISE: float = 0.8  # Short windows or confounders present

# Confidence floor when using pure prior (no observations)
PRIOR_ONLY_CONFIDENCE: float = 0.15

# Maximum confidence (even lots of data can't make us 100% sure)
MAX_CONFIDENCE: float = 0.95


# ──────────────────────────────────────────────────────────
# CALCULATOR
# ──────────────────────────────────────────────────────────


class ElasticityCalculator:
    """
    Bayesian hierarchical elasticity calculator.

    Hierarchy:
      Level 1: Category prior (from CategoryPriorStore — research + Tier 2 updates)
      Level 2: Product-level posterior (from this merchant's price change history)

    When no product-level data exists, returns the category prior.
    As observations accumulate, the posterior tightens around the
    product's true elasticity.

    Usage:
        store = CategoryPriorStore()
        calc = ElasticityCalculator(store)

        # No sales data — returns category prior
        result = calc.compute(category="electronics", price_change_events=[])

        # With sales data — Bayesian update
        events = [PriceChangeEvent(...), ...]
        result = calc.compute(category="electronics", price_change_events=events)
    """

    def __init__(self, prior_store: CategoryPriorStore):
        self._prior_store = prior_store

    def compute(
        self,
        category: str,
        price_change_events: Sequence[PriceChangeEvent] | None = None,
        current_price: float | None = None,
    ) -> ElasticityResult:
        """
        Compute elasticity estimate for a product.

        Args:
            category: Product category (resolved via CategoryPriorStore aliases).
            price_change_events: Historical price changes with volume data.
                Empty or None = use category prior only.
            current_price: Current product price (unused in v1, reserved for
                price-dependent elasticity in v2).

        Returns:
            ElasticityResult with posterior estimate, CI, and confidence.
        """
        prior = self._prior_store.get_prior(category)
        prior_source = self._prior_store.get_prior_source(category)

        # Filter to valid observations
        valid_observations = self._extract_valid_observations(price_change_events or [])

        if not valid_observations:
            # No data — return category prior as-is
            return self._result_from_prior(prior, prior_source)

        # Run Bayesian update
        return self._bayesian_update(prior, prior_source, valid_observations)

    def _extract_valid_observations(
        self,
        events: Sequence[PriceChangeEvent],
    ) -> list[tuple[float, float]]:
        """
        Extract valid (observed_ped, noise_sigma) pairs from price change events.

        Filters out:
        - Events where price changed less than MIN_PRICE_CHANGE_PCT
        - Events with insufficient post-change measurement window
        - Events with extreme PED values (likely noise)

        Returns:
            List of (observed_ped, observation_noise) tuples.
        """
        valid = []

        for event in events:
            # Skip tiny price changes (too noisy to learn from)
            if abs(event.price_change_pct) < MIN_PRICE_CHANGE_PCT:
                continue

            # Skip if insufficient post-change data
            if event.days_after_measured < MIN_POST_CHANGE_DAYS:
                continue

            # Compute observed PED
            ped = event.observed_ped
            if ped is None:
                continue

            # Clamp extreme values
            ped = max(PED_CLAMP_MIN, min(PED_CLAMP_MAX, ped))

            # Determine observation noise based on data quality
            noise = self._assess_observation_noise(event)

            valid.append((ped, noise))

        return valid

    def _assess_observation_noise(self, event: PriceChangeEvent) -> float:
        """
        Determine how much to trust this observation.

        Higher quality observations (longer measurement windows, no confounders)
        get lower noise, meaning the Bayesian update trusts them more.
        """
        if event.confounders_noted:
            return LOW_QUALITY_NOISE

        if event.days_before_measured >= 7 and event.days_after_measured >= 7:
            return HIGH_QUALITY_NOISE

        # Linear interpolation based on post-change days
        # 3 days → LOW_QUALITY_NOISE, 7+ days → HIGH_QUALITY_NOISE
        days_factor = min(
            (event.days_after_measured - MIN_POST_CHANGE_DAYS) / (7 - MIN_POST_CHANGE_DAYS),
            1.0,
        )
        return LOW_QUALITY_NOISE - (LOW_QUALITY_NOISE - HIGH_QUALITY_NOISE) * days_factor

    def _result_from_prior(
        self,
        prior: CategoryPrior,
        prior_source: str,
    ) -> ElasticityResult:
        """Build result when we have no observations — pure prior."""
        ci_lower = prior.mu - 1.96 * prior.sigma
        ci_upper = prior.mu + 1.96 * prior.sigma

        return ElasticityResult(
            estimate=prior.mu,
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            confidence=PRIOR_ONLY_CONFIDENCE,
            method="category_prior",
            prior_source=prior_source,
            n_observations=0,
            prior_mu=prior.mu,
            prior_sigma=prior.sigma,
            posterior_sigma=prior.sigma,
        )

    def _bayesian_update(
        self,
        prior: CategoryPrior,
        prior_source: str,
        observations: list[tuple[float, float]],
    ) -> ElasticityResult:
        """
        Normal-Normal conjugate Bayesian update with heterogeneous noise.

        Each observation has its own noise level, so we can't use the
        simple batch formula. Instead, accumulate precision incrementally:

            posterior_precision = prior_precision + Σ(1/σ²_i)
            posterior_mu = (prior_mu * prior_precision + Σ(x_i / σ²_i)) / posterior_precision

        This naturally weights high-quality observations more heavily.
        """
        prior_precision = prior.precision
        weighted_sum = prior.mu * prior_precision
        total_precision = prior_precision

        n_used = 0
        for obs_ped, obs_noise in observations:
            obs_precision = 1.0 / (obs_noise**2)
            weighted_sum += obs_ped * obs_precision
            total_precision += obs_precision
            n_used += 1

        posterior_mu = weighted_sum / total_precision
        posterior_sigma = math.sqrt(1.0 / total_precision)

        # 95% confidence interval
        ci_lower = posterior_mu - 1.96 * posterior_sigma
        ci_upper = posterior_mu + 1.96 * posterior_sigma

        # Confidence score: how much the posterior tightened vs the prior
        # 1.0 = posterior is infinitely tighter than prior (impossible)
        # 0.0 = no tightening at all
        sigma_reduction = 1.0 - (posterior_sigma / prior.sigma)
        raw_confidence = max(0.0, sigma_reduction)

        # Scale confidence: even with good data, cap at MAX_CONFIDENCE.
        # With 1 observation, typical confidence is 0.3-0.5.
        # With 5+ observations, typical confidence is 0.6-0.8.
        # Floor is above PRIOR_ONLY_CONFIDENCE so any data helps.
        confidence = PRIOR_ONLY_CONFIDENCE + ((MAX_CONFIDENCE - PRIOR_ONLY_CONFIDENCE) * raw_confidence)
        confidence = min(confidence, MAX_CONFIDENCE)
        confidence = round(confidence, 4)

        return ElasticityResult(
            estimate=round(posterior_mu, 4),
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            confidence=confidence,
            method="bayesian_hierarchical",
            prior_source=prior_source,
            n_observations=n_used,
            prior_mu=prior.mu,
            prior_sigma=prior.sigma,
            posterior_sigma=round(posterior_sigma, 6),
        )
