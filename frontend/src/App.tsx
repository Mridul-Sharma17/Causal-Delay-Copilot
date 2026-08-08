import { useCallback, useEffect, useRef, useState } from "react";

import {
  getDatasetLineage,
  getHealth,
  getProactiveProposals,
  getRiskSignals,
  getValidatedReference,
  getWorkspace,
  recordBootOccurrence,
  submitReactiveInvestigation,
  submitProactiveInvestigation,
} from "./api";
import {
  auditOutcomeCode,
  type AuditOccurrenceResponse,
  type DemoWorkspace,
  type HealthState,
  type HealthResponse,
  type LineageRecord,
  type LineageSnapshot,
  type PredictiveRiskStatus,
  type ProactiveIngressAttempt,
  type ProactiveProposalFixture,
  type ReactiveIngressAttempt,
  type RiskSignalFixture,
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
  const [riskFailureAttempt, setRiskFailureAttempt] =
    useState<ReactiveIngressAttempt | null>(null);
  const [riskFailureState, setRiskFailureState] = useState<RiskState>("pending");
  const [proactiveState, setProactiveState] = useState<RiskState>("pending");
  const [proactiveFixtures, setProactiveFixtures] = useState<ProactiveProposalFixture[]>([]);
  const [proactiveAttempt, setProactiveAttempt] =
    useState<ProactiveIngressAttempt | null>(null);
  const bootKey = useRef<string | null>(null);

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
      setRiskFailureAttempt(null);
      setRiskFailureState("pending");
      setProactiveState("pending");
      setProactiveFixtures([]);
      setProactiveAttempt(null);

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
