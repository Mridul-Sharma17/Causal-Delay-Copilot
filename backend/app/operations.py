from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ctypes
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from .canonical import canonical_json as _canonical_json
from .canonical import sha256 as _sha256
from .canonical import timestamp as _timestamp
from .errors import SafeErrorCode, WorkspaceRequestError
from .settings import QuotaPolicy


DURABLE_OPERATION_SCHEMA_VERSION = "durable-operation.v1"

OPERATION_STATES = frozenset(
    {
        "QUEUED",
        "RUNNING",
        "CANCELLING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
        "INTERRUPTED",
        "REJECTED",
    }
)
TERMINAL_OPERATION_STATES = frozenset(
    {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "INTERRUPTED", "REJECTED"}
)
OUTSTANDING_OPERATION_STATES = frozenset({"QUEUED", "RUNNING", "CANCELLING"})
MAX_RUNNING_OPERATIONS = 1
MAX_WAITING_OPERATIONS = 2
MAX_OUTSTANDING_OPERATIONS_PER_WORKSPACE = 1

DURABLE_OPERATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS durable_operations (
        operation_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        operation_kind TEXT NOT NULL,
        state TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        request_json TEXT NOT NULL,
        artifact_dir TEXT NOT NULL,
        created_at TEXT NOT NULL,
        queued_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        cancel_requested_at TEXT,
        retry_of_operation_id TEXT,
        failure_code TEXT,
        recovery_action TEXT,
        resource_warnings_json TEXT NOT NULL,
        artifact_state TEXT NOT NULL,
        timeout_seconds REAL NOT NULL,
        thread_cap INTEGER NOT NULL,
        memory_required_bytes INTEGER NOT NULL,
        memory_available_bytes INTEGER NOT NULL,
        disk_free_bytes INTEGER NOT NULL,
        UNIQUE (workspace_id, idempotency_key),
        FOREIGN KEY (workspace_id, operation_id)
            REFERENCES workspace_operations(workspace_id, operation_id)
    )
"""
DURABLE_OPERATIONS_COLUMNS = [
    "operation_id",
    "workspace_id",
    "idempotency_key",
    "operation_kind",
    "state",
    "request_hash",
    "request_json",
    "artifact_dir",
    "created_at",
    "queued_at",
    "started_at",
    "finished_at",
    "cancel_requested_at",
    "retry_of_operation_id",
    "failure_code",
    "recovery_action",
    "resource_warnings_json",
    "artifact_state",
    "timeout_seconds",
    "thread_cap",
    "memory_required_bytes",
    "memory_available_bytes",
    "disk_free_bytes",
]


def ensure_operation_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    if create:
        connection.execute(DURABLE_OPERATIONS_TABLE)
    columns = connection.execute(
        "PRAGMA table_info(durable_operations)"
    ).fetchall()
    if [str(column[1]) for column in columns] != DURABLE_OPERATIONS_COLUMNS:
        raise sqlite3.DatabaseError(
            "durable operation schema is not the locked Core schema"
        )


def disk_free_bytes(path: Path) -> int:
    return int(shutil.disk_usage(path).free)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def available_memory_bytes() -> int | None:
    if os.name == "nt":
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys)
        except (AttributeError, OSError):
            return None
        return None

    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None
    return page_size * available_pages


@dataclass(frozen=True, slots=True)
class DurableOperation:
    operation_id: str
    workspace_id: str
    operation_kind: str
    state: str
    created_at: datetime
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None
    retry_of_operation_id: str | None
    failure_code: str | None
    recovery_action: str | None
    resource_warnings: tuple[str, ...]
    artifact_state: str
    timeout_seconds: float
    thread_cap: int
    memory_required_bytes: int
    memory_available_bytes: int
    disk_free_bytes: int
    queue_position: int | None


@dataclass(frozen=True, slots=True)
class OperationReceipt:
    operation: DurableOperation
    replayed: bool


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resource_snapshot(
    state_root: Path,
    quotas: QuotaPolicy,
    memory_required_bytes: int,
) -> tuple[int, int, tuple[str, ...]]:
    free_disk = disk_free_bytes(state_root)
    if free_disk < quotas.disk_block_bytes:
        raise WorkspaceRequestError(
            SafeErrorCode.OPERATION_DISK_SPACE_BLOCKED,
            "RESTORE_CORE_STATE_AND_RETRY",
            507,
        )

    available_memory = available_memory_bytes()
    required_with_headroom = math.ceil(
        memory_required_bytes * (1 + quotas.memory_headroom_fraction)
    )
    if available_memory is None or available_memory < required_with_headroom:
        raise WorkspaceRequestError(
            SafeErrorCode.OPERATION_MEMORY_HEADROOM_INSUFFICIENT,
            "WAIT_FOR_MEMORY_AND_RETRY",
            503,
        )
    warnings = (
        ("DISK_SPACE_LOW",)
        if free_disk < quotas.disk_warning_bytes
        else ()
    )
    return free_disk, available_memory, warnings


class DurableOperationsMixin:
    """Transactional durable operation admission on the Core SQLite writer."""

    def initialize_operations(self) -> None:
        ensure_operation_schema(self._connection_or_raise(), create=False)

    def _operation_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> DurableOperation:
        state = str(row["state"])
        if state == "QUEUED":
            queue_position = (
                int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM durable_operations
                        WHERE state = 'QUEUED'
                          AND (
                              queued_at < ? OR
                              (queued_at = ? AND operation_id <= ?)
                          )
                        """,
                        (
                            str(row["queued_at"]),
                            str(row["queued_at"]),
                            str(row["operation_id"]),
                        ),
                    ).fetchone()[0]
                )
                or 1
            )
        else:
            queue_position = None
        warnings = tuple(
            str(item)
            for item in json.loads(str(row["resource_warnings_json"]))
        )
        return DurableOperation(
            operation_id=str(row["operation_id"]),
            workspace_id=str(row["workspace_id"]),
            operation_kind=str(row["operation_kind"]),
            state=state,
            created_at=_parse_timestamp(str(row["created_at"])) or datetime.now(timezone.utc),
            queued_at=_parse_timestamp(str(row["queued_at"])) or datetime.now(timezone.utc),
            started_at=_parse_timestamp(row["started_at"]),
            finished_at=_parse_timestamp(row["finished_at"]),
            cancel_requested_at=_parse_timestamp(row["cancel_requested_at"]),
            retry_of_operation_id=(
                None
                if row["retry_of_operation_id"] is None
                else str(row["retry_of_operation_id"])
            ),
            failure_code=(None if row["failure_code"] is None else str(row["failure_code"])),
            recovery_action=(
                None
                if row["recovery_action"] is None
                else str(row["recovery_action"])
            ),
            resource_warnings=warnings,
            artifact_state=str(row["artifact_state"]),
            timeout_seconds=float(row["timeout_seconds"]),
            thread_cap=int(row["thread_cap"]),
            memory_required_bytes=int(row["memory_required_bytes"]),
            memory_available_bytes=int(row["memory_available_bytes"]),
            disk_free_bytes=int(row["disk_free_bytes"]),
            queue_position=queue_position,
        )

    def _operation_row_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM durable_operations WHERE workspace_id = ? AND operation_id = ?",
            (workspace_id, operation_id),
        ).fetchone()

    def admit_operation(
        self,
        workspace_id: str,
        *,
        operation_kind: str,
        idempotency_key: str,
        request: Mapping[str, Any],
        memory_required_bytes: int,
        state_root: Path,
        now: datetime | None = None,
        retry_of_operation_id: str | None = None,
    ) -> OperationReceipt:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        request_json = _canonical_json(
            {
                "operation_kind": operation_kind,
                "memory_required_bytes": memory_required_bytes,
                "request": dict(request),
            }
        )
        request_hash = _sha256(request_json)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT * FROM durable_operations
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if str(existing["request_hash"]) != request_hash:
                        raise WorkspaceRequestError(
                            SafeErrorCode.DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT,
                            "USE_NEW_IDEMPOTENCY_KEY",
                            409,
                        )
                    operation = self._operation_from_row(connection, existing)
                    connection.commit()
                    return OperationReceipt(operation=operation, replayed=True)

                self._active_row_locked(workspace_id, current_time)
                free_disk, available_memory, resource_warnings = _resource_snapshot(
                    state_root,
                    self._quotas,
                    memory_required_bytes,
                )
                outstanding_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM durable_operations
                        WHERE state IN ('QUEUED', 'RUNNING', 'CANCELLING')
                        """
                    ).fetchone()[0]
                )
                if outstanding_count >= (
                    min(MAX_RUNNING_OPERATIONS, self._quotas.max_running_operations)
                    + min(MAX_WAITING_OPERATIONS, self._quotas.max_waiting_operations)
                ):
                    raise WorkspaceRequestError(
                        SafeErrorCode.OPERATION_QUEUE_CAPACITY_REACHED,
                        "WAIT_FOR_AN_OPERATION_TO_FINISH",
                        429,
                    )

                workspace_outstanding = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM durable_operations
                        WHERE workspace_id = ? AND state IN ('QUEUED', 'RUNNING', 'CANCELLING')
                        """,
                        (workspace_id,),
                    ).fetchone()[0]
                )
                if (
                    workspace_outstanding
                    >= min(
                        MAX_OUTSTANDING_OPERATIONS_PER_WORKSPACE,
                        self._quotas.max_outstanding_operations_per_workspace,
                    )
                ):
                    raise WorkspaceRequestError(
                        SafeErrorCode.DEMO_WORKSPACE_OPERATION_LIMIT_REACHED,
                        "WAIT_FOR_THIS_OPERATION_TO_FINISH_OR_RETRY_LATER",
                        429,
                    )

                operation_id = f"operation-{uuid4()}"
                timestamp = _timestamp(current_time)
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="DURABLE_OPERATION",
                    content_hash=request_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    raise sqlite3.DatabaseError(
                        "durable operation mutation has no matching operation"
                    )
                connection.execute(
                    """
                    INSERT INTO workspace_operations (
                        operation_id, workspace_id, operation_kind, status, created_at
                    ) VALUES (?, ?, ?, 'QUEUED', ?)
                    """,
                    (operation_id, workspace_id, operation_kind, timestamp),
                )
                connection.execute(
                    """
                    INSERT INTO durable_operations (
                        operation_id, workspace_id, idempotency_key, operation_kind,
                        state, request_hash, request_json, artifact_dir, created_at,
                        queued_at, retry_of_operation_id, resource_warnings_json,
                        artifact_state, timeout_seconds, thread_cap,
                        memory_required_bytes, memory_available_bytes, disk_free_bytes
                    ) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?, ?, ?,
                              'NOT_STARTED', ?, 1, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        workspace_id,
                        idempotency_key,
                        operation_kind,
                        request_hash,
                        request_json,
                        f"temporary/{operation_id}",
                        timestamp,
                        timestamp,
                        retry_of_operation_id,
                        _canonical_json(list(resource_warnings)),
                        self._quotas.compute_timeout_seconds,
                        memory_required_bytes,
                        available_memory,
                        free_disk,
                    ),
                )
                stored = self._operation_row_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                )
                if stored is None:
                    raise sqlite3.DatabaseError("durable operation insert was not readable")
                connection.commit()
                return OperationReceipt(
                    operation=self._operation_from_row(connection, stored),
                    replayed=False,
                )
            except Exception:
                connection.rollback()
                raise

    def get_operation(
        self,
        workspace_id: str,
        operation_id: str,
    ) -> DurableOperation | None:
        with self._lock:
            connection = self._connection_or_raise()
            row = self._operation_row_locked(
                connection,
                workspace_id=workspace_id,
                operation_id=operation_id,
            )
            return None if row is None else self._operation_from_row(connection, row)

    def claim_next_operation(self, *, now: datetime | None = None) -> DurableOperation | None:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                running_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM durable_operations
                        WHERE state IN ('RUNNING', 'CANCELLING')
                        """
                    ).fetchone()[0]
                )
                if running_count >= min(
                    MAX_RUNNING_OPERATIONS,
                    self._quotas.max_running_operations,
                ):
                    connection.rollback()
                    return None
                row = connection.execute(
                    """
                    SELECT * FROM durable_operations
                    WHERE state = 'QUEUED'
                    ORDER BY queued_at, operation_id
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                timestamp = _timestamp(current_time)
                connection.execute(
                    """
                    UPDATE durable_operations
                    SET state = 'RUNNING', started_at = ?, artifact_state = 'EXECUTING'
                    WHERE operation_id = ? AND state = 'QUEUED'
                    """,
                    (timestamp, str(row["operation_id"])),
                )
                connection.execute(
                    """
                    UPDATE workspace_operations
                    SET status = ?
                    WHERE workspace_id = ? AND operation_id = ?
                    """,
                    ("RUNNING", str(row["workspace_id"]), str(row["operation_id"])),
                )
                updated = self._operation_row_locked(
                    connection,
                    workspace_id=str(row["workspace_id"]),
                    operation_id=str(row["operation_id"]),
                )
                if updated is None:
                    raise sqlite3.DatabaseError("claimed operation was not readable")
                connection.commit()
                return self._operation_from_row(connection, updated)
            except Exception:
                connection.rollback()
                raise

    def cancel_operation(
        self,
        workspace_id: str,
        operation_id: str,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> OperationReceipt | None:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        action_hash = _sha256({"operation_id": operation_id, "action": "CANCEL"})
        mutation_key = f"operation-cancel:{idempotency_key}"
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._operation_row_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                )
                if row is None:
                    connection.rollback()
                    return None
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=mutation_key,
                    mutation_kind="OPERATION_CANCEL",
                    content_hash=action_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    current = self._operation_row_locked(
                        connection,
                        workspace_id=workspace_id,
                        operation_id=operation_id,
                    )
                    if current is None:
                        raise sqlite3.DatabaseError(
                            "cancel mutation has no operation row"
                        )
                    connection.commit()
                    return OperationReceipt(
                        operation=self._operation_from_row(connection, current),
                        replayed=True,
                    )

                state = str(row["state"])
                timestamp = _timestamp(current_time)
                if state == "QUEUED":
                    connection.execute(
                        """
                        UPDATE durable_operations
                        SET state = 'CANCELLED', finished_at = ?,
                            failure_code = 'OPERATION_CANCELLED',
                            recovery_action = 'EXPLICIT_RETRY_AS_NEW_OPERATION',
                            artifact_state = 'NOT_STARTED'
                        WHERE workspace_id = ? AND operation_id = ?
                        """,
                        (timestamp, workspace_id, operation_id),
                    )
                    connection.execute(
                        """
                        UPDATE workspace_operations
                        SET status = 'TERMINAL', finished_at = ?
                        WHERE workspace_id = ? AND operation_id = ?
                        """,
                        (timestamp, workspace_id, operation_id),
                    )
                elif state == "RUNNING":
                    connection.execute(
                        """
                        UPDATE durable_operations
                        SET state = 'CANCELLING', cancel_requested_at = ?
                        WHERE workspace_id = ? AND operation_id = ?
                        """,
                        (timestamp, workspace_id, operation_id),
                    )
                    connection.execute(
                        """
                        UPDATE workspace_operations
                        SET status = 'CANCELLING'
                        WHERE workspace_id = ? AND operation_id = ?
                        """,
                        (workspace_id, operation_id),
                    )
                current = self._operation_row_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                )
                if current is None:
                    raise sqlite3.DatabaseError("cancelled operation was not readable")
                connection.commit()
                return OperationReceipt(
                    operation=self._operation_from_row(connection, current),
                    replayed=False,
                )
            except Exception:
                connection.rollback()
                raise

    def retry_operation(
        self,
        workspace_id: str,
        operation_id: str,
        *,
        idempotency_key: str,
        state_root: Path,
        now: datetime | None = None,
    ) -> OperationReceipt | None:
        current_time = _as_utc(now or datetime.now(timezone.utc))
        mutation_key = f"operation-retry:{idempotency_key}"
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                old = self._operation_row_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                )
                if old is None:
                    connection.rollback()
                    return None
                existing = connection.execute(
                    """
                    SELECT * FROM durable_operations
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, mutation_key),
                ).fetchone()
                if existing is not None:
                    if str(existing["retry_of_operation_id"]) != operation_id:
                        raise WorkspaceRequestError(
                            SafeErrorCode.DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT,
                            "USE_NEW_IDEMPOTENCY_KEY",
                            409,
                        )
                    connection.commit()
                    return OperationReceipt(
                        operation=self._operation_from_row(connection, existing),
                        replayed=True,
                    )
                old_state = str(old["state"])
                if old_state not in {"INTERRUPTED", "FAILED", "TIMED_OUT", "CANCELLED"}:
                    raise WorkspaceRequestError(
                        SafeErrorCode.OPERATION_NOT_RETRYABLE,
                        "WAIT_FOR_A_TERMINAL_OPERATION_STATE",
                        409,
                    )

                request_json = str(old["request_json"])
                request_payload = json.loads(request_json)
                request_hash = str(old["request_hash"])
                free_disk, available_memory, resource_warnings = _resource_snapshot(
                    state_root,
                    self._quotas,
                    int(old["memory_required_bytes"]),
                )
                outstanding_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM durable_operations
                        WHERE state IN ('QUEUED', 'RUNNING', 'CANCELLING')
                        """
                    ).fetchone()[0]
                )
                if outstanding_count >= (
                    min(MAX_RUNNING_OPERATIONS, self._quotas.max_running_operations)
                    + min(MAX_WAITING_OPERATIONS, self._quotas.max_waiting_operations)
                ):
                    raise WorkspaceRequestError(
                        SafeErrorCode.OPERATION_QUEUE_CAPACITY_REACHED,
                        "WAIT_FOR_AN_OPERATION_TO_FINISH",
                        429,
                    )
                workspace_outstanding = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM durable_operations
                        WHERE workspace_id = ? AND state IN ('QUEUED', 'RUNNING', 'CANCELLING')
                        """,
                        (workspace_id,),
                    ).fetchone()[0]
                )
                if workspace_outstanding >= min(
                    MAX_OUTSTANDING_OPERATIONS_PER_WORKSPACE,
                    self._quotas.max_outstanding_operations_per_workspace,
                ):
                    raise WorkspaceRequestError(
                        SafeErrorCode.DEMO_WORKSPACE_OPERATION_LIMIT_REACHED,
                        "WAIT_FOR_THIS_OPERATION_TO_FINISH_OR_RETRY_LATER",
                        429,
                    )
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=mutation_key,
                    mutation_kind="OPERATION_RETRY",
                    content_hash=_sha256(
                        {"operation_id": operation_id, "action": "RETRY"}
                    ),
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    raise sqlite3.DatabaseError(
                        "retry mutation has no matching operation"
                    )
                operation_id = f"operation-{uuid4()}"
                timestamp = _timestamp(current_time)
                connection.execute(
                    """
                    INSERT INTO workspace_operations (
                        operation_id, workspace_id, operation_kind, status, created_at
                    ) VALUES (?, ?, ?, 'QUEUED', ?)
                    """,
                    (
                        operation_id,
                        workspace_id,
                        str(old["operation_kind"]),
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO durable_operations (
                        operation_id, workspace_id, idempotency_key, operation_kind,
                        state, request_hash, request_json, artifact_dir, created_at,
                        queued_at, retry_of_operation_id, resource_warnings_json,
                        artifact_state, timeout_seconds, thread_cap,
                        memory_required_bytes, memory_available_bytes, disk_free_bytes
                    ) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?, ?, ?,
                              'NOT_STARTED', ?, 1, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        workspace_id,
                        mutation_key,
                        str(old["operation_kind"]),
                        request_hash,
                        request_json,
                        f"temporary/{operation_id}",
                        timestamp,
                        timestamp,
                        str(old["operation_id"]),
                        _canonical_json(list(resource_warnings)),
                        self._quotas.compute_timeout_seconds,
                        int(request_payload["memory_required_bytes"]),
                        available_memory,
                        free_disk,
                    ),
                )
                new_row = self._operation_row_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                )
                if new_row is None:
                    raise sqlite3.DatabaseError("retry operation was not readable")
                connection.commit()
                return OperationReceipt(
                    operation=self._operation_from_row(connection, new_row),
                    replayed=False,
                )
            except Exception:
                connection.rollback()
                raise

    def finish_operation(
        self,
        operation_id: str,
        *,
        state: str,
        failure_code: str | None = None,
        recovery_action: str | None = None,
        artifact_state: str,
        expected_state: str | None = None,
        now: datetime | None = None,
    ) -> DurableOperation | None:
        if state not in TERMINAL_OPERATION_STATES:
            raise ValueError("only terminal operation states can be recorded")
        current_time = _as_utc(now or datetime.now(timezone.utc))
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM durable_operations WHERE operation_id = ?",
                    (operation_id,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                if str(row["state"]) in TERMINAL_OPERATION_STATES:
                    connection.commit()
                    return self._operation_from_row(connection, row)
                if expected_state is not None and str(row["state"]) != expected_state:
                    connection.commit()
                    return self._operation_from_row(connection, row)
                timestamp = _timestamp(current_time)
                connection.execute(
                    """
                    UPDATE durable_operations
                    SET state = ?, finished_at = ?, failure_code = ?,
                        recovery_action = ?, artifact_state = ?
                    WHERE operation_id = ?
                    """,
                    (
                        state,
                        timestamp,
                        failure_code,
                        recovery_action,
                        artifact_state,
                        operation_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE workspace_operations
                    SET status = 'TERMINAL', finished_at = ?
                    WHERE operation_id = ?
                    """,
                    (timestamp, operation_id),
                )
                updated = connection.execute(
                    "SELECT * FROM durable_operations WHERE operation_id = ?",
                    (operation_id,),
                ).fetchone()
                if updated is None:
                    raise sqlite3.DatabaseError("finished operation was not readable")
                connection.commit()
                return self._operation_from_row(connection, updated)
            except Exception:
                connection.rollback()
                raise

    def operation_is_cancelling(self, operation_id: str) -> bool:
        with self._lock:
            row = self._connection_or_raise().execute(
                "SELECT state FROM durable_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        return row is not None and str(row["state"]) in {"CANCELLING", "CANCELLED"}

    def recover_interrupted_operations(self, layout: Any) -> list[str]:
        with self._lock:
            connection = self._connection_or_raise()
            rows = connection.execute(
                """
                SELECT operation_id FROM durable_operations
                WHERE state IN ('RUNNING', 'CANCELLING')
                ORDER BY operation_id
                """
            ).fetchall()
        recovered: list[str] = []
        for row in rows:
            operation_id = str(row["operation_id"])
            _quarantine_operation_material(
                layout,
                operation_id,
                reason_code="RUN_EXECUTION_INTERRUPTED",
            )
            self.finish_operation(
                operation_id,
                state="INTERRUPTED",
                failure_code="RUN_EXECUTION_INTERRUPTED",
                recovery_action="EXPLICIT_RETRY_AS_NEW_OPERATION",
                artifact_state="QUARANTINED",
            )
            recovered.append(operation_id)
        return recovered


def _write_json_durable(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(payload))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _quarantine_operation_material(
    layout: Any,
    operation_id: str,
    *,
    reason_code: str,
) -> None:
    temporary_root = layout.temporary_root / operation_id
    published_root = layout.run_root / operation_id
    quarantine_root = layout.quarantine_root / operation_id
    if quarantine_root.exists():
        if not quarantine_root.is_dir():
            raise OSError("operation quarantine target is not a directory")
        if temporary_root.exists():
            temporary_target = quarantine_root / "temporary"
            if temporary_target.exists():
                raise OSError("operation temporary quarantine target already exists")
            os.replace(temporary_root, temporary_target)
        if published_root.exists():
            published_target = quarantine_root / "published"
            if published_target.exists():
                raise OSError("operation published quarantine target already exists")
            os.replace(published_root, published_target)
    else:
        quarantine_root.parent.mkdir(parents=True, exist_ok=True)
        if temporary_root.exists() and not published_root.exists():
            os.replace(temporary_root, quarantine_root)
        elif published_root.exists() and not temporary_root.exists():
            os.replace(published_root, quarantine_root)
        else:
            quarantine_root.mkdir()
            if temporary_root.exists():
                os.replace(temporary_root, quarantine_root / "temporary")
            if published_root.exists():
                os.replace(published_root, quarantine_root / "published")
    _write_json_durable(
        quarantine_root / "quarantine-manifest.json",
        {
            "schema_version": "analysis-run-quarantine-manifest.v1",
            "operation_id": operation_id,
            "reason_code": reason_code,
            "cleanup_eligible": True,
        },
    )


class OperationRunner:
    """One durable queue claimant and one bounded compute subprocess."""

    _THREAD_ENVIRONMENT = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    )

    def __init__(
        self,
        store: DurableOperationsMixin,
        layout: Any,
        *,
        worker_command_factory: Callable[[DurableOperation, Path], list[str]] | None = None,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self._store = store
        self._layout = layout
        self._worker_command_factory = worker_command_factory or self._default_worker_command
        self._poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="core-operation-runner",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _default_worker_command(
        self,
        operation: DurableOperation,
        temporary_root: Path,
    ) -> list[str]:
        return [
            sys.executable,
            "-m",
            "backend.app.operation_worker",
            operation.operation_kind,
            str(temporary_root),
        ]

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            operation = self._store.claim_next_operation()
            if operation is None:
                self._stop_event.wait(self._poll_interval_seconds)
                continue
            try:
                self._execute(operation)
            except Exception:
                self._store.finish_operation(
                    operation.operation_id,
                    state="FAILED",
                    failure_code="OPERATION_RUNNER_FAILED",
                    recovery_action="RESTORE_CORE_STATE_AND_RETRY",
                    artifact_state="QUARANTINE_UNAVAILABLE",
                )

    def _execute(self, operation: DurableOperation) -> None:
        temporary_root = self._layout.temporary_root / operation.operation_id
        process: subprocess.Popen[bytes] | None = None
        terminal_state: str | None = None
        try:
            temporary_root.mkdir(parents=True, exist_ok=True)
            _write_json_durable(
                temporary_root / "executing.json",
                {
                    "schema_version": "durable-operation-executing.v1",
                    "operation_id": operation.operation_id,
                    "thread_cap": operation.thread_cap,
                },
            )
            environment = os.environ.copy()
            for variable in self._THREAD_ENVIRONMENT:
                environment[variable] = "1"
            environment["PYTHONHASHSEED"] = "0"
            process = subprocess.Popen(
                self._worker_command_factory(operation, temporary_root),
                cwd=str(Path(__file__).resolve().parents[2]),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + operation.timeout_seconds
            while process.poll() is None:
                if self._stop_event.is_set():
                    terminal_state = "INTERRUPTED"
                    self._terminate(process)
                    break
                if self._store.operation_is_cancelling(operation.operation_id):
                    terminal_state = "CANCELLED"
                    self._terminate(process)
                    break
                if time.monotonic() >= deadline:
                    terminal_state = "TIMED_OUT"
                    self._terminate(process)
                    break
                time.sleep(self._poll_interval_seconds)
            return_code = process.poll()
            if terminal_state is None:
                terminal_state = (
                    "CANCELLED"
                    if self._store.operation_is_cancelling(operation.operation_id)
                    else "SUCCEEDED"
                    if return_code == 0
                    else "FAILED"
                )
            if terminal_state == "SUCCEEDED":
                self._publish_success(operation, temporary_root)
                completed = self._store.finish_operation(
                    operation.operation_id,
                    state="SUCCEEDED",
                    artifact_state="PUBLISHED",
                    expected_state="RUNNING",
                )
                if completed is not None and completed.state == "SUCCEEDED":
                    return
                terminal_state = "CANCELLED"
            reason_code = (
                "RUN_EXECUTION_INTERRUPTED"
                if terminal_state == "INTERRUPTED"
                else "OPERATION_CANCELLED"
                if terminal_state == "CANCELLED"
                else "OPERATION_TIMEOUT"
                if terminal_state == "TIMED_OUT"
                else "OPERATION_WORKER_FAILED"
            )
            self._quarantine_and_finish(
                operation,
                state=terminal_state,
                reason_code=reason_code,
                failure_code=reason_code,
            )
        except Exception:
            if process is not None and process.poll() is None:
                self._terminate(process)
            self._quarantine_and_finish(
                operation,
                state="FAILED",
                reason_code="OPERATION_RUNNER_FAILED",
                failure_code="OPERATION_RUNNER_FAILED",
            )

    def _quarantine_and_finish(
        self,
        operation: DurableOperation,
        *,
        state: str,
        reason_code: str,
        failure_code: str,
    ) -> None:
        try:
            _quarantine_operation_material(
                self._layout,
                operation.operation_id,
                reason_code=reason_code,
            )
        except Exception:
            self._store.finish_operation(
                operation.operation_id,
                state=state,
                failure_code="OPERATION_ARTIFACT_QUARANTINE_FAILED",
                recovery_action="RESTORE_CORE_STATE_AND_RETRY",
                artifact_state="QUARANTINE_UNAVAILABLE",
            )
            return
        self._store.finish_operation(
            operation.operation_id,
            state=state,
            failure_code=failure_code,
            recovery_action="EXPLICIT_RETRY_AS_NEW_OPERATION",
            artifact_state="QUARANTINED",
        )

    def _publish_success(self, operation: DurableOperation, temporary_root: Path) -> None:
        _write_json_durable(
            temporary_root / "operation-result.json",
            {
                "schema_version": "durable-operation-result.v1",
                "operation_id": operation.operation_id,
                "operation_kind": operation.operation_kind,
            },
        )
        destination = self._layout.run_root / operation.operation_id
        if destination.exists():
            raise OSError("operation result already exists")
        os.replace(temporary_root, destination)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
