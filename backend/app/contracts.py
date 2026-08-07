from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    occurrence_kind: Literal["BOOT_HEALTH_CHECK", "LINEAGE_SNAPSHOT_VIEW"]
    outcome_code: Literal[
        "CORE_READY",
        "CORE_READY_GEMINI_DEGRADED",
        "LINEAGE_SNAPSHOT_BOUND",
    ]
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


class IngestionRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    dataset_key: Literal["semi-synthetic-hero"]
    mapping_manifest_id: Literal["semi-synthetic-hero.mapping.v1"]


ValueState = Literal["present", "missing", "not_applicable", "invalid", "unresolved"]


class FieldValueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ValueState
    value: Any | None = None
    source_value: Any | None = None


TemporalKind = Literal["date", "local_datetime", "instant"]
TimezoneStatus = Literal["known", "assumed", "unknown", "not_applicable"]


class TemporalValueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TemporalKind
    source_value: str
    normalized_value: str
    precision: str
    timezone_status: TimezoneStatus
    source_timezone: FieldValueResponse


class TemporalFieldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ValueState
    value: TemporalValueResponse | None = None


class SourceObjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_name: str
    sha256: str
    size: int = Field(ge=0)
    protected_locator: str


class GeneratorMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generator_version: str
    seed: int
    scenario_id: str
    parameter_set_hash: str
    calibration_evidence_refs: list[str]
    ground_truth_artifact_hash: str


class MappingEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical: str
    source: str
    rule_id: str
    rule_version: str


class IdentityMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    rule_id: str
    rule_version: str


class FieldMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    canonical_type: str
    rule_id: str
    rule_version: str


class EventMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_path: str
    source_event_key: str
    kind: str
    milestone_kind: str
    occurred_at: str
    known_at: str
    available_at: str
    promised_for: str
    reason: str
    revises_promise_source_event_key: str


class MappingManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_manifest_id: str
    schema_version: str
    dataset_key: str
    source_kind: str
    intended_role: str
    source_schema_id: str
    source_schema_version: str
    canonical_schema_version: str
    adapter_id: str
    adapter_version: str
    mapping_assumptions: list[str]
    license_and_attribution_ref: str
    data_classification: str
    raw_redistribution_policy: str
    derived_redistribution_policy: str
    generator_metadata: GeneratorMetadataResponse
    identity_mappings: dict[str, IdentityMappingResponse]
    field_mappings: dict[str, FieldMappingResponse]
    event_mappings: EventMappingResponse
    entries: list[MappingEntryResponse]


class IngestionRunRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_run_id: str
    idempotency_key: str
    adapter_id: str
    adapter_version: str
    source_schema_id: str
    source_schema_version: str
    canonical_schema_version: str
    source_objects: list[SourceObjectResponse]
    mapping_assumptions: list[str]
    started_at: datetime
    completed_at: FieldValueResponse
    status: Literal["SUCCEEDED"]
    published_dataset_version_id: FieldValueResponse
    validation_summary: FieldValueResponse
    validation_finding_ids: FieldValueResponse


class RecordCountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_lines: int = Field(ge=0)
    order_line_events: int = Field(ge=0)
    source_observations: int = Field(ge=0)
    validation_findings: int = Field(ge=0)
    quarantine_records: int = Field(ge=0)


class ValidationSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    by_code: dict[str, int]
    by_disposition: dict[str, int]


class RedistributionPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str
    explanation: str


class ProvenanceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: dict[str, int]
    derivation: dict[str, int]
    calibration: dict[str, int]


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version_id: str
    predecessor_dataset_version_id: FieldValueResponse
    source_kind: str
    intended_role: str
    canonical_schema_version: str
    adapter_id: str
    adapter_version: str
    source_schema_id: str
    source_schema_version: str
    mapping_manifest_id: str
    input_hashes: list[str]
    semantic_payload_hashes: list[str]
    output_hashes: list[str]
    first_published_at: datetime
    first_published_by_run_id: str
    record_counts: RecordCountsResponse
    mapping_assumptions: list[str]
    validation_summary: ValidationSummaryResponse
    license_and_attribution_ref: FieldValueResponse
    data_classification: str
    raw_redistribution_policy: RedistributionPolicyResponse
    derived_redistribution_policy: RedistributionPolicyResponse
    provenance_summary: ProvenanceSummaryResponse
    generator_metadata: FieldValueResponse
    mapping_manifest: MappingManifestResponse


class OrderLineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str
    order_line_id: str
    order_group_id: str
    supplier_id: str
    fields: dict[str, FieldValueResponse]


EventKind = Literal[
    "committed",
    "promise_recorded",
    "promise_revised",
    "milestone_reached",
    "cancelled",
]


class EventClocksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: TemporalFieldResponse
    known_at: TemporalFieldResponse
    available_at: TemporalFieldResponse


class OrderLineEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str
    event_id: str
    order_line_id: str
    kind: EventKind
    milestone_kind: FieldValueResponse
    clocks: EventClocksResponse
    ingested_at: datetime
    promised_for: TemporalFieldResponse
    reason: FieldValueResponse
    revises_promise_event_id: FieldValueResponse
    supersedes_event_id: FieldValueResponse


class SourceObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str
    source_observation_id: str
    ingestion_run_id: str
    target_record_type: Literal["OrderLine", "OrderLineEvent"]
    target_record_id: str
    target_field_path: str
    source_object_hash: str
    source_locator_token: str
    source_field_path: FieldValueResponse
    known_at: TemporalFieldResponse
    available_at: TemporalFieldResponse
    origin: Literal["simulated"]
    derivation: Literal["direct", "normalized"]
    calibration: Literal["none"]
    transformation_rule_id: FieldValueResponse
    transformation_rule_version: FieldValueResponse
    evidence_refs: list[str]
    source_value_fingerprint: FieldValueResponse


FindingSeverity = Literal["info", "warning", "error"]
FindingDisposition = Literal["advisory", "invalidate_field", "quarantine_record", "reject_run"]
FindingScope = Literal["field", "record", "run"]


class ValidationFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str
    validation_finding_id: str
    ingestion_run_id: str
    code: str
    code_registry_version: str
    severity: FindingSeverity
    disposition: FindingDisposition
    scope: FindingScope
    affected_refs: list[str]
    affected_count: int = Field(ge=0)
    rule_id: str
    rule_version: str
    message: str
    remediation: str


class LineageAuditBindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    dataset_version_id: str
    occurrence_id: str
    event_seq: int = Field(gt=0)
    content_hash: str
    created_at: datetime


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    ingestion_run_id: str
    dataset_version_id: str
    status: Literal["SUCCEEDED"]


class DatasetVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DatasetVersionResponse]


class LineageSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_run: IngestionRunRecordResponse
    dataset_version: DatasetVersionResponse
    mapping_manifest: MappingManifestResponse
    order_lines: list[OrderLineResponse]
    order_line_events: list[OrderLineEventResponse]
    source_observations: list[SourceObservationResponse]
    validation_findings: list[ValidationFindingResponse]
    audit_binding: LineageAuditBindingResponse


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
