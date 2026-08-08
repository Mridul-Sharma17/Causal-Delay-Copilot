import { afterEach, expect, test, vi } from "vitest";

import { pollOperation } from "./api";
import { parseOperationResponse } from "./contracts";

function operation(state: string) {
  return {
    schema_version: "durable-operation.v1",
    operation_id: "operation-1",
    operation_kind: "BOUNDED_WORK",
    state,
    status: state,
    queue_position: state === "QUEUED" ? 1 : null,
    created_at: "2026-08-08T00:00:00Z",
    queued_at: "2026-08-08T00:00:00Z",
    started_at: state === "QUEUED" ? null : "2026-08-08T00:00:01Z",
    finished_at: state === "SUCCEEDED" ? "2026-08-08T00:00:02Z" : null,
    cancel_requested_at: null,
    retry_of_operation_id: null,
    failure_code: null,
    recovery_action: null,
    resource_warnings: [],
    artifact_state: state === "SUCCEEDED" ? "PUBLISHED" : "NOT_STARTED",
    retryable: false,
    timeout_seconds: 300,
    thread_cap: 1,
    memory_required_bytes: 1024,
    memory_available_bytes: 2048,
    disk_free_bytes: 2 * 1024 * 1024 * 1024,
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("pollOperation uses bounded backoff and stops at a terminal state", async () => {
  vi.useFakeTimers();
  const fetchMock = vi.spyOn(globalThis, "fetch");
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("QUEUED"))))
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("RUNNING"))))
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("RUNNING"))))
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("RUNNING"))))
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("RUNNING"))))
    .mockResolvedValueOnce(new Response(JSON.stringify(operation("SUCCEEDED"))));

  const pending = pollOperation("operation-1");
  await Promise.resolve();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  await vi.advanceTimersByTimeAsync(1_999);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(3_999);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(3);
  await vi.advanceTimersByTimeAsync(7_999);
  expect(fetchMock).toHaveBeenCalledTimes(3);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(4);
  await vi.advanceTimersByTimeAsync(9_999);
  expect(fetchMock).toHaveBeenCalledTimes(4);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(5);
  await vi.advanceTimersByTimeAsync(9_999);
  expect(fetchMock).toHaveBeenCalledTimes(5);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(6);

  await expect(pending).resolves.toMatchObject({ state: "SUCCEEDED" });
  expect(
    fetchMock.mock.calls.every(([url]) => url === "/api/operations/operation-1"),
  ).toBe(true);
});

test("parseOperationResponse accepts an estimated provisional fresh result", () => {
  const parsed = parseOperationResponse({
    ...operation("SUCCEEDED"),
    analysis_run: {
      schema_version: "analysis-run-status.v1",
      analysis_run_id: "analysis-run-1",
      occurrence_id: "operation-1",
      operation_id: "operation-1",
      status: "ESTIMATED",
      lifecycle: "sealed",
      scientific_outcome: "estimated",
      verification_state: "machine_verified",
      availability_state: "available",
      delivery_mode: "fresh_execution",
      reason_code: null,
      failure_code: null,
      recovery_action: null,
      estimator_executed: true,
      request_schema_version: "causal-engine-suite-request.v2",
      scientific_request_digest: "sha256:request",
      runtime_fingerprint: {},
      runtime_fingerprint_digest: "sha256:runtime",
      root_seed: 0,
      derived_seed_registry: [],
      estimator_descriptor: {},
      feature_descriptor: {},
      fold_descriptor: {},
      fresh_run_detail: {},
      primary_result: {
        schema_version: "fresh-primary-result.v1",
        state: "provisional",
        permission: {
          evidence_verdict: false,
          action_permission: false,
          state: "provisional_run_output_only",
        },
      },
    },
  });

  expect(parsed.analysis_run?.status).toBe("ESTIMATED");
  expect(parsed.analysis_run?.primary_result?.state).toBe("provisional");
});
