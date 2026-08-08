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

export type IngestionRunResponse = {
  result: "CREATED" | "IDEMPOTENT_REPLAY";
  ingestion_run_id: string;
  dataset_version_id: string;
  status: "SUCCEEDED";
};

export type LineageRecord = Record<string, unknown>;

export type LineageSnapshot = {
  ingestion_run: LineageRecord;
  dataset_version: {
    dataset_id: string;
    dataset_version_id: string;
    source_kind: "semi_synthetic";
    intended_role: "semi_synthetic_hero";
    mapping_manifest_id: string;
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
  if (
    typeof datasetVersion.dataset_id !== "string" ||
    typeof datasetVersion.dataset_version_id !== "string" ||
    datasetVersion.source_kind !== "semi_synthetic" ||
    datasetVersion.intended_role !== "semi_synthetic_hero" ||
    typeof datasetVersion.mapping_manifest_id !== "string" ||
    !isRecord(datasetVersion.record_counts)
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
  if (
    typeof auditBinding.snapshot_id !== "string" ||
    typeof auditBinding.dataset_version_id !== "string" ||
    typeof auditBinding.occurrence_id !== "string" ||
    typeof auditBinding.event_seq !== "number" ||
    !Number.isInteger(auditBinding.event_seq) ||
    auditBinding.event_seq < 1 ||
    typeof auditBinding.content_hash !== "string" ||
    typeof auditBinding.created_at !== "string"
  ) {
    throw new Error("invalid lineage response");
  }
  return {
    ingestion_run: parseRecord(value.ingestion_run),
    dataset_version: {
      dataset_id: datasetVersion.dataset_id,
      dataset_version_id: datasetVersion.dataset_version_id,
      source_kind: "semi_synthetic",
      intended_role: "semi_synthetic_hero",
      mapping_manifest_id: datasetVersion.mapping_manifest_id,
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
