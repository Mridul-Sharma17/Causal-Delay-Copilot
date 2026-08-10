from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    occurrence_kind: Literal[
        "BOOT_HEALTH_CHECK",
        "ANALYSIS_RUN_DELIVERY",
        "REFRESH_INVESTIGATION_SNAPSHOT",
        "DECISION_SUPPORT_CURRENTNESS_OPERATION",
        "DECISION_SUPPORT_CURRENTNESS_CHECK",
        "DECISION_SUPPORT_CURRENT_ADVICE_RENDER_REQUEST",
        "DECISION_SUPPORT_CURRENT_ADVICE_RENDER",
        "DECISION_SUPPORT_CURRENTNESS_INVALIDATION",
        "DECISION_SUPPORT_CURRENTNESS_CONSUMING_RESULT",
        "DECISION_SUPPORT_MONITORING_REVIEW_REQUEST",
        "GOVERNANCE_TRADEOFF_SELECTION",
        "DECISION_SUPPORT_TRADEOFF_SELECTION_VALIDATION",
        "DECISION_SUPPORT_TRADEOFF_SELECTION_CLAIM",
    ]
    outcome_code: Literal[
        "CORE_READY",
        "CORE_READY_GEMINI_DEGRADED",
        "FRESH_ANALYSIS_REQUESTED",
        "FRESH_REPRODUCTION_REQUESTED",
        "REFRESH_ANALYSIS_REQUESTED",
        "REFRESH_SNAPSHOT_CREATED",
        "CURRENT_ADVICE",
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "CURRENTNESS_OPERATION",
        "CURRENT_ADVICE_RENDER",
        "ADVICE_CURRENTNESS_INVALIDATION",
        "TRADEOFF_SELECTION_ACCEPTANCE",
        "MANAGER_AUTHORIZATION",
        "MONITORING_TRIGGER_MATCH",
        "REQUEST_MANAGER_REVIEW",
        "TRADEOFF_SELECTION_RECORDED",
        "TRADEOFF_SELECTION_SCHEMA_INVALID",
        "TRADEOFF_SELECTION_SCHEMA_UNSUPPORTED",
        "TRADEOFF_SELECTION_SERIES_NOT_FOUND",
        "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH",
        "TRADEOFF_SELECTION_STALE",
        "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF",
        "TRADEOFF_SELECTION_INVALID_CANDIDATE",
        "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT",
        "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED",
        "TRADEOFF_SELECTION_ACCEPTED",
    ]


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
    occurrence_kind: Literal[
        "BOOT_HEALTH_CHECK",
        "LINEAGE_SNAPSHOT_VIEW",
        "REACTIVE_INGRESS",
        "PROACTIVE_INGRESS",
        "DECISION_BRIEF_SNAPSHOT",
        "DECISION_SUPPORT_EVALUATION",
        "DECISION_SUPPORT_INVALIDATION",
        "DECISION_SUPPORT_CURRENTNESS_OPERATION",
        "DECISION_SUPPORT_CURRENTNESS_CHECK",
        "DECISION_SUPPORT_CURRENT_ADVICE_RENDER_REQUEST",
        "DECISION_SUPPORT_CURRENT_ADVICE_RENDER",
        "DECISION_SUPPORT_CURRENTNESS_INVALIDATION",
        "DECISION_SUPPORT_CURRENTNESS_CONSUMING_RESULT",
        "DECISION_SUPPORT_MONITORING_REVIEW_REQUEST",
        "DECISION_SUPPORT_CURRENTNESS_SOURCE_OCCURRENCE",
        "DECISION_SUPPORT_CURRENTNESS_AUTHORITY",
        "GOVERNANCE_TRADEOFF_SELECTION",
        "DECISION_SUPPORT_TRADEOFF_SELECTION_VALIDATION",
        "DECISION_SUPPORT_TRADEOFF_SELECTION_CLAIM",
        "ANALYSIS_RUN_DELIVERY",
        "REFRESH_INVESTIGATION_SNAPSHOT",
    ]
    outcome_code: Literal[
        "CORE_READY",
        "CORE_READY_GEMINI_DEGRADED",
        "LINEAGE_SNAPSHOT_BOUND",
        "RISK_SIGNAL_ACCEPTED",
        "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
        "RISK_SIGNAL_INTEGRITY_FAILED",
        "RISK_SIGNAL_REVISION_CONFLICT",
        "RISK_SIGNAL_CLOCK_UNUSABLE",
        "REFRESH_CUTOFF_NOT_LATER",
        "RISK_SIGNAL_SUBJECT_UNRESOLVED",
        "RISK_SIGNAL_SUBJECT_AMBIGUOUS",
        "RISK_SIGNAL_SUBJECT_NOT_OPEN",
        "COMMITMENT_CUTOFF_UNUSABLE",
        "RISK_SIGNAL_TARGET_MISMATCH",
        "RISK_SIGNAL_SCORE_UNUSABLE",
        "RISK_SIGNAL_CONTEXT_CONFLICT",
        "RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
        "RISK_SIGNAL_MODE_MISMATCH",
        "PROACTIVE_ACCEPTED",
        "PROACTIVE_SCHEMA_UNSUPPORTED",
        "PROACTIVE_INTEGRITY_FAILED",
        "PROACTIVE_REVISION_CONFLICT",
        "PROACTIVE_DATASET_UNAVAILABLE",
        "PROACTIVE_SUBJECT_INPUT_UNUSABLE",
        "CAUSAL_QUESTION_VERSION_UNAVAILABLE",
        "ENGINE_CONFIGURATION_UNAVAILABLE",
        "SLIPPAGE_DURATION_BASIS_MIXED",
        "FROZEN_PROMISE_UNAVAILABLE",
        "FROZEN_PROMISE_CONFLICT",
        "FROZEN_PROMISE_TEMPORALLY_INVALID",
        "TARGET_MILESTONE_UNSUPPORTED",
        "FOLLOW_UP_IMMATURE",
        "FOLLOW_UP_UNRESOLVABLE",
        "OUTCOME_UNOBSERVED",
        "OUTCOME_TEMPORALLY_INVALID",
        "CANCELLED_BEFORE_MILESTONE",
        "DECISION_BRIEF_PUBLISHED",
        "FAILED",
        "NOT_PERMITTED",
        "NO_ELIGIBLE_OPTION",
        "TRADEOFF_REQUIRES_MANAGER_CHOICE",
        "RECOMMENDATION_AVAILABLE",
        "PERMISSION_INVALIDATION",
        "EVIDENCE_INTEGRITY_INVALIDATION",
        "ADVICE_CURRENTNESS_INVALIDATION",
        "FRESH_ANALYSIS_REQUESTED",
        "FRESH_REPRODUCTION_REQUESTED",
        "REFRESH_ANALYSIS_REQUESTED",
        "REFRESH_SNAPSHOT_CREATED",
        "CURRENT_ADVICE",
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "CURRENTNESS_OPERATION",
        "CURRENT_ADVICE_RENDER",
        "TRADEOFF_SELECTION_ACCEPTANCE",
        "MANAGER_AUTHORIZATION",
        "MONITORING_TRIGGER_MATCH",
        "REQUEST_MANAGER_REVIEW",
        "CURRENTNESS_SOURCE_REGISTERED",
        "CURRENTNESS_AUTHORITY_UPDATED",
        "TRADEOFF_SELECTION_RECORDED",
        "TRADEOFF_SELECTION_SCHEMA_INVALID",
        "TRADEOFF_SELECTION_SCHEMA_UNSUPPORTED",
        "TRADEOFF_SELECTION_SERIES_NOT_FOUND",
        "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH",
        "TRADEOFF_SELECTION_STALE",
        "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF",
        "TRADEOFF_SELECTION_INVALID_CANDIDATE",
        "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT",
        "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED",
        "TRADEOFF_SELECTION_ACCEPTED",
    ]
    created_at: datetime
    source_role_ceiling: SourceRoleCeilingResponse | None = None


class AuditOccurrenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditOccurrenceViewResponse]


class DecisionBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    reference_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )


class DecisionBriefSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["decision-brief-snapshot.v2"]
    snapshot_id: str
    investigation_request_id: str
    reference_id: str
    content_hash: str
    occurrence_id: str
    event_seq: int = Field(gt=0)
    created_at: datetime
    subject_applicability: dict[str, Any]
    subject_verdict: dict[str, Any] | None
    rendered_subject_verdict: dict[str, str] | None
    action_lane: dict[str, Any]
    investigation_request: dict[str, Any]
    ingress_attempt: dict[str, Any]
    lineage: dict[str, Any]
    reference: dict[str, Any]
    referenced_records: dict[str, Any]
    decision_support: dict[str, Any] | None = None
    decision_support_registry: dict[str, Any] | None = None


class DecisionBriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    snapshot: DecisionBriefSnapshotResponse


class DecisionSupportReferenceAndHash(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str = Field(min_length=1, max_length=512)
    content_hash: str = Field(min_length=1, max_length=128)


class DecisionSupportInvalidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    expected_head_occurrence_id: str = Field(min_length=1, max_length=128)
    expected_head_digest: str = Field(min_length=1, max_length=128)
    expected_head_result_hash: str = Field(min_length=1, max_length=128)
    invalidation_kind: Literal[
        "PERMISSION_INVALIDATION",
        "EVIDENCE_INTEGRITY_INVALIDATION",
        "ADVICE_CURRENTNESS_INVALIDATION",
    ]
    invalidated_artifact_ref_and_hash: DecisionSupportReferenceAndHash
    authoritative_invalidation_ref_and_hash: DecisionSupportReferenceAndHash
    reason_code: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )


class DecisionSupportEvaluationSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["decision-support-evaluation-read-model.v1"]
    evaluation_series_id: str
    identity_binding: dict[str, Any]
    head: dict[str, Any]
    history: list[dict[str, Any]]


class DecisionSupportInvalidationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    invalidation: dict[str, Any]
    head: dict[str, Any]


class DecisionSupportCurrentnessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: dict[str, Any]


class DecisionSupportCurrentAdviceRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_identifier: Literal["current-advice-render-request"]
    schema_version: Literal["1"]
    render_mode: Literal["CURRENT_ADVICE"]
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    advice_chain_kind: str = Field(min_length=1, max_length=128)
    recommendation_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    accepted_selection_claim_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    advice_chain_published_at: str | dict[str, Any]
    requested_at: str | dict[str, Any]
    available_at: str | dict[str, Any]
    render_request_occurrence_id: str | None = None
    current_advice_render_request_key: str | None = None
    content_hash: str | None = None


class DecisionSupportCurrentnessResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    operation: dict[str, Any]
    currentness: dict[str, Any]
    terminal_claim: dict[str, Any]
    render: dict[str, Any] | None = None
    consuming_result: dict[str, Any] | None = None
    head: dict[str, Any]


class DraftContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_advice: DecisionSupportCurrentAdviceRenderRequest


class DraftContextPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["deterministic-draft-preview"]
    schema_version: Literal["1"]
    state: Literal["UNSENT_PREVIEW"]
    currentness: dict[str, Any]
    draft_context: dict[str, Any]
    artifact: dict[str, Any]
    checker: dict[str, Any]
    drafting: dict[str, Any] = Field(default_factory=dict)


class DecisionSupportMonitoringObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict[str, Any]


class DecisionSupportMonitoringMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict[str, Any]
    evaluation_series_id: str | None = None
    accepted_selection_claim: dict[str, Any] | None = None


class DecisionSupportMonitoringObservationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    observation: dict[str, Any]


class TradeoffSelectionCandidateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    option_code: str = Field(min_length=1, max_length=128)
    option_version: str = Field(min_length=1, max_length=64)


class TradeoffSelectionCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_reference: TradeoffSelectionCandidateReference
    option_code: str = Field(min_length=1, max_length=128)
    option_version: str = Field(min_length=1, max_length=64)
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_identifier: Literal["tradeoff-selection"]
    schema_version: Literal["1"]
    selection_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    selected_candidate_ref: str = Field(min_length=1, max_length=512)
    selected_candidate: TradeoffSelectionCandidate
    manager_actor_ref: str = Field(min_length=1, max_length=256)
    selected_at: str | dict[str, Any]
    available_at: str | dict[str, Any]
    governance_tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionDeliveryAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_identifier: Literal["tradeoff-selection-delivery-attempt"]
    schema_version: Literal["1"]
    delivery_attempt_occurrence_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
    )
    occurrence_id: str | None = Field(default=None, min_length=1, max_length=256)
    tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    selected_candidate_ref: str = Field(min_length=1, max_length=512)
    selected_candidate: TradeoffSelectionCandidate
    selection_available_at: str | dict[str, Any]
    delivered_at: str | dict[str, Any]
    available_at: str | dict[str, Any]
    content_hash: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_one_occurrence_id(self) -> "TradeoffSelectionDeliveryAttempt":
        if (self.delivery_attempt_occurrence_id is None) == (self.occurrence_id is None):
            raise ValueError(
                "exactly one delivery attempt occurrence identity is required"
            )
        return self


class TradeoffSelectionPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: TradeoffSelectionRecord


class TradeoffSelectionPublishResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    selection: TradeoffSelectionRecord


class TradeoffSelectionValidationResultResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["tradeoff-selection-validation-result"]
    schema_version: Literal["1"]
    validation_result_occurrence_id: str = Field(min_length=1, max_length=256)
    validation_result_key: str = Field(min_length=1, max_length=128)
    validation_code: Literal[
        "TRADEOFF_SELECTION_SERIES_NOT_FOUND",
        "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH",
    ]
    delivery_attempt_ref_and_hash: DecisionSupportReferenceAndHash
    evaluation_series_id: str | None = None
    governance_tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash | None = None
    action_recommendation: None = None
    selection_not_authorization: Literal[True]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionOperationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["advice-currentness-operation"]
    schema_version: Literal["1"]
    operation_occurrence_id: str = Field(min_length=1, max_length=256)
    currentness_operation_key: str = Field(min_length=1, max_length=128)
    operation_kind: Literal["TRADEOFF_SELECTION_ACCEPTANCE"]
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    recommendation_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    accepted_selection_claim_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    operation_payload_ref_and_hash: DecisionSupportReferenceAndHash
    currentness_checked_at: str | dict[str, Any]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionCurrentnessResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["advice-currentness-check"]
    schema_version: Literal["1"]
    currentness_check_occurrence_id: str = Field(min_length=1, max_length=256)
    currentness_check_key: str = Field(min_length=1, max_length=128)
    currentness_operation_key: str = Field(min_length=1, max_length=128)
    currentness_operation_ref_and_hash: DecisionSupportReferenceAndHash
    currentness_outcome: Literal[
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "ADVICE_CURRENTNESS_INVALIDATION",
    ]
    currentness_evidence_digest: str = Field(min_length=1, max_length=128)
    currentness_checked_at: str | dict[str, Any]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionTerminalClaimResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    currentness_operation_key: str = Field(min_length=1, max_length=128)
    currentness_operation_ref_and_hash: DecisionSupportReferenceAndHash
    currentness_check_key: str = Field(min_length=1, max_length=128)
    terminal_currentness_ref_and_hash: DecisionSupportReferenceAndHash
    currentness_outcome: Literal[
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "ADVICE_CURRENTNESS_INVALIDATION",
    ]
    consuming_result_kind: Literal["tradeoff-selection-result", "NOT_APPLICABLE"]
    consuming_result_ref_and_hash: DecisionSupportReferenceAndHash | None = None
    refusal_result_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    installed_invalidation_head_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    terminal_head: dict[str, Any]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionClaimResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["tradeoff-selection-claim"]
    schema_version: Literal["1"]
    selection_claim_occurrence_id: str = Field(min_length=1, max_length=256)
    selection_claim_key: str = Field(min_length=1, max_length=128)
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    governance_tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    selected_candidate_ref: str = Field(min_length=1, max_length=512)
    selected_candidate_content_hash: str = Field(min_length=1, max_length=128)
    action_recommendation_key: str = Field(min_length=1, max_length=128)
    action_recommendation_ref_and_hash: DecisionSupportReferenceAndHash
    creation_currentness_operation_ref_and_hash: DecisionSupportReferenceAndHash
    creation_currentness_check_ref_and_hash: DecisionSupportReferenceAndHash
    published_at: str | dict[str, Any]
    selection_is_not_authorization: Literal[True]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionResultResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["tradeoff-selection-result"]
    schema_version: Literal["1"]
    consuming_result_occurrence_id: str = Field(min_length=1, max_length=256)
    consuming_result_key: str = Field(min_length=1, max_length=128)
    currentness_operation_key: str = Field(min_length=1, max_length=128)
    operation_kind: Literal["TRADEOFF_SELECTION_ACCEPTANCE"]
    currentness_operation_ref_and_hash: DecisionSupportReferenceAndHash
    currentness_check_ref_and_hash: DecisionSupportReferenceAndHash
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_digest: str = Field(min_length=1, max_length=128)
    terminal_result_ref_and_hash: DecisionSupportReferenceAndHash
    tradeoff_selection_delivery_attempt_ref_and_hash: DecisionSupportReferenceAndHash
    tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    governance_tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    selected_candidate_ref: str = Field(min_length=1, max_length=512)
    selected_candidate_content_hash: str = Field(min_length=1, max_length=128)
    selection_result: Literal[
        "TRADEOFF_SELECTION_STALE",
        "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF",
        "TRADEOFF_SELECTION_INVALID_CANDIDATE",
        "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT",
        "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED",
        "TRADEOFF_SELECTION_ACCEPTED",
    ]
    selection_claim_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    action_recommendation_ref_and_hash_or_null: DecisionSupportReferenceAndHash | None = None
    currentness_outcome: Literal[
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "ADVICE_CURRENTNESS_INVALIDATION",
    ]
    current_as_of: str | dict[str, Any]
    selection_not_authorization: Literal[True]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionActionRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_identifier: Literal["action-recommendation"]
    schema_version: Literal["1"]
    action_recommendation_key: str = Field(min_length=1, max_length=128)
    occurrence_id: str = Field(min_length=1, max_length=256)
    evaluation_series_id: str = Field(min_length=1, max_length=256)
    evaluation_occurrence_id: str = Field(min_length=1, max_length=256)
    decision_support_input_digest: str = Field(min_length=1, max_length=128)
    selected_option_code: str = Field(min_length=1, max_length=128)
    selected_option_version: str = Field(min_length=1, max_length=64)
    selected_candidate_ref: str = Field(min_length=1, max_length=512)
    selection_basis: Literal["MANAGER_TRADEOFF_SELECTION"]
    governance_tradeoff_selection_ref_and_hash: DecisionSupportReferenceAndHash
    selection_is_not_authorization: Literal[True]
    content_hash: str = Field(min_length=1, max_length=128)


class TradeoffSelectionHeadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    evaluation_series_id: str = Field(min_length=1, max_length=256)
    head_kind: Literal[
        "EVALUATION",
        "PERMISSION_INVALIDATION",
        "EVIDENCE_INTEGRITY_INVALIDATION",
        "ADVICE_CURRENTNESS_INVALIDATION",
    ]
    head_occurrence_id: str = Field(min_length=1, max_length=256)
    head_digest: str = Field(min_length=1, max_length=128)
    head_result_hash: str = Field(min_length=1, max_length=128)
    head_record_ref_and_hash: DecisionSupportReferenceAndHash


class TradeoffSelectionAcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_attempt: TradeoffSelectionDeliveryAttempt
    selection: TradeoffSelectionRecord | None = None


class TradeoffSelectionAcceptanceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    selection_result: TradeoffSelectionResultResponse | None = None
    validation_result: TradeoffSelectionValidationResultResponse | None = None
    delivery_attempt: TradeoffSelectionDeliveryAttempt | None = None
    operation: TradeoffSelectionOperationResponse | None = None
    currentness: TradeoffSelectionCurrentnessResponse | None = None
    terminal_claim: TradeoffSelectionTerminalClaimResponse | None = None
    selection_claim: TradeoffSelectionClaimResponse | None = None
    action_recommendation: TradeoffSelectionActionRecommendationResponse | None = None
    head: TradeoffSelectionHeadResponse | None = None

    @model_validator(mode="after")
    def require_one_terminal_result(self) -> "TradeoffSelectionAcceptanceResponse":
        if (self.selection_result is None) == (self.validation_result is None):
            raise ValueError(
                "exactly one trade-off selection terminal result is required"
            )
        return self


class ReplayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay.v1"]
    status: Literal["REPLAYED", "REPLAY_UNAVAILABLE"]
    investigation_request_id: str
    requested_event_seq: int = Field(gt=0)
    last_verified_event_seq: int = Field(ge=0)
    snapshot: DecisionBriefSnapshotResponse | None
    unresolved_references: list[str]
    recovery_action: str


class ValidatedReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    bundle_ref: str
    validation_attestation_ref: str
    release_candidate_id: str


class ValidatedReferenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ValidatedReferenceResponse]


class ValidatedReferenceDeliveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["analysis-run-read-model.v1"]
    delivery_mode: Literal["existing_run_reuse"]
    delivery_badge: Literal["Validated reference"]
    verification_state: Literal["reference_validated"]
    reference_slot_id: str
    reference_id: str
    analysis_run_id: str
    bundle_manifest_hash: str
    bundle_ref: str
    validation_attestation_id: str
    validation_attestation_ref: str
    release_candidate_id: str
    intended_role: str
    engine_result_status: Literal["estimated", "abstained"]
    scientific_request_digest: str
    dataset_version_id: str
    runtime_fingerprint_digest: str
    validation_policy_version: str
    validated_at: datetime
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_summary: dict[str, Any] = Field(default_factory=dict)
    robustness_grade: dict[str, Any] | None = None
    evidence_verdict: dict[str, Any] | None = None
    rendered_verdict: dict[str, str] | None = None


class IngestionRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    dataset_key: Literal[
        "semi-synthetic-hero",
        "olist-validation",
        "scms-rejection-vignette",
    ]
    mapping_manifest_id: Literal[
        "semi-synthetic-hero.mapping.v1",
        "olist-validation.mapping.v1",
        "scms-rejection-vignette.mapping.v1",
    ]


ValueState = Literal[
    "present",
    "missing",
    "unknown",
    "not_applicable",
    "invalid",
    "unresolved",
    "redacted",
]


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
    source_value: str | None
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
    source_paths: list[str] | None = None
    rule_id: str
    rule_version: str


class FieldMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    canonical_type: str
    fixed_state: str | None = None
    fixed_value: Any | None = None
    fixed_unit: str | None = None
    currency: str | None = None
    missingness_tokens: dict[str, str] | None = None
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
    transport_timing: dict[str, str] | None = None
    rejection_mapping: dict[str, Any] | None = None
    canonical_events: dict[str, dict[str, str]] | None = None
    scheduled_delivery: str | None = None
    delivered_to_client: str | None = None
    po_sent_to_vendor: str | None = None
    delivery_recorded: str | None = None


class AdvisoryContextMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_version: str
    source_namespace: str
    target_field: str
    resolution_kind: str


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
    reviewed_source_fields: list[str] | None = None
    generator_metadata: GeneratorMetadataResponse | FieldValueResponse
    identity_mappings: dict[str, IdentityMappingResponse]
    field_mappings: dict[str, FieldMappingResponse]
    event_mappings: EventMappingResponse
    advisory_context_mappings: dict[str, AdvisoryContextMappingResponse]
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


class SourceRoleCeilingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    permitted_claim_scope: str
    subject_application_role_permitted: bool
    decision_support_evaluation_permitted: bool


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version_id: str
    predecessor_dataset_version_id: FieldValueResponse
    source_kind: str
    intended_role: str
    source_role_ceiling: SourceRoleCeilingResponse
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
    origin: Literal["simulated", "observed"]
    derivation: Literal["direct", "normalized", "derived"]
    calibration: Literal["none", "externally_calibrated"]
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
    source_role_ceiling: SourceRoleCeilingResponse


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


OperationState = Literal[
    "QUEUED",
    "RUNNING",
    "CANCELLING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
    "INTERRUPTED",
    "REJECTED",
]


OperationKind = Literal[
    "FRESH_ANALYSIS",
    "FRESH_REPRODUCTION",
    "BOUNDED_WORK",
]


class OperationAdmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    operation_kind: OperationKind
    memory_required_bytes: int = Field(default=256 * 1024 * 1024, ge=1)
    request: dict[str, Any] = Field(default_factory=dict)


class OperationActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )


class AnalysisRunStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["analysis-run-status.v1"]
    analysis_run_id: str
    occurrence_id: str
    operation_id: str
    status: Literal["PENDING", "RUNNING", "ESTIMATED", "ABSTAINED", "FAILED"]
    lifecycle: Literal["executing", "sealed", "failed", "quarantined"]
    scientific_outcome: Literal["pending", "estimated", "abstained", "failed"]
    verification_state: Literal["pending", "machine_verified", "reference_validated", "invalid"]
    availability_state: Literal["available", "suppressed"]
    delivery_mode: Literal["fresh_execution", "existing_run_reuse"]
    run_relationship: Literal["fresh", "reproduction", "refresh"] = "fresh"
    reproduces_run_id: str | None = None
    refresh_of_request_id: str | None = None
    reason_code: str | None
    failure_code: str | None
    recovery_action: str | None
    estimator_executed: bool
    request_schema_version: Literal["causal-engine-suite-request.v2"]
    scientific_request_digest: str
    runtime_fingerprint: dict[str, Any]
    runtime_fingerprint_digest: str
    root_seed: int = Field(ge=0, le=2**64 - 1)
    derived_seed_registry: list[dict[str, Any]]
    estimator_descriptor: dict[str, Any]
    feature_descriptor: dict[str, Any]
    fold_descriptor: dict[str, Any]
    fresh_run_detail: dict[str, Any]
    primary_result: dict[str, Any] | None = None
    bundle_manifest_hash: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_summary: dict[str, Any] | None = None
    robustness_grade: dict[str, Any] | None = None
    evidence_verdict: dict[str, Any] | None = None
    rendered_verdict: dict[str, str] | None = None
    subject_verdict: dict[str, Any] | None = None
    rendered_subject_verdict: dict[str, str] | None = None
    reproduction_comparison: dict[str, Any] | None = None


class OperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["durable-operation.v1"]
    operation_id: str
    operation_kind: OperationKind
    state: OperationState
    status: OperationState
    queue_position: int | None = Field(default=None, ge=1)
    created_at: datetime
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None
    retry_of_operation_id: str | None
    failure_code: str | None
    recovery_action: str | None
    resource_warnings: list[Literal["DISK_SPACE_LOW"]]
    artifact_state: Literal[
        "NOT_STARTED",
        "EXECUTING",
        "PUBLISHED",
        "QUARANTINED",
        "QUARANTINE_UNAVAILABLE",
    ]
    retryable: bool
    timeout_seconds: float = Field(gt=0, le=300)
    thread_cap: int = Field(ge=1)
    memory_required_bytes: int = Field(ge=1)
    memory_available_bytes: int = Field(ge=0)
    disk_free_bytes: int = Field(ge=0)
    analysis_run: AnalysisRunStatusResponse | None = None


class OperationMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    operation: OperationResponse


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    recovery_action: str


class RiskSignalFieldValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ValueState
    value: Any | None = None


class SourceEntityReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(min_length=1, max_length=128)
    key: str | list[str]


class TriggerSourceEnvelopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=64)
    source_system: str = Field(min_length=1, max_length=128)
    source_payload_sha256: str = Field(min_length=1, max_length=80)
    protected_source_locator: str = Field(min_length=1, max_length=256)
    data_classification: Literal[
        "generated",
        "public",
        "restricted",
        "confidential",
    ]


class TemporalValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=128)
    kind: TemporalKind
    precision: str = Field(min_length=1, max_length=32)
    timezone_status: TimezoneStatus
    source_timezone: str | None = None


class RiskSignalAdvisoryContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_supplier_ref: RiskSignalFieldValueRequest | None = None
    source_material_or_equipment_ref: RiskSignalFieldValueRequest | None = None
    source_target_milestone_kind: RiskSignalFieldValueRequest | None = None
    source_original_promise: RiskSignalFieldValueRequest | None = None
    timeline_snapshot_as_of: RiskSignalFieldValueRequest | None = None


class RiskSignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=64)
    trigger_mode: Literal["reactive", "proactive"] = "reactive"
    source: TriggerSourceEnvelopeRequest
    source_signal_id: str = Field(min_length=1, max_length=128)
    source_revision: str = Field(min_length=1, max_length=128)
    scored_dataset_version_ref: str = Field(min_length=1, max_length=256)
    source_order_line_ref: SourceEntityReferenceRequest
    predictor_id: str = Field(min_length=1, max_length=128)
    predictor_version: str = Field(min_length=1, max_length=128)
    feature_contract_version: str = Field(min_length=1, max_length=128)
    target_definition_id: str = Field(min_length=1, max_length=128)
    target_milestone_kind: Literal[
        "supplier_completion",
        "supplier_handoff",
    ]
    score_semantic: str = Field(min_length=1, max_length=128)
    score_value: float
    alert_threshold: float
    flagged: bool
    generated_at: TemporalValueRequest
    known_at: TemporalValueRequest
    predictor_artifact_ref: RiskSignalFieldValueRequest
    predictive_attribution_ref: RiskSignalFieldValueRequest
    prediction_explanation_ref: RiskSignalFieldValueRequest = Field(
        default_factory=lambda: RiskSignalFieldValueRequest(state="missing")
    )
    prediction_calibration_ref: RiskSignalFieldValueRequest = Field(
        default_factory=lambda: RiskSignalFieldValueRequest(state="missing")
    )
    prediction_ranking_ref: RiskSignalFieldValueRequest = Field(
        default_factory=lambda: RiskSignalFieldValueRequest(state="missing")
    )
    prediction_delivery_metadata: RiskSignalFieldValueRequest = Field(
        default_factory=lambda: RiskSignalFieldValueRequest(state="missing")
    )
    advisory_context: RiskSignalFieldValueRequest | None = None


class RefreshInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    trigger_mode: Literal["reactive", "proactive"]
    request: dict[str, Any]
    observation_cutoff: TemporalValueRequest
    root_seed: int = Field(ge=0, le=2**64 - 1)


class ProactiveSubjectFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ValueState
    value: Any | None = None
    known_at: TemporalValueRequest | None = None
    lineage_ref: str | None = Field(default=None, min_length=1, max_length=256)


class ProactiveProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=64)
    trigger_mode: Literal["reactive", "proactive"] = "proactive"
    source: TriggerSourceEnvelopeRequest
    proposal_id: str = Field(min_length=1, max_length=128)
    proposal_revision: str = Field(min_length=1, max_length=128)
    dataset_version_id: str = Field(min_length=1, max_length=256)
    proposed_supplier_ref: ProactiveSubjectFieldRequest
    target_milestone_kind: ProactiveSubjectFieldRequest
    proposed_original_promise: ProactiveSubjectFieldRequest
    adjustment_inputs: dict[str, ProactiveSubjectFieldRequest]
    decision_at: ProactiveSubjectFieldRequest
    requester_ref: str = Field(min_length=1, max_length=256)


class RiskSignalSourcePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trigger-source-envelope.v1"]
    source_system: Literal["bundled-predictive-stub"]
    data_classification: Literal["generated"]


class RiskSignalPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["risk-signal.v1"]
    trigger_mode: Literal["reactive"]
    source: RiskSignalSourcePreviewResponse
    source_signal_id: str
    source_revision: str
    scored_dataset_version_ref: str
    source_order_line_ref: SourceEntityReferenceRequest
    predictor_id: str
    predictor_version: str
    feature_contract_version: str
    target_definition_id: str
    target_milestone_kind: Literal["supplier_completion", "supplier_handoff"]
    score_semantic: str
    score_value: float
    alert_threshold: float
    flagged: bool
    generated_at: TemporalValueRequest
    known_at: TemporalValueRequest
    predictor_artifact_ref: RiskSignalFieldValueRequest
    predictive_attribution_ref: RiskSignalFieldValueRequest
    prediction_explanation_ref: RiskSignalFieldValueRequest
    prediction_calibration_ref: RiskSignalFieldValueRequest
    prediction_ranking_ref: RiskSignalFieldValueRequest
    prediction_delivery_metadata: RiskSignalFieldValueRequest
    advisory_context: RiskSignalFieldValueRequest | None = None


class RiskSignalFixtureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    label: str
    signal: RiskSignalPreviewResponse


class PredictiveRiskStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["verified", "unavailable"]
    code: str
    message: str
    manual_investigation_available: bool


class RiskSignalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RiskSignalFixtureResponse]
    predictive_status: PredictiveRiskStatus | None = None


class ReactiveFixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str = Field(min_length=1, max_length=256)
    fixture_id: str = Field(min_length=1, max_length=128)


class ProactiveProposalSourcePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trigger-source-envelope.v1"]
    source_system: str
    data_classification: Literal[
        "generated",
        "public",
        "restricted",
        "confidential",
    ]


class ProactiveProposalPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["proactive-proposal.v1"]
    trigger_mode: Literal["proactive"]
    source: ProactiveProposalSourcePreviewResponse
    proposal_id: str
    proposal_revision: str
    dataset_version_id: str
    proposed_supplier_ref: ProactiveSubjectFieldRequest
    target_milestone_kind: ProactiveSubjectFieldRequest
    proposed_original_promise: ProactiveSubjectFieldRequest
    adjustment_inputs: dict[str, ProactiveSubjectFieldRequest]
    decision_at: ProactiveSubjectFieldRequest


class ProactiveProposalFixtureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    label: str
    proposal: ProactiveProposalPreviewResponse


class ProactiveProposalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProactiveProposalFixtureResponse]


class ProactiveFixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str = Field(min_length=1, max_length=256)
    fixture_id: str = Field(min_length=1, max_length=128)


class IngressFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    code: str
    severity: Literal["info", "warning", "error"]
    disposition: Literal["advisory", "reject"]
    affected_refs: list[str]
    message: str
    remediation: str


class IngressAuditBindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurrence_id: str
    event_seq: int = Field(gt=0)


class RiskSignalIngressReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["RiskSignal"]
    source_system: str
    source_signal_id: str
    source_revision: str
    source_payload_sha256: str
    source_order_line_ref: SourceEntityReferenceRequest


class ProactiveProposalIngressReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["ProactiveProposal"]
    source_system: str
    proposal_id: str
    proposal_revision: str
    source_payload_sha256: str


class InvestigationSubjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_line_id: str


class ProactiveSubjectInputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ValueState
    value: Any | None = None
    known_at: TemporalValueRequest | None = None
    lineage_ref: str | None = None


class ProactiveInvestigationSubjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["proactive_preview"]
    preview_subject_digest: str
    proposal_id: str
    proposal_revision: str
    supplier_id: ProactiveSubjectInputResponse
    target_milestone_kind: ProactiveSubjectInputResponse
    original_promise: ProactiveSubjectInputResponse
    adjustment_inputs: dict[str, ProactiveSubjectInputResponse]


class CausalWindowBoundsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known_at_lower: str
    known_at_upper: TemporalFieldResponse


class CausalSubjectRemovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_identity: str
    removed: bool
    post_subject_identity_hash: str


class CausalWindowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selector_version: str
    bounds: CausalWindowBoundsResponse
    selected_identity_hash: str
    selected_count: int = Field(ge=0)
    subject_removal: CausalSubjectRemovalResponse


class CausalSubjectAnalyticalValuesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: FieldValueResponse
    original_promise: TemporalFieldResponse
    adjustment_inputs: dict[str, FieldValueResponse]
    subject_exclusion_identity: str


class SupplierMilestoneOutcomeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["supplier-milestone-slippage.v1"]
    state: Literal["present", "unresolved", "not_applicable"]
    role: Literal["ESTIMATION_LINE", "SUBJECT_LINE"]
    canonical_slippage_duration_basis: Literal[
        "CALENDAR_DAY",
        "ELAPSED_86400_SECOND_DAY",
    ]
    supplier_milestone_slippage_duration_basis: Literal[
        "CALENDAR_DAY",
        "ELAPSED_86400_SECOND_DAY",
    ] | None = None
    frozen_promised_milestone: TemporalFieldResponse | None = None
    actual_target_milestone: TemporalFieldResponse | None = None
    supplier_milestone_slippage_days: float | None = None
    supplier_milestone_late: bool | None = None
    outcome_code: str | None
    reason_code: str | None
    reason: str
    eligibility_codes: list[str]
    follow_up: dict[str, Any] | None = None
    provenance: dict[str, Any]
    outcome_hash: str


class CausalEngineInputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    causal_input_schema_version: Literal["causal-input-projection.v2"]
    dataset_version_id: str
    subject_analytical_values: CausalSubjectAnalyticalValuesResponse
    decision_cutoff: TemporalFieldResponse
    observation_cutoff: TemporalFieldResponse
    target_milestone_kind: FieldValueResponse
    canonical_slippage_duration_basis: Literal[
        "CALENDAR_DAY",
        "ELAPSED_86400_SECOND_DAY",
    ]
    causal_question_version: str
    engine_configuration_ref: str
    supplier_load_exposure: dict[str, Any] | None = None
    supplier_milestone_outcome: SupplierMilestoneOutcomeResponse | None = None
    eligibility: dict[str, Any] | None = None
    estimator_window_ref: CausalWindowResponse
    history_lookback_ref: CausalWindowResponse
    historical_population_digest: str
    analytical_fact_lineage_refs: list[str]


class InvestigationRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_request_id: str
    schema_version: Literal["investigation-request.v1"]
    trigger_mode: Literal["reactive", "proactive"]
    ingress_ref: RiskSignalIngressReferenceResponse | ProactiveProposalIngressReferenceResponse
    rerun_of_request_id: FieldValueResponse
    dataset_version_id: str
    subject: InvestigationSubjectResponse | ProactiveInvestigationSubjectResponse
    decision_cutoff: TemporalFieldResponse
    decision_cutoff_source: Literal["canonical_commitment", "proactive_decision"]
    observation_cutoff: TemporalFieldResponse
    target_milestone_kind: FieldValueResponse
    causal_question_version: str
    engine_configuration_ref: str
    ingress_validation_refs: list[str]
    provenance_refs: list[str]
    prediction_metadata: FieldValueResponse
    accepted_at: datetime
    causal_engine_input: CausalEngineInputResponse
    causal_input_digest: str
    content_hash: str


class ReactiveIngressAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    status: Literal["accepted", "duplicate", "rejected", "accepted_with_warning"]
    scope: Literal["reactive_ingress"]
    source_system: str
    source_signal_id: str
    source_revision: str
    source_payload_sha256: str
    primary_code: str
    findings: list[IngressFindingResponse]
    evidence_refs: list[str]
    retryable: bool
    recovery_action: str
    received_at: datetime
    investigation_request_id: str | None
    investigation_request: InvestigationRequestResponse | None
    audit: IngressAuditBindingResponse


class ReactiveInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    attempt: ReactiveIngressAttemptResponse


class ProactiveIngressAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    status: Literal["accepted", "duplicate", "rejected", "accepted_with_warning"]
    scope: Literal["proactive_ingress"]
    source_system: str
    proposal_id: str
    proposal_revision: str
    source_payload_sha256: str
    primary_code: str
    findings: list[IngressFindingResponse]
    evidence_refs: list[str]
    retryable: bool
    recovery_action: str
    received_at: datetime
    investigation_request_id: str | None
    investigation_request: InvestigationRequestResponse | None
    audit: IngressAuditBindingResponse


class ProactiveInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    attempt: ProactiveIngressAttemptResponse


class RefreshInvestigationSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["refresh-investigation-snapshot.v1"]
    snapshot_id: str
    predecessor_request_id: str
    investigation_request_id: str
    trigger_mode: Literal["reactive", "proactive"]
    dataset_version_id: str
    observation_cutoff: dict[str, Any]
    causal_input_digest: str
    content_hash: str
    occurrence_id: str
    event_seq: int = Field(gt=0)
    created_at: datetime


class RefreshInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["CREATED", "IDEMPOTENT_REPLAY"]
    trigger_mode: Literal["reactive", "proactive"]
    attempt: ReactiveIngressAttemptResponse | ProactiveIngressAttemptResponse
    snapshot: RefreshInvestigationSnapshotResponse | None
    operation: OperationResponse | None
