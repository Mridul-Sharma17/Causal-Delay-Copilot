import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const riskSignal = {
  schema_version: "risk-signal.v1",
  trigger_mode: "reactive",
  source: {
    schema_version: "trigger-source-envelope.v1",
    source_system: "bundled-predictive-stub",
    source_payload_sha256: "sha256:risk-signal",
    protected_source_locator: "bundled://risk-signal/hero-reactive-risk-v1",
    data_classification: "generated",
  },
  source_signal_id: "hero-reactive-risk-001",
  source_revision: "v1",
  scored_dataset_version_ref: "sha256:hero-v1",
  source_order_line_ref: { namespace: "semi-synthetic-hero", key: "hero-line-001" },
  predictor_id: "predictive-stub",
  predictor_version: "predictive-stub.v1",
  feature_contract_version: "predictive-features.v1",
  target_definition_id: "supplier_milestone_miss.v1",
  target_milestone_kind: "supplier_handoff",
  score_semantic: "probability_supplier_milestone_miss",
  score_value: 0.78,
  alert_threshold: 0.5,
  flagged: true,
  generated_at: {
    value: "2026-01-10T09:00:00+05:30",
    kind: "instant",
    precision: "minute",
    timezone_status: "known",
    source_timezone: "Asia/Kolkata",
  },
  known_at: {
    value: "2026-01-10T09:05:00+05:30",
    kind: "instant",
    precision: "minute",
    timezone_status: "known",
    source_timezone: "Asia/Kolkata",
  },
  predictor_artifact_ref: { state: "present", value: "bundled://score" },
  predictive_attribution_ref: { state: "present", value: "bundled://attribution" },
  prediction_explanation_ref: { state: "missing" },
  prediction_calibration_ref: { state: "missing" },
  prediction_ranking_ref: { state: "missing" },
  prediction_delivery_metadata: {
    state: "present",
    value: { mode: "bundled_fixture", source_system: "bundled-predictive-stub" },
  },
  advisory_context: null,
};

const reactiveAttemptResponse = {
  result: "CREATED",
  attempt: {
    attempt_id: "attempt-1",
    status: "accepted",
    scope: "reactive_ingress",
    source_system: "bundled-predictive-stub",
    source_signal_id: "hero-reactive-risk-001",
    source_revision: "v1",
    source_payload_sha256: "sha256:risk-signal",
    primary_code: "RISK_SIGNAL_ACCEPTED",
    findings: [],
    evidence_refs: ["risk-signal:bundled-predictive-stub:hero-reactive-risk-001:v1"],
    retryable: false,
    recovery_action: "CONTINUE_TO_ELIGIBILITY_REVIEW",
    received_at: "2026-08-05T00:00:02Z",
    investigation_request_id: "ir-1",
    investigation_request: {
      investigation_request_id: "ir-1",
      schema_version: "investigation-request.v1",
      trigger_mode: "reactive",
      ingress_ref: {
        kind: "RiskSignal",
        source_system: "bundled-predictive-stub",
        source_signal_id: "hero-reactive-risk-001",
        source_revision: "v1",
        source_payload_sha256: "sha256:risk-signal",
        source_order_line_ref: {
          namespace: "semi-synthetic-hero",
          key: "hero-line-001",
        },
      },
      rerun_of_request_id: { state: "missing" },
      dataset_version_id: "sha256:hero-v1",
      subject: { order_line_id: "line-1" },
      decision_cutoff: {
        state: "present",
        value: {
          kind: "instant",
          source_value: "2026-01-05T09:30:00+05:30",
          normalized_value: "2026-01-05T04:00:00+00:00",
          precision: "minute",
          timezone_status: "known",
          source_timezone: { state: "present", value: "Asia/Kolkata" },
        },
      },
      decision_cutoff_source: "canonical_commitment",
      observation_cutoff: {
        state: "present",
        value: {
          kind: "instant",
          source_value: "2026-01-10T09:05:00+05:30",
          normalized_value: "2026-01-10T03:35:00+00:00",
          precision: "minute",
          timezone_status: "known",
          source_timezone: { state: "present", value: "Asia/Kolkata" },
        },
      },
      target_milestone_kind: { state: "present", value: "supplier_handoff" },
      causal_question_version: "supplier-load-slippage.v1",
      engine_configuration_ref: "causal-engine-config.v1",
      ingress_validation_refs: [],
      provenance_refs: ["risk-signal:bundled-predictive-stub:hero-reactive-risk-001:v1"],
      prediction_metadata: { state: "present", value: { score_value: 0.78 } },
      accepted_at: "2026-08-05T00:00:02Z",
      causal_engine_input: {
        causal_input_schema_version: "causal-input-projection.v2",
        dataset_version_id: "sha256:hero-v1",
        subject_analytical_values: {
          supplier_id: { state: "present", value: "supplier-1" },
          original_promise: { state: "unresolved" },
          adjustment_inputs: {},
          subject_exclusion_identity: "line-1",
        },
        decision_cutoff: {
          state: "present",
          value: {
            kind: "instant",
            source_value: "2026-01-05T09:30:00+05:30",
            normalized_value: "2026-01-05T04:00:00+00:00",
            precision: "minute",
            timezone_status: "known",
            source_timezone: { state: "present", value: "Asia/Kolkata" },
          },
        },
        observation_cutoff: {
          state: "present",
          value: {
            kind: "instant",
            source_value: "2026-01-10T09:05:00+05:30",
            normalized_value: "2026-01-10T03:35:00+00:00",
            precision: "minute",
            timezone_status: "known",
            source_timezone: { state: "present", value: "Asia/Kolkata" },
          },
        },
        target_milestone_kind: { state: "present", value: "supplier_handoff" },
        canonical_slippage_duration_basis: "CALENDAR_DAY",
        causal_question_version: "supplier-load-slippage.v1",
        engine_configuration_ref: "causal-engine-config.v1",
        supplier_milestone_outcome: {
          schema_version: "supplier-milestone-slippage.v1",
          state: "not_applicable",
          role: "SUBJECT_LINE",
          canonical_slippage_duration_basis: "CALENDAR_DAY",
          supplier_milestone_slippage_duration_basis: null,
          frozen_promised_milestone: null,
          actual_target_milestone: null,
          supplier_milestone_slippage_days: null,
          supplier_milestone_late: null,
          outcome_code: "OUTCOME_NOT_REQUIRED_FOR_SUBJECT",
          reason_code: "OUTCOME_NOT_REQUIRED_FOR_SUBJECT",
          reason:
            "A current subject is evaluated for eligibility; it is not an estimation line.",
          eligibility_codes: [],
          provenance: {
            selected_promise_event_id: "promise-1",
            promise_event_ids: ["promise-1"],
            selected_actual_event_id: null,
            selected_cancellation_event_id: null,
            contributing_event_ids: ["promise-1"],
            considered_event_ids: ["promise-1"],
          },
          follow_up: null,
          outcome_hash: "sha256:outcome",
        },
        estimator_window_ref: {
          selector_version: "estimator-window.v1",
          bounds: {
            known_at_lower: "unbounded",
            known_at_upper: { state: "unresolved" },
          },
          selected_identity_hash: "sha256:window",
          selected_count: 1,
          subject_removal: {
            subject_identity: "line-1",
            removed: true,
            post_subject_identity_hash: "sha256:empty",
          },
        },
        history_lookback_ref: {
          selector_version: "history-lookback.v1",
          bounds: {
            known_at_lower: "unbounded",
            known_at_upper: { state: "unresolved" },
          },
          selected_identity_hash: "sha256:window",
          selected_count: 1,
          subject_removal: {
            subject_identity: "line-1",
            removed: false,
            post_subject_identity_hash: "sha256:window",
          },
        },
        historical_population_digest: "sha256:population",
        analytical_fact_lineage_refs: [],
      },
      causal_input_digest: "sha256:causal-input",
      content_hash: "sha256:request",
    },
    audit: { occurrence_id: "occurrence-risk-1", event_seq: 2 },
  },
};

const rejectedRiskSignal = {
  ...riskSignal,
  source: {
    ...riskSignal.source,
    protected_source_locator:
      "bundled://risk-signal/hero-reactive-risk-target-mismatch-v1",
  },
  source_signal_id: "hero-reactive-risk-002",
  target_milestone_kind: "supplier_completion",
};

const rejectedReactiveAttemptResponse = {
  result: "CREATED",
  attempt: {
    ...reactiveAttemptResponse.attempt,
    attempt_id: "attempt-2",
    status: "rejected",
    source_signal_id: "hero-reactive-risk-002",
    primary_code: "RISK_SIGNAL_TARGET_MISMATCH",
    recovery_action: "USE_CONFIGURED_SUPPLIER_MILESTONE_TARGET",
    investigation_request_id: null,
    investigation_request: null,
    audit: { occurrence_id: "occurrence-risk-2", event_seq: 3 },
  },
};

const proactiveProposalResponse = {
  items: [
    {
      fixture_id: "hero-proactive-proposal-v1",
      label: "Bundled proactive proposal preview",
      proposal: {
        schema_version: "proactive-proposal.v1",
        trigger_mode: "proactive",
        source: {
          schema_version: "trigger-source-envelope.v1",
          source_system: "bundled-pre-award-hook",
          data_classification: "generated",
        },
        proposal_id: "hero-proposal-001",
        proposal_revision: "v1",
        dataset_version_id: "sha256:hero-v1",
        proposed_supplier_ref: { state: "present", value: "supplier-1" },
        target_milestone_kind: { state: "present", value: "supplier_handoff" },
        proposed_original_promise: { state: "present", value: "2026-02-15" },
        adjustment_inputs: {
          quantity: { state: "present", value: 10 },
        },
        decision_at: {
          state: "present",
          value: {
            kind: "instant",
            source_value: "2026-01-10T09:00:00+05:30",
            normalized_value: "2026-01-10T03:30:00+00:00",
            precision: "minute",
            timezone_status: "known",
            source_timezone: { state: "present", value: "Asia/Kolkata" },
          },
        },
      },
    },
  ],
};

const proactiveAttemptResponse = {
  result: "CREATED",
  attempt: {
    ...reactiveAttemptResponse.attempt,
    attempt_id: "proactive-attempt-1",
    scope: "proactive_ingress",
    source_system: "bundled-pre-award-hook",
    proposal_id: "hero-proposal-001",
    proposal_revision: "v1",
    source_payload_sha256: "sha256:proactive-proposal",
    primary_code: "PROACTIVE_ACCEPTED",
    evidence_refs: ["proactive-proposal:bundled-pre-award-hook:hero-proposal-001:v1"],
    recovery_action: "CONTINUE_TO_PREVIEW_REVIEW",
    investigation_request_id: "proactive-ir-1",
    investigation_request: {
      ...reactiveAttemptResponse.attempt.investigation_request,
      investigation_request_id: "proactive-ir-1",
      trigger_mode: "proactive",
      ingress_ref: {
        kind: "ProactiveProposal",
        source_system: "bundled-pre-award-hook",
        proposal_id: "hero-proposal-001",
        proposal_revision: "v1",
        source_payload_sha256: "sha256:proactive-proposal",
      },
      subject: {
        kind: "proactive_preview",
        preview_subject_digest: "sha256:preview-subject",
        proposal_id: "hero-proposal-001",
        proposal_revision: "v1",
        supplier_id: { state: "present", value: "supplier-1" },
        target_milestone_kind: { state: "present", value: "supplier_handoff" },
        original_promise: { state: "present", value: "2026-02-15" },
        adjustment_inputs: { quantity: { state: "present", value: 10 } },
      },
      decision_cutoff_source: "proactive_decision",
      prediction_metadata: { state: "not_applicable" },
      causal_engine_input: {
        ...reactiveAttemptResponse.attempt.investigation_request.causal_engine_input,
        subject_analytical_values: {
          ...reactiveAttemptResponse.attempt.investigation_request.causal_engine_input
            .subject_analytical_values,
          subject_exclusion_identity: "proactive-preview:sha256:preview-subject",
        },
        estimator_window_ref: {
          ...reactiveAttemptResponse.attempt.investigation_request.causal_engine_input
            .estimator_window_ref,
          subject_removal: {
            subject_identity: "proactive-preview:sha256:preview-subject",
            removed: false,
            post_subject_identity_hash: "sha256:window",
          },
        },
        history_lookback_ref: {
          ...reactiveAttemptResponse.attempt.investigation_request.causal_engine_input
            .history_lookback_ref,
          subject_removal: {
            subject_identity: "proactive-preview:sha256:preview-subject",
            removed: false,
            post_subject_identity_hash: "sha256:window",
          },
        },
      },
    },
    audit: { occurrence_id: "occurrence-proactive-1", event_seq: 4 },
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

      if (typeof input === "string" && input.startsWith("/api/risk-signals")) {
        return new Response(
          JSON.stringify({
            items: [
              {
                fixture_id: "hero-reactive-risk-v1",
                label: "Bundled reactive risk signal",
                signal: riskSignal,
              },
              {
                fixture_id: "hero-reactive-risk-target-mismatch-v1",
                label: "Conformance failure: target mismatch",
                signal: rejectedRiskSignal,
              },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }

      if (typeof input === "string" && input.startsWith("/api/proactive-proposals")) {
        return new Response(JSON.stringify(proactiveProposalResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      if (input === "/api/investigations/reactive/fixtures") {
        expect(init?.method).toBe("POST");
        const submitted = JSON.parse(String(init?.body));
        expect(submitted.dataset_version_id).toBe("sha256:hero-v1");
        if (submitted.fixture_id === "hero-reactive-risk-target-mismatch-v1") {
          return new Response(JSON.stringify(rejectedReactiveAttemptResponse), {
            status: 201,
            headers: { "content-type": "application/json" },
          });
        }
        expect(submitted.fixture_id).toBe("hero-reactive-risk-v1");
        return new Response(JSON.stringify(reactiveAttemptResponse), {
          status: 201,
          headers: { "content-type": "application/json" },
        });
      }

      if (input === "/api/investigations/proactive/fixtures") {
        expect(init?.method).toBe("POST");
        const submitted = JSON.parse(String(init?.body));
        expect(submitted).toEqual({
          dataset_version_id: "sha256:hero-v1",
          fixture_id: "hero-proactive-proposal-v1",
        });
        return new Response(JSON.stringify(proactiveAttemptResponse), {
          status: 201,
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
    expect(await screen.findByText("Investigation request accepted")).toBeInTheDocument();
    expect(await screen.findByText("Proactive preview accepted")).toBeInTheDocument();
    expect(screen.getAllByText("Eligibility stage")).toHaveLength(2);
    expect(screen.getAllByText("CALENDAR_DAY")).toHaveLength(2);
    expect(screen.getAllByText("OUTCOME_NOT_REQUIRED_FOR_SUBJECT")).toHaveLength(2);
    expect(screen.getAllByText(/No slippage estimate is displayed/)).toHaveLength(2);
    expect(screen.getByText("PROACTIVE · PREVIEW-ONLY")).toBeInTheDocument();
    expect(
      screen.getByText(/No canonical Order Line, commitment event, actual milestone/),
    ).toBeInTheDocument();
    expect(screen.getByText("Prediction score")).toBeInTheDocument();
    expect(screen.getByText("Trigger only; excluded from the scientific digest")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Try the rejected conformance fixture" }),
    );
    expect(
      await screen.findByText("Fail-closed path: RISK_SIGNAL_TARGET_MISMATCH"),
    ).toBeInTheDocument();
    expect(await screen.findByText("3 order lines")).toBeInTheDocument();
    expect(await screen.findByText("Canonical fields")).toBeInTheDocument();
    expect(await screen.findByText("committed")).toBeInTheDocument();
    expect(
      await screen.findByText("Source observation register (3)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("SOURCE_DUPLICATE_DEDUPED").length).toBeGreaterThan(0);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(10));
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
