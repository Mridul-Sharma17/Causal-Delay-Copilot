import { expect, test, type Page } from "@playwright/test";

const forbiddenLeakage = /\b(?:secret|source rows?|prompts?|provider responses?|notes?|stack traces?|filesystem paths?)\b/i;

async function expectNoPublicLeakage(page: Page) {
  expect(await page.locator("body").innerText()).not.toMatch(forbiddenLeakage);
}

test("shows the typed health journey and one audit occurrence", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("status")).toContainText(
    "Core ready with Gemini-only drafting unavailable",
  );
  await expect(page.getByText(/Demo Workspace active/)).toBeVisible();
  await expect(page.getByText("Process liveness")).toBeVisible();
  await expect(page.getByText("Core readiness")).toBeVisible();
  const healthResponse = await page.request.get("/api/health");
  expect(healthResponse.ok()).toBeTruthy();
  const health = await healthResponse.json();
  expect(Object.keys(health).sort()).toEqual([
    "code",
    "degraded_capabilities",
    "liveness",
    "observed_at",
    "readiness",
    "service",
    "state",
  ]);
  await expectNoPublicLeakage(page);
  await expect(page.getByText(/Audit occurrence recorded · event \d+/)).toBeVisible();
});

test("creates isolated browser workspaces with one idempotent audit row", async ({
  browser,
}) => {
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();

  try {
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    await Promise.all([pageA.goto("/"), pageB.goto("/")]);

    await expect(pageA.getByText(/Demo Workspace active/)).toBeVisible();
    await expect(pageB.getByText(/Demo Workspace active/)).toBeVisible();
    await expect(pageA.getByText(/Audit occurrence recorded/)).toBeVisible();
    await expect(pageB.getByText(/Audit occurrence recorded/)).toBeVisible();

    const workspaceAResponse = await pageA.request.get("/api/workspace");
    const workspaceBResponse = await pageB.request.get("/api/workspace");
    expect(workspaceAResponse.ok()).toBeTruthy();
    expect(workspaceBResponse.ok()).toBeTruthy();
    const workspaceA = await workspaceAResponse.json();
    const workspaceB = await workspaceBResponse.json();
    expect(workspaceA.workspace_id).not.toBe(workspaceB.workspace_id);
    expect(Object.keys(workspaceA).sort()).toEqual([
      "created_at",
      "last_seen_at",
      "mutation_count",
      "remaining_mutations",
      "remaining_terminal_fresh_bundles",
      "status",
      "terminal_fresh_bundle_count",
      "workspace_id",
    ]);

    const auditAResponse = await pageA.request.get("/api/audit/occurrences");
    const auditBResponse = await pageB.request.get("/api/audit/occurrences");
    expect(auditAResponse.ok()).toBeTruthy();
    expect(auditBResponse.ok()).toBeTruthy();
    const auditA = await auditAResponse.json();
    const auditB = await auditBResponse.json();
    expect(auditA.items).toHaveLength(1);
    expect(auditB.items).toHaveLength(1);
    expect(Object.keys(auditA.items[0]).sort()).toEqual([
      "created_at",
      "event_seq",
      "occurrence_id",
      "occurrence_kind",
      "outcome_code",
    ]);

    const retryResponse = await pageA.request.post("/api/audit/occurrences", {
      data: {
        idempotency_key: "core-boot-health-v1:CORE_READY_GEMINI_DEGRADED",
        occurrence_kind: "BOOT_HEALTH_CHECK",
        outcome_code: "CORE_READY_GEMINI_DEGRADED",
      },
    });
    expect(retryResponse.status()).toBe(200);
    expect((await retryResponse.json()).result).toBe("IDEMPOTENT_REPLAY");
    const auditAfterRetry = await pageA.request.get("/api/audit/occurrences");
    expect((await auditAfterRetry.json()).items).toHaveLength(1);
    await expectNoPublicLeakage(pageA);
    await expectNoPublicLeakage(pageB);
  } finally {
    await Promise.all([contextA.close(), contextB.close()]);
  }
});
