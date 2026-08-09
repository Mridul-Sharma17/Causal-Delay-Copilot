from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from threading import RLock
from typing import Callable
from uuid import uuid4

from .canonical import timestamp as _timestamp
from .errors import SafeErrorCode, WorkspaceRequestError
from .settings import QuotaPolicy


DEMO_WORKSPACE_COOKIE_NAME = "core_demo_workspace"
DEMO_WORKSPACE_CAPABILITY_BYTES = 32
DEMO_WORKSPACE_SCHEMA_VERSION = "demo-workspace.v1"

DEMO_WORKSPACES_TABLE = """
    CREATE TABLE IF NOT EXISTS demo_workspaces (
        workspace_id TEXT PRIMARY KEY,
        capability_digest TEXT NOT NULL UNIQUE,
        release_candidate_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        retired_at TEXT,
        mutation_count INTEGER NOT NULL DEFAULT 0,
        terminal_fresh_bundle_count INTEGER NOT NULL DEFAULT 0
    )
"""
DEMO_WORKSPACES_COLUMNS = [
    "workspace_id",
    "capability_digest",
    "release_candidate_id",
    "created_at",
    "last_seen_at",
    "retired_at",
    "mutation_count",
    "terminal_fresh_bundle_count",
]

DEMO_WORKSPACE_MUTATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS demo_workspace_mutations (
        mutation_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        mutation_kind TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        terminal_fresh_bundle INTEGER NOT NULL DEFAULT 0 CHECK (
            terminal_fresh_bundle IN (0, 1)
        ),
        UNIQUE (workspace_id, idempotency_key)
    )
"""
DEMO_WORKSPACE_MUTATIONS_COLUMNS = [
    "mutation_id",
    "workspace_id",
    "idempotency_key",
    "mutation_kind",
    "content_hash",
    "occurred_at",
    "terminal_fresh_bundle",
]

WORKSPACE_ARTIFACTS_TABLE = """
    CREATE TABLE IF NOT EXISTS workspace_artifacts (
        artifact_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        artifact_ref TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
"""
WORKSPACE_ARTIFACTS_COLUMNS = [
    "artifact_id",
    "workspace_id",
    "artifact_ref",
    "created_at",
]

WORKSPACE_OPERATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS workspace_operations (
        operation_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        operation_kind TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        finished_at TEXT,
        UNIQUE (workspace_id, operation_id)
    )
"""
WORKSPACE_OPERATIONS_COLUMNS = [
    "operation_id",
    "workspace_id",
    "operation_kind",
    "status",
    "created_at",
    "finished_at",
]

WORKSPACE_SELECTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS workspace_selections (
        selection_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        reference_id TEXT NOT NULL,
        selected_at TEXT NOT NULL
    )
"""
WORKSPACE_SELECTIONS_COLUMNS = [
    "selection_id",
    "workspace_id",
    "reference_id",
    "selected_at",
]

WORKSPACE_RESULTS_TABLE = """
    CREATE TABLE IF NOT EXISTS workspace_results (
        result_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        operation_id TEXT NOT NULL,
        result_ref TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id, operation_id)
            REFERENCES workspace_operations(workspace_id, operation_id)
    )
"""
WORKSPACE_RESULTS_COLUMNS = [
    "result_id",
    "workspace_id",
    "operation_id",
    "result_ref",
    "created_at",
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
        raise sqlite3.DatabaseError(f"{table_name} schema is not the locked Core schema")


def ensure_workspace_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    """Create or validate every workspace-owned persistence partition."""

    _ensure_table(
        connection,
        "demo_workspaces",
        DEMO_WORKSPACES_TABLE,
        DEMO_WORKSPACES_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "demo_workspace_mutations",
        DEMO_WORKSPACE_MUTATIONS_TABLE,
        DEMO_WORKSPACE_MUTATIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "workspace_artifacts",
        WORKSPACE_ARTIFACTS_TABLE,
        WORKSPACE_ARTIFACTS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "workspace_operations",
        WORKSPACE_OPERATIONS_TABLE,
        WORKSPACE_OPERATIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "workspace_selections",
        WORKSPACE_SELECTIONS_TABLE,
        WORKSPACE_SELECTIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "workspace_results",
        WORKSPACE_RESULTS_TABLE,
        WORKSPACE_RESULTS_COLUMNS,
        create=create,
    )


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    workspace_id: str
    release_candidate_id: str
    created_at: datetime
    last_seen_at: datetime
    mutation_count: int
    terminal_fresh_bundle_count: int


@dataclass(frozen=True, slots=True)
class WorkspaceResolution:
    snapshot: WorkspaceSnapshot
    new_capability: str | None


@dataclass(frozen=True, slots=True)
class MutationReceipt:
    mutation_id: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class WorkspaceSelectionView:
    selection_id: str
    reference_id: str
    selected_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceResultView:
    result_id: str
    operation_id: str
    result_ref: str
    created_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value))


def _capability_digest(capability: str) -> str:
    return hashlib.sha256(capability.encode("utf-8")).hexdigest()


def _owned_content_hash(*values: str) -> str:
    return hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _new_capability() -> str:
    raw = secrets.token_bytes(DEMO_WORKSPACE_CAPABILITY_BYTES)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class WorkspaceStore:
    """One SQLite-writer boundary for anonymous Demo Workspace state."""

    def __init__(
        self,
        database_path: Path,
        *,
        release_candidate_id: str,
        quotas: QuotaPolicy,
    ) -> None:
        self._database_path = database_path
        self._release_candidate_id = release_candidate_id
        self._quotas = quotas
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    @property
    def quotas(self) -> QuotaPolicy:
        return self._quotas

    def initialize(self) -> None:
        if not self._database_path.is_file():
            raise sqlite3.DatabaseError("Core database is not initialized")
        try:
            connection = sqlite3.connect(
                self._database_path,
                timeout=5.0,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            ensure_workspace_schema(connection, create=False)
        except sqlite3.Error:
            try:
                connection.close()
            except UnboundLocalError:
                pass
            raise
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

    def _connection_or_raise(self) -> sqlite3.Connection:
        connection = self._connection
        if connection is None:
            raise sqlite3.DatabaseError("workspace store is unavailable")
        return connection

    def _snapshot(self, row: sqlite3.Row) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(
            workspace_id=str(row["workspace_id"]),
            release_candidate_id=str(row["release_candidate_id"]),
            created_at=_parse_timestamp(str(row["created_at"])),
            last_seen_at=_parse_timestamp(str(row["last_seen_at"])),
            mutation_count=int(row["mutation_count"]),
            terminal_fresh_bundle_count=int(row["terminal_fresh_bundle_count"]),
        )

    def _access_error(self) -> WorkspaceRequestError:
        return WorkspaceRequestError(
            SafeErrorCode.DEMO_WORKSPACE_UNAVAILABLE,
            "START_A_NEW_DEMO_WORKSPACE",
            403,
        )

    def _active_row_locked(
        self,
        workspace_id: str,
        now: datetime,
        *,
        retire_expired: bool = True,
    ) -> sqlite3.Row:
        connection = self._connection_or_raise()
        row = connection.execute(
            "SELECT * FROM demo_workspaces WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if row is None:
            raise self._access_error()
        if str(row["release_candidate_id"]) != self._release_candidate_id:
            raise self._access_error()
        if row["retired_at"] is not None:
            raise self._access_error()
        if _as_utc(now) - _parse_timestamp(str(row["last_seen_at"])) >= timedelta(
            days=self._quotas.workspace_inactive_days
        ):
            if retire_expired:
                connection.execute(
                    "UPDATE demo_workspaces SET retired_at = ? WHERE workspace_id = ?",
                    (_timestamp(now), workspace_id),
                )
                connection.commit()
            raise self._access_error()
        return row

    def resolve_workspace(
        self,
        capability: str | None,
        *,
        now: datetime | None = None,
    ) -> WorkspaceResolution:
        """Resolve the cookie digest or issue one new release-bound capability."""

        current_time = _as_utc(now or _utc_now())
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                if capability is None:
                    stale_cutoff = _timestamp(
                        current_time
                        - timedelta(days=self._quotas.workspace_inactive_days)
                    )
                    connection.execute(
                        """
                        UPDATE demo_workspaces
                        SET retired_at = ?
                        WHERE retired_at IS NULL AND last_seen_at <= ?
                        """,
                        (_timestamp(current_time), stale_cutoff),
                    )
                    active_count = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM demo_workspaces WHERE retired_at IS NULL"
                        ).fetchone()[0]
                    )
                    if active_count >= self._quotas.max_workspaces:
                        connection.rollback()
                        raise WorkspaceRequestError(
                            SafeErrorCode.DEMO_WORKSPACE_CAPACITY_EXCEEDED,
                            "TRY_AGAIN_LATER",
                            429,
                        )
                    issued_capability = _new_capability()
                    workspace_id = uuid4().hex
                    timestamp = _timestamp(current_time)
                    connection.execute(
                        """
                        INSERT INTO demo_workspaces (
                            workspace_id,
                            capability_digest,
                            release_candidate_id,
                            created_at,
                            last_seen_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            workspace_id,
                            _capability_digest(issued_capability),
                            self._release_candidate_id,
                            timestamp,
                            timestamp,
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM demo_workspaces WHERE workspace_id = ?",
                        (workspace_id,),
                    ).fetchone()
                    connection.commit()
                    if row is None:
                        raise sqlite3.DatabaseError("workspace insert was not readable")
                    return WorkspaceResolution(
                        snapshot=self._snapshot(row),
                        new_capability=issued_capability,
                    )

                row = connection.execute(
                    """
                    SELECT * FROM demo_workspaces
                    WHERE capability_digest = ?
                    """,
                    (_capability_digest(capability),),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise self._access_error()
                if str(row["release_candidate_id"]) != self._release_candidate_id:
                    connection.rollback()
                    raise self._access_error()
                if row["retired_at"] is not None:
                    connection.rollback()
                    raise self._access_error()
                if _as_utc(current_time) - _parse_timestamp(
                    str(row["last_seen_at"])
                ) >= timedelta(days=self._quotas.workspace_inactive_days):
                    connection.execute(
                        "UPDATE demo_workspaces SET retired_at = ? WHERE workspace_id = ?",
                        (_timestamp(current_time), str(row["workspace_id"])),
                    )
                    connection.commit()
                    raise self._access_error()
                connection.execute(
                    "UPDATE demo_workspaces SET last_seen_at = ? WHERE workspace_id = ?",
                    (_timestamp(current_time), str(row["workspace_id"])),
                )
                updated = connection.execute(
                    "SELECT * FROM demo_workspaces WHERE workspace_id = ?",
                    (str(row["workspace_id"]),),
                ).fetchone()
                connection.commit()
                if updated is None:
                    raise sqlite3.DatabaseError("workspace update was not readable")
                return WorkspaceResolution(
                    snapshot=self._snapshot(updated),
                    new_capability=None,
                )
            except WorkspaceRequestError:
                raise
            except sqlite3.Error:
                connection.rollback()
                raise

    def touch_workspace(self, workspace_id: str, *, now: datetime | None = None) -> None:
        """Record activity for an already-resolved workspace."""

        current_time = _as_utc(now or _utc_now())
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._active_row_locked(workspace_id, current_time)
                connection.execute(
                    "UPDATE demo_workspaces SET last_seen_at = ? WHERE workspace_id = ?",
                    (_timestamp(current_time), workspace_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _record_mutation_locked(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        mutation_kind: str,
        content_hash: str,
        terminal_fresh_bundle: bool,
        now: datetime,
    ) -> MutationReceipt:
        connection = self._connection_or_raise()
        current_time = _as_utc(now)
        row = self._active_row_locked(workspace_id, current_time)
        existing = connection.execute(
            """
            SELECT mutation_id, mutation_kind, content_hash, terminal_fresh_bundle
            FROM demo_workspace_mutations
            WHERE workspace_id = ? AND idempotency_key = ?
            """,
            (workspace_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["mutation_kind"]) != mutation_kind
                or str(existing["content_hash"]) != content_hash
                or bool(existing["terminal_fresh_bundle"]) != terminal_fresh_bundle
            ):
                raise WorkspaceRequestError(
                    SafeErrorCode.DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT,
                    "USE_NEW_IDEMPOTENCY_KEY",
                    409,
                )
            return MutationReceipt(str(existing["mutation_id"]), replayed=True)

        mutation_count = int(row["mutation_count"])
        if mutation_count >= self._quotas.max_workspace_mutations:
            raise WorkspaceRequestError(
                SafeErrorCode.DEMO_WORKSPACE_MUTATION_LIMIT_REACHED,
                "START_A_NEW_DEMO_WORKSPACE",
                429,
            )

        cutoff = _timestamp(
            current_time - timedelta(minutes=1)
        )
        workspace_recent = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM demo_workspace_mutations
                WHERE workspace_id = ? AND occurred_at >= ?
                """,
                (workspace_id, cutoff),
            ).fetchone()[0]
        )
        if workspace_recent >= self._quotas.max_workspace_mutations_per_minute:
            raise WorkspaceRequestError(
                SafeErrorCode.DEMO_WORKSPACE_RATE_LIMITED,
                "WAIT_AND_RETRY",
                429,
            )

        global_recent = int(
            connection.execute(
                "SELECT COUNT(*) FROM demo_workspace_mutations WHERE occurred_at >= ?",
                (cutoff,),
            ).fetchone()[0]
        )
        if global_recent >= self._quotas.max_global_mutations_per_minute:
            raise WorkspaceRequestError(
                SafeErrorCode.DEMO_WORKSPACE_RATE_LIMITED,
                "WAIT_AND_RETRY",
                429,
            )

        terminal_count = int(row["terminal_fresh_bundle_count"])
        if (
            terminal_fresh_bundle
            and terminal_count >= self._quotas.max_workspace_terminal_fresh_bundles
        ):
            raise WorkspaceRequestError(
                SafeErrorCode.DEMO_WORKSPACE_FRESH_BUNDLE_LIMIT_REACHED,
                "START_A_NEW_DEMO_WORKSPACE",
                429,
            )

        mutation_id = uuid4().hex
        connection.execute(
            """
            INSERT INTO demo_workspace_mutations (
                mutation_id,
                workspace_id,
                idempotency_key,
                mutation_kind,
                content_hash,
                occurred_at,
                terminal_fresh_bundle
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mutation_id,
                workspace_id,
                idempotency_key,
                mutation_kind,
                content_hash,
                _timestamp(current_time),
                int(terminal_fresh_bundle),
            ),
        )
        connection.execute(
            """
            UPDATE demo_workspaces
            SET mutation_count = mutation_count + 1,
                terminal_fresh_bundle_count = terminal_fresh_bundle_count + ?
            WHERE workspace_id = ?
            """,
            (int(terminal_fresh_bundle), workspace_id),
        )
        return MutationReceipt(mutation_id, replayed=False)

    def record_mutation(
        self,
        workspace_id: str,
        *,
        idempotency_key: str,
        mutation_kind: str,
        content_hash: str,
        now: datetime | None = None,
    ) -> MutationReceipt:
        """Reserve one non-terminal bounded workspace mutation."""

        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                receipt = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind=mutation_kind,
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=_as_utc(now or _utc_now()),
                )
                connection.commit()
                return receipt
            except Exception:
                connection.rollback()
                raise

    def record_terminal_fresh_bundle(
        self,
        workspace_id: str,
        *,
        result_id: str,
        operation_id: str,
        result_ref: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> MutationReceipt:
        """Record a terminal fresh result through its completed operation."""

        return self.create_workspace_result(
            workspace_id,
            result_id=result_id,
            operation_id=operation_id,
            result_ref=result_ref,
            idempotency_key=idempotency_key,
            now=now,
        )

    def create_workspace_artifact(
        self,
        workspace_id: str,
        *,
        artifact_id: str,
        artifact_ref: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> MutationReceipt:
        current_time = _as_utc(now or _utc_now())
        content_hash = _owned_content_hash("ARTIFACT", artifact_id, artifact_ref)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="WORKSPACE_ARTIFACT",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    existing = connection.execute(
                        """
                        SELECT 1 FROM workspace_artifacts
                        WHERE artifact_id = ? AND workspace_id = ?
                        """,
                        (artifact_id, workspace_id),
                    ).fetchone()
                    if existing is None:
                        raise sqlite3.DatabaseError(
                            "workspace artifact mutation has no artifact row"
                        )
                    connection.commit()
                    return mutation
                connection.execute(
                    """
                    INSERT INTO workspace_artifacts (
                        artifact_id, workspace_id, artifact_ref, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (artifact_id, workspace_id, artifact_ref, _timestamp(current_time)),
                )
                connection.commit()
                return mutation
            except Exception:
                connection.rollback()
                raise

    def get_workspace_artifact(
        self,
        workspace_id: str,
        artifact_id: str,
    ) -> sqlite3.Row | None:
        with self._lock:
            connection = self._connection_or_raise()
            return connection.execute(
                """
                SELECT artifact_id, workspace_id, artifact_ref, created_at
                FROM workspace_artifacts
                WHERE artifact_id = ? AND workspace_id = ?
                """,
                (artifact_id, workspace_id),
            ).fetchone()

    def create_workspace_operation(
        self,
        workspace_id: str,
        *,
        operation_id: str,
        operation_kind: str,
        status: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> MutationReceipt:
        """Persist an operation while reserving its bounded mutation."""

        current_time = _as_utc(now or _utc_now())
        content_hash = _owned_content_hash(
            "OPERATION",
            operation_id,
            operation_kind,
            status,
        )
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="WORKSPACE_OPERATION",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    existing = connection.execute(
                        """
                        SELECT 1 FROM workspace_operations
                        WHERE operation_id = ? AND workspace_id = ?
                        """,
                        (operation_id, workspace_id),
                    ).fetchone()
                    if existing is None:
                        raise sqlite3.DatabaseError(
                            "workspace operation mutation has no operation row"
                        )
                    connection.commit()
                    return mutation
                connection.execute(
                    """
                    INSERT INTO workspace_operations (
                        operation_id,
                        workspace_id,
                        operation_kind,
                        status,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        workspace_id,
                        operation_kind,
                        status,
                        _timestamp(current_time),
                    ),
                )
                connection.commit()
                return mutation
            except Exception:
                connection.rollback()
                raise

    def get_workspace_operation(
        self,
        workspace_id: str,
        operation_id: str,
    ) -> sqlite3.Row | None:
        with self._lock:
            connection = self._connection_or_raise()
            return connection.execute(
                """
                SELECT operation_id, workspace_id, operation_kind, status,
                       created_at, finished_at
                FROM workspace_operations
                WHERE operation_id = ? AND workspace_id = ?
                """,
                (operation_id, workspace_id),
            ).fetchone()

    def create_workspace_selection(
        self,
        workspace_id: str,
        *,
        selection_id: str,
        reference_id: str,
        idempotency_key: str,
        reference_exists: Callable[[str], bool],
        now: datetime | None = None,
    ) -> MutationReceipt:
        current_time = _as_utc(now or _utc_now())
        content_hash = _owned_content_hash("SELECTION", selection_id, reference_id)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                reference_is_available = reference_exists(reference_id)
                if not reference_is_available:
                    raise WorkspaceRequestError(
                        SafeErrorCode.DEMO_WORKSPACE_RESOURCE_UNAVAILABLE,
                        "CHECK_WORKSPACE_AND_RETRY",
                        404,
                    )
                existing_mutation = connection.execute(
                    """
                    SELECT mutation_id
                    FROM demo_workspace_mutations
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
                if existing_mutation is None:
                    existing_selection = connection.execute(
                        """
                        SELECT workspace_id, reference_id
                        FROM workspace_selections
                        WHERE selection_id = ?
                        """,
                        (selection_id,),
                    ).fetchone()
                    if existing_selection is not None:
                        if (
                            str(existing_selection["workspace_id"]) != workspace_id
                            or str(existing_selection["reference_id"]) != reference_id
                        ):
                            raise WorkspaceRequestError(
                                SafeErrorCode.DEMO_WORKSPACE_RESOURCE_UNAVAILABLE,
                                "CHECK_WORKSPACE_AND_RETRY",
                                404,
                            )
                        raise WorkspaceRequestError(
                            SafeErrorCode.DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT,
                            "USE_NEW_IDEMPOTENCY_KEY",
                            409,
                        )
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="WORKSPACE_SELECTION",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    existing = connection.execute(
                        """
                        SELECT 1 FROM workspace_selections
                        WHERE selection_id = ? AND workspace_id = ?
                        """,
                        (selection_id, workspace_id),
                    ).fetchone()
                    if existing is None:
                        raise sqlite3.DatabaseError(
                            "workspace selection mutation has no selection row"
                        )
                    connection.commit()
                    return mutation
                connection.execute(
                    """
                    INSERT INTO workspace_selections (
                        selection_id, workspace_id, reference_id, selected_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        selection_id,
                        workspace_id,
                        reference_id,
                        _timestamp(current_time),
                    ),
                )
                connection.commit()
                return mutation
            except Exception:
                connection.rollback()
                raise

    def get_workspace_selection(
        self,
        workspace_id: str,
        selection_id: str,
    ) -> WorkspaceSelectionView | None:
        with self._lock:
            connection = self._connection_or_raise()
            row = connection.execute(
                """
                SELECT selection_id, workspace_id, reference_id, selected_at
                FROM workspace_selections
                WHERE selection_id = ? AND workspace_id = ?
                """,
                (selection_id, workspace_id),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceSelectionView(
            selection_id=str(row["selection_id"]),
            reference_id=str(row["reference_id"]),
            selected_at=datetime.fromisoformat(str(row["selected_at"])),
        )

    def create_workspace_result(
        self,
        workspace_id: str,
        *,
        result_id: str,
        operation_id: str,
        result_ref: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> MutationReceipt:
        current_time = _as_utc(now or _utc_now())
        content_hash = _owned_content_hash(
            "FRESH_RESULT",
            result_id,
            operation_id,
            result_ref,
        )
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                operation = connection.execute(
                    """
                    SELECT operation_kind, status FROM workspace_operations
                    WHERE operation_id = ? AND workspace_id = ?
                    """,
                    (operation_id, workspace_id),
                ).fetchone()
                if (
                    operation is None
                    or str(operation["operation_kind"])
                    not in {"FRESH_RUN", "FRESH_ANALYSIS", "FRESH_REPRODUCTION"}
                    or str(operation["status"]) != "TERMINAL"
                ):
                    raise WorkspaceRequestError(
                        SafeErrorCode.DEMO_WORKSPACE_RESOURCE_UNAVAILABLE,
                        "CHECK_WORKSPACE_AND_RETRY",
                        404,
                    )
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="WORKSPACE_FRESH_RESULT",
                    content_hash=content_hash,
                    terminal_fresh_bundle=True,
                    now=current_time,
                )
                if mutation.replayed:
                    existing = connection.execute(
                        """
                        SELECT 1 FROM workspace_results
                        WHERE result_id = ? AND workspace_id = ? AND operation_id = ?
                        """,
                        (result_id, workspace_id, operation_id),
                    ).fetchone()
                    if existing is None:
                        raise sqlite3.DatabaseError(
                            "workspace result mutation has no result row"
                        )
                    connection.commit()
                    return mutation
                connection.execute(
                    """
                    INSERT INTO workspace_results (
                        result_id, workspace_id, operation_id, result_ref, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        result_id,
                        workspace_id,
                        operation_id,
                        result_ref,
                        _timestamp(current_time),
                    ),
                )
                connection.commit()
                return mutation
            except Exception:
                connection.rollback()
                raise

    def get_workspace_result(
        self,
        workspace_id: str,
        result_id: str,
    ) -> WorkspaceResultView | None:
        with self._lock:
            connection = self._connection_or_raise()
            row = connection.execute(
                """
                SELECT result_id, workspace_id, operation_id, result_ref, created_at
                FROM workspace_results
                WHERE result_id = ? AND workspace_id = ?
                """,
                (result_id, workspace_id),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceResultView(
            result_id=str(row["result_id"]),
            operation_id=str(row["operation_id"]),
            result_ref=str(row["result_ref"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
