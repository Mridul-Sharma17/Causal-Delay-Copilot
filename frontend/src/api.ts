import {
  parseAuditOccurrenceResponse,
  parseHealthResponse,
  type AuditOccurrenceRequest,
  type AuditOccurrenceResponse,
  type HealthResponse,
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
      body: JSON.stringify(request),
    },
    parseAuditOccurrenceResponse,
  );
}
