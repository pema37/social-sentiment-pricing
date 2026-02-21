"""
Pipeline Tracing
=================
Phase 4 — Reasoning Protocols

Structured tracing for the Scout → Analyst → Strategist pipeline.
Each agent invocation is captured as a TraceSpan with:
  - Input/output hashes (not full data — privacy-safe)
  - Validation results
  - Timing
  - Conflict resolutions applied
  - Error details if failed

Designed for:
  - LangSmith / Arize Phoenix integration (export to_langsmith_run())
  - Local structured logging (export to_dict())
  - Dashboard display (export to_summary())

Location: backend/schemas/agent_contracts/tracing.py
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """
    A single span in the pipeline trace.

    Represents one agent invocation (Scout, Analyst, or Strategist).
    """
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Provenance
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None

    # Validation
    input_valid: bool = True
    output_valid: bool = True
    validation_errors: list[dict] = field(default_factory=list)

    # Conflicts
    conflicts_detected: list[str] = field(default_factory=list)
    conflicts_resolved: list[str] = field(default_factory=list)

    # Status
    success: bool = True
    error: Optional[str] = None
    error_type: Optional[str] = None

    # Custom metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "agent": self.agent,
            "duration_ms": round(self.duration_ms, 2),
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "input_valid": self.input_valid,
            "output_valid": self.output_valid,
            "validation_error_count": len(self.validation_errors),
            "conflicts_detected": self.conflicts_detected,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class PipelineTrace:
    """
    Full trace for a Scout → Analyst → Strategist pipeline run.

    Captures the complete evidence chain for debugging any recommendation.
    """
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: Optional[str] = None
    merchant_id: Optional[str] = None
    product_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_duration_ms: float = 0.0

    spans: list[TraceSpan] = field(default_factory=list)

    # Pipeline-level
    success: bool = True
    failure_reason: Optional[str] = None
    pipeline_version: str = "ie-v1.0"

    # Provenance chain
    scout_hash: Optional[str] = None
    analyst_hash: Optional[str] = None
    strategist_hash: Optional[str] = None

    def add_span(self, span: TraceSpan) -> None:
        self.spans.append(span)
        if not span.success:
            self.success = False

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "recommendation_id": self.recommendation_id,
            "merchant_id": self.merchant_id,
            "product_id": self.product_id,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "success": self.success,
            "failure_reason": self.failure_reason,
            "pipeline_version": self.pipeline_version,
            "provenance": {
                "scout": self.scout_hash,
                "analyst": self.analyst_hash,
                "strategist": self.strategist_hash,
            },
            "spans": [s.to_dict() for s in self.spans],
            "span_count": len(self.spans),
        }

    def to_summary(self) -> dict:
        """Compact summary for dashboard display."""
        return {
            "trace_id": self.trace_id,
            "success": self.success,
            "duration_ms": round(self.total_duration_ms, 2),
            "agents_called": [s.agent for s in self.spans],
            "agents_failed": [s.agent for s in self.spans if not s.success],
            "total_conflicts": sum(len(s.conflicts_detected) for s in self.spans),
            "total_validation_errors": sum(len(s.validation_errors) for s in self.spans),
        }

    def to_langsmith_run(self) -> dict:
        """
        Export as a LangSmith-compatible run dict.

        Can be sent to LangSmith API for external tracing dashboard.
        Ref: https://docs.smith.langchain.com/
        """
        return {
            "id": self.trace_id,
            "name": f"actualprice-pipeline-{self.pipeline_version}",
            "run_type": "chain",
            "start_time": self.started_at.isoformat() if self.started_at else None,
            "end_time": self.ended_at.isoformat() if self.ended_at else None,
            "inputs": {
                "merchant_id": self.merchant_id,
                "product_id": self.product_id,
            },
            "outputs": {
                "recommendation_id": self.recommendation_id,
                "success": self.success,
            },
            "error": self.failure_reason,
            "tags": [self.pipeline_version],
            "extra": {
                "provenance": {
                    "scout": self.scout_hash,
                    "analyst": self.analyst_hash,
                    "strategist": self.strategist_hash,
                },
            },
            "child_runs": [
                {
                    "id": span.span_id,
                    "name": f"agent-{span.agent}",
                    "run_type": "tool",
                    "start_time": span.started_at.isoformat() if span.started_at else None,
                    "end_time": span.ended_at.isoformat() if span.ended_at else None,
                    "error": span.error,
                }
                for span in self.spans
            ],
        }


class PipelineTracer:
    """
    Context-manager style tracer for the pipeline.

    Usage:
        tracer = PipelineTracer(merchant_id="m1", product_id="p1")
        with tracer.span("scout") as span:
            result = scout_agent.run(...)
            span.output_hash = result.provenance_hash
        trace = tracer.finalize()
    """

    def __init__(
        self,
        merchant_id: Optional[str] = None,
        product_id: Optional[str] = None,
        recommendation_id: Optional[str] = None,
        pipeline_version: str = "ie-v1.0",
    ):
        self._trace = PipelineTrace(
            recommendation_id=recommendation_id,
            merchant_id=merchant_id,
            product_id=product_id,
            started_at=datetime.now(timezone.utc),
            pipeline_version=pipeline_version,
        )
        self._current_span: Optional[TraceSpan] = None

    def span(self, agent: str) -> _SpanContext:
        """Create a new span context for an agent invocation."""
        return _SpanContext(self, agent)

    def finalize(self) -> PipelineTrace:
        """Close the trace and compute total duration."""
        self._trace.ended_at = datetime.now(timezone.utc)
        if self._trace.started_at:
            delta = (self._trace.ended_at - self._trace.started_at).total_seconds()
            self._trace.total_duration_ms = delta * 1000

        # Log the trace
        summary = self._trace.to_summary()
        if self._trace.success:
            logger.info("[Trace] Pipeline succeeded: %s", summary)
        else:
            logger.warning("[Trace] Pipeline failed: %s", summary)

        return self._trace

    def _add_span(self, span: TraceSpan) -> None:
        self._trace.add_span(span)


class _SpanContext:
    """Context manager for a single agent span."""

    def __init__(self, tracer: PipelineTracer, agent: str):
        self._tracer = tracer
        self.span = TraceSpan(agent=agent)

    def __enter__(self) -> TraceSpan:
        self.span.started_at = datetime.now(timezone.utc)
        self._start_time = time.monotonic()
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.span.ended_at = datetime.now(timezone.utc)
        self.span.duration_ms = (time.monotonic() - self._start_time) * 1000

        if exc_type is not None:
            self.span.success = False
            self.span.error = str(exc_val)
            self.span.error_type = exc_type.__name__

        self._tracer._add_span(self.span)
        return False  # Don't suppress exceptions
    

    