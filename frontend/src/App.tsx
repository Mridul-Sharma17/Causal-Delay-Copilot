import { useCallback, useEffect, useRef, useState } from "react";

import {
  getDatasetLineage,
  getHealth,
  getWorkspace,
  importHeroDataset,
  recordBootOccurrence,
} from "./api";
import {
  auditOutcomeCode,
  type AuditOccurrenceResponse,
  type DemoWorkspace,
  type HealthState,
  type HealthResponse,
  type LineageRecord,
  type LineageSnapshot,
} from "./contracts";
import "./styles.css";

type JourneyState = "loading" | "healthy" | "unavailable";
type AuditState = "pending" | "recorded" | "failed";
type WorkspaceState = "pending" | "created" | "failed";
type LineageState = "pending" | "loading" | "ready" | "failed";

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

function fieldState(value: LineageRecord): string {
  return typeof value.state === "string" ? value.state : "unresolved";
}

function fieldValue(value: LineageRecord): unknown {
  return value.value;
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
  const [auditState, setAuditState] = useState<AuditState>("pending");
  const [auditOccurrence, setAuditOccurrence] =
    useState<AuditOccurrenceResponse | null>(null);
  const [lineageState, setLineageState] = useState<LineageState>("pending");
  const [lineage, setLineage] = useState<LineageSnapshot | null>(null);
  const bootKey = useRef<string | null>(null);

  const loadHealth = useCallback(async () => {
    setJourneyState("loading");
    try {
      const nextHealth = await getHealth();
      setHealth(nextHealth);
      setJourneyState("healthy");
      setWorkspace(null);
      setWorkspaceState("pending");
      setAuditState("pending");
      setLineage(null);
      setLineageState("pending");

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

      setLineageState("loading");
      try {
        const imported = await importHeroDataset();
        const snapshot = await getDatasetLineage(imported.dataset_version_id);
        setLineage(snapshot);
        setLineageState("ready");
      } catch {
        setLineage(null);
        setLineageState("failed");
      }
    } catch {
      setHealth(null);
      setWorkspace(null);
      setWorkspaceState("failed");
      setJourneyState("unavailable");
      setAuditState("failed");
      setLineageState("failed");
    }
  }, []);

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
          </>
        )}
      </section>

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
                                  <span>Value: {formatValue(fieldValue(value))}</span>
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
                                        : `State: ${fieldState(field)} · Value: ${formatValue(fieldValue(field))}`;
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
