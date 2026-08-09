import { useCallback, useEffect, useRef, useState } from "react";

import {
  getDatasetLineage,
  getHealth,
  getProactiveProposals,
  getRiskSignals,
  getValidatedReference,
  getWorkspace,
  createOperation,
  publishDecisionBrief,
  pollOperation,
  recordBootOccurrence,
  refreshInvestigation,
  replayDecisionBrief,
  submitReactiveInvestigation,
  submitProactiveInvestigation,
} from "./api";
import {
  auditOutcomeCode,
  type AnalysisRunStatus,
  type AuditOccurrenceResponse,
  type DecisionBriefSnapshot,
  type DecisionSupportBoundary,
  type DecisionSupportOption,
  type DecisionSupportRegistryInspection,
  type DiagnosticResult,
  type DiagnosticSummary,
  type DurableOperation,
  type DemoWorkspace,
  type EvidenceVerdict,
  type HealthState,
  type HealthResponse,
  type LineageRecord,
  type LineageSnapshot,
  type PredictiveRiskStatus,
  type ProactiveIngressAttempt,
  type ProactiveProposalFixture,
  type ReactiveIngressAttempt,
  type RiskSignalFixture,
  type RobustnessGrade,
  type RenderedEvidenceVerdict,
  type RefreshInvestigationSnapshot,
  type ReplayResponse,
  type RiskSignal,
  type SupplierMilestoneOutcome,
  type ValidatedReferenceDelivery,
} from "./contracts";
import "./styles.css";

type JourneyState = "loading" | "healthy" | "unavailable";
type AuditState = "pending" | "recorded" | "failed";
type WorkspaceState = "pending" | "created" | "failed";
type ReferenceState = "pending" | "loading" | "ready" | "failed";
type LineageState = "pending" | "loading" | "ready" | "failed";
type RiskState = "pending" | "loading" | "ready" | "failed";
type DecisionBriefState = "pending" | "publishing" | "ready" | "failed";
type FreshOperationState = "idle" | "starting" | "polling" | "terminal" | "failed";

function runRelationshipLabel(
  relationship: AnalysisRunStatus["run_relationship"],
): string {
  switch (relationship) {
    case "reproduction":
      return "Fresh reproduction";
    case "refresh":
      return "Refresh investigation";
    default:
      return "Fresh run";
  }
}

function createBootKey(outcomeCode: string): string {
  return `core-boot-health-v1:${outcomeCode}`;
}

function probeLabel(state: HealthState): string {
  switch (state) {
    case "live":
      return "Live";
    case "ready":
      return "Ready";
    case "degraded":
      return "Ready with a capability degraded";
    case "unavailable":
      return "Unavailable";
  }
}

function recordLabel(record: LineageRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "Unavailable identity";
}

function fieldCount(record: LineageRecord): number {
  const fields = record.fields;
  return typeof fields === "object" && fields !== null
    ? Object.keys(fields).length
    : 0;
}

function recordEntries(value: unknown): Array<[string, LineageRecord]> {
  if (typeof value !== "object" || value === null) {
    return [];
  }
  return Object.entries(value).filter(
    (entry): entry is [string, LineageRecord] =>
      typeof entry[1] === "object" && entry[1] !== null,
  );
}

function formatValue(value: unknown): string {
  if (value === undefined || value === null || value === "") {
    return "Unavailable";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "Unavailable";
  }
}

function preferredRiskFixture(items: RiskSignalFixture[]): RiskSignalFixture | undefined {
  return (
    items.find((item) => item.fixture_id === "hero-reactive-risk-predictive-baseline-v1") ??
    items.find((item) => item.fixture_id === "hero-reactive-risk-metadata-unavailable-v1") ??
    items[0]
  );
}

function hasVerifiedPredictiveArtifacts(fixture: RiskSignalFixture | undefined): boolean {
  return (
    fixture?.fixture_id === "hero-reactive-risk-predictive-baseline-v1" &&
    fixture.signal.predictor_artifact_ref.state === "present" &&
    fixture.signal.predictive_attribution_ref.state === "present"
  );
}

function laterObservationCutoff(signal: RiskSignal): Record<string, unknown> {
  const source = signal.known_at;
  const parsed = new Date(source.value);
  if (Number.isNaN(parsed.getTime())) {
    return { ...source };
  }
  const later = new Date(parsed.getTime() + 24 * 60 * 60 * 1000);
  return {
    ...source,
    value: source.kind === "date" ? later.toISOString().slice(0, 10) : later.toISOString(),
  };
}

function fieldState(value: LineageRecord): string {
  return typeof value.state === "string" ? value.state : "unresolved";
}

function temporalSummary(value: LineageRecord): string {
  const state = fieldState(value);
  const temporal =
    typeof value.value === "object" && value.value !== null
      ? (value.value as LineageRecord)
      : null;
  if (typeof temporal !== "object" || temporal === null) {
    return `State: ${state}`;
  }
  const source = typeof temporal.source_value === "string" ? temporal.source_value : "Unavailable";
  const normalized =
    typeof temporal.normalized_value === "string"
      ? temporal.normalized_value
      : "Unavailable";
  const precision = typeof temporal.precision === "string" ? temporal.precision : "Unavailable";
  const timezone =
    typeof temporal.timezone_status === "string"
      ? temporal.timezone_status
      : "Unavailable";
  return `State: ${state} · ${source} → ${normalized} · ${precision} · timezone ${timezone}`;
}

function eligibilityValue(
  eligibility: Record<string, unknown> | undefined,
  key: string,
): string {
  if (eligibility === undefined) {
    return "Unavailable";
  }
  return formatValue(eligibility[key]);
}

function EligibilityStage({
  outcome,
  eligibility,
  badge,
  headingId,
}: {
  outcome: SupplierMilestoneOutcome | undefined;
  eligibility: Record<string, unknown> | undefined;
  badge: string;
  headingId: string;
}) {
  if (outcome === undefined && eligibility === undefined) {
    return null;
  }
  return (
    <section className="eligibility-stage" aria-labelledby={headingId}>
      <div className="record-heading">
        <div>
          <p className="eyebrow">Eligibility stage</p>
          <h4 id={headingId}>Supplier milestone outcome eligibility</h4>
        </div>
        <span>{badge}</span>
      </div>
      <dl className="risk-facts">
        <div>
          <dt>Outcome basis</dt>
          <dd>
            <code>{outcome?.canonical_slippage_duration_basis ?? "Unavailable"}</code>
          </dd>
        </div>
        <div>
          <dt>Outcome reason</dt>
          <dd>
            <code>{outcome?.reason_code ?? "Unavailable"}</code>
            <span>{outcome?.reason ?? "Unavailable"}</span>
          </dd>
        </div>
        {eligibility !== undefined && (
          <>
            <div>
              <dt>Pre-estimation state</dt>
              <dd>
                <code>{eligibilityValue(eligibility, "state")}</code>
              </dd>
            </div>
            <div>
              <dt>Eligibility reason</dt>
              <dd>
                <code>{eligibilityValue(eligibility, "reason_code")}</code>
                <span>{eligibilityValue(eligibility, "reason")}</span>
              </dd>
            </div>
            <div>
              <dt>Next step</dt>
              <dd>{eligibilityValue(eligibility, "next_step")}</dd>
            </div>
          </>
        )}
      </dl>
      <p className="risk-note">
        This subject is not an estimation line. No slippage estimate is displayed; an actual
        supplier milestone is not required at this stage.
      </p>
    </section>
  );
}

function sourceObservationIds(
  lineage: LineageSnapshot,
  targetRecordType: string,
  targetRecordId: string,
  targetFieldPath: string,
): string[] {
  return lineage.source_observations
    .filter(
      (observation) =>
        observation.target_record_type === targetRecordType &&
        observation.target_record_id === targetRecordId &&
        observation.target_field_path === targetFieldPath,
    )
    .map((observation) => recordLabel(observation, "source_observation_id"));
}

function findingsFor(
  lineage: LineageSnapshot,
  targetRecordId: string,
  targetFieldPath?: string,
): LineageRecord[] {
  const target = targetFieldPath ? `${targetRecordId}.${targetFieldPath}` : targetRecordId;
  return lineage.validation_findings.filter((finding) => {
    const refs = finding.affected_refs;
    return (
      Array.isArray(refs) &&
      refs.some(
        (reference) =>
          typeof reference === "string" &&
          (reference === target || reference.startsWith(`${target}.`)),
      )
    );
  });
}

function Trace({
  observationIds,
  findings,
}: {
  observationIds: string[];
  findings: LineageRecord[];
}) {
  return (
    <div className="fact-trace">
      <span>Source observation</span>
      <code>{observationIds.length > 0 ? observationIds.join(", ") : "Unavailable"}</code>
      <span>Validation finding</span>
      <code>
        {findings.length > 0
          ? findings.map((finding) => recordLabel(finding, "code")).join(", ")
          : "None recorded"}
      </code>
    </div>
  );
}

function diagnosticStatusLabel(status: DiagnosticResult["status"]): string {
  switch (status) {
    case "PASS":
      return "PASS — rule met";
    case "FAIL":
      return "FAIL — rule not met";
    case "UNSUPPORTED":
      return "UNSUPPORTED — scientific support missing";
    case "UNAVAILABLE":
      return "UNAVAILABLE — no verified result";
    case "FAILED":
      return "FAILED — execution or integrity failure";
    case "NOT_RUN":
      return "NOT_RUN — upstream short circuit";
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

const projectionRanges = [
  ["Recovered supplier-milestone days", "recovered_supplier_milestone_days"],
  ["Protected project-delay days", "project_delay_days_protected"],
  ["Gross avoided delay value", "gross_avoided_delay_value"],
  ["Gross consequence value", "gross_consequence_value"],
  ["Net assumption value", "net_assumption_value"],
] as const;

function ProjectionRange({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  const range = asRecord(value);
  if (range === null) {
    return null;
  }
  return (
    <div>
      <dt>{label}</dt>
      <dd className="projection-range">
        {(["lower", "central", "upper"] as const).map((bound) => (
          <span key={bound}>
            <strong>{bound}</strong> <code>{formatValue(range[bound])}</code>
          </span>
        ))}
      </dd>
    </div>
  );
}

export function DecisionSupportProjectionDetails({
  option,
}: {
  option: DecisionSupportOption;
}) {
  const projection = asRecord(option.benefit_projection);
  const assumptions = asRecord(option.assumptions);
  const costs = asRecord(option.costs);
  const caveats = Array.isArray(option.caveats)
    ? option.caveats.filter((item): item is string => typeof item === "string")
    : [];
  const unavailableReasons = Array.isArray(option.unavailable_reasons)
    ? option.unavailable_reasons.filter((item): item is Record<string, unknown> => asRecord(item) !== null)
    : [];
  const hasDetails =
    projection !== null ||
    option.value_status !== undefined ||
    assumptions !== null ||
    costs !== null ||
    caveats.length > 0 ||
    unavailableReasons.length > 0;

  if (!hasDetails) {
    return null;
  }

  return (
    <div className="option-projection">
      <strong>Assumption-based projections</strong>
      <dl className="projection-facts">
        <div>
          <dt>Value status</dt>
          <dd><code>{formatValue(option.value_status)}</code></dd>
        </div>
        {projection !== null && (
          <>
            <div>
              <dt>Disclosure</dt>
              <dd><code>{formatValue(projection.disclosure)}</code></dd>
            </div>
            {projectionRanges.map(([label, key]) => (
              <ProjectionRange key={key} label={label} value={projection[key]} />
            ))}
            <div>
              <dt>Schedule protection</dt>
              <dd><code>{formatValue(projection.schedule_protection)}</code></dd>
            </div>
            <div>
              <dt>Currency</dt>
              <dd><code>{formatValue(projection.currency)}</code></dd>
            </div>
          </>
        )}
      </dl>

      {(assumptions !== null || costs !== null) && (
        <details className="projection-inputs">
          <summary>Inspect assumptions and costs</summary>
          {assumptions !== null && (
            <div>
              <strong>Assumptions</strong>
              <code>{formatValue(assumptions)}</code>
            </div>
          )}
          {costs !== null && (
            <div>
              <strong>Costs</strong>
              <code>{formatValue(costs)}</code>
            </div>
          )}
        </details>
      )}

      <div className="projection-tags">
        <strong>Evidence tags</strong>
        <code>{formatValue(option.evidence_tags)}</code>
      </div>

      {caveats.length > 0 && (
        <div className="projection-caveats">
          <strong>Caveats</strong>
          <ul>
            {caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
          </ul>
        </div>
      )}

      <div className="projection-unavailable">
        <strong>Unavailable reasons</strong>
        {unavailableReasons.length === 0 ? (
          <span>None recorded.</span>
        ) : (
          <ul>
            {unavailableReasons.map((reason, index) => (
              <li key={`${String(reason.code ?? "reason")}-${index}`}>
                <code>{String(reason.code ?? "UNAVAILABLE")}</code>
                <span>{String(reason.reason ?? "No explanation recorded.")}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function diagnosticSummaryLabel(summary: DiagnosticSummary): string {
  switch (summary.state) {
    case "complete":
      return "Complete diagnostic set";
    case "limited":
      return "Limited diagnostic evidence";
    case "attention_required":
      return "Diagnostic attention required";
  }
}

function EvidenceDiagnostics({
  diagnostics,
  summary,
}: {
  diagnostics: DiagnosticResult[];
  summary: DiagnosticSummary;
}) {
  return (
    <section className="evidence-diagnostics" aria-labelledby="diagnostic-summary-heading">
      <div className="record-heading">
        <div>
          <p className="eyebrow">Validity diagnostics</p>
          <h3 id="diagnostic-summary-heading">Diagnostic summary</h3>
        </div>
        <span>{diagnosticSummaryLabel(summary)}</span>
      </div>
      <p className="supporting-copy">
        {summary.diagnostic_count === 0
          ? "No verified diagnostic records are available for this reference."
          : `${summary.diagnostic_count} verified diagnostic record${summary.diagnostic_count === 1 ? "" : "s"} are bound to this reference.`}
      </p>
      <p className="diagnostic-status-summary">
        Status counts: {Object.entries(summary.status_counts)
          .map(([status, count]) => `${status} ${count}`)
          .join("; ") || "none"}
      </p>
      <details className="diagnostic-details">
        <summary>Open diagnostic details ({diagnostics.length})</summary>
        {diagnostics.length === 0 ? (
          <p className="supporting-copy">Diagnostic detail is unavailable.</p>
        ) : (
          <ul className="diagnostic-list">
            {diagnostics.map((diagnostic) => (
              <li className="diagnostic-item" key={diagnostic.diagnostic_id}>
                <div className="diagnostic-item-heading">
                  <strong>{diagnostic.diagnostic_id}</strong>
                  <code aria-label={`Status: ${diagnostic.status}`}>
                    {diagnosticStatusLabel(diagnostic.status)}
                  </code>
                </div>
                <span>{diagnostic.reason}</span>
                <code>Reason: {diagnostic.reason_code}</code>
                {diagnostic.trigger_codes.length > 0 && (
                  <code>Triggers: {diagnostic.trigger_codes.join(", ")}</code>
                )}
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}

function verdictLabel(verdict: EvidenceVerdict): string {
  switch (verdict.verdict_code) {
    case "SUPPORTED_UNDER_ASSUMPTIONS":
      return "Supported under stated assumptions";
    case "TENTATIVE":
      return "Tentative — fragile";
    case "ASSOCIATION_ONLY":
      return "Association only";
    case "INSUFFICIENT":
      return "Insufficient evidence — abstain";
  }
}

function robustnessLabel(grade: RobustnessGrade): string {
  switch (grade.grade) {
    case "STRONG":
      return "Strong";
    case "MODERATE":
      return "Moderate";
    case "WEAK":
      return "Weak";
    case "UNAVAILABLE":
      return "Unavailable";
  }
}

function EvidenceVerdictPanel({
  verdict,
  grade,
  rendered,
}: {
  verdict: EvidenceVerdict | null;
  grade: RobustnessGrade | null;
  rendered: RenderedEvidenceVerdict | null;
}) {
  if (verdict === null || rendered === null) {
    return null;
  }
  return (
    <section className="evidence-verdict" aria-labelledby="evidence-verdict-heading">
      <div className="record-heading">
        <div>
          <p className="eyebrow">Evidence verdict</p>
          <h3 id="evidence-verdict-heading">{verdictLabel(verdict)}</h3>
        </div>
        <span className="verdict-scope">{verdict.scope} claim scope</span>
      </div>
      <dl className="verdict-facts">
        <div>
          <dt>Permitted claim scope</dt>
          <dd>{verdict.permitted_claim_scope}</dd>
        </div>
        <div>
          <dt>Decision Support</dt>
          <dd>
            {verdict.decision_support_evaluation_permitted
              ? "Evaluation permitted after separate eligibility checks"
              : "Prohibited by the evidence permission ceiling"}
          </dd>
        </div>
        <div>
          <dt>Primary trigger</dt>
          <dd><code>{verdict.primary_trigger_code}</code></dd>
        </div>
        {grade !== null && (
          <div>
            <dt>Robustness Grade</dt>
            <dd>{robustnessLabel(grade)}</dd>
          </div>
        )}
      </dl>
      <p className="verdict-language">{rendered.language}</p>
      <p className="verdict-next-step">
        <strong>Next step:</strong> {rendered.next_step}
      </p>
      {verdict.effect_display !== "NONE" && verdict.effect !== null && (
        <details className="verdict-effect-details">
          <summary>Open effect detail</summary>
          <dl className="verdict-facts">
            <div>
              <dt>Estimate</dt>
              <dd>{String(verdict.effect.estimate ?? "Unavailable")}</dd>
            </div>
            <div>
              <dt>95% interval</dt>
              <dd>
                {String(verdict.effect.ci_lower ?? "Unavailable")} to {String(verdict.effect.ci_upper ?? "Unavailable")}
              </dd>
            </div>
            <div>
              <dt>Duration basis</dt>
              <dd>{verdict.canonical_slippage_duration_basis ?? "Unavailable"}</dd>
            </div>
          </dl>
        </details>
      )}
    </section>
  );
}

function subjectApplicabilityLabel(
  state: DecisionBriefSnapshot["subject_applicability"]["state"],
): string {
  switch (state) {
    case "applicable":
      return "Applicable under the recorded support gates";
    case "population_limited":
      return "Population claim only";
    case "abstained":
      return "Insufficient subject support — abstained";
    case "unavailable":
      return "Subject applicability unavailable";
  }
}

function decisionSupportStateLabel(state: DecisionSupportBoundary["state"]): string {
  switch (state) {
    case "not_permitted":
      return "Not permitted by the verified evidence";
    case "inactive_driver":
      return "Inactive driver — no option evaluated";
    case "approval_dependent_suppressed":
      return "Approval-dependent paths suppressed";
    case "constraints_evaluated":
      return "Constraint evaluation complete";
    case "comparison_evaluated":
      return "Comparison complete — recommendation state explicit";
    case "tradeoff_requires_choice":
      return "Two-candidate trade-off — manager choice required";
    case "recommendation_available":
      return "Recommendation available — manager review required";
    case "unavailable":
      return "Decision Support unavailable";
  }
}

export function DecisionSupportActionsStage({
  boundary,
  registryInspection,
}: {
  boundary: DecisionSupportBoundary;
  registryInspection: DecisionSupportRegistryInspection | null;
}) {
  const registry: Record<string, unknown> = registryInspection ?? {};
  const releaseBinding =
    typeof registry.release_binding === "object" && registry.release_binding !== null
      ? (registry.release_binding as Record<string, unknown>)
      : null;
  const library =
    typeof registry.intervention_library === "object" &&
    registry.intervention_library !== null
      ? (registry.intervention_library as Record<string, unknown>)
      : null;
  const libraryOptions =
    library !== null && Array.isArray(library.options)
      ? library.options.filter(
          (option): option is Record<string, unknown> =>
            typeof option === "object" && option !== null,
        )
      : [];
  const governedRecords = [
    {
      label: "Intervention Library",
      value: library === null ? "Unavailable" : library.state,
      records: libraryOptions,
    },
    {
      label: "Driver-Action Links",
      value: "driver_action_links" in registry ? registry.driver_action_links : null,
      records: Array.isArray(registry.driver_action_links)
        ? registry.driver_action_links.filter(
            (record): record is Record<string, unknown> =>
              typeof record === "object" && record !== null,
          )
        : [],
    },
    {
      label: "Advisory Rubrics",
      value: "advisory_rubrics" in registry ? registry.advisory_rubrics : null,
      records: Array.isArray(registry.advisory_rubrics)
        ? registry.advisory_rubrics.filter(
            (record): record is Record<string, unknown> =>
              typeof record === "object" && record !== null,
          )
        : [],
    },
    {
      label: "Monitoring Triggers",
      value: "monitoring_triggers" in registry ? registry.monitoring_triggers : null,
      records: Array.isArray(registry.monitoring_triggers)
        ? registry.monitoring_triggers.filter(
            (record): record is Record<string, unknown> =>
              typeof record === "object" && record !== null,
          )
        : [],
    },
    {
      label: "Composite Reviews",
      value: "composite_reviews" in registry ? registry.composite_reviews : null,
      records: Array.isArray(registry.composite_reviews)
        ? registry.composite_reviews.filter(
            (record): record is Record<string, unknown> =>
              typeof record === "object" && record !== null,
          )
        : [],
    },
    {
      label: "Constraint Rules",
      value: "constraint_rules" in registry ? registry.constraint_rules : null,
      records: Array.isArray(registry.constraint_rules)
        ? registry.constraint_rules.filter(
            (record): record is Record<string, unknown> =>
              typeof record === "object" && record !== null,
          )
        : [],
    },
  ];

  const actionRecommendation = boundary.action_recommendation;
  const recommendationSelectionBasis =
    actionRecommendation !== null && typeof actionRecommendation.selection_basis === "string"
      ? actionRecommendation.selection_basis
      : null;
  const recommendationAuthorization =
    actionRecommendation !== null &&
    typeof actionRecommendation.authorization === "object" &&
    actionRecommendation.authorization !== null
      ? (actionRecommendation.authorization as Record<string, unknown>)
      : null;
  const recommendationRunnerUp =
    actionRecommendation !== null &&
    typeof actionRecommendation.runner_up === "object" &&
    actionRecommendation.runner_up !== null
      ? (actionRecommendation.runner_up as Record<string, unknown>)
      : null;
  const tradeoff = boundary.tradeoff;
  const tradeoffPivot =
    tradeoff !== null && typeof tradeoff.pivot === "string" ? tradeoff.pivot : null;
  const tradeoffCandidates =
    tradeoff !== null && Array.isArray(tradeoff.candidates)
      ? tradeoff.candidates.filter(
          (candidate): candidate is Record<string, unknown> =>
            typeof candidate === "object" && candidate !== null,
        )
      : [];
  const isMonitoringFallback =
    recommendationSelectionBasis === "MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION";
  const evaluationLifecycle = boundary.evaluation_lifecycle;
  const lifecycleHead =
    evaluationLifecycle !== undefined &&
    typeof evaluationLifecycle.head === "object" &&
    evaluationLifecycle.head !== null
      ? (evaluationLifecycle.head as Record<string, unknown>)
      : null;
  const lifecycleHistory =
    evaluationLifecycle !== undefined && Array.isArray(evaluationLifecycle.history)
      ? evaluationLifecycle.history
          .map(asRecord)
          .filter((item): item is Record<string, unknown> => item !== null)
      : [];
  const lifecycleStates = lifecycleHistory.reduce<Record<string, number>>(
    (counts, item) => {
      const state = item.record_state;
      if (typeof state === "string") {
        counts[state] = (counts[state] ?? 0) + 1;
      }
      return counts;
    },
    {},
  );
  const lifecycleCurrentness = asRecord(evaluationLifecycle?.currentness);
  const currentnessChecks =
    lifecycleCurrentness !== null && Array.isArray(lifecycleCurrentness.checks)
      ? lifecycleCurrentness.checks
          .map(asRecord)
          .filter((item): item is Record<string, unknown> => item !== null)
      : [];
  const currentnessStates = currentnessChecks.reduce<Record<string, number>>(
    (counts, item) => {
      const outcome = item.currentness_outcome;
      if (typeof outcome === "string") {
        counts[outcome] = (counts[outcome] ?? 0) + 1;
      }
      return counts;
    },
    {},
  );

  return (
    <section className="actions-stage" aria-labelledby="actions-stage-heading">
      <div className="record-heading">
        <div>
          <p className="eyebrow">Actions stage</p>
          <h3 id="actions-stage-heading">Decision Support boundary</h3>
        </div>
        <span>{decisionSupportStateLabel(boundary.state)}</span>
      </div>
      <p className="verdict-language">
        {boundary.reason ?? "Decision Support did not produce an effect-bearing result."}
      </p>
      <p className="verdict-next-step">
        <strong>Next step:</strong>{" "}
        {boundary.next_step ?? boundary.permission.next_step}
      </p>
      <dl className="verdict-facts">
        <div>
          <dt>Terminal outcome</dt>
          <dd><code>{boundary.outcome}</code></dd>
        </div>
        <div>
          <dt>Permission denial reason</dt>
          <dd><code>{boundary.permission.denial_reason_code ?? "None"}</code></dd>
        </div>
        <div>
          <dt>Action effect evidence</dt>
          <dd><code>{boundary.action_effect_evidence}</code></dd>
        </div>
        <div>
          <dt>Recommendation</dt>
          <dd>
            {actionRecommendation !== null
              ? isMonitoringFallback
                ? "Accept and Monitor fallback — manager review required"
                : `Available — ${formatValue(actionRecommendation.selected_option_code)}`
              : tradeoff !== null
                ? "Two candidates — manager choice required; no recommendation published"
                : "None — no recommendation is published."}
          </dd>
        </div>
        <div>
          <dt>Governed data release binding</dt>
          <dd>
            <code>{formatValue(releaseBinding?.state ?? "Unavailable")}</code>
          </dd>
        </div>
      </dl>

      {evaluationLifecycle !== undefined && (
        <div className="action-publication evaluation-lifecycle" role="status">
          <strong>Evaluation lifecycle</strong>
          <span>
            Series: <code>{formatValue(evaluationLifecycle.evaluation_series_id)}</code>
          </span>
          <span>
            Authoritative head: <code>{formatValue(lifecycleHead?.head_kind ?? "Unavailable")}</code>
          </span>
          <span>
            Advice state: <code>{formatValue(lifecycleHead?.advice_state ?? "Unavailable")}</code>
          </span>
          <span>
            Historical/currentness records: <code>{formatValue(lifecycleStates)}</code>
          </span>
          <span>
            Currentness checks: <code>{formatValue(currentnessStates)}</code>
          </span>
        </div>
      )}

      {actionRecommendation !== null && (
        <div className="action-publication" role="status">
          <strong>{isMonitoringFallback ? "Accept and Monitor fallback" : "Recommendation available"}</strong>
          <span>
            Selected option: <code>{formatValue(actionRecommendation.selected_option_code)}</code>
          </span>
          <span>
            Selection basis: <code>{formatValue(recommendationSelectionBasis)}</code>
          </span>
          <span>
            Manager authorization: <code>{formatValue(recommendationAuthorization?.state ?? "NOT_RECORDED")}</code>
          </span>
          {recommendationRunnerUp !== null && (
            <span>
              Runner-up: <code>{formatValue(recommendationRunnerUp.option_code)}</code> — {formatValue(recommendationRunnerUp.ordering_reason)}
            </span>
          )}
          <span>This publication does not authorize or execute an action.</span>
        </div>
      )}

      {tradeoff !== null && (
        <div className="action-tradeoff" role="status">
          <strong>Two-candidate trade-off</strong>
          {tradeoffPivot === "INCOMPARABLE_EVIDENCE_GAP" && (
            <span>Incomparable evidence gap</span>
          )}
          <span>
            Pivot: <code>{formatValue(tradeoffPivot)}</code>
          </span>
          <p>No candidate is recommended; manager choice is required.</p>
          <span>This publication does not imply approval or authorization.</span>
          {tradeoffCandidates.length > 0 && (
            <ol>
              {tradeoffCandidates.map((candidate) => (
                <li key={String(candidate.candidate_label ?? candidate.option_code)}>
                  <code>{formatValue(candidate.option_code)}</code>
                  <span>
                    Basis: {formatValue(candidate.candidate_basis ?? candidate.basis)}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      <div className="action-evidence">
        <strong>Evidence tags</strong>
        <ul>
          {Object.entries(boundary.evidence_tags).map(([slot, tag]) => (
            <li key={slot}>
              <span>{slot}</span>
              <code>{tag}</code>
            </li>
          ))}
        </ul>
      </div>

      <div className="action-suppressions">
        <strong>Deterministic suppression reasons</strong>
        {boundary.suppression_reasons.length === 0 ? (
          <span>None recorded.</span>
        ) : (
          <ol>
            {boundary.suppression_reasons.map((reason) => (
              <li key={`${reason.priority}-${reason.code}`}>
                <code>{reason.code}</code>
                <span>{reason.reason}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {boundary.options.length === 0 ? (
        <p className="supporting-copy">No Decision Support evaluation was created.</p>
      ) : (
        <div className="action-options">
          <strong>Option evaluations</strong>
          <ul>
            {boundary.options.map((option) => (
              <li key={`${option.option_code}-${option.option_version}`}>
                <div>
                  <strong>{option.label}</strong>
                  <code>{option.option_code} · {option.evaluation_state}</code>
                </div>
                <div>
                  <span>
                    {option.suppression_reasons.map((reason) => reason.code).join(", ")}
                  </span>
                  <code>
                    {Object.entries(option.evidence_tags)
                      .map(([slot, tag]) => `${slot}: ${tag}`)
                      .join(" · ")}
                  </code>
                </div>
                <DecisionSupportProjectionDetails option={option} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {boundary.options.some(
        (option) =>
          (option.constraint_results?.length ?? 0) > 0 ||
          option.provenance !== undefined,
      ) && (
        <div className="action-constraint-results">
          <strong>Typed constraint outcomes and provenance</strong>
          <ul>
            {boundary.options.map((option) => {
              const results = option.constraint_results ?? [];
              if (results.length === 0 && option.provenance === undefined) {
                return null;
              }
              return (
                <li key={`${option.option_code}-constraints`}>
                  <strong>{option.option_code}</strong>
                  <ul>
                    {results.length === 0 ? (
                      <li>
                        <code>NOT_EVALUATED</code>
                        <span>No rule result was produced before this option was suppressed.</span>
                      </li>
                    ) : (
                      results.map((rule, index) => (
                        <li key={`${String(rule.rule_code ?? "rule")}-${index}`}>
                          <code>
                            {String(rule.rule_code ?? "UNKNOWN_RULE")} / {String(rule.status ?? "UNKNOWN")}
                          </code>
                          <span>
                            {String(rule.explanation_code ?? "No explanation code")} / scope {String(rule.option_scope ?? "Unavailable")}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                  {option.provenance !== undefined && (
                    <details className="option-provenance">
                      <summary>Inspect option provenance</summary>
                      <code>{formatValue(option.provenance)}</code>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <details className="governed-records">
        <summary>Inspect governed Decision Support records</summary>
        <div className="governed-record-list">
          {governedRecords.map((group) => (
            <div key={group.label}>
              <strong>{group.label}</strong>
              <span>
                {Array.isArray(group.value)
                  ? `${group.value.length} record${group.value.length === 1 ? "" : "s"}`
                  : formatValue(group.value)}
              </span>
              <ul>
                {group.records.map((record, index) => (
                  <li key={`${group.label}-${String(record.option_code ?? record.link_id ?? record.rubric_id ?? record.trigger_id ?? index)}`}>
                    <code>
                      {String(
                        record.option_code ??
                          record.link_id ??
                          record.rubric_id ??
                          record.trigger_id ??
                          "record",
                      )}
                    </code>
                    <span>{formatValue(record.state ?? record.review_status ?? record.lifecycle_status)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}

function DecisionBriefPanel({
  state,
  snapshot,
  replay,
}: {
  state: DecisionBriefState;
  snapshot: DecisionBriefSnapshot | null;
  replay: ReplayResponse | null;
}) {
  if (state === "pending") {
    return null;
  }
  if (state === "publishing") {
    return (
      <section className="decision-brief" aria-labelledby="decision-brief-heading">
        <div className="record-heading">
          <div>
            <p className="eyebrow">Reference journey</p>
            <h3 id="decision-brief-heading">Publishing the Decision Brief Snapshot</h3>
          </div>
        </div>
        <p className="supporting-copy" role="status">
          Capturing the subject support gates and the validated reference state.
        </p>
      </section>
    );
  }
  if (state === "failed" || snapshot === null) {
    return (
      <section className="decision-brief" aria-labelledby="decision-brief-heading">
        <div className="record-heading">
          <div>
            <p className="eyebrow">Reference journey</p>
            <h3 id="decision-brief-heading">Decision Brief unavailable</h3>
          </div>
          <span>Unavailable</span>
        </div>
        <p className="lineage-warning" role="status">
          No stored subject applicability or current substitute was shown. Restore the verified
          reference journey and retry.
        </p>
      </section>
    );
  }

  const applicability = snapshot.subject_applicability;
  const profile = applicability.subject_profile;
  const profileCount =
    typeof profile === "object" && profile !== null ? Object.keys(profile).length : 0;
  const gates = Array.isArray(applicability.gates)
    ? applicability.gates.filter(
        (gate): gate is Record<string, unknown> =>
          typeof gate === "object" && gate !== null,
      )
    : [];
  const storedAttempt =
    typeof snapshot.ingress_attempt.attempt === "object" &&
    snapshot.ingress_attempt.attempt !== null
      ? (snapshot.ingress_attempt.attempt as Record<string, unknown>)
      : {};

  return (
    <section className="decision-brief" aria-labelledby="decision-brief-heading">
      <div className="record-heading">
        <div>
          <p className="eyebrow">Reference journey</p>
          <h3 id="decision-brief-heading">Subject applicability</h3>
        </div>
        <span>{subjectApplicabilityLabel(applicability.state)}</span>
      </div>
      <dl className="verdict-facts">
        <div>
          <dt>Subject identity</dt>
          <dd><code>{formatValue(applicability.subject_identity)}</code></dd>
        </div>
        <div>
          <dt>Explicit subject profile</dt>
          <dd>{profileCount > 0 ? `${profileCount} recorded fields` : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Population permission</dt>
          <dd>{formatValue(applicability.population_permission)}</dd>
        </div>
        <div>
          <dt>Source-role ceiling</dt>
          <dd>{formatValue(applicability.source_role_ceiling)}</dd>
        </div>
      </dl>
      <div className="support-gates">
        <strong>Support gates</strong>
        {gates.length === 0 ? (
          <span>Unavailable</span>
        ) : (
          <ul>
            {gates.map((gate) => (
              <li key={String(gate.gate)}>
                <span>{String(gate.gate ?? "support gate")}</span>
                <code>{String(gate.state ?? "unavailable")}</code>
                {gate.code !== null && gate.code !== undefined && (
                  <code>{String(gate.code)}</code>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="verdict-language">{formatValue(applicability.reason)}</p>
      <p className="verdict-next-step">
        <strong>Next step:</strong> {formatValue(applicability.next_step)}
      </p>
      <dl className="verdict-facts">
        <div>
          <dt>Stored ingress state</dt>
          <dd>
            {formatValue(storedAttempt.status)} · {formatValue(storedAttempt.primary_code)}
          </dd>
        </div>
        <div>
          <dt>Stored reference validation</dt>
          <dd>{formatValue(snapshot.reference.verification_state)}</dd>
        </div>
        <div>
          <dt>Stored diagnostic summary</dt>
          <dd>{formatValue(snapshot.reference.diagnostic_summary)}</dd>
        </div>
        <div>
          <dt>Stored canonical lineage</dt>
          <dd><code>{formatValue(snapshot.lineage.dataset_version_id)}</code></dd>
        </div>
        <div>
          <dt>Content-addressed records</dt>
          <dd>{Object.keys(snapshot.referenced_records).length}</dd>
        </div>
      </dl>
      <div className="action-lane">
        <strong>Action lane: read-only</strong>
        <span>{formatValue(snapshot.action_lane.reason)}</span>
        <span>{formatValue(snapshot.action_lane.next_step)}</span>
      </div>
      {snapshot.decision_support !== null && (
        <DecisionSupportActionsStage
          boundary={snapshot.decision_support}
          registryInspection={snapshot.decision_support_registry}
        />
      )}
      <p className="audit-status">
        Immutable snapshot {snapshot.snapshot_id} · event {snapshot.event_seq}
      </p>
      {replay?.status === "REPLAYED" && replay.snapshot !== null ? (
        <p className="replay-status" role="status">
          Replay verified from stored state at event {replay.requested_event_seq}; no current
          eligibility or reference state was read.
        </p>
      ) : (
        <p className="lineage-warning" role="status">
          Historical replay is unavailable. The stored snapshot remains read-only.
        </p>
      )}
    </section>
  );
}

function FreshRunDetailPanel({
  detail,
  primaryResult,
  diagnostics,
  diagnosticSummary,
  evidenceVerdict,
  robustnessGrade,
  renderedVerdict,
  subjectVerdict,
  renderedSubjectVerdict,
}: {
  detail: Record<string, unknown> | null | undefined;
  primaryResult: Record<string, unknown> | null | undefined;
  diagnostics: DiagnosticResult[];
  diagnosticSummary: DiagnosticSummary | null;
  evidenceVerdict: EvidenceVerdict | null;
  robustnessGrade: RobustnessGrade | null;
  renderedVerdict: RenderedEvidenceVerdict | null;
  subjectVerdict: EvidenceVerdict | null;
  renderedSubjectVerdict: RenderedEvidenceVerdict | null;
}) {
  if (
    (detail === null || detail === undefined) &&
    (primaryResult === null || primaryResult === undefined)
  ) {
    return null;
  }
  const variants = detail !== null && detail !== undefined && Array.isArray(detail.variants)
    ? detail.variants.filter(
        (value): value is Record<string, unknown> =>
          typeof value === "object" && value !== null && !Array.isArray(value),
      )
    : [];
  const failures =
    detail !== null && detail !== undefined && Array.isArray(detail.component_failures)
    ? detail.component_failures.length
    : 0;
  const primaryEffect =
    primaryResult !== null &&
    primaryResult !== undefined &&
    typeof primaryResult.primary_atte === "object" &&
    primaryResult.primary_atte !== null
      ? (primaryResult.primary_atte as Record<string, unknown>)
      : null;
  const contextEffect =
    primaryResult !== null &&
    primaryResult !== undefined &&
    typeof primaryResult.context_ate === "object" &&
    primaryResult.context_ate !== null
      ? (primaryResult.context_ate as Record<string, unknown>)
      : null;
  const effectInterval = (effect: Record<string, unknown> | null) =>
    effect === null
      ? "Unavailable"
      : `${String(effect.ci_lower ?? "Unavailable")} to ${String(effect.ci_upper ?? "Unavailable")}`;
  const sensitivityEntries =
    primaryResult !== null &&
    primaryResult !== undefined &&
    typeof primaryResult.sensitivity_results === "object" &&
    primaryResult.sensitivity_results !== null &&
    !Array.isArray(primaryResult.sensitivity_results)
      ? Object.entries(primaryResult.sensitivity_results).filter(
          (entry): entry is [string, Record<string, unknown>] =>
            typeof entry[1] === "object" && entry[1] !== null && !Array.isArray(entry[1]),
        )
      : [];
  const comparisonEntries =
    primaryResult !== null &&
    primaryResult !== undefined &&
    typeof primaryResult.comparison_results === "object" &&
    primaryResult.comparison_results !== null &&
    !Array.isArray(primaryResult.comparison_results)
      ? Object.entries(primaryResult.comparison_results).filter(
          (entry): entry is [string, Record<string, unknown>] =>
            typeof entry[1] === "object" && entry[1] !== null && !Array.isArray(entry[1]),
        )
      : [];
  const subjectSupport =
    primaryResult !== null &&
    primaryResult !== undefined &&
    typeof primaryResult.subject_support === "object" &&
    primaryResult.subject_support !== null &&
    !Array.isArray(primaryResult.subject_support)
      ? (primaryResult.subject_support as Record<string, unknown>)
      : null;
  const sensitivityLabel = (estimandId: string, variantId: string): string => {
    switch (estimandId) {
      case "sensitivity_late_risk_atte":
        return "Binary late-outcome risk difference";
      case "sensitivity_continuous_load_slope":
        return "Continuous-load slope";
      default:
        break;
    }
    switch (variantId) {
      case "stricter_threshold":
        return "Stricter threshold";
      case "short_history":
        return "Short history";
      case "long_history":
        return "Long history";
      default:
        return variantId;
    }
  };
  return (
    <>
      {detail !== null && detail !== undefined && (
        <section className="operation-detail" aria-label="Fresh run detail">
          <p className="eyebrow">Safe engine detail</p>
          <dl className="risk-facts">
            <div>
              <dt>Execution state</dt>
              <dd>{String(detail.execution_state ?? "unavailable")}</dd>
            </div>
            <div>
              <dt>Last completed stage</dt>
              <dd>{String(detail.last_completed_stage ?? "unavailable")}</dd>
            </div>
            <div>
              <dt>Component failures</dt>
              <dd>{failures}</dd>
            </div>
          </dl>
          {variants.length > 0 && (
            <ul className="status-list">
              {variants.map((variant) => (
                <li key={String(variant.variant_id)}>
                  <strong>{String(variant.variant_id)}</strong>: S8 {String(variant.s8_status)} ·
                  overlap {String(variant.overlap_status)} · S9 {String(variant.s9_status)} (
                  {String(variant.s9_count ?? 0)} rows)
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      <EvidenceVerdictPanel
        verdict={evidenceVerdict}
        grade={robustnessGrade}
        rendered={renderedVerdict}
      />
      {diagnosticSummary !== null && (
        <EvidenceDiagnostics diagnostics={diagnostics} summary={diagnosticSummary} />
      )}
      <EvidenceVerdictPanel
        verdict={subjectVerdict}
        grade={null}
        rendered={renderedSubjectVerdict}
      />
      {primaryResult !== null && primaryResult !== undefined && (
        <section className="operation-detail" aria-label="Sealed fresh-run result">
          <p className="eyebrow">Sealed fresh-run result</p>
          <p className="supporting-copy">
            Effect fields below are the exact projection permitted by the sealed Evidence Verdict.
          </p>
          <dl className="risk-facts">
            <div>
              <dt>Primary ATTE</dt>
              <dd>
                {String(primaryEffect?.estimate ?? "Unavailable")} days · 95% interval{" "}
                {effectInterval(primaryEffect)}
              </dd>
            </div>
            <div>
              <dt>Contextual ATE</dt>
              <dd>
                {String(contextEffect?.estimate ?? "Unavailable")} days · 95% interval{" "}
                {effectInterval(contextEffect)}
              </dd>
            </div>
            <div>
              <dt>Duration basis</dt>
              <dd>{String(primaryEffect?.duration_basis ?? "Unavailable")}</dd>
            </div>
            <div>
              <dt>Permission state</dt>
              <dd>
                {String(
                  (primaryResult.permission as Record<string, unknown> | undefined)
                    ?.effect_display ?? "No effect exposed",
                )}
              </dd>
            </div>
          </dl>
        </section>
      )}
      {sensitivityEntries.length > 0 && (
        <section
          className="operation-detail sensitivity-detail"
          aria-label="Subordinate sensitivity evidence"
        >
          <p className="eyebrow">Subordinate sensitivity evidence</p>
          <p className="supporting-copy">
            These pre-registered variants are subordinate evidence. They preserve exact cohort
            provenance and do not upgrade the primary estimand, Evidence Verdict, or action
            permission.
          </p>
          <ul className="status-list">
            {sensitivityEntries.map(([estimandId, sensitivity]) => {
              const variantId =
                typeof sensitivity.variant_id === "string"
                  ? sensitivity.variant_id
                  : estimandId;
              const provenance =
                typeof sensitivity.provenance === "object" &&
                sensitivity.provenance !== null &&
                !Array.isArray(sensitivity.provenance)
                  ? (sensitivity.provenance as Record<string, unknown>)
                  : {};
              const status = String(
                sensitivity.status ?? sensitivity.state ?? "unavailable",
              );
              const effect =
                typeof sensitivity.effect === "object" &&
                sensitivity.effect !== null &&
                !Array.isArray(sensitivity.effect)
                  ? (sensitivity.effect as Record<string, unknown>)
                  : sensitivity;
              const hasEstimate = typeof effect.estimate === "number";
              return (
                <li key={estimandId}>
                  <strong>{sensitivityLabel(estimandId, variantId)}</strong> · <code>{status}</code>
                  <dl className="risk-facts">
                    <div>
                      <dt>Result</dt>
                      <dd>{hasEstimate ? (() => {
                        const displayTransform =
                          typeof effect.display_transform === "object" &&
                          effect.display_transform !== null &&
                          !Array.isArray(effect.display_transform)
                            ? (effect.display_transform as Record<string, unknown>)
                            : null;
                        const displayEstimate = displayTransform?.estimate ?? effect.estimate;
                        const displayUnit =
                          displayTransform?.display_unit ?? effect.unit ?? "days";
                        const displayLower = displayTransform?.ci_lower ?? effect.ci_lower;
                        const displayUpper = displayTransform?.ci_upper ?? effect.ci_upper;
                        return `${String(displayEstimate ?? "Unavailable")} ${String(displayUnit)} · 95% interval ${String(displayLower ?? "Unavailable")} to ${String(displayUpper ?? "Unavailable")}`;
                      })() : String(sensitivity.reason_code ?? "No estimate published")}</dd>
                    </div>
                    <div>
                      <dt>Threshold rule</dt>
                      <dd><code>{formatValue(provenance.threshold_rule_ref)}</code></dd>
                    </div>
                    <div>
                      <dt>History/window selectors</dt>
                      <dd><code>{formatValue(provenance.selector_refs)}</code></dd>
                    </div>
                    <div>
                      <dt>S8/S9 identity</dt>
                      <dd>
                        <code>
                          {formatValue(provenance.s8_identity_hash)} · {formatValue(provenance.s9_identity_hash)}
                        </code>
                      </dd>
                    </div>
                    <div>
                      <dt>Seed provenance</dt>
                      <dd>
                        <code>
                          root {formatValue(provenance.root_seed)} · {formatValue(provenance.seed_registry_digest)}
                        </code>
                      </dd>
                    </div>
                    <div>
                      <dt>Evidence references</dt>
                      <dd><code>{formatValue(provenance.evidence_refs)}</code></dd>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {comparisonEntries.length > 0 && (
        <section
          className="operation-detail sensitivity-detail"
          aria-label="Descriptive comparison diagnostics"
        >
          <p className="eyebrow">Descriptive comparison diagnostics</p>
          <p className="supporting-copy">
            These registered comparisons use the primary cohort for triangulation. They are
            descriptive diagnostics and never replace the primary DoubleML estimand.
          </p>
          <ul className="status-list">
            {comparisonEntries.map(([comparisonId, comparison]) => (
              <li key={comparisonId}>
                <strong>{comparisonId}</strong> · {String(comparison.model_class ?? "model")}
                <dl className="risk-facts">
                  <div>
                    <dt>Exposure coefficient</dt>
                    <dd>
                      {String(comparison.estimate ?? "Unavailable")} days · 95% interval {String(
                        comparison.ci_lower ?? "Unavailable",
                      )} to {String(comparison.ci_upper ?? "Unavailable")}
                    </dd>
                  </div>
                  <div>
                    <dt>Clustered inference</dt>
                    <dd>
                      {String(comparison.cluster_key ?? "Unavailable")} · df {String(
                        comparison.inference_df ?? "Unavailable",
                      )} · corrected t interval
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        </section>
      )}
      {subjectSupport !== null && (
        <section className="operation-detail sensitivity-detail" aria-label="Subject support output">
          <p className="eyebrow">Subject support output</p>
          <p className="supporting-copy">
            Population evidence is not relabelled as an individualized effect. This output only
            reports whether the subject is supported by the registered population overlap checks.
          </p>
          <dl className="risk-facts">
            <div>
              <dt>Subject state</dt>
              <dd>{String(subjectSupport.state ?? "unavailable")} · {String(subjectSupport.reason_code ?? "no reason")}</dd>
            </div>
            <div>
              <dt>Propensity support</dt>
              <dd><code>{formatValue(subjectSupport.propensity)}</code></dd>
            </div>
            <div>
              <dt>Subject profile</dt>
              <dd><code>{formatValue(subjectSupport.subject_profile)}</code></dd>
            </div>
            <div>
              <dt>Exposure record</dt>
              <dd>
                <code>
                  {formatValue(subjectSupport.canonical_exposure ?? subjectSupport.provisional_exposure_preview)}
                </code>
              </dd>
            </div>
            <div>
              <dt>Overlap</dt>
              <dd><code>{formatValue(subjectSupport.overlap)}</code></dd>
            </div>
            <div>
              <dt>Distribution support</dt>
              <dd><code>{formatValue(subjectSupport.distribution_support)}</code></dd>
            </div>
            <div>
              <dt>Eligibility codes</dt>
              <dd><code>{formatValue(subjectSupport.eligibility_codes)}</code></dd>
            </div>
            <div>
              <dt>Evidence references</dt>
              <dd><code>{formatValue(subjectSupport.evidence_refs)}</code></dd>
            </div>
          </dl>
        </section>
      )}
    </>
  );
}

function App() {
  const [journeyState, setJourneyState] = useState<JourneyState>("loading");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [workspaceState, setWorkspaceState] = useState<WorkspaceState>("pending");
  const [workspace, setWorkspace] = useState<DemoWorkspace | null>(null);
  const [referenceState, setReferenceState] = useState<ReferenceState>("pending");
  const [reference, setReference] = useState<ValidatedReferenceDelivery | null>(null);
  const [auditState, setAuditState] = useState<AuditState>("pending");
  const [auditOccurrence, setAuditOccurrence] =
    useState<AuditOccurrenceResponse | null>(null);
  const [lineageState, setLineageState] = useState<LineageState>("pending");
  const [lineage, setLineage] = useState<LineageSnapshot | null>(null);
  const [riskState, setRiskState] = useState<RiskState>("pending");
  const [riskFixtures, setRiskFixtures] = useState<RiskSignalFixture[]>([]);
  const [predictiveStatus, setPredictiveStatus] = useState<PredictiveRiskStatus | null>(null);
  const [riskAttempt, setRiskAttempt] = useState<ReactiveIngressAttempt | null>(null);
  const [decisionBriefState, setDecisionBriefState] =
    useState<DecisionBriefState>("pending");
  const [decisionBrief, setDecisionBrief] =
    useState<DecisionBriefSnapshot | null>(null);
  const [decisionBriefReplay, setDecisionBriefReplay] =
    useState<ReplayResponse | null>(null);
  const [riskFailureAttempt, setRiskFailureAttempt] =
    useState<ReactiveIngressAttempt | null>(null);
  const [riskFailureState, setRiskFailureState] = useState<RiskState>("pending");
  const [proactiveState, setProactiveState] = useState<RiskState>("pending");
  const [proactiveFixtures, setProactiveFixtures] = useState<ProactiveProposalFixture[]>([]);
  const [proactiveAttempt, setProactiveAttempt] =
    useState<ProactiveIngressAttempt | null>(null);
  const [freshOperationState, setFreshOperationState] =
    useState<FreshOperationState>("idle");
  const [freshOperation, setFreshOperation] =
    useState<DurableOperation | null>(null);
  const [reproductionOperationState, setReproductionOperationState] =
    useState<FreshOperationState>("idle");
  const [reproductionOperation, setReproductionOperation] =
    useState<DurableOperation | null>(null);
  const [refreshOperationState, setRefreshOperationState] =
    useState<FreshOperationState>("idle");
  const [refreshOperation, setRefreshOperation] =
    useState<DurableOperation | null>(null);
  const [refreshSnapshot, setRefreshSnapshot] =
    useState<RefreshInvestigationSnapshot | null>(null);
  const bootKey = useRef<string | null>(null);
  const freshOperationKey = useRef<string | null>(null);
  const reproductionOperationKey = useRef<string | null>(null);
  const refreshOperationKey = useRef<string | null>(null);

  const loadHealth = useCallback(async () => {
    setJourneyState("loading");
    try {
      const nextHealth = await getHealth();
      setHealth(nextHealth);
      setJourneyState("healthy");
      setWorkspace(null);
      setWorkspaceState("pending");
      setReference(null);
      setReferenceState("pending");
      setAuditState("pending");
      setLineage(null);
      setLineageState("pending");
      setRiskState("pending");
      setPredictiveStatus(null);
      setRiskFixtures([]);
      setRiskAttempt(null);
      setDecisionBriefState("pending");
      setDecisionBrief(null);
      setDecisionBriefReplay(null);
      setRiskFailureAttempt(null);
      setRiskFailureState("pending");
      setProactiveState("pending");
      setProactiveFixtures([]);
      setProactiveAttempt(null);
      setFreshOperationState("idle");
      setFreshOperation(null);
      freshOperationKey.current = null;
      setReproductionOperationState("idle");
      setReproductionOperation(null);
      reproductionOperationKey.current = null;
      setRefreshOperationState("idle");
      setRefreshOperation(null);
      setRefreshSnapshot(null);
      refreshOperationKey.current = null;

      try {
        const nextWorkspace = await getWorkspace();
        setWorkspace(nextWorkspace);
        setWorkspaceState("created");
      } catch {
        setWorkspace(null);
        setWorkspaceState("failed");
        setAuditState("failed");
        setLineageState("failed");
        return;
      }

      let referenceAvailable = false;
      let validatedReferenceForJourney: ValidatedReferenceDelivery | null = null;
      setReferenceState("loading");
      try {
        const validatedReference = await getValidatedReference();
        validatedReferenceForJourney = validatedReference;
        setReference(validatedReference);
        setReferenceState("ready");
        referenceAvailable = true;
      } catch {
        setReference(null);
        setReferenceState("failed");
      }

      try {
        const outcomeCode = auditOutcomeCode(nextHealth);
        const idempotencyKey =
          bootKey.current ?? createBootKey(outcomeCode);
        bootKey.current = idempotencyKey;
        const occurrence = await recordBootOccurrence({
          idempotency_key: idempotencyKey,
          occurrence_kind: "BOOT_HEALTH_CHECK",
          outcome_code: outcomeCode,
        });
        setAuditOccurrence(occurrence);
        setAuditState("recorded");
      } catch {
        setAuditState("failed");
      }

      if (!referenceAvailable) {
        setLineageState("failed");
        setRiskState("failed");
        setRiskFailureState("failed");
        setProactiveState("failed");
        return;
      }

      setLineageState("loading");
      try {
        const datasetVersionId = validatedReferenceForJourney?.dataset_version_id;
        if (datasetVersionId === undefined) {
          throw new Error("validated reference dataset identity is unavailable");
        }
        const snapshot = await getDatasetLineage(datasetVersionId);
        setLineage(snapshot);
        setLineageState("ready");
        setRiskState("loading");
        try {
          const availableSignals = await getRiskSignals(datasetVersionId);
          setRiskFixtures(availableSignals.items);
          setPredictiveStatus(availableSignals.predictive_status ?? null);
          if (availableSignals.items.length === 0) {
            setRiskState("failed");
          } else {
            const validFixture = preferredRiskFixture(availableSignals.items);
            if (validFixture === undefined) {
              setRiskState("failed");
              return;
            }
            const attempt = await submitReactiveInvestigation(
              datasetVersionId,
              validFixture.fixture_id,
            );
            setRiskAttempt(attempt.attempt);
            setRiskState("ready");
            const investigationRequestId = attempt.attempt.investigation_request_id;
            if (
              investigationRequestId === null ||
              validatedReferenceForJourney === null
            ) {
              setDecisionBriefState("failed");
            } else {
              setDecisionBriefState("publishing");
              try {
                const published = await publishDecisionBrief(
                  investigationRequestId,
                  validatedReferenceForJourney.reference_id,
                );
                setDecisionBrief(published.snapshot);
                const replay = await replayDecisionBrief(
                  investigationRequestId,
                  published.snapshot.event_seq,
                );
                setDecisionBriefReplay(replay);
                setDecisionBriefState("ready");
              } catch {
                setDecisionBrief(null);
                setDecisionBriefReplay(null);
                setDecisionBriefState("failed");
              }
            }
          }
          setProactiveState("loading");
          try {
            const availableProposals = await getProactiveProposals(
              datasetVersionId,
            );
            setProactiveFixtures(availableProposals.items);
            const proposalFixture = availableProposals.items.find(
              (item) => item.fixture_id === "hero-proactive-proposal-v1",
            );
            if (proposalFixture === undefined) {
              setProactiveState("failed");
            } else {
              const attempt = await submitProactiveInvestigation(
                datasetVersionId,
                proposalFixture.fixture_id,
              );
              setProactiveAttempt(attempt.attempt);
              setProactiveState("ready");
            }
          } catch {
            setProactiveState("failed");
          }
        } catch {
          setRiskState("failed");
          setProactiveState("failed");
        }
      } catch {
        setLineage(null);
        setLineageState("failed");
        setRiskState("failed");
      }
    } catch {
      setHealth(null);
      setWorkspace(null);
      setWorkspaceState("failed");
      setReference(null);
      setReferenceState("failed");
      setJourneyState("unavailable");
      setAuditState("failed");
      setLineageState("failed");
      setDecisionBriefState("failed");
      setDecisionBrief(null);
      setDecisionBriefReplay(null);
    }
  }, []);

  const openFailureFixture = useCallback(async () => {
    const fixture =
      riskFixtures.find(
        (item) => item.fixture_id === "hero-reactive-risk-target-mismatch-v1",
      ) ?? riskFixtures[1];
    if (fixture === undefined) {
      return;
    }
    const datasetVersionId = lineage?.dataset_version.dataset_version_id;
    if (datasetVersionId === undefined) {
      setRiskFailureState("failed");
      return;
    }
    setRiskFailureState("loading");
    try {
      const attempt = await submitReactiveInvestigation(
        datasetVersionId,
        fixture.fixture_id,
      );
      setRiskFailureAttempt(attempt.attempt);
      setRiskFailureState("ready");
    } catch {
      setRiskFailureState("failed");
    }
  }, [lineage, riskFixtures]);

  const requestFreshAnalysis = useCallback(async () => {
    if (
      reference === null ||
      riskAttempt?.investigation_request_id === null ||
      riskAttempt?.investigation_request_id === undefined
    ) {
      return;
    }
    const investigationRequestId = riskAttempt.investigation_request_id;
    const idempotencyKey =
      freshOperationKey.current ??
      `fresh-analysis:${investigationRequestId}:seed-0`;
    freshOperationKey.current = idempotencyKey;
    setFreshOperationState("starting");
    try {
      const accepted = await createOperation({
        idempotency_key: idempotencyKey,
        operation_kind: "FRESH_ANALYSIS",
        request: {
          investigation_request_id: investigationRequestId,
          root_seed: 0,
        },
      });
      setFreshOperation(accepted.operation);
      if (
        accepted.operation.state === "SUCCEEDED" ||
        accepted.operation.state === "FAILED" ||
        accepted.operation.state === "CANCELLED" ||
        accepted.operation.state === "TIMED_OUT" ||
        accepted.operation.state === "INTERRUPTED" ||
        accepted.operation.state === "REJECTED"
      ) {
        setFreshOperationState("terminal");
        return;
      }
      setFreshOperationState("polling");
      const terminal = await pollOperation(accepted.operation.operation_id);
      setFreshOperation(terminal);
      setFreshOperationState("terminal");
    } catch {
      setFreshOperationState("failed");
    }
  }, [reference, riskAttempt]);

  const requestFreshReproduction = useCallback(async () => {
    const targetRun = freshOperation?.analysis_run;
    if (
      freshOperation === null ||
      targetRun === null ||
      targetRun === undefined ||
      freshOperation.state !== "SUCCEEDED"
    ) {
      return;
    }
    const idempotencyKey =
      reproductionOperationKey.current ??
      `fresh-reproduction:${targetRun.analysis_run_id}`;
    reproductionOperationKey.current = idempotencyKey;
    setReproductionOperationState("starting");
    try {
      const accepted = await createOperation({
        idempotency_key: idempotencyKey,
        operation_kind: "FRESH_REPRODUCTION",
        request: { target_analysis_run_id: targetRun.analysis_run_id },
      });
      setReproductionOperation(accepted.operation);
      if (
        accepted.operation.state === "SUCCEEDED" ||
        accepted.operation.state === "FAILED" ||
        accepted.operation.state === "CANCELLED" ||
        accepted.operation.state === "TIMED_OUT" ||
        accepted.operation.state === "INTERRUPTED" ||
        accepted.operation.state === "REJECTED"
      ) {
        setReproductionOperationState("terminal");
        return;
      }
      setReproductionOperationState("polling");
      const terminal = await pollOperation(accepted.operation.operation_id);
      setReproductionOperation(terminal);
      setReproductionOperationState("terminal");
    } catch {
      setReproductionOperationState("failed");
    }
  }, [freshOperation]);

  const requestRefreshInvestigation = useCallback(async () => {
    const fixture = preferredRiskFixture(riskFixtures);
    const investigationRequestId = riskAttempt?.investigation_request_id;
    if (
      fixture === undefined ||
      investigationRequestId === null ||
      investigationRequestId === undefined
    ) {
      return;
    }
    const idempotencyKey =
      refreshOperationKey.current ??
      `refresh-investigation:${investigationRequestId}:later-cutoff`;
    refreshOperationKey.current = idempotencyKey;
    setRefreshOperationState("starting");
    try {
      const response = await refreshInvestigation(investigationRequestId, {
        idempotency_key: idempotencyKey,
        trigger_mode: "reactive",
        request: fixture.signal as unknown as Record<string, unknown>,
        observation_cutoff: laterObservationCutoff(fixture.signal),
        root_seed: 0,
      });
      setRefreshSnapshot(response.snapshot);
      setRefreshOperation(response.operation);
      if (response.operation === null) {
        setRefreshOperationState("terminal");
        return;
      }
      if (
        response.operation.state === "SUCCEEDED" ||
        response.operation.state === "FAILED" ||
        response.operation.state === "CANCELLED" ||
        response.operation.state === "TIMED_OUT" ||
        response.operation.state === "INTERRUPTED" ||
        response.operation.state === "REJECTED"
      ) {
        setRefreshOperationState("terminal");
        return;
      }
      setRefreshOperationState("polling");
      const terminal = await pollOperation(response.operation.operation_id);
      setRefreshOperation(terminal);
      setRefreshOperationState("terminal");
    } catch {
      setRefreshOperationState("failed");
    }
  }, [riskAttempt, riskFixtures]);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const statusMessage =
    journeyState === "loading"
      ? "Checking Core health"
      : journeyState === "unavailable"
        ? "Core health is unavailable"
        : health?.readiness.state === "degraded"
          ? "Core ready with Gemini-only drafting unavailable"
          : "Core ready";
  const acceptedRiskFixture = preferredRiskFixture(riskFixtures);
  const predictiveArtifactsVerified = hasVerifiedPredictiveArtifacts(acceptedRiskFixture);
  const proactiveRequest = proactiveAttempt?.investigation_request ?? null;
  const proactiveSubject =
    proactiveRequest !== null &&
    "kind" in proactiveRequest.subject &&
    proactiveRequest.subject.kind === "proactive_preview"
      ? proactiveRequest.subject
      : null;

  return (
    <main className="core-shell">
      <header className="core-header">
        <p className="eyebrow">Causal Delay Copilot</p>
        <h1>Core application health</h1>
        <p className="lede">
          One contract-first browser application with a typed API and an
          immutable audit ledger.
        </p>
      </header>

      <section className="health-panel" aria-labelledby="health-heading">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Operational state</p>
            <h2 id="health-heading">Can the Core be used?</h2>
          </div>
          <span className={`state-mark state-${journeyState}`} aria-hidden="true" />
        </div>

        <p className="status-message" role="status" aria-live="polite">
          {statusMessage}
        </p>

        {journeyState === "loading" && (
          <p className="supporting-copy">The browser is checking the local Core process.</p>
        )}

        {journeyState === "unavailable" && (
          <div className="unavailable-block">
            <p className="supporting-copy">
              No internal details were returned. Check the Core process and retry.
            </p>
            <button className="retry-button" type="button" onClick={() => void loadHealth()}>
              Retry health check
            </button>
          </div>
        )}

        {health !== null && (
          <>
            <dl className="probe-list">
              <div>
                <dt>Process liveness</dt>
                <dd>
                  {probeLabel(health.liveness.state)} <code>{health.liveness.code}</code>
                </dd>
              </div>
              <div>
                <dt>Core readiness</dt>
                <dd>
                  {probeLabel(health.readiness.state)} <code>{health.readiness.code}</code>
                </dd>
              </div>
            </dl>

            {health.degraded_capabilities.length > 0 && (
              <p className="degradation-note">
                Gemini-only drafting is unavailable. Deterministic Core behavior remains
                available.
              </p>
            )}

            <p className="workspace-status" aria-live="polite">
              {workspaceState === "created" && workspace !== null
                ? `Demo Workspace active · ${workspace.workspace_id}`
                : workspaceState === "failed"
                  ? "Demo Workspace unavailable"
                  : "Creating Demo Workspace"}
            </p>

            <p className="audit-status" aria-live="polite">
              {auditState === "recorded" && auditOccurrence !== null
                ? `Audit occurrence recorded · event ${auditOccurrence.event_seq}`
                : auditState === "failed"
                  ? "Audit occurrence unavailable"
                  : "Recording the boot occurrence"}
            </p>

            <section className="reference-status" aria-labelledby="reference-heading">
              <div className="record-heading">
                <div>
                  <p className="eyebrow">Evidence delivery</p>
                  <h2 id="reference-heading">Ordinary demo evidence</h2>
                </div>
                <span>{reference?.delivery_badge ?? "Reference unavailable"}</span>
              </div>
              {referenceState === "loading" && (
                <p className="supporting-copy" aria-live="polite">
                  Verifying the current-release Validated Reference.
                </p>
              )}
              {referenceState === "failed" && (
                <p className="lineage-warning" aria-live="polite">
                  Validated Reference unavailable. No ordinary evidence was substituted.
                </p>
              )}
              {referenceState === "ready" && reference !== null && (
                <>
                  <p className="supporting-copy" aria-live="polite">
                    Existing run reused. No fresh scientific execution occurred.
                  </p>
                  <dl className="risk-facts">
                    <div>
                      <dt>Reference identity</dt>
                      <dd><code>{reference.reference_slot_id}</code></dd>
                    </div>
                    <div>
                      <dt>Analysis run</dt>
                      <dd><code>{reference.analysis_run_id}</code></dd>
                    </div>
                    <div>
                      <dt>Release identity</dt>
                      <dd><code>{reference.release_candidate_id}</code></dd>
                    </div>
                    <div>
                      <dt>Validation attestation</dt>
                      <dd><code>{reference.validation_attestation_ref}</code></dd>
                    </div>
                  </dl>
                  <EvidenceVerdictPanel
                    verdict={reference.evidence_verdict}
                    grade={reference.robustness_grade}
                    rendered={reference.rendered_verdict}
                  />
                  <EvidenceDiagnostics
                    diagnostics={reference.diagnostics}
                    summary={reference.diagnostic_summary}
                  />
                  <section className="operation-panel" aria-labelledby="fresh-operation-heading">
                    <div className="record-heading">
                      <div>
                        <p className="eyebrow">Fresh analysis boundary</p>
                        <h3 id="fresh-operation-heading">Durable operation status</h3>
                      </div>
                      <span>
                        {freshOperation?.analysis_run?.status ??
                          freshOperation?.state ??
                          "NOT_REQUESTED"}
                      </span>
                    </div>
                    <p className="supporting-copy">
                      Fresh work is admitted durably and polled over the typed API. Existing
                      reference evidence is never presented as a fresh run.
                    </p>
                    <p className="supporting-copy">
                      A refresh investigation creates a new request, cutoff, and causal
                      snapshot; replay reuses an earlier response, while reproduction reruns
                      the same scientific projection.
                    </p>
                    {freshOperation?.analysis_run !== null &&
                      freshOperation?.analysis_run !== undefined && (
                        <dl className="risk-facts">
                          <div>
                            <dt>Run relationship</dt>
                            <dd>
                              {runRelationshipLabel(
                                freshOperation.analysis_run.run_relationship,
                              )}
                            </dd>
                          </div>
                          {freshOperation.analysis_run.reproduces_run_id !== null && (
                            <div>
                              <dt>Reproduction target</dt>
                              <dd>
                                <code>{freshOperation.analysis_run.reproduces_run_id}</code>
                              </dd>
                            </div>
                          )}
                          {freshOperation.analysis_run.refresh_of_request_id !== null && (
                            <div>
                              <dt>Refresh predecessor</dt>
                              <dd>
                                <code>
                                  {freshOperation.analysis_run.refresh_of_request_id}
                                </code>
                              </dd>
                            </div>
                          )}
                        </dl>
                      )}
                    <button
                      className="retry-button"
                      type="button"
                      onClick={() => void requestFreshAnalysis()}
                      disabled={
                        riskAttempt?.investigation_request_id === null ||
                        riskAttempt?.investigation_request_id === undefined ||
                        freshOperationState === "starting" ||
                        freshOperationState === "polling"
                      }
                    >
                      {freshOperationState === "starting"
                        ? "Admitting fresh analysis"
                        : freshOperationState === "polling"
                          ? "Polling fresh analysis"
                          : "Request fresh analysis"}
                    </button>
                    <button
                      className="retry-button"
                      type="button"
                      onClick={() => void requestRefreshInvestigation()}
                      disabled={
                        riskAttempt?.investigation_request_id === null ||
                        riskAttempt?.investigation_request_id === undefined ||
                        refreshOperationState === "starting" ||
                        refreshOperationState === "polling"
                      }
                    >
                      {refreshOperationState === "starting"
                        ? "Admitting refresh investigation"
                        : refreshOperationState === "polling"
                          ? "Polling refresh investigation"
                          : "Refresh investigation"}
                    </button>
                    <button
                      className="retry-button"
                      type="button"
                      onClick={() => void requestFreshReproduction()}
                      disabled={
                        freshOperation?.state !== "SUCCEEDED" ||
                        reproductionOperationState === "starting" ||
                        reproductionOperationState === "polling"
                      }
                    >
                      {reproductionOperationState === "starting"
                        ? "Admitting fresh reproduction"
                        : reproductionOperationState === "polling"
                          ? "Polling fresh reproduction"
                      : "Reproduce this fresh run"}
                    </button>
                    {refreshOperationState === "failed" && (
                      <p className="lineage-warning" role="status">
                        Refresh investigation is unavailable. The predecessor request was not
                        changed or reused as a refresh.
                      </p>
                    )}
                    {refreshOperationState === "terminal" && (
                      <p className="supporting-copy" role="status">
                        {refreshOperation?.analysis_run?.run_relationship === "refresh" &&
                        refreshSnapshot !== null
                          ? `Refresh investigation created a new request and causal snapshot at audit event ${refreshSnapshot.event_seq}.`
                          : refreshOperation?.state === "SUCCEEDED"
                            ? "Refresh investigation completed without a comparable new run."
                            : `Refresh investigation ended ${refreshOperation?.state ?? "UNAVAILABLE"}; the predecessor remains unchanged.`}
                      </p>
                    )}
                    {freshOperationState === "failed" && (
                      <p className="lineage-warning" role="status">
                        Fresh operation status is unavailable. No result was substituted.
                      </p>
                    )}
                    {freshOperationState === "terminal" && freshOperation !== null && (
                      <>
                        <p className="supporting-copy" role="status">
                          {freshOperation.analysis_run?.status === "ESTIMATED"
                            ? "Fresh request completed with a machine-verified sealed evidence bundle. The Evidence Verdict controls claim scope and effect exposure."
                            : freshOperation.analysis_run?.status === "ABSTAINED"
                            ? `Fresh request validated and abstained before estimator execution; the sealed run exposes no effect. ${freshOperation.analysis_run.reason_code ?? "No scientific result was published."}`
                            : freshOperation.analysis_run?.status === "FAILED"
                              ? `Fresh request failed safely. ${freshOperation.analysis_run.failure_code ?? "No result was published."}`
                              : freshOperation.state === "SUCCEEDED"
                                ? "Fresh request is durably sealed without a fabricated estimate."
                                : `Fresh operation ended ${freshOperation.state}. ${freshOperation.failure_code ?? "No result was published."}`}
                        </p>
                        <FreshRunDetailPanel
                          detail={freshOperation.analysis_run?.fresh_run_detail}
                          primaryResult={freshOperation.analysis_run?.primary_result}
                          diagnostics={freshOperation.analysis_run?.diagnostics ?? []}
                          diagnosticSummary={
                            freshOperation.analysis_run?.diagnostic_summary ?? null
                          }
                          evidenceVerdict={
                            freshOperation.analysis_run?.evidence_verdict ?? null
                          }
                          robustnessGrade={
                            freshOperation.analysis_run?.robustness_grade ?? null
                          }
                          renderedVerdict={
                            freshOperation.analysis_run?.rendered_verdict ?? null
                          }
                          subjectVerdict={
                            freshOperation.analysis_run?.subject_verdict ?? null
                          }
                          renderedSubjectVerdict={
                            freshOperation.analysis_run?.rendered_subject_verdict ?? null
                          }
                        />
                      </>
                    )}
                    {reproductionOperationState === "failed" && (
                      <p className="lineage-warning" role="status">
                        Fresh reproduction is unavailable. The source run was not repaired or
                        replaced.
                      </p>
                    )}
                    {reproductionOperationState === "terminal" &&
                      reproductionOperation !== null && (
                        <p className="supporting-copy" role="status">
                          {reproductionOperation.analysis_run?.reproduction_comparison
                            ?.status === "passed"
                            ? "Fresh reproduction completed and its declared scientific projection matched the target under the registered tolerances."
                            : reproductionOperation.state === "SUCCEEDED"
                              ? "Fresh reproduction completed without a comparable scientific projection."
                              : `Fresh reproduction ended ${reproductionOperation.state}; no source result was substituted.`}
                        </p>
                      )}
                  </section>
                </>
              )}
            </section>
          </>
        )}
      </section>

      {health !== null && (
        <section className="risk-panel" aria-labelledby="risk-heading">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Risk intake</p>
              <h2 id="risk-heading">Open a reactive investigation</h2>
            </div>
            <span
              className={`state-mark state-${riskState === "ready" ? "healthy" : riskState === "failed" ? "unavailable" : "pending"}`}
              aria-hidden="true"
            />
          </div>

          <p className="supporting-copy">
            A prediction can initiate an investigation, but it is not causal evidence.
            Canonical facts stay bound to one frozen Order Line and Dataset Version.
          </p>

          {riskState === "loading" && (
            <p className="supporting-copy" role="status">
              Loading the verified calibrated predictive Risk Signal.
            </p>
          )}
          {riskState === "failed" && (
            <p className="lineage-warning" role="status">
              Reactive Risk intake is unavailable. No signal or cached result was substituted.
            </p>
          )}
          {riskState === "ready" && riskAttempt !== null && (
            <article className="risk-attempt">
              <div className="record-heading">
                <div>
                  <p className="eyebrow">{acceptedRiskFixture?.label ?? "Reactive signal"}</p>
                  <h3>
                    {riskAttempt.status === "rejected"
                      ? "Investigation request rejected"
                      : riskAttempt.status === "duplicate"
                      ? "Existing investigation request reused"
                      : "Investigation request accepted"}
                  </h3>
                </div>
                <span>{riskAttempt.primary_code}</span>
              </div>

              <dl className="risk-facts">
                <div>
                  <dt>Prediction score</dt>
                  <dd>
                    {predictiveArtifactsVerified
                      ? acceptedRiskFixture?.signal.score_value
                      : "Unavailable — manual investigation remains available"}
                  </dd>
                </div>
                <div>
                  <dt>Prediction role</dt>
                  <dd>Trigger only; excluded from the scientific digest</dd>
                </div>
                <div>
                  <dt>Predictive attribution</dt>
                  <dd>
                    {predictiveArtifactsVerified && acceptedRiskFixture
                      ? formatValue(acceptedRiskFixture.signal.predictive_attribution_ref)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Explanation metadata</dt>
                  <dd>
                    {predictiveArtifactsVerified && acceptedRiskFixture
                      ? formatValue(acceptedRiskFixture.signal.prediction_explanation_ref)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Calibration metadata</dt>
                  <dd>
                    {predictiveArtifactsVerified && acceptedRiskFixture
                      ? formatValue(acceptedRiskFixture.signal.prediction_calibration_ref)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Ranking metadata</dt>
                  <dd>
                    {predictiveArtifactsVerified && acceptedRiskFixture
                      ? formatValue(acceptedRiskFixture.signal.prediction_ranking_ref)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Delivery metadata</dt>
                  <dd>
                    {predictiveArtifactsVerified && acceptedRiskFixture
                      ? formatValue(acceptedRiskFixture.signal.prediction_delivery_metadata)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Reactive subject</dt>
                  <dd>
                    {riskAttempt.investigation_request !== null &&
                    "order_line_id" in riskAttempt.investigation_request.subject
                      ? riskAttempt.investigation_request.subject.order_line_id
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Causal decision cutoff</dt>
                  <dd>
                    {riskAttempt.investigation_request
                      ? temporalSummary(riskAttempt.investigation_request.decision_cutoff)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Observation cutoff</dt>
                  <dd>
                    {riskAttempt.investigation_request
                      ? temporalSummary(riskAttempt.investigation_request.observation_cutoff)
                      : "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>Scientific input digest</dt>
                  <dd>
                    <code>{riskAttempt.investigation_request?.causal_input_digest ?? "Unavailable"}</code>
                  </dd>
                </div>
              </dl>
              <EligibilityStage
                outcome={
                  riskAttempt.investigation_request?.causal_engine_input
                    .supplier_milestone_outcome
                }
                eligibility={
                  riskAttempt.investigation_request?.causal_engine_input.eligibility
                }
                badge="SUBJECT"
                headingId="reactive-eligibility-heading"
              />
              <DecisionBriefPanel
                state={decisionBriefState}
                snapshot={decisionBrief}
                replay={decisionBriefReplay}
              />
              <p className="supporting-copy">
                Predictive attribution - not causal evidence. Manual investigation remains
                available when predictive artifacts are unavailable.
              </p>
              {predictiveStatus?.state === "unavailable" && (
                <p className="lineage-warning" role="status">
                  {predictiveStatus.code}: {predictiveStatus.message}
                </p>
              )}
              {riskAttempt.findings
                .filter((finding) => finding.severity === "warning")
                .map((finding) => (
                  <p className="lineage-warning" key={finding.finding_id}>
                    {finding.code}: {finding.message}
                  </p>
                ))}

              <p className="risk-note">
                Prediction score, threshold, flagged state, attribution, and advisory context
                remain inspectable metadata outside the causal-engine projection.
              </p>

              {riskFixtures.length > 1 && (
                <button
                  className="retry-button"
                  type="button"
                  onClick={() => void openFailureFixture()}
                  disabled={riskFailureState === "loading"}
                >
                  {riskFailureState === "loading"
                    ? "Checking rejected fixture"
                    : "Try the rejected conformance fixture"}
                </button>
              )}

              {riskFailureState === "failed" && (
                <p className="lineage-warning" role="status">
                  The rejected conformance path could not be recorded.
                </p>
              )}
              {riskFailureState === "ready" && riskFailureAttempt !== null && (
                <div className="risk-failure" role="status">
                  <strong>Fail-closed path: {riskFailureAttempt.primary_code}</strong>
                  <span>{riskFailureAttempt.recovery_action}</span>
                  <span>No Investigation Request was created.</span>
                </div>
              )}
            </article>
          )}

          {proactiveState === "loading" && (
            <p className="supporting-copy" role="status">
              Loading the bundled proactive proposal preview.
            </p>
          )}
          {proactiveState === "failed" && (
            <p className="lineage-warning" role="status">
              Proactive proposal intake is unavailable. No cached proposal was substituted.
            </p>
          )}
          {proactiveState === "ready" && proactiveAttempt !== null && (
            <article className="risk-attempt proactive-attempt">
              <div className="record-heading">
                <div>
                  <p className="eyebrow">
                    {proactiveFixtures.find(
                      (item) =>
                        item.proposal.proposal_id === proactiveAttempt.proposal_id &&
                        item.proposal.proposal_revision === proactiveAttempt.proposal_revision,
                    )?.label ?? "Proactive proposal"}
                  </p>
                  <h3>
                    {proactiveAttempt.status === "rejected"
                      ? "Proactive preview rejected"
                      : proactiveAttempt.status === "duplicate"
                        ? "Existing proactive preview reused"
                        : proactiveAttempt.status === "accepted_with_warning"
                          ? "Proactive preview accepted with warning"
                          : "Proactive preview accepted"}
                  </h3>
                </div>
                <span>PROACTIVE · PREVIEW-ONLY</span>
              </div>

              <p className="supporting-copy">
                This pre-award proposal is a preview subject. It is not a committed Order Line
                and cannot create actual milestone or post-commitment history.
              </p>

              <dl className="risk-facts">
                <div>
                  <dt>Proposal subject</dt>
                  <dd>
                    {proactiveAttempt.proposal_id} · {proactiveAttempt.proposal_revision}
                  </dd>
                </div>
                <div>
                  <dt>Supplier preview</dt>
                  <dd>
                    {proactiveSubject === null
                      ? "Unavailable"
                      : `${fieldState(proactiveSubject.supplier_id)} · ${formatValue(proactiveSubject.supplier_id.value)}`}
                  </dd>
                </div>
                <div>
                  <dt>Target milestone</dt>
                  <dd>
                    {proactiveSubject === null
                      ? "Unavailable"
                      : `${fieldState(proactiveSubject.target_milestone_kind)} · ${formatValue(proactiveSubject.target_milestone_kind.value)}`}
                  </dd>
                </div>
                <div>
                  <dt>Decision cutoff</dt>
                  <dd>
                    {proactiveRequest === null
                      ? "Unavailable"
                      : temporalSummary(proactiveRequest.decision_cutoff)}
                  </dd>
                </div>
                <div>
                  <dt>Observation cutoff</dt>
                  <dd>
                    {proactiveRequest === null
                      ? "Unavailable"
                      : temporalSummary(proactiveRequest.observation_cutoff)}
                  </dd>
                </div>
                <div>
                  <dt>Scientific input digest</dt>
                  <dd>
                    <code>{proactiveRequest?.causal_input_digest ?? "Unavailable"}</code>
                  </dd>
                </div>
              </dl>

              <EligibilityStage
                outcome={proactiveRequest?.causal_engine_input.supplier_milestone_outcome}
                eligibility={proactiveRequest?.causal_engine_input.eligibility}
                badge="PREVIEW ONLY"
                headingId="proactive-eligibility-heading"
              />

              <p className="risk-note">
                No canonical Order Line, commitment event, actual milestone, or post-commitment
                history was created.
              </p>
            </article>
          )}
        </section>
      )}

      {health !== null && (
        <section className="lineage-panel" aria-labelledby="lineage-heading">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Intake &amp; lineage</p>
              <h2 id="lineage-heading">Canonical lineage</h2>
            </div>
            <span
              className={`state-mark state-${lineageState === "ready" ? "healthy" : lineageState === "failed" ? "unavailable" : "pending"}`}
              aria-hidden="true"
            />
          </div>

          {lineageState === "loading" && (
            <p className="supporting-copy">Importing the bundled semi-synthetic hero dataset.</p>
          )}

          {lineageState === "failed" && (
            <p className="lineage-warning" role="status">
              Canonical lineage is unavailable. No source facts were substituted.
            </p>
          )}

          {lineageState === "ready" && lineage !== null && (
            <>
              <p className="supporting-copy">
                Mapping manifest <code>{lineage.dataset_version.mapping_manifest_id}</code> is
                bound to an immutable dataset version.
              </p>
              <section className="lineage-subsection" aria-labelledby="source-role-heading">
                <div className="record-heading">
                  <div>
                    <p className="eyebrow">Source-role boundary</p>
                    <h3 id="source-role-heading">
                      {lineage.dataset_version.source_role_ceiling.label}
                    </h3>
                  </div>
                  <span>{lineage.dataset_version.source_kind}</span>
                </div>
                <dl className="verdict-facts">
                  <div>
                    <dt>Permitted claim scope</dt>
                    <dd>{lineage.dataset_version.source_role_ceiling.permitted_claim_scope}</dd>
                  </div>
                  <div>
                    <dt>In-domain subject application</dt>
                    <dd>
                      {lineage.dataset_version.source_role_ceiling.subject_application_role_permitted
                        ? "Permitted"
                        : "Prohibited"}
                    </dd>
                  </div>
                  <div>
                    <dt>Decision Support permission</dt>
                    <dd>
                      {lineage.dataset_version.source_role_ceiling
                        .decision_support_evaluation_permitted
                        ? "Permitted after separate evidence checks"
                        : "Prohibited by the source-role ceiling"}
                    </dd>
                  </div>
                </dl>
                {lineage.dataset_version.intended_role !== "semi_synthetic_hero" && (
                  <p className="lineage-warning" role="status">
                    {lineage.dataset_version.intended_role === "out_of_domain_validation"
                      ? "Validation-only evidence. It cannot support an in-domain construction effect or action permission."
                      : "Rejection-vignette evidence. It cannot support an effect claim, in-domain subject application, or action permission."}
                  </p>
                )}
              </section>

              <dl className="probe-list lineage-counts">
                <div>
                  <dt>Canonical scope</dt>
                  <dd>{lineage.dataset_version.record_counts.order_lines} order lines</dd>
                </div>
                <div>
                  <dt>Event history</dt>
                  <dd>{lineage.dataset_version.record_counts.order_line_events} order line events</dd>
                </div>
                <div>
                  <dt>Field lineage</dt>
                  <dd>{lineage.dataset_version.record_counts.source_observations} source observations</dd>
                </div>
                <div>
                  <dt>Validation</dt>
                  <dd>{lineage.dataset_version.record_counts.validation_findings} validation findings</dd>
                </div>
              </dl>

              <ul className="lineage-list">
                {lineage.order_lines.map((orderLine) => (
                  <li key={recordLabel(orderLine, "order_line_id")}>
                    <code>{recordLabel(orderLine, "order_line_id")}</code>
                    <span>{fieldCount(orderLine)} canonical fields with source trace</span>
                  </li>
                ))}
              </ul>

              <div className="lineage-records">
                {lineage.order_lines.map((orderLine) => {
                  const orderLineId = recordLabel(orderLine, "order_line_id");
                  const orderLineEvents = lineage.order_line_events.filter(
                    (event) => event.order_line_id === orderLineId,
                  );
                  const orderLineFindings = findingsFor(lineage, orderLineId);
                  return (
                    <article className="lineage-record" key={`detail-${orderLineId}`}>
                      <div className="record-heading">
                        <div>
                          <p className="eyebrow">Order line</p>
                          <h3>{orderLineId}</h3>
                        </div>
                        <span>{orderLineEvents.length} events</span>
                      </div>
                      <Trace
                        observationIds={sourceObservationIds(
                          lineage,
                          "OrderLine",
                          orderLineId,
                          "order_line_id",
                        )}
                        findings={orderLineFindings}
                      />

                      <section className="lineage-subsection" aria-labelledby={`fields-${orderLineId}`}>
                        <h4 id={`fields-${orderLineId}`}>Canonical fields</h4>
                        <dl className="canonical-list">
                          {recordEntries(orderLine.fields).map(([fieldName, value]) => {
                            const fieldPath = `fields.${fieldName}`;
                            return (
                              <div key={fieldPath}>
                                <dt>{fieldName}</dt>
                                <dd>
                                  <span>State: {fieldState(value)}</span>
                                  <span>Value: {formatValue(value.value)}</span>
                                  <span>Source value: {formatValue(value.source_value)}</span>
                                  <Trace
                                    observationIds={sourceObservationIds(
                                      lineage,
                                      "OrderLine",
                                      orderLineId,
                                      fieldPath,
                                    )}
                                    findings={findingsFor(lineage, orderLineId, fieldPath)}
                                  />
                                </dd>
                              </div>
                            );
                          })}
                        </dl>
                      </section>

                      <section className="lineage-subsection" aria-labelledby={`events-${orderLineId}`}>
                        <h4 id={`events-${orderLineId}`}>Order line events and clocks</h4>
                        <div className="event-list">
                          {orderLineEvents.map((event) => {
                            const eventId = recordLabel(event, "event_id");
                            const eventFindings = findingsFor(lineage, eventId);
                            return (
                              <article className="event-record" key={eventId}>
                                <div className="record-heading">
                                  <div>
                                    <strong>{recordLabel(event, "kind")}</strong>
                                    <code>{eventId}</code>
                                  </div>
                                </div>
                                <Trace
                                  observationIds={sourceObservationIds(
                                    lineage,
                                    "OrderLineEvent",
                                    eventId,
                                    "event_id",
                                  )}
                                  findings={eventFindings}
                                />
                                <Trace
                                  observationIds={sourceObservationIds(
                                    lineage,
                                    "OrderLineEvent",
                                    eventId,
                                    "kind",
                                  )}
                                  findings={eventFindings}
                                />
                                <dl className="event-facts">
                                  {(["occurred_at", "known_at", "available_at"] as const).map(
                                    (clockName) => {
                                      const clocks: LineageRecord =
                                        typeof event.clocks === "object" && event.clocks !== null
                                          ? (event.clocks as LineageRecord)
                                          : {};
                                      const clock =
                                        typeof clocks[clockName] === "object" &&
                                        clocks[clockName] !== null
                                          ? (clocks[clockName] as LineageRecord)
                                          : {};
                                      const fieldPath = `clocks.${clockName}`;
                                      return (
                                        <div key={fieldPath}>
                                          <dt>{clockName}</dt>
                                          <dd>
                                            {temporalSummary(clock)}
                                            <Trace
                                              observationIds={sourceObservationIds(
                                                lineage,
                                                "OrderLineEvent",
                                                eventId,
                                                fieldPath,
                                              )}
                                              findings={eventFindings}
                                            />
                                          </dd>
                                        </div>
                                      );
                                    },
                                  )}
                                  {(["milestone_kind", "promised_for", "reason", "revises_promise_event_id"] as const).map(
                                    (fieldName) => {
                                      const field =
                                        typeof event[fieldName] === "object" &&
                                        event[fieldName] !== null
                                          ? (event[fieldName] as LineageRecord)
                                          : {};
                                      const fieldPath = fieldName;
                                      const value = fieldName === "promised_for"
                                        ? temporalSummary(field)
                                        : `State: ${fieldState(field)} · Value: ${formatValue(field.value)}`;
                                      return (
                                        <div key={fieldPath}>
                                          <dt>{fieldName}</dt>
                                          <dd>
                                            {value}
                                            <Trace
                                              observationIds={sourceObservationIds(
                                                lineage,
                                                "OrderLineEvent",
                                                eventId,
                                                fieldPath,
                                              )}
                                              findings={eventFindings}
                                            />
                                          </dd>
                                        </div>
                                      );
                                    },
                                  )}
                                </dl>
                              </article>
                            );
                          })}
                        </div>
                      </section>
                    </article>
                  );
                })}
              </div>

              <details className="lineage-register">
                <summary>Source observation register ({lineage.source_observations.length})</summary>
                <ul>
                  {lineage.source_observations.map((observation) => (
                    <li key={recordLabel(observation, "source_observation_id")}>
                      <code>{recordLabel(observation, "source_observation_id")}</code>
                      <span>
                        {recordLabel(observation, "target_record_type")} · {recordLabel(observation, "target_field_path")}
                      </span>
                      <span>
                        Source field: {formatValue(
                          typeof observation.source_field_path === "object" &&
                            observation.source_field_path !== null
                            ? (observation.source_field_path as LineageRecord).value
                            : undefined,
                        )}
                      </span>
                      <span>Source locator: {recordLabel(observation, "source_locator_token")}</span>
                    </li>
                  ))}
                </ul>
              </details>

              <section className="lineage-findings" aria-labelledby="findings-heading">
                <h3 id="findings-heading">Validation findings</h3>
                {lineage.validation_findings.length === 0 ? (
                  <p className="supporting-copy">No findings were recorded.</p>
                ) : (
                  <ul>
                    {lineage.validation_findings.map((finding) => (
                      <li key={recordLabel(finding, "validation_finding_id")}>
                        <strong>{recordLabel(finding, "code")}</strong>
                        <span>{recordLabel(finding, "message")}</span>
                        <span>Affects: {formatValue(finding.affected_refs)}</span>
                        <span>Recovery: {recordLabel(finding, "remediation")}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <p className="audit-status">
                Snapshot bound to audit event {lineage.audit_binding.event_seq}
              </p>
            </>
          )}
        </section>
      )}
    </main>
  );
}

export default App;
