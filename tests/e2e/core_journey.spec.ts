import { expect, test } from "@playwright/test";

const forbiddenLeakage = /\b(?:secret|source rows?|prompts?|provider responses?|notes?|stack traces?|filesystem paths?)\b/i;
const journeyExpect = expect.configure({ timeout: 30_000 });
const expectedReleaseCandidateId =
  process.env.CORE_RELEASE_CANDIDATE_ID ?? "core-issue-64-local_fallback";

test("compiled SPA traverses the real validated-reference journey and replay", async ({
  page,
}) => {
  test.setTimeout(60_000);
  const documentResponse = await page.goto("/");
  expect(documentResponse?.ok()).toBeTruthy();
  expect(await documentResponse?.text()).toContain("Causal Delay Copilot");

  await journeyExpect(page.getByText("Validated reference", { exact: true })).toBeVisible();
  await journeyExpect(
    page.getByText(/Investigation request accepted|Existing investigation request reused/),
  ).toBeVisible();
  await journeyExpect(
    page.getByRole("heading", { name: "Subject applicability", exact: true }),
  ).toBeVisible();
  await journeyExpect(page.getByText("Action lane: read-only", { exact: true })).toBeVisible();
  await journeyExpect(
    page.getByText(/Replay verified from stored state at event \d+/),
  ).toBeVisible();
  await journeyExpect(
    page.getByText(/Proactive preview accepted|Existing proactive preview reused/),
  ).toBeVisible();

  const referenceResponse = await page.request.get("/api/evidence/reference");
  expect(referenceResponse.ok()).toBeTruthy();
  const reference = await referenceResponse.json();
  expect(reference.reference_slot_id).toBe("ordinary-demo");
  expect(reference.verification_state).toBe("reference_validated");
  expect(reference.dataset_version_id).toMatch(/^sha256:[0-9a-f]{64}$/);
  expect(reference.scientific_request_digest).toMatch(/^sha256:[0-9a-f]{64}$/);
  expect(reference.runtime_fingerprint_digest).toMatch(/^sha256:[0-9a-f]{64}$/);
  expect(reference.bundle_manifest_hash).toMatch(/^sha256:[0-9a-f]{64}$/);
  expect(reference.release_candidate_id).toBe(expectedReleaseCandidateId);

  const lineageResponse = await page.request.get(
    `/api/datasets/${encodeURIComponent(reference.dataset_version_id)}/lineage`,
  );
  expect(lineageResponse.ok()).toBeTruthy();
  const lineage = await lineageResponse.json();
  expect(lineage.dataset_version.dataset_version_id).toBe(reference.dataset_version_id);
  expect(lineage.dataset_version.mapping_manifest_id).toBe(
    "semi-synthetic-hero.mapping.v1",
  );

  const signalsResponse = await page.request.get(
    `/api/risk-signals?dataset_version_id=${encodeURIComponent(reference.dataset_version_id)}`,
  );
  expect(signalsResponse.ok()).toBeTruthy();
  const signals = await signalsResponse.json();
  expect(signals.predictive_status.state).toBe("verified");
  expect(signals.items).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ fixture_id: "hero-reactive-risk-predictive-baseline-v1" }),
    ]),
  );

  const proposalsResponse = await page.request.get(
    `/api/proactive-proposals?dataset_version_id=${encodeURIComponent(reference.dataset_version_id)}`,
  );
  expect(proposalsResponse.ok()).toBeTruthy();
  expect((await proposalsResponse.json()).items).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ fixture_id: "hero-proactive-proposal-v1" }),
    ]),
  );

  const occurrencesResponse = await page.request.get("/api/audit/occurrences");
  expect(occurrencesResponse.ok()).toBeTruthy();
  const occurrences = await occurrencesResponse.json();
  const occurrenceKinds = occurrences.items.map(
    (item: { occurrence_kind: string }) => item.occurrence_kind,
  );
  expect(occurrenceKinds).toEqual(
    expect.arrayContaining(["BOOT_HEALTH_CHECK", "REACTIVE_INGRESS", "PROACTIVE_INGRESS"]),
  );

  expect(await page.locator("body").innerText()).not.toMatch(forbiddenLeakage);
});
