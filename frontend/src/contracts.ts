export type HealthState = "live" | "ready" | "degraded" | "unavailable";
export type HealthCode =
  | "CORE_LIVE"
  | "CORE_READY"
  | "CORE_READY_GEMINI_DEGRADED"
  | "CORE_STORE_UNAVAILABLE";
export type AuditOutcomeCode = "CORE_READY" | "CORE_READY_GEMINI_DEGRADED";

export type HealthProbe = {
  state: HealthState;
  code: HealthCode;
};

export type HealthResponse = {
  service: "causal-delay-copilot";
  state: "ready" | "degraded" | "unavailable";
  code: HealthCode;
  liveness: HealthProbe;
  readiness: HealthProbe;
  degraded_capabilities: Array<"GEMINI_DRAFTING">;
  observed_at: string;
};

export type AuditOccurrenceRequest = {
  idempotency_key: string;
  occurrence_kind: "BOOT_HEALTH_CHECK";
  outcome_code: "CORE_READY" | "CORE_READY_GEMINI_DEGRADED";
};

export type AuditOccurrenceResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  occurrence_id: string;
  event_seq: number;
};

export type DecisionSupportEvidenceTags = {
  DRIVER_EVIDENCE: string;
  MECHANISTIC_LINK: string;
  RULE_BASED_ELIGIBILITY: string;
  ASSUMPTION_BASED_BENEFIT: string;
};

export type DecisionSupportSuppressionReason = {
  code: string;
  category: string;
  priority: number;
  reason: string;
  constraint_rule_priority?: number;
  rule_code?: string;
  option_scope?: string;
  explanation_code?: string;
  evidence_refs?: unknown[];
};

export type DecisionSupportOption = Record<string, unknown> & {
  option_code: string;
  option_version: string;
  label: string;
  evaluation_state: string;
  evidence_tags: DecisionSupportEvidenceTags;
  action_effect_evidence: string;
  suppression_reasons: DecisionSupportSuppressionReason[];
  constraint_results?: Array<Record<string, unknown>>;
  provenance?: Record<string, unknown>;
};

export type DecisionSupportRegistryInspection = Record<string, unknown> & {
  inspection_kind: "GOVERNED_RECORD_INSPECTION";
  effect_bearing: false;
  consumed_by_evaluation: false;
  release_binding: {
    state:
      | "BUNDLED_RELEASE_BOUND"
      | "RELEASE_BINDING_UNAVAILABLE"
      | "TEST_ONLY_NOT_SHIPPED";
    release_candidate_id: string | null;
    runtime_fingerprint_digest: string | null;
  };
};

export type DecisionSupportBoundary = Record<string, unknown> & {
  schema_version: "decision-support-boundary.v1";
  outcome:
    | "FAILED"
    | "NOT_PERMITTED"
    | "NO_ELIGIBLE_OPTION"
    | "TRADEOFF_REQUIRES_MANAGER_CHOICE"
    | "RECOMMENDATION_AVAILABLE";
  state:
    | "not_permitted"
    | "inactive_driver"
    | "approval_dependent_suppressed"
    | "constraints_evaluated"
    | "comparison_evaluated"
    | "tradeoff_requires_choice"
    | "recommendation_available"
    | "unavailable";
  primary_reason_code: string | null;
  reason: string | null;
  next_step: string | null;
  permission: {
    decision_support_evaluation_permitted: boolean;
    denial_reason_code: string | null;
    reason: string;
    next_step: string;
  };
  subject_driver_state: Record<string, unknown> | null;
  decision_support_evaluation_id: string | null;
  evaluation_lifecycle?: Record<string, unknown>;
  options: DecisionSupportOption[];
  evidence_tags: DecisionSupportEvidenceTags;
  suppression_reasons: DecisionSupportSuppressionReason[];
  action_effect_evidence: string;
  action_recommendation: Record<string, unknown> | null;
  tradeoff: Record<string, unknown> | null;
  monitoring: Record<string, unknown>;
  drafting: Record<string, unknown>;
  authorization: Record<string, unknown>;
  consumed_inputs: string[];
};

export type TradeoffSelectionReference = {
  reference: string;
  content_hash: string;
};

export type TradeoffSelectionCandidateReference = {
  evaluation_occurrence_id: string;
  option_code: string;
  option_version: string;
};

export type TradeoffSelectionCandidate = Record<string, unknown> & {
  candidate_reference: TradeoffSelectionCandidateReference;
  option_code: string;
  option_version: string;
  content_hash: string;
};

export type TradeoffSelectionRecord = Record<string, unknown> & {
  schema_identifier: "tradeoff-selection";
  schema_version: "1";
  selection_occurrence_id: string;
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  evaluation_digest: string;
  terminal_result_ref_and_hash: TradeoffSelectionReference;
  selected_candidate_ref: string;
  selected_candidate: TradeoffSelectionCandidate;
  manager_actor_ref: string;
  selected_at: string | Record<string, unknown>;
  available_at: string | Record<string, unknown>;
  governance_tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  content_hash: string;
};

export type TradeoffSelectionDeliveryAttempt = Record<string, unknown> & {
  schema_identifier: "tradeoff-selection-delivery-attempt";
  schema_version: "1";
  occurrence_id: string;
  tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  evaluation_digest: string;
  terminal_result_ref_and_hash: TradeoffSelectionReference;
  selected_candidate_ref: string;
  selected_candidate: TradeoffSelectionCandidate;
  selection_available_at: string | Record<string, unknown>;
  delivered_at: string | Record<string, unknown>;
  available_at: string | Record<string, unknown>;
  content_hash: string;
};

export type TradeoffSelectionPublishResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  selection: TradeoffSelectionRecord;
};

export type TradeoffSelectionValidationResult = Record<string, unknown> & {
  schema_identifier: "tradeoff-selection-validation-result";
  schema_version: "1";
  validation_result_occurrence_id: string;
  validation_result_key: string;
  validation_code:
    | "TRADEOFF_SELECTION_SERIES_NOT_FOUND"
    | "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH";
  delivery_attempt_ref_and_hash: TradeoffSelectionReference;
  evaluation_series_id: string | null;
  governance_tradeoff_selection_ref_and_hash: TradeoffSelectionReference | null;
  action_recommendation: null;
  selection_not_authorization: true;
  content_hash: string;
};

export type TradeoffSelectionOperation = Record<string, unknown> & {
  schema_identifier: "advice-currentness-operation";
  schema_version: "1";
  operation_occurrence_id: string;
  currentness_operation_key: string;
  operation_kind: "TRADEOFF_SELECTION_ACCEPTANCE";
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  evaluation_digest: string;
  terminal_result_ref_and_hash: TradeoffSelectionReference;
  recommendation_ref_and_hash_or_null: TradeoffSelectionReference | null;
  accepted_selection_claim_ref_and_hash_or_null: TradeoffSelectionReference | null;
  operation_payload_ref_and_hash: TradeoffSelectionReference;
  currentness_checked_at: string | Record<string, unknown>;
  content_hash: string;
};

export type TradeoffSelectionCurrentness = Record<string, unknown> & {
  schema_identifier: "advice-currentness-check";
  schema_version: "1";
  currentness_check_occurrence_id: string;
  currentness_check_key: string;
  currentness_operation_key: string;
  currentness_operation_ref_and_hash: TradeoffSelectionReference;
  currentness_outcome:
    | "CURRENTNESS_PROVEN_AT_CHECK"
    | "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
    | "ADVICE_CURRENTNESS_INVALIDATION";
  currentness_evidence_digest: string;
  currentness_checked_at: string | Record<string, unknown>;
  content_hash: string;
};

export type TradeoffSelectionTerminalClaim = Record<string, unknown> & {
  currentness_operation_key: string;
  currentness_operation_ref_and_hash: TradeoffSelectionReference;
  currentness_check_key: string;
  terminal_currentness_ref_and_hash: TradeoffSelectionReference;
  currentness_outcome: TradeoffSelectionCurrentness["currentness_outcome"];
  consuming_result_kind: "tradeoff-selection-result" | "NOT_APPLICABLE";
  consuming_result_ref_and_hash: TradeoffSelectionReference | null;
  refusal_result_ref_and_hash_or_null: TradeoffSelectionReference | null;
  installed_invalidation_head_ref_and_hash_or_null: TradeoffSelectionReference | null;
  terminal_head: TradeoffSelectionHead;
  content_hash: string;
};

export type TradeoffSelectionClaim = Record<string, unknown> & {
  schema_identifier: "tradeoff-selection-claim";
  schema_version: "1";
  selection_claim_occurrence_id: string;
  selection_claim_key: string;
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  evaluation_digest: string;
  terminal_result_ref_and_hash: TradeoffSelectionReference;
  tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  governance_tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  selected_candidate_ref: string;
  selected_candidate_content_hash: string;
  action_recommendation_key: string;
  action_recommendation_ref_and_hash: TradeoffSelectionReference;
  creation_currentness_operation_ref_and_hash: TradeoffSelectionReference;
  creation_currentness_check_ref_and_hash: TradeoffSelectionReference;
  published_at: string | Record<string, unknown>;
  selection_is_not_authorization: true;
  content_hash: string;
};

export type TradeoffSelectionResult = Record<string, unknown> & {
  schema_identifier: "tradeoff-selection-result";
  schema_version: "1";
  consuming_result_occurrence_id: string;
  consuming_result_key: string;
  currentness_operation_key: string;
  operation_kind: "TRADEOFF_SELECTION_ACCEPTANCE";
  currentness_operation_ref_and_hash: TradeoffSelectionReference;
  currentness_check_ref_and_hash: TradeoffSelectionReference;
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  evaluation_digest: string;
  terminal_result_ref_and_hash: TradeoffSelectionReference;
  tradeoff_selection_delivery_attempt_ref_and_hash: TradeoffSelectionReference;
  tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  governance_tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  selected_candidate_ref: string;
  selected_candidate_content_hash: string;
  selection_result:
    | "TRADEOFF_SELECTION_STALE"
    | "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF"
    | "TRADEOFF_SELECTION_INVALID_CANDIDATE"
    | "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT"
    | "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED"
    | "TRADEOFF_SELECTION_ACCEPTED";
  selection_claim_ref_and_hash_or_null: TradeoffSelectionReference | null;
  action_recommendation_ref_and_hash_or_null: TradeoffSelectionReference | null;
  currentness_outcome:
    | "CURRENTNESS_PROVEN_AT_CHECK"
    | "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
    | "ADVICE_CURRENTNESS_INVALIDATION";
  current_as_of: string | Record<string, unknown>;
  selection_not_authorization: true;
  content_hash: string;
};

export type TradeoffSelectionActionRecommendation = Record<string, unknown> & {
  schema_identifier: "action-recommendation";
  schema_version: "1";
  action_recommendation_key: string;
  occurrence_id: string;
  evaluation_series_id: string;
  evaluation_occurrence_id: string;
  decision_support_input_digest: string;
  selected_option_code: string;
  selected_option_version: string;
  selected_candidate_ref: string;
  selection_basis: "MANAGER_TRADEOFF_SELECTION";
  governance_tradeoff_selection_ref_and_hash: TradeoffSelectionReference;
  selection_is_not_authorization: true;
  content_hash: string;
};

export type TradeoffSelectionHead = Record<string, unknown> & {
  evaluation_series_id: string;
  head_kind:
    | "EVALUATION"
    | "PERMISSION_INVALIDATION"
    | "EVIDENCE_INTEGRITY_INVALIDATION"
    | "ADVICE_CURRENTNESS_INVALIDATION";
  head_occurrence_id: string;
  head_digest: string;
  head_result_hash: string;
  head_record_ref_and_hash: TradeoffSelectionReference;
};

export type TradeoffSelectionAcceptanceResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  selection_result: TradeoffSelectionResult | null;
  validation_result: TradeoffSelectionValidationResult | null;
  delivery_attempt: TradeoffSelectionDeliveryAttempt | null;
  operation: TradeoffSelectionOperation | null;
  currentness: TradeoffSelectionCurrentness | null;
  terminal_claim: TradeoffSelectionTerminalClaim | null;
  selection_claim: TradeoffSelectionClaim | null;
  action_recommendation: TradeoffSelectionActionRecommendation | null;
  head: TradeoffSelectionHead | null;
};

export type DecisionBriefSnapshot = {
  schema_version: "decision-brief-snapshot.v2";
  snapshot_id: string;
  investigation_request_id: string;
  reference_id: string;
  content_hash: string;
  occurrence_id: string;
  event_seq: number;
  created_at: string;
  subject_applicability: Record<string, unknown> & {
    state: "applicable" | "population_limited" | "abstained" | "unavailable";
  };
  subject_verdict: Record<string, unknown> | null;
  rendered_subject_verdict: Record<string, string> | null;
  action_lane: Record<string, unknown> & {
    state: "read_only" | "unavailable";
  };
  decision_support: DecisionSupportBoundary | null;
  decision_support_registry: DecisionSupportRegistryInspection | null;
  investigation_request: Record<string, unknown>;
  ingress_attempt: Record<string, unknown>;
  lineage: Record<string, unknown>;
  reference: Record<string, unknown>;
  referenced_records: Record<string, unknown>;
};

export type DecisionBriefResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  snapshot: DecisionBriefSnapshot;
};

export type ReplayResponse = {
  schema_version: "replay.v1";
  status: "REPLAYED" | "REPLAY_UNAVAILABLE";
  investigation_request_id: string;
  requested_event_seq: number;
  last_verified_event_seq: number;
  snapshot: DecisionBriefSnapshot | null;
  unresolved_references: string[];
  recovery_action: string;
};

export type DemoWorkspace = {
  workspace_id: string;
  status: "ACTIVE";
  created_at: string;
  last_seen_at: string;
  mutation_count: number;
  remaining_mutations: number;
  terminal_fresh_bundle_count: number;
  remaining_terminal_fresh_bundles: number;
};

export type OperationState =
  | "QUEUED"
  | "RUNNING"
  | "CANCELLING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT"
  | "INTERRUPTED"
  | "REJECTED";

export type OperationKind =
  | "FRESH_ANALYSIS"
  | "FRESH_REPRODUCTION"
  | "BOUNDED_WORK";

export type AnalysisRunStatus = {
  schema_version: "analysis-run-status.v1";
  analysis_run_id: string;
  occurrence_id: string;
  operation_id: string;
  status: "PENDING" | "RUNNING" | "ESTIMATED" | "ABSTAINED" | "FAILED";
  lifecycle: "executing" | "sealed" | "failed" | "quarantined";
  scientific_outcome: "pending" | "estimated" | "abstained" | "failed";
  verification_state:
    | "pending"
    | "machine_verified"
    | "reference_validated"
    | "invalid";
  availability_state: "available" | "suppressed";
  delivery_mode: "fresh_execution" | "existing_run_reuse";
  run_relationship: "fresh" | "reproduction" | "refresh";
  reproduces_run_id: string | null;
  refresh_of_request_id: string | null;
  reason_code: string | null;
  failure_code: string | null;
  recovery_action: string | null;
  estimator_executed: boolean;
  request_schema_version: "causal-engine-suite-request.v2";
  scientific_request_digest: string;
  runtime_fingerprint: Record<string, unknown>;
  runtime_fingerprint_digest: string;
  root_seed: number;
  derived_seed_registry: Array<Record<string, unknown>>;
  estimator_descriptor: Record<string, unknown>;
  feature_descriptor: Record<string, unknown>;
  fold_descriptor: Record<string, unknown>;
  fresh_run_detail: Record<string, unknown> | null;
  primary_result: Record<string, unknown> | null;
  bundle_manifest_hash: string | null;
  diagnostics: DiagnosticResult[];
  diagnostic_summary: DiagnosticSummary | null;
  robustness_grade: RobustnessGrade | null;
  evidence_verdict: EvidenceVerdict | null;
  rendered_verdict: RenderedEvidenceVerdict | null;
  subject_verdict: EvidenceVerdict | null;
  rendered_subject_verdict: RenderedEvidenceVerdict | null;
  reproduction_comparison: Record<string, unknown> | null;
};

export type DurableOperation = {
  schema_version: "durable-operation.v1";
  operation_id: string;
  operation_kind: OperationKind;
  state: OperationState;
  status: OperationState;
  queue_position: number | null;
  created_at: string;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested_at: string | null;
  retry_of_operation_id: string | null;
  failure_code: string | null;
  recovery_action: string | null;
  resource_warnings: Array<"DISK_SPACE_LOW">;
  artifact_state:
    | "NOT_STARTED"
    | "EXECUTING"
    | "PUBLISHED"
    | "QUARANTINED"
    | "QUARANTINE_UNAVAILABLE";
  retryable: boolean;
  timeout_seconds: number;
  thread_cap: number;
  memory_required_bytes: number;
  memory_available_bytes: number;
  disk_free_bytes: number;
  analysis_run: AnalysisRunStatus | null;
};

export type OperationMutationResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  operation: DurableOperation;
};

export type DiagnosticStatus =
  | "PASS"
  | "FAIL"
  | "UNSUPPORTED"
  | "UNAVAILABLE"
  | "FAILED"
  | "NOT_RUN";

export type DiagnosticResult = {
  schema_version: "diagnostic-result.v1";
  diagnostic_id: string;
  diagnostic_version: string;
  scope: string;
  status: DiagnosticStatus;
  policy_id: string;
  policy_version: string;
  rule_id: string;
  rule_version: string;
  observed: Record<string, unknown> | null;
  threshold: Record<string, unknown>;
  result: Record<string, unknown> | null;
  verdict_effect: "NONE" | "FRAGILITY" | "VETO" | "INSUFFICIENT";
  trigger_codes: string[];
  reason_code: string;
  reason: string;
  analysis_run_id: string | null;
  bundle_manifest_hash: string | null;
  evidence_refs: string[];
  input_refs: string[];
  diagnostic_identity: string;
  content_hash: string;
  upstream_trigger?: string;
};

export type DiagnosticSummary = {
  state: "complete" | "limited" | "attention_required";
  diagnostic_count: number;
  status_counts: Record<string, number>;
};

export type RobustnessGrade = {
  schema_version: "robustness-grade.v1";
  grade: "STRONG" | "MODERATE" | "WEAK" | "UNAVAILABLE";
  benchmark_group_refs: string[];
  strongest_group_ref: string | null;
  median_group_ref: string | null;
  strongest_adjusted_ci_lower: number | null;
  median_adjusted_ci_lower: number | null;
  content_hash: string;
};

export type EvidenceVerdict = {
  schema_version: "evidence-verdict.v2";
  scope: "population" | "subject";
  verdict_code:
    | "SUPPORTED_UNDER_ASSUMPTIONS"
    | "TENTATIVE"
    | "ASSOCIATION_ONLY"
    | "INSUFFICIENT";
  insufficient_evidence_reason_class: "NOT_ESTIMABLE" | "INCONCLUSIVE" | null;
  intended_role: string;
  permitted_claim_scope: string;
  subject_application_role_permitted: boolean;
  decision_support_role_permitted: boolean;
  decision_support_evaluation_permitted: boolean;
  population_verdict_ref: string | null;
  robustness_grade_ref: string | null;
  effect_display:
    | "NONE"
    | "INCONCLUSIVE_ESTIMATE"
    | "ADJUSTED_ASSOCIATION"
    | "CAUSAL_ESTIMATE";
  effect_result_ref: string | null;
  canonical_unit: string | null;
  canonical_slippage_duration_basis:
    | "CALENDAR_DAY"
    | "ELAPSED_86400_SECOND_DAY"
    | null;
  effect: Record<string, unknown> | null;
  primary_trigger_code: string;
  trigger_codes: string[];
  next_step_template_id: string;
  next_step_template_ids: string[];
  language_policy_id: string;
  content_hash: string;
};

export type RenderedEvidenceVerdict = {
  language: string;
  next_step: string;
  primary_trigger_label: string;
  next_step_template_id: string;
};

export type ValidatedReferenceDelivery = {
  schema_version: "analysis-run-read-model.v1";
  delivery_mode: "existing_run_reuse";
  delivery_badge: "Validated reference";
  verification_state: "reference_validated";
  reference_slot_id: string;
  reference_id: string;
  analysis_run_id: string;
  bundle_manifest_hash: string;
  bundle_ref: string;
  validation_attestation_id: string;
  validation_attestation_ref: string;
  release_candidate_id: string;
  intended_role: string;
  engine_result_status: "estimated" | "abstained";
  scientific_request_digest: string;
  dataset_version_id: string;
  runtime_fingerprint_digest: string;
  validation_policy_version: string;
  validated_at: string;
  diagnostics: DiagnosticResult[];
  diagnostic_summary: DiagnosticSummary;
  robustness_grade: RobustnessGrade | null;
  evidence_verdict: EvidenceVerdict | null;
  rendered_verdict: RenderedEvidenceVerdict | null;
};

export type IngestionRunResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  ingestion_run_id: string;
  dataset_version_id: string;
  status: "SUCCEEDED";
};

export type LineageRecord = Record<string, unknown>;

export type SourceRoleCeiling = {
  label: string;
  permitted_claim_scope: string;
  subject_application_role_permitted: boolean;
  decision_support_evaluation_permitted: boolean;
};

export type LineageSnapshot = {
  ingestion_run: LineageRecord;
  dataset_version: {
    dataset_id: string;
    dataset_version_id: string;
    source_kind: "semi_synthetic" | "olist" | "scms";
    intended_role:
      | "semi_synthetic_hero"
      | "out_of_domain_validation"
      | "rejection_vignette";
    mapping_manifest_id: string;
    source_role_ceiling: SourceRoleCeiling;
    record_counts: {
      order_lines: number;
      order_line_events: number;
      source_observations: number;
      validation_findings: number;
    };
  };
  mapping_manifest: LineageRecord;
  order_lines: LineageRecord[];
  order_line_events: LineageRecord[];
  source_observations: LineageRecord[];
  validation_findings: LineageRecord[];
  audit_binding: {
    snapshot_id: string;
    dataset_version_id: string;
    occurrence_id: string;
    event_seq: number;
    content_hash: string;
    created_at: string;
    source_role_ceiling: SourceRoleCeiling;
  };
};

export type RiskSignalFieldValue = {
  state: "present" | "missing" | "not_applicable" | "invalid" | "unresolved";
  value?: unknown;
};

export type RiskSignal = {
  schema_version: "risk-signal.v1";
  trigger_mode: "reactive";
  source: {
    schema_version: "trigger-source-envelope.v1";
    source_system: "bundled-predictive-stub";
    data_classification: "generated";
  };
  source_signal_id: string;
  source_revision: string;
  scored_dataset_version_ref: string;
  source_order_line_ref: {
    namespace: string;
    key: string | string[];
  };
  predictor_id: string;
  predictor_version: string;
  feature_contract_version: string;
  target_definition_id: string;
  target_milestone_kind: "supplier_completion" | "supplier_handoff";
  score_semantic: string;
  score_value: number;
  alert_threshold: number;
  flagged: boolean;
  generated_at: {
    value: string;
    kind: "date" | "local_datetime" | "instant";
    precision: string;
    timezone_status: "known" | "assumed" | "unknown" | "not_applicable";
    source_timezone: string | null;
  };
  known_at: {
    value: string;
    kind: "date" | "local_datetime" | "instant";
    precision: string;
    timezone_status: "known" | "assumed" | "unknown" | "not_applicable";
    source_timezone: string | null;
  };
  predictor_artifact_ref: RiskSignalFieldValue;
  predictive_attribution_ref: RiskSignalFieldValue;
  prediction_explanation_ref: RiskSignalFieldValue;
  prediction_calibration_ref: RiskSignalFieldValue;
  prediction_ranking_ref: RiskSignalFieldValue;
  prediction_delivery_metadata: RiskSignalFieldValue;
  advisory_context: RiskSignalFieldValue | null;
};

export type RiskSignalFixture = {
  fixture_id: string;
  label: string;
  signal: RiskSignal;
};

export type ProactiveSubjectField = RiskSignalFieldValue & {
  known_at?: RiskSignal["generated_at"];
  lineage_ref?: string;
};

export type ProactiveProposal = {
  schema_version: "proactive-proposal.v1";
  trigger_mode: "proactive";
  source: {
    schema_version: "trigger-source-envelope.v1";
    source_system: string;
    data_classification: "generated" | "public" | "restricted" | "confidential";
  };
  proposal_id: string;
  proposal_revision: string;
  dataset_version_id: string;
  proposed_supplier_ref: ProactiveSubjectField;
  target_milestone_kind: ProactiveSubjectField;
  proposed_original_promise: ProactiveSubjectField;
  adjustment_inputs: Record<string, ProactiveSubjectField>;
  decision_at: ProactiveSubjectField;
};

export type ProactiveProposalFixture = {
  fixture_id: string;
  label: string;
  proposal: ProactiveProposal;
};

export type PredictiveRiskStatus = {
  state: "verified" | "unavailable";
  code: string;
  message: string;
  manual_investigation_available: boolean;
};

export type IngressFinding = {
  finding_id: string;
  code: string;
  severity: "info" | "warning" | "error";
  disposition: "advisory" | "reject";
  affected_refs: string[];
  message: string;
  remediation: string;
};

export type CausalTemporalValue = {
  kind: "date" | "local_datetime" | "instant";
  source_value: string;
  normalized_value: string;
  precision: string;
  timezone_status: "known" | "assumed" | "unknown" | "not_applicable";
  source_timezone: RiskSignalFieldValue;
};

export type CausalTemporalField = {
  state: RiskSignalFieldValue["state"];
  value?: CausalTemporalValue;
};

export type CausalWindow = {
  selector_version: string;
  bounds: { known_at_lower: string; known_at_upper: CausalTemporalField };
  selected_identity_hash: string;
  selected_count: number;
  subject_removal: {
    subject_identity: string;
    removed: boolean;
    post_subject_identity_hash: string;
  };
};

export type SupplierLoadExposure = Record<string, unknown>;

export type SupplierMilestoneOutcome = {
  schema_version: "supplier-milestone-slippage.v1";
  state: "present" | "unresolved" | "not_applicable";
  role: "ESTIMATION_LINE" | "SUBJECT_LINE";
  canonical_slippage_duration_basis:
    | "CALENDAR_DAY"
    | "ELAPSED_86400_SECOND_DAY";
  supplier_milestone_slippage_duration_basis?:
    | "CALENDAR_DAY"
    | "ELAPSED_86400_SECOND_DAY";
  frozen_promised_milestone?: CausalTemporalField;
  actual_target_milestone?: CausalTemporalField;
  supplier_milestone_slippage_days: number | null;
  supplier_milestone_late: boolean | null;
  outcome_code: string | null;
  reason_code: string | null;
  reason: string;
  eligibility_codes: string[];
  follow_up?: Record<string, unknown>;
  provenance: Record<string, unknown>;
  outcome_hash: string;
};

export type CausalEngineInput = {
  causal_input_schema_version: "causal-input-projection.v2";
  dataset_version_id: string;
  subject_analytical_values: {
    supplier_id: RiskSignalFieldValue;
    original_promise: CausalTemporalField;
    adjustment_inputs: Record<string, RiskSignalFieldValue>;
    subject_exclusion_identity: string;
  };
  decision_cutoff: CausalTemporalField;
  observation_cutoff: CausalTemporalField;
  target_milestone_kind: RiskSignalFieldValue;
  canonical_slippage_duration_basis:
    | "CALENDAR_DAY"
    | "ELAPSED_86400_SECOND_DAY";
  causal_question_version: string;
  engine_configuration_ref: string;
  supplier_load_exposure?: SupplierLoadExposure;
  supplier_milestone_outcome?: SupplierMilestoneOutcome;
  eligibility?: Record<string, unknown>;
  estimator_window_ref: CausalWindow;
  history_lookback_ref: CausalWindow;
  historical_population_digest: string;
  analytical_fact_lineage_refs: string[];
};

export type InvestigationRequest = {
  investigation_request_id: string;
  schema_version: "investigation-request.v1";
  trigger_mode: "reactive" | "proactive";
  ingress_ref:
    | {
        kind: "RiskSignal";
        source_system: string;
        source_signal_id: string;
        source_revision: string;
        source_payload_sha256: string;
        source_order_line_ref: { namespace: string; key: string | string[] };
      }
    | {
        kind: "ProactiveProposal";
        source_system: string;
        proposal_id: string;
        proposal_revision: string;
        source_payload_sha256: string;
      };
  rerun_of_request_id: RiskSignalFieldValue;
  dataset_version_id: string;
  subject:
    | { order_line_id: string }
    | {
        kind: "proactive_preview";
        preview_subject_digest: string;
        proposal_id: string;
        proposal_revision: string;
        supplier_id: ProactiveSubjectField;
        target_milestone_kind: ProactiveSubjectField;
        original_promise: ProactiveSubjectField;
        adjustment_inputs: Record<string, ProactiveSubjectField>;
      };
  decision_cutoff: CausalTemporalField;
  decision_cutoff_source: "canonical_commitment" | "proactive_decision";
  observation_cutoff: CausalTemporalField;
  target_milestone_kind: RiskSignalFieldValue;
  causal_question_version: string;
  engine_configuration_ref: string;
  ingress_validation_refs: string[];
  provenance_refs: string[];
  prediction_metadata: RiskSignalFieldValue;
  accepted_at: string;
  causal_engine_input: CausalEngineInput;
  causal_input_digest: string;
  content_hash: string;
};

export type ReactiveIngressAttempt = {
  attempt_id: string;
  status: "accepted" | "duplicate" | "rejected" | "accepted_with_warning";
  scope: "reactive_ingress";
  source_system: string;
  source_signal_id: string;
  source_revision: string;
  source_payload_sha256: string;
  primary_code: string;
  findings: IngressFinding[];
  evidence_refs: string[];
  retryable: boolean;
  recovery_action: string;
  received_at: string;
  investigation_request_id: string | null;
  investigation_request: InvestigationRequest | null;
  audit: { occurrence_id: string; event_seq: number };
};

export type RiskSignalListResponse = {
  items: RiskSignalFixture[];
  predictive_status?: PredictiveRiskStatus;
};

export type ReactiveInvestigationResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  attempt: ReactiveIngressAttempt;
};

export type ProactiveIngressAttempt = {
  attempt_id: string;
  status: "accepted" | "duplicate" | "rejected" | "accepted_with_warning";
  scope: "proactive_ingress";
  source_system: string;
  proposal_id: string;
  proposal_revision: string;
  source_payload_sha256: string;
  primary_code: string;
  findings: IngressFinding[];
  evidence_refs: string[];
  retryable: boolean;
  recovery_action: string;
  received_at: string;
  investigation_request_id: string | null;
  investigation_request: InvestigationRequest | null;
  audit: { occurrence_id: string; event_seq: number };
};

export type ProactiveProposalListResponse = {
  items: ProactiveProposalFixture[];
};

export type ProactiveInvestigationResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  attempt: ProactiveIngressAttempt;
};

export type RefreshInvestigationSnapshot = {
  schema_version: "refresh-investigation-snapshot.v1";
  snapshot_id: string;
  predecessor_request_id: string;
  investigation_request_id: string;
  trigger_mode: "reactive" | "proactive";
  dataset_version_id: string;
  observation_cutoff: Record<string, unknown>;
  causal_input_digest: string;
  content_hash: string;
  occurrence_id: string;
  event_seq: number;
  created_at: string;
};

export type RefreshInvestigationResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  trigger_mode: "reactive" | "proactive";
  attempt: ReactiveIngressAttempt | ProactiveIngressAttempt;
  snapshot: RefreshInvestigationSnapshot | null;
  operation: DurableOperation | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function parseTradeoffReference(value: unknown): TradeoffSelectionReference {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    !isNonEmptyString(value.reference) ||
    !isNonEmptyString(value.content_hash)
  ) {
    throw new Error("invalid trade-off reference");
  }
  return { reference: value.reference, content_hash: value.content_hash };
}

function parseTradeoffCandidateReference(
  value: unknown,
): TradeoffSelectionCandidateReference {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    !isNonEmptyString(value.evaluation_occurrence_id) ||
    !isNonEmptyString(value.option_code) ||
    !isNonEmptyString(value.option_version)
  ) {
    throw new Error("invalid trade-off candidate reference");
  }
  return {
    evaluation_occurrence_id: value.evaluation_occurrence_id,
    option_code: value.option_code,
    option_version: value.option_version,
  };
}

function parseTradeoffCandidate(value: unknown): TradeoffSelectionCandidate {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    !isNonEmptyString(value.option_code) ||
    !isNonEmptyString(value.option_version) ||
    !isNonEmptyString(value.content_hash)
  ) {
    throw new Error("invalid trade-off candidate");
  }
  return {
    ...value,
    candidate_reference: parseTradeoffCandidateReference(value.candidate_reference),
    option_code: value.option_code,
    option_version: value.option_version,
    content_hash: value.content_hash,
  };
}

export function parseTradeoffSelectionRecord(value: unknown): TradeoffSelectionRecord {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    value.schema_identifier !== "tradeoff-selection" ||
    value.schema_version !== "1" ||
    !isNonEmptyString(value.selection_occurrence_id) ||
    !isNonEmptyString(value.evaluation_series_id) ||
    !isNonEmptyString(value.evaluation_occurrence_id) ||
    !isNonEmptyString(value.evaluation_digest) ||
    !isNonEmptyString(value.selected_candidate_ref) ||
    !isNonEmptyString(value.manager_actor_ref) ||
    !isNonEmptyString(value.content_hash) ||
    !(
      typeof value.selected_at === "string" ||
      (isRecord(value.selected_at) && !Array.isArray(value.selected_at))
    ) ||
    !(
      typeof value.available_at === "string" ||
      (isRecord(value.available_at) && !Array.isArray(value.available_at))
    )
  ) {
    throw new Error("invalid trade-off selection");
  }
  return {
    ...value,
    terminal_result_ref_and_hash: parseTradeoffReference(
      value.terminal_result_ref_and_hash,
    ),
    selected_candidate: parseTradeoffCandidate(value.selected_candidate),
    governance_tradeoff_selection_ref_and_hash: parseTradeoffReference(
      value.governance_tradeoff_selection_ref_and_hash,
    ),
    schema_identifier: "tradeoff-selection",
    schema_version: "1",
    selection_occurrence_id: value.selection_occurrence_id,
    evaluation_series_id: value.evaluation_series_id,
    evaluation_occurrence_id: value.evaluation_occurrence_id,
    evaluation_digest: value.evaluation_digest,
    selected_candidate_ref: value.selected_candidate_ref,
    manager_actor_ref: value.manager_actor_ref,
    selected_at: value.selected_at,
    available_at: value.available_at,
    content_hash: value.content_hash,
  };
}

export function parseTradeoffSelectionDeliveryAttempt(
  value: unknown,
): TradeoffSelectionDeliveryAttempt {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    value.schema_identifier !== "tradeoff-selection-delivery-attempt" ||
    value.schema_version !== "1" ||
    !isNonEmptyString(value.occurrence_id) ||
    !isNonEmptyString(value.evaluation_series_id) ||
    !isNonEmptyString(value.evaluation_occurrence_id) ||
    !isNonEmptyString(value.evaluation_digest) ||
    !isNonEmptyString(value.selected_candidate_ref) ||
    !isNonEmptyString(value.content_hash) ||
    !(
      typeof value.selection_available_at === "string" ||
      (isRecord(value.selection_available_at) && !Array.isArray(value.selection_available_at))
    ) ||
    !(
      typeof value.delivered_at === "string" ||
      (isRecord(value.delivered_at) && !Array.isArray(value.delivered_at))
    ) ||
    !(
      typeof value.available_at === "string" ||
      (isRecord(value.available_at) && !Array.isArray(value.available_at))
    )
  ) {
    throw new Error("invalid trade-off delivery attempt");
  }
  return {
    ...value,
    tradeoff_selection_ref_and_hash: parseTradeoffReference(
      value.tradeoff_selection_ref_and_hash,
    ),
    terminal_result_ref_and_hash: parseTradeoffReference(
      value.terminal_result_ref_and_hash,
    ),
    selected_candidate: parseTradeoffCandidate(value.selected_candidate),
    schema_identifier: "tradeoff-selection-delivery-attempt",
    schema_version: "1",
    occurrence_id: value.occurrence_id,
    evaluation_series_id: value.evaluation_series_id,
    evaluation_occurrence_id: value.evaluation_occurrence_id,
    evaluation_digest: value.evaluation_digest,
    selected_candidate_ref: value.selected_candidate_ref,
    selection_available_at: value.selection_available_at,
    delivered_at: value.delivered_at,
    available_at: value.available_at,
    content_hash: value.content_hash,
  };
}

function requiredTradeoffString(
  record: Record<string, unknown>,
  key: string,
  label: string,
): string {
  if (!isNonEmptyString(record[key])) {
    throw new Error(`invalid trade-off ${label}`);
  }
  return record[key];
}

function parseTradeoffTimestamp(
  value: unknown,
  label: string,
): string | Record<string, unknown> {
  if (
    typeof value !== "string" &&
    (!isRecord(value) || Array.isArray(value))
  ) {
    throw new Error(`invalid trade-off ${label}`);
  }
  return value;
}

function parseTradeoffResponseRecord(
  value: unknown,
  schemaIdentifier: string,
  label: string,
): Record<string, unknown> {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    value.schema_identifier !== schemaIdentifier ||
    value.schema_version !== "1" ||
    !isNonEmptyString(value.content_hash)
  ) {
    throw new Error(`invalid trade-off ${label}`);
  }
  return value;
}

function isTradeoffValidationCode(
  value: unknown,
): value is TradeoffSelectionValidationResult["validation_code"] {
  return (
    value === "TRADEOFF_SELECTION_SERIES_NOT_FOUND" ||
    value === "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH"
  );
}

function isTradeoffCurrentnessOutcome(
  value: unknown,
): value is TradeoffSelectionCurrentness["currentness_outcome"] {
  return (
    value === "CURRENTNESS_PROVEN_AT_CHECK" ||
    value === "CURRENTNESS_NOT_AUTHORITATIVE_HEAD" ||
    value === "ADVICE_CURRENTNESS_INVALIDATION"
  );
}

function isTradeoffSelectionResultCode(
  value: unknown,
): value is TradeoffSelectionResult["selection_result"] {
  return (
    value === "TRADEOFF_SELECTION_STALE" ||
    value === "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF" ||
    value === "TRADEOFF_SELECTION_INVALID_CANDIDATE" ||
    value === "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT" ||
    value === "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED" ||
    value === "TRADEOFF_SELECTION_ACCEPTED"
  );
}

function isTradeoffConsumingResultKind(
  value: unknown,
): value is TradeoffSelectionTerminalClaim["consuming_result_kind"] {
  return value === "tradeoff-selection-result" || value === "NOT_APPLICABLE";
}

function isTradeoffHeadKind(
  value: unknown,
): value is TradeoffSelectionHead["head_kind"] {
  return (
    value === "EVALUATION" ||
    value === "PERMISSION_INVALIDATION" ||
    value === "EVIDENCE_INTEGRITY_INVALIDATION" ||
    value === "ADVICE_CURRENTNESS_INVALIDATION"
  );
}

function optionalTradeoffReference(
  record: Record<string, unknown>,
  key: string,
): TradeoffSelectionReference | null {
  if (record[key] === null || record[key] === undefined) {
    return null;
  }
  return parseTradeoffReference(record[key]);
}

function parseTradeoffSelectionValidationResult(
  value: unknown,
): TradeoffSelectionValidationResult {
  const record = parseTradeoffResponseRecord(
    value,
    "tradeoff-selection-validation-result",
    "validation result",
  );
  if (
    record.selection_not_authorization !== true ||
    record.action_recommendation !== null ||
    !isTradeoffValidationCode(record.validation_code)
  ) {
    throw new Error("invalid trade-off validation result");
  }
  const evaluationSeriesId = record.evaluation_series_id;
  if (
    evaluationSeriesId !== null &&
    !isNonEmptyString(evaluationSeriesId)
  ) {
    throw new Error("invalid trade-off validation result");
  }
  return {
    ...record,
    schema_identifier: "tradeoff-selection-validation-result",
    schema_version: "1",
    validation_result_occurrence_id: requiredTradeoffString(
      record,
      "validation_result_occurrence_id",
      "validation result",
    ),
    validation_result_key: requiredTradeoffString(
      record,
      "validation_result_key",
      "validation result",
    ),
    validation_code: record.validation_code,
    delivery_attempt_ref_and_hash: parseTradeoffReference(
      record.delivery_attempt_ref_and_hash,
    ),
    evaluation_series_id: evaluationSeriesId,
    governance_tradeoff_selection_ref_and_hash: optionalTradeoffReference(
      record,
      "governance_tradeoff_selection_ref_and_hash",
    ),
    action_recommendation: null,
    selection_not_authorization: true,
    content_hash: requiredTradeoffString(record, "content_hash", "validation result"),
  } as TradeoffSelectionValidationResult;
}

function parseTradeoffSelectionOperation(
  value: unknown,
): TradeoffSelectionOperation {
  const record = parseTradeoffResponseRecord(
    value,
    "advice-currentness-operation",
    "operation",
  );
  if (record.operation_kind !== "TRADEOFF_SELECTION_ACCEPTANCE") {
    throw new Error("invalid trade-off operation");
  }
  return {
    ...record,
    schema_identifier: "advice-currentness-operation",
    schema_version: "1",
    operation_occurrence_id: requiredTradeoffString(record, "operation_occurrence_id", "operation"),
    currentness_operation_key: requiredTradeoffString(record, "currentness_operation_key", "operation"),
    operation_kind: "TRADEOFF_SELECTION_ACCEPTANCE",
    evaluation_series_id: requiredTradeoffString(record, "evaluation_series_id", "operation"),
    evaluation_occurrence_id: requiredTradeoffString(record, "evaluation_occurrence_id", "operation"),
    evaluation_digest: requiredTradeoffString(record, "evaluation_digest", "operation"),
    terminal_result_ref_and_hash: parseTradeoffReference(record.terminal_result_ref_and_hash),
    recommendation_ref_and_hash_or_null: optionalTradeoffReference(
      record,
      "recommendation_ref_and_hash_or_null",
    ),
    accepted_selection_claim_ref_and_hash_or_null: optionalTradeoffReference(
      record,
      "accepted_selection_claim_ref_and_hash_or_null",
    ),
    operation_payload_ref_and_hash: parseTradeoffReference(
      record.operation_payload_ref_and_hash,
    ),
    currentness_checked_at: parseTradeoffTimestamp(
      record.currentness_checked_at,
      "operation time",
    ),
    content_hash: requiredTradeoffString(record, "content_hash", "operation"),
  } as TradeoffSelectionOperation;
}

function parseTradeoffSelectionCurrentness(
  value: unknown,
): TradeoffSelectionCurrentness {
  const record = parseTradeoffResponseRecord(
    value,
    "advice-currentness-check",
    "currentness",
  );
  if (!isTradeoffCurrentnessOutcome(record.currentness_outcome)) {
    throw new Error("invalid trade-off currentness");
  }
  return {
    ...record,
    schema_identifier: "advice-currentness-check",
    schema_version: "1",
    currentness_check_occurrence_id: requiredTradeoffString(
      record,
      "currentness_check_occurrence_id",
      "currentness",
    ),
    currentness_check_key: requiredTradeoffString(record, "currentness_check_key", "currentness"),
    currentness_operation_key: requiredTradeoffString(
      record,
      "currentness_operation_key",
      "currentness",
    ),
    currentness_operation_ref_and_hash: parseTradeoffReference(
      record.currentness_operation_ref_and_hash,
    ),
    currentness_outcome: record.currentness_outcome,
    currentness_evidence_digest: requiredTradeoffString(
      record,
      "currentness_evidence_digest",
      "currentness",
    ),
    currentness_checked_at: parseTradeoffTimestamp(
      record.currentness_checked_at,
      "currentness time",
    ),
    content_hash: requiredTradeoffString(record, "content_hash", "currentness"),
  } as TradeoffSelectionCurrentness;
}

function parseTradeoffSelectionTerminalClaim(
  value: unknown,
): TradeoffSelectionTerminalClaim {
  if (!isRecord(value) || Array.isArray(value) || !isNonEmptyString(value.content_hash)) {
    throw new Error("invalid trade-off terminal claim");
  }
  if (
    !isTradeoffCurrentnessOutcome(value.currentness_outcome) ||
    !isTradeoffConsumingResultKind(value.consuming_result_kind) ||
    !isRecord(value.terminal_head) ||
    Array.isArray(value.terminal_head) ||
    !isTradeoffHeadKind(value.terminal_head.head_kind)
  ) {
    throw new Error("invalid trade-off terminal claim");
  }
  return {
    ...value,
    currentness_operation_key: requiredTradeoffString(value, "currentness_operation_key", "terminal claim"),
    currentness_operation_ref_and_hash: parseTradeoffReference(
      value.currentness_operation_ref_and_hash,
    ),
    currentness_check_key: requiredTradeoffString(value, "currentness_check_key", "terminal claim"),
    terminal_currentness_ref_and_hash: parseTradeoffReference(
      value.terminal_currentness_ref_and_hash,
    ),
    currentness_outcome: value.currentness_outcome,
    consuming_result_kind: value.consuming_result_kind,
    consuming_result_ref_and_hash: optionalTradeoffReference(
      value,
      "consuming_result_ref_and_hash",
    ),
    refusal_result_ref_and_hash_or_null: optionalTradeoffReference(
      value,
      "refusal_result_ref_and_hash_or_null",
    ),
    installed_invalidation_head_ref_and_hash_or_null: optionalTradeoffReference(
      value,
      "installed_invalidation_head_ref_and_hash_or_null",
    ),
    terminal_head: parseTradeoffSelectionHead(value.terminal_head),
    content_hash: requiredTradeoffString(value, "content_hash", "terminal claim"),
  } as TradeoffSelectionTerminalClaim;
}

function parseTradeoffSelectionClaim(value: unknown): TradeoffSelectionClaim {
  const record = parseTradeoffResponseRecord(
    value,
    "tradeoff-selection-claim",
    "selection claim",
  );
  if (record.selection_is_not_authorization !== true) {
    throw new Error("invalid trade-off selection claim");
  }
  return {
    ...record,
    schema_identifier: "tradeoff-selection-claim",
    schema_version: "1",
    selection_claim_occurrence_id: requiredTradeoffString(record, "selection_claim_occurrence_id", "selection claim"),
    selection_claim_key: requiredTradeoffString(record, "selection_claim_key", "selection claim"),
    evaluation_series_id: requiredTradeoffString(record, "evaluation_series_id", "selection claim"),
    evaluation_occurrence_id: requiredTradeoffString(record, "evaluation_occurrence_id", "selection claim"),
    evaluation_digest: requiredTradeoffString(record, "evaluation_digest", "selection claim"),
    terminal_result_ref_and_hash: parseTradeoffReference(record.terminal_result_ref_and_hash),
    tradeoff_selection_ref_and_hash: parseTradeoffReference(record.tradeoff_selection_ref_and_hash),
    governance_tradeoff_selection_ref_and_hash: parseTradeoffReference(
      record.governance_tradeoff_selection_ref_and_hash,
    ),
    selected_candidate_ref: requiredTradeoffString(record, "selected_candidate_ref", "selection claim"),
    selected_candidate_content_hash: requiredTradeoffString(
      record,
      "selected_candidate_content_hash",
      "selection claim",
    ),
    action_recommendation_key: requiredTradeoffString(record, "action_recommendation_key", "selection claim"),
    action_recommendation_ref_and_hash: parseTradeoffReference(
      record.action_recommendation_ref_and_hash,
    ),
    creation_currentness_operation_ref_and_hash: parseTradeoffReference(
      record.creation_currentness_operation_ref_and_hash,
    ),
    creation_currentness_check_ref_and_hash: parseTradeoffReference(
      record.creation_currentness_check_ref_and_hash,
    ),
    published_at: parseTradeoffTimestamp(record.published_at, "selection claim time"),
    selection_is_not_authorization: true,
    content_hash: requiredTradeoffString(record, "content_hash", "selection claim"),
  } as TradeoffSelectionClaim;
}

function parseTradeoffSelectionResult(value: unknown): TradeoffSelectionResult {
  const record = parseTradeoffResponseRecord(
    value,
    "tradeoff-selection-result",
    "selection result",
  );
  if (
    record.operation_kind !== "TRADEOFF_SELECTION_ACCEPTANCE" ||
    record.selection_not_authorization !== true ||
    !isTradeoffSelectionResultCode(record.selection_result) ||
    !isTradeoffCurrentnessOutcome(record.currentness_outcome)
  ) {
    throw new Error("invalid trade-off selection result");
  }
  return {
    ...record,
    schema_identifier: "tradeoff-selection-result",
    schema_version: "1",
    consuming_result_occurrence_id: requiredTradeoffString(record, "consuming_result_occurrence_id", "selection result"),
    consuming_result_key: requiredTradeoffString(record, "consuming_result_key", "selection result"),
    currentness_operation_key: requiredTradeoffString(record, "currentness_operation_key", "selection result"),
    operation_kind: "TRADEOFF_SELECTION_ACCEPTANCE",
    currentness_operation_ref_and_hash: parseTradeoffReference(record.currentness_operation_ref_and_hash),
    currentness_check_ref_and_hash: parseTradeoffReference(record.currentness_check_ref_and_hash),
    evaluation_series_id: requiredTradeoffString(record, "evaluation_series_id", "selection result"),
    evaluation_occurrence_id: requiredTradeoffString(record, "evaluation_occurrence_id", "selection result"),
    evaluation_digest: requiredTradeoffString(record, "evaluation_digest", "selection result"),
    terminal_result_ref_and_hash: parseTradeoffReference(record.terminal_result_ref_and_hash),
    tradeoff_selection_delivery_attempt_ref_and_hash: parseTradeoffReference(
      record.tradeoff_selection_delivery_attempt_ref_and_hash,
    ),
    tradeoff_selection_ref_and_hash: parseTradeoffReference(record.tradeoff_selection_ref_and_hash),
    governance_tradeoff_selection_ref_and_hash: parseTradeoffReference(
      record.governance_tradeoff_selection_ref_and_hash,
    ),
    selected_candidate_ref: requiredTradeoffString(record, "selected_candidate_ref", "selection result"),
    selected_candidate_content_hash: requiredTradeoffString(
      record,
      "selected_candidate_content_hash",
      "selection result",
    ),
    selection_result: record.selection_result,
    selection_claim_ref_and_hash_or_null: optionalTradeoffReference(
      record,
      "selection_claim_ref_and_hash_or_null",
    ),
    action_recommendation_ref_and_hash_or_null: optionalTradeoffReference(
      record,
      "action_recommendation_ref_and_hash_or_null",
    ),
    currentness_outcome: record.currentness_outcome,
    current_as_of: parseTradeoffTimestamp(record.current_as_of, "selection result time"),
    selection_not_authorization: true,
    content_hash: requiredTradeoffString(record, "content_hash", "selection result"),
  } as TradeoffSelectionResult;
}

function parseTradeoffSelectionActionRecommendation(
  value: unknown,
): TradeoffSelectionActionRecommendation {
  const record = parseTradeoffResponseRecord(
    value,
    "action-recommendation",
    "action recommendation",
  );
  if (
    record.selection_basis !== "MANAGER_TRADEOFF_SELECTION" ||
    record.selection_is_not_authorization !== true
  ) {
    throw new Error("invalid trade-off action recommendation");
  }
  return {
    ...record,
    schema_identifier: "action-recommendation",
    schema_version: "1",
    action_recommendation_key: requiredTradeoffString(record, "action_recommendation_key", "action recommendation"),
    occurrence_id: requiredTradeoffString(record, "occurrence_id", "action recommendation"),
    evaluation_series_id: requiredTradeoffString(record, "evaluation_series_id", "action recommendation"),
    evaluation_occurrence_id: requiredTradeoffString(record, "evaluation_occurrence_id", "action recommendation"),
    decision_support_input_digest: requiredTradeoffString(
      record,
      "decision_support_input_digest",
      "action recommendation",
    ),
    selected_option_code: requiredTradeoffString(record, "selected_option_code", "action recommendation"),
    selected_option_version: requiredTradeoffString(record, "selected_option_version", "action recommendation"),
    selected_candidate_ref: requiredTradeoffString(record, "selected_candidate_ref", "action recommendation"),
    selection_basis: "MANAGER_TRADEOFF_SELECTION",
    governance_tradeoff_selection_ref_and_hash: parseTradeoffReference(
      record.governance_tradeoff_selection_ref_and_hash,
    ),
    selection_is_not_authorization: true,
    content_hash: requiredTradeoffString(record, "content_hash", "action recommendation"),
  } as TradeoffSelectionActionRecommendation;
}

function parseTradeoffSelectionHead(value: unknown): TradeoffSelectionHead {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    !isTradeoffHeadKind(value.head_kind)
  ) {
    throw new Error("invalid trade-off head");
  }
  return {
    ...value,
    evaluation_series_id: requiredTradeoffString(value, "evaluation_series_id", "head"),
    head_kind: value.head_kind,
    head_occurrence_id: requiredTradeoffString(value, "head_occurrence_id", "head"),
    head_digest: requiredTradeoffString(value, "head_digest", "head"),
    head_result_hash: requiredTradeoffString(value, "head_result_hash", "head"),
    head_record_ref_and_hash: parseTradeoffReference(value.head_record_ref_and_hash),
  } as TradeoffSelectionHead;
}

function parseOptionalTradeoffResponse<T>(
  value: unknown,
  parser: (record: unknown) => T,
): T | null {
  if (value === null || value === undefined) {
    return null;
  }
  return parser(value);
}

export function parseTradeoffSelectionPublishResponse(
  value: unknown,
): TradeoffSelectionPublishResponse {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY")
  ) {
    throw new Error("invalid trade-off publication response");
  }
  return {
    result: value.result,
    selection: parseTradeoffSelectionRecord(value.selection),
  };
}

export function parseTradeoffSelectionAcceptanceResponse(
  value: unknown,
): TradeoffSelectionAcceptanceResponse {
  if (
    !isRecord(value) ||
    Array.isArray(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY")
  ) {
    throw new Error("invalid trade-off acceptance response");
  }
  const hasSelectionResult =
    value.selection_result !== null && value.selection_result !== undefined;
  const hasValidationResult =
    value.validation_result !== null && value.validation_result !== undefined;
  if (hasSelectionResult === hasValidationResult) {
    throw new Error("invalid trade-off acceptance terminal result cardinality");
  }
  return {
    result: value.result,
    selection_result: parseOptionalTradeoffResponse(
      value.selection_result,
      parseTradeoffSelectionResult,
    ),
    validation_result: parseOptionalTradeoffResponse(
      value.validation_result,
      parseTradeoffSelectionValidationResult,
    ),
    delivery_attempt:
      value.delivery_attempt === null
        ? null
        : parseTradeoffSelectionDeliveryAttempt(value.delivery_attempt),
    operation: parseOptionalTradeoffResponse(
      value.operation,
      parseTradeoffSelectionOperation,
    ),
    currentness: parseOptionalTradeoffResponse(
      value.currentness,
      parseTradeoffSelectionCurrentness,
    ),
    terminal_claim: parseOptionalTradeoffResponse(
      value.terminal_claim,
      parseTradeoffSelectionTerminalClaim,
    ),
    selection_claim: parseOptionalTradeoffResponse(
      value.selection_claim,
      parseTradeoffSelectionClaim,
    ),
    action_recommendation: parseOptionalTradeoffResponse(
      value.action_recommendation,
      parseTradeoffSelectionActionRecommendation,
    ),
    head: parseOptionalTradeoffResponse(value.head, parseTradeoffSelectionHead),
  };
}

function isHealthCode(value: unknown): value is HealthCode {
  return (
    value === "CORE_LIVE" ||
    value === "CORE_READY" ||
    value === "CORE_READY_GEMINI_DEGRADED" ||
    value === "CORE_STORE_UNAVAILABLE"
  );
}

function parseProbe(value: unknown): HealthProbe {
  if (!isRecord(value) || !isHealthCode(value.code)) {
    throw new Error("invalid health response");
  }
  const state = value.state;
  if (
    state !== "live" &&
    state !== "ready" &&
    state !== "degraded" &&
    state !== "unavailable"
  ) {
    throw new Error("invalid health response");
  }
  return { state, code: value.code };
}

export function parseHealthResponse(value: unknown): HealthResponse {
  if (!isRecord(value) || value.service !== "causal-delay-copilot") {
    throw new Error("invalid health response");
  }
  const liveness = parseProbe(value.liveness);
  const readiness = parseProbe(value.readiness);
  const livenessIsValid =
    liveness.state === "live" && liveness.code === "CORE_LIVE";
  const readinessIsValid =
    (readiness.state === "ready" && readiness.code === "CORE_READY") ||
    (readiness.state === "degraded" &&
      readiness.code === "CORE_READY_GEMINI_DEGRADED") ||
    (readiness.state === "unavailable" &&
      readiness.code === "CORE_STORE_UNAVAILABLE");
  if (
    !isHealthCode(value.code) ||
    (value.state !== "ready" &&
      value.state !== "degraded" &&
      value.state !== "unavailable") ||
    typeof value.observed_at !== "string" ||
    value.code !== readiness.code ||
    value.state !== readiness.state ||
    !livenessIsValid ||
    !readinessIsValid ||
    !Array.isArray(value.degraded_capabilities) ||
    !value.degraded_capabilities.every(
      (capability) => capability === "GEMINI_DRAFTING",
    )
  ) {
    throw new Error("invalid health response");
  }
  return {
    service: "causal-delay-copilot",
    state: value.state,
    code: value.code,
    liveness,
    readiness,
    degraded_capabilities: value.degraded_capabilities,
    observed_at: value.observed_at,
  };
}

export function auditOutcomeCode(
  health: HealthResponse,
): AuditOutcomeCode {
  if (
    health.readiness.code !== "CORE_READY" &&
    health.readiness.code !== "CORE_READY_GEMINI_DEGRADED"
  ) {
    throw new Error("health is not ready for an audit occurrence");
  }
  return health.readiness.code;
}

export function parseAuditOccurrenceResponse(
  value: unknown,
): AuditOccurrenceResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY") ||
    typeof value.occurrence_id !== "string" ||
    typeof value.event_seq !== "number" ||
    !Number.isInteger(value.event_seq) ||
    value.event_seq < 1
  ) {
    throw new Error("invalid audit response");
  }
  return {
    result: value.result,
    occurrence_id: value.occurrence_id,
    event_seq: value.event_seq,
  };
}

export function parseDemoWorkspaceResponse(value: unknown): DemoWorkspace {
  if (
    !isRecord(value) ||
    typeof value.workspace_id !== "string" ||
    value.status !== "ACTIVE" ||
    typeof value.created_at !== "string" ||
    typeof value.last_seen_at !== "string" ||
    !isNonNegativeInteger(value.mutation_count) ||
    !isNonNegativeInteger(value.remaining_mutations) ||
    !isNonNegativeInteger(value.terminal_fresh_bundle_count) ||
    !isNonNegativeInteger(value.remaining_terminal_fresh_bundles)
  ) {
    throw new Error("invalid workspace response");
  }
  return {
    workspace_id: value.workspace_id,
    status: "ACTIVE",
    created_at: value.created_at,
    last_seen_at: value.last_seen_at,
    mutation_count: value.mutation_count,
    remaining_mutations: value.remaining_mutations,
    terminal_fresh_bundle_count: value.terminal_fresh_bundle_count,
    remaining_terminal_fresh_bundles: value.remaining_terminal_fresh_bundles,
  };
}

function isOperationState(value: unknown): value is OperationState {
  return (
    value === "QUEUED" ||
    value === "RUNNING" ||
    value === "CANCELLING" ||
    value === "SUCCEEDED" ||
    value === "FAILED" ||
    value === "CANCELLED" ||
    value === "TIMED_OUT" ||
    value === "INTERRUPTED" ||
    value === "REJECTED"
  );
}

function isOperationKind(value: unknown): value is OperationKind {
  return (
    value === "FRESH_ANALYSIS" ||
    value === "FRESH_REPRODUCTION" ||
    value === "BOUNDED_WORK"
  );
}

function nullableString(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== "string") throw new Error("invalid operation response");
  return value;
}

function parseAnalysisRunStatus(value: unknown): AnalysisRunStatus {
  if (
    !isRecord(value) ||
    value.schema_version !== "analysis-run-status.v1" ||
    typeof value.analysis_run_id !== "string" ||
    typeof value.occurrence_id !== "string" ||
    typeof value.operation_id !== "string" ||
    (value.status !== "PENDING" &&
      value.status !== "RUNNING" &&
      value.status !== "ESTIMATED" &&
      value.status !== "ABSTAINED" &&
      value.status !== "FAILED") ||
    (value.lifecycle !== "executing" &&
      value.lifecycle !== "sealed" &&
      value.lifecycle !== "failed" &&
      value.lifecycle !== "quarantined") ||
    (value.scientific_outcome !== "pending" &&
      value.scientific_outcome !== "estimated" &&
      value.scientific_outcome !== "abstained" &&
      value.scientific_outcome !== "failed") ||
    (value.verification_state !== "pending" &&
      value.verification_state !== "machine_verified" &&
      value.verification_state !== "reference_validated" &&
      value.verification_state !== "invalid") ||
    (value.availability_state !== "available" &&
      value.availability_state !== "suppressed") ||
    (value.delivery_mode !== "fresh_execution" &&
      value.delivery_mode !== "existing_run_reuse") ||
    (value.run_relationship !== undefined &&
      value.run_relationship !== "fresh" &&
      value.run_relationship !== "reproduction" &&
      value.run_relationship !== "refresh") ||
    (value.reproduces_run_id !== undefined &&
      value.reproduces_run_id !== null &&
      typeof value.reproduces_run_id !== "string") ||
    (value.refresh_of_request_id !== undefined &&
      value.refresh_of_request_id !== null &&
      typeof value.refresh_of_request_id !== "string") ||
    (value.reason_code !== null && typeof value.reason_code !== "string") ||
    (value.failure_code !== null && typeof value.failure_code !== "string") ||
    (value.recovery_action !== null && typeof value.recovery_action !== "string") ||
    typeof value.estimator_executed !== "boolean" ||
    value.request_schema_version !== "causal-engine-suite-request.v2" ||
    typeof value.scientific_request_digest !== "string" ||
    !isRecord(value.runtime_fingerprint) ||
    typeof value.runtime_fingerprint_digest !== "string" ||
    !isNonNegativeInteger(value.root_seed) ||
    !Array.isArray(value.derived_seed_registry) ||
    !value.derived_seed_registry.every(isRecord) ||
    !isRecord(value.estimator_descriptor) ||
    !isRecord(value.feature_descriptor) ||
    !isRecord(value.fold_descriptor) ||
    (value.fresh_run_detail !== undefined &&
      value.fresh_run_detail !== null &&
      !isRecord(value.fresh_run_detail)) ||
    (value.primary_result !== undefined &&
      value.primary_result !== null &&
      !isRecord(value.primary_result)) ||
    (value.bundle_manifest_hash !== undefined &&
      value.bundle_manifest_hash !== null &&
      typeof value.bundle_manifest_hash !== "string") ||
    (value.reproduction_comparison !== undefined &&
      value.reproduction_comparison !== null &&
      !isRecord(value.reproduction_comparison))
  ) {
    throw new Error("invalid analysis run response");
  }
  const diagnostics =
    value.diagnostics === undefined
      ? []
      : !Array.isArray(value.diagnostics)
        ? (() => {
            throw new Error("invalid analysis run response");
          })()
        : value.diagnostics.map(parseDiagnosticRecord);
  const diagnosticSummary =
    value.diagnostic_summary === undefined || value.diagnostic_summary === null
      ? null
      : parseDiagnosticSummary(value.diagnostic_summary);
  const robustnessGrade =
    value.robustness_grade === undefined || value.robustness_grade === null
      ? null
      : parseRobustnessGrade(value.robustness_grade);
  const evidenceVerdict =
    value.evidence_verdict === undefined || value.evidence_verdict === null
      ? null
      : parseEvidenceVerdict(value.evidence_verdict);
  const renderedVerdict =
    value.rendered_verdict === undefined || value.rendered_verdict === null
      ? null
      : parseRenderedEvidenceVerdict(value.rendered_verdict);
  const subjectVerdict =
    value.subject_verdict === undefined || value.subject_verdict === null
      ? null
      : parseEvidenceVerdict(value.subject_verdict);
  const renderedSubjectVerdict =
    value.rendered_subject_verdict === undefined || value.rendered_subject_verdict === null
      ? null
      : parseRenderedEvidenceVerdict(value.rendered_subject_verdict);
  return {
    schema_version: "analysis-run-status.v1",
    analysis_run_id: value.analysis_run_id,
    occurrence_id: value.occurrence_id,
    operation_id: value.operation_id,
    status: value.status,
    lifecycle: value.lifecycle,
    scientific_outcome: value.scientific_outcome,
    verification_state: value.verification_state,
    availability_state: value.availability_state,
    delivery_mode: value.delivery_mode,
    run_relationship:
      value.run_relationship === undefined ? "fresh" : value.run_relationship,
    reproduces_run_id:
      value.reproduces_run_id === undefined
        ? null
        : nullableString(value.reproduces_run_id),
    refresh_of_request_id:
      value.refresh_of_request_id === undefined
        ? null
        : nullableString(value.refresh_of_request_id),
    reason_code: nullableString(value.reason_code),
    failure_code: nullableString(value.failure_code),
    recovery_action: nullableString(value.recovery_action),
    estimator_executed: value.estimator_executed,
    request_schema_version: "causal-engine-suite-request.v2",
    scientific_request_digest: value.scientific_request_digest,
    runtime_fingerprint: value.runtime_fingerprint,
    runtime_fingerprint_digest: value.runtime_fingerprint_digest,
    root_seed: value.root_seed,
    derived_seed_registry: value.derived_seed_registry,
    estimator_descriptor: value.estimator_descriptor,
    feature_descriptor: value.feature_descriptor,
    fold_descriptor: value.fold_descriptor,
    fresh_run_detail:
      value.fresh_run_detail === undefined || value.fresh_run_detail === null
        ? null
        : value.fresh_run_detail,
    primary_result:
      value.primary_result === undefined || value.primary_result === null
        ? null
        : value.primary_result,
    bundle_manifest_hash:
      value.bundle_manifest_hash === undefined || value.bundle_manifest_hash === null
        ? null
        : value.bundle_manifest_hash,
    diagnostics,
    diagnostic_summary: diagnosticSummary,
    robustness_grade: robustnessGrade,
    evidence_verdict: evidenceVerdict,
    rendered_verdict: renderedVerdict,
    subject_verdict: subjectVerdict,
    rendered_subject_verdict: renderedSubjectVerdict,
    reproduction_comparison:
      value.reproduction_comparison === undefined ||
      value.reproduction_comparison === null
        ? null
        : value.reproduction_comparison,
  };
}

export function parseOperationResponse(value: unknown): DurableOperation {
  if (
    !isRecord(value) ||
    value.schema_version !== "durable-operation.v1" ||
    typeof value.operation_id !== "string" ||
    !isOperationKind(value.operation_kind) ||
    !isOperationState(value.state) ||
    value.status !== value.state ||
    (value.queue_position !== null &&
      (!isNonNegativeInteger(value.queue_position) || value.queue_position < 1)) ||
    typeof value.created_at !== "string" ||
    typeof value.queued_at !== "string" ||
    (value.started_at !== null && typeof value.started_at !== "string") ||
    (value.finished_at !== null && typeof value.finished_at !== "string") ||
    (value.cancel_requested_at !== null &&
      typeof value.cancel_requested_at !== "string") ||
    (value.retry_of_operation_id !== null &&
      typeof value.retry_of_operation_id !== "string") ||
    (value.failure_code !== null && typeof value.failure_code !== "string") ||
    (value.recovery_action !== null && typeof value.recovery_action !== "string") ||
    !Array.isArray(value.resource_warnings) ||
    !value.resource_warnings.every((warning) => warning === "DISK_SPACE_LOW") ||
    (value.artifact_state !== "NOT_STARTED" &&
      value.artifact_state !== "EXECUTING" &&
      value.artifact_state !== "PUBLISHED" &&
      value.artifact_state !== "QUARANTINED" &&
      value.artifact_state !== "QUARANTINE_UNAVAILABLE") ||
    typeof value.retryable !== "boolean" ||
    typeof value.timeout_seconds !== "number" ||
    value.timeout_seconds <= 0 ||
    value.timeout_seconds > 300 ||
    !isNonNegativeInteger(value.thread_cap) ||
    value.thread_cap < 1 ||
    !isNonNegativeInteger(value.memory_required_bytes) ||
    value.memory_required_bytes < 1 ||
    !isNonNegativeInteger(value.memory_available_bytes) ||
    !isNonNegativeInteger(value.disk_free_bytes)
  ) {
    throw new Error("invalid operation response");
  }
  const parsedState = value.state;
  if (!isOperationState(parsedState)) {
    throw new Error("invalid operation response");
  }
  const analysisRun =
    value.analysis_run === undefined || value.analysis_run === null
      ? null
      : parseAnalysisRunStatus(value.analysis_run);
  return {
    schema_version: "durable-operation.v1",
    operation_id: value.operation_id,
    operation_kind: value.operation_kind,
    state: parsedState,
    status: parsedState,
    queue_position: value.queue_position,
    created_at: value.created_at,
    queued_at: value.queued_at,
    started_at: nullableString(value.started_at),
    finished_at: nullableString(value.finished_at),
    cancel_requested_at: nullableString(value.cancel_requested_at),
    retry_of_operation_id: nullableString(value.retry_of_operation_id),
    failure_code: nullableString(value.failure_code),
    recovery_action: nullableString(value.recovery_action),
    resource_warnings: value.resource_warnings,
    artifact_state: value.artifact_state,
    retryable: value.retryable,
    timeout_seconds: value.timeout_seconds,
    thread_cap: value.thread_cap,
    memory_required_bytes: value.memory_required_bytes,
    memory_available_bytes: value.memory_available_bytes,
    disk_free_bytes: value.disk_free_bytes,
    analysis_run: analysisRun,
  };
}

export function parseOperationMutationResponse(
  value: unknown,
): OperationMutationResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY") ||
    !isRecord(value.operation)
  ) {
    throw new Error("invalid operation response");
  }
  return {
    result: value.result,
    operation: parseOperationResponse(value.operation),
  };
}

function parseDecisionSupportReason(value: unknown): DecisionSupportSuppressionReason {
  if (
    !isRecord(value) ||
    typeof value.code !== "string" ||
    typeof value.category !== "string" ||
    !isNonNegativeInteger(value.priority) ||
    typeof value.reason !== "string"
  ) {
    throw new Error("invalid Decision Support suppression reason");
  }
  return {
    ...value,
    code: value.code,
    category: value.category,
    priority: value.priority,
    reason: value.reason,
  };
}

function parseDecisionSupportReasons(value: unknown): DecisionSupportSuppressionReason[] {
  if (!Array.isArray(value)) {
    throw new Error("invalid Decision Support suppression reasons");
  }
  return value.map(parseDecisionSupportReason);
}

function parseDecisionSupportTags(value: unknown): DecisionSupportEvidenceTags {
  if (
    !isRecord(value) ||
    typeof value.DRIVER_EVIDENCE !== "string" ||
    typeof value.MECHANISTIC_LINK !== "string" ||
    typeof value.RULE_BASED_ELIGIBILITY !== "string" ||
    typeof value.ASSUMPTION_BASED_BENEFIT !== "string"
  ) {
    throw new Error("invalid Decision Support evidence tags");
  }
  return {
    DRIVER_EVIDENCE: value.DRIVER_EVIDENCE,
    MECHANISTIC_LINK: value.MECHANISTIC_LINK,
    RULE_BASED_ELIGIBILITY: value.RULE_BASED_ELIGIBILITY,
    ASSUMPTION_BASED_BENEFIT: value.ASSUMPTION_BASED_BENEFIT,
  };
}

function parseDecisionSupportBoundary(value: unknown): DecisionSupportBoundary {
  if (!isRecord(value)) {
    throw new Error("invalid Decision Support boundary");
  }
  if (
    value.schema_version !== "decision-support-boundary.v1" ||
    (value.outcome !== "FAILED" &&
      value.outcome !== "NOT_PERMITTED" &&
      value.outcome !== "NO_ELIGIBLE_OPTION" &&
      value.outcome !== "TRADEOFF_REQUIRES_MANAGER_CHOICE" &&
      value.outcome !== "RECOMMENDATION_AVAILABLE") ||
    (value.state !== "not_permitted" &&
      value.state !== "inactive_driver" &&
      value.state !== "approval_dependent_suppressed" &&
      value.state !== "constraints_evaluated" &&
      value.state !== "comparison_evaluated" &&
      value.state !== "tradeoff_requires_choice" &&
      value.state !== "recommendation_available" &&
      value.state !== "unavailable") ||
    (value.primary_reason_code !== null && typeof value.primary_reason_code !== "string") ||
    (value.reason !== null && typeof value.reason !== "string") ||
    (value.next_step !== null && typeof value.next_step !== "string") ||
    !isRecord(value.permission) ||
    typeof value.permission.decision_support_evaluation_permitted !== "boolean" ||
    (value.permission.denial_reason_code !== null &&
      typeof value.permission.denial_reason_code !== "string") ||
    typeof value.permission.reason !== "string" ||
    typeof value.permission.next_step !== "string" ||
    (value.subject_driver_state !== null && !isRecord(value.subject_driver_state)) ||
    (value.decision_support_evaluation_id !== null &&
      typeof value.decision_support_evaluation_id !== "string") ||
    (value.evaluation_lifecycle !== undefined &&
      !isRecord(value.evaluation_lifecycle)) ||
    !Array.isArray(value.options) ||
    typeof value.action_effect_evidence !== "string" ||
    (value.action_recommendation !== null && !isRecord(value.action_recommendation)) ||
    (value.tradeoff !== null && !isRecord(value.tradeoff)) ||
    !isRecord(value.monitoring) ||
    !isRecord(value.drafting) ||
    !isRecord(value.authorization) ||
    !Array.isArray(value.consumed_inputs) ||
    !value.consumed_inputs.every((item) => typeof item === "string")
  ) {
    throw new Error("invalid Decision Support boundary");
  }
  const options = value.options.map((item) => {
    if (
      !isRecord(item) ||
      typeof item.option_code !== "string" ||
      typeof item.option_version !== "string" ||
      typeof item.label !== "string" ||
      typeof item.evaluation_state !== "string" ||
      typeof item.action_effect_evidence !== "string" ||
      (item.constraint_results !== undefined &&
        (!Array.isArray(item.constraint_results) ||
          !item.constraint_results.every(isRecord))) ||
      (item.provenance !== undefined && !isRecord(item.provenance))
    ) {
      throw new Error("invalid Decision Support option");
    }
    return {
      ...item,
      option_code: item.option_code,
      option_version: item.option_version,
      label: item.label,
      evaluation_state: item.evaluation_state,
      evidence_tags: parseDecisionSupportTags(item.evidence_tags),
      action_effect_evidence: item.action_effect_evidence,
      suppression_reasons: parseDecisionSupportReasons(item.suppression_reasons),
    };
  });
  return {
    ...value,
    schema_version: "decision-support-boundary.v1",
    outcome: value.outcome,
    state: value.state,
    primary_reason_code: value.primary_reason_code as string | null,
    reason: value.reason as string | null,
    next_step: value.next_step as string | null,
    permission: {
      decision_support_evaluation_permitted:
        value.permission.decision_support_evaluation_permitted,
      denial_reason_code: value.permission.denial_reason_code as string | null,
      reason: value.permission.reason,
      next_step: value.permission.next_step,
    },
    subject_driver_state:
      value.subject_driver_state === null ? null : value.subject_driver_state,
    decision_support_evaluation_id:
      value.decision_support_evaluation_id === null
        ? null
        : (value.decision_support_evaluation_id as string),
    evaluation_lifecycle:
      value.evaluation_lifecycle === undefined
        ? undefined
        : value.evaluation_lifecycle,
    options,
    evidence_tags: parseDecisionSupportTags(value.evidence_tags),
    suppression_reasons: parseDecisionSupportReasons(value.suppression_reasons),
    action_effect_evidence: value.action_effect_evidence,
    action_recommendation:
      value.action_recommendation === null ? null : value.action_recommendation,
    tradeoff: value.tradeoff === null ? null : value.tradeoff,
    monitoring: value.monitoring,
    drafting: value.drafting,
    authorization: value.authorization,
    consumed_inputs: value.consumed_inputs,
  };
}

function parseDecisionSupportRegistry(
  value: unknown,
): DecisionSupportRegistryInspection {
  if (
    !isRecord(value) ||
    value.inspection_kind !== "GOVERNED_RECORD_INSPECTION" ||
    value.effect_bearing !== false ||
    value.consumed_by_evaluation !== false ||
    !isRecord(value.release_binding) ||
    (value.release_binding.state !== "BUNDLED_RELEASE_BOUND" &&
      value.release_binding.state !== "RELEASE_BINDING_UNAVAILABLE" &&
      value.release_binding.state !== "TEST_ONLY_NOT_SHIPPED") ||
    (value.release_binding.release_candidate_id !== null &&
      typeof value.release_binding.release_candidate_id !== "string") ||
    (value.release_binding.runtime_fingerprint_digest !== null &&
      typeof value.release_binding.runtime_fingerprint_digest !== "string")
  ) {
    throw new Error("invalid Decision Support registry inspection");
  }
  return {
    ...value,
    inspection_kind: "GOVERNED_RECORD_INSPECTION",
    effect_bearing: false,
    consumed_by_evaluation: false,
    release_binding: {
      state: value.release_binding.state,
      release_candidate_id: value.release_binding.release_candidate_id as string | null,
      runtime_fingerprint_digest:
        value.release_binding.runtime_fingerprint_digest as string | null,
    },
  };
}

function parseDecisionBriefSnapshot(value: unknown): DecisionBriefSnapshot {
  if (
    !isRecord(value) ||
    value.schema_version !== "decision-brief-snapshot.v2" ||
    typeof value.snapshot_id !== "string" ||
    typeof value.investigation_request_id !== "string" ||
    typeof value.reference_id !== "string" ||
    typeof value.content_hash !== "string" ||
    typeof value.occurrence_id !== "string" ||
    !isNonNegativeInteger(value.event_seq) ||
    value.event_seq < 1 ||
    typeof value.created_at !== "string" ||
    !isRecord(value.subject_applicability) ||
    (value.subject_applicability.state !== "applicable" &&
      value.subject_applicability.state !== "population_limited" &&
      value.subject_applicability.state !== "abstained" &&
      value.subject_applicability.state !== "unavailable") ||
    (value.subject_verdict !== null && !isRecord(value.subject_verdict)) ||
    (value.rendered_subject_verdict !== null &&
      (!isRecord(value.rendered_subject_verdict) ||
        !Object.values(value.rendered_subject_verdict).every(
          (item) => typeof item === "string",
        ))) ||
    !isRecord(value.action_lane) ||
    (value.action_lane.state !== "read_only" &&
      value.action_lane.state !== "unavailable") ||
    !isRecord(value.investigation_request) ||
    !isRecord(value.ingress_attempt) ||
    !isRecord(value.lineage) ||
    !isRecord(value.reference) ||
    !isRecord(value.referenced_records)
  ) {
    throw new Error("invalid decision brief response");
  }
  const decisionSupport =
    value.decision_support === undefined || value.decision_support === null
      ? null
      : parseDecisionSupportBoundary(value.decision_support);
  const decisionSupportRegistry =
    value.decision_support_registry === undefined ||
    value.decision_support_registry === null
      ? null
      : parseDecisionSupportRegistry(value.decision_support_registry);
  return {
    schema_version: "decision-brief-snapshot.v2",
    snapshot_id: value.snapshot_id,
    investigation_request_id: value.investigation_request_id,
    reference_id: value.reference_id,
    content_hash: value.content_hash,
    occurrence_id: value.occurrence_id,
    event_seq: value.event_seq,
    created_at: value.created_at,
    subject_applicability: value.subject_applicability as DecisionBriefSnapshot["subject_applicability"],
    subject_verdict:
      value.subject_verdict === null
        ? null
        : (value.subject_verdict as Record<string, unknown>),
    rendered_subject_verdict:
      value.rendered_subject_verdict === null
        ? null
        : (value.rendered_subject_verdict as Record<string, string>),
    action_lane: value.action_lane as DecisionBriefSnapshot["action_lane"],
    decision_support: decisionSupport,
    decision_support_registry: decisionSupportRegistry,
    investigation_request: value.investigation_request,
    ingress_attempt: value.ingress_attempt,
    lineage: value.lineage,
    reference: value.reference,
    referenced_records: value.referenced_records,
  };
}

export function parseDecisionBriefResponse(value: unknown): DecisionBriefResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY")
  ) {
    throw new Error("invalid decision brief response");
  }
  return {
    result: value.result,
    snapshot: parseDecisionBriefSnapshot(value.snapshot),
  };
}

export function parseReplayResponse(value: unknown): ReplayResponse {
  if (
    !isRecord(value) ||
    value.schema_version !== "replay.v1" ||
    (value.status !== "REPLAYED" && value.status !== "REPLAY_UNAVAILABLE") ||
    typeof value.investigation_request_id !== "string" ||
    !isNonNegativeInteger(value.requested_event_seq) ||
    value.requested_event_seq < 1 ||
    !isNonNegativeInteger(value.last_verified_event_seq) ||
    (value.snapshot !== null && !isRecord(value.snapshot)) ||
    !Array.isArray(value.unresolved_references) ||
    !value.unresolved_references.every((item) => typeof item === "string") ||
    typeof value.recovery_action !== "string"
  ) {
    throw new Error("invalid replay response");
  }
  return {
    schema_version: "replay.v1",
    status: value.status,
    investigation_request_id: value.investigation_request_id,
    requested_event_seq: value.requested_event_seq,
    last_verified_event_seq: value.last_verified_event_seq,
    snapshot:
      value.snapshot === null ? null : parseDecisionBriefSnapshot(value.snapshot),
    unresolved_references: value.unresolved_references,
    recovery_action: value.recovery_action,
  };
}

function parseDiagnosticRecord(value: unknown): DiagnosticResult {
  if (!isRecord(value) || Array.isArray(value)) {
    throw new Error("invalid diagnostic response");
  }
  const status = value.status;
  if (
    status !== "PASS" &&
    status !== "FAIL" &&
    status !== "UNSUPPORTED" &&
    status !== "UNAVAILABLE" &&
    status !== "FAILED" &&
    status !== "NOT_RUN"
  ) {
    throw new Error("invalid diagnostic response");
  }
  const verdictEffect = value.verdict_effect;
  if (
    verdictEffect !== "NONE" &&
    verdictEffect !== "FRAGILITY" &&
    verdictEffect !== "VETO" &&
    verdictEffect !== "INSUFFICIENT"
  ) {
    throw new Error("invalid diagnostic response");
  }
  const nullableRecord = (candidate: unknown): Record<string, unknown> | null => {
    if (candidate === null) {
      return null;
    }
    if (!isRecord(candidate) || Array.isArray(candidate)) {
      throw new Error("invalid diagnostic response");
    }
    return candidate;
  };
  if (
    value.schema_version !== "diagnostic-result.v1" ||
    typeof value.diagnostic_id !== "string" ||
    typeof value.diagnostic_version !== "string" ||
    typeof value.scope !== "string" ||
    typeof value.policy_id !== "string" ||
    typeof value.policy_version !== "string" ||
    typeof value.rule_id !== "string" ||
    typeof value.rule_version !== "string" ||
    !isRecord(value.threshold) ||
    Array.isArray(value.threshold) ||
    typeof value.reason_code !== "string" ||
    typeof value.reason !== "string" ||
    (value.analysis_run_id !== null && typeof value.analysis_run_id !== "string") ||
    (value.bundle_manifest_hash !== null && typeof value.bundle_manifest_hash !== "string") ||
    !Array.isArray(value.trigger_codes) ||
    !value.trigger_codes.every((item) => typeof item === "string") ||
    !Array.isArray(value.evidence_refs) ||
    !value.evidence_refs.every((item) => typeof item === "string") ||
    !Array.isArray(value.input_refs) ||
    !value.input_refs.every((item) => typeof item === "string") ||
    typeof value.diagnostic_identity !== "string" ||
    typeof value.content_hash !== "string" ||
    (value.upstream_trigger !== undefined && typeof value.upstream_trigger !== "string")
  ) {
    throw new Error("invalid diagnostic response");
  }
  const upstreamTrigger = value.upstream_trigger;
  return {
    schema_version: "diagnostic-result.v1",
    diagnostic_id: value.diagnostic_id,
    diagnostic_version: value.diagnostic_version,
    scope: value.scope,
    status,
    policy_id: value.policy_id,
    policy_version: value.policy_version,
    rule_id: value.rule_id,
    rule_version: value.rule_version,
    observed: nullableRecord(value.observed),
    threshold: value.threshold,
    result: nullableRecord(value.result),
    verdict_effect: verdictEffect,
    trigger_codes: value.trigger_codes,
    reason_code: value.reason_code,
    reason: value.reason,
    analysis_run_id: value.analysis_run_id,
    bundle_manifest_hash: value.bundle_manifest_hash,
    evidence_refs: value.evidence_refs,
    input_refs: value.input_refs,
    diagnostic_identity: value.diagnostic_identity,
    content_hash: value.content_hash,
    ...(upstreamTrigger === undefined ? {} : { upstream_trigger: upstreamTrigger }),
  };
}

function parseDiagnosticSummary(value: unknown): DiagnosticSummary {
  if (!isRecord(value) || Array.isArray(value)) {
    throw new Error("invalid diagnostic response");
  }
  if (
    (value.state !== "complete" &&
      value.state !== "limited" &&
      value.state !== "attention_required") ||
    !isNonNegativeInteger(value.diagnostic_count) ||
    !isRecord(value.status_counts) ||
    Array.isArray(value.status_counts) ||
    !Object.values(value.status_counts).every(isNonNegativeInteger)
  ) {
    throw new Error("invalid diagnostic response");
  }
  return {
    state: value.state,
    diagnostic_count: value.diagnostic_count,
    status_counts: value.status_counts as Record<string, number>,
  };
}

function parseRobustnessGrade(value: unknown): RobustnessGrade {
  if (
    !isRecord(value) ||
    value.schema_version !== "robustness-grade.v1" ||
    (value.grade !== "STRONG" &&
      value.grade !== "MODERATE" &&
      value.grade !== "WEAK" &&
      value.grade !== "UNAVAILABLE") ||
    !Array.isArray(value.benchmark_group_refs) ||
    !value.benchmark_group_refs.every((item) => typeof item === "string") ||
    (value.strongest_group_ref !== null && typeof value.strongest_group_ref !== "string") ||
    (value.median_group_ref !== null && typeof value.median_group_ref !== "string") ||
    (value.strongest_adjusted_ci_lower !== null &&
      typeof value.strongest_adjusted_ci_lower !== "number") ||
    (value.median_adjusted_ci_lower !== null &&
      typeof value.median_adjusted_ci_lower !== "number") ||
    typeof value.content_hash !== "string"
  ) {
    throw new Error("invalid robustness grade response");
  }
  return {
    schema_version: "robustness-grade.v1",
    grade: value.grade,
    benchmark_group_refs: value.benchmark_group_refs,
    strongest_group_ref: value.strongest_group_ref,
    median_group_ref: value.median_group_ref,
    strongest_adjusted_ci_lower: value.strongest_adjusted_ci_lower,
    median_adjusted_ci_lower: value.median_adjusted_ci_lower,
    content_hash: value.content_hash,
  };
}

function parseEvidenceVerdict(value: unknown): EvidenceVerdict {
  if (
    !isRecord(value) ||
    value.schema_version !== "evidence-verdict.v2" ||
    (value.scope !== "population" && value.scope !== "subject") ||
    (value.verdict_code !== "SUPPORTED_UNDER_ASSUMPTIONS" &&
      value.verdict_code !== "TENTATIVE" &&
      value.verdict_code !== "ASSOCIATION_ONLY" &&
      value.verdict_code !== "INSUFFICIENT") ||
    (value.insufficient_evidence_reason_class !== null &&
      value.insufficient_evidence_reason_class !== "NOT_ESTIMABLE" &&
      value.insufficient_evidence_reason_class !== "INCONCLUSIVE") ||
    typeof value.intended_role !== "string" ||
    typeof value.permitted_claim_scope !== "string" ||
    typeof value.subject_application_role_permitted !== "boolean" ||
    typeof value.decision_support_role_permitted !== "boolean" ||
    typeof value.decision_support_evaluation_permitted !== "boolean" ||
    (value.population_verdict_ref !== null && typeof value.population_verdict_ref !== "string") ||
    (value.robustness_grade_ref !== null && typeof value.robustness_grade_ref !== "string") ||
    (value.effect_display !== "NONE" &&
      value.effect_display !== "INCONCLUSIVE_ESTIMATE" &&
      value.effect_display !== "ADJUSTED_ASSOCIATION" &&
      value.effect_display !== "CAUSAL_ESTIMATE") ||
    (value.effect_result_ref !== null && typeof value.effect_result_ref !== "string") ||
    (value.canonical_unit !== null && typeof value.canonical_unit !== "string") ||
    (value.canonical_slippage_duration_basis !== null &&
      value.canonical_slippage_duration_basis !== "CALENDAR_DAY" &&
      value.canonical_slippage_duration_basis !== "ELAPSED_86400_SECOND_DAY") ||
    (value.effect !== null && (!isRecord(value.effect) || Array.isArray(value.effect))) ||
    typeof value.primary_trigger_code !== "string" ||
    !Array.isArray(value.trigger_codes) ||
    !value.trigger_codes.every((item) => typeof item === "string") ||
    typeof value.next_step_template_id !== "string" ||
    !Array.isArray(value.next_step_template_ids) ||
    !value.next_step_template_ids.every((item) => typeof item === "string") ||
    typeof value.language_policy_id !== "string" ||
    typeof value.content_hash !== "string"
  ) {
    throw new Error("invalid evidence verdict response");
  }
  return {
    schema_version: "evidence-verdict.v2",
    scope: value.scope,
    verdict_code: value.verdict_code,
    insufficient_evidence_reason_class: value.insufficient_evidence_reason_class,
    intended_role: value.intended_role,
    permitted_claim_scope: value.permitted_claim_scope,
    subject_application_role_permitted: value.subject_application_role_permitted,
    decision_support_role_permitted: value.decision_support_role_permitted,
    decision_support_evaluation_permitted: value.decision_support_evaluation_permitted,
    population_verdict_ref: value.population_verdict_ref,
    robustness_grade_ref: value.robustness_grade_ref,
    effect_display: value.effect_display,
    effect_result_ref: value.effect_result_ref,
    canonical_unit: value.canonical_unit,
    canonical_slippage_duration_basis: value.canonical_slippage_duration_basis,
    effect: value.effect,
    primary_trigger_code: value.primary_trigger_code,
    trigger_codes: value.trigger_codes,
    next_step_template_id: value.next_step_template_id,
    next_step_template_ids: value.next_step_template_ids,
    language_policy_id: value.language_policy_id,
    content_hash: value.content_hash,
  };
}

function parseRenderedEvidenceVerdict(value: unknown): RenderedEvidenceVerdict {
  if (
    !isRecord(value) ||
    typeof value.language !== "string" ||
    typeof value.next_step !== "string" ||
    typeof value.primary_trigger_label !== "string" ||
    typeof value.next_step_template_id !== "string"
  ) {
    throw new Error("invalid rendered verdict response");
  }
  return {
    language: value.language,
    next_step: value.next_step,
    primary_trigger_label: value.primary_trigger_label,
    next_step_template_id: value.next_step_template_id,
  };
}

export function parseValidatedReferenceDelivery(
  value: unknown,
): ValidatedReferenceDelivery {
  if (
    !isRecord(value) ||
    value.schema_version !== "analysis-run-read-model.v1" ||
    value.delivery_mode !== "existing_run_reuse" ||
    value.delivery_badge !== "Validated reference" ||
    value.verification_state !== "reference_validated" ||
    typeof value.reference_slot_id !== "string" ||
    typeof value.reference_id !== "string" ||
    typeof value.analysis_run_id !== "string" ||
    typeof value.bundle_manifest_hash !== "string" ||
    typeof value.bundle_ref !== "string" ||
    typeof value.validation_attestation_id !== "string" ||
    typeof value.validation_attestation_ref !== "string" ||
    typeof value.release_candidate_id !== "string" ||
    typeof value.intended_role !== "string" ||
    (value.engine_result_status !== "estimated" &&
      value.engine_result_status !== "abstained") ||
    typeof value.scientific_request_digest !== "string" ||
    typeof value.dataset_version_id !== "string" ||
    typeof value.runtime_fingerprint_digest !== "string" ||
    typeof value.validation_policy_version !== "string" ||
    typeof value.validated_at !== "string"
  ) {
    throw new Error("invalid validated reference response");
  }
  const diagnostics =
    value.diagnostics === undefined
      ? []
      : !Array.isArray(value.diagnostics)
        ? (() => {
            throw new Error("invalid validated reference response");
          })()
        : value.diagnostics.map(parseDiagnosticRecord);
  const diagnosticSummary =
    value.diagnostic_summary === undefined
      ? {
          state: "limited" as const,
          diagnostic_count: diagnostics.length,
          status_counts: {},
        }
      : parseDiagnosticSummary(value.diagnostic_summary);
  const robustnessGrade =
    value.robustness_grade === undefined || value.robustness_grade === null
      ? null
      : parseRobustnessGrade(value.robustness_grade);
  const evidenceVerdict =
    value.evidence_verdict === undefined || value.evidence_verdict === null
      ? null
      : parseEvidenceVerdict(value.evidence_verdict);
  const renderedVerdict =
    value.rendered_verdict === undefined || value.rendered_verdict === null
      ? null
      : parseRenderedEvidenceVerdict(value.rendered_verdict);
  return {
    schema_version: "analysis-run-read-model.v1",
    delivery_mode: "existing_run_reuse",
    delivery_badge: "Validated reference",
    verification_state: "reference_validated",
    reference_slot_id: value.reference_slot_id,
    reference_id: value.reference_id,
    analysis_run_id: value.analysis_run_id,
    bundle_manifest_hash: value.bundle_manifest_hash,
    bundle_ref: value.bundle_ref,
    validation_attestation_id: value.validation_attestation_id,
    validation_attestation_ref: value.validation_attestation_ref,
    release_candidate_id: value.release_candidate_id,
    intended_role: value.intended_role,
    engine_result_status: value.engine_result_status,
    scientific_request_digest: value.scientific_request_digest,
    dataset_version_id: value.dataset_version_id,
    runtime_fingerprint_digest: value.runtime_fingerprint_digest,
    validation_policy_version: value.validation_policy_version,
    validated_at: value.validated_at,
    diagnostics,
    diagnostic_summary: diagnosticSummary,
    robustness_grade: robustnessGrade,
    evidence_verdict: evidenceVerdict,
    rendered_verdict: renderedVerdict,
  };
}

function parseRecord(value: unknown): LineageRecord {
  if (!isRecord(value)) {
    throw new Error("invalid lineage response");
  }
  return value;
}

function parseRecordList(value: unknown): LineageRecord[] {
  if (!Array.isArray(value)) {
    throw new Error("invalid lineage response");
  }
  return value.map(parseRecord);
}

function parseNonNegativeInteger(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error("invalid lineage response");
  }
  return value;
}

export function parseIngestionRunResponse(value: unknown): IngestionRunResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY") ||
    typeof value.ingestion_run_id !== "string" ||
    typeof value.dataset_version_id !== "string" ||
    value.status !== "SUCCEEDED"
  ) {
    throw new Error("invalid ingestion response");
  }
  return {
    result: value.result,
    ingestion_run_id: value.ingestion_run_id,
    dataset_version_id: value.dataset_version_id,
    status: "SUCCEEDED",
  };
}

export function parseLineageSnapshot(value: unknown): LineageSnapshot {
  if (!isRecord(value) || !isRecord(value.dataset_version)) {
    throw new Error("invalid lineage response");
  }
  const datasetVersion = value.dataset_version;
  const sourceKind = datasetVersion.source_kind;
  const intendedRole = datasetVersion.intended_role;
  if (
    typeof datasetVersion.dataset_id !== "string" ||
    typeof datasetVersion.dataset_version_id !== "string" ||
    (sourceKind !== "semi_synthetic" && sourceKind !== "olist" && sourceKind !== "scms") ||
    (intendedRole !== "semi_synthetic_hero" &&
      intendedRole !== "out_of_domain_validation" &&
      intendedRole !== "rejection_vignette") ||
    typeof datasetVersion.mapping_manifest_id !== "string" ||
    !isRecord(datasetVersion.record_counts)
  ) {
    throw new Error("invalid lineage response");
  }
  const sourceRoleCeiling = datasetVersion.source_role_ceiling;
  if (
    !isRecord(sourceRoleCeiling) ||
    typeof sourceRoleCeiling.label !== "string" ||
    typeof sourceRoleCeiling.permitted_claim_scope !== "string" ||
    typeof sourceRoleCeiling.subject_application_role_permitted !== "boolean" ||
    typeof sourceRoleCeiling.decision_support_evaluation_permitted !== "boolean"
  ) {
    throw new Error("invalid lineage response");
  }
  const counts = datasetVersion.record_counts;
  if (
    counts.order_lines === undefined ||
    counts.order_line_events === undefined ||
    counts.source_observations === undefined ||
    counts.validation_findings === undefined
  ) {
    throw new Error("invalid lineage response");
  }
  if (!isRecord(value.audit_binding)) {
    throw new Error("invalid lineage response");
  }
  const auditBinding = value.audit_binding;
  const auditSourceRoleCeiling = auditBinding.source_role_ceiling;
  if (
    typeof auditBinding.snapshot_id !== "string" ||
    typeof auditBinding.dataset_version_id !== "string" ||
    typeof auditBinding.occurrence_id !== "string" ||
    typeof auditBinding.event_seq !== "number" ||
    !Number.isInteger(auditBinding.event_seq) ||
    auditBinding.event_seq < 1 ||
    typeof auditBinding.content_hash !== "string" ||
    typeof auditBinding.created_at !== "string" ||
    !isRecord(auditSourceRoleCeiling) ||
    typeof auditSourceRoleCeiling.label !== "string" ||
    typeof auditSourceRoleCeiling.permitted_claim_scope !== "string" ||
    typeof auditSourceRoleCeiling.subject_application_role_permitted !== "boolean" ||
    typeof auditSourceRoleCeiling.decision_support_evaluation_permitted !== "boolean"
  ) {
    throw new Error("invalid lineage response");
  }
  return {
    ingestion_run: parseRecord(value.ingestion_run),
    dataset_version: {
      dataset_id: datasetVersion.dataset_id,
      dataset_version_id: datasetVersion.dataset_version_id,
      source_kind: sourceKind,
      intended_role: intendedRole,
      mapping_manifest_id: datasetVersion.mapping_manifest_id,
      source_role_ceiling: {
        label: sourceRoleCeiling.label,
        permitted_claim_scope: sourceRoleCeiling.permitted_claim_scope,
        subject_application_role_permitted:
          sourceRoleCeiling.subject_application_role_permitted,
        decision_support_evaluation_permitted:
          sourceRoleCeiling.decision_support_evaluation_permitted,
      },
      record_counts: {
        order_lines: parseNonNegativeInteger(counts.order_lines),
        order_line_events: parseNonNegativeInteger(counts.order_line_events),
        source_observations: parseNonNegativeInteger(counts.source_observations),
        validation_findings: parseNonNegativeInteger(counts.validation_findings),
      },
    },
    mapping_manifest: parseRecord(value.mapping_manifest),
    order_lines: parseRecordList(value.order_lines),
    order_line_events: parseRecordList(value.order_line_events),
    source_observations: parseRecordList(value.source_observations),
    validation_findings: parseRecordList(value.validation_findings),
    audit_binding: {
      snapshot_id: auditBinding.snapshot_id,
      dataset_version_id: auditBinding.dataset_version_id,
      occurrence_id: auditBinding.occurrence_id,
      event_seq: auditBinding.event_seq,
      content_hash: auditBinding.content_hash,
      created_at: auditBinding.created_at,
      source_role_ceiling: {
        label: auditSourceRoleCeiling.label,
        permitted_claim_scope: auditSourceRoleCeiling.permitted_claim_scope,
        subject_application_role_permitted:
          auditSourceRoleCeiling.subject_application_role_permitted,
        decision_support_evaluation_permitted:
          auditSourceRoleCeiling.decision_support_evaluation_permitted,
      },
    },
  };
}

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new Error("invalid reactive response");
  }
  return value;
}

function parseRiskSignalFieldValue(value: unknown): RiskSignalFieldValue {
  if (!isRecord(value)) {
    throw new Error("invalid reactive response");
  }
  const state = value.state;
  if (
    state !== "present" &&
    state !== "missing" &&
    state !== "not_applicable" &&
    state !== "invalid" &&
    state !== "unresolved"
  ) {
    throw new Error("invalid reactive response");
  }
  return { state, value: value.value };
}

function parseProactiveSubjectField(value: unknown): ProactiveSubjectField {
  if (!isRecord(value)) {
    throw new Error("invalid proactive response");
  }
  const field = parseRiskSignalFieldValue(value);
  const knownAt =
    value.known_at === undefined
      ? undefined
      : parseSignalTemporal(value.known_at);
  if (value.lineage_ref !== undefined && typeof value.lineage_ref !== "string") {
    throw new Error("invalid proactive response");
  }
  return {
    ...field,
    ...(knownAt === undefined ? {} : { known_at: knownAt }),
    ...(value.lineage_ref === undefined ? {} : { lineage_ref: value.lineage_ref }),
  };
}

function parseSignalTemporal(value: unknown): RiskSignal["generated_at"] {
  if (
    !isRecord(value) ||
    typeof value.value !== "string" ||
    typeof value.precision !== "string" ||
    (value.kind !== "date" &&
      value.kind !== "local_datetime" &&
      value.kind !== "instant") ||
    (value.timezone_status !== "known" &&
      value.timezone_status !== "assumed" &&
      value.timezone_status !== "unknown" &&
      value.timezone_status !== "not_applicable") ||
    (value.source_timezone !== null && typeof value.source_timezone !== "string")
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    value: value.value,
    kind: value.kind,
    precision: value.precision,
    timezone_status: value.timezone_status,
    source_timezone: value.source_timezone,
  };
}

function parseRiskSignal(value: unknown): RiskSignal {
  if (!isRecord(value) || !isRecord(value.source) || !isRecord(value.source_order_line_ref)) {
    throw new Error("invalid reactive response");
  }
  const source = value.source;
  const sourceRef = value.source_order_line_ref;
  if (
    value.schema_version !== "risk-signal.v1" ||
    value.trigger_mode !== "reactive" ||
    source.schema_version !== "trigger-source-envelope.v1" ||
    source.source_system !== "bundled-predictive-stub" ||
    source.data_classification !== "generated" ||
    typeof value.source_signal_id !== "string" ||
    typeof value.source_revision !== "string" ||
    typeof value.scored_dataset_version_ref !== "string" ||
    typeof sourceRef.namespace !== "string" ||
    (typeof sourceRef.key !== "string" &&
      (!Array.isArray(sourceRef.key) ||
        !sourceRef.key.every((item) => typeof item === "string"))) ||
    typeof value.predictor_id !== "string" ||
    typeof value.predictor_version !== "string" ||
    typeof value.feature_contract_version !== "string" ||
    typeof value.target_definition_id !== "string" ||
    (value.target_milestone_kind !== "supplier_completion" &&
      value.target_milestone_kind !== "supplier_handoff") ||
    typeof value.score_semantic !== "string" ||
    typeof value.score_value !== "number" ||
    !Number.isFinite(value.score_value) ||
    typeof value.alert_threshold !== "number" ||
    !Number.isFinite(value.alert_threshold) ||
    typeof value.flagged !== "boolean" ||
    !isRecord(value.generated_at) ||
    !isRecord(value.known_at)
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    schema_version: value.schema_version,
    trigger_mode: value.trigger_mode,
    source: {
      schema_version: source.schema_version,
      source_system: source.source_system,
      data_classification: source.data_classification,
    },
    source_signal_id: value.source_signal_id,
    source_revision: value.source_revision,
    scored_dataset_version_ref: value.scored_dataset_version_ref,
    source_order_line_ref: {
      namespace: sourceRef.namespace,
      key: sourceRef.key,
    },
    predictor_id: value.predictor_id,
    predictor_version: value.predictor_version,
    feature_contract_version: value.feature_contract_version,
    target_definition_id: value.target_definition_id,
    target_milestone_kind: value.target_milestone_kind,
    score_semantic: value.score_semantic,
    score_value: value.score_value,
    alert_threshold: value.alert_threshold,
    flagged: value.flagged,
    generated_at: parseSignalTemporal(value.generated_at),
    known_at: parseSignalTemporal(value.known_at),
    predictor_artifact_ref: parseRiskSignalFieldValue(value.predictor_artifact_ref),
    predictive_attribution_ref: parseRiskSignalFieldValue(
      value.predictive_attribution_ref,
    ),
    prediction_explanation_ref: parseRiskSignalFieldValue(
      value.prediction_explanation_ref,
    ),
    prediction_calibration_ref: parseRiskSignalFieldValue(
      value.prediction_calibration_ref,
    ),
    prediction_ranking_ref: parseRiskSignalFieldValue(
      value.prediction_ranking_ref,
    ),
    prediction_delivery_metadata: parseRiskSignalFieldValue(
      value.prediction_delivery_metadata,
    ),
    advisory_context:
      value.advisory_context === null
        ? null
        : parseRiskSignalFieldValue(value.advisory_context),
  };
}

export function parseRiskSignalListResponse(value: unknown): RiskSignalListResponse {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    throw new Error("invalid reactive response");
  }
  const predictiveStatus = value.predictive_status;
  if (predictiveStatus !== undefined) {
    if (
      !isRecord(predictiveStatus) ||
      (predictiveStatus.state !== "verified" && predictiveStatus.state !== "unavailable") ||
      typeof predictiveStatus.code !== "string" ||
      typeof predictiveStatus.message !== "string" ||
      typeof predictiveStatus.manual_investigation_available !== "boolean"
    ) {
      throw new Error("invalid predictive status");
    }
  }
  return {
    items: value.items.map((item) => {
      if (!isRecord(item) || typeof item.fixture_id !== "string" || typeof item.label !== "string") {
        throw new Error("invalid reactive response");
      }
      return {
        fixture_id: item.fixture_id,
        label: item.label,
        signal: parseRiskSignal(item.signal),
      };
    }),
    predictive_status:
      predictiveStatus === undefined
        ? undefined
        : (predictiveStatus as PredictiveRiskStatus),
  };
}

function parseProactiveProposal(value: unknown): ProactiveProposal {
  if (!isRecord(value) || !isRecord(value.source)) {
    throw new Error("invalid proactive response");
  }
  const source = value.source;
  if (
    value.schema_version !== "proactive-proposal.v1" ||
    value.trigger_mode !== "proactive" ||
    source.schema_version !== "trigger-source-envelope.v1" ||
    typeof source.source_system !== "string" ||
    (source.data_classification !== "generated" &&
      source.data_classification !== "public" &&
      source.data_classification !== "restricted" &&
      source.data_classification !== "confidential") ||
    typeof value.proposal_id !== "string" ||
    typeof value.proposal_revision !== "string" ||
    typeof value.dataset_version_id !== "string" ||
    !isRecord(value.adjustment_inputs) ||
    !isRecord(value.proposed_supplier_ref) ||
    !isRecord(value.target_milestone_kind) ||
    !isRecord(value.proposed_original_promise) ||
    !isRecord(value.decision_at)
  ) {
    throw new Error("invalid proactive response");
  }
  return {
    schema_version: value.schema_version,
    trigger_mode: value.trigger_mode,
    source: {
      schema_version: source.schema_version,
      source_system: source.source_system,
      data_classification: source.data_classification,
    },
    proposal_id: value.proposal_id,
    proposal_revision: value.proposal_revision,
    dataset_version_id: value.dataset_version_id,
    proposed_supplier_ref: parseProactiveSubjectField(value.proposed_supplier_ref),
    target_milestone_kind: parseProactiveSubjectField(value.target_milestone_kind),
    proposed_original_promise: parseProactiveSubjectField(
      value.proposed_original_promise,
    ),
    adjustment_inputs: Object.fromEntries(
      Object.entries(value.adjustment_inputs).map(([key, item]) => [
        key,
        parseProactiveSubjectField(item),
      ]),
    ),
    decision_at: parseProactiveSubjectField(value.decision_at),
  };
}

export function parseProactiveProposalListResponse(
  value: unknown,
): ProactiveProposalListResponse {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    throw new Error("invalid proactive response");
  }
  return {
    items: value.items.map((item) => {
      if (!isRecord(item) || typeof item.fixture_id !== "string" || typeof item.label !== "string") {
        throw new Error("invalid proactive response");
      }
      return {
        fixture_id: item.fixture_id,
        label: item.label,
        proposal: parseProactiveProposal(item.proposal),
      };
    }),
  };
}

function parseCausalTemporalField(value: unknown): CausalTemporalField {
  if (!isRecord(value)) {
    throw new Error("invalid reactive response");
  }
  const state = value.state;
  if (
    state !== "present" &&
    state !== "missing" &&
    state !== "not_applicable" &&
    state !== "invalid" &&
    state !== "unresolved"
  ) {
    throw new Error("invalid reactive response");
  }
  if (state !== "present") {
    return { state };
  }
  if (!isRecord(value.value) || !isRecord(value.value.source_timezone)) {
    throw new Error("invalid reactive response");
  }
  const temporal = value.value;
  if (
    typeof temporal.source_value !== "string" ||
    typeof temporal.normalized_value !== "string" ||
    typeof temporal.precision !== "string" ||
    (temporal.kind !== "date" &&
      temporal.kind !== "local_datetime" &&
      temporal.kind !== "instant") ||
    (temporal.timezone_status !== "known" &&
      temporal.timezone_status !== "assumed" &&
      temporal.timezone_status !== "unknown" &&
      temporal.timezone_status !== "not_applicable")
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    state: "present",
    value: {
      kind: temporal.kind,
      source_value: temporal.source_value,
      normalized_value: temporal.normalized_value,
      precision: temporal.precision,
      timezone_status: temporal.timezone_status,
      source_timezone: parseRiskSignalFieldValue(temporal.source_timezone),
    },
  };
}

function parseSupplierMilestoneOutcome(value: unknown): SupplierMilestoneOutcome {
  if (
    !isRecord(value) ||
    value.schema_version !== "supplier-milestone-slippage.v1" ||
    (value.state !== "present" &&
      value.state !== "unresolved" &&
      value.state !== "not_applicable") ||
    (value.role !== "ESTIMATION_LINE" && value.role !== "SUBJECT_LINE") ||
    (value.canonical_slippage_duration_basis !== "CALENDAR_DAY" &&
      value.canonical_slippage_duration_basis !==
        "ELAPSED_86400_SECOND_DAY") ||
    (value.supplier_milestone_slippage_duration_basis !== undefined &&
      value.supplier_milestone_slippage_duration_basis !== null &&
      value.supplier_milestone_slippage_duration_basis !== "CALENDAR_DAY" &&
      value.supplier_milestone_slippage_duration_basis !==
        "ELAPSED_86400_SECOND_DAY") ||
    (typeof value.supplier_milestone_slippage_days !== "number" &&
      value.supplier_milestone_slippage_days !== null) ||
    (typeof value.supplier_milestone_late !== "boolean" &&
      value.supplier_milestone_late !== null) ||
    (typeof value.outcome_code !== "string" && value.outcome_code !== null) ||
    (typeof value.reason_code !== "string" && value.reason_code !== null) ||
    typeof value.reason !== "string" ||
    !Array.isArray(value.eligibility_codes) ||
    !value.eligibility_codes.every((item) => typeof item === "string") ||
    (value.follow_up !== undefined &&
      value.follow_up !== null &&
      !isRecord(value.follow_up)) ||
    !isRecord(value.provenance) ||
    typeof value.outcome_hash !== "string"
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    schema_version: value.schema_version,
    state: value.state,
    role: value.role,
    canonical_slippage_duration_basis: value.canonical_slippage_duration_basis,
    supplier_milestone_slippage_duration_basis:
      value.supplier_milestone_slippage_duration_basis === null
        ? undefined
        : value.supplier_milestone_slippage_duration_basis,
    frozen_promised_milestone:
      value.frozen_promised_milestone === undefined ||
      value.frozen_promised_milestone === null
        ? undefined
        : parseCausalTemporalField(value.frozen_promised_milestone),
    actual_target_milestone:
      value.actual_target_milestone === undefined ||
      value.actual_target_milestone === null
        ? undefined
        : parseCausalTemporalField(value.actual_target_milestone),
    supplier_milestone_slippage_days: value.supplier_milestone_slippage_days,
    supplier_milestone_late: value.supplier_milestone_late,
    outcome_code: value.outcome_code,
    reason_code: value.reason_code,
    reason: value.reason,
    eligibility_codes: value.eligibility_codes,
    follow_up:
      value.follow_up === null ? undefined : value.follow_up,
    provenance: value.provenance,
    outcome_hash: value.outcome_hash,
  };
}

function parseCausalWindow(value: unknown): CausalWindow {
  if (
    !isRecord(value) ||
    typeof value.selector_version !== "string" ||
    !isRecord(value.bounds) ||
    typeof value.bounds.known_at_lower !== "string" ||
    !isRecord(value.bounds.known_at_upper) ||
    typeof value.selected_identity_hash !== "string" ||
    typeof value.selected_count !== "number" ||
    !Number.isInteger(value.selected_count) ||
    value.selected_count < 0 ||
    !isRecord(value.subject_removal) ||
    typeof value.subject_removal.subject_identity !== "string" ||
    typeof value.subject_removal.removed !== "boolean" ||
    typeof value.subject_removal.post_subject_identity_hash !== "string"
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    selector_version: value.selector_version,
    bounds: {
      known_at_lower: value.bounds.known_at_lower,
      known_at_upper: parseCausalTemporalField(value.bounds.known_at_upper),
    },
    selected_identity_hash: value.selected_identity_hash,
    selected_count: value.selected_count,
    subject_removal: {
      subject_identity: value.subject_removal.subject_identity,
      removed: value.subject_removal.removed,
      post_subject_identity_hash: value.subject_removal.post_subject_identity_hash,
    },
  };
}

function parseCausalEngineInput(value: unknown): CausalEngineInput {
  if (!isRecord(value) || !isRecord(value.subject_analytical_values)) {
    throw new Error("invalid reactive response");
  }
  const subject = value.subject_analytical_values;
  if (
    !isRecord(subject.adjustment_inputs) ||
    !isRecord(subject.original_promise) ||
    typeof subject.subject_exclusion_identity !== "string" ||
    value.causal_input_schema_version !== "causal-input-projection.v2" ||
    typeof value.dataset_version_id !== "string" ||
    !isRecord(value.decision_cutoff) ||
    !isRecord(value.observation_cutoff) ||
    !isRecord(value.target_milestone_kind) ||
    (value.canonical_slippage_duration_basis !== "CALENDAR_DAY" &&
      value.canonical_slippage_duration_basis !== "ELAPSED_86400_SECOND_DAY") ||
    typeof value.causal_question_version !== "string" ||
    typeof value.engine_configuration_ref !== "string" ||
    (value.supplier_load_exposure !== undefined &&
      !isRecord(value.supplier_load_exposure)) ||
    (value.supplier_milestone_outcome !== undefined &&
      !isRecord(value.supplier_milestone_outcome)) ||
    (value.eligibility !== undefined && !isRecord(value.eligibility)) ||
    typeof value.historical_population_digest !== "string" ||
    !Array.isArray(value.analytical_fact_lineage_refs) ||
    !value.analytical_fact_lineage_refs.every((item) => typeof item === "string")
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    causal_input_schema_version: value.causal_input_schema_version,
    dataset_version_id: value.dataset_version_id,
    subject_analytical_values: {
      supplier_id: parseRiskSignalFieldValue(subject.supplier_id),
      original_promise: parseCausalTemporalField(subject.original_promise),
      adjustment_inputs: Object.fromEntries(
        Object.entries(subject.adjustment_inputs).map(([key, item]) => [
          key,
          parseRiskSignalFieldValue(item),
        ]),
      ),
      subject_exclusion_identity: subject.subject_exclusion_identity,
    },
    decision_cutoff: parseCausalTemporalField(value.decision_cutoff),
    observation_cutoff: parseCausalTemporalField(value.observation_cutoff),
    target_milestone_kind: parseRiskSignalFieldValue(value.target_milestone_kind),
    canonical_slippage_duration_basis: value.canonical_slippage_duration_basis,
    causal_question_version: value.causal_question_version,
    engine_configuration_ref: value.engine_configuration_ref,
    supplier_load_exposure: value.supplier_load_exposure,
    supplier_milestone_outcome:
      value.supplier_milestone_outcome === undefined
        ? undefined
        : parseSupplierMilestoneOutcome(value.supplier_milestone_outcome),
    eligibility: value.eligibility === undefined ? undefined : value.eligibility,
    estimator_window_ref: parseCausalWindow(value.estimator_window_ref),
    history_lookback_ref: parseCausalWindow(value.history_lookback_ref),
    historical_population_digest: value.historical_population_digest,
    analytical_fact_lineage_refs: value.analytical_fact_lineage_refs,
  };
}

function parseInvestigationIngressReference(
  value: unknown,
): InvestigationRequest["ingress_ref"] {
  if (!isRecord(value) || typeof value.kind !== "string") {
    throw new Error("invalid investigation response");
  }
  if (value.kind === "RiskSignal") {
    if (
      typeof value.source_system !== "string" ||
      typeof value.source_signal_id !== "string" ||
      typeof value.source_revision !== "string" ||
      typeof value.source_payload_sha256 !== "string" ||
      !isRecord(value.source_order_line_ref) ||
      typeof value.source_order_line_ref.namespace !== "string" ||
      (typeof value.source_order_line_ref.key !== "string" &&
        (!Array.isArray(value.source_order_line_ref.key) ||
          !value.source_order_line_ref.key.every(
            (item) => typeof item === "string",
          )))
    ) {
      throw new Error("invalid investigation response");
    }
    return {
      kind: "RiskSignal",
      source_system: value.source_system,
      source_signal_id: value.source_signal_id,
      source_revision: value.source_revision,
      source_payload_sha256: value.source_payload_sha256,
      source_order_line_ref: {
        namespace: value.source_order_line_ref.namespace,
        key: value.source_order_line_ref.key,
      },
    };
  }
  if (
    value.kind !== "ProactiveProposal" ||
    typeof value.source_system !== "string" ||
    typeof value.proposal_id !== "string" ||
    typeof value.proposal_revision !== "string" ||
    typeof value.source_payload_sha256 !== "string"
  ) {
    throw new Error("invalid investigation response");
  }
  return {
    kind: "ProactiveProposal",
    source_system: value.source_system,
    proposal_id: value.proposal_id,
    proposal_revision: value.proposal_revision,
    source_payload_sha256: value.source_payload_sha256,
  };
}

function parseInvestigationSubject(
  value: unknown,
): InvestigationRequest["subject"] {
  if (!isRecord(value)) {
    throw new Error("invalid investigation response");
  }
  if (value.kind === "proactive_preview") {
    if (
      typeof value.preview_subject_digest !== "string" ||
      typeof value.proposal_id !== "string" ||
      typeof value.proposal_revision !== "string" ||
      !isRecord(value.supplier_id) ||
      !isRecord(value.target_milestone_kind) ||
      !isRecord(value.original_promise) ||
      !isRecord(value.adjustment_inputs)
    ) {
      throw new Error("invalid investigation response");
    }
    return {
      kind: "proactive_preview",
      preview_subject_digest: value.preview_subject_digest,
      proposal_id: value.proposal_id,
      proposal_revision: value.proposal_revision,
      supplier_id: parseProactiveSubjectField(value.supplier_id),
      target_milestone_kind: parseProactiveSubjectField(
        value.target_milestone_kind,
      ),
      original_promise: parseProactiveSubjectField(value.original_promise),
      adjustment_inputs: Object.fromEntries(
        Object.entries(value.adjustment_inputs).map(([key, item]) => [
          key,
          parseProactiveSubjectField(item),
        ]),
      ),
    };
  }
  if (typeof value.order_line_id !== "string") {
    throw new Error("invalid investigation response");
  }
  return { order_line_id: value.order_line_id };
}

function parseInvestigationRequest(value: unknown): InvestigationRequest {
  if (
    !isRecord(value) ||
    typeof value.investigation_request_id !== "string" ||
    value.schema_version !== "investigation-request.v1" ||
    (value.trigger_mode !== "reactive" && value.trigger_mode !== "proactive") ||
    !isRecord(value.decision_cutoff) ||
    !isRecord(value.observation_cutoff) ||
    (value.decision_cutoff_source !== "canonical_commitment" &&
      value.decision_cutoff_source !== "proactive_decision") ||
    typeof value.dataset_version_id !== "string" ||
    !isRecord(value.target_milestone_kind) ||
    typeof value.causal_question_version !== "string" ||
    typeof value.engine_configuration_ref !== "string" ||
    !Array.isArray(value.ingress_validation_refs) ||
    !value.ingress_validation_refs.every((item) => typeof item === "string") ||
    !Array.isArray(value.provenance_refs) ||
    !value.provenance_refs.every((item) => typeof item === "string") ||
    typeof value.accepted_at !== "string" ||
    !isRecord(value.causal_engine_input) ||
    typeof value.causal_input_digest !== "string" ||
    typeof value.content_hash !== "string"
  ) {
    throw new Error("invalid investigation response");
  }
  return {
    investigation_request_id: value.investigation_request_id,
    schema_version: value.schema_version,
    trigger_mode: value.trigger_mode,
    ingress_ref: parseInvestigationIngressReference(value.ingress_ref),
    rerun_of_request_id: parseRiskSignalFieldValue(value.rerun_of_request_id),
    dataset_version_id: value.dataset_version_id,
    subject: parseInvestigationSubject(value.subject),
    decision_cutoff: parseCausalTemporalField(value.decision_cutoff),
    decision_cutoff_source: value.decision_cutoff_source,
    observation_cutoff: parseCausalTemporalField(value.observation_cutoff),
    target_milestone_kind: parseRiskSignalFieldValue(value.target_milestone_kind),
    causal_question_version: value.causal_question_version,
    engine_configuration_ref: value.engine_configuration_ref,
    ingress_validation_refs: parseStringArray(value.ingress_validation_refs),
    provenance_refs: parseStringArray(value.provenance_refs),
    prediction_metadata: parseRiskSignalFieldValue(value.prediction_metadata),
    accepted_at: value.accepted_at,
    causal_engine_input: parseCausalEngineInput(value.causal_engine_input),
    causal_input_digest: value.causal_input_digest,
    content_hash: value.content_hash,
  };
}

function parseReactiveIngressAttempt(value: unknown): ReactiveIngressAttempt {
  if (!isRecord(value) || !isRecord(value.audit)) {
    throw new Error("invalid reactive response");
  }
  if (
    typeof value.attempt_id !== "string" ||
    (value.status !== "accepted" &&
      value.status !== "duplicate" &&
      value.status !== "rejected" &&
      value.status !== "accepted_with_warning") ||
    value.scope !== "reactive_ingress" ||
    typeof value.source_system !== "string" ||
    typeof value.source_signal_id !== "string" ||
    typeof value.source_revision !== "string" ||
    typeof value.source_payload_sha256 !== "string" ||
    typeof value.primary_code !== "string" ||
    !Array.isArray(value.findings) ||
    !value.findings.every((finding) => {
      if (!isRecord(finding)) return false;
      return (
        typeof finding.finding_id === "string" &&
        typeof finding.code === "string" &&
        (finding.severity === "info" ||
          finding.severity === "warning" ||
          finding.severity === "error") &&
        (finding.disposition === "advisory" || finding.disposition === "reject") &&
        Array.isArray(finding.affected_refs) &&
        finding.affected_refs.every((item) => typeof item === "string") &&
        typeof finding.message === "string" &&
        typeof finding.remediation === "string"
      );
    }) ||
    !Array.isArray(value.evidence_refs) ||
    !value.evidence_refs.every((item) => typeof item === "string") ||
    typeof value.retryable !== "boolean" ||
    typeof value.recovery_action !== "string" ||
    typeof value.received_at !== "string" ||
    (value.investigation_request_id !== null &&
      typeof value.investigation_request_id !== "string") ||
    (value.investigation_request !== null &&
      !isRecord(value.investigation_request)) ||
    typeof value.audit.occurrence_id !== "string" ||
    typeof value.audit.event_seq !== "number" ||
    !Number.isInteger(value.audit.event_seq) ||
    value.audit.event_seq < 1
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    attempt_id: value.attempt_id,
    status: value.status,
    scope: "reactive_ingress",
    source_system: value.source_system,
    source_signal_id: value.source_signal_id,
    source_revision: value.source_revision,
    source_payload_sha256: value.source_payload_sha256,
    primary_code: value.primary_code,
    findings: value.findings as IngressFinding[],
    evidence_refs: value.evidence_refs,
    retryable: value.retryable,
    recovery_action: value.recovery_action,
    received_at: value.received_at,
    investigation_request_id: value.investigation_request_id,
    investigation_request:
      value.investigation_request === null
        ? null
        : parseInvestigationRequest(value.investigation_request),
    audit: {
      occurrence_id: value.audit.occurrence_id,
      event_seq: value.audit.event_seq,
    },
  };
}

export function parseReactiveInvestigationResponse(
  value: unknown,
): ReactiveInvestigationResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY")
  ) {
    throw new Error("invalid reactive response");
  }
  return {
    result: value.result,
    attempt: parseReactiveIngressAttempt(value.attempt),
  };
}

function parseProactiveIngressAttempt(value: unknown): ProactiveIngressAttempt {
  if (!isRecord(value) || !isRecord(value.audit)) {
    throw new Error("invalid proactive response");
  }
  if (
    typeof value.attempt_id !== "string" ||
    (value.status !== "accepted" &&
      value.status !== "duplicate" &&
      value.status !== "rejected" &&
      value.status !== "accepted_with_warning") ||
    value.scope !== "proactive_ingress" ||
    typeof value.source_system !== "string" ||
    typeof value.proposal_id !== "string" ||
    typeof value.proposal_revision !== "string" ||
    typeof value.source_payload_sha256 !== "string" ||
    typeof value.primary_code !== "string" ||
    !Array.isArray(value.findings) ||
    !value.findings.every((finding) => {
      if (!isRecord(finding)) return false;
      return (
        typeof finding.finding_id === "string" &&
        typeof finding.code === "string" &&
        (finding.severity === "info" ||
          finding.severity === "warning" ||
          finding.severity === "error") &&
        (finding.disposition === "advisory" || finding.disposition === "reject") &&
        Array.isArray(finding.affected_refs) &&
        finding.affected_refs.every((item) => typeof item === "string") &&
        typeof finding.message === "string" &&
        typeof finding.remediation === "string"
      );
    }) ||
    !Array.isArray(value.evidence_refs) ||
    !value.evidence_refs.every((item) => typeof item === "string") ||
    typeof value.retryable !== "boolean" ||
    typeof value.recovery_action !== "string" ||
    typeof value.received_at !== "string" ||
    (value.investigation_request_id !== null &&
      typeof value.investigation_request_id !== "string") ||
    (value.investigation_request !== null &&
      !isRecord(value.investigation_request)) ||
    typeof value.audit.occurrence_id !== "string" ||
    typeof value.audit.event_seq !== "number" ||
    !Number.isInteger(value.audit.event_seq) ||
    value.audit.event_seq < 1
  ) {
    throw new Error("invalid proactive response");
  }
  return {
    attempt_id: value.attempt_id,
    status: value.status,
    scope: "proactive_ingress",
    source_system: value.source_system,
    proposal_id: value.proposal_id,
    proposal_revision: value.proposal_revision,
    source_payload_sha256: value.source_payload_sha256,
    primary_code: value.primary_code,
    findings: value.findings as IngressFinding[],
    evidence_refs: value.evidence_refs,
    retryable: value.retryable,
    recovery_action: value.recovery_action,
    received_at: value.received_at,
    investigation_request_id: value.investigation_request_id,
    investigation_request:
      value.investigation_request === null
        ? null
        : parseInvestigationRequest(value.investigation_request),
    audit: {
      occurrence_id: value.audit.occurrence_id,
      event_seq: value.audit.event_seq,
    },
  };
}

export function parseProactiveInvestigationResponse(
  value: unknown,
): ProactiveInvestigationResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY")
  ) {
    throw new Error("invalid proactive response");
  }
  return {
    result: value.result,
    attempt: parseProactiveIngressAttempt(value.attempt),
  };
}

function parseRefreshInvestigationSnapshot(
  value: unknown,
): RefreshInvestigationSnapshot {
  if (
    !isRecord(value) ||
    value.schema_version !== "refresh-investigation-snapshot.v1" ||
    typeof value.snapshot_id !== "string" ||
    typeof value.predecessor_request_id !== "string" ||
    typeof value.investigation_request_id !== "string" ||
    (value.trigger_mode !== "reactive" && value.trigger_mode !== "proactive") ||
    typeof value.dataset_version_id !== "string" ||
    !isRecord(value.observation_cutoff) ||
    typeof value.causal_input_digest !== "string" ||
    typeof value.content_hash !== "string" ||
    typeof value.occurrence_id !== "string" ||
    !isNonNegativeInteger(value.event_seq) ||
    value.event_seq < 1 ||
    typeof value.created_at !== "string"
  ) {
    throw new Error("invalid refresh response");
  }
  return {
    schema_version: "refresh-investigation-snapshot.v1",
    snapshot_id: value.snapshot_id,
    predecessor_request_id: value.predecessor_request_id,
    investigation_request_id: value.investigation_request_id,
    trigger_mode: value.trigger_mode,
    dataset_version_id: value.dataset_version_id,
    observation_cutoff: value.observation_cutoff,
    causal_input_digest: value.causal_input_digest,
    content_hash: value.content_hash,
    occurrence_id: value.occurrence_id,
    event_seq: value.event_seq,
    created_at: value.created_at,
  };
}

export function parseRefreshInvestigationResponse(
  value: unknown,
): RefreshInvestigationResponse {
  if (
    !isRecord(value) ||
    (value.result !== "CREATED" && value.result !== "IDEMPOTENT_REPLAY") ||
    (value.trigger_mode !== "reactive" && value.trigger_mode !== "proactive") ||
    !isRecord(value.attempt)
  ) {
    throw new Error("invalid refresh response");
  }
  const attempt =
    value.trigger_mode === "reactive"
      ? parseReactiveIngressAttempt(value.attempt)
      : parseProactiveIngressAttempt(value.attempt);
  const snapshot =
    value.snapshot === undefined || value.snapshot === null
      ? null
      : parseRefreshInvestigationSnapshot(value.snapshot);
  const operation =
    value.operation === undefined || value.operation === null
      ? null
      : parseOperationResponse(value.operation);
  return {
    result: value.result,
    trigger_mode: value.trigger_mode,
    attempt,
    snapshot,
    operation,
  };
}
