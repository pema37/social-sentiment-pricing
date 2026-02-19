"""
Agent Boundary Validation
==========================
Phase 4 — Reasoning Protocols

Runtime validation at every agent boundary. Wraps agent calls to:
  1. Validate inputs before the agent runs
  2. Validate outputs after the agent returns
  3. Convert Pydantic errors into structured ContractViolation
  4. Log validation failures with full diagnostic context
  5. Provide fallback behavior for graceful degradation

Usage:
    validated_scout = AgentValidator.validate_scout_output(raw_dict)
    validated_analyst = AgentValidator.validate_analyst_output(raw_dict, scout_hash)

Location: backend/schemas/agent_contracts/validation.py
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from pydantic import ValidationError

from .contracts_v2 import (
    AnalystInput,
    AnalystOutput,
    ContractViolation,
    ScoutInput,
    ScoutOutput,
    StrategistInput,
    StrategistOutput,
    compute_provenance_hash,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Validation result wrapper
# ---------------------------------------------------------------------------

class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"     # Some fields invalid but usable with defaults


class ValidationResult:
    """
    Result of a contract validation attempt.

    Contains the validated model (if successful), errors (if failed),
    and diagnostic information for tracing.
    """

    def __init__(
        self,
        status: ValidationStatus,
        agent: str,
        model: Optional[Any] = None,
        errors: Optional[list[ContractViolation]] = None,
        raw_output: Optional[dict] = None,
        duration_ms: float = 0.0,
    ):
        self.status = status
        self.agent = agent
        self.model = model
        self.errors = errors or []
        self.raw_output = raw_output
        self.duration_ms = duration_ms

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID

    def raise_if_invalid(self) -> None:
        """Raise the first ContractViolation if validation failed."""
        if not self.is_valid and self.errors:
            raise self.errors[0]

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "agent": self.agent,
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "duration_ms": round(self.duration_ms, 2),
        }


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

class AgentValidator:
    """
    Validates agent inputs and outputs against their semantic contracts.

    Methods are static — no state. Call from anywhere in the pipeline.

    Error handling strategy:
    - On validation failure, log the full error + raw output
    - Return ValidationResult with structured errors
    - Caller decides whether to halt, fallback, or retry
    """

    @staticmethod
    def validate_scout_input(raw: dict) -> ValidationResult:
        """Validate data before it goes to the Scout agent."""
        return AgentValidator._validate("scout", ScoutInput, raw)

    @staticmethod
    def validate_scout_output(raw: dict) -> ValidationResult:
        """Validate the Scout agent's output."""
        return AgentValidator._validate("scout", ScoutOutput, raw)

    @staticmethod
    def validate_analyst_input(
        scout_output: ScoutOutput,
        category_priors: Optional[dict] = None,
        historical_outcomes: Optional[list] = None,
    ) -> ValidationResult:
        """
        Validate data before it goes to the Analyst agent.

        Automatically computes provenance hash from Scout output.
        """
        raw = {
            "scout_output": scout_output.model_dump(mode="json"),
            "scout_provenance_hash": scout_output.provenance_hash,
            "category_priors": category_priors,
            "historical_outcomes": historical_outcomes,
        }
        return AgentValidator._validate("analyst", AnalystInput, raw)

    @staticmethod
    def validate_analyst_output(raw: dict) -> ValidationResult:
        """Validate the Analyst agent's output."""
        return AgentValidator._validate("analyst", AnalystOutput, raw)

    @staticmethod
    def validate_strategist_input(
        analyst_output: AnalystOutput,
        scout_output: ScoutOutput,
        merchant_preferences: Optional[dict] = None,
        experiment_overrides: Optional[dict] = None,
    ) -> ValidationResult:
        """
        Validate data before it goes to the Strategist agent.

        Automatically computes provenance hash from Analyst output.
        """
        raw = {
            "analyst_output": analyst_output.model_dump(mode="json"),
            "analyst_provenance_hash": analyst_output.provenance_hash,
            "scout_output": scout_output.model_dump(mode="json"),
            "merchant_preferences": merchant_preferences,
            "experiment_overrides": experiment_overrides,
        }
        return AgentValidator._validate("strategist", StrategistInput, raw)

    @staticmethod
    def validate_strategist_output(raw: dict) -> ValidationResult:
        """Validate the Strategist agent's output."""
        return AgentValidator._validate("strategist", StrategistOutput, raw)

    # -------------------------------------------------------------------
    # Private: core validation logic
    # -------------------------------------------------------------------

    @staticmethod
    def _validate(agent: str, model_class: type, raw: dict) -> ValidationResult:
        """
        Attempt to validate raw dict against a Pydantic model.

        Converts Pydantic ValidationError into ContractViolation list.
        """
        t0 = time.monotonic()
        try:
            validated = model_class.model_validate(raw)
            duration = (time.monotonic() - t0) * 1000
            return ValidationResult(
                status=ValidationStatus.VALID,
                agent=agent,
                model=validated,
                raw_output=raw,
                duration_ms=duration,
            )
        except ValidationError as exc:
            duration = (time.monotonic() - t0) * 1000
            errors = []
            for error in exc.errors():
                field_path = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(ContractViolation(
                    agent=agent,
                    field=field_path,
                    value=error.get("input"),
                    constraint=error["msg"],
                    raw_output=raw,
                ))

            logger.warning(
                "[Contract] %s output validation failed: %d errors. First: %s",
                agent, len(errors), errors[0] if errors else "unknown",
            )

            return ValidationResult(
                status=ValidationStatus.INVALID,
                agent=agent,
                errors=errors,
                raw_output=raw,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.error(
                "[Contract] Unexpected error validating %s: %s",
                agent, exc, exc_info=True,
            )
            return ValidationResult(
                status=ValidationStatus.INVALID,
                agent=agent,
                errors=[ContractViolation(
                    agent=agent,
                    field="__root__",
                    value=None,
                    constraint=f"Unexpected error: {exc}",
                    raw_output=raw,
                )],
                raw_output=raw,
                duration_ms=duration,
            )


# ---------------------------------------------------------------------------
# Pipeline validator: wraps full Scout → Analyst → Strategist flow
# ---------------------------------------------------------------------------

class PipelineValidator:
    """
    Validates the entire Scout → Analyst → Strategist pipeline.

    Wraps each agent call with input/output validation and provenance
    chain verification. If any validation fails, returns structured
    diagnostics showing exactly which agent and field failed.
    """

    def __init__(
        self,
        scout_fn: Callable[[ScoutInput], dict],
        analyst_fn: Callable[[AnalystInput], dict],
        strategist_fn: Callable[[StrategistInput], dict],
        strict: bool = True,
    ):
        """
        Args:
            scout_fn: Callable that runs the Scout agent
            analyst_fn: Callable that runs the Analyst agent
            strategist_fn: Callable that runs the Strategist agent
            strict: If True, halt on any validation failure.
                    If False, continue with best-effort results.
        """
        self._scout_fn = scout_fn
        self._analyst_fn = analyst_fn
        self._strategist_fn = strategist_fn
        self._strict = strict

    def run_validated_pipeline(
        self, scout_input_data: dict
    ) -> dict[str, Any]:
        """
        Run the full pipeline with contract validation at every boundary.

        Returns:
            {
                "scout_output": ScoutOutput | None,
                "analyst_output": AnalystOutput | None,
                "strategist_output": StrategistOutput | None,
                "validations": [ValidationResult, ...],
                "provenance_chain": {scout_hash, analyst_hash, strategist_hash},
                "success": bool,
            }
        """
        validations: list[ValidationResult] = []
        provenance: dict[str, str] = {}

        # Step 1: Validate Scout input
        scout_input_result = AgentValidator.validate_scout_input(scout_input_data)
        validations.append(scout_input_result)
        if not scout_input_result.is_valid:
            if self._strict:
                return self._failure_result(validations, provenance, "Scout input invalid")
            logger.warning("Scout input validation failed (non-strict), continuing")

        # Step 2: Run Scout
        try:
            scout_raw = self._scout_fn(scout_input_result.model or scout_input_data)
        except Exception as exc:
            validations.append(ValidationResult(
                status=ValidationStatus.INVALID, agent="scout",
                errors=[ContractViolation("scout", "__call__", None, str(exc))],
            ))
            return self._failure_result(validations, provenance, f"Scout execution failed: {exc}")

        # Step 3: Validate Scout output
        scout_output_result = AgentValidator.validate_scout_output(scout_raw)
        validations.append(scout_output_result)
        if not scout_output_result.is_valid:
            if self._strict:
                return self._failure_result(validations, provenance, "Scout output invalid")

        scout_output: ScoutOutput = scout_output_result.model
        provenance["scout_hash"] = scout_output.provenance_hash

        # Step 4: Validate Analyst input (with provenance)
        analyst_input_result = AgentValidator.validate_analyst_input(scout_output)
        validations.append(analyst_input_result)

        # Step 5: Run Analyst
        try:
            analyst_raw = self._analyst_fn(analyst_input_result.model or scout_output)
        except Exception as exc:
            validations.append(ValidationResult(
                status=ValidationStatus.INVALID, agent="analyst",
                errors=[ContractViolation("analyst", "__call__", None, str(exc))],
            ))
            return self._failure_result(validations, provenance, f"Analyst execution failed: {exc}")

        # Step 6: Validate Analyst output
        analyst_output_result = AgentValidator.validate_analyst_output(analyst_raw)
        validations.append(analyst_output_result)
        if not analyst_output_result.is_valid:
            if self._strict:
                return self._failure_result(validations, provenance, "Analyst output invalid")

        analyst_output: AnalystOutput = analyst_output_result.model
        provenance["analyst_hash"] = analyst_output.provenance_hash

        # Step 7: Validate Strategist input (with provenance)
        strategist_input_result = AgentValidator.validate_strategist_input(
            analyst_output, scout_output
        )
        validations.append(strategist_input_result)

        # Step 8: Run Strategist
        try:
            strategist_raw = self._strategist_fn(
                strategist_input_result.model or analyst_output
            )
        except Exception as exc:
            validations.append(ValidationResult(
                status=ValidationStatus.INVALID, agent="strategist",
                errors=[ContractViolation("strategist", "__call__", None, str(exc))],
            ))
            return self._failure_result(validations, provenance, f"Strategist execution failed: {exc}")

        # Step 9: Validate Strategist output
        strategist_output_result = AgentValidator.validate_strategist_output(strategist_raw)
        validations.append(strategist_output_result)
        if not strategist_output_result.is_valid:
            if self._strict:
                return self._failure_result(validations, provenance, "Strategist output invalid")

        strategist_output: StrategistOutput = strategist_output_result.model
        provenance["strategist_hash"] = strategist_output.provenance_hash

        return {
            "scout_output": scout_output,
            "analyst_output": analyst_output,
            "strategist_output": strategist_output,
            "validations": [v.to_dict() for v in validations],
            "provenance_chain": provenance,
            "success": True,
        }

    @staticmethod
    def _failure_result(
        validations: list[ValidationResult],
        provenance: dict[str, str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "scout_output": None,
            "analyst_output": None,
            "strategist_output": None,
            "validations": [v.to_dict() for v in validations],
            "provenance_chain": provenance,
            "success": False,
            "failure_reason": reason,
        }
    

    