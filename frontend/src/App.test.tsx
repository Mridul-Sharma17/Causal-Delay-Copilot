import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const healthResponse = {
  service: "causal-delay-copilot",
  state: "degraded",
  code: "CORE_READY_GEMINI_DEGRADED",
  liveness: { state: "live", code: "CORE_LIVE" },
  readiness: { state: "degraded", code: "CORE_READY_GEMINI_DEGRADED" },
  degraded_capabilities: ["GEMINI_DRAFTING"],
  observed_at: "2026-08-05T00:00:00Z",
};

const workspaceResponse = {
  workspace_id: "demo-workspace-1",
  status: "ACTIVE",
  created_at: "2026-08-05T00:00:00Z",
  last_seen_at: "2026-08-05T00:00:00Z",
  mutation_count: 0,
  remaining_mutations: 200,
  terminal_fresh_bundle_count: 0,
  remaining_terminal_fresh_bundles: 4,
};

const lineageResponse = {
  ingestion_run: {
    ingestion_run_id: "run-1",
    status: "SUCCEEDED",
  },
  dataset_version: {
    dataset_id: "semi-synthetic-hero",
    dataset_version_id: "sha256:hero-v1",
    source_kind: "semi_synthetic",
    intended_role: "semi_synthetic_hero",
    mapping_manifest_id: "semi-synthetic-hero.mapping.v1",
    record_counts: {
      order_lines: 3,
      order_line_events: 6,
      source_observations: 18,
      validation_findings: 1,
    },
  },
  mapping_manifest: {},
  order_lines: [
    {
      order_line_id: "line-1",
      order_group_id: "group-1",
      supplier_id: "supplier-1",
      fields: {
        material_class: { state: "present", value: "switchgear" },
      },
    },
  ],
  order_line_events: [
    {
      event_id: "event-1",
      order_line_id: "line-1",
      kind: "committed",
      clocks: {
        occurred_at: {
          state: "present",
          value: {
            source_value: "2026-01-05T09:30:00+05:30",
            normalized_value: "2026-01-05T04:00:00+00:00",
            precision: "minute",
            timezone_status: "known",
          },
        },
        known_at: { state: "unresolved" },
        available_at: { state: "unresolved" },
      },
      milestone_kind: { state: "not_applicable" },
      promised_for: { state: "not_applicable" },
      reason: { state: "missing" },
      revises_promise_event_id: { state: "not_applicable" },
    },
  ],
  source_observations: [
    {
      source_observation_id: "observation-line-1",
      target_record_type: "OrderLine",
      target_record_id: "line-1",
      target_field_path: "fields.material_class",
      source_field_path: { state: "present", value: "fields.material_class" },
      source_locator_token: "loc-line-1",
    },
    {
      source_observation_id: "observation-line-id",
      target_record_type: "OrderLine",
      target_record_id: "line-1",
      target_field_path: "order_line_id",
      source_field_path: { state: "present", value: "source_key" },
      source_locator_token: "loc-line-id",
    },
    {
      source_observation_id: "observation-event-1",
      target_record_type: "OrderLineEvent",
      target_record_id: "event-1",
      target_field_path: "event_id",
      source_field_path: { state: "present", value: "source_event_key" },
      source_locator_token: "loc-event-1",
    },
  ],
  validation_findings: [
    {
      validation_finding_id: "finding-1",
      code: "SOURCE_DUPLICATE_DEDUPED",
      message: "An exact repeated bundled observation was deduplicated.",
      remediation: "No action is required.",
      affected_refs: ["line-1"],
    },
  ],
  audit_binding: {
    snapshot_id: "sha256:snapshot-1",
    dataset_version_id: "sha256:hero-v1",
    occurrence_id: "occurrence-2",
    event_seq: 4,
    content_hash: "sha256:lineage-1",
    created_at: "2026-08-05T00:00:01Z",
  },
};

describe("Core health journey", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("shows typed liveness/readiness and records one audited boot occurrence", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async (input, init) => {
      if (input === "/api/health") {
        return new Response(JSON.stringify(healthResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      if (input === "/api/workspace") {
        return new Response(JSON.stringify(workspaceResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      if (input === "/api/ingestion-runs") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({
          idempotency_key: "core-semi-synthetic-hero-v1",
          dataset_key: "semi-synthetic-hero",
          mapping_manifest_id: "semi-synthetic-hero.mapping.v1",
        });
        return new Response(
          JSON.stringify({
            result: "CREATED",
            ingestion_run_id: "run-1",
            dataset_version_id: "sha256:hero-v1",
            status: "SUCCEEDED",
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        );
      }

      if (typeof input === "string" && input.startsWith("/api/datasets/")) {
        return new Response(JSON.stringify(lineageResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      expect(input).toBe("/api/audit/occurrences");
      expect(init?.method).toBe("POST");
      const request = JSON.parse(String(init?.body)) as {
        idempotency_key: string;
        occurrence_kind: string;
        outcome_code: string;
      };
      expect(request.idempotency_key).toBe(
        "core-boot-health-v1:CORE_READY_GEMINI_DEGRADED",
      );
      expect(request.occurrence_kind).toBe("BOOT_HEALTH_CHECK");
      expect(request.outcome_code).toBe("CORE_READY_GEMINI_DEGRADED");

      return new Response(
        JSON.stringify({
          result: "CREATED",
          occurrence_id: "occurrence-1",
          event_seq: 1,
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core ready with Gemini-only drafting unavailable",
    );
    expect(screen.getByText(/Demo Workspace active/)).toBeInTheDocument();
    expect(screen.getByText("Process liveness")).toBeInTheDocument();
    expect(screen.getByText("Core readiness")).toBeInTheDocument();
    expect(screen.getByText("Audit occurrence recorded · event 1")).toBeInTheDocument();
    expect(await screen.findByText("Canonical lineage")).toBeInTheDocument();
    expect(await screen.findByText("3 order lines")).toBeInTheDocument();
    expect(await screen.findByText("Canonical fields")).toBeInTheDocument();
    expect(await screen.findByText("committed")).toBeInTheDocument();
    expect(
      await screen.findByText("Source observation register (3)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("SOURCE_DUPLICATE_DEDUPED").length).toBeGreaterThan(0);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
  });

  test("does not expose an internal error when health is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ code: "CORE_STORE_UNAVAILABLE" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core health is unavailable",
    );
    expect(screen.queryByText("CORE_STORE_UNAVAILABLE")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("keeps health available when the audit write is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async (input) => {
      if (input === "/api/health") {
        return new Response(JSON.stringify(healthResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (input === "/api/workspace") {
        return new Response(JSON.stringify(workspaceResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(null, { status: 503 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core ready with Gemini-only drafting unavailable",
    );
    expect(screen.getByText(/Demo Workspace active/)).toBeInTheDocument();
    expect(screen.getByText("Audit occurrence unavailable")).toBeInTheDocument();
  });

  test("does not write an audit occurrence when workspace creation is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async (input) => {
      if (input === "/api/health") {
        return new Response(JSON.stringify(healthResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(null, { status: 503 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Demo Workspace unavailable")).toBeInTheDocument();
    expect(screen.getByText("Audit occurrence unavailable")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/audit/occurrences",
      expect.anything(),
    );
  });
});
