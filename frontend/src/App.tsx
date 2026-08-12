import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import {
  ArrowRight,
  ArrowUpRight,
  CheckmarkFilled,
  ChevronDown,
  ChevronRight,
  Document,
  Email,
  Events,
  FlowData,
  Information,
  Launch,
  Menu,
  Notification,
  Renew,
  Search,
  SettingsAdjust,
  WarningAltFilled,
} from "@carbon/icons-react";

import {
  getDatasetLineage,
  getHealth,
  getProactiveProposals,
  getRiskSignals,
  getReleaseIdentity,
  getValidatedReference,
  getWorkspace,
  acceptTradeoffSelection,
  createOperation,
  disposeDraft,
  editDraft,
  prepareDraftContext,
  publishDecisionBrief,
  publishTradeoffSelection,
  pollOperation,
  recordManagerDecision,
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
  type DraftContextPreview,
  type DraftVersion,
  type ManagerDecisionResponse,
  type DiagnosticResult,
  type DiagnosticSummary,
  type DurableOperation,
  type DemoWorkspace,
  type EvidenceVerdict,
  type HealthState,
  type HealthResponse,
  type HistoricalReplayState,
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
  type TradeoffSelectionDeliveryAttempt,
  type TradeoffSelectionRecord,
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

export type JourneyStage = {
  key: string;
  label: string;
  targetId: string;
  status: string;
};

export function JourneyStageNav({ stages }: { stages: readonly JourneyStage[] }) {
  const [announcement, setAnnouncement] = useState(
    "Decision journey navigation is ready.",
  );

  const moveToStage = (
    event: ReactMouseEvent<HTMLAnchorElement>,
    stage: JourneyStage,
  ) => {
    const target = document.getElementById(stage.targetId);
    if (target === null) {
      event.preventDefault();
      setAnnouncement(`${stage.label} is unavailable. ${stage.status}.`);
      return;
    }

    event.preventDefault();
    window.history.replaceState({}, "", `#${stage.targetId}`);
    if (typeof target.scrollIntoView === "function") {
      const reduceMotion =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
    target.focus({ preventScroll: true });
    setAnnouncement(`Moved to ${stage.label}. ${stage.status}.`);
  };

  return (
    <nav
      id="decision-journey"
      className="journey-navigation"
      aria-labelledby="decision-journey-heading"
    >
      <div className="journey-navigation-heading">
        <div>
          <p className="eyebrow">Decision Brief</p>
          <h2 id="decision-journey-heading">Decision journey</h2>
        </div>
        <p className="journey-navigation-caption">
          Six stages keep evidence, authority, and replay visible in one keyboard-operable path.
        </p>
      </div>
      <ol className="journey-stage-list">
        {stages.map((stage, index) => {
          const statusId = `${stage.key}-stage-status`;
          return (
            <li key={stage.key}>
              <a
                href={`#${stage.targetId}`}
                aria-describedby={statusId}
                onClick={(event) => moveToStage(event, stage)}
              >
                <span className="journey-stage-number" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="journey-stage-label">{stage.label}</span>
                <span id={statusId} className="journey-stage-status">
                  Status: {stage.status}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
    </nav>
  );
}

function JourneyStagePlaceholder({
  eyebrow,
  targetId,
  headingId,
  heading,
  description,
  status,
}: {
  eyebrow: string;
  targetId: string;
  headingId: string;
  heading: string;
  description: string;
  status: string;
}) {
  return (
    <section
      className="journey-stage-overview journey-stage-target"
      id={targetId}
      tabIndex={-1}
      aria-labelledby={headingId}
    >
      <p className="eyebrow">{eyebrow}</p>
      <h3 id={headingId}>{heading}</h3>
      <p className="supporting-copy">{description}</p>
      <p className="stage-status-copy" aria-live="polite">
        {status}.
      </p>
    </section>
  );
}

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

function tradeoffCandidateReference(candidate: Record<string, unknown>): string | null {
  const optionCode = candidate.option_code;
  const optionVersion = candidate.option_version ?? "1";
  const candidateIdentity = asRecord(candidate.candidate_reference);
  const evaluationOccurrenceId = candidateIdentity?.evaluation_occurrence_id;
  return typeof optionCode === "string" &&
    typeof optionVersion === "string" &&
    typeof evaluationOccurrenceId === "string"
    ? `candidate:${evaluationOccurrenceId}:${optionCode}:${optionVersion}`
    : null;
}

function referenceAndHash(value: unknown): Record<string, string> | null {
  const record = asRecord(value);
  return record !== null &&
    typeof record.reference === "string" &&
    record.reference.length > 0 &&
    typeof record.content_hash === "string" &&
    record.content_hash.length > 0
    ? { reference: record.reference, content_hash: record.content_hash }
    : null;
}

function currentAdviceRenderRequest(
  evaluationSeriesId: string | null,
  evaluationOccurrenceId: string | null,
  evaluationDigest: string | null,
  terminalBinding: Record<string, unknown> | null,
  recommendation: Record<string, unknown> | null,
  adviceChainKind: "IMMEDIATE_EVALUATION_RECOMMENDATION" | "ACCEPTED_TRADEOFF_SELECTION",
  selectionClaim: Record<string, unknown> | null,
  evaluationPublishedAt: unknown,
): Record<string, unknown> | null {
  const recommendationBinding = referenceAndHash(
    recommendation === null
      ? null
      : {
          reference: recommendation.occurrence_id,
          content_hash: recommendation.content_hash,
        },
  );
  const claimBinding =
    selectionClaim === null
      ? null
      : referenceAndHash({
          reference: `tradeoff-selection-claim:${String(selectionClaim.selection_claim_occurrence_id ?? "")}`,
          content_hash: selectionClaim.content_hash,
        });
  const chainPublishedAt =
    adviceChainKind === "ACCEPTED_TRADEOFF_SELECTION"
      ? selectionClaim?.published_at
      : evaluationPublishedAt;
  if (
    evaluationSeriesId === null ||
    evaluationOccurrenceId === null ||
    evaluationDigest === null ||
    terminalBinding === null ||
    referenceAndHash(terminalBinding) === null ||
    recommendationBinding === null ||
    (adviceChainKind === "ACCEPTED_TRADEOFF_SELECTION" && claimBinding === null) ||
    (adviceChainKind === "IMMEDIATE_EVALUATION_RECOMMENDATION" && claimBinding !== null) ||
    chainPublishedAt === null ||
    chainPublishedAt === undefined
  ) {
    return null;
  }
  const now = new Date().toISOString();
  return {
    schema_identifier: "current-advice-render-request",
    schema_version: "1",
    render_mode: "CURRENT_ADVICE",
    evaluation_series_id: evaluationSeriesId,
    evaluation_occurrence_id: evaluationOccurrenceId,
    evaluation_digest: evaluationDigest,
    terminal_result_ref_and_hash: referenceAndHash(terminalBinding),
    advice_chain_kind: adviceChainKind,
    recommendation_ref_and_hash_or_null: recommendationBinding,
    accepted_selection_claim_ref_and_hash_or_null: claimBinding,
    advice_chain_published_at: chainPublishedAt,
    requested_at: now,
    available_at: now,
  };
}

function clientOccurrenceId(prefix: string): string | null {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (typeof randomUuid === "string" && randomUuid) {
    return `${prefix}-${randomUuid}`;
  }
  const randomValues = globalThis.crypto?.getRandomValues;
  if (typeof randomValues !== "function") {
    return null;
  }
  const bytes = new Uint32Array(4);
  randomValues.call(globalThis.crypto, bytes);
  return `${prefix}-${Array.from(bytes)
    .map((value) => value.toString(16).padStart(8, "0"))
    .join("")}`;
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function contentHash(value: unknown): Promise<string> {
  if (globalThis.crypto?.subtle === undefined) {
    throw new Error("content hashing is unavailable");
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(canonicalJson(value)),
  );
  return `sha256:${Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
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

function HistoricalReplayPanel({ state }: { state: HistoricalReplayState }) {
  const evidence = state.evidence;
  const recommendation = state.recommendation;
  const selection = state.tradeoff_selection;
  const draft = state.draft;
  const disposition = state.disposition;
  const decision = state.decision;
  const recommendationReference =
    typeof recommendation.reference === "object" && recommendation.reference !== null
      ? (recommendation.reference as Record<string, unknown>)
      : null;
  const draftRecord =
    typeof draft.head === "object" && draft.head !== null
      ? (draft.head as Record<string, unknown>)
      : null;
  const decisionRecord =
    typeof decision.record === "object" && decision.record !== null
      ? (decision.record as Record<string, unknown>)
      : null;
  const occurrenceCount = Array.isArray(state.occurrences) ? state.occurrences.length : 0;

  return (
    <section className="historical-replay" aria-labelledby="historical-replay-heading">
      <div className="record-heading">
        <div>
          <p className="eyebrow">Historical manager timeline</p>
          <h4 id="historical-replay-heading">
            Exact read-only state at event {state.cutoff_event_seq}
          </h4>
        </div>
        <span>Read-only</span>
      </div>
      <p className="supporting-copy">
        This projection is reconstructed from stored occurrences at the cutoff. Current policy,
        currentness, source adapters, and provider output were not consulted.
      </p>
      <dl className="verdict-facts">
        <div>
          <dt>What was known</dt>
          <dd>Request, ingress, lineage, validated reference, and the immutable brief snapshot</dd>
        </div>
        <div>
          <dt>Evidence / verdict</dt>
          <dd>
            {formatValue(
              evidence.subject_verdict === null ? "No subject verdict" : "Stored subject verdict",
            )}
            {" · "}
            {formatValue(
              evidence.evaluation === null ? "No evaluation published" : "Stored evaluation",
            )}
          </dd>
        </div>
        <div>
          <dt>Recommendation</dt>
          <dd>
            {formatValue(recommendation.state)}
            {recommendationReference !== null && (
              <code>{formatValue(recommendationReference.reference)}</code>
            )}
          </dd>
        </div>
        <div>
          <dt>Trade-off selection</dt>
          <dd>{formatValue(selection.state)}</dd>
        </div>
        <div>
          <dt>Draft source / fallback</dt>
          <dd>
            {formatValue(draft.source)}{" / "}{formatValue(draft.fallback)}
            {draftRecord !== null && <code>{formatValue(draftRecord.occurrence_id)}</code>}
          </dd>
        </div>
        <div>
          <dt>Edits / disposition</dt>
          <dd>
            {Array.isArray(draft.edits) ? draft.edits.length : 0} recorded edit(s)
            {" · "}
            {formatValue(disposition.state)}
          </dd>
        </div>
        <div>
          <dt>Manager Decision</dt>
          <dd>
            {formatValue(decision.state)}
            {decisionRecord !== null && <code>{formatValue(decisionRecord.disposition)}</code>}
          </dd>
        </div>
        <div>
          <dt>Verified occurrences</dt>
          <dd>{occurrenceCount} through event {state.cutoff_event_seq}</dd>
        </div>
      </dl>
      <p className="audit-status">
        Exact content-addressed references and the event prefix remain available in this read-only
        record.
      </p>
    </section>
  );
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

export function DraftContextPreviewPanel({
  preview,
}: {
  preview: DraftContextPreview;
}) {
  const persistedDraft = preview.draft ?? null;
  const [draft, setDraft] = useState<DraftVersion | null>(persistedDraft);
  const [managerDecision, setManagerDecision] = useState<ManagerDecisionResponse | null>(null);
  const [subject, setSubject] = useState(
    persistedDraft?.subject ??
      (typeof preview.artifact.subject === "string" ? preview.artifact.subject : ""),
  );
  const [body, setBody] = useState(persistedDraft?.body ?? preview.artifact.body);
  const [rejectionCode, setRejectionCode] = useState("DRAFT_CONTENT_INACCURATE");
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [mutationState, setMutationState] = useState<
    "idle" | "saving" | "submitting" | "unavailable"
  >("idle");
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const mutationKeys = useRef<Record<string, string>>({});

  useEffect(() => {
    setDraft(persistedDraft);
    setSubject(
      persistedDraft?.subject ??
        (typeof preview.artifact.subject === "string" ? preview.artifact.subject : ""),
    );
    setBody(persistedDraft?.body ?? preview.artifact.body);
    setManagerDecision(null);
    setMutationState("idle");
    setMutationMessage(null);
  }, [persistedDraft?.content_hash, preview.artifact.body, preview.artifact.subject]);

  const contextProvenance = asRecord(preview.draft_context.provenance);
  const recommendationBinding =
    contextProvenance === null ? null : referenceAndHash(contextProvenance.action_recommendation);
  const currentness =
    typeof preview.currentness.currentness_outcome === "string"
      ? preview.currentness.currentness_outcome
      : "UNAVAILABLE";
  const drafting = asRecord(preview.drafting);
  const draftingSource =
    typeof drafting?.source === "string" ? drafting.source : preview.artifact.source;
  const fallback = asRecord(drafting?.fallback);
  const mutationKey = (action: string): string => {
    if (draft === null) {
      throw new Error("draft is unavailable");
    }
    const identity = `${action}:${draft.draft_id}:${draft.content_hash}`;
    const existing = mutationKeys.current[identity];
    if (existing !== undefined) {
      return existing;
    }
    const generated = clientOccurrenceId(`draft-${action.toLowerCase()}`);
    if (generated === null) {
      throw new Error("idempotency is unavailable");
    }
    mutationKeys.current[identity] = generated;
    return generated;
  };
  const headBinding =
    draft === null
      ? null
      : { reference: draft.occurrence_id, content_hash: draft.content_hash };
  const hasUnsavedEdits =
    draft !== null && (subject !== draft.subject || body !== draft.body);
  const saveDraftEdit = async () => {
    if (draft === null || headBinding === null) {
      return;
    }
    if (subject === draft.subject && body === draft.body) {
      setMutationMessage("No content change was submitted; the immutable head is unchanged.");
      return;
    }
    setMutationState("saving");
    setMutationMessage("Validating the edited draft and recording an immutable successor…");
    try {
      const result = await editDraft(draft.draft_id, {
        idempotency_key: mutationKey("edit"),
        expected_head_ref_and_hash: headBinding,
        manager_actor_ref: draft.manager_actor_ref,
        subject,
        body,
      });
      setDraft(result.draft);
      setSubject(result.draft.subject);
      setBody(result.draft.body);
      setMutationState("idle");
      setMutationMessage(
        `Immutable draft successor version ${result.draft.version_number} recorded. No authorization or execution occurred.`,
      );
    } catch {
      setMutationState("unavailable");
      setMutationMessage(
        "The edited draft was unavailable or stale. Read the current draft head and retry; no content or authority was overwritten.",
      );
    }
  };
  const submitDisposition = async (
    disposition: "APPROVE" | "REJECT" | "INVESTIGATE_FURTHER",
  ) => {
    if (draft === null || headBinding === null) {
      return;
    }
    if (disposition === "REJECT" && rejectionDetail.trim() === "") {
      setMutationState("unavailable");
      setMutationMessage("Reject requires a governed reason code and a non-empty detail.");
      return;
    }
    setMutationState("submitting");
    setMutationMessage("Recording the manager disposition as a non-authorizing operation…");
    try {
      const result = await disposeDraft(draft.draft_id, {
        idempotency_key: mutationKey(disposition.toLowerCase()),
        expected_head_ref_and_hash: headBinding,
        manager_actor_ref: draft.manager_actor_ref,
        disposition,
        ...(disposition === "REJECT"
          ? {
              rejection_reason: {
                code: rejectionCode,
                detail: rejectionDetail.trim(),
              },
            }
          : {}),
      });
      setDraft(result.draft);
      setSubject(result.draft.subject);
      setBody(result.draft.body);
      setMutationState("idle");
      setMutationMessage(
        disposition === "INVESTIGATE_FURTHER"
          ? "Investigation further was recorded as an exact manager operation. Evidence and recommendation bindings were not changed."
          : disposition === "REJECT"
            ? "Rejection was recorded with its governed reason. The draft remains unsent and unauthorized."
            : "Approval intent was recorded only. Separate authorization/currentness persistence remains required; nothing was sent or executed.",
      );
    } catch {
      setMutationState("unavailable");
      setMutationMessage(
        "The disposition was unavailable or stale. Read the current draft head and retry; no authorization or execution occurred.",
      );
    }
  };
  const submitManagerDecision = async (
    disposition: "APPROVE" | "REJECT" | "INVESTIGATE_FURTHER",
  ) => {
    if (draft === null || headBinding === null) {
      return;
    }
    const expectedDisposition = {
      APPROVE: "APPROVE_INTENT",
      REJECT: "REJECTED",
      INVESTIGATE_FURTHER: "INVESTIGATE_FURTHER",
    }[disposition];
    if (draft.disposition !== expectedDisposition) {
      setMutationState("unavailable");
      setMutationMessage(
        "Record the matching immutable manager disposition before creating a terminal decision.",
      );
      return;
    }
    setMutationState("submitting");
    setMutationMessage(
      disposition === "APPROVE"
        ? "Re-proving exact authorization-time currentness and publishing the Manager Decision…"
        : "Publishing the terminal non-authorizing Manager Decision…",
    );
    try {
      const result = await recordManagerDecision(draft.draft_id, {
        idempotency_key: mutationKey(`decision-${disposition.toLowerCase()}`),
        expected_head_ref_and_hash: headBinding,
        manager_actor_ref: draft.manager_actor_ref,
        disposition,
      });
      setManagerDecision(result);
      setMutationState(result.result === "CURRENTNESS_REFUSED" ? "unavailable" : "idle");
      setMutationMessage(
        result.result === "CURRENTNESS_REFUSED"
          ? "Authorization was refused because the exact advice was no longer the authoritative head. No Manager Decision, send, or execution was recorded."
          : disposition === "APPROVE"
            ? "Manager authorization was recorded from a fresh exact currentness proof. No message was sent and no action was executed."
            : "The terminal Manager Decision was recorded without fabricating authorization. No message was sent and no action was executed.",
      );
    } catch {
      setMutationState("unavailable");
      setMutationMessage(
        "The Manager Decision was unavailable or stale. Read the current draft head and exact evidence chain; no authority was overwritten.",
      );
    }
  };
  const operation = draft === null ? null : asRecord(draft.manager_operation);
  const terminalDisposition =
    draft?.disposition === "APPROVE_INTENT"
      ? "APPROVE"
      : draft?.disposition === "REJECTED"
        ? "REJECT"
        : draft?.disposition === "INVESTIGATE_FURTHER"
          ? "INVESTIGATE_FURTHER"
          : null;
  const terminalDecision = managerDecision?.decision ?? null;
  return (
    <section
      className="draft-preview action-publication"
      aria-labelledby="draft-preview-heading"
      aria-busy={mutationState === "saving" || mutationState === "submitting" ? "true" : undefined}
    >
      <strong id="draft-preview-heading" aria-live="polite">
        {draftingSource === "GEMINI_CHECKED"
          ? "Checked Gemini unsent draft preview"
          : "Deterministic unsent draft preview"}
      </strong>
      <span>
        State: <code>{preview.artifact.state}</code> · source: <code>{preview.artifact.source}</code>
      </span>
      <span>
        Drafting path: <code>{draftingSource}</code> · cache: <code>{formatValue(drafting?.cache ?? "DISABLED")}</code>
      </span>
      {fallback?.used === true && (
        <span>
          Fallback: <code>{formatValue(fallback.reason_code ?? "UNAVAILABLE")}</code>
        </span>
      )}
      <span>
        Checker: <code>{preview.checker.state}</code> · currentness: <code>{currentness}</code>
      </span>
      <span>
        This content is a preview only. It is not approval, authorization, sending, or execution.
      </span>
      <pre className="draft-preview-body">{preview.artifact.body}</pre>
      {draft !== null && (
        <section className="draft-governance" aria-labelledby="draft-governance-heading">
          <div className="record-heading">
            <div>
              <p className="eyebrow">Manager draft ledger</p>
              <h4 id="draft-governance-heading">Version {draft.version_number} · immutable draft</h4>
            </div>
            <span>{draft.disposition}</span>
          </div>
          <p>
            Draft preparation is complete. Content editing creates a successor version; manager
            selection records intent only. Authorization, sending, and execution are separate.
          </p>
          <dl className="draft-version-facts">
            <div>
              <dt>Actor</dt>
              <dd><code>{draft.manager_actor_ref}</code></dd>
            </div>
            <div>
              <dt>Available time</dt>
              <dd><code>{formatValue(draft.available_at)}</code></dd>
            </div>
            <div>
              <dt>Recommendation reference</dt>
              <dd><code>{formatValue(draft.recommendation_ref_and_hash)}</code></dd>
            </div>
            <div>
              <dt>Evidence reference</dt>
              <dd><code>{formatValue(draft.evidence_ref_and_hash)}</code></dd>
            </div>
            <div>
              <dt>Version hash</dt>
              <dd><code>{draft.content_hash}</code></dd>
            </div>
            <div>
              <dt>Authorization</dt>
              <dd><code>{draft.authorization_state}</code></dd>
            </div>
          </dl>

          <div className="draft-editing">
            <strong>Content editing</strong>
            <label htmlFor="draft-subject">Subject</label>
            <input
              id="draft-subject"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              disabled={mutationState === "saving" || mutationState === "submitting"}
            />
            <label htmlFor="draft-body">Draft body</label>
            <textarea
              id="draft-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={12}
              disabled={mutationState === "saving" || mutationState === "submitting"}
            />
            <button
              type="button"
              onClick={() => void saveDraftEdit()}
              disabled={mutationState === "saving" || mutationState === "submitting"}
            >
              {mutationState === "saving" ? "Saving immutable edit…" : "Save immutable draft edit"}
            </button>
          </div>

          <fieldset className="draft-disposition">
            <legend>Manager selection and disposition</legend>
            {hasUnsavedEdits && (
              <span>Save the immutable content edit before recording a disposition.</span>
            )}
            <label htmlFor="draft-rejection-code">Governed rejection reason</label>
            <select
              id="draft-rejection-code"
              value={rejectionCode}
              onChange={(event) => setRejectionCode(event.target.value)}
              disabled={mutationState === "saving" || mutationState === "submitting"}
            >
              <option value="DRAFT_CONTENT_INACCURATE">Content is inaccurate</option>
              <option value="DRAFT_EVIDENCE_INSUFFICIENT">Evidence is insufficient</option>
              <option value="DRAFT_ACTION_NOT_FEASIBLE">Action is not feasible</option>
              <option value="DRAFT_TIMING_OR_CONSTRAINT_CONFLICT">Timing or constraint conflict</option>
              <option value="DRAFT_NO_LONGER_NEEDED">No longer needed</option>
              <option value="DRAFT_OTHER_GOVERNED">Other governed reason</option>
            </select>
            <label htmlFor="draft-rejection-detail">Rejection detail</label>
            <textarea
              id="draft-rejection-detail"
              value={rejectionDetail}
              onChange={(event) => setRejectionDetail(event.target.value)}
              rows={3}
              placeholder="Explain the governed rejection reason"
              disabled={mutationState === "saving" || mutationState === "submitting"}
            />
            <div className="draft-disposition-actions">
              <button
                type="button"
                onClick={() => void submitDisposition("APPROVE")}
                disabled={
                  hasUnsavedEdits ||
                  mutationState === "saving" ||
                  mutationState === "submitting"
                }
              >
                Approve draft
              </button>
              <button
                type="button"
                onClick={() => void submitDisposition("REJECT")}
                disabled={
                  hasUnsavedEdits ||
                  mutationState === "saving" ||
                  mutationState === "submitting"
                }
              >
                Reject with reason
              </button>
              <button
                type="button"
                onClick={() => void submitDisposition("INVESTIGATE_FURTHER")}
                disabled={
                  hasUnsavedEdits ||
                  mutationState === "saving" ||
                  mutationState === "submitting"
                }
              >
                Investigate further
              </button>
            </div>
            <span>
              These controls record a manager operation. They never send a message, authorize an
              action, or execute operational work.
            </span>
          </fieldset>
          <fieldset className="draft-disposition manager-decision-actions">
            <legend>Terminal Governance decision</legend>
            <p>
              This is the terminal Governance record. Approval requires a new exact
              authorization-time currentness proof; rejection and investigation remain explicitly
              non-authorizing.
            </p>
            {terminalDisposition === null ? (
              <span>Record a manager disposition before publishing its terminal decision.</span>
            ) : (
              <button
                type="button"
                onClick={() => void submitManagerDecision(terminalDisposition)}
                disabled={mutationState === "saving" || mutationState === "submitting"}
              >
                {terminalDisposition === "APPROVE"
                  ? "Authorize and record Manager Decision"
                  : terminalDisposition === "REJECT"
                    ? "Record rejected Manager Decision"
                    : "Record investigate-further Manager Decision"}
              </button>
            )}
            <span>
              Nothing here sends a message or executes an operational action. The immutable result
              below is the authority boundary only.
            </span>
          </fieldset>
          {managerDecision !== null && (
            <section className="manager-decision-result" aria-labelledby="manager-decision-heading">
              <div className="record-heading">
                <div>
                  <p className="eyebrow">Governance terminal record</p>
                  <h4 id="manager-decision-heading">
                    {managerDecision.result === "CURRENTNESS_REFUSED"
                      ? "Authorization refused"
                      : "Manager Decision recorded"}
                  </h4>
                </div>
                <span>{formatValue(terminalDecision?.disposition ?? managerDecision.result)}</span>
              </div>
              {terminalDecision !== null ? (
                <>
                  <p>{String(terminalDecision.no_send_language ?? "No message was sent and no action was executed.")}</p>
                  <dl className="draft-version-facts">
                    <div>
                      <dt>Authorization</dt>
                      <dd><code>{formatValue(terminalDecision.authorization_state)}</code></dd>
                    </div>
                    <div>
                      <dt>Execution</dt>
                      <dd><code>{formatValue(terminalDecision.execution_state)}</code></dd>
                    </div>
                    <div>
                      <dt>Draft version</dt>
                      <dd><code>{formatValue(terminalDecision.draft_version_ref_and_hash)}</code></dd>
                    </div>
                    <div>
                      <dt>Recommendation</dt>
                      <dd><code>{formatValue(terminalDecision.recommendation_ref_and_hash)}</code></dd>
                    </div>
                    <div>
                      <dt>Evidence</dt>
                      <dd><code>{formatValue(terminalDecision.evidence_ref_and_hash)}</code></dd>
                    </div>
                    <div>
                      <dt>Currentness</dt>
                      <dd><code>{formatValue(terminalDecision.currentness_outcome_or_null)}</code></dd>
                    </div>
                  </dl>
                  <details>
                    <summary>Inspect exact authorization, evidence, recommendation, and draft chain</summary>
                    <code>{formatValue({
                      decision: terminalDecision,
                      snapshot: managerDecision.snapshot,
                      authorization_attempt: managerDecision.authorization_attempt,
                      authorization_currentness: managerDecision.authorization_currentness,
                      currentness: managerDecision.currentness,
                      terminal_claim: managerDecision.terminal_claim,
                    })}</code>
                  </details>
                </>
              ) : (
                <p>
                  No Manager Decision was published because the authorization-time currentness
                  proof was refused. No message was sent and no action was executed.
                </p>
              )}
            </section>
          )}
          {operation !== null && (
            <details>
              <summary>Inspect investigate-further operation</summary>
              <code>{formatValue(operation)}</code>
            </details>
          )}
          {mutationMessage !== null && (
            <p className="supporting-copy" role="status">
              {mutationMessage}
            </p>
          )}
        </section>
      )}
      <details>
        <summary>
          Inspect complete {draftingSource === "GEMINI_CHECKED" ? "drafting" : "deterministic"} provenance
        </summary>
        <span>
          Action recommendation: <code>{formatValue(recommendationBinding)}</code>
        </span>
        <code>{formatValue(preview.artifact.provenance)}</code>
      </details>
    </section>
  );
}

export function DecisionSupportActionsStage({
  boundary,
  registryInspection,
}: {
  boundary: DecisionSupportBoundary;
  registryInspection: DecisionSupportRegistryInspection | null;
}) {
  const [tradeoffSelectionState, setTradeoffSelectionState] = useState<
    "idle" | "submitting" | "accepted" | "unavailable"
  >("idle");
  const [selectedTradeoffCandidateRef, setSelectedTradeoffCandidateRef] = useState<string | null>(
    null,
  );
  const [tradeoffSelectionMessage, setTradeoffSelectionMessage] = useState<string | null>(null);
  const [draftPreview, setDraftPreview] = useState<DraftContextPreview | null>(null);
  const [draftPreviewState, setDraftPreviewState] = useState<
    "idle" | "preparing" | "ready" | "unavailable"
  >("idle");
  const [draftPreviewMessage, setDraftPreviewMessage] = useState<string | null>(null);
  const draftCreationKeys = useRef<Record<string, string>>({});
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
  const draftStageStatus =
    actionRecommendation === null
      ? tradeoff !== null
        ? "Waiting: manager choice required"
        : "Unavailable: no recommendation published"
      : "Ready after exact currentness check";
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
  const monitoring = boundary.monitoring;
  const monitoringState =
    typeof monitoring.state === "string" ? monitoring.state : "UNAVAILABLE_OR_UNKNOWN";
  const monitoringReasonCode =
    typeof monitoring.reason_code === "string" ? monitoring.reason_code : null;
  const monitoringSuppressionReasons = Array.isArray(monitoring.suppression_reasons)
    ? monitoring.suppression_reasons
        .map(asRecord)
        .filter((item): item is Record<string, unknown> => item !== null)
    : [];
  const currentnessReasonCodes = currentnessChecks.flatMap((item) =>
    Array.isArray(item.ordered_currentness_reasons)
      ? item.ordered_currentness_reasons.filter(
          (reason): reason is string => typeof reason === "string",
        )
      : [],
  );
  const monitoringTriggerMode =
    actionRecommendation !== null && typeof actionRecommendation.trigger_mode === "string"
      ? actionRecommendation.trigger_mode.toUpperCase()
      : typeof asRecord(boundary.subject_driver_state)?.trigger_mode === "string"
        ? String(asRecord(boundary.subject_driver_state)?.trigger_mode).toUpperCase()
        : null;
  const monitoringTrigger =
    Array.isArray(registry.monitoring_triggers)
      ? registry.monitoring_triggers
          .map(asRecord)
          .find((item) => {
            if (item === null || monitoringTriggerMode === null) {
              return item !== null;
            }
            const modes = Array.isArray(item.trigger_modes)
              ? item.trigger_modes
              : [item.trigger_mode];
            return modes.some(
              (mode): mode is string =>
                typeof mode === "string" && mode.toUpperCase() === monitoringTriggerMode,
            );
          }) ?? null
      : null;
  const monitoringTriggerState =
    monitoringTrigger === null
      ? "UNAVAILABLE"
      : [monitoringTrigger.state, monitoringTrigger.review_status, monitoringTrigger.lifecycle_status]
          .filter((value): value is string => typeof value === "string")
          .join("/") || "UNKNOWN";
  const monitoringMatches =
    lifecycleCurrentness !== null && Array.isArray(lifecycleCurrentness.consuming_results)
      ? lifecycleCurrentness.consuming_results
          .map(asRecord)
          .filter(
            (item): item is Record<string, unknown> =>
              item !== null && item.schema_identifier === "monitoring-match-result",
          )
      : [];
  const latestMonitoringMatch =
    monitoringMatches.length > 0 ? monitoringMatches[monitoringMatches.length - 1] : null;
  const monitoringMatchOutcome =
    typeof latestMonitoringMatch?.match_outcome === "string"
      ? latestMonitoringMatch.match_outcome
      : currentnessStates.ADVICE_CURRENTNESS_INVALIDATION !== undefined ||
          currentnessStates.CURRENTNESS_NOT_AUTHORITATIVE_HEAD !== undefined
        ? "STALE_OR_UNAVAILABLE"
        : "NO_CANONICAL_OBSERVATION";
  const lifecycleEvaluation = lifecycleHistory.find(
    (item) =>
      item.record_type === "evaluation" &&
      item.evaluation_occurrence_id === boundary.decision_support_evaluation_id,
  );
  const tradeoffEvaluationSeriesId =
    typeof evaluationLifecycle?.evaluation_series_id === "string"
      ? evaluationLifecycle.evaluation_series_id
      : null;
  const tradeoffEvaluationOccurrenceId =
    typeof boundary.decision_support_evaluation_id === "string"
      ? boundary.decision_support_evaluation_id
      : null;
  const tradeoffEvaluationDigest =
    typeof lifecycleEvaluation?.evaluation_digest === "string"
      ? lifecycleEvaluation.evaluation_digest
      : typeof boundary.evaluation_digest === "string"
        ? boundary.evaluation_digest
        : null;
  const tradeoffTerminalBinding =
    asRecord(lifecycleEvaluation?.terminal_result_ref_and_hash) ??
    asRecord(boundary.terminal_result_ref_and_hash);
  const prepareDraftPreviewFor = async (
    recommendation: Record<string, unknown> | null,
    adviceChainKind: "IMMEDIATE_EVALUATION_RECOMMENDATION" | "ACCEPTED_TRADEOFF_SELECTION",
    selectionClaim: Record<string, unknown> | null,
  ) => {
    const request = currentAdviceRenderRequest(
      tradeoffEvaluationSeriesId,
      tradeoffEvaluationOccurrenceId,
      tradeoffEvaluationDigest,
      tradeoffTerminalBinding,
      recommendation,
      adviceChainKind,
      selectionClaim,
      recommendation?.evaluation_published_at ??
        lifecycleEvaluation?.evaluation_published_at ??
        boundary.evaluation_published_at,
    );
    if (request === null) {
      setDraftPreviewState("unavailable");
      setDraftPreviewMessage(
        "DraftContext is unavailable because the exact current-advice bindings are incomplete.",
      );
      return;
    }
    setDraftPreviewState("preparing");
    setDraftPreviewMessage("Re-proving currentness and preparing the deterministic preview…");
    try {
      const draftIdentity = `${adviceChainKind}:${String(recommendation?.occurrence_id ?? "")}:${String(selectionClaim?.selection_claim_occurrence_id ?? "")}`;
      let idempotencyKey = draftCreationKeys.current[draftIdentity];
      if (idempotencyKey === undefined) {
        const generatedIdempotencyKey = clientOccurrenceId("draft-create");
        if (generatedIdempotencyKey === null) {
          throw new Error("draft idempotency is unavailable");
        }
        idempotencyKey = generatedIdempotencyKey;
        draftCreationKeys.current[draftIdentity] = idempotencyKey;
      }
      const prepared = await prepareDraftContext(request, {
        idempotencyKey,
        managerActorRef: "anonymous-demo-manager",
      });
      setDraftPreview(prepared);
      setDraftPreviewState("ready");
      setDraftPreviewMessage("Deterministic DraftContext passed its checker; preview remains unsent.");
    } catch {
      setDraftPreview(null);
      setDraftPreviewState("unavailable");
      setDraftPreviewMessage(
        "DraftContext is unavailable or stale. No draft, authorization, or action was created.",
      );
    }
  };
  const selectTradeoffCandidate = async (candidate: Record<string, unknown>) => {
    const candidateRef = tradeoffCandidateReference(candidate);
    const now = new Date().toISOString();
    if (
      candidateRef === null ||
      tradeoffEvaluationSeriesId === null ||
      tradeoffEvaluationOccurrenceId === null ||
      tradeoffEvaluationDigest === null ||
      tradeoffTerminalBinding === null
    ) {
      setTradeoffSelectionState("unavailable");
      setTradeoffSelectionMessage(
        "Selection is unavailable because the exact evaluation binding is not present.",
      );
      return;
    }
    const selectionOccurrenceId = clientOccurrenceId("ui-tradeoff-selection");
    if (selectionOccurrenceId === null) {
      setTradeoffSelectionState("unavailable");
      setTradeoffSelectionMessage(
        "Selection is unavailable because a cryptographic occurrence identity could not be created.",
      );
      return;
    }
    setTradeoffSelectionState("submitting");
    setSelectedTradeoffCandidateRef(candidateRef);
    setTradeoffSelectionMessage("Recording the Governance & Audit selection and proving currentness…");
    const selection = {
      schema_identifier: "tradeoff-selection",
      schema_version: "1",
      selection_occurrence_id: selectionOccurrenceId,
      evaluation_series_id: tradeoffEvaluationSeriesId,
      evaluation_occurrence_id: tradeoffEvaluationOccurrenceId,
      evaluation_digest: tradeoffEvaluationDigest,
      terminal_result_ref_and_hash: tradeoffTerminalBinding,
      selected_candidate_ref: candidateRef,
      selected_candidate: candidate,
      manager_actor_ref: "anonymous-demo-manager",
      selected_at: now,
      available_at: now,
    } as TradeoffSelectionRecord;
    try {
      selection.content_hash = await contentHash(selection);
      selection.governance_tradeoff_selection_ref_and_hash = {
        reference: `governance-tradeoff-selection:${selection.selection_occurrence_id as string}`,
        content_hash: selection.content_hash,
      };
      const published = await publishTradeoffSelection(selection);
      const publishedSelection = published.selection;
      const selectionHash = publishedSelection.content_hash;
      const publishedSelectionOccurrenceId = publishedSelection.selection_occurrence_id;
      const deliveryOccurrenceId = clientOccurrenceId("ui-tradeoff-delivery");
      if (deliveryOccurrenceId === null) {
        throw new Error("cryptographic delivery occurrence identity is unavailable");
      }
      const deliveryAttempt = {
        schema_identifier: "tradeoff-selection-delivery-attempt",
        schema_version: "1",
        occurrence_id: deliveryOccurrenceId,
        tradeoff_selection_ref_and_hash: {
          reference: publishedSelectionOccurrenceId,
          content_hash: selectionHash,
        },
        evaluation_series_id: tradeoffEvaluationSeriesId,
        evaluation_occurrence_id: tradeoffEvaluationOccurrenceId,
        evaluation_digest: tradeoffEvaluationDigest,
        terminal_result_ref_and_hash: tradeoffTerminalBinding,
        selected_candidate_ref: candidateRef,
        selected_candidate: candidate,
        selection_available_at: publishedSelection.available_at,
        delivered_at: now,
        available_at: now,
      } as TradeoffSelectionDeliveryAttempt;
      deliveryAttempt.content_hash = await contentHash(deliveryAttempt);
      const accepted = await acceptTradeoffSelection(
        tradeoffEvaluationSeriesId,
        deliveryAttempt,
        publishedSelection,
      );
      const selectionResult = asRecord(accepted.selection_result);
      const resultCode = selectionResult?.selection_result;
      if (
        resultCode !== "TRADEOFF_SELECTION_ACCEPTED" &&
        resultCode !== "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT"
      ) {
        setTradeoffSelectionState("unavailable");
        setTradeoffSelectionMessage(
          `Selection was not published: ${String(resultCode ?? "UNAVAILABLE")}. No authorization or action was created.`,
        );
        return;
      }
      setTradeoffSelectionState("accepted");
      setTradeoffSelectionMessage(
        `Candidate ${String(candidate.option_code)} was selected under a proven currentness claim. This records a choice only; it is not authorization and does not execute an action.`,
      );
      const acceptedRecommendation = asRecord(accepted.action_recommendation);
      const acceptedSelectionClaim = asRecord(accepted.selection_claim);
      if (acceptedRecommendation !== null && acceptedSelectionClaim !== null) {
        await prepareDraftPreviewFor(
          acceptedRecommendation,
          "ACCEPTED_TRADEOFF_SELECTION",
          acceptedSelectionClaim,
        );
      }
    } catch {
      setTradeoffSelectionState("unavailable");
      setTradeoffSelectionMessage(
        "Selection could not be proven current. No recommendation, authorization, or action was published.",
      );
    }
  };

  return (
    <section
      className="actions-stage journey-stage-target"
      id="stage-actions"
      tabIndex={-1}
      aria-labelledby="actions-stage-heading"
      aria-busy={
        tradeoffSelectionState === "submitting" || draftPreviewState === "preparing"
          ? "true"
          : undefined
      }
    >
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

      <section
        className="draft-stage"
        id="stage-draft"
        tabIndex={-1}
        aria-labelledby="draft-stage-heading"
      >
        <div className="record-heading">
          <div>
            <p className="eyebrow">Stage 5 · Draft &amp; decide</p>
            <h4 id="draft-stage-heading">
              Prepare an unsent preview and retain manager authority
            </h4>
          </div>
          <span>{draftPreviewState === "ready" ? "Preview ready" : draftStageStatus}</span>
        </div>
        <p className="supporting-copy">
          Only a current, governed recommendation can open the draft path. Editing, disposition,
          authorization, sending, and execution remain separate operations.
        </p>
        {actionRecommendation !== null && (
          <div className="action-publication" aria-labelledby="recommendation-heading">
            <strong id="recommendation-heading" aria-live="polite">
              {isMonitoringFallback ? "Accept and Monitor fallback" : "Recommendation available"}
            </strong>
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
            <button
              type="button"
              onClick={() =>
                void prepareDraftPreviewFor(
                  actionRecommendation,
                  "IMMEDIATE_EVALUATION_RECOMMENDATION",
                  null,
                )
              }
              disabled={draftPreviewState === "preparing"}
            >
              {draftPreviewState === "preparing"
                ? "Preparing deterministic preview…"
                : "Prepare deterministic unsent draft"}
            </button>
          </div>
        )}

        {actionRecommendation === null && (
          <p className="lineage-warning" aria-live="polite">
            Draft unavailable. No current Action Recommendation was published; the manager choice
            or evidence gate must remain explicit.
          </p>
        )}
        {draftPreviewMessage !== null && (
          <p className="supporting-copy" role="status" aria-live="polite">
            {draftPreviewMessage}
          </p>
        )}
        {draftPreview !== null && <DraftContextPreviewPanel preview={draftPreview} />}
      </section>

      <div className="action-monitoring" role="status">
        <strong>Governed monitoring fallback</strong>
        <span>
          Eligibility: <code>{formatValue(monitoringState)}</code>
        </span>
        <span>
          Atomic trigger: <code>{formatValue(monitoringTriggerState)}</code>
        </span>
        <span>
          Canonical observation match: <code>{formatValue(monitoringMatchOutcome)}</code>
        </span>
        {monitoringReasonCode !== null && (
          <span>
            Eligibility reason: <code>{monitoringReasonCode}</code>
          </span>
        )}
        {monitoringSuppressionReasons.length > 0 && (
          <span>
            Suppression reasons: <code>{formatValue(monitoringSuppressionReasons)}</code>
          </span>
        )}
        {currentnessReasonCodes.length > 0 && (
          <span>
            Currentness/audit reasons: <code>{formatValue(currentnessReasonCodes)}</code>
          </span>
        )}
        {monitoringMatchOutcome === "REQUEST_MANAGER_REVIEW" ? (
          <span>Manager review was requested; this state does not select, authorize, send, or execute an action.</span>
        ) : monitoringMatchOutcome === "NO_REVIEW_REQUEST" ? (
          <span>The typed predicate did not match; no manager review request was emitted.</span>
        ) : monitoringMatchOutcome === "NO_CANONICAL_OBSERVATION" ? (
          <span>No canonical source observation has been matched for this recommendation.</span>
        ) : (
          <span>The observation or currentness proof is unavailable/stale; no review request is emitted.</span>
        )}
      </div>

      {tradeoff !== null && (
        <div className="action-tradeoff" aria-labelledby="tradeoff-heading">
          <strong id="tradeoff-heading" aria-live="polite">Two-candidate trade-off</strong>
          {tradeoffPivot === "INCOMPARABLE_EVIDENCE_GAP" && (
            <span>Incomparable evidence gap</span>
          )}
          <span>
            Pivot: <code>{formatValue(tradeoffPivot)}</code>
          </span>
          <p>No candidate is recommended; manager choice is required.</p>
          <span>This publication does not imply approval or authorization.</span>
          <span>
            Selection records a manager choice only; it does not authorize or execute an action.
          </span>
          {tradeoffSelectionMessage !== null && (
            <span role="status">{tradeoffSelectionMessage}</span>
          )}
          {tradeoffCandidates.length > 0 && (
            <ol>
              {tradeoffCandidates.map((candidate) => (
                <li key={String(candidate.candidate_label ?? candidate.option_code)}>
                  <div>
                    <code>{formatValue(candidate.option_code)}</code>
                    <button
                      type="button"
                      onClick={() => void selectTradeoffCandidate(candidate)}
                      disabled={tradeoffSelectionState === "submitting"}
                      aria-pressed={
                        selectedTradeoffCandidateRef === tradeoffCandidateReference(candidate)
                      }
                    >
                      {tradeoffSelectionState === "submitting" &&
                      selectedTradeoffCandidateRef === tradeoffCandidateReference(candidate)
                        ? "Proving selection…"
                        : `Select ${formatValue(candidate.option_code)}`}
                    </button>
                  </div>
                  <span>
                    Basis: {formatValue(candidate.candidate_basis ?? candidate.basis)}
                  </span>
                  <details>
                    <summary>Inspect unchanged candidate evidence</summary>
                    <span>
                      Candidate binding: <code>{formatValue(tradeoffCandidateReference(candidate))}</code>
                    </span>
                    <span>
                      Candidate content hash: <code>{formatValue(candidate.content_hash)}</code>
                    </span>
                    <code>{formatValue(candidate.option_evaluation ?? candidate.comparison_profile)}</code>
                  </details>
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
      <section
        className="audit-stage journey-stage-target"
        id="stage-audit"
        tabIndex={-1}
        aria-labelledby="audit-stage-heading"
      >
        <div className="record-heading">
          <div>
            <p className="eyebrow">Stage 6 · Audit replay</p>
            <h4 id="audit-stage-heading">Replay exactly what was known and recorded</h4>
          </div>
          <span>
            {replay?.status === "REPLAYED" && replay.historical_state !== null
              ? "Replay verified"
              : "Replay unavailable"}
          </span>
        </div>
        <p className="supporting-copy">
          Replay is read-only. It does not rerun analysis, call a provider, reevaluate currentness,
          or apply current policy to historical facts.
        </p>
        {replay?.status === "REPLAYED" && replay.historical_state !== null && (
          <HistoricalReplayPanel state={replay.historical_state} />
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

type ShowcaseCase = {
  id: "switchgear" | "concrete" | "hvac";
  priority: "Urgent" | "Needs evidence" | "Monitoring";
  title: string;
  project: string;
  detail: string;
  due: string;
};

type EvidenceStepKey = "signal" | "eligibility" | "causal" | "verdict";

type DemoAuthIdentity = {
  name: string;
  email: string;
  provider: "Google" | "Microsoft" | "Email";
};

const defaultDemoIdentity: DemoAuthIdentity = {
  name: "Alex Morgan",
  email: "alex.morgan@projectalpha.com",
  provider: "Google",
};

function initialsForName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "AM";
}

const showcaseCases: ShowcaseCase[] = [
  {
    id: "switchgear",
    priority: "Urgent",
    title: "Switchgear handoff risk",
    project: "Project Alpha",
    detail: "120 units · Electrical package",
    due: "Decision due today",
  },
  {
    id: "concrete",
    priority: "Needs evidence",
    title: "Concrete enclosure delay",
    project: "Project Alpha",
    detail: "Substructure · Activity 3.2",
    due: "Review due tomorrow",
  },
  {
    id: "hvac",
    priority: "Monitoring",
    title: "HVAC unit long-lead risk",
    project: "Project Beta",
    detail: "Mechanical · Activity 6.1",
    due: "Next review in 2 days",
  },
];

const demoHeroScenario = {
  score: 0.9090909107676192,
  recommendation: "Request supplier recovery plan",
  inputs: {
    source: "Amber risk signal",
    supplier: "PowerGrid Systems",
    order: "120 high-complexity switchgear units",
    package: "Project Alpha · Electrical package",
    promise: "Feb 15, 2026",
    revision: "Feb 20, 2026",
    exposure: "$185,000 order exposure",
  },
  analysis: {
    headline: "The supplier handoff is the decision point.",
    language:
      "High-load exposure is estimated to increase Supplier Milestone Slippage by 1.5 calendar days (95% interval 0.2 to 2.8), under the stated assumptions.",
    scope: "Subject-level support available",
    effect: "1.5 calendar days",
    interval: "0.2 – 2.8 days · 95% interval",
    robustness: "Moderate robustness",
    nextStep: "Request a dated supplier recovery plan",
  },
  recipient: "recovery@powergrid-systems.com",
  subject: "Project Alpha: recovery plan for switchgear handoff",
  body: "Hi Priya,\n\nWe are reviewing the revised February 20 handoff for Project Alpha's switchgear package. Please share a dated recovery plan covering the remaining 120 units, the next confirmed milestone, and any action needed from our team.\n\nPlease send the plan by 3:00 PM today so we can protect the downstream installation sequence.\n\nBest,\nAlex Morgan",
  evidence: {
    signal:
      "The risk signal crossed the review threshold at 91%. It starts an investigation; it is not a causal conclusion.",
    eligibility:
      "The switchgear order line is in scope: the supplier handoff, promised date, revised date, and downstream activity are all bound to the same case.",
    causal:
      "The evidence supports a supplier recovery conversation for this handoff. The recommendation stays bounded to the current evidence chain.",
    verdict:
      "Request a dated recovery plan from the supplier. The manager reviews and sends the message; the copilot does not execute the action.",
  } satisfies Record<EvidenceStepKey, string>,
} as const;

type DemoActionChoice = "recovery" | "monitor" | "escalate";

const demoResponseOptions: Array<{
  id: DemoActionChoice;
  label: string;
  rationale: string;
  subject: string;
  body: string;
  recommended: boolean;
}> = [
  {
    id: "recovery",
    label: "Request supplier recovery plan",
    rationale: "Protect the switchgear handoff with a dated supplier commitment.",
    subject: demoHeroScenario.subject,
    body: demoHeroScenario.body,
    recommended: true,
  },
  {
    id: "monitor",
    label: "Accept and monitor",
    rationale: "Keep the case open and verify the next supplier milestone before escalating.",
    subject: "Project Alpha: monitor switchgear handoff",
    body: "Hi Priya,\n\nPlease confirm the next production milestone for Project Alpha's switchgear handoff and let us know if the February 20 date is still achievable. We will keep the case under review and follow up at the next checkpoint.\n\nBest,\nAlex Morgan",
    recommended: false,
  },
  {
    id: "escalate",
    label: "Escalate to project controls",
    rationale: "Bring the schedule owner into the decision before the downstream sequence is affected.",
    subject: "Project Alpha: switchgear handoff needs schedule review",
    body: "Hi team,\n\nThe Project Alpha switchgear handoff has moved from February 15 to February 20. Please review the downstream installation sequence and confirm the mitigation path for the 120-unit package.\n\nBest,\nAlex Morgan",
    recommended: false,
  },
];

function showcaseValue(value: unknown, fallback = "Unavailable"): string {
  if (typeof value === "string" && value.length > 0) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function showcaseFieldValue(value: unknown, fallback = "Unavailable"): string {
  const field = asRecord(value);
  if (field === null) {
    return fallback;
  }
  const nested = asRecord(field.value);
  return showcaseValue(
    nested?.normalized_value ?? nested?.source_value ?? field.value,
    fallback,
  );
}

function showcaseOptionLabel(value: unknown, fallback: string): string {
  const label = showcaseValue(value, "");
  if (label.length === 0) {
    return fallback;
  }
  return label
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/(^|\s)\S/g, (character) => character.toUpperCase());
}

function ShowcaseEvidenceIcon({ step }: { step: EvidenceStepKey }) {
  if (step === "signal") {
    return <Events size={20} aria-hidden="true" />;
  }
  if (step === "eligibility") {
    return <Document size={20} aria-hidden="true" />;
  }
  if (step === "causal") {
    return <FlowData size={20} aria-hidden="true" />;
  }
  return <CheckmarkFilled size={20} aria-hidden="true" />;
}

function ShowcaseDashboard({
  journeyState,
  health,
  referenceState,
  riskState,
  riskFixture,
  riskAttempt,
  decisionBriefState,
  decisionBrief,
  actionRecommendation,
  demoMode,
  identity,
  onOpenAuth,
  onRetry,
}: {
  journeyState: JourneyState;
  health: HealthResponse | null;
  referenceState: ReferenceState;
  riskState: RiskState;
  riskFixture: RiskSignalFixture | undefined;
  riskAttempt: ReactiveIngressAttempt | null;
  decisionBriefState: DecisionBriefState;
  decisionBrief: DecisionBriefSnapshot | null;
  actionRecommendation: Record<string, unknown> | null;
  demoMode: boolean;
  identity: DemoAuthIdentity;
  onOpenAuth: () => void;
  onRetry: () => void;
}) {
  const [selectedCaseId, setSelectedCaseId] = useState<ShowcaseCase["id"]>("switchgear");
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceStepKey>("signal");
  const [searchQuery, setSearchQuery] = useState("");
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("Workbench");
  const [announcement, setAnnouncement] = useState("Workbench ready.");
  const [demoDraftOpened, setDemoDraftOpened] = useState(false);
  const [demoGmailStatus, setDemoGmailStatus] = useState<"idle" | "opened">("idle");
  const [demoActionChoice, setDemoActionChoice] = useState<DemoActionChoice>("recovery");
  const [demoDraftTo, setDemoDraftTo] = useState<string>(demoHeroScenario.recipient);
  const [demoDraftSubject, setDemoDraftSubject] = useState<string>(demoHeroScenario.subject);
  const [demoDraftBody, setDemoDraftBody] = useState<string>(demoHeroScenario.body);

  const moveToSurface = (targetId: string, label: string) => {
    const target = document.getElementById(targetId);
    if (target === null) {
      setAnnouncement(`${label} is not available yet.`);
      return;
    }
    const parentDetails = target.closest("details");
    if (parentDetails instanceof HTMLDetailsElement) {
      parentDetails.open = true;
    }
    setActiveNav(label);
    target.scrollIntoView({
      behavior:
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
      block: "start",
    });
    if (typeof target.focus === "function") {
      target.focus({ preventScroll: true });
    }
    setAnnouncement(`Moved to ${label}.`);
  };

  const filteredCases = showcaseCases.filter((item) => {
    const query = searchQuery.trim().toLowerCase();
    const matchesQuery =
      query.length === 0 ||
      `${item.title} ${item.project} ${item.detail}`.toLowerCase().includes(query);
    return matchesQuery && (!urgentOnly || item.priority === "Urgent");
  });
  const selectedCase =
    showcaseCases.find((item) => item.id === selectedCaseId) ?? showcaseCases[0];
  const isHeroCase = selectedCase.id === "switchgear";
  const demoHeroActive = demoMode && isHeroCase;
  const selectedDemoAction =
    demoResponseOptions.find((option) => option.id === demoActionChoice) ??
    demoResponseOptions[0];
  const request = riskAttempt?.investigation_request ?? null;
  const requestSubject = asRecord(request?.causal_engine_input.subject_analytical_values);
  const score = demoHeroActive ? demoHeroScenario.score : riskFixture?.signal.score_value;
  const scoreLabel = typeof score === "number" ? `${Math.round(score * 100)}%` : "—";
  const subjectState = decisionBrief?.subject_applicability.state ?? null;
  const actionReady = demoHeroActive || actionRecommendation !== null;
  const actionLabel = actionReady
    ? demoHeroActive
      ? selectedDemoAction.label
      : showcaseOptionLabel(
        actionRecommendation?.label ?? actionRecommendation?.selected_option_code,
        "Review governed response",
      )
    : "Awaiting governed recommendation";
  const evidenceReady = demoHeroActive || decisionBriefState === "ready";
  const safeStateUnavailable = !demoHeroActive && journeyState === "unavailable";
  const draftRecipient = demoHeroActive
    ? demoDraftTo
    : actionReady
      ? demoHeroScenario.recipient
      : "";
  const draftSubject = demoHeroActive
    ? demoDraftSubject
    : actionReady
      ? demoHeroScenario.subject
      : "";
  const draftBody = demoHeroActive ? demoDraftBody : "";
  const openDemoGmail = () => {
    const gmailUrl = new URL("https://mail.google.com/mail/");
    gmailUrl.searchParams.set("view", "cm");
    gmailUrl.searchParams.set("fs", "1");
    gmailUrl.searchParams.set("to", demoDraftTo);
    gmailUrl.searchParams.set("su", demoDraftSubject);
    gmailUrl.searchParams.set("body", demoDraftBody);
    window.open(gmailUrl.toString(), "_blank", "noopener,noreferrer");
    setDemoGmailStatus("opened");
    setAnnouncement("Gmail compose opened in a new tab. Sending remains with the manager.");
  };
  const openDemoDraft = () => {
    setDemoDraftOpened(true);
    moveToSurface("demo-draft", "Draft workspace");
  };
  const chooseDemoAction = (choice: DemoActionChoice) => {
    const option = demoResponseOptions.find((candidate) => candidate.id === choice);
    setDemoActionChoice(choice);
    if (demoHeroActive && option !== undefined) {
      setDemoDraftSubject(option.subject);
      setDemoDraftBody(option.body);
      setDemoDraftOpened(false);
      setDemoGmailStatus("idle");
      setAnnouncement(`${option.label} selected. Review the draft before handing it to Gmail.`);
    }
  };
  const openEvidenceDetails = () => {
    if (demoHeroActive) {
      setAnnouncement(`${selectedStep.title} evidence is available in the current case record.`);
      return;
    }
    moveToSurface(
      selectedStep.key === "signal"
        ? "stage-risk-intake"
        : selectedStep.key === "eligibility"
          ? "stage-eligibility"
          : "stage-evidence",
      `${selectedStep.title} details`,
    );
  };
  const effectiveJourneyState = demoHeroActive ? "healthy" : journeyState;
  const effectiveReferenceState = demoHeroActive ? "ready" : referenceState;
  const effectiveSubjectState = demoHeroActive ? "supported" : subjectState;
  const renderedVerdict = asRecord(decisionBrief?.rendered_subject_verdict);
  const analysisLanguage = demoHeroActive
    ? demoHeroScenario.analysis.language
    : decisionBrief?.subject_applicability.state === "abstained"
      ? "Population evidence is available, but this case does not support a subject-level effect claim."
      : showcaseValue(
          renderedVerdict?.language,
          decisionBriefState === "ready"
            ? "Decision Brief published. Open the evidence record for the rendered conclusion."
            : "The analysis conclusion will appear after the evidence chain is ready.",
        );
  const analysisScope = demoHeroActive
    ? demoHeroScenario.analysis.scope
    : decisionBrief?.subject_applicability.state === "applicable"
      ? "Subject-level support available"
      : decisionBrief?.subject_applicability.state === "population_limited"
        ? "Population-level evidence only"
        : "Support unavailable";
  const analysisEffect = demoHeroActive ? demoHeroScenario.analysis.effect : "See Decision Brief";
  const analysisInterval = demoHeroActive
    ? demoHeroScenario.analysis.interval
    : "Bound to the published evidence verdict";
  const analysisRobustness = demoHeroActive
    ? demoHeroScenario.analysis.robustness
    : decisionBriefState === "ready"
      ? "Published with diagnostics"
      : "Not evaluated";
  const analysisNextStep = actionReady
    ? actionLabel
    : "No manager action is published yet";
  const coreStatus =
    demoHeroActive
      ? "Workspace ready"
      : journeyState === "loading"
      ? "Checking Core"
      : journeyState === "unavailable"
        ? "Core unavailable"
        : health?.readiness.state === "degraded"
          ? "Core ready · drafting limited"
          : "Core ready";
  const signalStatus =
    demoHeroActive
      ? `${scoreLabel} flagged`
      : riskState === "loading"
      ? "Checking signal"
      : riskState === "ready"
        ? `${scoreLabel} flagged`
        : riskState === "failed"
          ? "Unavailable"
          : "Waiting";
  const eligibilityStatus =
    demoHeroActive
      ? "In scope"
      : riskState !== "ready"
      ? "Waiting"
      : request?.causal_engine_input.eligibility !== undefined
        ? "In scope"
        : "Review required";
  const causalStatus =
    demoHeroActive
      ? "Evaluated"
      : decisionBriefState === "publishing"
      ? "Verifying"
      : decisionBriefState !== "ready"
        ? "Waiting"
        : subjectState === "abstained"
          ? "Read-only"
          : "Evaluated";
  const verdictStatus =
    demoHeroActive
      ? "Decision ready"
      : decisionBriefState !== "ready"
      ? "Waiting"
      : subjectState === "abstained"
        ? "Needs support"
        : "Decision ready";
  const evidenceSteps: Array<{
    key: EvidenceStepKey;
    title: string;
    description: string;
    status: string;
  }> = [
    {
      key: "signal",
      title: "Signal",
      description: "What triggered this case",
      status: signalStatus,
    },
    {
      key: "eligibility",
      title: "Eligibility",
      description: "Why this case is in scope",
      status: eligibilityStatus,
    },
    {
      key: "causal",
      title: "Causal analysis",
      description: "What the evidence can support",
      status: causalStatus,
    },
    {
      key: "verdict",
      title: "Verdict",
      description: "What the manager can conclude",
      status: verdictStatus,
    },
  ];
  const selectedStep =
    evidenceSteps.find((step) => step.key === selectedEvidence) ?? evidenceSteps[0];
  const selectedStepDetail = demoHeroActive
    ? demoHeroScenario.evidence[selectedEvidence]
    : selectedEvidence === "signal"
      ? riskState === "ready"
        ? `The risk signal crossed the review threshold at ${scoreLabel}. It starts an investigation; it is not a causal conclusion.`
        : "The workspace is waiting for a verified risk signal before it creates an investigation."
      : selectedEvidence === "eligibility"
        ? request === null
          ? "The investigation request has not been accepted yet."
          : `The request is bound to a canonical subject and a decision cutoff of ${showcaseFieldValue(request.decision_cutoff, "the recorded cutoff")}.`
        : selectedEvidence === "causal"
          ? decisionBriefState !== "ready"
            ? "The immutable Decision Brief is still being prepared."
            : subjectState === "abstained"
              ? "Population evidence is available, but this reference does not support a subject-level effect claim."
              : "The causal analysis has been evaluated under the evidence and eligibility contract."
          : effectiveSubjectState === "abstained"
            ? "This case is read-only until subject support is available. The copilot will not invent a recommendation."
            : "The verdict is ready to inform the manager's next decision.";

  return (
    <section className="workbench-shell" id="workspace" aria-labelledby="workbench-heading">
      <header className="workbench-topbar">
        <div className="workbench-brand-block">
          <button className="workbench-icon-button workbench-menu-button" type="button" aria-label="Open navigation">
            <Menu size={20} aria-hidden="true" />
          </button>
          <button className="workbench-brand" type="button" onClick={() => moveToSurface("workspace", "Workbench")}>
            Causal Delay Copilot
          </button>
        </div>

        <nav className="workbench-primary-nav" aria-label="Primary">
          {[
            { label: "Workbench", target: "workspace" },
            { label: "Evidence", target: "technical-evidence" },
            { label: "Decisions", target: "stage-actions" },
            { label: "Configuration", target: "lineage-heading" },
          ].map((item) => (
            <button
              className={`workbench-nav-link ${activeNav === item.label ? "is-active" : ""}`}
              key={item.label}
              type="button"
              onClick={() =>
                item.target === "workspace"
                  ? (setActiveNav(item.label), moveToSurface("workspace", item.label))
                  : moveToSurface(item.target, item.label)
              }
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="workbench-topbar-tools">
          <div className="workbench-core-status" role="status" aria-live="polite">
            <span className={`workbench-status-dot ${effectiveJourneyState === "unavailable" ? "is-error" : ""}`} aria-hidden="true" />
            {coreStatus}
          </div>
          <button className="workbench-icon-button" type="button" aria-label="Notifications">
            <Notification size={20} aria-hidden="true" />
          </button>
          <div className="workbench-user-menu">
            <button
              className="workbench-user-button"
              type="button"
              aria-expanded={userMenuOpen}
              onClick={() => setUserMenuOpen((open) => !open)}
            >
              <span className="workbench-avatar" aria-hidden="true">{initialsForName(identity.name)}</span>
              <span className="workbench-user-name">{identity.name}</span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {userMenuOpen && (
              <div className="workbench-user-popover" role="menu">
                <strong>Signed in with {identity.provider}</strong>
                <span>{identity.email}</span>
                <button type="button" role="menuitem" onClick={() => { setUserMenuOpen(false); onOpenAuth(); }}>Switch account</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="workbench-layout">
        <aside className="workbench-inbox" aria-labelledby="attention-inbox-heading">
          <div className="workbench-inbox-heading">
            <div>
              <p className="workbench-overline">Today</p>
              <h2 id="attention-inbox-heading">Attention inbox</h2>
            </div>
            <span className="workbench-count" aria-label={`${showcaseCases.length} cases`}>{showcaseCases.length}</span>
          </div>
          <p className="workbench-inbox-summary">Prioritised cases that need a manager's attention.</p>
          <div className="workbench-inbox-tools">
            <label className="workbench-search-wrap">
              <Search size={16} aria-hidden="true" />
              <span className="visually-hidden">Find a case</span>
              <input
                className="workbench-search"
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Find a case"
              />
            </label>
            <button
              className={`workbench-filter-button ${urgentOnly ? "is-active" : ""}`}
              type="button"
              aria-pressed={urgentOnly}
              onClick={() => setUrgentOnly((active) => !active)}
            >
              <SettingsAdjust size={16} aria-hidden="true" />
              <span className="visually-hidden">{urgentOnly ? "Show all cases" : "Show urgent cases"}</span>
            </button>
          </div>

          <div className="workbench-case-list">
            {filteredCases.length === 0 ? (
              <div className="workbench-inbox-empty">
                <Search size={20} aria-hidden="true" />
                <p>No cases match that search.</p>
                <button type="button" onClick={() => { setSearchQuery(""); setUrgentOnly(false); }}>Clear filters</button>
              </div>
            ) : (
              filteredCases.map((item) => (
                <button
                  className={`workbench-case-item ${selectedCaseId === item.id ? "is-selected" : ""}`}
                  key={item.id}
                  type="button"
                  aria-pressed={selectedCaseId === item.id}
                  onClick={() => {
                    setSelectedCaseId(item.id);
                    setAnnouncement(`${item.title} selected.`);
                  }}
                >
                  <span className={`workbench-case-priority priority-${item.priority.toLowerCase().replace(/\s+/g, "-")}`}>
                    <span className="workbench-priority-dot" aria-hidden="true" />
                    {item.priority}
                  </span>
                  <strong>{item.title}</strong>
                  <span>{item.project}</span>
                  <span>{item.detail}</span>
                  <span className="workbench-case-due">{item.due}<ChevronRight size={16} aria-hidden="true" /></span>
                </button>
              ))
            )}
          </div>

          <button className="workbench-link-button workbench-inbox-footer" type="button" onClick={() => { setSearchQuery(""); setUrgentOnly(false); setAnnouncement("Showing all cases."); }}>
            View all cases
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        </aside>

        <main className="workbench-main" aria-labelledby="workbench-heading">
          {!isHeroCase ? (
            <section className="workbench-empty-case" aria-live="polite">
              <p className="workbench-overline">{selectedCase.priority}</p>
              <h1>{selectedCase.title}</h1>
              <p className="workbench-empty-case-copy">
                This case is in the inbox, but its verified investigation has not been opened in this workspace yet.
              </p>
              <button className="workbench-button workbench-button-primary" type="button" onClick={() => setSelectedCaseId("switchgear")}>
                Return to switchgear case
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </section>
          ) : (
            <>
              <div className="workbench-case-header">
                <div className="workbench-breadcrumbs">
                  <span>Project Alpha</span>
                  <ChevronRight size={14} aria-hidden="true" />
                  <span>Case CASE-1052</span>
                  <span className="workbench-case-updated">{demoHeroActive ? "Updated just now" : riskAttempt === null ? "Waiting for Core" : "Updated just now"}</span>
                </div>
                <div className="workbench-case-heading-row">
                  <div>
                    <p className="workbench-overline workbench-overline-blue">Urgent case</p>
                    <h1 id="workbench-heading">Switchgear handoff risk</h1>
                    <p className="workbench-case-subtitle">120 high-complexity units · Electrical package · Supplier handoff</p>
                  </div>
                  <button className="workbench-quiet-button" type="button" onClick={() => moveToSurface("stage-risk-intake", "Risk intake")}>
                    <Document size={16} aria-hidden="true" />
                    View case record
                  </button>
                </div>

                <div className="workbench-metric-row" aria-label="Case summary">
                  <div className="workbench-metric workbench-metric-emphasis">
                    <span>Risk level</span>
                    <strong>High</strong>
                  </div>
                  <div className="workbench-metric">
                    <span>Amber signal</span>
                    <strong>{scoreLabel}</strong>
                  </div>
                  <div className="workbench-metric">
                    <span>Promised handoff</span>
                    <strong>Feb 15</strong>
                  </div>
                  <div className="workbench-metric">
                    <span>Revised handoff</span>
                    <strong>Feb 20</strong>
                  </div>
                  <div className="workbench-metric">
                    <span>Decision owner</span>
                    <strong>{identity.name}</strong>
                  </div>
                </div>
              </div>

              <section className="workbench-case-input" aria-labelledby="case-input-heading">
                <div className="workbench-case-input-heading">
                  <div>
                    <p className="workbench-overline">What came in</p>
                    <h2 id="case-input-heading">Amber flagged a supplier handoff risk</h2>
                    <p>These are the frozen inputs the Copilot uses before it makes any causal or action claim.</p>
                  </div>
                  <button className="workbench-link-button" type="button" onClick={() => { setSelectedEvidence("signal"); setAnnouncement("Showing the upstream Amber signal inputs."); }}>
                    Inspect source signal <ArrowUpRight size={16} aria-hidden="true" />
                  </button>
                </div>
                <dl className="workbench-input-facts">
                  <div><dt>Source</dt><dd>{demoHeroScenario.inputs.source}</dd></div>
                  <div><dt>Supplier</dt><dd>{demoHeroScenario.inputs.supplier}</dd></div>
                  <div><dt>Order line</dt><dd>{demoHeroScenario.inputs.order}</dd></div>
                  <div><dt>Milestone</dt><dd>{demoHeroScenario.inputs.promise} → {demoHeroScenario.inputs.revision}</dd></div>
                  <div><dt>Project value</dt><dd>{demoHeroScenario.inputs.exposure}</dd></div>
                </dl>
              </section>

              <section className="workbench-status-band" aria-label="Causal status">
                <div className="workbench-status-primary">
                  {evidenceReady && effectiveSubjectState === "abstained" ? (
                    <WarningAltFilled size={24} aria-hidden="true" />
                  ) : (
                    <Information size={24} aria-hidden="true" />
                  )}
                  <div>
                    <span>Causal status</span>
                    <strong>{evidenceReady && effectiveSubjectState === "abstained" ? "Needs subject support" : evidenceReady ? "Evidence reviewed" : "Investigation in progress"}</strong>
                  </div>
                </div>
                <div className="workbench-status-stat">
                  <span>Evidence state</span>
                  <strong>{evidenceReady ? "Decision Brief ready" : decisionBriefState === "publishing" ? "Publishing" : "Waiting"}</strong>
                </div>
                <div className="workbench-status-stat">
                  <span>Action lane</span>
                  <strong>{actionReady ? "Recommendation ready" : "Read-only"}</strong>
                </div>
                <div className="workbench-status-stat">
                  <span>Release</span>
                  <strong>{effectiveReferenceState === "ready" ? "Validated" : referenceState === "loading" ? "Checking" : "Unavailable"}</strong>
                </div>
              </section>

              <section className="workbench-evidence-section" id="evidence-chain" aria-labelledby="evidence-chain-heading">
                <div className="workbench-section-heading">
                  <div>
                    <p className="workbench-overline">The decision path</p>
                    <h2 id="evidence-chain-heading">From signal to verdict</h2>
                  </div>
                  <button className="workbench-link-button" type="button" onClick={() => demoHeroActive ? setAnnouncement("The verified evidence chain is open in this case.") : moveToSurface("stage-evidence", "Evidence")}>Review all evidence <ArrowUpRight size={16} aria-hidden="true" /></button>
                </div>
                <div className="workbench-evidence-chain">
                  {evidenceSteps.map((step, index) => (
                    <button
                      className={`workbench-evidence-step ${selectedEvidence === step.key ? "is-selected" : ""}`}
                      key={step.key}
                      type="button"
                      aria-pressed={selectedEvidence === step.key}
                      onClick={() => {
                        setSelectedEvidence(step.key);
                        setAnnouncement(`${step.title} evidence selected.`);
                      }}
                    >
                      <span className="workbench-evidence-step-top">
                        <span className="workbench-evidence-icon"><ShowcaseEvidenceIcon step={step.key} /></span>
                        <span className="workbench-evidence-index">0{index + 1}</span>
                      </span>
                      <strong>{step.title}</strong>
                      <span>{step.description}</span>
                      <span className={`workbench-step-status status-${step.key}`}>{step.status}</span>
                      <ChevronRight className="workbench-evidence-chevron" size={16} aria-hidden="true" />
                    </button>
                  ))}
                </div>
                <div className="workbench-evidence-detail" role="status" aria-live="polite">
                  <div className="workbench-evidence-detail-label">
                    <ShowcaseEvidenceIcon step={selectedStep.key} />
                    <strong>{selectedStep.title}</strong>
                  </div>
                  <p>{selectedStepDetail}</p>
                  <button className="workbench-link-button" type="button" onClick={openEvidenceDetails}>
                    Open details <ArrowRight size={16} aria-hidden="true" />
                  </button>
                </div>
                <section className="workbench-analysis-readout" aria-labelledby="analysis-readout-heading">
                  <div className="workbench-analysis-copy">
                    <p className="workbench-overline">What the evidence says</p>
                    <h2 id="analysis-readout-heading">{demoHeroActive ? demoHeroScenario.analysis.headline : "The analysis conclusion"}</h2>
                    <p>{analysisLanguage}</p>
                  </div>
                  <dl className="workbench-analysis-facts">
                    <div><dt>Claim scope</dt><dd>{analysisScope}</dd></div>
                    <div><dt>Estimated effect</dt><dd>{analysisEffect}</dd></div>
                    <div><dt>Uncertainty</dt><dd>{analysisInterval}</dd></div>
                    <div><dt>Evidence quality</dt><dd>{analysisRobustness}</dd></div>
                  </dl>
                  <div className="workbench-analysis-next">
                    <span>Next permitted step</span>
                    <strong>{analysisNextStep}</strong>
                    <small>The manager chooses and owns the response. The Copilot does not execute it.</small>
                  </div>
                </section>
              </section>

              <section className="workbench-activity-section" aria-labelledby="activity-heading">
                <div className="workbench-section-heading">
                  <div>
                    <p className="workbench-overline">Case history</p>
                    <h2 id="activity-heading">Recent activity</h2>
                  </div>
                  <button className="workbench-link-button" type="button" onClick={() => moveToSurface("stage-audit", "Decision history")}>View decision history <ArrowUpRight size={16} aria-hidden="true" /></button>
                </div>
                <ol className="workbench-activity-list">
                  <li><span className="workbench-activity-dot" aria-hidden="true" /><span><strong>Risk signal received</strong><small>{demoHeroActive ? "Investigation accepted" : riskState === "ready" ? "Investigation accepted by Core" : "Waiting for verified intake"}</small></span><time>Today</time></li>
                  <li><span className="workbench-activity-dot" aria-hidden="true" /><span><strong>Evidence chain opened</strong><small>Signal separated from causal analysis</small></span><time>{demoHeroActive || decisionBriefState === "ready" ? "Today" : "Pending"}</time></li>
                  <li><span className="workbench-activity-dot" aria-hidden="true" /><span><strong>Manager review</strong><small>{actionReady ? "Recommendation ready" : "Awaiting subject support"}</small></span><time>{actionReady ? "Next" : "Pending"}</time></li>
                </ol>
              </section>
            </>
          )}
        </main>

        <aside className="workbench-action-rail" aria-labelledby="action-brief-heading">
          <div className="workbench-action-heading">
            <div>
              <p className="workbench-overline">Manager review</p>
              <h2 id="action-brief-heading">Action brief</h2>
            </div>
            <button className="workbench-icon-button" type="button" aria-label="Open action brief in focus view" onClick={() => demoHeroActive ? openDemoDraft() : moveToSurface("stage-actions", "Actions")}>
              <ArrowUpRight size={18} aria-hidden="true" />
            </button>
          </div>

          <section className={`workbench-action-summary ${actionReady ? "is-ready" : "is-waiting"}`}>
            <div className="workbench-action-summary-top">
              <span className="workbench-action-symbol" aria-hidden="true">{actionReady ? <CheckmarkFilled size={20} /> : <WarningAltFilled size={20} />}</span>
              <span>{actionReady ? demoHeroActive && !selectedDemoAction.recommended ? "Selected response" : "Recommended response" : "No action published"}</span>
            </div>
            <h3>{actionLabel}</h3>
            <p>{actionReady ? demoHeroActive ? "Open the draft, make any edits, then hand the message off to Gmail. No message is sent from this workspace." : "This response is bound to the current evidence chain and still needs manager approval." : decisionBrief?.action_lane.state === "read_only" ? "The current reference is read-only. The copilot will not invent an action from incomplete subject support." : "Complete the evidence chain before asking the manager to act."}</p>
            <div className="workbench-action-reason">
              <span>Why this matters</span>
              <strong>{actionReady ? demoHeroActive ? selectedDemoAction.rationale : "Protect the switchgear handoff" : "Keep the decision explainable"}</strong>
            </div>
            <button className={`workbench-button ${actionReady ? "workbench-button-primary" : "workbench-button-secondary"}`} type="button" onClick={() => demoHeroActive ? openDemoDraft() : moveToSurface(actionReady ? "stage-draft" : "stage-actions", actionReady ? "Draft workspace" : "Actions") }>
              {actionReady ? <><Email size={18} aria-hidden="true" /> {demoHeroActive ? "Review & edit draft" : "Approve draft & open Gmail"} <Launch size={16} aria-hidden="true" /></> : <><ArrowRight size={18} aria-hidden="true" /> Open evidence &amp; actions</>}
            </button>
            <button className="workbench-button workbench-button-quiet" type="button" onClick={() => moveToSurface("stage-evidence", "Evidence")}>Review before deciding</button>
          </section>

          {demoHeroActive && (
            <section className="workbench-response-options" aria-labelledby="response-options-heading">
              <div className="workbench-draft-heading">
                <div>
                  <p className="workbench-overline">Manager input</p>
                  <h3 id="response-options-heading">Choose the next conversation</h3>
                </div>
                <span className="workbench-draft-state is-ready">1 selected</span>
              </div>
              <p className="workbench-response-copy">The evidence informs the choice; it does not make the choice for you.</p>
              <div className="workbench-response-list" role="group" aria-label="Response options">
                {demoResponseOptions.map((option) => (
                  <button
                    className={`workbench-response-option ${demoActionChoice === option.id ? "is-selected" : ""}`}
                    key={option.id}
                    type="button"
                    aria-pressed={demoActionChoice === option.id}
                    onClick={() => chooseDemoAction(option.id)}
                  >
                    <span className="workbench-response-option-marker" aria-hidden="true" />
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.rationale}</small>
                    </span>
                    {option.recommended && <em>Recommended</em>}
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="workbench-draft-panel" id="demo-draft" aria-labelledby="draft-preview-heading">
            <div className="workbench-draft-heading">
              <div>
                <p className="workbench-overline">Next step</p>
                <h3 id="draft-preview-heading">Supplier email</h3>
              </div>
              <span className={`workbench-draft-state ${actionReady ? "is-ready" : ""}`}>{demoHeroActive ? demoGmailStatus === "opened" ? "Gmail opened" : demoDraftOpened ? "Reviewing" : "Ready" : actionReady ? "Editable" : "Waiting"}</span>
            </div>
            <label className="workbench-field">
              <span>To</span>
              <input type="email" value={draftRecipient} onChange={(event) => demoHeroActive && setDemoDraftTo(event.target.value)} placeholder="Recipient appears after approval path" readOnly={!demoHeroActive} />
            </label>
            <label className="workbench-field">
              <span>Subject</span>
              <input type="text" value={draftSubject} onChange={(event) => demoHeroActive && setDemoDraftSubject(event.target.value)} placeholder="Subject appears after approval path" readOnly={!demoHeroActive} />
            </label>
            <label className="workbench-field">
              <span>Message</span>
              <textarea value={draftBody} onChange={(event) => demoHeroActive && setDemoDraftBody(event.target.value)} placeholder={actionReady ? "Open the draft workspace to prepare the unsent message." : "The unsent draft is created only after a governed recommendation."} readOnly={!demoHeroActive} />
            </label>
            <div className="workbench-draft-footnote"><Information size={16} aria-hidden="true" /><span>{demoHeroActive ? "Approve opens Gmail with this message prefilled. Sending always stays with the manager." : "When the draft is ready, Gmail opens prefilled. Sending always stays with the manager."}</span></div>
            {demoHeroActive && (
              <div className="workbench-draft-actions">
                <button className="workbench-button workbench-button-primary" type="button" onClick={openDemoGmail}>
                  <Email size={18} aria-hidden="true" /> Approve draft &amp; open Gmail <Launch size={16} aria-hidden="true" />
                </button>
                {demoGmailStatus === "opened" && <p className="workbench-draft-confirmation" role="status">Gmail compose opened in a new tab. Review and send it there.</p>}
              </div>
            )}
          </section>

          <section className="workbench-safe-state" role="status" aria-live="polite">
            <span className="workbench-safe-icon"><Information size={16} aria-hidden="true" /></span>
            <div>
              <strong>{safeStateUnavailable ? "Core is unavailable" : "Human approval stays in the loop"}</strong>
              <p>{safeStateUnavailable ? "Retry the Core check before trusting any case state." : "No message is sent and no operational action runs from this screen."}</p>
            </div>
            {safeStateUnavailable && <button className="workbench-icon-button" type="button" aria-label="Retry Core check" onClick={onRetry}><Renew size={16} aria-hidden="true" /></button>}
          </section>
        </aside>
      </div>

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">{announcement}</div>
    </section>
  );
}

function CausalMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" stroke="currentColor" strokeWidth="2" />
      <path d="M8 10H15M8 16H22M8 22H15" stroke="currentColor" strokeWidth="2" strokeLinecap="square" />
      <circle cx="23" cy="10" r="3" fill="currentColor" />
      <circle cx="23" cy="22" r="3" fill="currentColor" />
    </svg>
  );
}

function GoogleMark() {
  return (
    <svg className="auth-provider-logo" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path fill="#4285F4" d="M21.35 12.27c0-.78-.07-1.54-.22-2.27H12v4.3h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.69 2.91-4.18 2.91-7.42Z" />
      <path fill="#34A853" d="M12 21.75c2.63 0 4.84-.87 6.45-2.36l-3.14-2.45c-.87.58-1.98.92-3.31.92-2.54 0-4.7-1.72-5.47-4.03H3.28v2.53A9.75 9.75 0 0 0 12 21.75Z" />
      <path fill="#FBBC05" d="M6.53 13.83a5.86 5.86 0 0 1 0-3.66V7.64H3.28a9.75 9.75 0 0 0 0 8.72l3.25-2.53Z" />
      <path fill="#EA4335" d="M12 6.14c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.23 14.63 2.25 12 2.25a9.75 9.75 0 0 0-8.72 5.39l3.25 2.53C7.3 7.86 9.46 6.14 12 6.14Z" />
    </svg>
  );
}

function MicrosoftMark() {
  return (
    <svg className="auth-provider-logo auth-provider-logo-microsoft" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path fill="#F25022" d="M2.5 2.5h9.1v9.1H2.5z" />
      <path fill="#7FBA00" d="M12.4 2.5h9.1v9.1h-9.1z" />
      <path fill="#00A4EF" d="M2.5 12.4h9.1v9.1H2.5z" />
      <path fill="#FFB900" d="M12.4 12.4h9.1v9.1h-9.1z" />
    </svg>
  );
}

function AuthStory({ onResetMode }: { onResetMode: () => void }) {
  return (
    <section className="auth-story" aria-label="What Causal Delay Copilot does">
      <div className="auth-story-header">
        <button className="auth-brand" type="button" onClick={onResetMode}>
          <span className="auth-brand-mark" aria-hidden="true"><CausalMark size={22} /></span>
          <span className="auth-brand-lockup">
            <strong>Causal Delay</strong>
            <small>Copilot</small>
          </span>
        </button>
        <span className="auth-story-tag">Manager workspace</span>
      </div>

      <div className="auth-story-content">
        <p className="auth-overline">Supply-chain decision support</p>
        <h1>Make the next move before a delay becomes a domino effect.</h1>
        <p>Bring risk signals, evidence, and manager action into one focused operating surface.</p>

        <div className="auth-product-preview" aria-label="Product flow preview">
          <div className="auth-preview-header">
            <span>Case preview</span>
            <span className="auth-preview-status"><span aria-hidden="true" />Review ready</span>
          </div>
          <div className="auth-preview-case">
            <div className="auth-preview-case-heading">
              <span className="auth-preview-case-icon" aria-hidden="true"><WarningAltFilled size={18} /></span>
              <span>
                <strong>Switchgear handoff risk</strong>
                <small>Project Alpha · Electrical package</small>
              </span>
              <span className="auth-preview-priority">Urgent</span>
            </div>
            <div className="auth-preview-track" aria-label="Signal to action flow">
              <span className="is-complete"><i>1</i>Signal</span>
              <span className="is-complete"><i>2</i>Evidence</span>
              <span className="is-current"><i>3</i>Action</span>
            </div>
            <div className="auth-preview-callout">
              <span><CheckmarkFilled size={16} aria-hidden="true" /></span>
              <p>120 units at risk. A recovery-plan draft is ready for manager review.</p>
              <ArrowRight size={16} aria-hidden="true" />
            </div>
          </div>
        </div>

        <div className="auth-story-steps" aria-label="Product flow">
          <div><span>01</span><strong>Detect</strong><small>Surface the cases that need attention.</small></div>
          <div><span>02</span><strong>Explain</strong><small>Make the evidence chain easy to inspect.</small></div>
          <div><span>03</span><strong>Act</strong><small>Prepare the next move without losing control.</small></div>
        </div>
      </div>

      <div className="auth-story-footer">
        <span>Built for project delivery teams</span>
        <span className="auth-story-footer-mark"><CausalMark size={14} /> Evidence-led decisions</span>
      </div>
    </section>
  );
}

function DemoAuth({
  onComplete,
}: {
  onComplete: (identity: DemoAuthIdentity) => void;
}) {
  const [mode, setMode] = useState<"sign-in" | "create">("sign-in");
  const [provider, setProvider] = useState<"Google" | "Microsoft" | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const finishWithProvider = () => {
    if (provider === null) {
      return;
    }
    onComplete({
      name: defaultDemoIdentity.name,
      email: defaultDemoIdentity.email,
      provider,
    });
  };

  const submitEmail = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedEmail = email.trim();
    if (!trimmedEmail.includes("@")) {
      setError("Enter a work email to continue.");
      return;
    }
    if (mode === "create" && name.trim().length < 2) {
      setError("Enter your name to create a workspace.");
      return;
    }
    if (password.length < 4) {
      setError("Use at least 4 characters for your password.");
      return;
    }
    onComplete({
      name: mode === "create" ? name.trim() : "Alex Morgan",
      email: trimmedEmail,
      provider: "Email",
    });
  };

  return (
    <main className="auth-shell" aria-labelledby="auth-heading">
      <AuthStory onResetMode={() => { setMode("sign-in"); setProvider(null); setError(null); }} />

      {provider !== null ? (
        <section className="auth-panel auth-provider-panel" aria-labelledby="auth-heading">
          <div className="auth-provider-panel-topline">
            <button className="auth-back-button" type="button" onClick={() => setProvider(null)}>
              <ChevronRight className="auth-back-icon" size={18} aria-hidden="true" />
              Back to sign in
            </button>
            <span className="auth-provider-mark" aria-hidden="true">{provider === "Google" ? <GoogleMark /> : <MicrosoftMark />}</span>
          </div>
          <div className="auth-panel-header">
            <p className="auth-overline">Continue with {provider}</p>
            <h1 id="auth-heading">Choose an account</h1>
            <p className="auth-copy">Select the manager identity you want to use for this workspace.</p>
          </div>
          <button className="auth-account-choice" type="button" onClick={finishWithProvider}>
            <span className="auth-account-avatar" aria-hidden="true">AM</span>
            <span>
              <strong>Alex Morgan</strong>
              <small>alex.morgan@projectalpha.com</small>
            </span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
          <div className="auth-provider-note">
            <Information size={16} aria-hidden="true" />
            <p>The selected account will be used for the manager review workspace and approved email handoff.</p>
          </div>
        </section>
      ) : (
        <section className="auth-panel" aria-labelledby="auth-heading">
          <div className="auth-panel-inner">
            <div className="auth-panel-header">
              <p className="auth-overline">{mode === "sign-in" ? "Welcome back" : "Create your workspace"}</p>
              <h1 id="auth-heading">{mode === "sign-in" ? "Sign in to your workspace" : "Start with a manager workspace"}</h1>
              <p className="auth-copy">{mode === "sign-in" ? "Pick up where your team left off." : "Set up your workspace and bring the next decision into focus."}</p>
            </div>

            <form className="auth-form" onSubmit={submitEmail}>
              {mode === "create" && (
                <label>
                  <span>Your name</span>
                  <input autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Alex Morgan" />
                </label>
              )}
              <label>
                <span>Work email</span>
                <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" />
              </label>
              <label>
                <span>Password</span>
                <input type="password" autoComplete={mode === "sign-in" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
              </label>
              {error !== null && <p className="auth-error" role="alert">{error}</p>}
              <button className="auth-submit-button" type="submit">
                {mode === "sign-in" ? "Sign in" : "Create account"}
                <ArrowRight size={18} aria-hidden="true" />
              </button>
            </form>

            <div className="auth-divider"><span>or continue with</span></div>

            <div className="auth-provider-actions">
              <button className="auth-provider-button" type="button" onClick={() => setProvider("Google")}>
                <GoogleMark />
                <span>Google</span>
              </button>
              <button className="auth-provider-button" type="button" onClick={() => setProvider("Microsoft")}>
                <MicrosoftMark />
                <span>Microsoft</span>
              </button>
            </div>

            <div className="auth-mode-switch">
              <span>{mode === "sign-in" ? "New to the workspace?" : "Already have an account?"}</span>
              <button type="button" onClick={() => { setMode(mode === "sign-in" ? "create" : "sign-in"); setError(null); }}>
                {mode === "sign-in" ? "Create account" : "Sign in"}
              </button>
            </div>
            <p className="auth-legal">By continuing, you agree to use this workspace for manager review and decision support.</p>
          </div>
        </section>
      )}
    </main>
  );
}

function App() {
  const [authView, setAuthView] = useState<"workbench" | "auth">(() => {
    if (typeof window === "undefined") {
      return "workbench";
    }
    return new URLSearchParams(window.location.search).get("view") === "signin"
      ? "auth"
      : "workbench";
  });
  const [demoMode] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return new URLSearchParams(window.location.search).get("demo") === "hero";
  });
  const [demoIdentity, setDemoIdentity] = useState<DemoAuthIdentity>(defaultDemoIdentity);
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
      await getReleaseIdentity();
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
      health?.fresh_run.state === "unavailable" ||
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
  }, [health, reference, riskAttempt]);

  const requestFreshReproduction = useCallback(async () => {
    const targetRun = freshOperation?.analysis_run;
    if (
      health?.fresh_run.state === "unavailable" ||
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
  }, [freshOperation, health]);

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
    if (authView === "auth") {
      return;
    }
    void loadHealth();
  }, [authView, loadHealth]);

  const statusMessage =
    journeyState === "loading"
      ? "Checking Core health"
      : journeyState === "unavailable"
        ? "Core health is unavailable"
        : health?.readiness.state === "degraded"
          ? "Core ready with Gemini-only drafting unavailable"
          : "Core ready";
  const freshRunUnavailable = health?.fresh_run.state === "unavailable";
  const acceptedRiskFixture = preferredRiskFixture(riskFixtures);
  const predictiveArtifactsVerified = hasVerifiedPredictiveArtifacts(acceptedRiskFixture);
  const proactiveRequest = proactiveAttempt?.investigation_request ?? null;
  const proactiveSubject =
    proactiveRequest !== null &&
    "kind" in proactiveRequest.subject &&
    proactiveRequest.subject.kind === "proactive_preview"
      ? proactiveRequest.subject
      : null;
  const decisionSupport = decisionBrief?.decision_support ?? null;
  const decisionBriefSnapshotReady = decisionBriefState === "ready" && decisionBrief !== null;
  const decisionSupportStageAvailable = decisionBriefSnapshotReady && decisionSupport !== null;
  const actionRecommendation = decisionSupport?.action_recommendation ?? null;
  const riskIntakeStageStatus =
    journeyState === "loading"
      ? "Loading Core health"
      : journeyState === "unavailable"
        ? "Unavailable: Core health"
        : riskState === "loading"
          ? "Loading verified intake"
          : riskState === "ready"
            ? "Ready: investigation accepted"
            : riskState === "failed"
              ? "Unavailable: no verified signal"
              : "Waiting for verified intake";
  const eligibilityStageStatus =
    riskState === "loading"
      ? "Loading eligibility inputs"
      : riskState === "ready" &&
          riskAttempt !== null &&
          riskAttempt.investigation_request !== null &&
          riskAttempt.investigation_request !== undefined
        ? "Ready: subject gate is visible"
        : riskState === "failed"
          ? "Unavailable: no frozen investigation"
          : "Waiting for accepted investigation";
  const evidenceStageStatus =
    decisionBriefState === "publishing"
      ? "Publishing immutable snapshot"
      : decisionBriefState === "ready"
        ? decisionBrief?.subject_applicability.state === "abstained"
          ? "Abstained: no effect claim"
          : "Ready: verdict before actions"
        : decisionBriefState === "failed"
          ? "Unavailable: no verified snapshot"
          : "Waiting for accepted intake";
  const actionsStageStatus =
    decisionBrief === null
      ? "Unavailable: no Decision Brief"
      : decisionSupport === null
        ? "Read-only: no evaluation published"
        : decisionSupportStateLabel(decisionSupport.state);
  const draftStageStatus =
    decisionSupport === null
      ? "Unavailable: evidence gate is read-only"
      : actionRecommendation !== null
        ? "Ready after exact currentness check"
        : decisionSupport.tradeoff !== null
          ? "Waiting: manager choice required"
          : "Unavailable: no recommendation published";
  const auditStageStatus =
    decisionBriefReplay?.status === "REPLAYED" && decisionBriefReplay.historical_state !== null
      ? "Replay verified"
      : decisionBriefState === "ready"
        ? "Unavailable: exact replay not available"
        : "Waiting for immutable snapshot";
  const journeyStages: JourneyStage[] = [
    {
      key: "risk-intake",
      label: "Risk intake",
      targetId: "stage-risk-intake",
      status: riskIntakeStageStatus,
    },
    {
      key: "eligibility",
      label: "Eligibility",
      targetId: "stage-eligibility",
      status: eligibilityStageStatus,
    },
    {
      key: "evidence",
      label: "Evidence",
      targetId: "stage-evidence",
      status: evidenceStageStatus,
    },
    {
      key: "actions",
      label: "Actions",
      targetId: "stage-actions",
      status: actionsStageStatus,
    },
    {
      key: "draft",
      label: "Draft & decide",
      targetId: "stage-draft",
      status: draftStageStatus,
    },
    {
      key: "audit",
      label: "Audit replay",
      targetId: "stage-audit",
      status: auditStageStatus,
    },
  ];

  const openDemoAuth = () => {
    setAuthView("auth");
    if (typeof window !== "undefined") {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.set("view", "signin");
      window.history.replaceState({}, "", nextUrl);
    }
  };

  const completeDemoAuth = (identity: DemoAuthIdentity) => {
    setDemoIdentity(identity);
    setAuthView("workbench");
    if (typeof window !== "undefined") {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.delete("view");
      window.history.replaceState({}, "", nextUrl);
    }
  };

  if (authView === "auth") {
    return <DemoAuth onComplete={completeDemoAuth} />;
  }

  return (
    <main className="core-shell core-shell--workbench" aria-labelledby="workbench-heading">
      <a className="skip-link" href="#workspace">
        Skip to workbench
      </a>

      <ShowcaseDashboard
        journeyState={journeyState}
        health={health}
        referenceState={referenceState}
        riskState={riskState}
        riskFixture={acceptedRiskFixture}
        riskAttempt={riskAttempt}
        decisionBriefState={decisionBriefState}
        decisionBrief={decisionBrief}
        actionRecommendation={actionRecommendation}
        demoMode={demoMode}
        identity={demoIdentity}
        onOpenAuth={openDemoAuth}
        onRetry={() => void loadHealth()}
      />

      <details className="technical-details" id="technical-evidence">
        <summary>
          <span>
            <span className="technical-details-kicker">Under the hood</span>
            <strong>Open technical evidence &amp; audit</strong>
          </span>
          <span className="technical-details-summary-action">Core contracts, diagnostics, replay, and recovery</span>
        </summary>
        <div className="technical-details-body">
      <header className="core-header">
        <p className="eyebrow">Causal Delay Copilot</p>
        <h1 id="app-heading">Core application health</h1>
        <p className="lede">
          One contract-first browser application with a typed API and an
          immutable audit ledger.
        </p>
      </header>

      <JourneyStageNav stages={journeyStages} />

      <section
        className="health-panel"
        aria-labelledby="health-heading"
        aria-busy={journeyState === "loading" ? "true" : undefined}
      >
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

            {freshRunUnavailable && (
              <p className="lineage-warning" role="status">
                Fresh demo runs are unavailable until three consecutive verified runs finish
                under five minutes. The validated reference remains read-only and available.
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
                  <section
                    className="operation-panel"
                    aria-labelledby="fresh-operation-heading"
                    aria-busy={
                      freshOperationState === "starting" ||
                      freshOperationState === "polling" ||
                      reproductionOperationState === "starting" ||
                      reproductionOperationState === "polling" ||
                      refreshOperationState === "starting" ||
                      refreshOperationState === "polling"
                        ? "true"
                        : undefined
                    }
                  >
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
                        freshRunUnavailable ||
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
                          : freshRunUnavailable
                            ? "Fresh run unavailable"
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
                        freshRunUnavailable ||
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
        <section
          className="risk-panel journey-stage-target"
          id="stage-risk-intake"
          tabIndex={-1}
          aria-labelledby="risk-heading"
          aria-busy={
            riskState === "loading" ||
            proactiveState === "loading" ||
            decisionBriefState === "publishing"
              ? "true"
              : undefined
          }
        >
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

          <section
            className="journey-stage-overview"
            id="stage-eligibility"
            tabIndex={-1}
            aria-labelledby="eligibility-stage-heading"
          >
            <p className="eyebrow">Stage 2 · Eligibility</p>
            <h3 id="eligibility-stage-heading">
              Check whether this subject can support a defensible result
            </h3>
            <p className="supporting-copy">
              Eligibility is checked before estimation or Decision Support. Missing, abstained,
              stale, and unavailable inputs stay visible and do not become a result.
            </p>
            <p className="stage-status-copy" aria-live="polite">
              {eligibilityStageStatus}.
            </p>
          </section>

          <section
            className="journey-stage-overview"
            id="stage-evidence"
            tabIndex={-1}
            aria-labelledby="evidence-stage-heading"
          >
            <p className="eyebrow">Stage 3 · Evidence</p>
            <h3 id="evidence-stage-heading">
              Read the evidence verdict before any action lane
            </h3>
            <p className="supporting-copy">
              The immutable Decision Brief Snapshot exposes claim scope, diagnostics, and
              abstention before options, drafting, or authorization.
            </p>
            <p className="stage-status-copy" aria-live="polite">
              {evidenceStageStatus}.
            </p>
          </section>

          {!decisionSupportStageAvailable && (
            <>
              <JourneyStagePlaceholder
                eyebrow="Stage 4 · Actions"
                targetId="stage-actions"
                headingId="actions-stage-heading"
                heading="Keep the action lane read-only until evidence permits review"
                description="Decision Support is a governed boundary. A missing, abstained, stale, or unavailable verdict never becomes a recommendation or authorization."
                status={actionsStageStatus}
              />
              <JourneyStagePlaceholder
                eyebrow="Stage 5 · Draft & decide"
                targetId="stage-draft"
                headingId="draft-stage-heading"
                heading="Prepare an unsent preview and retain manager authority"
                description="Drafting remains a preview-only operation. Editing, disposition, authorization, sending, and execution stay separate and explicit."
                status={draftStageStatus}
              />
            </>
          )}
          {!decisionBriefSnapshotReady && (
            <JourneyStagePlaceholder
              eyebrow="Stage 6 · Audit replay"
              targetId="stage-audit"
              headingId="audit-stage-heading"
              heading="Replay exactly what was known and recorded"
              description="Replay is read-only and cannot run until an immutable Decision Brief Snapshot exists."
              status={auditStageStatus}
            />
          )}

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
                <p className="lineage-warning" aria-live="polite">
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
                <p className="lineage-warning" aria-live="polite">
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
        </div>
      </details>
    </main>
  );
}

export default App;
