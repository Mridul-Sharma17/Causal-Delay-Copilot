from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping
from uuid import uuid4

from .canonical import canonical_json as _canonical_json
from .canonical import sha256 as _sha256


DECISION_SUPPORT_HEAD_SCHEMA_VERSION = "decision-support-evaluation-series-head.v1"
DECISION_SUPPORT_READ_MODEL_SCHEMA_VERSION = "decision-support-evaluation-read-model.v1"
DECISION_SUPPORT_EVALUATION_RECORD_SCHEMA_VERSION = "1"
DECISION_SUPPORT_INVALIDATION_RECORD_SCHEMA_VERSION = "1"

EVALUATION_HEAD_KINDS = frozenset(
    {
        "EVALUATION",
        "PERMISSION_INVALIDATION",
        "EVIDENCE_INTEGRITY_INVALIDATION",
        "ADVICE_CURRENTNESS_INVALIDATION",
    }
)

_INVALIDATION_OUTCOMES = {
    "PERMISSION_INVALIDATION": (
        "NOT_PERMITTED",
        "not_permitted",
        "DECISION_SUPPORT_VERDICT_PERMISSION_DOWNGRADED",
    ),
    "EVIDENCE_INTEGRITY_INVALIDATION": (
        "FAILED",
        "unavailable",
        "DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED",
    ),
    "ADVICE_CURRENTNESS_INVALIDATION": (
        "FAILED",
        "unavailable",
        "DECISION_SUPPORT_ADVICE_NOT_CURRENT",
    ),
}

_REGISTERED_INVALIDATION_REASONS = {
    "PERMISSION_INVALIDATION": frozenset(
        {
            "DECISION_SUPPORT_VERDICT_PERMISSION_DOWNGRADED",
            "DECISION_SUPPORT_EVIDENCE_UNAVAILABLE_AT_CUTOFF",
            "EVIDENCE_DOWNGRADED",
            "PERMISSION_LOST",
            "VERDICT_SUPERSEDED",
        }
    ),
    "EVIDENCE_INTEGRITY_INVALIDATION": frozenset(
        {
            "ARTIFACT_QUARANTINED",
            "ARTIFACT_CORRUPTED",
            "ARTIFACT_REVOKED",
            "ARTIFACT_SUPERSEDED",
            "RUN_ARTIFACT_INTEGRITY_FAILED",
            "RUN_ARTIFACT_INTEGRITY_MISMATCH",
            "DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED",
            "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
        }
    ),
    "ADVICE_CURRENTNESS_INVALIDATION": frozenset(
        {
            "GOVERNED_DEPENDENCY_NOT_CURRENT",
            "OPERATIONAL_FACT_EXPIRED",
            "CURRENTNESS_COMPARISON_UNRESOLVED",
        }
    ),
}


class DecisionSupportEvaluationUnavailable(RuntimeError):
    """A stored Decision Support evaluation or head failed its integrity contract."""


class DecisionSupportEvaluationConflict(RuntimeError):
    """A logical Decision Support occurrence was redelivered with conflicting content."""


class DecisionSupportHeadRaceLost(RuntimeError):
    """The named authoritative head changed before compare-and-publish."""


class DecisionSupportEvaluationSeriesUnavailable(RuntimeError):
    """The requested Decision Support evaluation series is not available."""


@dataclass(frozen=True, slots=True)
class StoredDecisionSupportEvaluation:
    result: str
    evaluation: dict[str, Any]
    result_projection: dict[str, Any]
    head: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StoredDecisionSupportInvalidation:
    result: str
    invalidation: dict[str, Any]
    record: dict[str, Any]
    head: dict[str, Any]


DECISION_SUPPORT_EVALUATION_SERIES_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_evaluation_series (
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        evaluation_series_id TEXT NOT NULL,
        series_key TEXT NOT NULL,
        identity_binding_hash TEXT NOT NULL,
        identity_binding_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (workspace_id, evaluation_series_id),
        UNIQUE (workspace_id, series_key)
    )
"""
DECISION_SUPPORT_EVALUATION_SERIES_COLUMNS = [
    "workspace_id",
    "evaluation_series_id",
    "series_key",
    "identity_binding_hash",
    "identity_binding_json",
    "created_at",
]

DECISION_SUPPORT_EVALUATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_evaluations (
        evaluation_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        predecessor_occurrence_id TEXT,
        evaluation_digest TEXT NOT NULL,
        result_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        evaluation_published_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, idempotency_key),
        FOREIGN KEY (workspace_id, evaluation_series_id)
            REFERENCES decision_support_evaluation_series(workspace_id, evaluation_series_id)
    )
"""
DECISION_SUPPORT_EVALUATIONS_COLUMNS = [
    "evaluation_occurrence_id",
    "workspace_id",
    "evaluation_series_id",
    "idempotency_key",
    "predecessor_occurrence_id",
    "evaluation_digest",
    "result_hash",
    "content_hash",
    "evaluation_published_at",
    "created_at",
    "payload_json",
]

DECISION_SUPPORT_INVALIDATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_invalidation_records (
        invalidation_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        invalidation_kind TEXT NOT NULL,
        predecessor_head_occurrence_id TEXT NOT NULL,
        predecessor_head_digest TEXT NOT NULL,
        predecessor_head_result_hash TEXT NOT NULL,
        invalidated_artifact_ref TEXT NOT NULL,
        invalidated_artifact_hash TEXT NOT NULL,
        authoritative_invalidation_ref TEXT NOT NULL,
        authoritative_invalidation_hash TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        result_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, idempotency_key),
        UNIQUE (
            workspace_id,
            evaluation_series_id,
            predecessor_head_occurrence_id,
            invalidation_kind,
            invalidated_artifact_ref,
            authoritative_invalidation_ref
        ),
        FOREIGN KEY (workspace_id, evaluation_series_id)
            REFERENCES decision_support_evaluation_series(workspace_id, evaluation_series_id)
    )
"""
DECISION_SUPPORT_INVALIDATIONS_COLUMNS = [
    "invalidation_occurrence_id",
    "workspace_id",
    "evaluation_series_id",
    "idempotency_key",
    "invalidation_kind",
    "predecessor_head_occurrence_id",
    "predecessor_head_digest",
    "predecessor_head_result_hash",
    "invalidated_artifact_ref",
    "invalidated_artifact_hash",
    "authoritative_invalidation_ref",
    "authoritative_invalidation_hash",
    "reason_code",
    "result_hash",
    "content_hash",
    "created_at",
    "payload_json",
]

DECISION_SUPPORT_HEADS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_evaluation_heads (
        workspace_id TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        head_kind TEXT NOT NULL,
        head_occurrence_id TEXT NOT NULL,
        head_digest TEXT NOT NULL,
        head_result_hash TEXT NOT NULL,
        head_record_hash TEXT NOT NULL,
        predecessor_occurrence_id TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (workspace_id, evaluation_series_id),
        FOREIGN KEY (workspace_id, evaluation_series_id)
            REFERENCES decision_support_evaluation_series(workspace_id, evaluation_series_id)
    )
"""
DECISION_SUPPORT_HEADS_COLUMNS = [
    "workspace_id",
    "evaluation_series_id",
    "head_kind",
    "head_occurrence_id",
    "head_digest",
    "head_result_hash",
    "head_record_hash",
    "predecessor_occurrence_id",
    "updated_at",
]


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
            f"{table_name} schema is not the locked Decision Support schema"
        )


def ensure_decision_support_schema(
    connection: sqlite3.Connection,
    *,
    create: bool,
) -> None:
    """Create or validate immutable evaluation records and the mutable head projection."""

    _ensure_table(
        connection,
        "decision_support_evaluation_series",
        DECISION_SUPPORT_EVALUATION_SERIES_TABLE,
        DECISION_SUPPORT_EVALUATION_SERIES_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "decision_support_evaluations",
        DECISION_SUPPORT_EVALUATIONS_TABLE,
        DECISION_SUPPORT_EVALUATIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "decision_support_invalidation_records",
        DECISION_SUPPORT_INVALIDATIONS_TABLE,
        DECISION_SUPPORT_INVALIDATIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "decision_support_evaluation_heads",
        DECISION_SUPPORT_HEADS_TABLE,
        DECISION_SUPPORT_HEADS_COLUMNS,
        create=create,
    )
    if create:
        for table_name, message in (
            (
                "decision_support_evaluation_series",
                "decision support evaluation series are immutable",
            ),
            (
                "decision_support_evaluations",
                "decision support evaluations are immutable",
            ),
            (
                "decision_support_invalidation_records",
                "decision support invalidations are immutable",
            ),
        ):
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, '{message}');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, '{message}');
                END
                """
            )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _json_mapping(value: object, *, error_message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionSupportEvaluationUnavailable(error_message) from error
    if not isinstance(parsed, Mapping):
        raise DecisionSupportEvaluationUnavailable(error_message)
    return deepcopy(dict(parsed))


def _hash_without_content_hash(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    payload.pop("content_hash", None)
    return _sha256(payload)


def _is_content_hash(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == len("sha256:") + 64
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _ref_and_hash(value: object) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    reference = value.get("reference")
    content_hash = value.get("content_hash")
    if (
        not isinstance(reference, str)
        or not reference
        or not isinstance(content_hash, str)
        or not _is_content_hash(content_hash)
    ):
        return None
    return {"reference": reference, "content_hash": content_hash}


def permission_invalidation_verdict_bindings(
    permission_provenance: object,
) -> dict[str, dict[str, str] | None] | None:
    """Return the exact superseding verdict bindings required for permission loss."""

    if not isinstance(permission_provenance, Mapping):
        return None
    bindings: dict[str, dict[str, str] | None] = {}
    for key in (
        "subject_verdict_ref_and_hash",
        "population_verdict_ref_and_hash",
    ):
        value = permission_provenance.get(key)
        if value is None:
            bindings[key] = None
            continue
        binding = _ref_and_hash(value)
        if binding is None:
            return None
        bindings[key] = binding
    if not any(bindings.values()):
        return None
    return bindings


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise DecisionSupportEvaluationUnavailable("stored Decision Support time is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DecisionSupportEvaluationUnavailable(
            "stored Decision Support time is invalid"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _replay_comparable(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    payload.pop("content_hash", None)
    for key in (
        "decision_support_evaluation_id",
        "decision_support_evaluation_series_id",
        "evaluation_occurrence_id",
        "evaluation_published_at",
    ):
        payload.pop(key, None)
    return payload


def evaluation_series_id_for(identity_binding: Mapping[str, Any]) -> str:
    """Derive a series identity from the exact upstream subject/cutoff envelope."""

    if not isinstance(identity_binding, Mapping):
        raise DecisionSupportEvaluationUnavailable("evaluation identity binding is invalid")
    supplied = identity_binding.get("evaluation_series_id")
    if isinstance(supplied, str) and supplied:
        return supplied
    series_identity = {
        "investigation_request": deepcopy(identity_binding.get("investigation_request")),
        "subject_identity": deepcopy(identity_binding.get("subject_identity")),
        "causal_decision_at": deepcopy(identity_binding.get("causal_decision_at")),
        "trigger_mode": identity_binding.get("trigger_mode"),
    }
    return f"dses:{_sha256(series_identity).split(':', 1)[1][:32]}"


def _head_read_model(row: sqlite3.Row) -> dict[str, Any]:
    head_kind = str(row["head_kind"])
    if head_kind not in EVALUATION_HEAD_KINDS:
        raise DecisionSupportEvaluationUnavailable("evaluation head kind is invalid")
    advice_state = "current" if head_kind == "EVALUATION" else "invalidated"
    return {
        "schema_version": DECISION_SUPPORT_HEAD_SCHEMA_VERSION,
        "evaluation_series_id": str(row["evaluation_series_id"]),
        "head_kind": head_kind,
        "head_occurrence_id": str(row["head_occurrence_id"]),
        "head_digest": str(row["head_digest"]),
        "head_result_hash": str(row["head_result_hash"]),
        "head_record_ref_and_hash": {
            "reference": str(row["head_occurrence_id"]),
            "content_hash": str(row["head_record_hash"]),
        },
        "predecessor_occurrence_id": (
            None
            if row["predecessor_occurrence_id"] is None
            else str(row["predecessor_occurrence_id"])
        ),
        "advice_state": advice_state,
        "current": head_kind == "EVALUATION",
        "updated_at": str(row["updated_at"]),
    }


def _result_projection(
    evaluation: Mapping[str, Any],
    *,
    evaluation_occurrence_id: str,
    evaluation_series_id: str,
    identity_binding: Mapping[str, Any],
    published_at: str,
) -> dict[str, Any]:
    from .decision_support_currentness import (
        DecisionSupportCurrentnessUnavailable,
        derive_advice_currentness_metadata,
    )

    result = deepcopy(dict(evaluation))
    result.pop("content_hash", None)
    try:
        currentness_metadata = derive_advice_currentness_metadata(
            result,
            identity_binding,
        )
        metadata_state = currentness_metadata.get("advice_currentness_metadata_state")
        if not isinstance(metadata_state, Mapping) or metadata_state.get("state") != "COMPLETE":
            raise DecisionSupportCurrentnessUnavailable(
                "Decision Support currentness metadata is incomplete"
            )
        result.update(currentness_metadata)
    except DecisionSupportCurrentnessUnavailable as error:
        raise DecisionSupportEvaluationUnavailable(
            "Decision Support currentness metadata is unavailable"
        ) from error
    result["decision_support_evaluation_id"] = evaluation_occurrence_id
    result["decision_support_evaluation_series_id"] = evaluation_series_id
    result["evaluation_published_at"] = published_at
    recommendation = _mapping(result.get("action_recommendation"))
    if recommendation is not None and recommendation.get("selected_option_code") == "ACCEPT_AND_MONITOR":
        recommendation = deepcopy(dict(recommendation))
        subject_identity = identity_binding.get("subject_identity")
        trigger_mode = identity_binding.get("trigger_mode")
        if isinstance(subject_identity, str) and subject_identity:
            recommendation["subject_identity"] = subject_identity
        if isinstance(trigger_mode, str) and trigger_mode:
            recommendation["trigger_mode"] = trigger_mode.upper()
        recommendation["monitoring_activated_at"] = published_at
        recommendation.pop("content_hash", None)
        recommendation["content_hash"] = _sha256(recommendation)
        result["action_recommendation"] = recommendation
        result["action_recommendation_ref_and_hash"] = {
            "reference": recommendation["occurrence_id"],
            "content_hash": recommendation["content_hash"],
        }
        evaluation_record = _mapping(result.get("decision_support_evaluation"))
        if evaluation_record is not None:
            evaluation_record = deepcopy(dict(evaluation_record))
            evaluation_record["action_recommendation_ref_and_hash"] = deepcopy(
                result["action_recommendation_ref_and_hash"]
            )
            evaluation_record.pop("content_hash", None)
            evaluation_record["content_hash"] = _sha256(evaluation_record)
            result["decision_support_evaluation"] = evaluation_record
    result["content_hash"] = _sha256(result)
    return result


def _audit_event_locked(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
    idempotency_key: str,
    occurrence_kind: str,
    outcome_code: str,
    content_hash: str,
    created_at: str,
) -> int:
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
            occurrence_kind,
            outcome_code,
            content_hash,
            created_at,
        ),
    )
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("Decision Support audit event was not sequenced")
    return int(cursor.lastrowid)


class DecisionSupportEvaluationMixin:
    """SQLite-backed immutable Decision Support evaluations and one exact head per series."""

    def _decision_support_connection(self) -> sqlite3.Connection:
        connection = self._connection_or_raise()  # type: ignore[attr-defined]
        ensure_decision_support_schema(connection, create=False)
        return connection

    def _head_row_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM decision_support_evaluation_heads
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        ).fetchone()

    def _capture_expected_head_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> tuple[str | None, str | None, str | None]:
        row = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if row is None:
            return None, None, None
        self._validated_head_read_model(connection, row)
        return (
            str(row["head_occurrence_id"]),
            str(row["head_digest"]),
            str(row["head_result_hash"]),
        )

    @staticmethod
    def _assert_expected_head(
        current: sqlite3.Row | None,
        expected_head_occurrence_id: str | None,
        expected_head_digest: str | None = None,
        expected_head_result_hash: str | None = None,
    ) -> None:
        current_id = None if current is None else str(current["head_occurrence_id"])
        if current_id != expected_head_occurrence_id:
            raise DecisionSupportHeadRaceLost
        if current is None:
            if expected_head_digest is not None or expected_head_result_hash is not None:
                raise DecisionSupportHeadRaceLost
            return
        if (
            expected_head_digest is not None
            and str(current["head_digest"]) != expected_head_digest
        ) or (
            expected_head_result_hash is not None
            and str(current["head_result_hash"]) != expected_head_result_hash
        ):
            raise DecisionSupportHeadRaceLost

    def _ensure_series_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        evaluation_series_id: str,
        identity_binding: Mapping[str, Any],
        created_at: str,
    ) -> sqlite3.Row:
        identity = {
            "investigation_request": deepcopy(identity_binding.get("investigation_request")),
            "subject_identity": deepcopy(identity_binding.get("subject_identity")),
            "causal_decision_at": deepcopy(identity_binding.get("causal_decision_at")),
            "trigger_mode": identity_binding.get("trigger_mode"),
        }
        identity_hash = _sha256(identity)
        series_key = _sha256(identity)
        existing = connection.execute(
            """
            SELECT * FROM decision_support_evaluation_series
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["identity_binding_hash"]) != identity_hash
                or str(existing["series_key"]) != series_key
            ):
                raise DecisionSupportEvaluationConflict
            return existing
        connection.execute(
            """
            INSERT INTO decision_support_evaluation_series (
                workspace_id, evaluation_series_id, series_key,
                identity_binding_hash, identity_binding_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                evaluation_series_id,
                series_key,
                identity_hash,
                _canonical_json(identity),
                created_at,
            ),
        )
        row = connection.execute(
            """
            SELECT * FROM decision_support_evaluation_series
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        ).fetchone()
        if row is None:
            raise DecisionSupportEvaluationUnavailable("evaluation series was not readable")
        return row

    def _evaluation_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            error_message="stored Decision Support evaluation is invalid",
        )
        if (
            record.get("schema_identifier") != "decision-support-evaluation"
            or record.get("schema_version")
            != DECISION_SUPPORT_EVALUATION_RECORD_SCHEMA_VERSION
            or record.get("evaluation_occurrence_id")
            != str(row["evaluation_occurrence_id"])
            or record.get("evaluation_series_id") != str(row["evaluation_series_id"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
        ):
            raise DecisionSupportEvaluationUnavailable
        terminal = _mapping(record.get("terminal_result"))
        if terminal is None or terminal.get("content_hash") != str(row["result_hash"]):
            raise DecisionSupportEvaluationUnavailable
        if _hash_without_content_hash(terminal) != str(row["result_hash"]):
            raise DecisionSupportEvaluationUnavailable
        return record

    def _invalidation_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            error_message="stored Decision Support invalidation is invalid",
        )
        if (
            record.get("schema_identifier") != "decision-support-invalidation"
            or record.get("schema_version")
            != DECISION_SUPPORT_INVALIDATION_RECORD_SCHEMA_VERSION
            or record.get("invalidation_occurrence_id")
            != str(row["invalidation_occurrence_id"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
        ):
            raise DecisionSupportEvaluationUnavailable
        result = _mapping(record.get("result"))
        if result is None or result.get("content_hash") != str(row["result_hash"]):
            raise DecisionSupportEvaluationUnavailable
        if _hash_without_content_hash(result) != str(row["result_hash"]):
            raise DecisionSupportEvaluationUnavailable
        return record

    def _validated_head_read_model(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        head_kind = str(row["head_kind"])
        workspace_id = str(row["workspace_id"])
        evaluation_series_id = str(row["evaluation_series_id"])
        if head_kind == "EVALUATION":
            record_row = connection.execute(
                """
                SELECT * FROM decision_support_evaluations
                WHERE workspace_id = ? AND evaluation_series_id = ?
                  AND evaluation_occurrence_id = ?
                """,
                (
                    workspace_id,
                    evaluation_series_id,
                    str(row["head_occurrence_id"]),
                ),
            ).fetchone()
            if record_row is None:
                raise DecisionSupportEvaluationUnavailable(
                    "authoritative evaluation head record is unavailable"
                )
            record = self._evaluation_from_row(record_row)
            if (
                str(row["head_digest"]) != str(record_row["evaluation_digest"])
                or str(row["head_result_hash"]) != str(record_row["result_hash"])
                or str(row["head_record_hash"]) != str(record_row["content_hash"])
                or (
                    None
                    if row["predecessor_occurrence_id"] is None
                    else str(row["predecessor_occurrence_id"])
                )
                != (
                    None
                    if record.get("predecessor_occurrence_id") is None
                    else str(record["predecessor_occurrence_id"])
                )
            ):
                raise DecisionSupportEvaluationUnavailable(
                    "authoritative evaluation head does not match its record"
                )
            return _head_read_model(row)
        if head_kind not in {
            "PERMISSION_INVALIDATION",
            "EVIDENCE_INTEGRITY_INVALIDATION",
            "ADVICE_CURRENTNESS_INVALIDATION",
        }:
            raise DecisionSupportEvaluationUnavailable("evaluation head kind is invalid")
        record_row = connection.execute(
            """
            SELECT * FROM decision_support_invalidation_records
            WHERE workspace_id = ? AND evaluation_series_id = ?
              AND invalidation_occurrence_id = ?
            """,
            (
                workspace_id,
                evaluation_series_id,
                str(row["head_occurrence_id"]),
            ),
        ).fetchone()
        if record_row is None:
            raise DecisionSupportEvaluationUnavailable(
                "authoritative invalidation head record is unavailable"
            )
        record = self._invalidation_from_row(record_row)
        invalidation_digest = record.get("invalidation_digest")
        if invalidation_digest is None:
            invalidation_result = _mapping(record.get("result"))
            invalidation_details = (
                None
                if invalidation_result is None
                else _mapping(invalidation_result.get("decision_support_invalidation"))
            )
            invalidation_digest = (
                None
                if invalidation_details is None
                else invalidation_details.get("invalidation_digest")
            )
        if (
            str(record_row["invalidation_kind"]) != head_kind
            or str(row["head_digest"]) != str(invalidation_digest)
            or str(row["head_result_hash"]) != str(record_row["result_hash"])
            or str(row["head_record_hash"]) != str(record_row["content_hash"])
            or str(row["predecessor_occurrence_id"])
            != str(record_row["predecessor_head_occurrence_id"])
        ):
            raise DecisionSupportEvaluationUnavailable(
                "authoritative invalidation head does not match its record"
            )
        return _head_read_model(row)

    def _series_read_model_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> dict[str, Any] | None:
        series_row = connection.execute(
            """
            SELECT * FROM decision_support_evaluation_series
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        ).fetchone()
        if series_row is None:
            return None
        head_row = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if head_row is None:
            raise DecisionSupportEvaluationUnavailable("evaluation series has no authoritative head")
        head = self._validated_head_read_model(connection, head_row)
        history: list[dict[str, Any]] = []
        evaluation_rows = connection.execute(
            """
            SELECT * FROM decision_support_evaluations
            WHERE workspace_id = ? AND evaluation_series_id = ?
            ORDER BY rowid
            """,
            (workspace_id, evaluation_series_id),
        ).fetchall()
        invalidation_rows = connection.execute(
            """
            SELECT * FROM decision_support_invalidation_records
            WHERE workspace_id = ? AND evaluation_series_id = ?
            ORDER BY rowid
            """,
            (workspace_id, evaluation_series_id),
        ).fetchall()
        for row in evaluation_rows:
            record = self._evaluation_from_row(row)
            occurrence_id = str(row["evaluation_occurrence_id"])
            if head["head_kind"] == "EVALUATION" and occurrence_id == head["head_occurrence_id"]:
                state = "current"
            elif any(
                str(item["predecessor_head_occurrence_id"]) == occurrence_id
                for item in invalidation_rows
            ):
                state = "invalidated"
            else:
                state = "superseded"
            history.append(
                {
                    "record_type": "evaluation",
                    "record_state": state,
                    "evaluation_occurrence_id": occurrence_id,
                    "evaluation_series_id": evaluation_series_id,
                    "evaluation_digest": str(row["evaluation_digest"]),
                    "result_hash": str(row["result_hash"]),
                    "content_hash": str(row["content_hash"]),
                    "identity_binding": deepcopy(record.get("identity_binding", {})),
                    "predecessor_occurrence_id": record.get("predecessor_occurrence_id"),
                    "evaluation_published_at": str(row["evaluation_published_at"]),
                    "terminal_result_ref_and_hash": deepcopy(
                        record.get("terminal_result_ref_and_hash")
                    ),
                    "action_recommendation": deepcopy(
                        _mapping(record.get("terminal_result", {})).get(
                            "action_recommendation"
                        )
                        if isinstance(record.get("terminal_result"), Mapping)
                        else None
                    ),
                }
            )
            terminal = _mapping(record.get("terminal_result"))
            recommendation = (
                _mapping(terminal.get("action_recommendation"))
                if terminal is not None
                else None
            )
            if recommendation is not None:
                history.append(
                    {
                        "record_type": "advice",
                        "record_state": "current" if state == "current" else "non-head",
                        "evaluation_occurrence_id": occurrence_id,
                        "recommendation_ref_and_hash": {
                            "reference": recommendation.get("occurrence_id"),
                            "content_hash": recommendation.get("content_hash"),
                        },
                        "selection_basis": recommendation.get("selection_basis"),
                    }
                )
        for row in invalidation_rows:
            record = self._invalidation_from_row(row)
            history.append(
                {
                    "record_type": "invalidation",
                    "record_state": (
                        "current"
                        if str(row["invalidation_occurrence_id"]) == head["head_occurrence_id"]
                        else "historical"
                    ),
                    "invalidation_occurrence_id": str(row["invalidation_occurrence_id"]),
                    "invalidation_kind": str(row["invalidation_kind"]),
                    "predecessor_head_occurrence_id": str(
                        row["predecessor_head_occurrence_id"]
                    ),
                    "reason_code": str(row["reason_code"]),
                    "result_hash": str(row["result_hash"]),
                    "content_hash": str(row["content_hash"]),
                    "invalidation": deepcopy(record),
                }
            )
        currentness_operations: list[dict[str, Any]] = []
        currentness_checks: list[dict[str, Any]] = []
        currentness_claims: list[dict[str, Any]] = []
        currentness_renders: list[dict[str, Any]] = []
        currentness_consuming_results: list[dict[str, Any]] = []
        tradeoff_selection_claims: list[dict[str, Any]] = []
        for operation_row in connection.execute(
            """
            SELECT * FROM decision_support_currentness_operations
            WHERE workspace_id = ? AND evaluation_series_id = ?
            ORDER BY created_at, operation_occurrence_id
            """,
            (workspace_id, evaluation_series_id),
        ).fetchall():
            operation = self._currentness_operation_from_row(operation_row)  # type: ignore[attr-defined]
            currentness_operations.append(operation)
            check_row = connection.execute(
                """
                SELECT * FROM decision_support_currentness_checks
                WHERE workspace_id = ? AND currentness_operation_key = ?
                """,
                (workspace_id, operation_row["currentness_operation_key"]),
            ).fetchone()
            if check_row is not None:
                currentness_checks.append(
                    self._currentness_check_from_row(check_row)  # type: ignore[attr-defined]
                )
            claim_row = connection.execute(
                """
                SELECT * FROM decision_support_currentness_terminal_claims
                WHERE workspace_id = ? AND currentness_operation_key = ?
                """,
                (workspace_id, operation_row["currentness_operation_key"]),
            ).fetchone()
            if claim_row is not None:
                claim = self._currentness_claim_from_row(claim_row)  # type: ignore[attr-defined]
                currentness_claims.append(claim)
                render, consuming_result = self._consuming_projection_from_claim_locked(  # type: ignore[attr-defined]
                    connection,
                    workspace_id=workspace_id,
                    claim=claim,
                )
                if render is not None:
                    currentness_renders.append(render)
                if consuming_result is not None:
                    currentness_consuming_results.append(consuming_result)
        for claim_row in connection.execute(
            """
            SELECT * FROM decision_support_tradeoff_selection_claims
            WHERE workspace_id = ? AND evaluation_series_id = ?
            ORDER BY created_at, selection_claim_occurrence_id
            """,
            (workspace_id, evaluation_series_id),
        ).fetchall():
            claim = self._tradeoff_selection_claim_from_row_locked(  # type: ignore[attr-defined]
                connection,
                workspace_id=workspace_id,
                evaluation_series_id=str(claim_row["evaluation_series_id"]),
                evaluation_occurrence_id=str(claim_row["evaluation_occurrence_id"]),
            )
            if claim is None:
                raise DecisionSupportEvaluationUnavailable(
                    "trade-off selection claim is unavailable"
                )
            tradeoff_selection_claims.append(claim)
            recommendation = _mapping(claim.get("action_recommendation"))
            if recommendation is not None:
                history.append(
                    {
                        "record_type": "advice",
                        "record_state": (
                            "current"
                            if head["head_kind"] == "EVALUATION"
                            and head["head_occurrence_id"] == claim["evaluation_occurrence_id"]
                            else "non-head"
                        ),
                        "evaluation_occurrence_id": claim["evaluation_occurrence_id"],
                        "recommendation_ref_and_hash": {
                            "reference": recommendation.get("occurrence_id"),
                            "content_hash": recommendation.get("content_hash"),
                        },
                        "selection_basis": recommendation.get("selection_basis"),
                        "selection_is_not_authorization": True,
                    }
                )
        return {
            "schema_version": DECISION_SUPPORT_READ_MODEL_SCHEMA_VERSION,
            "evaluation_series_id": evaluation_series_id,
            "identity_binding": _json_mapping(
                series_row["identity_binding_json"],
                error_message="evaluation series identity binding is invalid",
            ),
            "head": head,
            "history": history,
            "currentness": {
                "schema_version": "decision-support-currentness-read-model.v2",
                "operations": currentness_operations,
                "checks": currentness_checks,
                "terminal_claims": currentness_claims,
                "render_results": currentness_renders,
                "consuming_results": currentness_consuming_results,
                "tradeoff_selection_claims": tradeoff_selection_claims,
            },
        }

    def _publish_decision_support_evaluation_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        *,
        idempotency_key: str,
        evaluation: Mapping[str, Any],
        identity_binding: Mapping[str, Any],
        expected_head_occurrence_id: str | None,
        expected_head_digest: str | None,
        expected_head_result_hash: str | None,
        now: datetime,
        evaluation_occurrence_id: str | None = None,
    ) -> StoredDecisionSupportEvaluation:
        supplied_series_id = identity_binding.get("evaluation_series_id")
        evaluation_series_value = evaluation.get("decision_support_evaluation_series_id")
        if (
            isinstance(supplied_series_id, str)
            and supplied_series_id
            and isinstance(evaluation_series_value, str)
            and evaluation_series_value
            and supplied_series_id != evaluation_series_value
        ):
            raise DecisionSupportEvaluationConflict
        evaluation_series_id = evaluation_series_id_for(
            {
                **deepcopy(dict(identity_binding)),
                "evaluation_series_id": evaluation_series_value,
            }
        )
        evaluation_digest = str(
            evaluation.get("decision_support_input_digest")
            or _sha256(identity_binding)
        )
        existing = connection.execute(
            """
            SELECT * FROM decision_support_evaluations
            WHERE workspace_id = ? AND idempotency_key = ?
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            record = self._evaluation_from_row(existing)
            terminal = _mapping(record.get("terminal_result"))
            if terminal is None:
                raise DecisionSupportEvaluationUnavailable
            from .decision_support_currentness import (
                DecisionSupportCurrentnessUnavailable,
                derive_advice_currentness_metadata,
            )

            comparable_evaluation = deepcopy(dict(evaluation))
            try:
                comparable_evaluation.update(
                    derive_advice_currentness_metadata(
                        comparable_evaluation,
                        identity_binding,
                    )
                )
            except DecisionSupportCurrentnessUnavailable as error:
                raise DecisionSupportEvaluationUnavailable(
                    "Decision Support currentness metadata is unavailable"
                ) from error
            if (
                str(existing["evaluation_series_id"]) != evaluation_series_id
                or record.get("identity_binding") != deepcopy(dict(identity_binding))
                or str(existing["evaluation_digest"]) != evaluation_digest
                or (
                    evaluation_occurrence_id is not None
                    and str(existing["evaluation_occurrence_id"])
                    != evaluation_occurrence_id
                )
                or _replay_comparable(terminal)
                != _replay_comparable(comparable_evaluation)
            ):
                raise DecisionSupportEvaluationConflict
            head = self._head_row_locked(
                connection,
                workspace_id,
                str(existing["evaluation_series_id"]),
            )
            if head is None:
                raise DecisionSupportEvaluationUnavailable
            return StoredDecisionSupportEvaluation(
                result="IDEMPOTENT_REPLAY",
                evaluation=record,
                result_projection=deepcopy(dict(terminal)),
                head=self._validated_head_read_model(connection, head),
            )

        created_at = _timestamp(now)
        self._ensure_series_locked(
            connection,
            workspace_id=workspace_id,
            evaluation_series_id=evaluation_series_id,
            identity_binding=identity_binding,
            created_at=created_at,
        )
        current = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if current is not None:
            self._validated_head_read_model(connection, current)
        self._assert_expected_head(
            current,
            expected_head_occurrence_id,
            expected_head_digest,
            expected_head_result_hash,
        )
        occurrence_id = evaluation_occurrence_id or uuid4().hex
        if not isinstance(occurrence_id, str) or not occurrence_id:
            raise DecisionSupportEvaluationUnavailable("evaluation occurrence identity is invalid")
        published_at = created_at
        if current is not None and _parse_timestamp(published_at) < _parse_timestamp(
            current["updated_at"]
        ):
            raise DecisionSupportEvaluationUnavailable(
                "Decision Support successor publication is earlier than its predecessor"
            )
        terminal = _result_projection(
            evaluation,
            evaluation_occurrence_id=occurrence_id,
            evaluation_series_id=evaluation_series_id,
            identity_binding=identity_binding,
            published_at=published_at,
        )
        result_hash = str(terminal["content_hash"])
        predecessor = None if current is None else str(current["head_occurrence_id"])
        record: dict[str, Any] = {
            "schema_identifier": "decision-support-evaluation",
            "schema_version": DECISION_SUPPORT_EVALUATION_RECORD_SCHEMA_VERSION,
            "evaluation_occurrence_id": occurrence_id,
            "evaluation_series_id": evaluation_series_id,
            "predecessor_occurrence_id": predecessor,
            "evaluation_digest": evaluation_digest,
            "evaluation_published_at": published_at,
            "terminal_result_ref_and_hash": {
                "reference": f"decision-support-result:{occurrence_id}",
                "content_hash": result_hash,
            },
            "identity_binding": deepcopy(dict(identity_binding)),
            "terminal_result": terminal,
        }
        record["content_hash"] = _sha256(record)
        content_hash = str(record["content_hash"])
        _audit_event_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            idempotency_key=f"decision-support-evaluation:{idempotency_key}",
            occurrence_kind="DECISION_SUPPORT_EVALUATION",
            outcome_code=str(terminal.get("outcome", "FAILED")),
            content_hash=content_hash,
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO decision_support_evaluations (
                evaluation_occurrence_id, workspace_id, evaluation_series_id,
                idempotency_key, predecessor_occurrence_id, evaluation_digest,
                result_hash, content_hash, evaluation_published_at, created_at,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                workspace_id,
                evaluation_series_id,
                idempotency_key,
                predecessor,
                record["evaluation_digest"],
                result_hash,
                content_hash,
                published_at,
                created_at,
                _canonical_json(record),
            ),
        )
        if current is None:
            try:
                connection.execute(
                    """
                    INSERT INTO decision_support_evaluation_heads (
                        workspace_id, evaluation_series_id, head_kind,
                        head_occurrence_id, head_digest, head_result_hash,
                        head_record_hash, predecessor_occurrence_id, updated_at
                    ) VALUES (?, ?, 'EVALUATION', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        evaluation_series_id,
                        occurrence_id,
                        record["evaluation_digest"],
                        result_hash,
                        content_hash,
                        predecessor,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise DecisionSupportHeadRaceLost from error
        else:
            cursor = connection.execute(
                """
                UPDATE decision_support_evaluation_heads
                SET head_kind = 'EVALUATION',
                    head_occurrence_id = ?,
                    head_digest = ?,
                    head_result_hash = ?,
                    head_record_hash = ?,
                    predecessor_occurrence_id = ?,
                    updated_at = ?
                WHERE workspace_id = ? AND evaluation_series_id = ?
                  AND head_occurrence_id = ?
                  AND head_digest = ?
                  AND head_result_hash = ?
                """,
                (
                    occurrence_id,
                    record["evaluation_digest"],
                    result_hash,
                    content_hash,
                    predecessor,
                    created_at,
                    workspace_id,
                    evaluation_series_id,
                    str(current["head_occurrence_id"]),
                    str(current["head_digest"]),
                    str(current["head_result_hash"]),
                ),
            )
            if cursor.rowcount != 1:
                raise DecisionSupportHeadRaceLost
        self._replace_currentness_authority_locked(  # type: ignore[attr-defined]
            connection,
            workspace_id=workspace_id,
            evaluation_series_id=evaluation_series_id,
            dependencies=terminal.get("advice_currentness_dependency_set", []),
            updated_at=created_at,
        )
        head = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if head is None:
            raise DecisionSupportEvaluationUnavailable("evaluation head was not readable")
        return StoredDecisionSupportEvaluation(
            result="CREATED",
            evaluation=record,
            result_projection=terminal,
            head=self._validated_head_read_model(connection, head),
        )

    def publish_decision_support_evaluation(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        evaluation: Mapping[str, Any],
        identity_binding: Mapping[str, Any],
        expected_head_occurrence_id: str | None = None,
        expected_head_digest: str | None = None,
        expected_head_result_hash: str | None = None,
        now: datetime | None = None,
        evaluation_occurrence_id: str | None = None,
    ) -> StoredDecisionSupportEvaluation:
        """Publish one immutable evaluation and compare-and-publish its series head."""

        if not isinstance(evaluation, Mapping) or not isinstance(identity_binding, Mapping):
            raise DecisionSupportEvaluationUnavailable("evaluation publication envelope is invalid")
        current_time = now or datetime.now(timezone.utc)
        with self._lock:  # type: ignore[attr-defined]
            connection = self._decision_support_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                series_id = evaluation_series_id_for(
                    {
                        **deepcopy(dict(identity_binding)),
                        "evaluation_series_id": evaluation.get(
                            "decision_support_evaluation_series_id"
                        ),
                    }
                )
                expected = expected_head_occurrence_id
                expected_digest = expected_head_digest
                expected_result_hash = expected_head_result_hash
                if (
                    expected_head_occurrence_id is None
                    and expected_head_digest is None
                    and expected_head_result_hash is None
                ):
                    (
                        expected,
                        expected_digest,
                        expected_result_hash,
                    ) = self._capture_expected_head_locked(
                        connection,
                        workspace_id,
                        series_id,
                    )
                elif expected_head_occurrence_id is None:
                    raise DecisionSupportEvaluationUnavailable(
                        "head digest requires an expected head occurrence"
                    )
                elif expected_head_digest is None or expected_head_result_hash is None:
                    raise DecisionSupportEvaluationUnavailable(
                        "exact head publication requires occurrence, digest, and result hash"
                    )
                stored = self._publish_decision_support_evaluation_locked(
                    connection,
                    workspace_id,
                    idempotency_key=idempotency_key,
                    evaluation=evaluation,
                    identity_binding=identity_binding,
                    expected_head_occurrence_id=expected,
                    expected_head_digest=expected_digest,
                    expected_head_result_hash=expected_result_hash,
                    now=current_time,
                    evaluation_occurrence_id=evaluation_occurrence_id,
                )
                connection.commit()
                return stored
            except (
                DecisionSupportEvaluationConflict,
                DecisionSupportEvaluationUnavailable,
                DecisionSupportHeadRaceLost,
            ):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise DecisionSupportEvaluationConflict from error
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportEvaluationUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def _invalidate_decision_support_evaluation_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        *,
        idempotency_key: str,
        evaluation_series_id: str,
        expected_head_occurrence_id: str,
        expected_head_digest: str,
        expected_head_result_hash: str,
        invalidation_kind: str,
        invalidated_artifact_ref_and_hash: Mapping[str, Any],
        authoritative_invalidation_ref_and_hash: Mapping[str, Any],
        reason_code: str,
        permission_provenance: Mapping[str, Any] | None = None,
        now: datetime,
    ) -> StoredDecisionSupportInvalidation:
        if invalidation_kind not in _INVALIDATION_OUTCOMES:
            raise DecisionSupportEvaluationUnavailable("invalidation kind is unsupported")
        if not isinstance(reason_code, str) or reason_code not in _REGISTERED_INVALIDATION_REASONS[
            invalidation_kind
        ]:
            raise DecisionSupportEvaluationUnavailable("invalidation reason is unregistered")
        if not isinstance(invalidated_artifact_ref_and_hash, Mapping) or not isinstance(
            authoritative_invalidation_ref_and_hash, Mapping
        ):
            raise DecisionSupportEvaluationUnavailable("invalidation references are invalid")
        invalidated_ref = invalidated_artifact_ref_and_hash.get("reference")
        invalidated_hash = invalidated_artifact_ref_and_hash.get("content_hash")
        authoritative_ref = authoritative_invalidation_ref_and_hash.get("reference")
        authoritative_hash = authoritative_invalidation_ref_and_hash.get("content_hash")
        if not all(
            isinstance(value, str) and value
            for value in (
                invalidated_ref,
                invalidated_hash,
                authoritative_ref,
                authoritative_hash,
                reason_code,
            )
        ) or _ref_and_hash(invalidated_artifact_ref_and_hash) is None or _ref_and_hash(
            authoritative_invalidation_ref_and_hash
        ) is None:
            raise DecisionSupportEvaluationUnavailable("invalidation references are incomplete")
        superseding_verdicts = None
        if invalidation_kind == "PERMISSION_INVALIDATION":
            superseding_verdicts = permission_invalidation_verdict_bindings(
                permission_provenance
            )
            if superseding_verdicts is None:
                raise DecisionSupportEvaluationUnavailable(
                    "permission invalidation requires exact superseding verdict bindings"
                )
        existing = connection.execute(
            """
            SELECT * FROM decision_support_invalidation_records
            WHERE workspace_id = ? AND idempotency_key = ?
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            existing_record = self._invalidation_from_row(existing)
            if (
                str(existing["evaluation_series_id"]) != evaluation_series_id
                or str(existing["invalidation_kind"]) != invalidation_kind
                or str(existing["predecessor_head_occurrence_id"])
                != expected_head_occurrence_id
                or str(existing["predecessor_head_digest"]) != expected_head_digest
                or str(existing["predecessor_head_result_hash"])
                != expected_head_result_hash
                or str(existing["invalidated_artifact_ref"]) != invalidated_ref
                or str(existing["invalidated_artifact_hash"]) != invalidated_hash
                or str(existing["authoritative_invalidation_ref"]) != authoritative_ref
                or str(existing["authoritative_invalidation_hash"]) != authoritative_hash
                or str(existing["reason_code"]) != reason_code
                or existing_record.get("superseding_verdict_ref_and_hash")
                != superseding_verdicts
            ):
                raise DecisionSupportEvaluationConflict
            record = existing_record
            head = self._head_row_locked(connection, workspace_id, evaluation_series_id)
            if head is None:
                raise DecisionSupportEvaluationUnavailable
            return StoredDecisionSupportInvalidation(
                result="IDEMPOTENT_REPLAY",
                invalidation=deepcopy(dict(record["result"])),
                record=record,
                head=self._validated_head_read_model(connection, head),
            )
        head = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if head is None:
            raise DecisionSupportEvaluationSeriesUnavailable
        self._validated_head_read_model(connection, head)
        if (
            str(head["head_occurrence_id"]) != expected_head_occurrence_id
            or str(head["head_digest"]) != expected_head_digest
            or str(head["head_result_hash"]) != expected_head_result_hash
        ):
            raise DecisionSupportHeadRaceLost
        outcome, state, primary_reason = _INVALIDATION_OUTCOMES[invalidation_kind]
        created_at = _timestamp(now)
        if _parse_timestamp(created_at) < _parse_timestamp(head["updated_at"]):
            raise DecisionSupportEvaluationUnavailable(
                "Decision Support invalidation is earlier than its predecessor head"
            )
        invalidation_occurrence_id = uuid4().hex
        invalidation_digest = _sha256(
            {
                "evaluation_series_id": evaluation_series_id,
                "predecessor_head_occurrence_id": expected_head_occurrence_id,
                "predecessor_head_digest": expected_head_digest,
                "predecessor_head_result_hash": expected_head_result_hash,
                "invalidated_artifact_ref_and_hash": deepcopy(
                    dict(invalidated_artifact_ref_and_hash)
                ),
                "authoritative_invalidation_ref_and_hash": deepcopy(
                    dict(authoritative_invalidation_ref_and_hash)
                ),
                "registered_invalidation_reason": reason_code,
                "superseding_verdict_ref_and_hash": deepcopy(superseding_verdicts),
            }
        )
        result: dict[str, Any] = {
            "schema_version": "decision-support-boundary.v1",
            "outcome": outcome,
            "state": state,
            "primary_reason_code": primary_reason,
            "reason": (
                "The authoritative Decision Support evidence chain no longer permits the "
                "predecessor advice to remain current."
            ),
            "next_step": "Publish a fresh permission-true evaluation after restoring the exact governed evidence.",
            "permission": {
                "decision_support_evaluation_permitted": outcome != "NOT_PERMITTED",
                "denial_reason_code": primary_reason if outcome == "NOT_PERMITTED" else None,
                "reason": "The predecessor evaluation is no longer permitted for current advice.",
                "next_step": "Restore the exact governed evidence and request a fresh evaluation.",
            },
            "decision_support_evaluation_id": None,
            "decision_support_evaluation_series_id": evaluation_series_id,
            "permission_provenance": (
                deepcopy(superseding_verdicts)
                if superseding_verdicts is not None
                else None
            ),
            "decision_support_invalidation": {
                "schema_identifier": "decision-support-invalidation",
                "schema_version": DECISION_SUPPORT_INVALIDATION_RECORD_SCHEMA_VERSION,
                "invalidation_kind": invalidation_kind,
                "invalidation_digest": invalidation_digest,
                "predecessor_head_occurrence_id": expected_head_occurrence_id,
                "predecessor_head_digest": expected_head_digest,
                "predecessor_head_result_hash": expected_head_result_hash,
                "invalidated_artifact_ref_and_hash": deepcopy(
                    dict(invalidated_artifact_ref_and_hash)
                ),
                "authoritative_invalidation_ref_and_hash": deepcopy(
                    dict(authoritative_invalidation_ref_and_hash)
                ),
                "registered_invalidation_reason": reason_code,
                "superseding_verdict_ref_and_hash": deepcopy(superseding_verdicts),
                "invalidation_occurrence_id": invalidation_occurrence_id,
                "created_at": created_at,
            },
            "options": [],
            "evidence_tags": {
                "DRIVER_EVIDENCE": "NOT_EVALUATED",
                "MECHANISTIC_LINK": "NOT_EVALUATED",
                "RULE_BASED_ELIGIBILITY": "NOT_EVALUATED",
                "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
            },
            "suppression_reasons": [
                {
                    "code": primary_reason,
                    "category": "INVALIDATION",
                    "priority": 100,
                    "reason": "The predecessor advice is locked as unavailable for current use.",
                }
            ],
            "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "action_recommendation": None,
            "tradeoff": None,
            "monitoring": {"state": "NOT_AVAILABLE"},
            "drafting": {"state": "NOT_PERMITTED"},
            "authorization": {"state": "NOT_PERMITTED"},
            "consumed_inputs": [],
        }
        result["content_hash"] = _sha256(result)
        result_hash = str(result["content_hash"])
        record: dict[str, Any] = {
            "schema_identifier": "decision-support-invalidation",
            "schema_version": DECISION_SUPPORT_INVALIDATION_RECORD_SCHEMA_VERSION,
            "invalidation_occurrence_id": invalidation_occurrence_id,
            "evaluation_series_id": evaluation_series_id,
            "invalidation_kind": invalidation_kind,
            "predecessor_head_occurrence_id": expected_head_occurrence_id,
            "predecessor_head_digest": expected_head_digest,
            "predecessor_head_result_hash": expected_head_result_hash,
            "invalidated_artifact_ref_and_hash": deepcopy(
                dict(invalidated_artifact_ref_and_hash)
            ),
            "authoritative_invalidation_ref_and_hash": deepcopy(
                dict(authoritative_invalidation_ref_and_hash)
            ),
            "registered_invalidation_reason": reason_code,
            "superseding_verdict_ref_and_hash": deepcopy(superseding_verdicts),
            "invalidation_digest": invalidation_digest,
            "created_at": created_at,
            "result": result,
        }
        record["content_hash"] = _sha256(record)
        content_hash = str(record["content_hash"])
        _audit_event_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=invalidation_occurrence_id,
            idempotency_key=f"decision-support-invalidation:{idempotency_key}",
            occurrence_kind="DECISION_SUPPORT_INVALIDATION",
            outcome_code=invalidation_kind,
            content_hash=content_hash,
            created_at=created_at,
        )
        try:
            connection.execute(
                """
                INSERT INTO decision_support_invalidation_records (
                    invalidation_occurrence_id, workspace_id, evaluation_series_id,
                    idempotency_key, invalidation_kind,
                    predecessor_head_occurrence_id, predecessor_head_digest,
                    predecessor_head_result_hash, invalidated_artifact_ref,
                    invalidated_artifact_hash, authoritative_invalidation_ref,
                    authoritative_invalidation_hash, reason_code, result_hash,
                    content_hash, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invalidation_occurrence_id,
                    workspace_id,
                    evaluation_series_id,
                    idempotency_key,
                    invalidation_kind,
                    expected_head_occurrence_id,
                    expected_head_digest,
                    expected_head_result_hash,
                    invalidated_ref,
                    invalidated_hash,
                    authoritative_ref,
                    authoritative_hash,
                    reason_code,
                    result_hash,
                    content_hash,
                    created_at,
                    _canonical_json(record),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise DecisionSupportEvaluationConflict from error
        cursor = connection.execute(
            """
            UPDATE decision_support_evaluation_heads
            SET head_kind = ?,
                head_occurrence_id = ?,
                head_digest = ?,
                head_result_hash = ?,
                head_record_hash = ?,
                predecessor_occurrence_id = ?,
                updated_at = ?
            WHERE workspace_id = ? AND evaluation_series_id = ?
              AND head_kind = ?
              AND head_occurrence_id = ?
              AND head_digest = ?
              AND head_result_hash = ?
            """,
            (
                invalidation_kind,
                invalidation_occurrence_id,
                invalidation_digest,
                result_hash,
                content_hash,
                expected_head_occurrence_id,
                created_at,
                workspace_id,
                evaluation_series_id,
                str(head["head_kind"]),
                expected_head_occurrence_id,
                expected_head_digest,
                expected_head_result_hash,
            ),
        )
        if cursor.rowcount != 1:
            raise DecisionSupportHeadRaceLost
        updated = self._head_row_locked(connection, workspace_id, evaluation_series_id)
        if updated is None:
            raise DecisionSupportEvaluationUnavailable("invalidation head was not readable")
        return StoredDecisionSupportInvalidation(
            result="CREATED",
            invalidation=result,
            record=record,
            head=self._validated_head_read_model(connection, updated),
        )

    def invalidate_decision_support_evaluation(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        evaluation_series_id: str,
        expected_head_occurrence_id: str,
        expected_head_digest: str,
        expected_head_result_hash: str,
        invalidation_kind: str,
        invalidated_artifact_ref_and_hash: Mapping[str, Any],
        authoritative_invalidation_ref_and_hash: Mapping[str, Any],
        reason_code: str,
        permission_provenance: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> StoredDecisionSupportInvalidation:
        """Publish one locked invalidation only if the exact named head is still current."""

        current_time = now or datetime.now(timezone.utc)
        with self._lock:  # type: ignore[attr-defined]
            connection = self._decision_support_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                stored = self._invalidate_decision_support_evaluation_locked(
                    connection,
                    workspace_id,
                    idempotency_key=idempotency_key,
                    evaluation_series_id=evaluation_series_id,
                    expected_head_occurrence_id=expected_head_occurrence_id,
                    expected_head_digest=expected_head_digest,
                    expected_head_result_hash=expected_head_result_hash,
                    invalidation_kind=invalidation_kind,
                    invalidated_artifact_ref_and_hash=invalidated_artifact_ref_and_hash,
                    authoritative_invalidation_ref_and_hash=authoritative_invalidation_ref_and_hash,
                    reason_code=reason_code,
                    permission_provenance=permission_provenance,
                    now=current_time,
                )
                connection.commit()
                return stored
            except (
                DecisionSupportEvaluationConflict,
                DecisionSupportEvaluationSeriesUnavailable,
                DecisionSupportEvaluationUnavailable,
                DecisionSupportHeadRaceLost,
            ):
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportEvaluationUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def get_decision_support_evaluation_head(
        self,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:  # type: ignore[attr-defined]
            connection = self._decision_support_connection()
            try:
                connection.execute("BEGIN")
                row = self._head_row_locked(connection, workspace_id, evaluation_series_id)
                result = None if row is None else self._validated_head_read_model(connection, row)
                connection.commit()
                return result
            except DecisionSupportEvaluationUnavailable:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportEvaluationUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def get_decision_support_evaluation_series(
        self,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:  # type: ignore[attr-defined]
            connection = self._decision_support_connection()
            try:
                connection.execute("BEGIN")
                result = self._series_read_model_locked(
                    connection,
                    workspace_id=workspace_id,
                    evaluation_series_id=evaluation_series_id,
                )
                connection.commit()
                return result
            except DecisionSupportEvaluationUnavailable:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportEvaluationUnavailable from error
            except Exception:
                connection.rollback()
                raise
