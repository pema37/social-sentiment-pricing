"""
Category Priors — Bayesian prior distributions for price elasticity by product category.

This is the Analyst's institutional memory. Each category has a prior
distribution (Normal) for price elasticity of demand, informed by
econometric research and updated by Tier 2 weekly batch learning
as outcome data accumulates.

Phase 2 Scoring Engine — Component 0 (data layer).
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/category_priors.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional


@dataclass
class CategoryPrior:
    """
    Normal prior for price elasticity of demand (PED) in a product category.

    Convention: PED is negative for normal goods.
      - mu = -1.2 means "a 1% price increase causes ~1.2% demand decrease"
      - sigma controls uncertainty. Wider sigma = less confident prior.
      - sample_size tracks how many real observations have updated this prior.
        0 = pure research-based prior. >0 = posterior incorporating merchant data.
    """

    mu: float             # Prior mean (negative for normal goods)
    sigma: float          # Prior standard deviation (uncertainty)
    sample_size: int = 0  # Observations used to update from base prior
    last_updated: Optional[datetime] = None
    version: str = "research_v1"  # Tracks prior source for auditability

    def __post_init__(self):
        if self.sigma <= 0:
            raise ValueError(f"sigma must be positive, got {self.sigma}")

    @property
    def variance(self) -> float:
        return self.sigma ** 2

    @property
    def is_informed(self) -> bool:
        """True if this prior has been updated with real outcome data."""
        return self.sample_size > 0

    @property
    def precision(self) -> float:
        """Bayesian precision = 1 / variance. Higher = more confident."""
        return 1.0 / self.variance


# ──────────────────────────────────────────────────────────
# RESEARCH-BASED PRIORS
#
# Sources:
#   - Bijmolt et al. (2005) meta-analysis: mean PED across categories ≈ -2.62
#   - Tellis (1988) meta-analysis: mean PED ≈ -1.76
#   - E-commerce typically shows higher elasticity than brick-and-mortar
#     due to lower switching costs and price transparency.
#   - Category-specific estimates from industry research and
#     published econometric studies.
#
# These are starting points. Tier 2 learning (weekly batch) updates
# them as outcome data accumulates via:
#   CategoryPriorStore.update_prior(category, observed_elasticity)
# ──────────────────────────────────────────────────────────

_BASE_PRIORS: dict[str, CategoryPrior] = {
    # ── High elasticity (price-sensitive, easy to comparison-shop) ──
    "electronics": CategoryPrior(
        mu=-1.8, sigma=0.6,
        version="research_v1",
    ),
    "books_media": CategoryPrior(
        mu=-2.0, sigma=0.5,
        version="research_v1",
    ),
    "toys_games": CategoryPrior(
        mu=-1.7, sigma=0.6,
        version="research_v1",
    ),

    # ── Moderate elasticity ──
    "fashion_apparel": CategoryPrior(
        mu=-1.2, sigma=0.8,
        version="research_v1",
    ),
    "home_garden": CategoryPrior(
        mu=-1.5, sigma=0.7,
        version="research_v1",
    ),
    "sports_outdoors": CategoryPrior(
        mu=-1.3, sigma=0.6,
        version="research_v1",
    ),
    "beauty_personal_care": CategoryPrior(
        mu=-1.0, sigma=0.5,
        version="research_v1",
    ),
    "pet_supplies": CategoryPrior(
        mu=-1.1, sigma=0.5,
        version="research_v1",
    ),
    "automotive": CategoryPrior(
        mu=-1.4, sigma=0.7,
        version="research_v1",
    ),
    "office_supplies": CategoryPrior(
        mu=-1.3, sigma=0.6,
        version="research_v1",
    ),

    # ── Low elasticity (necessities, brand-loyal, hard to compare) ──
    "groceries_food": CategoryPrior(
        mu=-0.4, sigma=0.3,
        version="research_v1",
    ),
    "health_supplements": CategoryPrior(
        mu=-0.6, sigma=0.4,
        version="research_v1",
    ),
    "baby_kids": CategoryPrior(
        mu=-0.7, sigma=0.4,
        version="research_v1",
    ),

    # ── Luxury / premium (complex elasticity, high variance) ──
    "jewelry_watches": CategoryPrior(
        mu=-0.8, sigma=0.9,
        version="research_v1",
    ),
    "luxury_goods": CategoryPrior(
        mu=-0.5, sigma=1.0,
        version="research_v1",
    ),
}

# Default prior: used when category is unknown or unmapped.
# Wide sigma means "we don't know much — learn fast from data."
_DEFAULT_PRIOR = CategoryPrior(
    mu=-1.2, sigma=1.0,
    version="default_v1",
)


class CategoryPriorStore:
    """
    Manages category-level Bayesian priors for the elasticity calculator.

    Thread-safe for reads. Writes (update_prior) are called from Tier 2
    weekly batch jobs — not from the hot recommendation path.

    Usage:
        store = CategoryPriorStore()
        prior = store.get_prior("electronics")
        # prior.mu = -1.8, prior.sigma = 0.6

        # After Tier 2 learning:
        store.update_prior("electronics", observed_elasticity=-2.1)
        # prior.mu shifts toward -2.1, sigma tightens
    """

    def __init__(self):
        # Deep-copy base priors so updates don't mutate the module-level dict
        self._priors: dict[str, CategoryPrior] = {
            k: CategoryPrior(
                mu=v.mu,
                sigma=v.sigma,
                sample_size=v.sample_size,
                last_updated=v.last_updated,
                version=v.version,
            )
            for k, v in _BASE_PRIORS.items()
        }
        self._default = CategoryPrior(
            mu=_DEFAULT_PRIOR.mu,
            sigma=_DEFAULT_PRIOR.sigma,
            version=_DEFAULT_PRIOR.version,
        )

        # Category name aliases → canonical key
        self._aliases: dict[str, str] = {
            "electronics": "electronics",
            "computers": "electronics",
            "phones": "electronics",
            "gadgets": "electronics",
            "books": "books_media",
            "media": "books_media",
            "music": "books_media",
            "movies": "books_media",
            "fashion": "fashion_apparel",
            "apparel": "fashion_apparel",
            "clothing": "fashion_apparel",
            "shoes": "fashion_apparel",
            "home": "home_garden",
            "garden": "home_garden",
            "furniture": "home_garden",
            "sports": "sports_outdoors",
            "outdoors": "sports_outdoors",
            "fitness": "sports_outdoors",
            "beauty": "beauty_personal_care",
            "skincare": "beauty_personal_care",
            "cosmetics": "beauty_personal_care",
            "health": "health_supplements",
            "supplements": "health_supplements",
            "vitamins": "health_supplements",
            "food": "groceries_food",
            "groceries": "groceries_food",
            "grocery": "groceries_food",
            "baby": "baby_kids",
            "kids": "baby_kids",
            "children": "baby_kids",
            "toys": "toys_games",
            "games": "toys_games",
            "pet": "pet_supplies",
            "pets": "pet_supplies",
            "automotive": "automotive",
            "auto": "automotive",
            "car": "automotive",
            "office": "office_supplies",
            "stationery": "office_supplies",
            "jewelry": "jewelry_watches",
            "watches": "jewelry_watches",
            "luxury": "luxury_goods",
        }

    def _resolve_category(self, category: str) -> str:
        """Normalize category string to canonical key."""
        normalized = category.lower().strip().replace(" ", "_").replace("-", "_").replace("&", "_")

        # Direct match
        if normalized in self._priors:
            return normalized

        # Alias match
        if normalized in self._aliases:
            return self._aliases[normalized]

        # Substring match — check if any alias is contained in the input
        for alias, canonical in self._aliases.items():
            if alias in normalized or normalized in alias:
                return canonical

        return "__default__"

    def get_prior(self, category: str) -> CategoryPrior:
        """
        Get the prior distribution for a category.

        Falls back to the default wide prior if category is unknown.
        The default prior has high sigma, meaning the Bayesian update
        will be dominated by observed data — exactly the right behavior
        for an unknown category.
        """
        key = self._resolve_category(category)
        if key == "__default__":
            return CategoryPrior(
                mu=self._default.mu,
                sigma=self._default.sigma,
                version="default_v1",
            )
        return self._priors[key]

    def get_prior_source(self, category: str) -> str:
        """
        Return the prior_source label for ElasticityEstimate.

        Returns:
            'category_benchmark' — matched a known category
            'default' — fell back to default prior
        """
        key = self._resolve_category(category)
        if key == "__default__":
            return "default"
        prior = self._priors[key]
        if prior.is_informed:
            return "merchant_history"
        return "category_benchmark"

    def update_prior(
        self,
        category: str,
        observed_elasticity: float,
        observation_noise_sigma: float = 0.5,
    ) -> CategoryPrior:
        """
        Bayesian posterior update: incorporate one new elasticity observation.

        Normal-Normal conjugate update:
            posterior_precision = prior_precision + observation_precision
            posterior_mu = (prior_mu * prior_precision + obs * obs_precision) / posterior_precision
            posterior_sigma = sqrt(1 / posterior_precision)

        Called by Tier 2 weekly batch job when outcome data reveals
        actual elasticity for a product in this category.

        Args:
            category: Product category string.
            observed_elasticity: The PED observed from a real price change.
                Should be negative for normal goods.
            observation_noise_sigma: Assumed noise in the observation.
                Lower = we trust this observation more.
                Default 0.5 is moderately noisy (single merchant, limited data).

        Returns:
            Updated CategoryPrior (also stored in-memory).
        """
        key = self._resolve_category(category)

        if key == "__default__":
            # Create a new category entry from the default prior
            prior = CategoryPrior(
                mu=self._default.mu,
                sigma=self._default.sigma,
                version="default_v1",
            )
            # Store under the raw normalized key so future lookups find it
            store_key = category.lower().strip().replace(" ", "_").replace("-", "_")
            self._priors[store_key] = prior
            key = store_key
        else:
            prior = self._priors[key]

        # Normal-Normal conjugate Bayesian update
        prior_precision = prior.precision  # 1 / sigma^2
        obs_precision = 1.0 / (observation_noise_sigma ** 2)

        posterior_precision = prior_precision + obs_precision
        posterior_mu = (
            (prior.mu * prior_precision + observed_elasticity * obs_precision)
            / posterior_precision
        )
        posterior_sigma = math.sqrt(1.0 / posterior_precision)

        # Update in place
        prior.mu = round(posterior_mu, 6)
        prior.sigma = round(posterior_sigma, 6)
        prior.sample_size += 1
        prior.last_updated = datetime.now(UTC)
        prior.version = (
            f"posterior_n{prior.sample_size}"
            if prior.sample_size > 0
            else prior.version
        )

        return prior

    def batch_update(
        self,
        category: str,
        observations: list[float],
        observation_noise_sigma: float = 0.5,
    ) -> CategoryPrior:
        """
        Update prior with multiple observations at once.

        More efficient than calling update_prior() in a loop because
        it does a single batch update using sufficient statistics.

        Args:
            category: Product category string.
            observations: List of observed PED values.
            observation_noise_sigma: Assumed noise per observation.

        Returns:
            Updated CategoryPrior.
        """
        if not observations:
            return self.get_prior(category)

        key = self._resolve_category(category)

        if key == "__default__":
            prior = CategoryPrior(
                mu=self._default.mu,
                sigma=self._default.sigma,
                version="default_v1",
            )
            store_key = category.lower().strip().replace(" ", "_").replace("-", "_")
            self._priors[store_key] = prior
            key = store_key
        else:
            prior = self._priors[key]

        n = len(observations)
        obs_mean = sum(observations) / n
        obs_variance = observation_noise_sigma ** 2

        # Normal-Normal conjugate with n observations
        prior_precision = prior.precision
        obs_precision = n / obs_variance

        posterior_precision = prior_precision + obs_precision
        posterior_mu = (
            (prior.mu * prior_precision + obs_mean * obs_precision)
            / posterior_precision
        )
        posterior_sigma = math.sqrt(1.0 / posterior_precision)

        prior.mu = round(posterior_mu, 6)
        prior.sigma = round(posterior_sigma, 6)
        prior.sample_size += n
        prior.last_updated = datetime.now(UTC)
        prior.version = f"posterior_n{prior.sample_size}"

        return prior

    def list_categories(self) -> dict[str, CategoryPrior]:
        """Return all known category priors. For debugging / admin endpoints."""
        return dict(self._priors)

    def reset_category(self, category: str) -> CategoryPrior:
        """Reset a category to its base research prior. For testing / admin."""
        key = self._resolve_category(category)
        if key == "__default__" or key not in _BASE_PRIORS:
            return self.get_prior(category)

        base = _BASE_PRIORS[key]
        self._priors[key] = CategoryPrior(
            mu=base.mu,
            sigma=base.sigma,
            sample_size=0,
            last_updated=None,
            version=base.version,
        )
        return self._priors[key]
    

    