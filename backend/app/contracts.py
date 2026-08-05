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


class DemoWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    status: Literal["ACTIVE"]
    created_at: datetime
    last_seen_at: datetime
    mutation_count: int = Field(ge=0)
    remaining_mutations: int = Field(ge=0)
    terminal_fresh_bundle_count: int = Field(ge=0)
    remaining_terminal_fresh_bundles: int = Field(ge=0)


class AuditOccurrenceViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurrence_id: str
    event_seq: int = Field(gt=0)
    occurrence_kind: Literal["BOOT_HEALTH_CHECK"]
    outcome_code: Literal["CORE_READY", "CORE_READY_GEMINI_DEGRADED"]
    created_at: datetime


class AuditOccurrenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditOccurrenceViewResponse]


class ValidatedReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    bundle_ref: str
    validation_attestation_ref: str
    release_candidate_id: str


class ValidatedReferenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ValidatedReferenceResponse]


class WorkspaceSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    reference_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )


class WorkspaceSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    selection_id: str
    reference_id: str


class WorkspaceSelectionViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: str
    reference_id: str
    selected_at: datetime


class WorkspaceResultViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    operation_id: str
    result_ref: str
    created_at: datetime


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    recovery_action: str
