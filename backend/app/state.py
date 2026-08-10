from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from .audit import ensure_audit_schema
from .canonical import canonical_json as _canonical_json
from .drafts import DRAFT_STORAGE_SCHEMA_VERSION, ensure_draft_schema
from .errors import CoreSafeError, SafeErrorCode
from .governance import GOVERNANCE_SCHEMA_VERSION, ensure_governance_schema
from .ingestion import INGESTION_SCHEMA_VERSION, ensure_ingestion_schema
from .manager_decisions import (
    MANAGER_DECISION_SCHEMA_VERSION,
    ensure_manager_decision_schema,
)
from .operations import (
    DURABLE_OPERATION_SCHEMA_VERSION,
    ensure_operation_schema,
)
from .risk import ensure_risk_schema
from .settings import Settings
from .tradeoff_selection import TRADEOFF_SELECTION_STORAGE_SCHEMA_VERSION
from .workspace import DEMO_WORKSPACE_SCHEMA_VERSION, ensure_workspace_schema


CORE_STATE_SCHEMA_VERSION = "core-state.v13"
RELEASE_IDENTITY_SCHEMA_VERSION = "release-identity.v1"
QUOTA_POLICY_SCHEMA_VERSION = "quota-policy.v1"
VALIDATED_REFERENCE_PARTITION_SCHEMA_VERSION = "validated-reference-partition.v1"

CORE_METADATA_TABLE = """
    CREATE TABLE IF NOT EXISTS core_state_metadata (
        metadata_key TEXT PRIMARY KEY,
        metadata_value TEXT NOT NULL
    )
"""
CORE_METADATA_COLUMNS = ["metadata_key", "metadata_value"]

VALIDATED_REFERENCES_TABLE = """
    CREATE TABLE IF NOT EXISTS validated_references (
        reference_id TEXT PRIMARY KEY,
        bundle_ref TEXT NOT NULL,
        validation_attestation_ref TEXT NOT NULL,
        release_candidate_id TEXT NOT NULL
    )
"""
VALIDATED_REFERENCES_COLUMNS = [
    "reference_id",
    "bundle_ref",
    "validation_attestation_ref",
    "release_candidate_id",
]


@dataclass(frozen=True, slots=True)
class StateLayout:
    state_root: Path
    database_path: Path
    artifact_root: Path
    validated_reference_root: Path
    object_root: Path
    run_root: Path
    attestation_root: Path
    release_root: Path
    temporary_root: Path
    quarantine_root: Path
    runtime_root: Path
    release_identity_path: Path
    quota_policy_path: Path
    runtime_fingerprint_path: Path
    validated_reference_manifest_path: Path
    state_manifest_path: Path


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


class StateRoot:
    """Creates or validates one sealed SQLite/artifact state root."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._layout = StateLayout(
            state_root=settings.state_root,
            database_path=settings.database_path,
            artifact_root=settings.artifact_root,
            validated_reference_root=settings.validated_reference_root,
            object_root=settings.artifact_root / "objects",
            run_root=settings.artifact_root / "runs",
            attestation_root=settings.artifact_root / "attestations",
            release_root=settings.artifact_root / "releases",
            temporary_root=settings.artifact_root / "temporary",
            quarantine_root=settings.artifact_root / "quarantine",
            runtime_root=settings.state_root / "runtime",
            release_identity_path=settings.state_root
            / "runtime"
            / "release_identity.json",
            quota_policy_path=settings.state_root / "runtime" / "quota_policy.json",
            runtime_fingerprint_path=settings.state_root
            / "runtime"
            / "runtime_fingerprint.json",
            validated_reference_manifest_path=settings.validated_reference_root
            / "partition_manifest.json",
            state_manifest_path=settings.state_root / "state_manifest.json",
        )

    @property
    def layout(self) -> StateLayout:
        return self._layout

    def validate_sealed(self) -> StateLayout:
        """Validate an existing state root without creating or repairing it."""

        self._validate_sealed_state()
        return self._layout

    def initialize(self) -> StateLayout:
        root = self._layout.state_root
        try:
            if root.exists() and not root.is_dir():
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            if not root.exists():
                root.parent.mkdir(parents=True, exist_ok=True)

            if self._layout.state_manifest_path.exists():
                self._validate_sealed_state()
                return self._layout

            if root.exists() and any(root.iterdir()):
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )

            self._initialize_new_state()
            return self._layout
        except CoreSafeError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError) as error:
            raise CoreSafeError(
                SafeErrorCode.STATE_INITIALIZATION_FAILED,
                "RESTORE_CORE_STATE_AND_RETRY",
            ) from error

    def _initialize_new_state(self) -> None:
        root = self._layout.state_root
        created_directories: list[Path] = []
        created_files: list[Path] = []
        root_created = False
        try:
            if not root.exists():
                root.mkdir(parents=True)
                root_created = True

            self._create_directory(self._layout.artifact_root, created_directories)
            self._create_directory(
                self._layout.validated_reference_root,
                created_directories,
            )
            for directory in (
                self._layout.object_root,
                self._layout.run_root,
                self._layout.attestation_root,
                self._layout.release_root,
                self._layout.temporary_root,
                self._layout.quarantine_root,
            ):
                self._create_directory(directory, created_directories)
            self._create_directory(self._layout.runtime_root, created_directories)

            self._create_database(created_files)
            self._write_json(
                self._layout.release_identity_path,
                self._release_identity_payload(),
                created_files,
            )
            self._write_json(
                self._layout.quota_policy_path,
                self._quota_policy_payload(),
                created_files,
            )
            self._write_json(
                self._layout.runtime_fingerprint_path,
                self._settings.runtime_fingerprint.model_dump(mode="json"),
                created_files,
            )
            self._write_json(
                self._layout.validated_reference_manifest_path,
                self._validated_reference_partition_payload(),
                created_files,
            )
            self._write_json(
                self._layout.state_manifest_path,
                self._state_manifest_payload(),
                created_files,
            )
        except CoreSafeError:
            self._cleanup(created_files, created_directories, root_created)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as error:
            self._cleanup(created_files, created_directories, root_created)
            raise CoreSafeError(
                SafeErrorCode.STATE_INITIALIZATION_FAILED,
                "RESTORE_CORE_STATE_AND_RETRY",
            ) from error

    def _create_directory(self, path: Path, created_directories: list[Path]) -> None:
        if path.exists():
            if not path.is_dir():
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            return
        path.mkdir(parents=True)
        created_directories.append(path)

    def _create_database(self, created_files: list[Path]) -> None:
        database_path = self._layout.database_path
        if database_path.exists():
            raise CoreSafeError(
                SafeErrorCode.STATE_CORRUPT,
                "RESTORE_CORE_STATE_AND_RETRY",
            )
        created_files.append(database_path)
        metadata = self._database_metadata()
        connection = sqlite3.connect(database_path, timeout=5.0)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            ensure_workspace_schema(connection, create=True)
            ensure_audit_schema(connection, create=True)
            ensure_ingestion_schema(connection, create=True)
            ensure_risk_schema(connection, create=True)
            ensure_governance_schema(connection, create=True)
            ensure_operation_schema(connection, create=True)
            ensure_draft_schema(connection, create=True)
            ensure_manager_decision_schema(connection, create=True)
            _ensure_table(
                connection,
                "core_state_metadata",
                CORE_METADATA_TABLE,
                CORE_METADATA_COLUMNS,
                create=True,
            )
            _ensure_table(
                connection,
                "validated_references",
                VALIDATED_REFERENCES_TABLE,
                VALIDATED_REFERENCES_COLUMNS,
                create=True,
            )
            connection.executemany(
                "INSERT INTO core_state_metadata (metadata_key, metadata_value) VALUES (?, ?)",
                metadata.items(),
            )
            connection.commit()
        finally:
            connection.close()

    def _write_json(
        self,
        path: Path,
        payload: object,
        created_files: list[Path],
    ) -> None:
        temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary_path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(_canonical_json(payload))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            created_files.append(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _validate_sealed_state(self) -> None:
        required_directories = [
            self._layout.artifact_root,
            self._layout.validated_reference_root,
            self._layout.object_root,
            self._layout.run_root,
            self._layout.attestation_root,
            self._layout.release_root,
            self._layout.temporary_root,
            self._layout.quarantine_root,
            self._layout.runtime_root,
        ]
        required_files = [
            self._layout.database_path,
            self._layout.release_identity_path,
            self._layout.quota_policy_path,
            self._layout.runtime_fingerprint_path,
            self._layout.validated_reference_manifest_path,
            self._layout.state_manifest_path,
        ]
        if any(not path.is_dir() for path in required_directories) or any(
            not path.is_file() for path in required_files
        ):
            raise CoreSafeError(
                SafeErrorCode.STATE_CORRUPT,
                "RESTORE_CORE_STATE_AND_RETRY",
            )

        try:
            if self._read_json(self._layout.state_manifest_path) != self._state_manifest_payload():
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            release_identity = self._read_json(self._layout.release_identity_path)
            fingerprint = self._read_json(self._layout.runtime_fingerprint_path)
            if release_identity != self._release_identity_payload() or fingerprint != (
                self._settings.runtime_fingerprint.model_dump(mode="json")
            ):
                raise CoreSafeError(
                    SafeErrorCode.STATE_RELEASE_MISMATCH,
                    "USE_THE_MATCHING_RELEASE_CONFIGURATION",
                )
            if self._read_json(self._layout.quota_policy_path) != self._quota_policy_payload():
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            if self._read_json(
                self._layout.validated_reference_manifest_path
            ) != self._validated_reference_partition_payload():
                raise CoreSafeError(
                    SafeErrorCode.STATE_CORRUPT,
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            self._validate_database()
        except CoreSafeError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError, json.JSONDecodeError) as error:
            raise CoreSafeError(
                SafeErrorCode.STATE_CORRUPT,
                "RESTORE_CORE_STATE_AND_RETRY",
            ) from error

    def _validate_database(self) -> None:
        connection = sqlite3.connect(self._layout.database_path, timeout=5.0)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise sqlite3.DatabaseError("SQLite integrity check failed")
            ensure_workspace_schema(connection, create=False)
            ensure_audit_schema(connection, create=False)
            ensure_ingestion_schema(connection, create=False)
            ensure_risk_schema(connection, create=False)
            ensure_governance_schema(connection, create=False)
            ensure_operation_schema(connection, create=False)
            ensure_draft_schema(connection, create=False)
            ensure_manager_decision_schema(connection, create=False)
            _ensure_table(
                connection,
                "core_state_metadata",
                CORE_METADATA_TABLE,
                CORE_METADATA_COLUMNS,
                create=False,
            )
            _ensure_table(
                connection,
                "validated_references",
                VALIDATED_REFERENCES_TABLE,
                VALIDATED_REFERENCES_COLUMNS,
                create=False,
            )
            rows = connection.execute(
                "SELECT metadata_key, metadata_value FROM core_state_metadata"
            ).fetchall()
            if dict(rows) != self._database_metadata():
                raise sqlite3.DatabaseError("state metadata does not match the sealed contract")
        finally:
            connection.close()

    def _read_json(self, path: Path) -> object:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _release_identity_payload(self) -> dict[str, str]:
        return {
            "schema_version": RELEASE_IDENTITY_SCHEMA_VERSION,
            "release_candidate_id": self._settings.release_candidate_id,
            "build_manifest_id": self._settings.build_manifest_id,
        }

    def _quota_policy_payload(self) -> dict[str, object]:
        return {
            "schema_version": QUOTA_POLICY_SCHEMA_VERSION,
            **self._settings.quotas.model_dump(mode="json"),
        }

    def _validated_reference_partition_payload(self) -> dict[str, object]:
        return {
            "schema_version": VALIDATED_REFERENCE_PARTITION_SCHEMA_VERSION,
            "scope": "GLOBAL",
            "workspace_owned": False,
        }

    def _state_manifest_payload(self) -> dict[str, object]:
        return {
            "schema_version": CORE_STATE_SCHEMA_VERSION,
            "sealed": True,
            "database": "core.sqlite3",
            "artifact_root": "artifacts",
            "validated_reference_partition": "artifacts/validated-references",
            "demo_workspace_partition": "demo_workspaces",
            "runtime_root": "runtime",
        }

    def _database_metadata(self) -> dict[str, str]:
        return {
            "state_schema_version": CORE_STATE_SCHEMA_VERSION,
            "release_identity": _canonical_json(self._release_identity_payload()),
            "quota_policy": _canonical_json(self._quota_policy_payload()),
            "runtime_fingerprint": _canonical_json(
                self._settings.runtime_fingerprint.model_dump(mode="json")
            ),
            "validated_reference_partition": _canonical_json(
                self._validated_reference_partition_payload()
            ),
            "demo_workspace_schema": DEMO_WORKSPACE_SCHEMA_VERSION,
            "intake_lineage_schema": INGESTION_SCHEMA_VERSION,
            "governance_schema": GOVERNANCE_SCHEMA_VERSION,
            "durable_operation_schema": DURABLE_OPERATION_SCHEMA_VERSION,
            "tradeoff_selection_schema": TRADEOFF_SELECTION_STORAGE_SCHEMA_VERSION,
            "draft_storage_schema": DRAFT_STORAGE_SCHEMA_VERSION,
            "manager_decision_schema": MANAGER_DECISION_SCHEMA_VERSION,
        }

    def _cleanup(
        self,
        created_files: list[Path],
        created_directories: list[Path],
        root_created: bool,
    ) -> None:
        for path in reversed(created_files):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for path in sorted(created_directories, key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass
        if root_created:
            try:
                self._layout.state_root.rmdir()
            except OSError:
                pass


def initialize_state(settings: Settings) -> StateLayout:
    return StateRoot(settings).initialize()
