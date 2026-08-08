import {
  parseIngestionRunResponse,
  parseLineageSnapshot,
  parseDemoWorkspaceResponse,
  parseAuditOccurrenceResponse,
  parseHealthResponse,
  parseProactiveInvestigationResponse,
  parseProactiveProposalListResponse,
  parseReactiveInvestigationResponse,
  parseRiskSignalListResponse,
  parseValidatedReferenceDelivery,
  type AuditOccurrenceRequest,
  type AuditOccurrenceResponse,
  type DemoWorkspace,
  type HealthResponse,
  type IngestionRunResponse,
  type LineageSnapshot,
  type ProactiveInvestigationResponse,
  type ProactiveProposalListResponse,
  type ReactiveInvestigationResponse,
  type RiskSignalListResponse,
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

export function importHeroDataset(): Promise<IngestionRunResponse> {
  return requestJson(
    "/api/ingestion-runs",
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        idempotency_key: "core-semi-synthetic-hero-v1",
        dataset_key: "semi-synthetic-hero",
        mapping_manifest_id: "semi-synthetic-hero.mapping.v1",
      }),
    },
    parseIngestionRunResponse,
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
