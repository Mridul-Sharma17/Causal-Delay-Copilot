import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { expect, test, type APIRequestContext, type Browser, type BrowserContext } from "@playwright/test";

const execFileAsync = promisify(execFile);
const qualificationExpect = expect.configure({ timeout: 45_000 });

test.describe.configure({ mode: "serial" });
test.beforeEach(() => {
  test.skip(
    process.env.HOSTED_QUALIFICATION !== "1",
    "Hosted qualification is run only by scripts/hosted_qualification.py.",
  );
});

function requireQualificationEnvironment(): void {
  for (const name of [
    "HOSTED_QUALIFICATION",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_ENVIRONMENT_ID",
  ]) {
    expect(process.env[name], `${name} is required for hosted qualification`).toBeTruthy();
  }
}

async function jsonResponse(
  request: APIRequestContext,
  path: string,
  options?: Parameters<APIRequestContext["fetch"]>[1],
): Promise<{ status: number; body: Record<string, any> }> {
  const response = await request.fetch(path, options);
  const text = await response.text();
  let body: Record<string, any> = {};
  if (text !== "") {
    body = JSON.parse(text) as Record<string, any>;
  }
  return { status: response.status(), body };
}

async function createWorkspace(browser: Browser): Promise<{
  context: BrowserContext;
  page: Awaited<ReturnType<BrowserContext["newPage"]>>;
}> {
  const context = await browser.newContext();
  const page = await context.newPage();
  const workspace = await jsonResponse(page.request, "/api/workspace");
  expect(workspace.status).toBe(200);
  expect(workspace.body.workspace_id).toEqual(expect.any(String));
  return { context, page };
}

test("qualifies the real reference journey and an explicit abstention boundary", async ({
  page,
}) => {
  requireQualificationEnvironment();
  const document = await page.goto("/");
  expect(document?.ok()).toBeTruthy();
  await qualificationExpect(page.getByText("Validated reference", { exact: true })).toBeVisible();

  const release = await jsonResponse(page.request, "/api/release");
  const reference = await jsonResponse(page.request, "/api/evidence/reference");
  expect(release.status).toBe(200);
  expect(reference.status).toBe(200);
  expect(release.body.release_candidate_id).toBe(process.env.HOSTED_RELEASE_CANDIDATE_ID);
  expect(release.body.build_manifest_id).toBe(process.env.HOSTED_BUILD_MANIFEST_ID);
  expect(reference.body.verification_state).toBe("reference_validated");
  expect(reference.body.release_candidate_id).toBe(release.body.release_candidate_id);
  expect(reference.body.bundle_manifest_hash).toMatch(/^sha256:[0-9a-f]{64}$/);

  const registeredReference = await jsonResponse(
    page.request,
    `/api/validated-references/${encodeURIComponent(reference.body.reference_slot_id)}`,
  );
  expect(registeredReference.status).toBe(200);
  expect(registeredReference.body.bundle_ref).toBe(reference.body.bundle_manifest_hash);
  expect(registeredReference.body.release_candidate_id).toBe(
    process.env.HOSTED_RELEASE_CANDIDATE_ID,
  );

  const abstention = await jsonResponse(page.request, "/api/investigations/reactive", {
    method: "POST",
    data: {},
  });
  expect(abstention.status).toBe(422);
  expect(abstention.body).toEqual({
    code: "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
    recovery_action: "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
  });
  const abstentionLedger = await jsonResponse(page.request, "/api/audit/occurrences");
  expect(abstentionLedger.status).toBe(200);
  expect(abstentionLedger.body.items).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        occurrence_kind: "REACTIVE_INGRESS",
        outcome_code: "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
      }),
    ]),
  );
});

test("qualifies workspace isolation and mutation rate/quota refusal", async ({ browser }) => {
  requireQualificationEnvironment();
  const first = await createWorkspace(browser);
  const second = await createWorkspace(browser);
  try {
    const firstOccurrence = await jsonResponse(first.page.request, "/api/audit/occurrences", {
      method: "POST",
      data: {
        idempotency_key: `hosted-isolation-${Date.now()}`,
        occurrence_kind: "BOOT_HEALTH_CHECK",
        outcome_code: "CORE_READY",
      },
    });
    expect(firstOccurrence.status).toBe(201);
    const occurrenceId = firstOccurrence.body.occurrence_id;
    expect(occurrenceId).toEqual(expect.any(String));
    const persistedLedger = await jsonResponse(first.page.request, "/api/audit/occurrences");
    expect(persistedLedger.status).toBe(200);
    expect(persistedLedger.body.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          occurrence_id: occurrenceId,
          occurrence_kind: "BOOT_HEALTH_CHECK",
          outcome_code: "CORE_READY",
        }),
      ]),
    );

    const crossWorkspace = await jsonResponse(
      second.page.request,
      `/api/audit/occurrences/${encodeURIComponent(occurrenceId)}`,
    );
    const unknown = await jsonResponse(
      second.page.request,
      "/api/audit/occurrences/not-a-real-occurrence",
    );
    expect(crossWorkspace.status).toBe(404);
    expect(crossWorkspace.body).toEqual(unknown.body);
    expect(crossWorkspace.body.code).toBe("DEMO_WORKSPACE_RESOURCE_UNAVAILABLE");

    const workspaceAfterMutation = await jsonResponse(first.page.request, "/api/workspace");
    expect(workspaceAfterMutation.status).toBe(200);
    expect(workspaceAfterMutation.body.mutation_count).toBeGreaterThanOrEqual(1);
    expect(workspaceAfterMutation.body.remaining_mutations).toBeLessThan(
      Number(process.env.HOSTED_MAX_WORKSPACE_MUTATIONS ?? "200"),
    );

    const mutationResponses = [];
    for (let index = 0; index < 35; index += 1) {
      mutationResponses.push(
        await jsonResponse(first.page.request, "/api/audit/occurrences", {
          method: "POST",
          data: {
            idempotency_key: `hosted-rate-${Date.now()}-${index}`,
            occurrence_kind: "BOOT_HEALTH_CHECK",
            outcome_code: "CORE_READY",
          },
        }),
      );
    }
    expect(
      mutationResponses.some(
        (response) =>
          response.status === 429 && response.body.code === "DEMO_WORKSPACE_RATE_LIMITED",
      ),
    ).toBeTruthy();
  } finally {
    await Promise.all([first.context.close(), second.context.close()]);
  }
});

test("qualifies durable queue saturation and restart recovery", async ({ browser }) => {
  test.setTimeout(900_000);
  requireQualificationEnvironment();
  const contexts = await Promise.all([
    createWorkspace(browser),
    createWorkspace(browser),
    createWorkspace(browser),
    createWorkspace(browser),
  ]);
  const admittedOperationIds: Array<{
    page: (typeof contexts)[number]["page"];
    id: string;
  }> = [];
  try {
    const reference = await jsonResponse(contexts[0].page.request, "/api/evidence/reference");
    expect(reference.status).toBe(200);
    const datasetVersionId = reference.body.dataset_version_id as string;
    const attempts = await Promise.all(
      contexts.map(({ page }) =>
        jsonResponse(page.request, "/api/investigations/reactive/fixtures", {
          method: "POST",
          data: {
            dataset_version_id: datasetVersionId,
            fixture_id: "hero-reactive-risk-predictive-baseline-v1",
          },
        }),
      ),
    );
    attempts.forEach((attempt) => expect(attempt.status).toBe(201));
    const admitted = await Promise.all(
      contexts.map(({ page }, index) =>
        jsonResponse(page.request, "/api/operations", {
          method: "POST",
          data: {
            operation_kind: "FRESH_ANALYSIS",
            idempotency_key: `hosted-queue-${Date.now()}-${index}`,
            memory_required_bytes: 1024,
            request: {
              investigation_request_id: attempts[index].body.attempt.investigation_request_id,
              root_seed: index,
            },
          },
        }),
      ),
    );
    const queueRefusal = admitted.find(
      (response) =>
        response.status === 429 && response.body.code === "OPERATION_QUEUE_CAPACITY_REACHED",
    );
    expect(queueRefusal).toBeDefined();
    admitted.forEach((response, index) => {
      const operationId = response.body.operation?.operation_id;
      if (typeof operationId === "string") {
        expect(operationId).toMatch(/^operation-/);
        admittedOperationIds.push({ page: contexts[index].page, id: operationId });
      }
    });

    await Promise.all(
      admittedOperationIds.map(async ({ page, id }, index) => {
        await jsonResponse(page.request, `/api/operations/${encodeURIComponent(id)}/cancel`, {
          method: "POST",
          data: { idempotency_key: `hosted-queue-cleanup-${Date.now()}-${index}` },
        });
        await qualificationExpect.poll(async () => {
          const operation = await jsonResponse(
            page.request,
            `/api/operations/${encodeURIComponent(id)}`,
          );
          return operation.body.state;
        }).toMatch(/^(SUCCEEDED|FAILED|CANCELLED|TIMED_OUT|INTERRUPTED)$/);
      }),
    );

    const recoveryContext = await createWorkspace(browser);
    contexts.push(recoveryContext);
    const recoveryAttempt = await jsonResponse(
      recoveryContext.page.request,
      "/api/investigations/reactive/fixtures",
      {
        method: "POST",
        data: {
          dataset_version_id: datasetVersionId,
          fixture_id: "hero-reactive-risk-predictive-baseline-v1",
        },
      },
    );
    expect(recoveryAttempt.status).toBe(201);
    const recoveryAdmission = await jsonResponse(
      recoveryContext.page.request,
      "/api/operations",
      {
        method: "POST",
        data: {
          operation_kind: "FRESH_ANALYSIS",
          idempotency_key: `hosted-restart-${Date.now()}`,
          memory_required_bytes: 1024,
          request: {
            investigation_request_id: recoveryAttempt.body.attempt.investigation_request_id,
            root_seed: 77,
          },
        },
      },
    );
    expect(recoveryAdmission.status).toBe(202);
    const recoveryOperationId = recoveryAdmission.body.operation.operation_id as string;
    admittedOperationIds.push({ page: recoveryContext.page, id: recoveryOperationId });
    const persistenceSentinel = await jsonResponse(
      recoveryContext.page.request,
      "/api/audit/occurrences",
      {
        method: "POST",
        data: {
          idempotency_key: `hosted-persistence-${Date.now()}`,
          occurrence_kind: "HOSTED_RESTART_PERSISTENCE_CHECK",
          outcome_code: "PERSISTENCE_SENTINEL_WRITTEN",
        },
      },
    );
    expect(persistenceSentinel.status).toBe(201);
    const persistenceOccurrenceId = persistenceSentinel.body.occurrence_id as string;

    const railwayCommand = process.platform === "win32" ? "npx.cmd" : "npx";
    const railwayArgs = [
      "--yes",
      "@railway/cli@5.37.4",
      "restart",
      "--project",
      process.env.RAILWAY_PROJECT_ID as string,
      "--service",
      process.env.RAILWAY_SERVICE_ID as string,
      "--environment",
      process.env.RAILWAY_ENVIRONMENT_ID as string,
      "--yes",
      "--json",
    ];
    await execFileAsync(railwayCommand, railwayArgs, {
      env: process.env,
      timeout: 120_000,
      windowsHide: true,
    });

    await qualificationExpect.poll(async () => {
      const health = await jsonResponse(recoveryContext.page.request, "/api/health");
      return health.status === 200 && ["ready", "degraded"].includes(health.body.state);
    }).toBeTruthy();
    await qualificationExpect.poll(async () => {
      const operation = await jsonResponse(
        recoveryContext.page.request,
        `/api/operations/${encodeURIComponent(recoveryOperationId)}`,
      );
      return operation.body.state;
    }).toMatch(/^(INTERRUPTED|FAILED|CANCELLED|SUCCEEDED|TIMED_OUT)$/);
    const recovered = await jsonResponse(
      recoveryContext.page.request,
      `/api/operations/${encodeURIComponent(recoveryOperationId)}`,
    );
    expect(recovered.body.state).toBe("INTERRUPTED");
    const persistedLedger = await jsonResponse(
      recoveryContext.page.request,
      "/api/audit/occurrences",
    );
    expect(persistedLedger.status).toBe(200);
    expect(persistedLedger.body.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          occurrence_id: persistenceOccurrenceId,
          outcome_code: "PERSISTENCE_SENTINEL_WRITTEN",
        }),
      ]),
    );
    const retry = await jsonResponse(
      recoveryContext.page.request,
      `/api/operations/${encodeURIComponent(recoveryOperationId)}/retry`,
      {
        method: "POST",
        data: { idempotency_key: `hosted-retry-${Date.now()}` },
      },
    );
    expect(retry.status).toBe(202);
    expect(retry.body.operation.operation_id).not.toBe(recoveryOperationId);
    if (typeof retry.body.operation.operation_id === "string") {
      admittedOperationIds.push({
        page: recoveryContext.page,
        id: retry.body.operation.operation_id,
      });
    }
  } finally {
    await Promise.all(
      admittedOperationIds.map(async ({ page, id }, index) => {
        await jsonResponse(page.request, `/api/operations/${encodeURIComponent(id)}/cancel`, {
          method: "POST",
          data: { idempotency_key: `hosted-cleanup-${Date.now()}-${index}` },
        });
      }),
    );
    await Promise.all(
      contexts.map(async ({ context }) => {
        await context.close();
      }),
    );
  }
});

test("qualifies global mutation rate/quota refusal", async ({ browser }) => {
  test.setTimeout(240_000);
  requireQualificationEnvironment();
  const contexts = await Promise.all(
    Array.from({ length: 5 }, () => createWorkspace(browser)),
  );
  let overflow: { status: number; body: Record<string, any> } | undefined;
  const acceptedByWorkspace = Array.from({ length: contexts.length }, () => 0);
  try {
    outer: for (let round = 0; round < 30; round += 1) {
      for (let index = 0; index < contexts.length; index += 1) {
        const response = await jsonResponse(
          contexts[index].page.request,
          "/api/audit/occurrences",
          {
            method: "POST",
            data: {
              idempotency_key: `hosted-global-rate-${Date.now()}-${round}-${index}`,
              occurrence_kind: "HOSTED_GLOBAL_RATE_CHECK",
              outcome_code: "GLOBAL_MUTATION_RATE_PROBE",
            },
          },
        );
        if (response.status === 429) {
          overflow = response;
          break outer;
        }
        expect(response.status).toBe(201);
        acceptedByWorkspace[index] += 1;
      }
    }
    expect(overflow).toBeDefined();
    expect(acceptedByWorkspace.every((count) => count < 30)).toBeTruthy();

    const freshWorkspace = await createWorkspace(browser);
    try {
      const globalRefusal = await jsonResponse(
        freshWorkspace.page.request,
        "/api/audit/occurrences",
        {
          method: "POST",
          data: {
            idempotency_key: `hosted-global-rate-confirm-${Date.now()}`,
            occurrence_kind: "HOSTED_GLOBAL_RATE_CHECK",
            outcome_code: "GLOBAL_MUTATION_RATE_CONFIRMATION",
          },
        },
      );
      expect(globalRefusal.status).toBe(429);
      expect(globalRefusal.body.code).toBe("DEMO_WORKSPACE_RATE_LIMITED");
    } finally {
      await freshWorkspace.context.close();
    }
  } finally {
    await Promise.all(contexts.map(({ context }) => context.close()));
  }
});
