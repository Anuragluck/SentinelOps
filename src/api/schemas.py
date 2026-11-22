from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"
    UNKNOWN = "UNKNOWN"


class AlertInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: str = Field(default_factory=lambda: str(uuid4()), max_length=128)
    service: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=4000)
    severity: Severity = Severity.UNKNOWN
    environment: str = Field(default="production", max_length=64)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = Field(default_factory=dict, max_length=50)

    @field_validator("service", "summary", "environment")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Citation(BaseModel):
    source_type: str
    evidence_id: str
    excerpt: str = Field(max_length=1000)
    uri: str | None = None


class ProposedCommand(BaseModel):
    command: str
    rationale: str
    decision: str
    reasons: list[str] = Field(default_factory=list)


class IncidentReport(BaseModel):
    incident_id: str
    service: str
    severity: Severity
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation]
    proposed_commands: list[ProposedCommand]
    rollback_steps: list[str]
    status: str = "investigated"
    limitations: list[str] = Field(default_factory=list)


class TraceSummary(BaseModel):
    trace_id: str
    duration_ms: float
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0


class TriageResponse(BaseModel):
    report: IncidentReport
    trace: TraceSummary
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
