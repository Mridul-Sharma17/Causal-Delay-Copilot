import {
  parseLineageSnapshot,
  parseDemoWorkspaceResponse,
  parseAuditOccurrenceResponse,
  parseDecisionBriefResponse,
  parseHealthResponse,
  parseOperationMutationResponse,
  parseOperationResponse,
  parseProactiveInvestigationResponse,
  parseProactiveProposalListResponse,
  parseReactiveInvestigationResponse,
  parseRiskSignalListResponse,
  parseReplayResponse,
  parseValidatedReferenceDelivery,
  type AuditOccurrenceRequest,
  type AuditOccurrenceResponse,
  type DecisionBriefResponse,
  type DurableOperation,
  type DemoWorkspace,
  type HealthResponse,
  type OperationMutationResponse,
  type LineageSnapshot,
  type ProactiveInvestigationResponse,
  type ProactiveProposalListResponse,
  type ReactiveInvestigationResponse,
  type RiskSignalListResponse,
  type ReplayResponse,
  type ValidatedReferenceDelivery,
} from "./contracts";

export class SafeApiError extends Error {
  constructor() {
    super("Core request failed");
    this.name = "SafeApiError";
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new SafeApiError();
  }
}

async function requestJson<T>(
  url: string,
  init: RequestInit,
  parse: (value: unknown) => T,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new SafeApiError();
  }
  const payload = await readJson(response);
  if (!response.ok) {
    throw new SafeApiError();
  }
  try {
    return parse(payload);
  } catch {
    throw new SafeApiError();
  }
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson(
    "/api/health",
    { headers: { accept: "application/json" } },
    parseHealthResponse,
  );
}

export function getWorkspace(): Promise<DemoWorkspace> {
  return requestJson(
    "/api/workspace",
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseDemoWorkspaceResponse,
  );
}

export function getValidatedReference(): Promise<ValidatedReferenceDelivery> {
  return requestJson(
    "/api/evidence/reference",
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseValidatedReferenceDelivery,
  );
}

export async function recordBootOccurrence(
  request: AuditOccurrenceRequest,
): Promise<AuditOccurrenceResponse> {
  return requestJson(
    "/api/audit/occurrences",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseAuditOccurrenceResponse,
  );
}

export function getDatasetLineage(datasetVersionId: string): Promise<LineageSnapshot> {
  return requestJson(
    `/api/datasets/${datasetVersionId}/lineage`,
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseLineageSnapshot,
  );
}

export function createOperation(request: {
  idempotency_key: string;
  operation_kind: "FRESH_ANALYSIS" | "FRESH_REPRODUCTION" | "BOUNDED_WORK";
  memory_required_bytes?: number;
  request?: Record<string, unknown>;
}): Promise<OperationMutationResponse> {
  return requestJson(
    "/api/operations",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseOperationMutationResponse,
  );
}

export function getOperation(operationId: string): Promise<DurableOperation> {
  return requestJson(
    `/api/operations/${encodeURIComponent(operationId)}`,
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseOperationResponse,
  );
}

export function cancelOperation(
  operationId: string,
  idempotencyKey: string,
): Promise<OperationMutationResponse> {
  return requestJson(
    `/api/operations/${encodeURIComponent(operationId)}/cancel`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ idempotency_key: idempotencyKey }),
    },
    parseOperationMutationResponse,
  );
}

export function retryOperation(
  operationId: string,
  idempotencyKey: string,
): Promise<OperationMutationResponse> {
  return requestJson(
    `/api/operations/${encodeURIComponent(operationId)}/retry`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ idempotency_key: idempotencyKey }),
    },
    parseOperationMutationResponse,
  );
}

const TERMINAL_OPERATION_STATES = new Set([
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
  "TIMED_OUT",
  "INTERRUPTED",
  "REJECTED",
]);

export async function pollOperation(operationId: string): Promise<DurableOperation> {
  let delayMilliseconds = 2_000;
  while (true) {
    const operation = await getOperation(operationId);
    if (TERMINAL_OPERATION_STATES.has(operation.state)) {
      return operation;
    }
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, delayMilliseconds);
    });
    delayMilliseconds = Math.min(delayMilliseconds * 2, 10_000);
  }
}

export function publishDecisionBrief(
  investigationRequestId: string,
  referenceId: string,
): Promise<DecisionBriefResponse> {
  return requestJson(
    `/api/investigations/${encodeURIComponent(investigationRequestId)}/decision-brief`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({
        idempotency_key: `decision-brief:${investigationRequestId}:${referenceId}`,
        reference_id: referenceId,
      }),
    },
    parseDecisionBriefResponse,
  );
}

export function replayDecisionBrief(
  investigationRequestId: string,
  eventSeq: number,
): Promise<ReplayResponse> {
  const params = new URLSearchParams({
    investigation_request_id: investigationRequestId,
    event_seq: String(eventSeq),
  });
  return requestJson(
    `/api/audit/replay?${params.toString()}`,
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseReplayResponse,
  );
}

export function getRiskSignals(
  datasetVersionId: string,
): Promise<RiskSignalListResponse> {
  return requestJson(
    `/api/risk-signals?dataset_version_id=${encodeURIComponent(datasetVersionId)}`,
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseRiskSignalListResponse,
  );
}

export function submitReactiveInvestigation(
  datasetVersionId: string,
  fixtureId: string,
): Promise<ReactiveInvestigationResponse> {
  return requestJson(
    "/api/investigations/reactive/fixtures",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({
        dataset_version_id: datasetVersionId,
        fixture_id: fixtureId,
      }),
    },
    parseReactiveInvestigationResponse,
  );
}

export function getProactiveProposals(
  datasetVersionId: string,
): Promise<ProactiveProposalListResponse> {
  return requestJson(
    `/api/proactive-proposals?dataset_version_id=${encodeURIComponent(datasetVersionId)}`,
    {
      headers: { accept: "application/json" },
      credentials: "same-origin",
    },
    parseProactiveProposalListResponse,
  );
}

export function submitProactiveInvestigation(
  datasetVersionId: string,
  fixtureId: string,
): Promise<ProactiveInvestigationResponse> {
  return requestJson(
    "/api/investigations/proactive/fixtures",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({
        dataset_version_id: datasetVersionId,
        fixture_id: fixtureId,
      }),
    },
    parseProactiveInvestigationResponse,
  );
}
