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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
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
