import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App, {
  DecisionSupportActionsStage,
  DecisionSupportProjectionDetails,
  DraftContextPreviewPanel,
} from "./App";
import type {
  DecisionSupportBoundary,
  DecisionSupportOption,
  DecisionSupportRegistryInspection,
  DraftContextPreview,
} from "./contracts";
import { parseDraftContextPreview } from "./contracts";

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

const referenceDeliveryResponse = {
  schema_version: "analysis-run-read-model.v1",
  delivery_mode: "existing_run_reuse",
  delivery_badge: "Validated reference",
  verification_state: "reference_validated",
  reference_slot_id: "ordinary-demo",
  reference_id: "ordinary-demo",
  analysis_run_id: "analysis-run-00000000-0000-4000-8000-000000000001",
  bundle_manifest_hash: "sha256:bundle",
  bundle_ref: "sha256:bundle",
  validation_attestation_id: "attestation-ordinary-demo",
  validation_attestation_ref: "attestation-ordinary-demo",
  release_candidate_id: "local-local_development",
  intended_role: "semi_synthetic_hero",
  engine_result_status: "estimated",
  scientific_request_digest: "sha256:request",
  dataset_version_id: "sha256:hero-v1",
  runtime_fingerprint_digest: "sha256:runtime",
  validation_policy_version: "release-validation.v1",
  validated_at: "2026-08-05T00:00:00Z",
  diagnostics: [
    {
      schema_version: "diagnostic-result.v1",
      diagnostic_id: "primary_interval",
      diagnostic_version: "1",
      scope: "population",
      status: "UNAVAILABLE",
      policy_id: "causal-validity-verdict-policy",
      policy_version: "1",
      rule_id: "primary-interval-sign",
      rule_version: "1",
      observed: null,
      threshold: { null: 0 },
      result: null,
      verdict_effect: "NONE",
      trigger_codes: [],
      reason_code: "PRIMARY_INTERVAL_UNAVAILABLE",
      reason: "The verified evidence bundle contains no primary interval.",
      analysis_run_id: "analysis-run-00000000-0000-4000-8000-000000000001",
      bundle_manifest_hash: "sha256:bundle",
      evidence_refs: ["diagnostic_artifacts:diagnostic_artifacts"],
      input_refs: ["diagnostic_artifacts:diagnostic_artifacts"],
      diagnostic_identity: "sha256:diagnostic-identity",
      content_hash: "sha256:diagnostic-content",
    },
  ],
  diagnostic_summary: {
    state: "limited",
    diagnostic_count: 1,
    status_counts: { UNAVAILABLE: 1 },
  },
  robustness_grade: {
    schema_version: "robustness-grade.v1",
    grade: "STRONG",
    benchmark_group_refs: ["supplier_history"],
    strongest_group_ref: "supplier_history",
    median_group_ref: "supplier_history",
    strongest_adjusted_ci_lower: 0.2,
    median_adjusted_ci_lower: 0.2,
    content_hash: "sha256:robustness",
  },
  evidence_verdict: {
    schema_version: "evidence-verdict.v2",
    scope: "population",
    verdict_code: "SUPPORTED_UNDER_ASSUMPTIONS",
    insufficient_evidence_reason_class: null,
    intended_role: "semi_synthetic_hero",
    permitted_claim_scope: "population_and_subject",
    subject_application_role_permitted: true,
    decision_support_role_permitted: true,
    decision_support_evaluation_permitted: true,
    population_verdict_ref: null,
    robustness_grade_ref: "sha256:robustness",
    effect_display: "CAUSAL_ESTIMATE",
    effect_result_ref: "engine_result:primary",
    canonical_unit: "days",
    canonical_slippage_duration_basis: "CALENDAR_DAY",
    effect: {
      estimate: 1.5,
      ci_lower: 0.2,
      ci_upper: 2.8,
    },
    primary_trigger_code: "EVIDENCE_POLICY_PASSED",
    trigger_codes: ["EVIDENCE_POLICY_PASSED"],
    next_step_template_id: "validity-next-step-templates:evidence_policy_passed",
    next_step_template_ids: ["validity-next-step-templates:evidence_policy_passed"],
    language_policy_id: "causal-validity-language-policy",
    content_hash: "sha256:verdict",
  },
  rendered_verdict: {
    language:
      "High-Load Exposure is estimated to increase Supplier Milestone Slippage by 1.5 calendar days (95% interval 0.2 to 2.8), under the stated assumptions.",
    next_step:
      "Evaluate eligible Intervention Options under the separate Decision Support contract.",
    primary_trigger_label: "evidence policy passed",
    next_step_template_id: "validity-next-step-templates:evidence_policy_passed",
  },
};

const decisionBriefSnapshotResponse = {
  schema_version: "decision-brief-snapshot.v2",
  snapshot_id: "snapshot-1",
  investigation_request_id: "ir-1",
  reference_id: "ordinary-demo",
  content_hash: "sha256:decision-brief",
  occurrence_id: "occurrence-decision-brief-1",
  event_seq: 4,
  created_at: "2026-08-05T00:00:03Z",
  subject_applicability: {
    schema_version: "subject-applicability.v1",
    state: "abstained",
    subject_identity: "hero-line-001",
    subject_profile: { material_class: { state: "present", value: "switchgear" } },
    subject_profile_hash: "sha256:subject-profile",
    population_permission: true,
    source_role_ceiling: true,
    gates: [
      { gate: "subject_profile", state: "passed", code: null },
      { gate: "propensity_support", state: "unavailable", code: "SUBJECT_PROPENSITY_UNAVAILABLE" },
      { gate: "distribution_support", state: "failed", code: "SUBJECT_DISTRIBUTION_UNSUPPORTED" },
    ],
    reason_code: "SUBJECT_PROPENSITY_UNAVAILABLE",
    reason: "Subject applicability is unavailable because subject propensity unavailable.",
    next_step: "Supply the frozen subject propensity support before applying population evidence.",
    claim_scope: "population",
  },
  subject_verdict: null,
  rendered_subject_verdict: null,
  action_lane: {
    schema_version: "reference-journey-action-lane.v1",
    state: "read_only",
    reason: "Subject applicability is insufficient; no action is authorized from this reference journey.",
    next_step: "Supply the frozen subject propensity support before applying population evidence.",
  },
  decision_support: {
    schema_version: "decision-support-boundary.v1",
    outcome: "NOT_PERMITTED",
    state: "not_permitted",
    primary_reason_code: "SUBJECT_PROPENSITY_UNAVAILABLE",
    reason: "Subject applicability is unavailable because subject propensity unavailable.",
    next_step: "Supply the frozen subject propensity support before applying population evidence.",
    permission: {
      decision_support_evaluation_permitted: false,
      denial_reason_code: "SUBJECT_PROPENSITY_UNAVAILABLE",
      reason: "Subject applicability is unavailable because subject propensity unavailable.",
      next_step: "Supply the frozen subject propensity support before applying population evidence.",
    },
    subject_driver_state: null,
    decision_support_evaluation_id: null,
    decision_support_evaluation_series_id: null,
    decision_support_permission_digest: null,
    decision_support_driver_state_digest: null,
    options: [],
    evidence_tags: {
      DRIVER_EVIDENCE: "NOT_EVALUATED",
      MECHANISTIC_LINK: "NOT_EVALUATED",
      RULE_BASED_ELIGIBILITY: "NOT_EVALUATED",
      ASSUMPTION_BASED_BENEFIT: "NOT_EVALUATED",
    },
    suppression_reasons: [
      {
        code: "SUBJECT_PROPENSITY_UNAVAILABLE",
        category: "PERMISSION",
        priority: 100,
        reason: "Subject applicability is unavailable because subject propensity unavailable.",
      },
    ],
    action_effect_evidence: "INTERVENTION_EFFECT_NOT_ESTIMATED",
    action_recommendation: null,
    tradeoff: null,
    monitoring: { state: "NOT_EVALUATED" },
    drafting: { state: "NOT_PERMITTED" },
    authorization: { state: "NOT_PERMITTED" },
    consumed_inputs: ["permission_envelope"],
    content_hash: "sha256:decision-support",
  },
  decision_support_registry: {
    inspection_kind: "GOVERNED_RECORD_INSPECTION",
    effect_bearing: false,
    consumed_by_evaluation: false,
    release_binding: {
      state: "BUNDLED_RELEASE_BOUND",
      release_candidate_id: "local-local_development",
      runtime_fingerprint_digest: "sha256:runtime",
    },
    intervention_library: {
      identifier: "core-intervention-library",
      version: "1",
      state: "BUNDLED_CLOSED",
      options: [
        {
          option_code: "PROTECTED_PRODUCTION_SLOT",
          option_version: "1",
          lifecycle_status: "ACTIVE",
        },
      ],
    },
    driver_action_links: [
      { link_id: "dal:protected-production-slot:reactive", review_status: "PROVISIONAL" },
    ],
    advisory_rubrics: [
      { rubric_id: "rubric:protected-production-slot", state: "UNAVAILABLE_PENDING_REVIEW" },
    ],
    monitoring_triggers: [
      { trigger_id: "trigger:accept-and-monitor:reactive", state: "UNAVAILABLE_PENDING_REVIEW" },
    ],
    composite_reviews: [
      {
        option_code: "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
        state: "UNAVAILABLE_PENDING_REVIEW",
      },
    ],
  },
  investigation_request: {
    investigation_request_id: "ir-1",
    content_hash: "sha256:request",
  },
  ingress_attempt: {
    attempt_id: "attempt-1",
    record_hash: "sha256:attempt",
  },
  lineage: {
    dataset_version_id: "dataset-1",
    content_hash: "sha256:lineage",
  },
  reference: {
    reference_id: "ordinary-demo",
    verification_state: "reference_validated",
  },
  referenced_records: {
    investigation_request: { content_hash: "sha256:request" },
    ingress_attempt: { content_hash: "sha256:attempt" },
    lineage: { content_hash: "sha256:lineage" },
    validated_reference: { content_hash: "sha256:reference" },
  },
  presentation: {
    schema_version: "reference-journey-presentation.v1",
  },
};

const projectionOption: DecisionSupportOption = {
  option_code: "PROTECTED_PRODUCTION_SLOT",
  option_version: "1",
  label: "Protected production slot",
  evaluation_state: "ACTIVE",
  evidence_tags: {
    DRIVER_EVIDENCE: "SUPPORTED_UNDER_ASSUMPTIONS",
    MECHANISTIC_LINK: "REVIEWED_PLAUSIBLE",
    RULE_BASED_ELIGIBILITY: "SATISFIED",
    ASSUMPTION_BASED_BENEFIT: "EXPOSURE_TRANSLATION_ASSUMPTION",
  },
  action_effect_evidence: "INTERVENTION_EFFECT_NOT_ESTIMATED",
  suppression_reasons: [],
  value_status: "ROBUSTLY_POSITIVE",
  benefit_projection: {
    disclosure: "ASSUMPTION_BASED_PROJECTION_RANGE",
    recovered_supplier_milestone_days: {
      lower: { numerator: "12", denominator: "5" },
      central: { numerator: "4", denominator: "1" },
      upper: { numerator: "28", denominator: "5" },
    },
    project_delay_days_protected: {
      lower: { numerator: "12", denominator: "5" },
      central: { numerator: "4", denominator: "1" },
      upper: { numerator: "28", denominator: "5" },
    },
    net_assumption_value: {
      lower: { numerator: "90000", denominator: "1" },
      central: { numerator: "250000", denominator: "1" },
      upper: { numerator: "410000", denominator: "1" },
    },
    schedule_protection: {
      basis: "PROJECT_DELAY_DAYS",
      duration_basis: "CALENDAR_DAY",
      central: { numerator: "4", denominator: "1" },
    },
    currency: "INR",
  },
  assumptions: {
    recoverable_fraction: { selected: { selected_value: { numerator: "2", denominator: "5" } } },
  },
  costs: {
    direct_action_cost: { amount: { numerator: "150000", denominator: "1" }, currency: "INR" },
  },
  caveats: ["INTERVENTION_EFFECT_NOT_ESTIMATED"],
  unavailable_reasons: [
    { code: "EXAMPLE_UNAVAILABLE", reason: "A governed input is unavailable." },
  ],
};

const replayResponse = {
  schema_version: "replay.v1",
  status: "REPLAYED",
  investigation_request_id: "ir-1",
  requested_event_seq: 4,
  last_verified_event_seq: 4,
  snapshot: decisionBriefSnapshotResponse,
  historical_state: {
    schema_version: "historical-replay.v1",
    investigation_request_id: "ir-1",
    cutoff_event_seq: 4,
    historical: true,
    read_only: true,
    known: {},
    evidence: { subject_verdict: null, evaluation: null },
    recommendation: { state: "NOT_PUBLISHED", reference: null },
    tradeoff_selection: { state: "NOT_PUBLISHED" },
    draft: { state: "NOT_PUBLISHED", source: null, fallback: null, head: null, edits: [] },
    disposition: { state: "NOT_RECORDED" },
    decision: { state: "NOT_RECORDED", record: null },
    references: {},
    occurrences: [],
    presentation: { mode: "HISTORICAL_READ_ONLY" },
  },
  unresolved_references: [],
  recovery_action: "NONE",
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
    source_role_ceiling: {
      label: "Construction demonstration",
      permitted_claim_scope: "construction_demonstration",
      subject_application_role_permitted: true,
      decision_support_evaluation_permitted: true,
    },
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
    source_role_ceiling: {
      label: "Construction demonstration",
      permitted_claim_scope: "construction_demonstration",
      subject_application_role_permitted: true,
      decision_support_evaluation_permitted: true,
    },
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

describe("Decision Support projection disclosure", () => {
  afterEach(cleanup);

  test("shows exact ranges, assumptions, caveats, tags, and unavailable reasons", () => {
    render(<DecisionSupportProjectionDetails option={projectionOption} />);

    expect(screen.getByText("Assumption-based projections")).toBeInTheDocument();
    expect(screen.getByText("ROBUSTLY_POSITIVE")).toBeInTheDocument();
    expect(screen.getByText("ASSUMPTION_BASED_PROJECTION_RANGE")).toBeInTheDocument();
    expect(screen.getByText("Recovered supplier-milestone days")).toBeInTheDocument();
    expect(screen.getByText(/EXPOSURE_TRANSLATION_ASSUMPTION/)).toBeInTheDocument();
    expect(screen.getByText("INTERVENTION_EFFECT_NOT_ESTIMATED")).toBeInTheDocument();
    expect(screen.getByText("EXAMPLE_UNAVAILABLE")).toBeInTheDocument();
  });
});

describe("Deterministic DraftContext preview", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("shows a checked unsent draft and complete provenance without authorization controls", () => {
    const preview = {
      schema_identifier: "deterministic-draft-preview",
      schema_version: "1",
      state: "UNSENT_PREVIEW",
      currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
      draft_context: {
        provenance: {
          action_recommendation: {
            reference: "action-recommendation:1",
            content_hash: "sha256:" + "a".repeat(64),
          },
        },
      },
      artifact: {
        state: "UNSENT_PREVIEW",
        source: "DETERMINISTIC_ZERO_LLM",
        body: "Subject: Review request: Protected production slot",
        provenance: { currentness_check: "currentness-check:1" },
      },
      checker: { state: "PASS", failure_codes: [] },
    } as unknown as DraftContextPreview;

    render(<DraftContextPreviewPanel preview={preview} />);

    expect(screen.getByText("Deterministic unsent draft preview")).toBeInTheDocument();
    expect(screen.getByText(/Subject: Review request: Protected production slot/)).toBeInTheDocument();
    expect(screen.getByText(/This content is a preview only/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /authorize|send|approve/i })).not.toBeInTheDocument();
  });

  test("shows the bounded provider path and fallback audit state", () => {
    const preview = {
      schema_identifier: "deterministic-draft-preview",
      schema_version: "1",
      state: "UNSENT_PREVIEW",
      currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
      draft_context: { provenance: {} },
      drafting: {
        source: "DETERMINISTIC_ZERO_LLM",
        cache: "DISABLED",
        fallback: { used: true, reason_code: "PROVIDER_FAILURE" },
      },
      artifact: {
        state: "UNSENT_PREVIEW",
        source: "DETERMINISTIC_ZERO_LLM",
        body: "Subject: Review request",
        provenance: {},
      },
      checker: { state: "PASS", failure_codes: [] },
    } as unknown as DraftContextPreview;

    render(<DraftContextPreviewPanel preview={preview} />);

    expect(screen.getByText(/Drafting path:/)).toHaveTextContent("DETERMINISTIC_ZERO_LLM");
    expect(screen.getByText(/Drafting path:/)).toHaveTextContent("DISABLED");
    expect(screen.getByText(/Fallback:/)).toHaveTextContent("PROVIDER_FAILURE");
  });

  test("labels checked Gemini prose separately from the deterministic renderer", () => {
    const preview = {
      schema_identifier: "deterministic-draft-preview",
      schema_version: "1",
      state: "UNSENT_PREVIEW",
      currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
      draft_context: { provenance: {} },
      drafting: { source: "GEMINI_CHECKED", cache: "DISABLED" },
      artifact: {
        state: "UNSENT_PREVIEW",
        source: "GEMINI_CHECKED",
        body: "Subject: Review request",
        provenance: {},
      },
      checker: { state: "PASS", failure_codes: [] },
    };

    const parsed = parseDraftContextPreview(preview);
    render(<DraftContextPreviewPanel preview={parsed} />);

    expect(screen.getByText("Checked Gemini unsent draft preview")).toBeInTheDocument();
    expect(screen.queryByText("Deterministic unsent draft preview")).not.toBeInTheDocument();
    expect(screen.getByText(/Drafting path:/)).toHaveTextContent("GEMINI_CHECKED");
  });

  test("prepares the preview through the current-advice endpoint", async () => {
    const baseBoundary = decisionBriefSnapshotResponse.decision_support as unknown as DecisionSupportBoundary;
    const recommendation = {
      occurrence_id: "action-recommendation:recommendation-1",
      content_hash: "sha256:recommendation",
      selected_option_code: "PROTECTED_PRODUCTION_SLOT",
      selected_option_version: "1",
      selection_basis: "SOLE_ELIGIBLE_OPTION",
      authorization: { state: "NOT_RECORDED" },
      runner_up: null,
      evaluation_published_at: "2026-08-09T10:02:00+00:00",
    };
    const evaluationLifecycle = {
      schema_version: "decision-support-evaluation-read-model.v1",
      evaluation_series_id: "series-1",
      head: { head_kind: "EVALUATION", advice_state: "current" },
      history: [
        {
          record_type: "evaluation",
          record_state: "current",
          evaluation_occurrence_id: "evaluation-1",
          evaluation_digest: "sha256:evaluation",
          terminal_result_ref_and_hash: {
            reference: "decision-support-result:evaluation-1",
            content_hash: "sha256:terminal",
          },
          evaluation_published_at: "2026-08-09T10:02:00+00:00",
        },
      ],
    };
    const recommendationBoundary = {
      ...baseBoundary,
      outcome: "RECOMMENDATION_AVAILABLE",
      state: "recommendation_available",
      decision_support_evaluation_id: "evaluation-1",
      action_recommendation: recommendation,
      tradeoff: null,
      evaluation_lifecycle: evaluationLifecycle,
    } as DecisionSupportBoundary;
    const preview = {
      schema_identifier: "deterministic-draft-preview",
      schema_version: "1",
      state: "UNSENT_PREVIEW",
      currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
      draft_context: { provenance: { action_recommendation: recommendation } },
      artifact: {
        state: "UNSENT_PREVIEW",
        source: "DETERMINISTIC_ZERO_LLM",
        body: "Subject: Review request: Protected production slot",
        provenance: { currentness_check: "currentness-check:1" },
      },
      checker: { state: "PASS", failure_codes: [] },
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(preview), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DecisionSupportActionsStage
        boundary={recommendationBoundary}
        registryInspection={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Prepare deterministic unsent draft" }));
    await waitFor(() =>
      expect(screen.getByText("Deterministic unsent draft preview")).toBeInTheDocument(),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/decision-support/draft-context");
    const submitted = JSON.parse(String(init?.body)) as {
      current_advice: Record<string, unknown>;
    };
    expect(submitted.current_advice).toMatchObject({
      render_mode: "CURRENT_ADVICE",
      evaluation_series_id: "series-1",
      evaluation_occurrence_id: "evaluation-1",
      advice_chain_kind: "IMMEDIATE_EVALUATION_RECOMMENDATION",
      recommendation_ref_and_hash_or_null: {
        reference: recommendation.occurrence_id,
        content_hash: recommendation.content_hash,
      },
    });
    expect(screen.queryByRole("button", { name: /authorize|send|approve/i })).not.toBeInTheDocument();
  });

  test("shows persisted editing and non-authorizing disposition controls", async () => {
    const draft = {
      schema_identifier: "draft-version",
      schema_version: "1",
      draft_id: "draft-1",
      version_number: 1,
      occurrence_id: "draft-version:draft-1:1",
      predecessor_ref_and_hash_or_null: null,
      source: "DETERMINISTIC_ZERO_LLM",
      source_artifact_ref_and_hash: {
        reference: "drafted-artefact:1",
        content_hash: "sha256:" + "a".repeat(64),
      },
      draft_context_ref_and_hash: {
        reference: "draft-context:1",
        content_hash: "sha256:" + "b".repeat(64),
      },
      deterministic_sections: { opening: "Hello" },
      generated_sections: null,
      manager_edits: { changed_fields: [] },
      manager_actor_ref: "anonymous-demo-manager",
      available_at: "2026-08-09T10:03:00+00:00",
      recommendation_ref_and_hash: {
        reference: "action-recommendation:1",
        content_hash: "sha256:" + "c".repeat(64),
      },
      evidence_ref_and_hash: {
        reference: "decision-support-result:evaluation-1",
        content_hash: "sha256:" + "d".repeat(64),
      },
      subject: "Review request",
      recipient: "[APPROVED_RECIPIENT]",
      body: "Subject: Review request\nTo: [APPROVED_RECIPIENT]\n\nHello,",
      disposition: "NOT_DISPOSED",
      rejection_reason: null,
      manager_operation: null,
      authorization_state: "NOT_AUTHORIZED",
      execution_state: "NOT_EXECUTED",
      content_hash: "sha256:" + "e".repeat(64),
    };
    const editedDraft = {
      ...draft,
      version_number: 2,
      occurrence_id: "draft-version:draft-1:2",
      predecessor_ref_and_hash_or_null: {
        reference: draft.occurrence_id,
        content_hash: draft.content_hash,
      },
      body: `${draft.body} Please review this with the team.`,
      manager_edits: { changed_fields: ["body"] },
      content_hash: "sha256:" + "f".repeat(64),
    };
    const approvedDraft = {
      ...editedDraft,
      version_number: 3,
      occurrence_id: "draft-version:draft-1:3",
      predecessor_ref_and_hash_or_null: {
        reference: editedDraft.occurrence_id,
        content_hash: editedDraft.content_hash,
      },
      disposition: "APPROVE_INTENT",
      manager_edits: { changed_fields: [] },
      content_hash: "sha256:" + "1".repeat(64),
    };
    const preview = {
      schema_identifier: "deterministic-draft-preview",
      schema_version: "1",
      state: "UNSENT_PREVIEW",
      currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
      draft_context: { provenance: {} },
      artifact: {
        state: "UNSENT_PREVIEW",
        source: "DETERMINISTIC_ZERO_LLM",
        subject: draft.subject,
        body: draft.body,
        provenance: {},
      },
      checker: { state: "PASS", failure_codes: [] },
      draft,
    } as unknown as DraftContextPreview;
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ draft: editedDraft }), { status: 201 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ draft: approvedDraft }), { status: 201 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            result: "CREATED",
            decision: {
              disposition: "APPROVE",
              authorization_state: "AUTHORIZED",
              execution_state: "NOT_EXECUTED",
              no_send: true,
              no_send_language: "No message was sent and no action was executed.",
              draft_version_ref_and_hash: {
                reference: approvedDraft.occurrence_id,
                content_hash: approvedDraft.content_hash,
              },
              recommendation_ref_and_hash: approvedDraft.recommendation_ref_and_hash,
              evidence_ref_and_hash: approvedDraft.evidence_ref_and_hash,
              currentness_outcome_or_null: "CURRENTNESS_PROVEN_AT_CHECK",
            },
            snapshot: {},
            draft: approvedDraft,
            authorization_attempt: {},
            authorization_currentness: {},
            operation: {},
            currentness: { currentness_outcome: "CURRENTNESS_PROVEN_AT_CHECK" },
            terminal_claim: {},
          }),
          { status: 201 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<DraftContextPreviewPanel preview={preview} />);

    expect(screen.getByText(/Version 1/)).toBeInTheDocument();
    expect(screen.getByLabelText("Subject")).toHaveValue("Review request");
    expect(screen.getByRole("button", { name: "Approve draft" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject with reason" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigate further" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Draft body"), {
      target: { value: `${draft.body} Please review this with the team.` },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save immutable draft edit" }));
    await waitFor(() => expect(screen.getByText(/successor version 2/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      body: editedDraft.body,
      expected_head_ref_and_hash: {
        reference: draft.occurrence_id,
        content_hash: draft.content_hash,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Approve draft" }));
    await waitFor(() => expect(screen.getByText(/Approval intent was recorded only/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      disposition: "APPROVE",
      expected_head_ref_and_hash: {
        reference: editedDraft.occurrence_id,
        content_hash: editedDraft.content_hash,
      },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Authorize and record Manager Decision" }),
    );
    await waitFor(() =>
      expect(
        screen.getByText(/Manager authorization was recorded from a fresh exact currentness proof/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("No message was sent and no action was executed.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      disposition: "APPROVE",
      expected_head_ref_and_hash: {
        reference: approvedDraft.occurrence_id,
        content_hash: approvedDraft.content_hash,
      },
    });
  });
});

describe("Decision Support publication states", () => {
  afterEach(cleanup);

  test("distinguishes a recommendation from an unresolved manager trade-off", () => {
    const baseBoundary = decisionBriefSnapshotResponse.decision_support as unknown as DecisionSupportBoundary;
    const recommendationBoundary = {
      ...baseBoundary,
      outcome: "RECOMMENDATION_AVAILABLE",
      state: "recommendation_available",
      action_recommendation: {
        selected_option_code: "PROTECTED_PRODUCTION_SLOT",
        selection_basis: "SOLE_ELIGIBLE_OPTION",
        runner_up: null,
      },
      tradeoff: null,
      evaluation_lifecycle: {
        schema_version: "decision-support-evaluation-read-model.v1",
        evaluation_series_id: "series-1",
        head: {
          head_kind: "PERMISSION_INVALIDATION",
          advice_state: "invalidated",
        },
        history: [
          { record_type: "evaluation", record_state: "invalidated" },
          { record_type: "advice", record_state: "non-head" },
        ],
      },
    } as DecisionSupportBoundary;

    render(
      <DecisionSupportActionsStage
        boundary={recommendationBoundary}
        registryInspection={null}
      />,
    );

    expect(screen.getByText("Recommendation available")).toBeInTheDocument();
    expect(screen.getByText("NOT_RECORDED")).toBeInTheDocument();
    expect(screen.getByText("PROTECTED_PRODUCTION_SLOT")).toBeInTheDocument();
    expect(screen.getByText("PERMISSION_INVALIDATION")).toBeInTheDocument();
    expect(screen.getByText("invalidated")).toBeInTheDocument();

    cleanup();

    const tradeoffBoundary = {
      ...baseBoundary,
      outcome: "TRADEOFF_REQUIRES_MANAGER_CHOICE",
      state: "tradeoff_requires_choice",
      action_recommendation: null,
      tradeoff: {
        pivot: "DIRECT_ACTION_COST",
        candidates: [
          { option_code: "PROTECTED_PRODUCTION_SLOT", ordering_evidence: "A" },
          { option_code: "EXPEDITED_SUPPLIER_ESCALATION", ordering_evidence: "B" },
        ],
      },
    } as DecisionSupportBoundary;

    render(
      <DecisionSupportActionsStage
        boundary={tradeoffBoundary}
        registryInspection={null}
      />,
    );

    expect(screen.getByText("Two-candidate trade-off")).toBeInTheDocument();
    expect(screen.getByText(/No candidate is recommended/)).toBeInTheDocument();
    expect(screen.getByText("DIRECT_ACTION_COST")).toBeInTheDocument();
  });

  test("discloses a monitoring match as manager review without an action effect", () => {
    const baseBoundary = decisionBriefSnapshotResponse.decision_support as unknown as DecisionSupportBoundary;
    const monitoringBoundary = {
      ...baseBoundary,
      outcome: "RECOMMENDATION_AVAILABLE",
      state: "recommendation_available",
      action_recommendation: {
        selected_option_code: "ACCEPT_AND_MONITOR",
        selected_option_version: "1",
        selection_basis: "MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION",
        trigger_mode: "PROACTIVE",
        runner_up: null,
      },
      monitoring: { state: "ELIGIBLE_FALLBACK", suppression_reasons: [] },
      evaluation_lifecycle: {
        schema_version: "decision-support-evaluation-read-model.v1",
        evaluation_series_id: "series-monitoring",
        head: { head_kind: "EVALUATION", advice_state: "current" },
        history: [],
        currentness: {
          consuming_results: [
            {
              schema_identifier: "monitoring-match-result",
              match_outcome: "REQUEST_MANAGER_REVIEW",
            },
          ],
        },
      },
    } as DecisionSupportBoundary;

    render(
      <DecisionSupportActionsStage
        boundary={monitoringBoundary}
        registryInspection={
          {
            monitoring_triggers: [
              { trigger_mode: "REACTIVE", state: "APPROVED" },
              { trigger_mode: "PROACTIVE", state: "APPROVED" },
            ],
          } as unknown as DecisionSupportRegistryInspection
        }
      />,
    );

    expect(screen.getByText("Governed monitoring fallback")).toBeInTheDocument();
    expect(screen.getByText("REQUEST_MANAGER_REVIEW")).toBeInTheDocument();
    expect(
      screen.getByText(/does not select, authorize, send, or execute an action/),
    ).toBeInTheDocument();
  });
});

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

      if (input === "/api/evidence/reference") {
        return new Response(JSON.stringify(referenceDeliveryResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      if (typeof input === "string" && input.startsWith("/api/datasets/")) {
        expect(input).toBe(
          `/api/datasets/${referenceDeliveryResponse.dataset_version_id}/lineage`,
        );
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

      if (
        typeof input === "string" &&
        input.startsWith("/api/investigations/ir-1/decision-brief")
      ) {
        expect(init?.method).toBe("POST");
        return new Response(
          JSON.stringify({ result: "CREATED", snapshot: decisionBriefSnapshotResponse }),
          { status: 201, headers: { "content-type": "application/json" } },
        );
      }

      if (typeof input === "string" && input.startsWith("/api/audit/replay?")) {
        expect(input).toContain("investigation_request_id=ir-1");
        expect(input).toContain("event_seq=4");
        return new Response(JSON.stringify(replayResponse), {
          status: 200,
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

      if (input === "/api/operations") {
        expect(init?.method).toBe("POST");
        return new Response(
          JSON.stringify({
            result: "CREATED",
            operation: {
              schema_version: "durable-operation.v1",
              operation_id: "operation-fresh-estimated",
              operation_kind: "FRESH_ANALYSIS",
              state: "SUCCEEDED",
              status: "SUCCEEDED",
              queue_position: null,
              created_at: "2026-08-05T00:00:04Z",
              queued_at: "2026-08-05T00:00:04Z",
              started_at: "2026-08-05T00:00:04Z",
              finished_at: "2026-08-05T00:00:05Z",
              cancel_requested_at: null,
              retry_of_operation_id: null,
              failure_code: null,
              recovery_action: null,
              resource_warnings: [],
              artifact_state: "PUBLISHED",
              retryable: false,
              timeout_seconds: 300,
              thread_cap: 1,
              memory_required_bytes: 1024,
              memory_available_bytes: 2048,
              disk_free_bytes: 2 * 1024 * 1024 * 1024,
              analysis_run: {
                schema_version: "analysis-run-status.v1",
                analysis_run_id: "analysis-run-fresh-estimated",
                occurrence_id: "operation-fresh-estimated",
                operation_id: "operation-fresh-estimated",
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
                scientific_request_digest: "sha256:fresh-request",
                runtime_fingerprint: {},
                runtime_fingerprint_digest: "sha256:fresh-runtime",
                root_seed: 0,
                derived_seed_registry: [],
                estimator_descriptor: {},
                feature_descriptor: {},
                fold_descriptor: {},
                fresh_run_detail: {},
                bundle_manifest_hash: "sha256:fresh-bundle",
                diagnostics: referenceDeliveryResponse.diagnostics,
                diagnostic_summary: referenceDeliveryResponse.diagnostic_summary,
                robustness_grade: referenceDeliveryResponse.robustness_grade,
                evidence_verdict: referenceDeliveryResponse.evidence_verdict,
                rendered_verdict: referenceDeliveryResponse.rendered_verdict,
                subject_verdict: null,
                rendered_subject_verdict: null,
                primary_result: {
                  schema_version: "fresh-primary-result.v2",
                  state: "sealed",
                  primary_atte: {
                    estimate: 1.5,
                    ci_lower: 0.4,
                    ci_upper: 2.6,
                    duration_basis: "CALENDAR_DAY",
                  },
                  context_ate: {
                    estimate: 1.2,
                    ci_lower: 0.3,
                    ci_upper: 2.1,
                    duration_basis: "CALENDAR_DAY",
                  },
                  sensitivity_results: {
                    sensitivity_stricter_atte_slippage: {
                      variant_id: "stricter_threshold",
                      status: "estimated",
                      state: "estimated",
                      estimand_id: "sensitivity_stricter_atte_slippage",
                      score: "ATTE",
                      estimate: 1.4,
                      ci_lower: 0.2,
                      ci_upper: 2.7,
                      duration_basis: "CALENDAR_DAY",
                      provenance: {
                        threshold_rule_ref: "nearest-rank-percentile-0.75.v1",
                        selector_refs: ["history-lookback.v1", "estimator-window.v1"],
                        s8_identity_hash: "sha256:strict-s8",
                        s9_identity_hash: "sha256:strict-s9",
                        seed_registry_digest: "sha256:strict-seeds",
                        root_seed: 0,
                        evidence_refs: ["lineage:strict-variant"],
                      },
                    },
                    sensitivity_short_history_atte_slippage: {
                      variant_id: "short_history",
                      status: "unsupported",
                      state: "unsupported",
                      reason_code: "COHORT_SUPPORT_INSUFFICIENT",
                      effect: null,
                      provenance: {
                        threshold_rule_ref: "nearest-rank-percentile-0.67.v1",
                        selector_refs: ["history-lookback-5.v1"],
                        seed_registry_digest: "sha256:short-seeds",
                        root_seed: 0,
                      },
                    },
                  },
                  permission: {
                    evidence_verdict: true,
                    action_permission: true,
                    state: "sealed_machine_verified",
                    claim_scope: "population_and_subject",
                    effect_display: "CAUSAL_ESTIMATE",
                  },
                },
              },
            },
          }),
          { status: 202, headers: { "content-type": "application/json" } },
        );
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
    expect(
      await screen.findByText("Existing run reused. No fresh scientific execution occurred."),
    ).toBeInTheDocument();
    expect(screen.getByText("ordinary-demo")).toBeInTheDocument();
    expect(await screen.findByText("Diagnostic summary")).toBeInTheDocument();
    expect(screen.getByText("Supported under stated assumptions")).toBeInTheDocument();
    expect(screen.getByText("population claim scope")).toBeInTheDocument();
    expect(
      screen.getByText(/High-Load Exposure is estimated to increase Supplier Milestone Slippage/),
    ).toBeInTheDocument();
    expect(screen.getByText("Robustness Grade")).toBeInTheDocument();
    expect(screen.getByText("Limited diagnostic evidence")).toBeInTheDocument();
    const diagnosticSummary = screen.getByText("Open diagnostic details (1)");
    expect(diagnosticSummary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(diagnosticSummary);
    expect(screen.getByText(/UNAVAILABLE — no verified result/)).toBeInTheDocument();
    expect(screen.getByText("Audit occurrence recorded · event 1")).toBeInTheDocument();
    expect(await screen.findByText("Canonical lineage")).toBeInTheDocument();
    expect(await screen.findByText("Investigation request accepted")).toBeInTheDocument();
    expect(await screen.findByText("Subject applicability")).toBeInTheDocument();
    expect(await screen.findByText("Actions stage")).toBeInTheDocument();
    expect(screen.getByText("No Decision Support evaluation was created.")).toBeInTheDocument();
    expect(screen.getByText("Inspect governed Decision Support records")).toBeInTheDocument();
    expect(screen.getByText("INTERVENTION_EFFECT_NOT_ESTIMATED")).toBeInTheDocument();
    expect(screen.getByText("Insufficient subject support — abstained")).toBeInTheDocument();
    expect(screen.getByText(/Replay verified from stored state at event 4/)).toBeInTheDocument();
    expect(screen.getByText("Exact read-only state at event 4")).toBeInTheDocument();
    expect(screen.getByText("Trade-off selection")).toBeInTheDocument();
    expect(await screen.findByText("Proactive preview accepted")).toBeInTheDocument();
    expect(screen.getAllByText("Eligibility stage")).toHaveLength(2);
    expect(screen.getAllByText("CALENDAR_DAY")).toHaveLength(3);
    expect(screen.getAllByText("OUTCOME_NOT_REQUIRED_FOR_SUBJECT")).toHaveLength(2);
    expect(screen.getAllByText(/No slippage estimate is displayed/)).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Request fresh analysis" }));
    expect(
      await screen.findByText(
        /Fresh request completed with a machine-verified sealed evidence bundle/,
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText("Sealed fresh-run result")).toBeInTheDocument();
    expect(screen.getByText("Primary ATTE")).toBeInTheDocument();
    expect(screen.getByText("CAUSAL_ESTIMATE")).toBeInTheDocument();
    expect(await screen.findByText("Subordinate sensitivity evidence")).toBeInTheDocument();
    expect(screen.getByText("Stricter threshold")).toBeInTheDocument();
    expect(screen.getByText("nearest-rank-percentile-0.75.v1")).toBeInTheDocument();
    expect(screen.getByText(/sha256:strict-seeds/)).toBeInTheDocument();
    expect(screen.getByText("COHORT_SUPPORT_INSUFFICIENT")).toBeInTheDocument();
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(13));
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

  test("fails closed and does not load ordinary evidence when the reference is unavailable", async () => {
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
      if (input === "/api/evidence/reference") {
        return new Response(JSON.stringify({ code: "RUN_REFERENCE_INVALID" }), {
          status: 503,
          headers: { "content-type": "application/json" },
        });
      }
      if (input === "/api/audit/occurrences") {
        return new Response(
          JSON.stringify({
            result: "CREATED",
            occurrence_id: "occurrence-reference-unavailable",
            event_seq: 1,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        );
      }
      throw new Error(`unexpected request: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByText(
        "Validated Reference unavailable. No ordinary evidence was substituted.",
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Reactive Risk intake is unavailable. No signal or cached result was substituted.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Canonical fields")).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => input === "/api/ingestion-runs"),
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(
        ([input]) => typeof input === "string" && input.startsWith("/api/datasets/"),
      ),
    ).toBe(false);
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

  test("labels public validation evidence and its source-role ceiling", async () => {
    let publicLineageResponse = {
      ...lineageResponse,
      dataset_version: {
        ...lineageResponse.dataset_version,
        dataset_id: "olist-validation",
        dataset_version_id: "sha256:olist-validation-v1",
        source_kind: "olist",
        intended_role: "out_of_domain_validation",
        mapping_manifest_id: "olist-validation.mapping.v1",
        source_role_ceiling: {
          label: "Out-of-domain validation only",
          permitted_claim_scope: "out_of_domain_validation",
          subject_application_role_permitted: false,
          decision_support_evaluation_permitted: false,
        },
      },
      audit_binding: {
        ...lineageResponse.audit_binding,
        source_role_ceiling: {
          label: "Out-of-domain validation only",
          permitted_claim_scope: "out_of_domain_validation",
          subject_application_role_permitted: false,
          decision_support_evaluation_permitted: false,
        },
      },
    };
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
      if (input === "/api/evidence/reference") {
        return new Response(JSON.stringify(referenceDeliveryResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (typeof input === "string" && input.startsWith("/api/datasets/")) {
        return new Response(JSON.stringify(publicLineageResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (typeof input === "string" && input.startsWith("/api/risk-signals")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (typeof input === "string" && input.startsWith("/api/proactive-proposals")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      expect(input).toBe("/api/audit/occurrences");
      return new Response(
        JSON.stringify({
          result: "CREATED",
          occurrence_id: "occurrence-public-lineage",
          event_seq: 1,
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Out-of-domain validation only" }),
    ).toBeInTheDocument();
    expect(screen.getByText("out_of_domain_validation")).toBeInTheDocument();
    expect(screen.getByText("Prohibited by the source-role ceiling")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Validation-only evidence. It cannot support an in-domain construction effect or action permission.",
      ),
    ).toBeInTheDocument();

    publicLineageResponse = {
      ...publicLineageResponse,
      dataset_version: {
        ...publicLineageResponse.dataset_version,
        source_kind: "scms",
        intended_role: "rejection_vignette",
        source_role_ceiling: {
          label: "Rejection vignette only",
          permitted_claim_scope: "rejection_vignette",
          subject_application_role_permitted: false,
          decision_support_evaluation_permitted: false,
        },
      },
      audit_binding: {
        ...publicLineageResponse.audit_binding,
        source_role_ceiling: {
          label: "Rejection vignette only",
          permitted_claim_scope: "rejection_vignette",
          subject_application_role_permitted: false,
          decision_support_evaluation_permitted: false,
        },
      },
    };
    cleanup();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Rejection vignette only" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Rejection-vignette evidence. It cannot support an effect claim, in-domain subject application, or action permission.",
      ),
    ).toBeInTheDocument();
  });
});
