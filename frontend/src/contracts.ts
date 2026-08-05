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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
