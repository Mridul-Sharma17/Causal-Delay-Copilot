from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from .audit import AuditIdempotencyConflict, AuditStoreUnavailable
from .canonical import canonical_json as _canonical_json
from .canonical import sha256 as _sha256
from .diagnostics import diagnostic_summary as _diagnostic_summary
from .validity import (
    ValidityIntegrityError,
    derive_subject_evidence_verdict,
    render_evidence_verdict,
    render_subject_evidence_verdict,
    verify_evidence_verdict,
)


GOVERNANCE_SCHEMA_VERSION = "governance.v1"
DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION = "decision-brief-snapshot.v2"
REPLAY_SCHEMA_VERSION = "replay.v1"

DECISION_BRIEF_SNAPSHOTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_brief_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        investigation_request_id TEXT NOT NULL REFERENCES investigation_requests(investigation_request_id),
        idempotency_key TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        occurrence_id TEXT NOT NULL UNIQUE,
        event_seq INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, idempotency_key)
    )
"""
DECISION_BRIEF_SNAPSHOTS_COLUMNS = [
    "snapshot_id",
    "workspace_id",
    "investigation_request_id",
    "idempotency_key",
    "reference_id",
    "content_hash",
    "occurrence_id",
    "event_seq",
    "created_at",
    "payload_json",
]


class InvestigationRequestUnavailable(Exception):
    """The immutable Investigation Request is not available for publication."""


class DecisionBriefUnavailable(Exception):
    """A stored Decision Brief Snapshot failed its integrity contract."""


@dataclass(frozen=True, slots=True)
class StoredDecisionBrief:
    result: str
    snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReplayDecisionBrief:
    status: str
    investigation_request_id: str
    requested_event_seq: int
    last_verified_event_seq: int
    snapshot: dict[str, Any] | None
    unresolved_references: list[str]
    recovery_action: str


def _ensure_table(
    connection: sqlite3.Connection,
    table_name: str,
    create_sql: str,
    expected_columns: list[str],
    *,
    create: bool,
) -> None:
    if create:
        connection.execute(create_sql)
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if [str(column[1]) for column in columns] != expected_columns:
        raise sqlite3.DatabaseError(
            f"{table_name} schema is not the locked governance schema"
        )


def ensure_governance_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    _ensure_table(
        connection,
        "decision_brief_snapshots",
        DECISION_BRIEF_SNAPSHOTS_TABLE,
        DECISION_BRIEF_SNAPSHOTS_COLUMNS,
        create=create,
    )
    if create:
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS decision_brief_snapshots_immutable_update
            BEFORE UPDATE ON decision_brief_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'decision brief snapshots are immutable');
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS decision_brief_snapshots_immutable_delete
            BEFORE DELETE ON decision_brief_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'decision brief snapshots are immutable');
            END
            """
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat()


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) and value else default


def _reference_projection(reference: object) -> dict[str, Any]:
    evidence_verdict = getattr(reference, "evidence_verdict", None)
    verified_verdict: dict[str, Any] | None = None
    rendered_verdict: dict[str, str] | None = None
    if evidence_verdict is not None:
        if not isinstance(evidence_verdict, Mapping):
            raise DecisionBriefUnavailable("reference evidence verdict is not an object")
        try:
            verified_verdict = verify_evidence_verdict(evidence_verdict)
            rendered_verdict = render_evidence_verdict(verified_verdict)
        except ValidityIntegrityError as error:
            raise DecisionBriefUnavailable("reference evidence verdict is invalid") from error

    diagnostics = getattr(reference, "diagnostic_results", ())
    if not isinstance(diagnostics, (list, tuple)):
        raise DecisionBriefUnavailable("reference diagnostic results are invalid")
    reference_slot_id = _text(getattr(reference, "reference_slot_id", None))
    bundle_manifest_hash = _text(
        getattr(reference, "bundle_manifest_hash", None)
    )

    projection: dict[str, Any] = {
        "schema_version": "validated-reference-snapshot.v1",
        "delivery_schema_version": "analysis-run-read-model.v1",
        "delivery_mode": _text(
            getattr(reference, "delivery_mode", None),
            default="existing_run_reuse",
        ),
        "delivery_badge": "Validated reference",
        "verification_state": _text(
            getattr(reference, "verification_state", None),
            default="reference_validated",
        ),
        "reference_id": reference_slot_id,
        "reference_slot_id": reference_slot_id,
        "analysis_run_id": _text(getattr(reference, "analysis_run_id", None)),
        "bundle_manifest_hash": bundle_manifest_hash,
        "bundle_ref": bundle_manifest_hash,
        "validation_attestation_id": _text(
            getattr(reference, "validation_attestation_id", None)
        ),
        "validation_attestation_ref": _text(
            getattr(reference, "validation_attestation_ref", None)
        ),
        "release_candidate_id": _text(
            getattr(reference, "release_candidate_id", None)
        ),
        "intended_role": _text(getattr(reference, "intended_role", None)),
        "engine_result_status": _text(
            getattr(reference, "engine_result_status", None)
        ),
        "scientific_request_digest": _text(
            getattr(reference, "scientific_request_digest", None)
        ),
        "dataset_version_id": _text(getattr(reference, "dataset_version_id", None)),
        "cache_key": _text(getattr(reference, "cache_key", None), default=""),
        "runtime_fingerprint_digest": _text(
            getattr(reference, "runtime_fingerprint_digest", None)
        ),
        "validation_policy_version": _text(
            getattr(reference, "validation_policy_version", None)
        ),
        "validated_at": _timestamp(getattr(reference, "validated_at")),
        "completed_at": _timestamp(getattr(reference, "completed_at")),
        "diagnostics": deepcopy([dict(item) for item in diagnostics]),
        "diagnostic_summary": _diagnostic_summary(diagnostics),
        "robustness_grade": deepcopy(getattr(reference, "robustness_grade", None)),
        "evidence_verdict": verified_verdict,
        "rendered_verdict": rendered_verdict,
    }
    if not projection["reference_slot_id"] or not projection["dataset_version_id"]:
        raise DecisionBriefUnavailable("reference identity is incomplete")
    projection["reference_record_hash"] = _sha256(projection)
    return projection


def _request_from_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise InvestigationRequestUnavailable from error
    if not isinstance(payload, Mapping):
        raise InvestigationRequestUnavailable
    request = deepcopy(dict(payload))
    stored_hash = request.pop("content_hash", None)
    expected_hash = _sha256(
        {
            key: value
            for key, value in request.items()
            if key != "accepted_at"
        }
    )
    if stored_hash != expected_hash or str(row["content_hash"]) != stored_hash:
        raise InvestigationRequestUnavailable
    request["content_hash"] = stored_hash
    if request.get("investigation_request_id") != str(row["investigation_request_id"]):
        raise InvestigationRequestUnavailable
    return request


def _subject_inputs(request: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    subject = _mapping(request.get("subject")) or {}
    subject_id = _text(subject.get("order_line_id")) or _text(
        subject.get("preview_subject_digest")
    )
    causal_input = _mapping(request.get("causal_engine_input")) or {}
    eligibility = _mapping(causal_input.get("eligibility")) or {}
    eligibility_subject = _mapping(eligibility.get("subject")) or {}
    profile = _mapping(eligibility_subject.get("inputs")) or {}
    propensity = _mapping(eligibility_subject.get("propensity")) or {
        "state": "unavailable",
        "value": None,
        "support_interval": {"lower": 0.10, "upper": 0.90, "inclusive": True},
    }
    distribution = _mapping(eligibility_subject.get("distribution_support")) or {
        "state": "unavailable",
        "reason_code": "SUBJECT_DISTRIBUTION_UNSUPPORTED",
    }
    return subject_id, dict(profile), dict(propensity), dict(distribution)


def _subject_applicability(
    *,
    request: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, str] | None]:
    subject_id, profile, propensity, distribution = _subject_inputs(request)
    population = reference.get("evidence_verdict")
    if not isinstance(population, Mapping) or not subject_id:
        unavailable = {
            "schema_version": "subject-applicability.v1",
            "state": "unavailable",
            "subject_identity": subject_id or "unavailable",
            "subject_profile": profile,
            "propensity_support": propensity,
            "distribution_support": distribution,
            "population_permission": False,
            "source_role_ceiling": False,
            "reason_code": "POPULATION_EVIDENCE_UNAVAILABLE",
            "reason": "A verified population Evidence Verdict is unavailable for this reference journey.",
            "next_step": "Restore a verified population Evidence Verdict before applying evidence to this subject.",
        }
        return unavailable, None, None

    subject_verdict = derive_subject_evidence_verdict(
        population,
        subject_id=subject_id,
        subject_profile=profile,
        subject_propensity=propensity,
        distribution_support=distribution,
        source_role=_text(reference.get("intended_role")),
    )
    rendered = render_subject_evidence_verdict(subject_verdict)
    gates = subject_verdict.get("subject_gates", [])
    if not isinstance(gates, list):
        gates = []
    gate_states = {
        str(gate.get("gate")): str(gate.get("state"))
        for gate in gates
        if isinstance(gate, Mapping)
    }
    applicability = {
        "schema_version": "subject-applicability.v1",
        "state": subject_verdict["subject_applicability_state"],
        "subject_identity": subject_verdict["subject_identity"],
        "subject_profile": profile,
        "subject_profile_hash": subject_verdict["subject_profile_hash"],
        "propensity_support": propensity,
        "distribution_support": distribution,
        "gates": deepcopy(gates),
        "population_permission": gate_states.get("population_permission") == "passed",
        "source_role_ceiling": gate_states.get("source_role_ceiling") == "passed",
        "population_verdict_ref": subject_verdict["population_verdict_ref"],
        "reason_code": subject_verdict["primary_trigger_code"],
        "reason": rendered["language"],
        "next_step": rendered["next_step"],
        "claim_scope": subject_verdict["permitted_claim_scope"],
    }
    return applicability, subject_verdict, rendered


def _ingress_attempt_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    trigger_mode = request.get("trigger_mode")
    if trigger_mode == "reactive":
        table_name = "reactive_ingress_attempts"
        occurrence_kind = "REACTIVE_INGRESS"
    elif trigger_mode == "proactive":
        table_name = "proactive_ingress_attempts"
        occurrence_kind = "PROACTIVE_INGRESS"
    else:
        raise DecisionBriefUnavailable("investigation trigger mode is unsupported")

    row = connection.execute(
        f"""
        SELECT attempts.attempt_id, attempts.content_hash,
               attempts.occurrence_id, attempts.event_seq,
               attempts.received_at, attempts.payload_json
        FROM {table_name} AS attempts
        JOIN audit_events AS audit
          ON audit.workspace_id = attempts.workspace_id
         AND audit.occurrence_id = attempts.occurrence_id
         AND audit.event_seq = attempts.event_seq
         AND audit.content_hash = attempts.content_hash
         AND audit.occurrence_kind = ?
        WHERE attempts.workspace_id = ?
          AND attempts.investigation_request_id = ?
        """,
        (occurrence_kind, workspace_id, request["investigation_request_id"]),
    ).fetchone()
    if row is None:
        raise DecisionBriefUnavailable("ingress attempt is unavailable")
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionBriefUnavailable("ingress attempt payload is invalid") from error
    if not isinstance(payload, Mapping):
        raise DecisionBriefUnavailable("ingress attempt payload is not an object")
    attempt = deepcopy(dict(payload))
    if (
        attempt.get("attempt_id") != str(row["attempt_id"])
        or attempt.get("investigation_request_id")
        != str(request["investigation_request_id"])
    ):
        raise DecisionBriefUnavailable("ingress attempt identity is inconsistent")
    audit = _mapping(attempt.get("audit"))
    if audit is None or (
        audit.get("occurrence_id") != str(row["occurrence_id"])
        or audit.get("event_seq") != int(row["event_seq"])
    ):
        raise DecisionBriefUnavailable("ingress attempt audit binding is inconsistent")
    return {
        "schema_version": "ingress-attempt-snapshot.v1",
        "trigger_mode": trigger_mode,
        "attempt_id": str(row["attempt_id"]),
        "content_hash": str(row["content_hash"]),
        "record_hash": _sha256(attempt),
        "audit_binding": {
            "occurrence_id": str(row["occurrence_id"]),
            "event_seq": int(row["event_seq"]),
            "created_at": str(row["received_at"]),
        },
        "attempt": attempt,
    }


def _lineage_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    dataset_version_id: str,
) -> dict[str, Any]:
    version_row = connection.execute(
        """
        SELECT payload_json FROM dataset_versions
        WHERE dataset_version_id = ?
        """,
        (dataset_version_id,),
    ).fetchone()
    run_row = connection.execute(
        """
        SELECT payload_json FROM ingestion_runs
        WHERE dataset_version_id = ?
        ORDER BY started_at, ingestion_run_id
        LIMIT 1
        """,
        (dataset_version_id,),
    ).fetchone()
    if version_row is None or run_row is None:
        raise DecisionBriefUnavailable("canonical lineage is unavailable")

    try:
        dataset_version = json.loads(str(version_row["payload_json"]))
        ingestion_run = json.loads(str(run_row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionBriefUnavailable("canonical lineage payload is invalid") from error
    if not isinstance(dataset_version, Mapping) or not isinstance(ingestion_run, Mapping):
        raise DecisionBriefUnavailable("canonical lineage payload is not an object")

    records: list[dict[str, Any]] = []
    for row in connection.execute(
        """
        SELECT record_type, record_id, payload_json
        FROM lineage_records
        WHERE dataset_version_id = ?
        ORDER BY record_type, record_id
        """,
        (dataset_version_id,),
    ).fetchall():
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise DecisionBriefUnavailable("canonical lineage record is invalid") from error
        if not isinstance(payload, Mapping):
            raise DecisionBriefUnavailable("canonical lineage record is not an object")
        records.append(
            {
                "record_type": str(row["record_type"]),
                "record_id": str(row["record_id"]),
                "payload": deepcopy(dict(payload)),
            }
        )

    lineage = {
        "ingestion_run": deepcopy(dict(ingestion_run)),
        "dataset_version": deepcopy(dict(dataset_version)),
        "mapping_manifest": deepcopy(dict(dataset_version.get("mapping_manifest", {})))
        if isinstance(dataset_version.get("mapping_manifest"), Mapping)
        else {},
        "order_lines": [
            item["payload"] for item in records if item["record_type"] == "OrderLine"
        ],
        "order_line_events": [
            item["payload"]
            for item in records
            if item["record_type"] == "OrderLineEvent"
        ],
        "source_observations": [
            item["payload"]
            for item in records
            if item["record_type"] == "SourceObservation"
        ],
        "validation_findings": [
            item["payload"]
            for item in records
            if item["record_type"] == "ValidationFinding"
        ],
    }
    binding_row = connection.execute(
        """
        SELECT snapshots.snapshot_id, snapshots.occurrence_id,
               snapshots.event_seq, snapshots.content_hash, snapshots.created_at
        FROM lineage_snapshots AS snapshots
        JOIN audit_events AS audit
          ON audit.workspace_id = snapshots.workspace_id
         AND audit.occurrence_id = snapshots.occurrence_id
         AND audit.event_seq = snapshots.event_seq
         AND audit.content_hash = snapshots.content_hash
         AND audit.occurrence_kind = 'LINEAGE_SNAPSHOT_VIEW'
        WHERE snapshots.workspace_id = ? AND snapshots.dataset_version_id = ?
        """,
        (workspace_id, dataset_version_id),
    ).fetchone()
    return {
        "schema_version": "lineage-snapshot.v1",
        "dataset_version_id": dataset_version_id,
        "content_hash": _sha256(lineage),
        "audit_binding": (
            None
            if binding_row is None
            else {
                "snapshot_id": str(binding_row["snapshot_id"]),
                "occurrence_id": str(binding_row["occurrence_id"]),
                "event_seq": int(binding_row["event_seq"]),
                "content_hash": str(binding_row["content_hash"]),
                "created_at": str(binding_row["created_at"]),
            }
        ),
        "payload": lineage,
    }


def _snapshot_content(
    *,
    connection: sqlite3.Connection,
    workspace_id: str,
    request: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> dict[str, Any]:
    subject_applicability, subject_verdict, rendered_subject = _subject_applicability(
        request=request,
        reference=reference,
    )
    ingress_attempt = _ingress_attempt_projection(
        connection,
        workspace_id=workspace_id,
        request=request,
    )
    lineage = _lineage_projection(
        connection,
        workspace_id=workspace_id,
        dataset_version_id=str(request["dataset_version_id"]),
    )
    action_state = "read_only"
    action_reason = (
        "Subject applicability is insufficient; no action is authorized from this reference journey."
        if subject_applicability["state"] in {"abstained", "unavailable"}
        else "This reference journey presents evidence only; no action is authorized here."
    )
    action_next_step = subject_applicability["next_step"]
    return {
        "schema_version": DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION,
        "investigation_request_id": request["investigation_request_id"],
        "investigation_request": deepcopy(dict(request)),
        "ingress_attempt": ingress_attempt,
        "lineage": lineage,
        "reference": deepcopy(dict(reference)),
        "referenced_records": {
            "investigation_request": {
                "record_id": request["investigation_request_id"],
                "content_hash": request["content_hash"],
            },
            "ingress_attempt": {
                "record_id": ingress_attempt["attempt_id"],
                "content_hash": ingress_attempt["record_hash"],
                "event_seq": ingress_attempt["audit_binding"]["event_seq"],
            },
            "lineage": {
                "record_id": lineage["dataset_version_id"],
                "content_hash": lineage["content_hash"],
                "event_seq": (
                    None
                    if lineage["audit_binding"] is None
                    else lineage["audit_binding"]["event_seq"]
                ),
            },
            "validated_reference": {
                "record_id": reference["reference_id"],
                "content_hash": reference["reference_record_hash"],
            },
        },
        "subject_applicability": subject_applicability,
        "subject_verdict": subject_verdict,
        "rendered_subject_verdict": rendered_subject,
        "action_lane": {
            "schema_version": "reference-journey-action-lane.v1",
            "state": action_state,
            "reason": action_reason,
            "next_step": action_next_step,
        },
        "presentation": {
            "schema_version": "reference-journey-presentation.v1",
            "language_policy_id": "subject-applicability-language.v1",
            "rendered_from": "stored_subject_verdict",
            "replay_source": "immutable_decision_brief_snapshot",
        },
    }


def _snapshot_from_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionBriefUnavailable from error
    if not isinstance(payload, Mapping):
        raise DecisionBriefUnavailable
    content = deepcopy(dict(payload))
    content_hash = content.pop("content_hash", None)
    if not isinstance(content_hash, str) or _sha256(content) != content_hash:
        raise DecisionBriefUnavailable
    if content_hash != str(row["content_hash"]):
        raise DecisionBriefUnavailable
    subject_verdict = content.get("subject_verdict")
    if subject_verdict is not None:
        if not isinstance(subject_verdict, Mapping):
            raise DecisionBriefUnavailable
        if subject_verdict.get("scope") != "subject":
            raise DecisionBriefUnavailable
    if content.get("schema_version") != DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION:
        raise DecisionBriefUnavailable
    request = _mapping(content.get("investigation_request"))
    reference = _mapping(content.get("reference"))
    ingress_attempt = _mapping(content.get("ingress_attempt"))
    lineage = _mapping(content.get("lineage"))
    references = _mapping(content.get("referenced_records"))
    if any(
        value is None
        for value in (request, reference, ingress_attempt, lineage, references)
    ):
        raise DecisionBriefUnavailable

    request_hash = request.get("content_hash")
    request_without_hash = deepcopy(dict(request))
    request_without_hash.pop("content_hash", None)
    if (
        not isinstance(request_hash, str)
        or _sha256(
            {
                key: value
                for key, value in request_without_hash.items()
                if key != "accepted_at"
            }
        )
        != request_hash
    ):
        raise DecisionBriefUnavailable

    reference_hash = reference.get("reference_record_hash")
    reference_without_hash = deepcopy(dict(reference))
    reference_without_hash.pop("reference_record_hash", None)
    if (
        not isinstance(reference_hash, str)
        or _sha256(reference_without_hash) != reference_hash
    ):
        raise DecisionBriefUnavailable

    attempt = _mapping(ingress_attempt.get("attempt"))
    attempt_hash = ingress_attempt.get("record_hash")
    if (
        attempt is None
        or not isinstance(attempt_hash, str)
        or _sha256(attempt) != attempt_hash
    ):
        raise DecisionBriefUnavailable

    lineage_payload = _mapping(lineage.get("payload"))
    lineage_hash = lineage.get("content_hash")
    if (
        lineage_payload is None
        or not isinstance(lineage_hash, str)
        or _sha256(lineage_payload) != lineage_hash
    ):
        raise DecisionBriefUnavailable

    required_references = {
        "investigation_request": request_hash,
        "ingress_attempt": attempt_hash,
        "lineage": lineage_hash,
        "validated_reference": reference_hash,
    }
    for name, expected_hash in required_references.items():
        record = _mapping(references.get(name))
        if record is None or record.get("content_hash") != expected_hash:
            raise DecisionBriefUnavailable
    content["content_hash"] = content_hash
    content["snapshot_id"] = str(row["snapshot_id"])
    content["reference_id"] = str(row["reference_id"])
    content["occurrence_id"] = str(row["occurrence_id"])
    content["event_seq"] = int(row["event_seq"])
    content["created_at"] = str(row["created_at"])
    if content.get("investigation_request_id") != str(row["investigation_request_id"]):
        raise DecisionBriefUnavailable
    return content


class GovernanceMixin:
    """Immutable Decision Brief publication and semantic replay on Core SQLite."""

    def _get_investigation_request_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        investigation_request_id: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT investigation_request_id, content_hash, payload_json
            FROM investigation_requests
            WHERE workspace_id = ? AND investigation_request_id = ?
            """,
            (workspace_id, investigation_request_id),
        ).fetchone()
        return None if row is None else _request_from_row(row)

    def get_decision_brief_by_idempotency(
        self,
        workspace_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                row = connection.execute(
                    """
                    SELECT snapshots.*
                    FROM decision_brief_snapshots AS snapshots
                    JOIN audit_events AS audit
                      ON audit.workspace_id = snapshots.workspace_id
                     AND audit.occurrence_id = snapshots.occurrence_id
                     AND audit.event_seq = snapshots.event_seq
                     AND audit.content_hash = snapshots.content_hash
                     AND audit.occurrence_kind = 'DECISION_BRIEF_SNAPSHOT'
                    WHERE snapshots.workspace_id = ?
                      AND snapshots.idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        return None if row is None else _snapshot_from_row(row)

    def publish_decision_brief(
        self,
        workspace_id: str,
        *,
        investigation_request_id: str,
        idempotency_key: str,
        reference_id: str,
        reference: object,
        now: datetime | None = None,
    ) -> StoredDecisionBrief:
        current_time = now or datetime.now(timezone.utc)
        reference_projection = _reference_projection(reference)
        if reference_projection["reference_slot_id"] != reference_id:
            raise DecisionBriefUnavailable("reference identity does not match request")

        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT snapshots.*
                    FROM decision_brief_snapshots AS snapshots
                    JOIN audit_events AS audit
                      ON audit.workspace_id = snapshots.workspace_id
                     AND audit.occurrence_id = snapshots.occurrence_id
                     AND audit.event_seq = snapshots.event_seq
                     AND audit.content_hash = snapshots.content_hash
                     AND audit.occurrence_kind = 'DECISION_BRIEF_SNAPSHOT'
                    WHERE snapshots.workspace_id = ?
                      AND snapshots.idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if str(existing["reference_id"]) != reference_id:
                        connection.rollback()
                        raise AuditIdempotencyConflict
                    snapshot = _snapshot_from_row(existing)
                    connection.commit()
                    return StoredDecisionBrief("IDEMPOTENT_REPLAY", snapshot)

                request = self._get_investigation_request_locked(
                    connection,
                    workspace_id,
                    investigation_request_id,
                )
                if request is None:
                    connection.rollback()
                    raise InvestigationRequestUnavailable
                if request.get("dataset_version_id") != reference_projection["dataset_version_id"]:
                    connection.rollback()
                    raise DecisionBriefUnavailable(
                        "reference dataset does not match the Investigation Request"
                    )

                content = _snapshot_content(
                    connection=connection,
                    workspace_id=workspace_id,
                    request=request,
                    reference=reference_projection,
                )
                content_hash = _sha256(content)
                content["content_hash"] = content_hash
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="DECISION_BRIEF_SNAPSHOT",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    connection.rollback()
                    raise AuditStoreUnavailable

                occurrence_id = uuid5(
                    NAMESPACE_URL,
                    f"causal-delay-copilot:decision-brief:{workspace_id}:{idempotency_key}",
                ).hex
                created_at = _timestamp(current_time)
                cursor = connection.execute(
                    """
                    INSERT INTO audit_events (
                        workspace_id, occurrence_id, idempotency_key,
                        occurrence_kind, outcome_code, content_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        occurrence_id,
                        idempotency_key,
                        "DECISION_BRIEF_SNAPSHOT",
                        "DECISION_BRIEF_PUBLISHED",
                        content_hash,
                        created_at,
                    ),
                )
                if cursor.lastrowid is None:
                    raise sqlite3.DatabaseError("decision brief audit event was not sequenced")
                event_seq = int(cursor.lastrowid)
                snapshot_id = uuid5(
                    NAMESPACE_URL,
                    f"causal-delay-copilot:decision-brief-snapshot:{workspace_id}:{investigation_request_id}:{content_hash}",
                ).hex
                connection.execute(
                    """
                    INSERT INTO decision_brief_snapshots (
                        snapshot_id, workspace_id, investigation_request_id,
                        idempotency_key, reference_id, content_hash,
                        occurrence_id, event_seq, created_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        workspace_id,
                        investigation_request_id,
                        idempotency_key,
                        reference_id,
                        content_hash,
                        occurrence_id,
                        event_seq,
                        created_at,
                        _canonical_json(content),
                    ),
                )
                connection.commit()
                row = connection.execute(
                    """
                    SELECT snapshots.*
                    FROM decision_brief_snapshots AS snapshots
                    JOIN audit_events AS audit
                      ON audit.workspace_id = snapshots.workspace_id
                     AND audit.occurrence_id = snapshots.occurrence_id
                     AND audit.event_seq = snapshots.event_seq
                     AND audit.content_hash = snapshots.content_hash
                     AND audit.occurrence_kind = 'DECISION_BRIEF_SNAPSHOT'
                    WHERE snapshots.snapshot_id = ?
                      AND snapshots.workspace_id = ?
                    """,
                    (snapshot_id, workspace_id),
                ).fetchone()
                if row is None:
                    raise AuditStoreUnavailable
                return StoredDecisionBrief("CREATED", _snapshot_from_row(row))
            except (
                AuditIdempotencyConflict,
                AuditStoreUnavailable,
                DecisionBriefUnavailable,
                InvestigationRequestUnavailable,
            ):
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def get_decision_brief(
        self,
        workspace_id: str,
        investigation_request_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                row = connection.execute(
                    """
                    SELECT snapshots.*
                    FROM decision_brief_snapshots AS snapshots
                    JOIN audit_events AS audit
                      ON audit.workspace_id = snapshots.workspace_id
                     AND audit.occurrence_id = snapshots.occurrence_id
                     AND audit.event_seq = snapshots.event_seq
                     AND audit.content_hash = snapshots.content_hash
                     AND audit.occurrence_kind = 'DECISION_BRIEF_SNAPSHOT'
                    WHERE snapshots.workspace_id = ?
                      AND snapshots.investigation_request_id = ?
                    ORDER BY snapshots.event_seq DESC
                    LIMIT 1
                    """,
                    (workspace_id, investigation_request_id),
                ).fetchone()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        return None if row is None else _snapshot_from_row(row)

    def replay_decision_brief(
        self,
        workspace_id: str,
        investigation_request_id: str,
        event_seq: int,
    ) -> ReplayDecisionBrief:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                rows = connection.execute(
                    """
                    SELECT snapshots.*
                    FROM decision_brief_snapshots AS snapshots
                    JOIN audit_events AS audit
                      ON audit.workspace_id = snapshots.workspace_id
                     AND audit.occurrence_id = snapshots.occurrence_id
                     AND audit.event_seq = snapshots.event_seq
                     AND audit.content_hash = snapshots.content_hash
                     AND audit.occurrence_kind = 'DECISION_BRIEF_SNAPSHOT'
                    WHERE snapshots.workspace_id = ?
                      AND snapshots.investigation_request_id = ?
                      AND snapshots.event_seq <= ?
                    ORDER BY snapshots.event_seq DESC
                    """,
                    (workspace_id, investigation_request_id, event_seq),
                ).fetchall()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error

        last_verified = 0
        for row in rows:
            try:
                snapshot = _snapshot_from_row(row)
            except DecisionBriefUnavailable:
                continue
            last_verified = int(row["event_seq"])
            return ReplayDecisionBrief(
                status="REPLAYED",
                investigation_request_id=investigation_request_id,
                requested_event_seq=event_seq,
                last_verified_event_seq=last_verified,
                snapshot=snapshot,
                unresolved_references=[],
                recovery_action="NONE",
            )

        return ReplayDecisionBrief(
            status="REPLAY_UNAVAILABLE",
            investigation_request_id=investigation_request_id,
            requested_event_seq=event_seq,
            last_verified_event_seq=last_verified,
            snapshot=None,
            unresolved_references=[
                f"decision-brief:{investigation_request_id}:{event_seq}"
            ],
            recovery_action="PUBLISH_DECISION_BRIEF_OR_REQUEST_AN_EARLIER_VERIFIED_EVENT_SEQUENCE",
        )
