"""
Pipeline Result - Complete trace of a recommendation pipeline run.

Use this to debug failed recommendations end-to-end.
All three agent outputs in one object, plus metadata.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from .analyst import AnalystOutput
from .scout import ScoutOutput
from .strategist import StrategistOutput


class PipelineResult(BaseModel):
    """Complete trace of a recommendation pipeline run."""

    product_id: UUID
    scout: ScoutOutput
    analyst: AnalystOutput
    strategist: StrategistOutput
    pipeline_started_at: datetime
    pipeline_completed_at: datetime
    total_time_ms: int
    success: bool = True
    error: str | None = None

    def store_evidence(self) -> dict:
        """
        Return the three evidence dicts for record_outcome().

        Usage:
            result = PipelineResult(...)
            evidence = result.store_evidence()
            await outcome_service.record_outcome(
                ...,
                scout_evidence=evidence["scout"],
                analyst_evidence=evidence["analyst"],
                strategist_evidence=evidence["strategist"],
            )
        """
        return {
            "scout": self.scout.to_evidence(),
            "analyst": self.analyst.to_evidence(),
            "strategist": self.strategist.to_evidence(),
        }
