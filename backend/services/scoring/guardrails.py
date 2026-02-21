"""
Guardrail Enforcer — Hard constraints that are never violated.

Four guardrails, checked in order:
  1. Rate limit: max 1 change per 24h per product
  2. Velocity cap: total change in 30-day window <= 20%
  3. Max single change: |change_pct| <= 10%
  4. Margin floor: new_price >= cost × (1 + min_margin_pct)

Margin floor is checked LAST because it's the absolute constraint.
If the price would violate margin, it gets clamped to the floor
even if that means exceeding max_change.

All thresholds are configurable via GuardrailConfig.

Phase 2 Scoring Engine — Guardrail layer.
Zero LLM calls. Pure Python math.

Place at: backend/services/scoring/guardrails.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Optional

from .fusion_types import (
    GuardrailConfig,
    GuardrailResult,
    GuardrailType,
    ProductContext,
)


class GuardrailEnforcer:
    """
    Applies hard guardrails to a raw price recommendation.

    Usage:
        enforcer = GuardrailEnforcer(config)
        final_price, results, was_clamped = enforcer.apply(
            raw_price=55.0,
            raw_change_pct=0.10,
            product=product_context,
        )
    """

    def __init__(self, config: Optional[GuardrailConfig] = None):
        self._config = config or GuardrailConfig()

    def apply(
        self,
        raw_price: float,
        raw_change_pct: float,
        product: ProductContext,
    ) -> tuple[float, list[GuardrailResult], bool]:
        """
        Apply all guardrails in order.

        Returns:
            (final_price, guardrail_results, was_clamped)
        """
        price = raw_price
        results: list[GuardrailResult] = []
        was_clamped = False
        g = self._config

        # ── Guardrail 1: Rate limit ──
        rate_passed, price, clamped = self._check_rate_limit(
            price, product, g,
        )
        results.append(rate_passed)
        if clamped:
            was_clamped = True
            # Rate limit forces hold — skip other guardrails
            return price, results, was_clamped

        # ── Guardrail 2: Velocity cap ──
        velocity_result, price, clamped = self._check_velocity_cap(
            price, raw_change_pct, product, g,
        )
        results.append(velocity_result)
        if clamped:
            was_clamped = True

        # ── Guardrail 3: Max single change ──
        max_change_result, price, clamped = self._check_max_change(
            price, product, g,
        )
        results.append(max_change_result)
        if clamped:
            was_clamped = True

        # ── Guardrail 4: Margin floor (absolute — checked LAST) ──
        margin_result, price, clamped = self._check_margin_floor(
            price, raw_price, product, g,
        )
        if margin_result is not None:
            results.append(margin_result)
            if clamped:
                was_clamped = True

        return round(price, 2), results, was_clamped

    # ──────────────────────────────────────────────
    # INDIVIDUAL GUARDRAILS
    # ──────────────────────────────────────────────

    @staticmethod
    def _check_rate_limit(
        price: float,
        product: ProductContext,
        config: GuardrailConfig,
    ) -> tuple[GuardrailResult, float, bool]:
        """
        Guardrail 1: No more than 1 change per rate_limit_hours.

        If a price change happened within the window, force hold.
        """
        passed = True
        clamped = False

        if product.recent_changes:
            now = datetime.now(UTC)
            cutoff = now - timedelta(hours=config.rate_limit_hours)
            recent = [c for c in product.recent_changes if c.changed_at >= cutoff]
            if recent:
                passed = False
                clamped = True
                price = product.current_price  # Force hold

        result = GuardrailResult(
            guardrail_type=GuardrailType.RATE_LIMIT,
            passed=passed,
            reason="" if passed else f"Price changed within last {config.rate_limit_hours}h",
        )
        return result, price, clamped

    @staticmethod
    def _check_velocity_cap(
        price: float,
        raw_change_pct: float,
        product: ProductContext,
        config: GuardrailConfig,
    ) -> tuple[GuardrailResult, float, bool]:
        """
        Guardrail 2: Total absolute change in window <= velocity_cap_pct.

        If prior changes consume most of the budget, reduce or block
        the current change to stay within the cap.
        """
        passed = True
        clamped = False

        if product.recent_changes and product.current_price > 0:
            now = datetime.now(UTC)
            window_start = now - timedelta(days=config.velocity_window_days)
            window_changes = [
                c for c in product.recent_changes
                if c.changed_at >= window_start
            ]
            if window_changes:
                total_prior_change = sum(abs(c.change_pct) for c in window_changes)
                proposed_change = abs(
                    (price - product.current_price) / product.current_price
                )

                if total_prior_change + proposed_change > config.velocity_cap_pct:
                    remaining = max(0.0, config.velocity_cap_pct - total_prior_change)
                    original_pct = f"{raw_change_pct:+.2%}"

                    if remaining <= 0.005:
                        # No room left — force hold
                        price = product.current_price
                    else:
                        # Reduce to remaining capacity
                        if price > product.current_price:
                            price = product.current_price * (1.0 + remaining)
                        else:
                            price = product.current_price * (1.0 - remaining)

                    passed = False
                    clamped = True

                    clamped_pct = (
                        f"{((price - product.current_price) / product.current_price):+.2%}"
                        if product.current_price > 0 else "+0.00%"
                    )

                    return GuardrailResult(
                        guardrail_type=GuardrailType.VELOCITY_CAP,
                        passed=False,
                        original_value=original_pct,
                        clamped_value=clamped_pct,
                        reason=f"Velocity cap: {config.velocity_cap_pct:.0%} in {config.velocity_window_days}d",
                    ), price, True

        return GuardrailResult(
            guardrail_type=GuardrailType.VELOCITY_CAP,
            passed=True,
        ), price, False

    @staticmethod
    def _check_max_change(
        price: float,
        product: ProductContext,
        config: GuardrailConfig,
    ) -> tuple[GuardrailResult, float, bool]:
        """
        Guardrail 3: |change_pct| <= max_change_pct.

        Clamps the price so the change doesn't exceed the max in
        either direction.
        """
        if product.current_price <= 0:
            return GuardrailResult(
                guardrail_type=GuardrailType.MAX_CHANGE,
                passed=True,
            ), price, False

        actual_change_pct = abs(
            (price - product.current_price) / product.current_price
        )

        if actual_change_pct <= config.max_change_pct:
            return GuardrailResult(
                guardrail_type=GuardrailType.MAX_CHANGE,
                passed=True,
            ), price, False

        # Clamp
        if price > product.current_price:
            clamped_price = product.current_price * (1.0 + config.max_change_pct)
        else:
            clamped_price = product.current_price * (1.0 - config.max_change_pct)

        return GuardrailResult(
            guardrail_type=GuardrailType.MAX_CHANGE,
            passed=False,
            original_value=f"{actual_change_pct:.2%}",
            clamped_value=f"{config.max_change_pct:.2%}",
            reason=f"Max single change: {config.max_change_pct:.0%}",
        ), clamped_price, True

    @staticmethod
    def _check_margin_floor(
        price: float,
        raw_price: float,
        product: ProductContext,
        config: GuardrailConfig,
    ) -> tuple[Optional[GuardrailResult], float, bool]:
        """
        Guardrail 4: new_price >= cost × (1 + min_margin_pct).

        Only applies when product cost is known.
        Returns None for the result if cost is unknown (guardrail skipped).
        """
        if product.cost is None or product.cost <= 0:
            return None, price, False

        margin_floor_price = product.cost * (1.0 + config.min_margin_pct)

        if price >= margin_floor_price:
            return GuardrailResult(
                guardrail_type=GuardrailType.MARGIN_FLOOR,
                passed=True,
            ), price, False

        return GuardrailResult(
            guardrail_type=GuardrailType.MARGIN_FLOOR,
            passed=False,
            original_value=f"{raw_price:.2f}",
            clamped_value=f"{margin_floor_price:.2f}",
            reason=f"Margin floor: cost ${product.cost:.2f} × {1 + config.min_margin_pct:.2f}",
        ), margin_floor_price, True
    

    