from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping
from uuid import uuid4

from .canonical import canonical_json, sha256, timestamp
from .draft_context import (
    DraftContextUnavailable,
    validate_drafted_artifact,
    validate_draft_context,
    validate_manager_edited_draft,
)
from .errors import WorkspaceRequestError


DRAFT_STORAGE_SCHEMA_VERSION = "draft-storage.v1"
DRAFT_VERSION_SCHEMA_IDENTIFIER = "draft-version"
DRAFT_VERSION_SCHEMA_VERSION = "1"
DRAFT_AUDIT_KIND = "GOVERNANCE_DRAFT_VERSION"

DRAFT_VERSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS governance_draft_versions (
        draft_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        occurrence_id TEXT NOT NULL UNIQUE,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (draft_id, version_number),
        UNIQUE (workspace_id, idempotency_key)
    )
"""
DRAFT_VERSIONS_COLUMNS = [
    "draft_id",
    "version_number",
    "workspace_id",
    "idempotency_key",
    "request_hash",
    "occurrence_id",
    "content_hash",
    "created_at",
    "payload_json",
]


class DraftStoreUnavailable(Exception):
    """The immutable draft ledger cannot safely serve the request."""


class DraftIdempotencyConflict(Exception):
    """An idempotency key was reused for different draft input."""


class DraftHeadRace(Exception):
    """A draft edit or disposition targeted an obsolete head."""


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
        raise sqlite3.DatabaseError("draft ledger schema is not the locked Core schema")


def ensure_draft_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    _ensure_table(
        connection,
        "governance_draft_versions",
        DRAFT_VERSIONS_TABLE,
        DRAFT_VERSIONS_COLUMNS,
        create=create,
    )
    if create:
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS governance_draft_versions_immutable_update
            BEFORE UPDATE ON governance_draft_versions
            BEGIN
                SELECT RAISE(ABORT, 'governance draft versions are immutable');
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS governance_draft_versions_immutable_delete
            BEFORE DELETE ON governance_draft_versions
            BEGIN
                SELECT RAISE(ABORT, 'governance draft versions are immutable');
            END
            """
        )


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _reference_and_hash(value: object, label: str) -> dict[str, str]:
    mapping = _mapping(value)
    if mapping is None:
        raise DraftStoreUnavailable(f"{label} is unavailable")
    reference = mapping.get("reference")
    content_hash = mapping.get("content_hash")
    if not isinstance(reference, str) or not reference:
        raise DraftStoreUnavailable(f"{label} reference is unavailable")
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        raise DraftStoreUnavailable(f"{label} hash is unavailable")
    return {"reference": reference, "content_hash": content_hash}


def _json_object(value: object, label: str) -> dict[str, Any]:
    mapping = _mapping(value)
    if mapping is None:
        raise DraftStoreUnavailable(f"{label} is unavailable")
    return deepcopy(dict(mapping))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    without_hash = dict(payload)
    without_hash.pop("content_hash", None)
    return sha256(without_hash)


def _outcome_for(disposition: str) -> str:
    return {
        "NOT_DISPOSED": "DRAFT_CREATED",
        "APPROVE_INTENT": "DRAFT_APPROVAL_INTENT_RECORDED",
        "REJECTED": "DRAFT_REJECTED",
        "INVESTIGATE_FURTHER": "DRAFT_INVESTIGATION_REQUESTED",
    }[disposition]


def _operation_payload(
    *,
    draft_id: str,
    predecessor: Mapping[str, str],
    recommendation: Mapping[str, str],
    evidence: Mapping[str, str],
    manager_actor_ref: str,
    available_at: object,
) -> dict[str, Any]:
    operation_key = sha256(
        {
            "kind": "INVESTIGATE_FURTHER",
            "draft_id": draft_id,
            "draft_version_ref_and_hash": predecessor,
        }
    )
    operation = {
        "schema_identifier": "manager-draft-operation",
        "schema_version": "1",
        "operation_kind": "INVESTIGATE_FURTHER",
        "operation_key": operation_key,
        "status": "REQUESTED",
        "draft_version_ref_and_hash": deepcopy(dict(predecessor)),
        "recommendation_ref_and_hash": deepcopy(dict(recommendation)),
        "evidence_ref_and_hash": deepcopy(dict(evidence)),
        "manager_actor_ref": manager_actor_ref,
        "available_at": deepcopy(available_at),
        "authorization_state": "NOT_AUTHORIZED",
        "execution_state": "NOT_EXECUTED",
    }
    operation["occurrence_id"] = f"manager-operation:{operation_key}"
    operation["content_hash"] = _payload_hash(operation)
    return operation


class DraftStoreMixin:
    """Append-only, workspace-scoped persistence for manager draft versions."""

    def _draft_row_to_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise DraftStoreUnavailable from error
        if not isinstance(payload, dict):
            raise DraftStoreUnavailable
        if (
            payload.get("draft_id") != str(row["draft_id"])
            or payload.get("version_number") != int(row["version_number"])
            or payload.get("occurrence_id") != str(row["occurrence_id"])
            or payload.get("content_hash") != str(row["content_hash"])
            or _payload_hash(payload) != str(row["content_hash"])
        ):
            raise DraftStoreUnavailable
        try:
            context = validate_draft_context(payload.get("source_context"))
            artifact = validate_drafted_artifact(
                context,
                payload.get("source_artifact"),
            )
            recommendation = _reference_and_hash(
                artifact.get("recommendation_ref_and_hash"),
                "draft recommendation",
            )
            evidence = _reference_and_hash(
                _json_object(artifact.get("provenance"), "draft provenance").get(
                    "evaluation_result"
                ),
                "draft evidence",
            )
            if (
                payload.get("source") != artifact.get("source")
                or payload.get("recommendation_ref_and_hash") != recommendation
                or payload.get("evidence_ref_and_hash") != evidence
                or payload.get("authorization_state") != "NOT_AUTHORIZED"
                or payload.get("execution_state") != "NOT_EXECUTED"
            ):
                raise DraftStoreUnavailable
        except (DraftContextUnavailable, DraftStoreUnavailable):
            raise DraftStoreUnavailable
        return payload

    def _draft_existing_locked(
        self,
        workspace_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        connection = self._connection_or_raise()
        row = connection.execute(
            """
            SELECT * FROM governance_draft_versions
            WHERE workspace_id = ? AND idempotency_key = ?
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise DraftIdempotencyConflict
        return self._draft_row_to_payload(row)

    def find_draft_idempotency(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            try:
                return self._draft_existing_locked(
                    workspace_id,
                    idempotency_key,
                    request_hash,
                )
            except DraftIdempotencyConflict:
                raise
            except sqlite3.Error as error:
                raise DraftStoreUnavailable from error

    def get_draft_history(self, workspace_id: str, draft_id: str) -> dict[str, Any]:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM governance_draft_versions
                    WHERE workspace_id = ? AND draft_id = ?
                    ORDER BY version_number
                    """,
                    (workspace_id, draft_id),
                ).fetchall()
                history = [self._draft_row_to_payload(row) for row in rows]
            except DraftStoreUnavailable:
                raise
            except sqlite3.Error as error:
                raise DraftStoreUnavailable from error
        if not history:
            raise DraftStoreUnavailable
        return {"draft_id": draft_id, "head": history[-1], "history": history}

    def persist_prepared_draft(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        request_hash: str,
        manager_actor_ref: str,
        available_at: object,
        prepared: Mapping[str, Any],
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        context = validate_draft_context(prepared.get("draft_context"))
        artifact = validate_drafted_artifact(context, prepared.get("artifact"))
        currentness = _json_object(prepared.get("currentness"), "draft currentness")
        checker = _json_object(prepared.get("checker"), "draft checker")
        drafting = _json_object(prepared.get("drafting"), "drafting metadata")
        recommendation = _reference_and_hash(
            artifact.get("recommendation_ref_and_hash"),
            "draft recommendation",
        )
        evidence = _reference_and_hash(
            _json_object(artifact.get("provenance"), "draft provenance").get(
                "evaluation_result"
            ),
            "draft evidence",
        )
        current_time = now or datetime.now(timezone.utc)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._draft_existing_locked(
                    workspace_id,
                    idempotency_key,
                    request_hash,
                )
                if existing is not None:
                    connection.commit()
                    return existing, True
                self._active_row_locked(workspace_id, current_time)
                draft_id = uuid4().hex
                version = self._build_version(
                    draft_id=draft_id,
                    version_number=1,
                    predecessor=None,
                    source_artifact=artifact,
                    source_context=context,
                    currentness=currentness,
                    checker=checker,
                    drafting=drafting,
                    manager_actor_ref=manager_actor_ref,
                    available_at=available_at,
                    subject=str(artifact["subject"]),
                    body=str(artifact["body"]),
                    changed_fields=[],
                    disposition="NOT_DISPOSED",
                    rejection_reason=None,
                    manager_operation=None,
                    recommendation=recommendation,
                    evidence=evidence,
                    created_at=current_time,
                )
                self._insert_version_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    payload=version,
                    now=current_time,
                )
                connection.commit()
                return version, False
            except (DraftIdempotencyConflict, DraftStoreUnavailable):
                connection.rollback()
                raise
            except WorkspaceRequestError:
                connection.rollback()
                raise
            except (DraftContextUnavailable, sqlite3.Error) as error:
                connection.rollback()
                if isinstance(error, DraftContextUnavailable):
                    raise
                raise DraftStoreUnavailable from error

    def edit_draft(
        self,
        workspace_id: str,
        draft_id: str,
        *,
        idempotency_key: str,
        manager_actor_ref: str,
        expected_head: Mapping[str, str],
        subject: str,
        body: str,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        current_time = now or datetime.now(timezone.utc)
        request_hash = sha256(
            {
                "kind": "DRAFT_EDIT",
                "draft_id": draft_id,
                "manager_actor_ref": manager_actor_ref,
                "expected_head": dict(expected_head),
                "subject": subject,
                "body": body,
            }
        )
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._draft_existing_locked(
                    workspace_id,
                    idempotency_key,
                    request_hash,
                )
                if existing is not None:
                    connection.commit()
                    return existing, True
                head = self._head_locked(connection, workspace_id, draft_id)
                self._assert_head(head, expected_head)
                context = self._draft_row_context(head)
                artifact = self._draft_row_artifact(head)
                edited = validate_manager_edited_draft(
                    context,
                    artifact,
                    subject=subject,
                    body=body,
                )
                changed_fields = [
                    field
                    for field, value in (
                        ("subject", edited["subject"]),
                        ("body", edited["body"]),
                    )
                    if value != head[field]
                ]
                version = self._successor_version(
                    head,
                    manager_actor_ref=manager_actor_ref,
                    subject=edited["subject"],
                    body=edited["body"],
                    changed_fields=changed_fields,
                    disposition=str(head["disposition"]),
                    rejection_reason=head.get("rejection_reason"),
                    manager_operation=head.get("manager_operation"),
                    created_at=current_time,
                )
                self._insert_version_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    payload=version,
                    now=current_time,
                )
                connection.commit()
                return version, False
            except (DraftIdempotencyConflict, DraftHeadRace, DraftStoreUnavailable):
                connection.rollback()
                raise
            except WorkspaceRequestError:
                connection.rollback()
                raise
            except DraftContextUnavailable:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise DraftStoreUnavailable from error

    def dispose_draft(
        self,
        workspace_id: str,
        draft_id: str,
        *,
        idempotency_key: str,
        manager_actor_ref: str,
        expected_head: Mapping[str, str],
        disposition: str,
        rejection_reason: Mapping[str, str] | None,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        current_time = now or datetime.now(timezone.utc)
        request_hash = sha256(
            {
                "kind": "DRAFT_DISPOSITION",
                "draft_id": draft_id,
                "manager_actor_ref": manager_actor_ref,
                "expected_head": dict(expected_head),
                "disposition": disposition,
                "rejection_reason": deepcopy(rejection_reason),
            }
        )
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._draft_existing_locked(
                    workspace_id,
                    idempotency_key,
                    request_hash,
                )
                if existing is not None:
                    connection.commit()
                    return existing, True
                head = self._head_locked(connection, workspace_id, draft_id)
                self._assert_head(head, expected_head)
                source_artifact = self._draft_row_artifact(head)
                if disposition not in {"APPROVE", "REJECT", "INVESTIGATE_FURTHER"}:
                    raise DraftStoreUnavailable
                if disposition == "REJECT" and rejection_reason is None:
                    raise DraftStoreUnavailable
                if disposition != "REJECT" and rejection_reason is not None:
                    raise DraftStoreUnavailable
                recommendation = _reference_and_hash(
                    source_artifact.get("recommendation_ref_and_hash"),
                    "draft recommendation",
                )
                evidence = _reference_and_hash(
                    _json_object(source_artifact.get("provenance"), "draft provenance").get(
                        "evaluation_result"
                    ),
                    "draft evidence",
                )
                manager_operation = None
                if disposition == "INVESTIGATE_FURTHER":
                    manager_operation = _operation_payload(
                        draft_id=draft_id,
                        predecessor={
                            "reference": str(head["occurrence_id"]),
                            "content_hash": str(head["content_hash"]),
                        },
                        recommendation=recommendation,
                        evidence=evidence,
                        manager_actor_ref=manager_actor_ref,
                        available_at=head["available_at"],
                    )
                version = self._successor_version(
                    head,
                    manager_actor_ref=manager_actor_ref,
                    subject=str(head["subject"]),
                    body=str(head["body"]),
                    changed_fields=[],
                    disposition={
                        "APPROVE": "APPROVE_INTENT",
                        "REJECT": "REJECTED",
                        "INVESTIGATE_FURTHER": "INVESTIGATE_FURTHER",
                    }[disposition],
                    rejection_reason=deepcopy(rejection_reason),
                    manager_operation=manager_operation,
                    created_at=current_time,
                )
                self._insert_version_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    payload=version,
                    now=current_time,
                )
                connection.commit()
                return version, False
            except (DraftIdempotencyConflict, DraftHeadRace, DraftStoreUnavailable):
                connection.rollback()
                raise
            except WorkspaceRequestError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise DraftStoreUnavailable from error

    def _draft_row_context(self, head: Mapping[str, Any]) -> dict[str, Any]:
        context = head.get("source_context")
        return validate_draft_context(context)

    def _draft_row_artifact(self, head: Mapping[str, Any]) -> dict[str, Any]:
        context = self._draft_row_context(head)
        artifact = head.get("source_artifact")
        return validate_drafted_artifact(context, artifact)

    def _head_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        draft_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT * FROM governance_draft_versions
            WHERE workspace_id = ? AND draft_id = ?
            ORDER BY version_number DESC LIMIT 1
            """,
            (workspace_id, draft_id),
        ).fetchone()
        if row is None:
            raise DraftStoreUnavailable
        return self._draft_row_to_payload(row)

    @staticmethod
    def _assert_head(head: Mapping[str, Any], expected: Mapping[str, str]) -> None:
        if (
            expected.get("reference") != head.get("occurrence_id")
            or expected.get("content_hash") != head.get("content_hash")
        ):
            raise DraftHeadRace

    def _build_version(
        self,
        *,
        draft_id: str,
        version_number: int,
        predecessor: Mapping[str, Any] | None,
        source_artifact: Mapping[str, Any],
        source_context: Mapping[str, Any],
        currentness: Mapping[str, Any],
        checker: Mapping[str, Any],
        drafting: Mapping[str, Any],
        manager_actor_ref: str,
        available_at: object,
        subject: str,
        body: str,
        changed_fields: list[str],
        disposition: str,
        rejection_reason: Mapping[str, Any] | None,
        manager_operation: Mapping[str, Any] | None,
        recommendation: Mapping[str, str],
        evidence: Mapping[str, str],
        created_at: datetime,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_identifier": DRAFT_VERSION_SCHEMA_IDENTIFIER,
            "schema_version": DRAFT_VERSION_SCHEMA_VERSION,
            "draft_id": draft_id,
            "version_number": version_number,
            "occurrence_id": f"draft-version:{draft_id}:{version_number}",
            "predecessor_ref_and_hash_or_null": deepcopy(
                dict(predecessor) if predecessor is not None else None
            ),
            "source": source_artifact["source"],
            "source_artifact_ref_and_hash": {
                "reference": source_artifact["occurrence_id"],
                "content_hash": source_artifact["content_hash"],
            },
            "draft_context_ref_and_hash": deepcopy(
                dict(source_artifact["draft_context_ref_and_hash"])
            ),
            "deterministic_sections": deepcopy(
                dict(source_artifact["deterministic_sections"])
            ),
            "generated_sections": deepcopy(source_artifact.get("provider_sections")),
            "manager_edits": {"changed_fields": list(changed_fields)},
            "manager_actor_ref": manager_actor_ref,
            "available_at": deepcopy(available_at),
            "recommendation_ref_and_hash": deepcopy(dict(recommendation)),
            "evidence_ref_and_hash": deepcopy(dict(evidence)),
            "subject": subject,
            "recipient": source_artifact["recipient"],
            "body": body,
            "disposition": disposition,
            "rejection_reason": deepcopy(
                dict(rejection_reason) if rejection_reason is not None else None
            ),
            "manager_operation": deepcopy(
                dict(manager_operation) if manager_operation is not None else None
            ),
            "authorization_state": "NOT_AUTHORIZED",
            "execution_state": "NOT_EXECUTED",
            "source_context": deepcopy(dict(source_context)),
            "source_artifact": deepcopy(dict(source_artifact)),
            "currentness": deepcopy(dict(currentness)),
            "checker": deepcopy(dict(checker)),
            "drafting": deepcopy(dict(drafting)),
            "versioned_at": timestamp(created_at),
        }
        payload["content_hash"] = _payload_hash(payload)
        return payload

    def _successor_version(
        self,
        head: Mapping[str, Any],
        *,
        manager_actor_ref: str,
        subject: str,
        body: str,
        changed_fields: list[str],
        disposition: str,
        rejection_reason: Mapping[str, Any] | None,
        manager_operation: Mapping[str, Any] | None,
        created_at: datetime,
    ) -> dict[str, Any]:
        predecessor = {
            "reference": str(head["occurrence_id"]),
            "content_hash": str(head["content_hash"]),
        }
        payload = deepcopy(dict(head))
        payload.update(
            {
                "version_number": int(head["version_number"]) + 1,
                "occurrence_id": f"draft-version:{head['draft_id']}:{int(head['version_number']) + 1}",
                "predecessor_ref_and_hash_or_null": predecessor,
                "manager_edits": {"changed_fields": list(changed_fields)},
                "manager_actor_ref": manager_actor_ref,
                "subject": subject,
                "body": body,
                "disposition": disposition,
                "rejection_reason": deepcopy(
                    dict(rejection_reason) if rejection_reason is not None else None
                ),
                "manager_operation": deepcopy(
                    dict(manager_operation) if manager_operation is not None else None
                ),
                "authorization_state": "NOT_AUTHORIZED",
                "execution_state": "NOT_EXECUTED",
                "versioned_at": timestamp(created_at),
            }
        )
        payload["content_hash"] = _payload_hash(payload)
        return payload

    def _insert_version_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        idempotency_key: str,
        request_hash: str,
        payload: Mapping[str, Any],
        now: datetime,
    ) -> None:
        mutation = self._record_mutation_locked(
            workspace_id,
            idempotency_key=idempotency_key,
            mutation_kind=DRAFT_AUDIT_KIND,
            content_hash=str(payload["content_hash"]),
            terminal_fresh_bundle=False,
            now=now,
        )
        if mutation.replayed:
            raise DraftStoreUnavailable
        outcome_code = _outcome_for(str(payload["disposition"]))
        audit_key = f"draft-audit:{payload['draft_id']}:{payload['version_number']}"
        audit_hash = sha256(
            {
                "occurrence_id": payload["occurrence_id"],
                "outcome_code": outcome_code,
                "content_hash": payload["content_hash"],
            }
        )
        cursor = connection.execute(
            """
            INSERT INTO audit_events (
                workspace_id, occurrence_id, idempotency_key, occurrence_kind,
                outcome_code, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                f"draft-audit:{payload['draft_id']}:{payload['version_number']}",
                audit_key,
                DRAFT_AUDIT_KIND,
                outcome_code,
                audit_hash,
                timestamp(now),
            ),
        )
        if cursor.lastrowid is None:
            raise DraftStoreUnavailable
        stored_payload = deepcopy(dict(payload))
        connection.execute(
            """
            INSERT INTO governance_draft_versions (
                draft_id, version_number, workspace_id, idempotency_key,
                request_hash, occurrence_id, content_hash, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored_payload["draft_id"],
                stored_payload["version_number"],
                workspace_id,
                idempotency_key,
                request_hash,
                stored_payload["occurrence_id"],
                stored_payload["content_hash"],
                timestamp(now),
                canonical_json(stored_payload),
            ),
        )
