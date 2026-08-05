from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from .contracts import AuditOccurrenceRequest


class AuditIdempotencyConflict(Exception):
    """The same logical key was submitted with different safe content."""


class AuditStoreUnavailable(Exception):
    """The authoritative SQLite store cannot serve the requested operation."""


@dataclass(frozen=True, slots=True)
class StoredOccurrence:
    occurrence_id: str
    event_seq: int
    replayed: bool


class AuditStore:
    """One-process SQLite writer for immutable Core occurrences."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self._database_path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                occurrence_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL UNIQUE,
                occurrence_kind TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection = connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def check_ready(self) -> bool:
        with self._lock:
            connection = self._connection
            if connection is None:
                return False
            try:
                connection.execute("SELECT 1").fetchone()
            except sqlite3.Error:
                return False
            return True

    def append_occurrence(self, request: AuditOccurrenceRequest) -> StoredOccurrence:
        with self._lock:
            connection = self._connection
            if connection is None:
                raise AuditStoreUnavailable

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

            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT occurrence_id, event_seq, content_hash
                    FROM audit_events
                    WHERE idempotency_key = ?
                    """,
                    (request.idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if existing["content_hash"] != content_hash:
                        connection.rollback()
                        raise AuditIdempotencyConflict
                    connection.commit()
                    return StoredOccurrence(
                        occurrence_id=existing["occurrence_id"],
                        event_seq=int(existing["event_seq"]),
                        replayed=True,
                    )

                occurrence_id = uuid4().hex
                created_at = datetime.now(timezone.utc).isoformat()
                cursor = connection.execute(
                    """
                    INSERT INTO audit_events (
                        occurrence_id,
                        idempotency_key,
                        occurrence_kind,
                        outcome_code,
                        content_hash,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
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
            except AuditIdempotencyConflict:
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
