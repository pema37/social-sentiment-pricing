"""
Thompson Sampling Bandit — Multi-armed bandit for pricing strategy selection.

Beta-Bernoulli model with revenue-weighted arm selection:
  1. For each arm k, maintain Beta(α_k, β_k)
  2. Sample θ_k ~ Beta(α_k, β_k)
  3. Select arm maximizing: strategy_value × θ_k
  4. Update: α_k += successes, β_k += failures

Success is defined as: recommendation was acted on AND revenue_delta > 0.

Cold start: Beta(1, 19) = 5% expected success rate (typical conversion baseline).
Hierarchical: when a new category appears, its priors can be initialized from
the population-level posterior across all categories.

Phase 3 Intelligence Environment — Block B, File 6.

Place at: backend/services/scoring/experimentation/bandit.py
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class ArmState:
    """
    State of one bandit arm (strategy) in one category.

    Beta(α, β) distribution:
    - Mean = α / (α + β)
    - Variance = αβ / ((α+β)²(α+β+1))
    - Higher α → more evidence of success
    - Higher β → more evidence of failure
    """

    strategy_name: str
    alpha: float = 1.0  # Successes + prior
    beta: float = 19.0  # Failures + prior
    n_selections: int = 0  # Times this arm was chosen
    n_rewards: int = 0  # Times a reward (success) was observed
    n_updates: int = 0  # Total outcome observations
    total_reward: float = 0.0  # Cumulative reward (for revenue-weighted)
    last_selected: datetime | None = None
    last_updated: datetime | None = None

    @property
    def mean(self) -> float:
        """Expected success rate: α / (α + β)."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """Variance of the Beta distribution."""
        ab = self.alpha + self.beta
        return (self.alpha * self.beta) / (ab * ab * (ab + 1))

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    @property
    def confidence_width(self) -> float:
        """95% credible interval width (approximate)."""
        return 4 * self.std  # ≈ 2 std on each side

    @property
    def is_explored(self) -> bool:
        """Has this arm been selected at least once?"""
        return self.n_selections > 0

    def sample(self, rng: random.Random | None = None) -> float:
        """
        Sample from Beta(α, β).

        Uses the provided RNG for reproducibility in tests,
        or module-level random if not provided.
        """
        r = rng or random
        return r.betavariate(self.alpha, self.beta)

    def to_dict(self) -> dict:
        """Serialize for DB persistence or API response."""
        return {
            "strategy_name": self.strategy_name,
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "n_selections": self.n_selections,
            "n_rewards": self.n_rewards,
            "n_updates": self.n_updates,
            "total_reward": round(self.total_reward, 2),
            "last_selected": self.last_selected.isoformat() if self.last_selected else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ArmState:
        """Deserialize from DB or API."""
        return cls(
            strategy_name=d["strategy_name"],
            alpha=d["alpha"],
            beta=d["beta"],
            n_selections=d.get("n_selections", 0),
            n_rewards=d.get("n_rewards", 0),
            n_updates=d.get("n_updates", 0),
            total_reward=d.get("total_reward", 0.0),
            last_selected=datetime.fromisoformat(d["last_selected"]) if d.get("last_selected") else None,
            last_updated=datetime.fromisoformat(d["last_updated"]) if d.get("last_updated") else None,
        )


@dataclass
class SelectionResult:
    """Result of an arm selection (for logging and experiment tracking)."""

    selected_arm: str
    category: str
    sampled_values: dict[str, float]  # {arm_name: sampled_theta}
    selection_reason: str  # "thompson_sampling" or "exploration"
    is_exploration: bool = False


# ──────────────────────────────────────────────────────────
# THOMPSON SAMPLING BANDIT
# ──────────────────────────────────────────────────────────


class ThompsonSamplingBandit:
    """
    Multi-armed bandit using Thompson Sampling for strategy selection.

    Maintains per-category arm states. Each category independently
    learns which pricing strategy works best.

    Usage:
        bandit = ThompsonSamplingBandit(
            arm_names=["conservative", "elasticity_optimal", "competitive", "premium"]
        )

        # At recommendation time:
        result = bandit.select_arm("electronics")
        # result.selected_arm = "elasticity_optimal"

        # After outcome measured:
        bandit.update("electronics", "elasticity_optimal", success=True, reward=3.5)

        # Check convergence:
        winner = bandit.get_leader("electronics")
    """

    def __init__(
        self,
        arm_names: list[str],
        default_alpha: float = 1.0,
        default_beta: float = 19.0,
        exploration_rate: float = 0.05,
        seed: int | None = None,
    ):
        """
        Args:
            arm_names: Strategy names (one per arm).
            default_alpha: Initial α for new arms. Beta(1, 19) = 5% baseline.
            default_beta: Initial β.
            exploration_rate: Fraction of selections that are pure random (0-1).
                0.05 = 5% exploration holdout for unbiased estimates.
            seed: Random seed for reproducibility.
        """
        if not arm_names:
            raise ValueError("Must provide at least one arm name")

        self._arm_names = list(arm_names)
        self._default_alpha = default_alpha
        self._default_beta = default_beta
        self._exploration_rate = exploration_rate
        self._rng = random.Random(seed) if seed is not None else random.Random()

        # Per-category arm states: {category: {arm_name: ArmState}}
        self._states: dict[str, dict[str, ArmState]] = {}

    @property
    def arm_names(self) -> list[str]:
        return list(self._arm_names)

    @property
    def categories(self) -> list[str]:
        return list(self._states.keys())

    def _ensure_category(self, category: str) -> dict[str, ArmState]:
        """Initialize arm states for a category if not already present."""
        if category not in self._states:
            self._states[category] = {
                name: ArmState(
                    strategy_name=name,
                    alpha=self._default_alpha,
                    beta=self._default_beta,
                )
                for name in self._arm_names
            }
        return self._states[category]

    # ──────────────────────────────────────────────
    # ARM SELECTION
    # ──────────────────────────────────────────────

    def select_arm(self, category: str) -> SelectionResult:
        """
        Select a strategy arm for this category using Thompson Sampling.

        With probability exploration_rate, selects uniformly at random
        (for unbiased holdout data). Otherwise, samples from each arm's
        Beta posterior and selects the highest.

        Returns SelectionResult with the selected arm and all sampled values.
        """
        arms = self._ensure_category(category)
        now = datetime.now(UTC)

        # ── Exploration check ──
        is_exploration = self._rng.random() < self._exploration_rate

        if is_exploration:
            selected = self._rng.choice(self._arm_names)
            sampled = {name: arm.sample(self._rng) for name, arm in arms.items()}
            arms[selected].n_selections += 1
            arms[selected].last_selected = now
            return SelectionResult(
                selected_arm=selected,
                category=category,
                sampled_values=sampled,
                selection_reason="exploration_holdout",
                is_exploration=True,
            )

        # ── Thompson Sampling ──
        sampled = {}
        for name, arm in arms.items():
            sampled[name] = arm.sample(self._rng)

        selected = max(sampled, key=sampled.get)
        arms[selected].n_selections += 1
        arms[selected].last_selected = now

        return SelectionResult(
            selected_arm=selected,
            category=category,
            sampled_values=sampled,
            selection_reason="thompson_sampling",
            is_exploration=False,
        )

    # ──────────────────────────────────────────────
    # OUTCOME UPDATE
    # ──────────────────────────────────────────────

    def update(
        self,
        category: str,
        arm_name: str,
        success: bool,
        reward: float = 0.0,
    ) -> ArmState:
        """
        Update arm posterior with an observed outcome.

        Args:
            category: Product category.
            arm_name: Which strategy was used.
            success: True if the recommendation produced positive revenue lift.
            reward: Revenue lift % (for weighted tracking, not used in Beta update).

        Returns:
            Updated ArmState.
        """
        arms = self._ensure_category(category)
        if arm_name not in arms:
            raise KeyError(f"Unknown arm '{arm_name}'. Available: {list(arms.keys())}")

        arm = arms[arm_name]

        if success:
            arm.alpha += 1
            arm.n_rewards += 1
        else:
            arm.beta += 1

        arm.n_updates += 1
        arm.total_reward += reward
        arm.last_updated = datetime.now(UTC)

        return arm

    def batch_update(
        self,
        category: str,
        arm_name: str,
        successes: int,
        failures: int,
        total_reward: float = 0.0,
    ) -> ArmState:
        """
        Batch update with aggregated outcomes.

        More efficient than calling update() in a loop.
        Used by experiment_tasks.py daily batch.
        """
        arms = self._ensure_category(category)
        if arm_name not in arms:
            raise KeyError(f"Unknown arm '{arm_name}'")

        arm = arms[arm_name]
        arm.alpha += successes
        arm.beta += failures
        arm.n_rewards += successes
        arm.n_updates += successes + failures
        arm.total_reward += total_reward
        arm.last_updated = datetime.now(UTC)

        return arm

    # ──────────────────────────────────────────────
    # ANALYSIS
    # ──────────────────────────────────────────────

    def get_arm_state(self, category: str, arm_name: str) -> ArmState:
        """Get current state of one arm in one category."""
        arms = self._ensure_category(category)
        return arms[arm_name]

    def get_category_states(self, category: str) -> dict[str, ArmState]:
        """Get all arm states for a category."""
        return dict(self._ensure_category(category))

    def get_leader(self, category: str) -> str | None:
        """
        Get the current leading arm (highest posterior mean).

        Returns None if no arm has been updated yet.
        """
        arms = self._ensure_category(category)
        updated_arms = {n: a for n, a in arms.items() if a.n_updates > 0}
        if not updated_arms:
            return None
        return max(updated_arms, key=lambda n: updated_arms[n].mean)

    def has_converged(
        self,
        category: str,
        min_selections: int = 30,
        separation_threshold: float = 0.10,
    ) -> tuple[bool, str | None]:
        """
        Check if the bandit has converged on a winner for this category.

        Convergence requires:
        1. Every arm has been selected min_selections times
        2. The leader's mean is at least separation_threshold above the runner-up
        3. The leader's 95% CI lower bound is above the runner-up's mean

        Returns: (converged: bool, winner: Optional[str])
        """
        arms = self._ensure_category(category)

        # Check minimum selections
        for arm in arms.values():
            if arm.n_selections < min_selections:
                return False, None

        # Sort by posterior mean (descending)
        sorted_arms = sorted(arms.values(), key=lambda a: a.mean, reverse=True)
        leader = sorted_arms[0]
        runner_up = sorted_arms[1] if len(sorted_arms) > 1 else None

        if runner_up is None:
            return True, leader.strategy_name

        # Check separation
        separation = leader.mean - runner_up.mean
        if separation < separation_threshold:
            return False, None

        # Check CI overlap: leader's lower bound > runner-up's mean
        leader_lower = leader.mean - 2 * leader.std
        if leader_lower <= runner_up.mean:
            return False, None

        return True, leader.strategy_name

    def get_probabilities(self, category: str, n_samples: int = 1000) -> dict[str, float]:
        """
        Estimate the probability that each arm is the best.

        Monte Carlo: sample from each arm's posterior n_samples times,
        count how often each arm wins.
        """
        arms = self._ensure_category(category)
        wins = {name: 0 for name in arms}

        for _ in range(n_samples):
            samples = {name: arm.sample(self._rng) for name, arm in arms.items()}
            winner = max(samples, key=samples.get)
            wins[winner] += 1

        return {name: round(count / n_samples, 4) for name, count in wins.items()}

    # ──────────────────────────────────────────────
    # HIERARCHICAL PRIORS
    # ──────────────────────────────────────────────

    def initialize_from_population(
        self,
        category: str,
        population_states: dict[str, ArmState],
        weight: float = 0.5,
    ) -> None:
        """
        Initialize a new category's priors from population-level posteriors.

        Used for cold start: when a new category appears, transfer
        knowledge from the aggregate experience across all categories.

        Args:
            category: New category to initialize.
            population_states: Aggregate arm states across all categories.
            weight: How much to weight population vs default prior (0-1).
                0 = ignore population (pure default)
                1 = fully adopt population posterior
        """
        arms = self._ensure_category(category)

        for name, arm in arms.items():
            if name in population_states:
                pop = population_states[name]
                arm.alpha = weight * pop.alpha + (1 - weight) * self._default_alpha
                arm.beta = weight * pop.beta + (1 - weight) * self._default_beta

    def get_population_state(self) -> dict[str, ArmState]:
        """
        Compute population-level posteriors across all categories.

        Aggregates α and β from all categories, weighted equally.
        Used as hierarchical prior for new categories.
        """
        if not self._states:
            return {}

        population = {}
        n_cats = len(self._states)

        for arm_name in self._arm_names:
            total_alpha = 0.0
            total_beta = 0.0
            total_selections = 0
            total_rewards = 0
            total_updates = 0

            for cat_arms in self._states.values():
                if arm_name in cat_arms:
                    arm = cat_arms[arm_name]
                    total_alpha += arm.alpha
                    total_beta += arm.beta
                    total_selections += arm.n_selections
                    total_rewards += arm.n_rewards
                    total_updates += arm.n_updates

            # Average across categories for the prior
            population[arm_name] = ArmState(
                strategy_name=arm_name,
                alpha=total_alpha / n_cats,
                beta=total_beta / n_cats,
                n_selections=total_selections,
                n_rewards=total_rewards,
                n_updates=total_updates,
            )

        return population

    # ──────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        """
        Serialize full bandit state for DB persistence.

        Store this in a JSONB column or Redis hash.
        """
        return {
            "arm_names": self._arm_names,
            "default_alpha": self._default_alpha,
            "default_beta": self._default_beta,
            "exploration_rate": self._exploration_rate,
            "categories": {
                cat: {name: arm.to_dict() for name, arm in arms.items()} for cat, arms in self._states.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict, seed: int | None = None) -> ThompsonSamplingBandit:
        """Restore bandit state from persisted data."""
        bandit = cls(
            arm_names=d["arm_names"],
            default_alpha=d.get("default_alpha", 1.0),
            default_beta=d.get("default_beta", 19.0),
            exploration_rate=d.get("exploration_rate", 0.05),
            seed=seed,
        )
        for cat, arms_dict in d.get("categories", {}).items():
            bandit._states[cat] = {name: ArmState.from_dict(arm_data) for name, arm_data in arms_dict.items()}
        return bandit
