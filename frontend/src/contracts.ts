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
