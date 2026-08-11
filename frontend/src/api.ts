import {
  parseLineageSnapshot,
  parseManagerDecisionResponse,
  parseDemoWorkspaceResponse,
  parseDraftContextPreview,
  parseDraftMutationResponse,
  parseAuditOccurrenceResponse,
  parseDecisionBriefResponse,
  parseHealthResponse,
  parseReleaseIdentity,
  parseOperationMutationResponse,
  parseOperationResponse,
  parseProactiveInvestigationResponse,
  parseProactiveProposalListResponse,
  parseReactiveInvestigationResponse,
  parseRefreshInvestigationResponse,
  parseRiskSignalListResponse,
  parseReplayResponse,
  parseTradeoffSelectionAcceptanceResponse,
  parseTradeoffSelectionPublishResponse,
  parseValidatedReferenceDelivery,
  type AuditOccurrenceRequest,
  type AuditOccurrenceResponse,
  type DecisionBriefResponse,
  type DurableOperation,
  type DemoWorkspace,
  type DraftContextPreview,
  type DraftMutationResponse,
  type ManagerDecisionResponse,
  type HealthResponse,
  type ReleaseIdentity,
  type OperationMutationResponse,
  type LineageSnapshot,
  type ProactiveInvestigationResponse,
  type ProactiveProposalListResponse,
  type ReactiveInvestigationResponse,
  type RefreshInvestigationResponse,
  type RiskSignalListResponse,
  type ReplayResponse,
  type TradeoffSelectionAcceptanceResponse,
  type TradeoffSelectionDeliveryAttempt,
  type TradeoffSelectionPublishResponse,
  type TradeoffSelectionRecord,
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

export function getReleaseIdentity(): Promise<ReleaseIdentity> {
  return requestJson(
    "/api/release",
    { headers: { accept: "application/json" } },
    parseReleaseIdentity,
  );
}

export function publishTradeoffSelection(
  selection: TradeoffSelectionRecord,
): Promise<TradeoffSelectionPublishResponse> {
  return requestJson(
    "/api/decision-support/tradeoff-selections",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ selection }),
    },
    parseTradeoffSelectionPublishResponse,
  );
}

export function acceptTradeoffSelection(
  evaluationSeriesId: string,
  deliveryAttempt: TradeoffSelectionDeliveryAttempt,
  selection: TradeoffSelectionRecord,
): Promise<TradeoffSelectionAcceptanceResponse> {
  return requestJson(
    `/api/decision-support/evaluation-series/${encodeURIComponent(evaluationSeriesId)}/tradeoff-selection/accept`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ delivery_attempt: deliveryAttempt, selection }),
    },
    parseTradeoffSelectionAcceptanceResponse,
  );
}

export function prepareDraftContext(
  currentAdvice: Record<string, unknown>,
  options: {
    idempotencyKey?: string;
    managerActorRef?: string;
  } = {},
): Promise<DraftContextPreview> {
  return requestJson(
    "/api/decision-support/draft-context",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({
        current_advice: currentAdvice,
        ...(options.idempotencyKey === undefined
          ? {}
          : { idempotency_key: options.idempotencyKey }),
        ...(options.managerActorRef === undefined
          ? {}
          : { manager_actor_ref: options.managerActorRef }),
      }),
    },
    parseDraftContextPreview,
  );
}

export function editDraft(
  draftId: string,
  request: {
    idempotency_key: string;
    expected_head_ref_and_hash: { reference: string; content_hash: string };
    manager_actor_ref: string;
    subject: string;
    body: string;
  },
): Promise<DraftMutationResponse> {
  return requestJson(
    `/api/decision-support/drafts/${encodeURIComponent(draftId)}/edits`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseDraftMutationResponse,
  );
}

export function disposeDraft(
  draftId: string,
  request: {
    idempotency_key: string;
    expected_head_ref_and_hash: { reference: string; content_hash: string };
    manager_actor_ref: string;
    disposition: "APPROVE" | "REJECT" | "INVESTIGATE_FURTHER";
    rejection_reason?: { code: string; detail: string };
  },
): Promise<DraftMutationResponse> {
  return requestJson(
    `/api/decision-support/drafts/${encodeURIComponent(draftId)}/dispositions`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseDraftMutationResponse,
  );
}

export function recordManagerDecision(
  draftId: string,
  request: {
    idempotency_key: string;
    expected_head_ref_and_hash: { reference: string; content_hash: string };
    manager_actor_ref: string;
    disposition: "APPROVE" | "REJECT" | "INVESTIGATE_FURTHER";
  },
): Promise<ManagerDecisionResponse> {
  return requestJson(
    `/api/decision-support/drafts/${encodeURIComponent(draftId)}/decisions`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseManagerDecisionResponse,
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

export function refreshInvestigation(
  investigationRequestId: string,
  request: {
    idempotency_key: string;
    trigger_mode: "reactive" | "proactive";
    request: Record<string, unknown>;
    observation_cutoff: Record<string, unknown>;
    root_seed: number;
  },
): Promise<RefreshInvestigationResponse> {
  return requestJson(
    `/api/investigations/${encodeURIComponent(investigationRequestId)}/refresh`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(request),
    },
    parseRefreshInvestigationResponse,
  );
}
