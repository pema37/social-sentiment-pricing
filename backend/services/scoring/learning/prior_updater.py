"""
Prior Updater — Safe, dampened updates to CategoryPriorStore from outcome data.

This is the safety layer between raw feature_engineer output and the
scoring engine's Bayesian priors. Without this layer, a single batch
of noisy observations could radically shift pricing behavior.

Dampening strategies (from Phase 3 plan Section 3.4):
  1. EMA blending: new posterior = 0.97 × old + 0.03 × raw_new
  2. Bounded shift: category mu can move max 15% per weekly cycle
  3. Minimum observations: skip categories with < 3 elasticity observations
  4. Outlier filtering: drop observations outside 3σ of current prior
  5. Audit trail: every update logged with before/after for rollback

Phase 3 Intelligence Environment — Block A, File 2.
Called by batch_tasks.py (File 4) weekly.

Place at: backend/services/scoring/learning/prior_updater.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Phase 2 imports (duck-typed for testing without actual imports)
# In production: from services.scoring.category_priors import CategoryPriorStore, CategoryPrior
# Here we define the protocol so this file is self-contained for testing.


@dataclass
class UpdateConfig:
    """Configuration for dampened prior updates."""

    # ── EMA dampening ──
    ema_decay: float = 0.97
    """Blend factor: new_mu = decay × old_mu + (1-decay) × raw_posterior_mu.
    Higher = more conservative (slower to change). 0.97 = system remembers
    97% of previous belief, incorporates 3% of new evidence per cycle."""

    # ── Bounded shift ──
    max_mu_shift_pct: float = 0.15
    """Maximum allowed shift in mu per update cycle, as fraction of |current mu|.
    0.15 = mu can move at most 15% per week. Prevents a single bad batch
    from radically changing pricing behavior."""

    max_sigma_reduction_pct: float = 0.25
    """Maximum allowed reduction in sigma per cycle. 0.25 = sigma can shrink
    at most 25% per week. Prevents premature confidence from a few observations."""

    # ── Minimum data requirements ──
    min_observations: int = 3
    """Skip update if category has fewer than this many elasticity observations.
    With < 3, the sample is too small to be meaningful."""

    # ── Outlier filtering ──
    outlier_sigma_threshold: float = 3.0
    """Drop observations more than this many σ from the current prior mu.
    Prevents extreme noise from corrupting the prior."""

    # ── Exploration preference ──
    prefer_exploration_data: bool = True
    """When True, weight observations from the 5% exploration holdout
    more heavily (lower noise sigma), since they provide unbiased
    causal estimates vs confounded production data."""

    exploration_noise_sigma: float = 0.3
    """Noise sigma for exploration observations (more trusted)."""

    production_noise_sigma: float = 0.5
    """Noise sigma for production observations (potentially confounded)."""


@dataclass
class PriorSnapshot:
    """Snapshot of a prior before/after update for audit trail."""

    category: str
    before_mu: float
    before_sigma: float
    before_sample_size: int
    after_mu: float
    after_sigma: float
    after_sample_size: int
    raw_posterior_mu: float  # What the posterior would be without dampening
    raw_posterior_sigma: float
    observations_received: int  # Total from feature_engineer
    observations_used: int  # After outlier filtering
    observations_dropped: int  # Outlier-filtered count
    was_dampened: bool  # True if EMA or bounds changed the raw posterior
    dampening_applied: list[str]  # Which dampening strategies fired
    skipped: bool = False  # True if update was skipped entirely
    skip_reason: str | None = None


@dataclass
class UpdateResult:
    """Result of a full prior update cycle across all categories."""

    updated_categories: list[PriorSnapshot]
    skipped_categories: list[PriorSnapshot]
    total_observations_processed: int
    total_categories_updated: int
    total_categories_skipped: int
    cycle_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class PriorUpdater:
    """
    Safely updates CategoryPriorStore from FeatureEngineer output.

    Usage:
        from services.scoring.category_priors import CategoryPriorStore
        from services.scoring.learning.feature_engineer import FeatureEngineer

        store = CategoryPriorStore()
        fe = FeatureEngineer()
        updater = PriorUpdater(store)

        # In weekly Celery task:
        features = fe.compute(outcome_records)
        result = updater.update_all(features)
        # result.updated_categories has audit trail
    """

    def __init__(
        self,
        prior_store,  # CategoryPriorStore (duck-typed)
        config: UpdateConfig | None = None,
    ):
        self._store = prior_store
        self._config = config or UpdateConfig()
        self._history: list[UpdateResult] = []

    @property
    def config(self) -> UpdateConfig:
        return self._config

    @property
    def history(self) -> list[UpdateResult]:
        """Audit trail of all update cycles."""
        return list(self._history)

    def update_all(
        self,
        category_features: dict,  # dict[str, CategoryFeatures]
    ) -> UpdateResult:
        """
        Update priors for all categories with new outcome data.

        Args:
            category_features: Output of FeatureEngineer.compute().
                Keys are category names, values are CategoryFeatures.

        Returns:
            UpdateResult with audit trail for every category.
        """
        updated = []
        skipped = []
        total_obs = 0

        for category, features in category_features.items():
            total_obs += features.elasticity_n
            snapshot = self._update_category(category, features)

            if snapshot.skipped:
                skipped.append(snapshot)
            else:
                updated.append(snapshot)

        result = UpdateResult(
            updated_categories=updated,
            skipped_categories=skipped,
            total_observations_processed=total_obs,
            total_categories_updated=len(updated),
            total_categories_skipped=len(skipped),
        )

        self._history.append(result)
        return result

    def update_single(
        self,
        category: str,
        observed_elasticities: list[float],
        exploration_flags: list[bool] | None = None,
    ) -> PriorSnapshot:
        """
        Update a single category's prior. Lower-level than update_all().

        Args:
            category: Category name.
            observed_elasticities: Raw PED observations.
            exploration_flags: Per-observation flag, True if from exploration holdout.

        Returns:
            PriorSnapshot with audit trail.
        """
        return self._update_from_observations(category, observed_elasticities, exploration_flags)

    # ──────────────────────────────────────────────
    # INTERNAL: Category update pipeline
    # ──────────────────────────────────────────────

    def _update_category(self, category: str, features) -> PriorSnapshot:
        """Update one category from its CategoryFeatures."""
        elasticities = features.observed_elasticities

        # Check minimum observation requirement
        if len(elasticities) < self._config.min_observations:
            prior = self._store.get_prior(category)
            return PriorSnapshot(
                category=category,
                before_mu=prior.mu,
                before_sigma=prior.sigma,
                before_sample_size=prior.sample_size,
                after_mu=prior.mu,
                after_sigma=prior.sigma,
                after_sample_size=prior.sample_size,
                raw_posterior_mu=prior.mu,
                raw_posterior_sigma=prior.sigma,
                observations_received=len(elasticities),
                observations_used=0,
                observations_dropped=0,
                was_dampened=False,
                dampening_applied=[],
                skipped=True,
                skip_reason=f"Insufficient observations: {len(elasticities)} < {self._config.min_observations}",
            )

        # No per-observation exploration flags from CategoryFeatures,
        # so pass None (all treated as production data)
        return self._update_from_observations(category, elasticities)

    def _update_from_observations(
        self,
        category: str,
        raw_observations: list[float],
        exploration_flags: list[bool] | None = None,
    ) -> PriorSnapshot:
        """Core update logic with full dampening pipeline."""

        cfg = self._config
        prior = self._store.get_prior(category)

        before_mu = prior.mu
        before_sigma = prior.sigma
        before_n = prior.sample_size

        # ── Step 1: Outlier filtering ──
        filtered, n_dropped = self._filter_outliers(raw_observations, prior.mu, prior.sigma)

        if not filtered:
            return PriorSnapshot(
                category=category,
                before_mu=before_mu,
                before_sigma=before_sigma,
                before_sample_size=before_n,
                after_mu=before_mu,
                after_sigma=before_sigma,
                after_sample_size=before_n,
                raw_posterior_mu=before_mu,
                raw_posterior_sigma=before_sigma,
                observations_received=len(raw_observations),
                observations_used=0,
                observations_dropped=n_dropped,
                was_dampened=False,
                dampening_applied=[],
                skipped=True,
                skip_reason="All observations filtered as outliers",
            )

        # ── Step 2: Compute raw posterior (what batch_update would give) ──
        # We compute it manually to get the raw values before dampening
        raw_mu, raw_sigma = self._compute_raw_posterior(
            prior.mu, prior.sigma, filtered, exploration_flags, raw_observations
        )

        # ── Step 3: Apply dampening ──
        dampened_mu = raw_mu
        dampened_sigma = raw_sigma
        dampening_applied = []

        # 3a: EMA blending on mu
        ema_mu = cfg.ema_decay * before_mu + (1 - cfg.ema_decay) * raw_mu
        if abs(ema_mu - raw_mu) > 1e-6:
            dampened_mu = ema_mu
            dampening_applied.append(f"EMA(decay={cfg.ema_decay}): raw_mu={raw_mu:.4f} → ema_mu={ema_mu:.4f}")

        # 3b: Bounded shift on mu
        if before_mu != 0:
            max_shift = abs(before_mu) * cfg.max_mu_shift_pct
            actual_shift = dampened_mu - before_mu

            if abs(actual_shift) > max_shift:
                clamped_mu = before_mu + math.copysign(max_shift, actual_shift)
                dampening_applied.append(
                    f"BoundedShift(max={cfg.max_mu_shift_pct:.0%}): "
                    f"shift={actual_shift:.4f} clamped to {clamped_mu - before_mu:.4f}"
                )
                dampened_mu = clamped_mu

        # 3c: EMA blending on sigma
        ema_sigma = cfg.ema_decay * before_sigma + (1 - cfg.ema_decay) * raw_sigma
        dampened_sigma = ema_sigma

        # 3d: Bounded sigma reduction (prevent premature confidence)
        min_sigma = before_sigma * (1 - cfg.max_sigma_reduction_pct)
        if dampened_sigma < min_sigma:
            dampening_applied.append(
                f"BoundedSigma(max_reduction={cfg.max_sigma_reduction_pct:.0%}): "
                f"sigma={dampened_sigma:.4f} clamped to {min_sigma:.4f}"
            )
            dampened_sigma = min_sigma

        was_dampened = len(dampening_applied) > 0

        # ── Step 4: Apply to the store ──
        # We bypass batch_update() and set values directly since we've
        # already computed the dampened posterior
        prior.mu = round(dampened_mu, 6)
        prior.sigma = round(dampened_sigma, 6)
        prior.sample_size += len(filtered)
        prior.last_updated = datetime.now(UTC)
        prior.version = f"dampened_n{prior.sample_size}"

        return PriorSnapshot(
            category=category,
            before_mu=round(before_mu, 6),
            before_sigma=round(before_sigma, 6),
            before_sample_size=before_n,
            after_mu=prior.mu,
            after_sigma=prior.sigma,
            after_sample_size=prior.sample_size,
            raw_posterior_mu=round(raw_mu, 6),
            raw_posterior_sigma=round(raw_sigma, 6),
            observations_received=len(raw_observations),
            observations_used=len(filtered),
            observations_dropped=n_dropped,
            was_dampened=was_dampened,
            dampening_applied=dampening_applied,
        )

    # ──────────────────────────────────────────────
    # INTERNAL: Math helpers
    # ──────────────────────────────────────────────

    def _filter_outliers(
        self,
        observations: list[float],
        prior_mu: float,
        prior_sigma: float,
    ) -> tuple[list[float], int]:
        """
        Remove observations more than outlier_sigma_threshold × σ from prior mu.

        Returns: (filtered_observations, num_dropped)
        """
        threshold = self._config.outlier_sigma_threshold
        cutoff = threshold * prior_sigma

        filtered = [obs for obs in observations if abs(obs - prior_mu) <= cutoff]
        return filtered, len(observations) - len(filtered)

    def _compute_raw_posterior(
        self,
        prior_mu: float,
        prior_sigma: float,
        filtered_obs: list[float],
        exploration_flags: list[bool] | None,
        raw_observations: list[float],
    ) -> tuple[float, float]:
        """
        Compute the raw Bayesian posterior (before dampening).

        Uses Normal-Normal conjugate update, matching CategoryPriorStore math.
        If exploration_flags provided, exploration observations get lower noise.
        """
        cfg = self._config
        prior_precision = 1.0 / (prior_sigma**2)

        # Separate observations by trust level if flags provided
        if (
            exploration_flags is not None
            and cfg.prefer_exploration_data
            and len(exploration_flags) == len(raw_observations)
        ):
            # Build a mapping from raw obs to their flags
            # Only use flags for observations that survived filtering
            filtered_set = set()
            raw_idx = 0
            obs_with_noise = []

            for i, obs in enumerate(raw_observations):
                if raw_idx < len(filtered_obs) and abs(obs - filtered_obs[raw_idx]) < 1e-10:
                    is_explore = exploration_flags[i] if i < len(exploration_flags) else False
                    noise = cfg.exploration_noise_sigma if is_explore else cfg.production_noise_sigma
                    obs_with_noise.append((filtered_obs[raw_idx], noise))
                    raw_idx += 1

            # If mapping didn't work cleanly, fall back to uniform noise
            if len(obs_with_noise) != len(filtered_obs):
                obs_with_noise = [(obs, cfg.production_noise_sigma) for obs in filtered_obs]
        else:
            obs_with_noise = [(obs, cfg.production_noise_sigma) for obs in filtered_obs]

        # Accumulate precision-weighted observations
        total_obs_precision = 0.0
        precision_weighted_sum = 0.0

        for obs, noise_sigma in obs_with_noise:
            obs_precision = 1.0 / (noise_sigma**2)
            total_obs_precision += obs_precision
            precision_weighted_sum += obs * obs_precision

        posterior_precision = prior_precision + total_obs_precision
        posterior_mu = (prior_mu * prior_precision + precision_weighted_sum) / posterior_precision
        posterior_sigma = math.sqrt(1.0 / posterior_precision)

        return posterior_mu, posterior_sigma
