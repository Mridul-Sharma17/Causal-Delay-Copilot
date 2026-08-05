from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .contracts import AuditOccurrenceRequest
from .settings import QuotaPolicy
from .workspace import (
    WorkspaceStore,
    ensure_workspace_schema,
)


AUDIT_EVENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS audit_events (
        event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        occurrence_id TEXT NOT NULL UNIQUE,
        idempotency_key TEXT NOT NULL,
        occurrence_kind TEXT NOT NULL,
        outcome_code TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (workspace_id, idempotency_key)
    )
"""
AUDIT_EVENTS_COLUMNS = [
    "event_seq",
    "workspace_id",
    "occurrence_id",
    "idempotency_key",
    "occurrence_kind",
    "outcome_code",
    "content_hash",
    "created_at",
]


def ensure_audit_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    if create:
        ensure_workspace_schema(connection, create=True)
        connection.execute(AUDIT_EVENTS_TABLE)
    columns = connection.execute("PRAGMA table_info(audit_events)").fetchall()
    if [str(column[1]) for column in columns] != AUDIT_EVENTS_COLUMNS:
        raise sqlite3.DatabaseError("audit schema is not the locked Core schema")


class AuditIdempotencyConflict(Exception):
    """The same logical audit key was submitted with different safe content."""


class AuditStoreUnavailable(Exception):
    """The authoritative SQLite store cannot serve the requested operation."""


@dataclass(frozen=True, slots=True)
class StoredOccurrence:
    occurrence_id: str
    event_seq: int
    replayed: bool


@dataclass(frozen=True, slots=True)
class AuditOccurrenceView:
    occurrence_id: str
    event_seq: int
    occurrence_kind: str
    outcome_code: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredValidatedReference:
    reference_id: str
    bundle_ref: str
    validation_attestation_ref: str
    release_candidate_id: str


def _occurrence_view(row: sqlite3.Row) -> AuditOccurrenceView:
    return AuditOccurrenceView(
        occurrence_id=str(row["occurrence_id"]),
        event_seq=int(row["event_seq"]),
        occurrence_kind=str(row["occurrence_kind"]),
        outcome_code=str(row["outcome_code"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _validated_reference(row: sqlite3.Row) -> StoredValidatedReference:
    return StoredValidatedReference(
        reference_id=str(row["reference_id"]),
        bundle_ref=str(row["bundle_ref"]),
        validation_attestation_ref=str(row["validation_attestation_ref"]),
        release_candidate_id=str(row["release_candidate_id"]),
    )


class AuditStore(WorkspaceStore):
    """One-process SQLite writer for workspace-scoped Core occurrences."""

    def __init__(
        self,
        database_path: Path,
        *,
        release_candidate_id: str = "local-default",
        quotas: QuotaPolicy | None = None,
    ) -> None:
        super().__init__(
            database_path,
            release_candidate_id=release_candidate_id,
            quotas=quotas or QuotaPolicy(),
        )

    def initialize(self) -> None:
        try:
            super().initialize()
            connection = self._connection_or_raise()
            ensure_audit_schema(connection, create=False)
        except sqlite3.Error as error:
            self.close()
            raise AuditStoreUnavailable from error

    def append_occurrence(
        self,
        request: AuditOccurrenceRequest,
        workspace_id: str,
        *,
        now: datetime | None = None,
    ) -> StoredOccurrence:
        current_time = now or datetime.now(timezone.utc)
        content = {
            "occurrence_kind": request.occurrence_kind,
            "outcome_code": request.outcome_code,
        }
        content_hash = hashlib.sha256(
            json.dumps(
                content,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT occurrence_id, event_seq, content_hash
                    FROM audit_events
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, request.idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing["content_hash"] != content_hash:
                        connection.rollback()
                        raise AuditIdempotencyConflict
                    connection.commit()
                    return StoredOccurrence(
                        occurrence_id=str(existing["occurrence_id"]),
                        event_seq=int(existing["event_seq"]),
                        replayed=True,
                    )

                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=request.idempotency_key,
                    mutation_kind=request.occurrence_kind,
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    raise AuditStoreUnavailable

                occurrence_id = uuid4().hex
                created_at = current_time.astimezone(timezone.utc).isoformat()
                cursor = connection.execute(
                    """
                    INSERT INTO audit_events (
                        workspace_id,
                        occurrence_id,
                        idempotency_key,
                        occurrence_kind,
                        outcome_code,
                        content_hash,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        occurrence_id,
                        request.idempotency_key,
                        request.occurrence_kind,
                        request.outcome_code,
                        content_hash,
                        created_at,
                    ),
                )
                connection.commit()
                if cursor.lastrowid is None:
                    raise AuditStoreUnavailable
                return StoredOccurrence(
                    occurrence_id=occurrence_id,
                    event_seq=int(cursor.lastrowid),
                    replayed=False,
                )
            except (AuditIdempotencyConflict, AuditStoreUnavailable):
                connection.rollback()
                raise
            except Exception as error:
                connection.rollback()
                if isinstance(error, sqlite3.Error):
                    raise AuditStoreUnavailable from error
                raise

    def list_occurrences(self, workspace_id: str) -> list[AuditOccurrenceView]:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                rows = connection.execute(
                    """
                    SELECT occurrence_id, event_seq, occurrence_kind, outcome_code, created_at
                    FROM audit_events
                    WHERE workspace_id = ?
                    ORDER BY event_seq
                    """,
                    (workspace_id,),
                ).fetchall()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        return [_occurrence_view(row) for row in rows]

    def get_occurrence(
        self,
        workspace_id: str,
        occurrence_id: str,
    ) -> AuditOccurrenceView | None:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                row = connection.execute(
                    """
                    SELECT occurrence_id, event_seq, occurrence_kind, outcome_code, created_at
                    FROM audit_events
                    WHERE occurrence_id = ? AND workspace_id = ?
                    """,
                    (occurrence_id, workspace_id),
                ).fetchone()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        if row is None:
            return None
        return _occurrence_view(row)

    def list_validated_references(self) -> list[StoredValidatedReference]:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                rows = connection.execute(
                    """
                    SELECT reference_id, bundle_ref, validation_attestation_ref,
                           release_candidate_id
                    FROM validated_references
                    WHERE release_candidate_id = ?
                    ORDER BY reference_id
                    """,
                    (self._release_candidate_id,),
                ).fetchall()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        return [_validated_reference(row) for row in rows]

    def get_validated_reference(
        self,
        reference_id: str,
    ) -> StoredValidatedReference | None:
        with self._lock:
            connection = self._connection_or_raise()
            try:
                row = connection.execute(
                    """
                    SELECT reference_id, bundle_ref, validation_attestation_ref,
                           release_candidate_id
                    FROM validated_references
                    WHERE reference_id = ? AND release_candidate_id = ?
                    """,
                    (reference_id, self._release_candidate_id),
                ).fetchone()
            except sqlite3.Error as error:
                raise AuditStoreUnavailable from error
        if row is None:
            return None
        return _validated_reference(row)
