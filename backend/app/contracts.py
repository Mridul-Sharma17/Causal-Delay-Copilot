from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


HealthState = Literal["live", "ready", "degraded", "unavailable"]
HealthCode = Literal[
    "CORE_LIVE",
    "CORE_READY",
    "CORE_READY_GEMINI_DEGRADED",
    "CORE_STORE_UNAVAILABLE",
]
DegradedCapability = Literal["GEMINI_DRAFTING"]


class HealthProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: HealthState
    code: HealthCode


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: Literal["causal-delay-copilot"]
    state: Literal["ready", "degraded", "unavailable"]
    code: HealthCode
    liveness: HealthProbe
    readiness: HealthProbe
    degraded_capabilities: list[DegradedCapability]
    observed_at: datetime


class AuditOccurrenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    occurrence_kind: Literal["BOOT_HEALTH_CHECK"]
    outcome_code: Literal["CORE_READY", "CORE_READY_GEMINI_DEGRADED"]


class AuditOccurrenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    occurrence_id: str
    event_seq: int = Field(gt=0)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    recovery_action: str
