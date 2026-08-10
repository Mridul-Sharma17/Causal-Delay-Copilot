from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from .canonical import canonical_json as _canonical_json
from .canonical import sha256 as _sha256
from .canonical import timestamp as _timestamp
from .decision_support_currentness import (
    CURRENTNESS_POLICY_IDENTIFIER_AND_VERSION,
    DecisionSupportCurrentnessConflict,
    DecisionSupportCurrentnessOperationMismatch,
    DecisionSupportCurrentnessUnavailable,
    _audit_locked,
    _hash_without_content_hash,
    _key_fields,
    _mapping,
    _operation_record_for,
    _ref_and_hash,
    _same_ref,
    currentness_operation_key_for,
)
from .draft_context import DraftContextUnavailable
from .drafts import DraftHeadRace, DraftStoreUnavailable
from .errors import WorkspaceRequestError


MANAGER_DECISION_SCHEMA_VERSION = "manager-decision.v1"
MANAGER_DECISION_SCHEMA_IDENTIFIER = "manager-decision"
DECISION_BRIEF_SNAPSHOT_SCHEMA_IDENTIFIER = "decision-brief-snapshot"
DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION = "1"
MANAGER_DECISION_AUDIT_KIND = "GOVERNANCE_MANAGER_DECISION"
MANAGER_DECISION_AUDIT_OUTCOME = "MANAGER_DECISION_RECORDED"
MANAGER_DECISION_SNAPSHOT_AUDIT_KIND = "MANAGER_DECISION_BRIEF_SNAPSHOT"
MANAGER_DECISION_SNAPSHOT_AUDIT_OUTCOME = "DECISION_BRIEF_PUBLISHED"

MANAGER_DECISIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS governance_manager_decisions (
        manager_decision_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        decision_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        snapshot_id TEXT NOT NULL,
        snapshot_hash TEXT NOT NULL,
        occurrence_id TEXT NOT NULL UNIQUE,
        event_seq INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, idempotency_key),
        UNIQUE (workspace_id, decision_key)
    )
"""
MANAGER_DECISIONS_COLUMNS = [
    "manager_decision_id",
    "workspace_id",
    "idempotency_key",
    "request_hash",
    "decision_key",
    "content_hash",
    "snapshot_id",
    "snapshot_hash",
    "occurrence_id",
    "event_seq",
    "created_at",
    "payload_json",
]

MANAGER_DECISION_SNAPSHOTS_TABLE = """
    CREATE TABLE IF NOT EXISTS governance_manager_decision_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        decision_key TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        occurrence_id TEXT NOT NULL UNIQUE,
        event_seq INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, decision_key)
    )
"""
MANAGER_DECISION_SNAPSHOTS_COLUMNS = [
    "snapshot_id",
    "workspace_id",
    "decision_key",
    "reference_id",
    "content_hash",
    "occurrence_id",
    "event_seq",
    "created_at",
    "payload_json",
]


class ManagerDecisionUnavailable(Exception):
    """The exact manager decision chain cannot be safely authorized or read."""


class ManagerDecisionConflict(Exception):
    """One manager decision identity was reused with different content."""


class ManagerDecisionHeadRace(Exception):
    """A manager decision targeted an obsolete immutable draft head."""


@dataclass(frozen=True, slots=True)
class StoredManagerDecision:
    result: str
    decision: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    draft: dict[str, Any]
    authorization_attempt: dict[str, Any] | None
    authorization_currentness: dict[str, Any] | None
    operation: dict[str, Any] | None
    currentness: dict[str, Any] | None
    terminal_claim: dict[str, Any] | None


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
            f"{table_name} schema is not the locked Core schema"
        )


def ensure_manager_decision_schema(
    connection: sqlite3.Connection,
    *,
    create: bool,
) -> None:
    _ensure_table(
        connection,
        "governance_manager_decisions",
        MANAGER_DECISIONS_TABLE,
        MANAGER_DECISIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "governance_manager_decision_snapshots",
        MANAGER_DECISION_SNAPSHOTS_TABLE,
        MANAGER_DECISION_SNAPSHOTS_COLUMNS,
        create=create,
    )
    if create:
        for table, message in (
            (
                "governance_manager_decisions",
                "manager decisions are immutable",
            ),
            (
                "governance_manager_decision_snapshots",
                "manager decision snapshots are immutable",
            ),
        ):
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
                BEFORE UPDATE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, '{message}');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
                BEFORE DELETE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, '{message}');
                END
                """
            )


def _json_mapping(value: object, message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ManagerDecisionUnavailable(message) from error
    if not isinstance(parsed, Mapping):
        raise ManagerDecisionUnavailable(message)
    return deepcopy(dict(parsed))


def _required_ref(value: object, label: str) -> dict[str, str]:
    reference = _ref_and_hash(value)
    if reference is None:
        raise ManagerDecisionUnavailable(f"{label} is unavailable")
    return reference


def _optional_ref(value: object, label: str) -> dict[str, str] | None:
    if value is None:
        return None
    return _required_ref(value, label)


def _audit_event_seq(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
) -> int:
    row = connection.execute(
        """
        SELECT event_seq
        FROM audit_events
        WHERE workspace_id = ? AND occurrence_id = ?
        """,
        (workspace_id, occurrence_id),
    ).fetchone()
    if row is None:
        raise ManagerDecisionUnavailable("manager decision audit binding is missing")
    return int(row["event_seq"])


def _next_audit_event_seq(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'audit_events'"
    ).fetchone()
    return 1 if row is None else int(row["seq"]) + 1


def _validate_audit_binding(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
    event_seq: int,
    content_hash: str,
    occurrence_kind: str,
    outcome_code: str,
) -> None:
    row = connection.execute(
        """
        SELECT occurrence_kind, outcome_code, content_hash, event_seq
        FROM audit_events
        WHERE workspace_id = ? AND occurrence_id = ?
        """,
        (workspace_id, occurrence_id),
    ).fetchone()
    if (
        row is None
        or int(row["event_seq"]) != event_seq
        or str(row["occurrence_kind"]) != occurrence_kind
        or str(row["outcome_code"]) != outcome_code
        or str(row["content_hash"]) != content_hash
    ):
        raise ManagerDecisionUnavailable("manager decision audit binding failed integrity")


def _draft_ref(draft: Mapping[str, Any]) -> dict[str, str]:
    return {
        "reference": str(draft["occurrence_id"]),
        "content_hash": str(draft["content_hash"]),
    }


def _occurrence_from_reference(reference: str, prefix: str) -> str:
    if reference.startswith(f"{prefix}:"):
        return reference.split(":", 1)[1]
    return reference


class ManagerDecisionMixin:
    """Atomic Governance persistence for authorization and terminal decisions."""

    def _manager_decision_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        payload = _json_mapping(
            row["payload_json"],
            "stored manager decision is invalid",
        )
        if (
            payload.get("schema_identifier") != MANAGER_DECISION_SCHEMA_IDENTIFIER
            or payload.get("schema_version") != "1"
            or payload.get("occurrence_id") != str(row["occurrence_id"])
            or payload.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(payload) != str(row["content_hash"])
            or payload.get("decision_key") != str(row["decision_key"])
            or payload.get("decision_brief_snapshot_ref_and_hash")
            != {
                "reference": f"decision-brief-snapshot:{row['snapshot_id']}",
                "content_hash": str(row["snapshot_hash"]),
            }
        ):
            raise ManagerDecisionUnavailable("stored manager decision failed integrity")
        _validate_audit_binding(
            connection,
            workspace_id=str(row["workspace_id"]),
            occurrence_id=str(row["occurrence_id"]),
            event_seq=int(row["event_seq"]),
            content_hash=str(row["content_hash"]),
            occurrence_kind=MANAGER_DECISION_AUDIT_KIND,
            outcome_code=MANAGER_DECISION_AUDIT_OUTCOME,
        )
        return payload

    def _manager_snapshot_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        payload = _json_mapping(
            row["payload_json"],
            "stored manager decision snapshot is invalid",
        )
        if (
            payload.get("schema_identifier") != DECISION_BRIEF_SNAPSHOT_SCHEMA_IDENTIFIER
            or payload.get("schema_version") != DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION
            or payload.get("snapshot_id") != str(row["snapshot_id"])
            or payload.get("occurrence_id") != str(row["occurrence_id"])
            or payload.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(payload) != str(row["content_hash"])
            or payload.get("decision_key") != str(row["decision_key"])
        ):
            raise ManagerDecisionUnavailable(
                "stored manager decision snapshot failed integrity"
            )
        _validate_audit_binding(
            connection,
            workspace_id=str(row["workspace_id"]),
            occurrence_id=str(row["occurrence_id"]),
            event_seq=int(row["event_seq"]),
            content_hash=str(row["content_hash"]),
            occurrence_kind=MANAGER_DECISION_SNAPSHOT_AUDIT_KIND,
            outcome_code=MANAGER_DECISION_SNAPSHOT_AUDIT_OUTCOME,
        )
        return payload

    def _manager_existing_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> StoredManagerDecision | None:
        row = connection.execute(
            """
            SELECT *
            FROM governance_manager_decisions
            WHERE workspace_id = ? AND idempotency_key = ?
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise ManagerDecisionConflict
        decision = self._manager_decision_from_row(connection, row)
        snapshot_row = connection.execute(
            """
            SELECT *
            FROM governance_manager_decision_snapshots
            WHERE workspace_id = ? AND snapshot_id = ?
            """,
            (workspace_id, str(row["snapshot_id"])),
        ).fetchone()
        if snapshot_row is None:
            raise ManagerDecisionUnavailable("manager decision snapshot is missing")
        snapshot = self._manager_snapshot_from_row(connection, snapshot_row)
        draft_ref = _required_ref(
            decision.get("draft_version_ref_and_hash"),
            "stored decision draft head",
        )
        return StoredManagerDecision(
            result="IDEMPOTENT_REPLAY",
            decision=decision,
            snapshot=snapshot,
            draft=self._manager_draft_version_locked(
                connection,
                workspace_id=workspace_id,
                draft_id=str(decision["draft_id"]),
                expected_version=draft_ref,
                manager_actor_ref=str(decision["manager_actor_ref"]),
            ),
            authorization_attempt=_mapping(decision.get("authorization_attempt")),
            authorization_currentness=_mapping(
                decision.get("authorization_currentness")
            ),
            operation=_mapping(decision.get("operation")),
            currentness=_mapping(decision.get("currentness")),
            terminal_claim=_mapping(decision.get("terminal_claim")),
        )

    def _manager_draft_head_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        draft_id: str,
        expected_head: Mapping[str, Any],
        manager_actor_ref: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT *
            FROM governance_draft_versions
            WHERE workspace_id = ? AND draft_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (workspace_id, draft_id),
        ).fetchone()
        if row is None:
            raise ManagerDecisionUnavailable("manager draft is unavailable")
        try:
            head = self._draft_row_to_payload(row)
        except DraftStoreUnavailable as error:
            raise ManagerDecisionUnavailable("manager draft is unavailable") from error
        if not _same_ref(expected_head, _draft_ref(head)):
            raise ManagerDecisionHeadRace
        if head.get("manager_actor_ref") != manager_actor_ref:
            raise ManagerDecisionUnavailable("manager actor does not own the draft head")
        return head

    def _manager_draft_version_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        draft_id: str,
        expected_version: Mapping[str, Any],
        manager_actor_ref: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT *
            FROM governance_draft_versions
            WHERE workspace_id = ? AND draft_id = ? AND occurrence_id = ?
            """,
            (workspace_id, draft_id, expected_version.get("reference")),
        ).fetchone()
        if row is None:
            raise ManagerDecisionUnavailable("stored manager decision draft version is missing")
        try:
            version = self._draft_row_to_payload(row)
        except DraftStoreUnavailable as error:
            raise ManagerDecisionUnavailable(
                "stored manager decision draft version is invalid"
            ) from error
        if not _same_ref(expected_version, _draft_ref(version)):
            raise ManagerDecisionUnavailable("stored manager decision draft binding failed integrity")
        if version.get("manager_actor_ref") != manager_actor_ref:
            raise ManagerDecisionUnavailable("stored manager decision actor binding failed integrity")
        return version

    def _manager_draft_history_refs_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        draft_id: str,
        head: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        rows = connection.execute(
            """
            SELECT *
            FROM governance_draft_versions
            WHERE workspace_id = ? AND draft_id = ?
            ORDER BY version_number
            """,
            (workspace_id, draft_id),
        ).fetchall()
        if not rows:
            raise ManagerDecisionUnavailable("manager draft history is unavailable")
        history: list[dict[str, Any]] = []
        for expected_version, row in enumerate(rows, start=1):
            try:
                version = self._draft_row_to_payload(row)
            except DraftStoreUnavailable as error:
                raise ManagerDecisionUnavailable("manager draft history is unavailable") from error
            if int(version.get("version_number", 0)) != expected_version:
                raise ManagerDecisionUnavailable("manager draft version sequence is invalid")
            if version.get("draft_id") != draft_id:
                raise ManagerDecisionUnavailable("manager draft history identity is invalid")
            predecessor = version.get("predecessor_ref_and_hash_or_null")
            expected_predecessor = (
                None if not history else _draft_ref(history[-1])
            )
            if predecessor != expected_predecessor:
                raise ManagerDecisionUnavailable("manager draft predecessor chain is invalid")
            history.append(version)
        if not _same_ref(_draft_ref(history[-1]), _draft_ref(head)):
            raise ManagerDecisionHeadRace
        return [_draft_ref(version) for version in history]

    def _manager_chain_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        head: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            context = self._draft_row_context(head)
            artifact = self._draft_row_artifact(head)
        except (DraftContextUnavailable, DraftStoreUnavailable) as error:
            raise ManagerDecisionUnavailable("manager draft provenance is unavailable") from error
        provenance = _mapping(context.get("provenance"))
        if provenance is None:
            raise ManagerDecisionUnavailable("manager draft provenance is unavailable")
        evaluation_ref = _required_ref(
            provenance.get("evaluation_result"),
            "draft evaluation result",
        )
        evaluation_occurrence_id = _occurrence_from_reference(
            evaluation_ref["reference"],
            "decision-support-result",
        )
        rows = connection.execute(
            """
            SELECT *
            FROM decision_support_evaluations
            WHERE workspace_id = ? AND evaluation_occurrence_id = ?
            """,
            (workspace_id, evaluation_occurrence_id),
        ).fetchall()
        if len(rows) != 1:
            raise ManagerDecisionUnavailable("draft evaluation result is unavailable")
        evaluation_row, evaluation, terminal = self._load_evaluation_locked(
            connection,
            workspace_id=workspace_id,
            evaluation_series_id=str(rows[0]["evaluation_series_id"]),
            evaluation_occurrence_id=evaluation_occurrence_id,
            evaluation_digest=str(rows[0]["evaluation_digest"]),
            terminal_binding=evaluation_ref,
        )
        terminal_ref = {
            "reference": f"decision-support-result:{evaluation_occurrence_id}",
            "content_hash": str(evaluation_row["result_hash"]),
        }
        if not _same_ref(terminal_ref, evaluation_ref):
            raise ManagerDecisionUnavailable("draft evaluation binding is not authoritative")
        recommendation = _mapping(terminal.get("action_recommendation"))
        recommendation_ref = _required_ref(
            None if recommendation is None else {
                "reference": recommendation.get("occurrence_id"),
                "content_hash": recommendation.get("content_hash"),
            },
            "Action Recommendation",
        )
        draft_recommendation = _required_ref(
            head.get("recommendation_ref_and_hash"),
            "draft recommendation",
        )
        if not _same_ref(draft_recommendation, recommendation_ref):
            raise ManagerDecisionUnavailable("draft recommendation is not the authoritative recommendation")
        evidence_ref = _required_ref(head.get("evidence_ref_and_hash"), "draft evidence")
        if not _same_ref(evidence_ref, terminal_ref):
            raise ManagerDecisionUnavailable("draft evidence is not the evaluation result")
        selection_ref = _optional_ref(
            provenance.get("accepted_selection_claim"),
            "accepted selection claim",
        )
        selection_claim = None
        if selection_ref is not None:
            selection_claim = self._selection_claim_by_ref_locked(
                connection,
                workspace_id=workspace_id,
                reference=selection_ref["reference"],
                content_hash=selection_ref["content_hash"],
            )
            if selection_claim is None:
                raise ManagerDecisionUnavailable("accepted selection claim is unavailable")
        selection_basis = recommendation.get("selection_basis")
        if (selection_basis == "MANAGER_TRADEOFF_SELECTION") != (
            selection_ref is not None
        ):
            raise ManagerDecisionUnavailable("recommendation and accepted selection claim disagree")
        chain_published_at = (
            selection_claim.get("published_at")
            if selection_claim is not None
            else evaluation.get("evaluation_published_at")
        )
        if not isinstance(chain_published_at, (str, Mapping)):
            raise ManagerDecisionUnavailable("advice chain publication time is unavailable")
        return {
            "context": context,
            "artifact": artifact,
            "evaluation": evaluation,
            "terminal": terminal,
            "evaluation_row": evaluation_row,
            "evaluation_series_id": str(rows[0]["evaluation_series_id"]),
            "evaluation_occurrence_id": evaluation_occurrence_id,
            "evaluation_digest": str(rows[0]["evaluation_digest"]),
            "terminal_ref": terminal_ref,
            "recommendation_ref": recommendation_ref,
            "recommendation": deepcopy(dict(recommendation)),
            "evidence_ref": evidence_ref,
            "selection_ref": selection_ref,
            "selection_claim": selection_claim,
            "chain_published_at": deepcopy(chain_published_at),
            "draft_history_ref_and_hashes": self._manager_draft_history_refs_locked(
                connection,
                workspace_id=workspace_id,
                draft_id=str(head["draft_id"]),
                head=head,
            ),
        }

    def _manager_non_authorizing_chain_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        head: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            context = self._draft_row_context(head)
            artifact = self._draft_row_artifact(head)
        except (DraftContextUnavailable, DraftStoreUnavailable) as error:
            raise ManagerDecisionUnavailable("manager draft provenance is unavailable") from error
        provenance = _mapping(context.get("provenance"))
        if provenance is None:
            raise ManagerDecisionUnavailable("manager draft provenance is unavailable")
        evaluation_ref = _required_ref(
            provenance.get("evaluation_result"),
            "draft evaluation result",
        )
        return {
            "context": context,
            "artifact": artifact,
            "evaluation": None,
            "terminal": None,
            "evaluation_row": None,
            "evaluation_series_id": None,
            "evaluation_occurrence_id": _occurrence_from_reference(
                evaluation_ref["reference"],
                "decision-support-result",
            ),
            "evaluation_digest": None,
            "terminal_ref": evaluation_ref,
            "recommendation_ref": _required_ref(
                head.get("recommendation_ref_and_hash"),
                "draft recommendation",
            ),
            "recommendation": None,
            "evidence_ref": _required_ref(head.get("evidence_ref_and_hash"), "draft evidence"),
            "selection_ref": _optional_ref(
                provenance.get("accepted_selection_claim"),
                "accepted selection claim",
            ),
            "selection_claim": None,
            "chain_published_at": None,
            "draft_history_ref_and_hashes": self._manager_draft_history_refs_locked(
                connection,
                workspace_id=workspace_id,
                draft_id=str(head["draft_id"]),
                head=head,
            ),
        }

    def _authorization_attempt(
        self,
        *,
        workspace_id: str,
        head: Mapping[str, Any],
        chain: Mapping[str, Any],
        manager_actor_ref: str,
        available_at: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        attempt_fields = {
            "schema_identifier": "manager-authorization-attempt",
            "schema_version": "1",
            "requested_disposition": "APPROVE",
            "draft_id": str(head["draft_id"]),
            "draft_version_ref_and_hash": _draft_ref(head),
            "draft_context_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("draft_context_ref_and_hash"), "draft context"))
            ),
            "drafted_artifact_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("source_artifact_ref_and_hash"), "drafted artifact"))
            ),
            "draft_history_ref_and_hashes": deepcopy(
                list(chain["draft_history_ref_and_hashes"])
            ),
            "evaluation_series_id": chain.get("evaluation_series_id"),
            "evaluation_occurrence_id": chain.get("evaluation_occurrence_id"),
            "evaluation_digest": chain.get("evaluation_digest"),
            "terminal_result_ref_and_hash": deepcopy(dict(chain["terminal_ref"])),
            "recommendation_ref_and_hash": deepcopy(dict(chain["recommendation_ref"])),
            "accepted_selection_claim_ref_and_hash": deepcopy(
                chain["selection_ref"]
            ),
            "manager_actor_ref": manager_actor_ref,
            "advice_chain_published_at": deepcopy(chain["chain_published_at"]),
            "requested_at": available_at,
            "available_at": available_at,
        }
        attempt_key = _sha256(
            {
                "schema_identifier_and_version": {
                    "identifier": "manager-authorization-attempt",
                    "version": "1",
                },
                "requested_disposition": attempt_fields["requested_disposition"],
                "evaluation_series_id": attempt_fields["evaluation_series_id"],
                "evaluation_occurrence_id": attempt_fields[
                    "evaluation_occurrence_id"
                ],
                "evaluation_digest": attempt_fields["evaluation_digest"],
                "terminal_result_ref_and_hash": deepcopy(
                    dict(attempt_fields["terminal_result_ref_and_hash"])
                ),
                "recommendation_ref_and_hash": deepcopy(
                    dict(attempt_fields["recommendation_ref_and_hash"])
                ),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                    attempt_fields["accepted_selection_claim_ref_and_hash"]
                ),
                "manager_actor_ref": attempt_fields["manager_actor_ref"],
                "advice_chain_published_at": deepcopy(
                    attempt_fields["advice_chain_published_at"]
                ),
                "requested_at": attempt_fields["requested_at"],
                "available_at": attempt_fields["available_at"],
            }
        )
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:manager-authorization-attempt:{workspace_id}:{attempt_key}",
        ).hex
        attempt = {
            **attempt_fields,
            "authorization_attempt_key": attempt_key,
            "occurrence_id": occurrence_id,
            "authorization_attempt_ref": f"manager-authorization-attempt:{occurrence_id}",
        }
        attempt["content_hash"] = _hash_without_content_hash(attempt)
        return attempt, {
            "reference": f"manager-authorization-attempt:{occurrence_id}",
            "content_hash": str(attempt["content_hash"]),
        }

    def _authorization_operation(
        self,
        *,
        attempt: Mapping[str, Any],
        attempt_ref: Mapping[str, Any],
        chain: Mapping[str, Any],
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "schema_identifier": "advice-currentness-operation",
            "schema_version": "1",
            "currentness_policy_identifier_and_version": deepcopy(
                CURRENTNESS_POLICY_IDENTIFIER_AND_VERSION
            ),
            "operation_kind": "MANAGER_AUTHORIZATION",
            "evaluation_series_id": chain.get("evaluation_series_id"),
            "evaluation_occurrence_id": chain.get("evaluation_occurrence_id"),
            "evaluation_digest": chain.get("evaluation_digest"),
            "terminal_result_ref_and_hash": deepcopy(dict(chain["terminal_ref"])),
            "recommendation_ref_and_hash_or_null": deepcopy(
                dict(chain["recommendation_ref"])
            ),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                chain["selection_ref"]
            ),
            "operation_payload_ref_and_hash": deepcopy(dict(attempt_ref)),
            "currentness_checked_at": deepcopy(attempt["available_at"]),
            "operation_payload": deepcopy(dict(attempt)),
        }
        fields = _key_fields(operation)
        operation_key = currentness_operation_key_for(fields)
        record = _operation_record_for(fields, attempt, operation_key)
        operation.update(
            {
                "currentness_operation_key": operation_key,
                "operation_occurrence_id": record["operation_occurrence_id"],
                "content_hash": record["content_hash"],
            }
        )
        return operation

    def _publish_manager_decision_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        idempotency_key: str,
        request_hash: str,
        head: Mapping[str, Any],
        chain: Mapping[str, Any],
        disposition: str,
        manager_actor_ref: str,
        decided_at: str,
        authorization_attempt: Mapping[str, Any] | None,
        authorization_currentness: Mapping[str, Any] | None,
        operation: Mapping[str, Any] | None,
        currentness: Mapping[str, Any] | None,
        terminal_claim: Mapping[str, Any] | None,
    ) -> StoredManagerDecision:
        authorization_attempt_ref = (
            None
            if authorization_attempt is None
            else {
                "reference": f"manager-authorization-attempt:{authorization_attempt['occurrence_id']}",
                "content_hash": authorization_attempt["content_hash"],
            }
        )
        authorization_currentness_ref = (
            None
            if authorization_currentness is None
            else {
                "reference": (
                    "authorization-currentness-result:"
                    + str(authorization_currentness["consuming_result_occurrence_id"])
                ),
                "content_hash": authorization_currentness["content_hash"],
            }
        )
        operation_ref = (
            None
            if operation is None
            else {
                "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
                "content_hash": operation["content_hash"],
            }
        )
        check_ref = (
            None
            if currentness is None
            else {
                "reference": f"currentness-check:{currentness['currentness_check_occurrence_id']}",
                "content_hash": currentness["content_hash"],
            }
        )
        terminal_currentness_ref = (
            None
            if terminal_claim is None
            else _optional_ref(
                terminal_claim.get("terminal_currentness_ref_and_hash"),
                "terminal currentness",
            )
        )
        if disposition == "APPROVE":
            decision_key_fields = {
                "authorization_attempt_ref_and_hash": deepcopy(
                    dict(authorization_attempt_ref or {})
                ),
                "authorization_currentness_ref_and_hash": deepcopy(
                    dict(authorization_currentness_ref or {})
                ),
                "disposition": disposition,
                "recommendation_ref_and_hash": deepcopy(
                    dict(chain["recommendation_ref"])
                ),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                    chain["selection_ref"]
                ),
                "manager_actor_ref": manager_actor_ref,
                "decided_at": decided_at,
            }
        else:
            decision_key_fields = {
                "draft_id": str(head["draft_id"]),
                "draft_version_ref_and_hash": _draft_ref(head),
                "draft_history_ref_and_hashes": deepcopy(
                    list(chain["draft_history_ref_and_hashes"])
                ),
                "disposition": disposition,
                "manager_actor_ref": manager_actor_ref,
                "decided_at": decided_at,
                "recommendation_ref_and_hash": deepcopy(
                    dict(chain["recommendation_ref"])
                ),
                "evidence_ref_and_hash": deepcopy(dict(chain["evidence_ref"])),
            }
        decision_key = _sha256(decision_key_fields)
        decision_occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:manager-decision:{workspace_id}:{decision_key}",
        ).hex
        snapshot_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:decision-brief-snapshot:{workspace_id}:{decision_key}",
        ).hex
        snapshot_occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:decision-brief-snapshot-occurrence:{workspace_id}:{decision_key}",
        ).hex
        snapshot_reference_id = f"decision-brief:{workspace_id}:{decision_key}"
        decision_reference = f"manager-decision:{decision_occurrence_id}"
        snapshot_event_seq = _next_audit_event_seq(connection)
        snapshot_payload: dict[str, Any] = {
            "schema_identifier": DECISION_BRIEF_SNAPSHOT_SCHEMA_IDENTIFIER,
            "schema_version": DECISION_BRIEF_SNAPSHOT_SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "occurrence_id": snapshot_occurrence_id,
            "reference_id": snapshot_reference_id,
            "event_seq": snapshot_event_seq,
            "created_at": decided_at,
            "decision_key": decision_key,
            "manager_decision_occurrence_id": decision_occurrence_id,
            "manager_decision_ref": decision_reference,
            "draft_id": str(head["draft_id"]),
            "draft_version": deepcopy(dict(head)),
            "draft_version_ref_and_hash": _draft_ref(head),
            "draft_context": deepcopy(dict(chain["context"])),
            "draft_context_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("draft_context_ref_and_hash"), "draft context"))
            ),
            "drafted_artifact": deepcopy(dict(chain["artifact"])),
            "drafted_artifact_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("source_artifact_ref_and_hash"), "drafted artifact"))
            ),
            "draft_history_ref_and_hashes": deepcopy(
                list(chain["draft_history_ref_and_hashes"])
            ),
            "recommendation_ref_and_hash": deepcopy(dict(chain["recommendation_ref"])),
            "action_recommendation": (
                None
                if chain.get("recommendation") is None
                else deepcopy(dict(chain["recommendation"]))
            ),
            "evidence_ref_and_hash": deepcopy(dict(chain["evidence_ref"])),
            "evaluation": (
                None
                if chain.get("evaluation") is None
                else deepcopy(dict(chain["evaluation"]))
            ),
            "evidence": (
                None
                if chain.get("terminal") is None
                else deepcopy(dict(chain["terminal"]))
            ),
            "terminal_result_ref_and_hash": deepcopy(dict(chain["terminal_ref"])),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                chain["selection_ref"]
            ),
            "accepted_selection_claim": (
                None
                if chain.get("selection_claim") is None
                else deepcopy(dict(chain["selection_claim"]))
            ),
            "manager_actor_ref": manager_actor_ref,
            "disposition": disposition,
            "decided_at": decided_at,
            "authorization_attempt_ref_and_hash_or_null": authorization_attempt_ref,
            "authorization_currentness_ref_and_hash_or_null": authorization_currentness_ref,
            "currentness_operation_ref_and_hash_or_null": operation_ref,
            "currentness_check_ref_and_hash_or_null": check_ref,
            "currentness_outcome_or_null": (
                None if currentness is None else currentness.get("currentness_outcome")
            ),
            "authorization_state": (
                "AUTHORIZED" if disposition == "APPROVE" else "NOT_AUTHORIZED"
            ),
            "execution_state": "NOT_EXECUTED",
            "no_send": True,
            "no_send_language": (
                "This records manager authority only; no message was sent and no action was executed."
            ),
            "presentation_contract": {
                "show_exact_evidence_chain": True,
                "show_exact_recommendation_chain": True,
                "show_exact_draft_chain": True,
                "show_no_send_language": True,
            },
            "references": {
                "manager_decision": decision_reference,
                "draft_version": _draft_ref(head),
                "draft_history": deepcopy(list(chain["draft_history_ref_and_hashes"])),
                "recommendation": deepcopy(dict(chain["recommendation_ref"])),
                "evidence": deepcopy(dict(chain["evidence_ref"])),
                "authorization_attempt": authorization_attempt_ref,
                "authorization_currentness": authorization_currentness_ref,
                "currentness_operation": operation_ref,
                "currentness_check": check_ref,
            },
        }
        snapshot_payload["content_hash"] = _hash_without_content_hash(snapshot_payload)
        snapshot_ref = {
            "reference": f"decision-brief-snapshot:{snapshot_id}",
            "content_hash": snapshot_payload["content_hash"],
        }
        decision: dict[str, Any] = {
            "schema_identifier": MANAGER_DECISION_SCHEMA_IDENTIFIER,
            "schema_version": "1",
            "manager_decision_id": decision_occurrence_id,
            "occurrence_id": decision_occurrence_id,
            "decision_key": decision_key,
            "draft_id": str(head["draft_id"]),
            "draft_version_ref_and_hash": _draft_ref(head),
            "draft_context_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("draft_context_ref_and_hash"), "draft context"))
            ),
            "drafted_artifact_ref_and_hash": deepcopy(
                dict(_required_ref(head.get("source_artifact_ref_and_hash"), "drafted artifact"))
            ),
            "draft_history_ref_and_hashes": deepcopy(
                list(chain["draft_history_ref_and_hashes"])
            ),
            "recommendation_ref_and_hash": deepcopy(dict(chain["recommendation_ref"])),
            "evidence_ref_and_hash": deepcopy(dict(chain["evidence_ref"])),
            "evaluation_series_id": chain.get("evaluation_series_id"),
            "evaluation_occurrence_id": chain.get("evaluation_occurrence_id"),
            "evaluation_digest": chain.get("evaluation_digest"),
            "terminal_result_ref_and_hash": deepcopy(dict(chain["terminal_ref"])),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                chain["selection_ref"]
            ),
            "manager_actor_ref": manager_actor_ref,
            "disposition": disposition,
            "decided_at": decided_at,
            "authorization_attempt_ref_and_hash_or_null": authorization_attempt_ref,
            "authorization_currentness_ref_and_hash_or_null": authorization_currentness_ref,
            "currentness_operation_ref_and_hash_or_null": operation_ref,
            "currentness_check_ref_and_hash_or_null": check_ref,
            "terminal_currentness_ref_and_hash_or_null": terminal_currentness_ref,
            "currentness_outcome_or_null": (
                None if currentness is None else currentness.get("currentness_outcome")
            ),
            "authorization_attempt": (
                None
                if authorization_attempt is None
                else deepcopy(dict(authorization_attempt))
            ),
            "authorization_currentness": (
                None
                if authorization_currentness is None
                else deepcopy(dict(authorization_currentness))
            ),
            "operation": None if operation is None else deepcopy(dict(operation)),
            "currentness": None if currentness is None else deepcopy(dict(currentness)),
            "terminal_claim": (
                None if terminal_claim is None else deepcopy(dict(terminal_claim))
            ),
            "authorization_state": (
                "AUTHORIZED" if disposition == "APPROVE" else "NOT_AUTHORIZED"
            ),
            "execution_state": "NOT_EXECUTED",
            "no_send": True,
            "no_send_language": (
                "This records manager authority only; no message was sent and no action was executed."
            ),
            "decision_brief_snapshot_ref_and_hash": snapshot_ref,
            "references": {
                "manager_decision": decision_reference,
                "decision_brief_snapshot": snapshot_ref,
                "draft_version": _draft_ref(head),
                "draft_history": deepcopy(list(chain["draft_history_ref_and_hashes"])),
                "recommendation": deepcopy(dict(chain["recommendation_ref"])),
                "evidence": deepcopy(dict(chain["evidence_ref"])),
                "authorization_attempt": authorization_attempt_ref,
                "authorization_currentness": authorization_currentness_ref,
                "currentness_operation": operation_ref,
                "currentness_check": check_ref,
            },
        }
        decision["content_hash"] = _hash_without_content_hash(decision)
        now = datetime.fromisoformat(decided_at)
        mutation = self._record_mutation_locked(
            workspace_id,
            idempotency_key=idempotency_key,
            mutation_kind=MANAGER_DECISION_AUDIT_KIND,
            content_hash=str(decision["content_hash"]),
            terminal_fresh_bundle=False,
            now=now,
        )
        if mutation.replayed:
            raise ManagerDecisionUnavailable("manager decision mutation is missing")
        snapshot_created_at = decided_at
        snapshot_cursor = connection.execute(
            """
            INSERT INTO audit_events (
                workspace_id, occurrence_id, idempotency_key,
                occurrence_kind, outcome_code, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                snapshot_occurrence_id,
                f"manager-decision-snapshot:{decision_key}",
                MANAGER_DECISION_SNAPSHOT_AUDIT_KIND,
                MANAGER_DECISION_SNAPSHOT_AUDIT_OUTCOME,
                snapshot_payload["content_hash"],
                snapshot_created_at,
            ),
        )
        if snapshot_cursor.lastrowid is None:
            raise ManagerDecisionUnavailable("manager decision snapshot was not sequenced")
        if int(snapshot_cursor.lastrowid) != int(snapshot_payload["event_seq"]):
            raise ManagerDecisionUnavailable("manager decision snapshot sequence changed")
        snapshot_event_seq = int(snapshot_cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO governance_manager_decision_snapshots (
                snapshot_id, workspace_id, decision_key, reference_id,
                content_hash, occurrence_id, event_seq, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                workspace_id,
                decision_key,
                snapshot_reference_id,
                snapshot_payload["content_hash"],
                snapshot_occurrence_id,
                snapshot_event_seq,
                snapshot_created_at,
                _canonical_json(snapshot_payload),
            ),
        )
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=decision_occurrence_id,
            idempotency_key=idempotency_key,
            occurrence_kind=MANAGER_DECISION_AUDIT_KIND,
            outcome_code=MANAGER_DECISION_AUDIT_OUTCOME,
            content_hash=str(decision["content_hash"]),
            created_at=decided_at,
        )
        decision_event_seq = _audit_event_seq(
            connection,
            workspace_id=workspace_id,
            occurrence_id=decision_occurrence_id,
        )
        connection.execute(
            """
            INSERT INTO governance_manager_decisions (
                manager_decision_id, workspace_id, idempotency_key,
                request_hash, decision_key, content_hash, snapshot_id,
                snapshot_hash, occurrence_id, event_seq, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_occurrence_id,
                workspace_id,
                idempotency_key,
                request_hash,
                decision_key,
                decision["content_hash"],
                snapshot_id,
                snapshot_payload["content_hash"],
                decision_occurrence_id,
                decision_event_seq,
                decided_at,
                _canonical_json(decision),
            ),
        )
        return StoredManagerDecision(
            result="CREATED",
            decision=decision,
            snapshot=snapshot_payload,
            draft=deepcopy(dict(head)),
            authorization_attempt=(
                None
                if authorization_attempt is None
                else deepcopy(dict(authorization_attempt))
            ),
            authorization_currentness=(
                None
                if authorization_currentness is None
                else deepcopy(dict(authorization_currentness))
            ),
            operation=None if operation is None else deepcopy(dict(operation)),
            currentness=None if currentness is None else deepcopy(dict(currentness)),
            terminal_claim=(
                None if terminal_claim is None else deepcopy(dict(terminal_claim))
            ),
        )

    def record_manager_decision(
        self,
        workspace_id: str,
        draft_id: str,
        *,
        idempotency_key: str,
        manager_actor_ref: str,
        expected_head: Mapping[str, Any],
        disposition: str,
        now: datetime | None = None,
    ) -> StoredManagerDecision:
        if disposition not in {"APPROVE", "REJECT", "INVESTIGATE_FURTHER"}:
            raise ManagerDecisionUnavailable("manager disposition is unsupported")
        if not isinstance(manager_actor_ref, str) or not manager_actor_ref:
            raise ManagerDecisionUnavailable("manager actor is unavailable")
        request_hash = _sha256(
            {
                "kind": "MANAGER_DECISION",
                "draft_id": draft_id,
                "manager_actor_ref": manager_actor_ref,
                "expected_head": deepcopy(dict(expected_head)),
                "disposition": disposition,
            }
        )
        current_time = now or datetime.now(timezone.utc)
        decided_at = _timestamp(current_time)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._manager_existing_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    connection.commit()
                    return existing
                head = self._manager_draft_head_locked(
                    connection,
                    workspace_id=workspace_id,
                    draft_id=draft_id,
                    expected_head=expected_head,
                    manager_actor_ref=manager_actor_ref,
                )
                expected_disposition = {
                    "APPROVE": "APPROVE_INTENT",
                    "REJECT": "REJECTED",
                    "INVESTIGATE_FURTHER": "INVESTIGATE_FURTHER",
                }[disposition]
                if head.get("disposition") != expected_disposition:
                    raise ManagerDecisionUnavailable(
                        "manager decision does not match the draft disposition"
                    )
                chain = (
                    self._manager_chain_locked(
                        connection,
                        workspace_id=workspace_id,
                        head=head,
                    )
                    if disposition == "APPROVE"
                    else self._manager_non_authorizing_chain_locked(
                        connection,
                        workspace_id=workspace_id,
                        head=head,
                    )
                )
                authorization_attempt = None
                authorization_currentness = None
                operation = None
                currentness = None
                terminal_claim = None
                if disposition == "APPROVE":
                    authorization_attempt, attempt_ref = self._authorization_attempt(
                        workspace_id=workspace_id,
                        head=head,
                        chain=chain,
                        manager_actor_ref=manager_actor_ref,
                        available_at=decided_at,
                    )
                    _audit_locked(
                        connection,
                        workspace_id=workspace_id,
                        occurrence_id=str(authorization_attempt["occurrence_id"]),
                        idempotency_key=(
                            "manager-authorization-attempt:"
                            + str(authorization_attempt["authorization_attempt_key"])
                        ),
                        occurrence_kind="DECISION_SUPPORT_CURRENTNESS_SOURCE_OCCURRENCE",
                        outcome_code="CURRENTNESS_SOURCE_REGISTERED",
                        content_hash=str(authorization_attempt["content_hash"]),
                        created_at=decided_at,
                    )
                    operation = self._authorization_operation(
                        attempt=authorization_attempt,
                        attempt_ref=attempt_ref,
                        chain=chain,
                    )
                    stored_currentness = self._check_currentness_locked(
                        connection,
                        workspace_id=workspace_id,
                        operation=operation,
                        currentness_context=None,
                        now=decided_at,
                    )
                    currentness = stored_currentness.currentness
                    terminal_claim = stored_currentness.terminal_claim
                    authorization_currentness = stored_currentness.consuming_result
                    if (
                        currentness.get("currentness_outcome")
                        != "CURRENTNESS_PROVEN_AT_CHECK"
                        or authorization_currentness is None
                    ):
                        connection.commit()
                        return StoredManagerDecision(
                            result="CURRENTNESS_REFUSED",
                            decision=None,
                            snapshot=None,
                            draft=deepcopy(dict(head)),
                            authorization_attempt=deepcopy(dict(authorization_attempt)),
                            authorization_currentness=(
                                None
                                if authorization_currentness is None
                                else deepcopy(dict(authorization_currentness))
                            ),
                            operation=deepcopy(dict(operation)),
                            currentness=deepcopy(dict(currentness)),
                            terminal_claim=deepcopy(dict(terminal_claim)),
                        )
                stored = self._publish_manager_decision_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    head=head,
                    chain=chain,
                    disposition=disposition,
                    manager_actor_ref=manager_actor_ref,
                    decided_at=decided_at,
                    authorization_attempt=authorization_attempt,
                    authorization_currentness=authorization_currentness,
                    operation=operation,
                    currentness=currentness,
                    terminal_claim=terminal_claim,
                )
                connection.commit()
                return stored
            except ManagerDecisionConflict:
                connection.rollback()
                raise
            except ManagerDecisionHeadRace:
                connection.rollback()
                raise
            except (
                ManagerDecisionUnavailable,
                DecisionSupportCurrentnessConflict,
                DecisionSupportCurrentnessOperationMismatch,
                DecisionSupportCurrentnessUnavailable,
                DraftHeadRace,
                DraftStoreUnavailable,
                DraftContextUnavailable,
                WorkspaceRequestError,
            ):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ManagerDecisionConflict from error
            except sqlite3.Error as error:
                connection.rollback()
                raise ManagerDecisionUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def get_manager_decisions(
        self,
        workspace_id: str,
        draft_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM governance_manager_decisions
                    WHERE workspace_id = ?
                    ORDER BY event_seq
                    """,
                    (workspace_id,),
                ).fetchall()
                items: list[dict[str, Any]] = []
                for row in rows:
                    decision = self._manager_decision_from_row(connection, row)
                    if decision.get("draft_id") != draft_id:
                        continue
                    snapshot_row = connection.execute(
                        """
                        SELECT *
                        FROM governance_manager_decision_snapshots
                        WHERE workspace_id = ? AND snapshot_id = ?
                        """,
                        (workspace_id, str(row["snapshot_id"])),
                    ).fetchone()
                    if snapshot_row is None:
                        raise ManagerDecisionUnavailable(
                            "manager decision snapshot is missing"
                        )
                    snapshot = self._manager_snapshot_from_row(connection, snapshot_row)
                    items.append({"decision": decision, "snapshot": snapshot})
                return {"draft_id": draft_id, "items": items}
            except ManagerDecisionUnavailable:
                raise
            except sqlite3.Error as error:
                raise ManagerDecisionUnavailable from error

    authorize_manager_decision = record_manager_decision
    authorize_draft = record_manager_decision
