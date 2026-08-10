from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any, Callable, Mapping
from uuid import uuid4

from .canonical import canonical_json, sha256
from .errors import CoreSafeError, SafeErrorCode
from .references import ReferenceVerificationError, ValidatedReferenceStore
from .settings import DeliveryProfile, Settings


RECOVERY_SCHEMA_VERSION = "core-state-recovery.v1"
BASELINE_SCHEMA_VERSION = "core-state-baseline.v1"
ARCHIVE_SCHEMA_VERSION = "core-state-archive.v1"
QUARANTINE_SCHEMA_VERSION = "core-state-corruption-quarantine.v1"
BASELINE_ID = "baseline"
RECOVERY_ACTION = "RESTORE_CORE_STATE_AND_RETRY"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ACTIVE_OPERATION_STATES = frozenset({"QUEUED", "RUNNING", "CANCELLING"})
_RECOVERY_PENDING_ARTIFACT_STATES = frozenset({"QUARANTINE_UNAVAILABLE"})


class StateRecoveryError(RuntimeError):
    """A safe, actionable failure at the local state recovery boundary."""

    def __init__(
        self,
        code: str,
        recovery_action: str = RECOVERY_ACTION,
        *,
        quarantine_id: str | None = None,
    ) -> None:
        self.code = code
        self.recovery_action = recovery_action
        self.quarantine_id = quarantine_id
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    operation: str
    status: str
    archive_id: str | None
    source_id: str | None
    quarantine_id: str | None
    state_digest: str | None
    preflight_state: str
    recovery_action: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "operation": self.operation,
            "status": self.status,
            "archive_id": self.archive_id,
            "source_id": self.source_id,
            "quarantine_id": self.quarantine_id,
            "state_digest": self.state_digest,
            "preflight": self.preflight_state,
            "recovery_action": self.recovery_action,
        }


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    archive_id: str
    state_digest: str
    file_count: int


@dataclass(frozen=True, slots=True)
class _Snapshot:
    state_digest: str
    files: tuple[dict[str, object], ...]


class StateRecovery:
    """Archive, verify, quarantine, and replace one complete local state root."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state_root = settings.state_root.resolve()
        if self._state_root == self._state_root.parent:
            raise ValueError("state root must not be a filesystem root")
        self._recovery_root = self._state_root.parent / (
            f".{self._state_root.name}-recovery"
        )

    @property
    def state_root(self) -> Path:
        return self._state_root

    @property
    def recovery_root(self) -> Path:
        return self._recovery_root

    @property
    def archive_root(self) -> Path:
        return self._recovery_root / "archives"

    @property
    def quarantine_root(self) -> Path:
        return self._recovery_root / "quarantine"

    @property
    def baseline_root(self) -> Path:
        return self._recovery_root / "baseline"

    @property
    def pending_path(self) -> Path:
        return self._recovery_root / "recovery-pending.json"

    def ensure_baseline(self) -> str:
        """Create one immutable baseline, or validate the existing one."""

        self._require_non_hosted()
        self._verify_current_or_raise()
        return self._ensure_baseline_snapshot()

    def finalize_baseline_after_setup(self) -> str:
        """Capture setup completion in the initial baseline exactly once."""

        self._require_non_hosted()
        self._verify_current_or_raise()
        if self._baseline_exists():
            baseline_state = self.baseline_root / "state"
            self._validate_baseline_snapshot()
            if (baseline_state / "runtime" / "setup_success.json").is_file():
                return BASELINE_ID
            self._remove_exact(self.baseline_root)
        return self._create_baseline()

    def verify_current_state(self, *, quarantine_on_failure: bool = True) -> RecoveryReceipt:
        """Verify the sealed root and quarantine it when corruption is detected."""

        self._assert_no_pending_recovery()
        try:
            digest = self._verify_root(self._state_root)
        except StateRecoveryError as error:
            if (
                not quarantine_on_failure
                or error.code != "CORE_STATE_CORRUPT"
                or self._settings.profile is DeliveryProfile.HOSTED
            ):
                raise
            quarantine_id = self._quarantine_current_state(error.code)
            raise StateRecoveryError(
                "CORE_STATE_CORRUPT",
                RECOVERY_ACTION,
                quarantine_id=quarantine_id,
            ) from error
        return RecoveryReceipt(
            operation="VERIFY",
            status="VERIFIED",
            archive_id=None,
            source_id=None,
            quarantine_id=None,
            state_digest=digest,
            preflight_state="VERIFIED",
            recovery_action="NONE",
        )

    def archive(self) -> ArchiveReceipt:
        """Copy the complete current state to an immutable archive."""

        self._require_local_fallback()
        self._assert_operator_idle()
        self._verify_current_or_raise()
        return self._copy_current_to_archive()

    def reset(
        self,
        *,
        project_root: Path | None = None,
        interpreter_path: Path | None = None,
        preflight: Callable[[], object] | None = None,
    ) -> RecoveryReceipt:
        """Archive current state and replace it with the one sealed baseline."""

        self._require_local_fallback()
        self._assert_operator_idle()
        try:
            self._ensure_baseline_snapshot()
        except StateRecoveryError as error:
            if error.code != "CORE_STATE_CORRUPT":
                raise
            quarantine_id = self._quarantine_current_state(error.code)
            raise StateRecoveryError(
                "CORE_STATE_BACKUP_INVALID",
                RECOVERY_ACTION,
                quarantine_id=quarantine_id,
            ) from error
        baseline_state = self.baseline_root / "state"
        archive_id: str | None = None
        quarantine_id: str | None = None
        try:
            self._verify_root(self._state_root)
        except StateRecoveryError as error:
            if error.code != "CORE_STATE_CORRUPT":
                raise
            quarantine_id = self._quarantine_current_state(error.code)
        else:
            self._write_pending("RESET", BASELINE_ID, None)
            archive_id = self._move_current_to_archive()

        if not self.pending_path.exists():
            self._write_pending("RESET", BASELINE_ID, archive_id)
        receipt = self._replace_with_snapshot(
            operation="RESET",
            source_id=BASELINE_ID,
            source_state=baseline_state,
            archive_id=archive_id,
            quarantine_id=quarantine_id,
            project_root=project_root,
            interpreter_path=interpreter_path,
            preflight=preflight,
        )
        return receipt

    def restore(
        self,
        archive_id: str,
        *,
        project_root: Path | None = None,
        interpreter_path: Path | None = None,
        preflight: Callable[[], object] | None = None,
    ) -> RecoveryReceipt:
        """Replace current state with one previously archived complete state."""

        self._require_local_fallback()
        self._assert_operator_idle(allow_pending=True)
        source_state = self._archive_state(archive_id)
        try:
            self._validate_snapshot(
                source_state,
                self.archive_root / archive_id / "archive-manifest.json",
                expected_schema=ARCHIVE_SCHEMA_VERSION,
                expected_id=archive_id,
            )
            self._verify_root(source_state)
        except StateRecoveryError as error:
            if error.code not in {
                "CORE_STATE_BACKUP_INVALID",
                "CORE_STATE_CORRUPT",
                SafeErrorCode.STATE_RELEASE_MISMATCH.value,
            }:
                raise
            quarantine_id = self._quarantine_recovery_snapshot(
                self.archive_root / archive_id,
                error.code,
            )
            raise StateRecoveryError(
                error.code,
                RECOVERY_ACTION,
                quarantine_id=quarantine_id,
            ) from error

        archive_current_id: str | None = None
        quarantine_id: str | None = None
        self._write_pending("RESTORE", archive_id, None)
        if self._state_root.exists():
            try:
                self._verify_root(self._state_root)
            except StateRecoveryError as error:
                if error.code != "CORE_STATE_CORRUPT":
                    raise
                quarantine_id = self._quarantine_current_state(error.code)
            else:
                archive_current_id = self._move_current_to_archive()
        self._write_pending("RESTORE", archive_id, archive_current_id)
        return self._replace_with_snapshot(
            operation="RESTORE",
            source_id=archive_id,
            source_state=source_state,
            archive_id=archive_current_id,
            quarantine_id=quarantine_id,
            project_root=project_root,
            interpreter_path=interpreter_path,
            preflight=preflight,
        )

    def restore_baseline(
        self,
        *,
        project_root: Path | None = None,
        interpreter_path: Path | None = None,
        preflight: Callable[[], object] | None = None,
    ) -> RecoveryReceipt:
        """Explicitly restore the immutable baseline without resetting history implicitly."""

        self._require_local_fallback()
        self._assert_operator_idle(allow_pending=True)
        if not self._baseline_exists():
            raise StateRecoveryError(
                "CORE_STATE_BACKUP_INVALID",
                "RUN_SETUP_PS1_WHILE_ONLINE",
            )
        baseline_state = self.baseline_root / "state"
        self._validate_baseline_snapshot()
        archive_current_id: str | None = None
        quarantine_id: str | None = None
        self._write_pending("RESTORE_BASELINE", BASELINE_ID, None)
        if self._state_root.exists():
            try:
                self._verify_root(self._state_root)
            except StateRecoveryError as error:
                if error.code != "CORE_STATE_CORRUPT":
                    raise
                quarantine_id = self._quarantine_current_state(error.code)
            else:
                archive_current_id = self._move_current_to_archive()
        self._write_pending("RESTORE_BASELINE", BASELINE_ID, archive_current_id)
        return self._replace_with_snapshot(
            operation="RESTORE_BASELINE",
            source_id=BASELINE_ID,
            source_state=baseline_state,
            archive_id=archive_current_id,
            quarantine_id=quarantine_id,
            project_root=project_root,
            interpreter_path=interpreter_path,
            preflight=preflight,
        )

    def _require_non_hosted(self) -> None:
        if self._settings.profile is DeliveryProfile.HOSTED:
            raise StateRecoveryError(
                "CORE_RECOVERY_UNAVAILABLE",
                "USE_LOCAL_FALLBACK_CONFIGURATION",
            )

    def _require_local_fallback(self) -> None:
        if self._settings.profile is not DeliveryProfile.LOCAL_FALLBACK:
            raise StateRecoveryError(
                "CORE_RECOVERY_UNAVAILABLE",
                "USE_LOCAL_FALLBACK_CONFIGURATION",
            )

    def _baseline_exists(self) -> bool:
        return (
            self._regular_directory(self.baseline_root)
            and self._regular_directory(self.baseline_root / "state")
            and (self.baseline_root / "baseline-manifest.json").is_file()
        )

    def _ensure_baseline_snapshot(self) -> str:
        if self._baseline_exists():
            self._validate_baseline_snapshot()
            return BASELINE_ID
        try:
            self._verify_root(self._state_root)
        except StateRecoveryError:
            raise
        return self._create_baseline()

    def _validate_baseline_snapshot(self) -> _Snapshot:
        try:
            snapshot = self._validate_snapshot(
                self.baseline_root / "state",
                self.baseline_root / "baseline-manifest.json",
                expected_schema=BASELINE_SCHEMA_VERSION,
                expected_id=BASELINE_ID,
            )
            self._verify_root(self.baseline_root / "state")
            return snapshot
        except StateRecoveryError as error:
            if error.code not in {
                "CORE_STATE_BACKUP_INVALID",
                "CORE_STATE_CORRUPT",
                SafeErrorCode.STATE_RELEASE_MISMATCH.value,
            }:
                raise
            quarantine_id = self._quarantine_recovery_snapshot(
                self.baseline_root,
                error.code,
            )
            raise StateRecoveryError(
                error.code,
                RECOVERY_ACTION,
                quarantine_id=quarantine_id,
            ) from error

    def _verify_current_or_raise(self) -> str:
        self._assert_no_pending_recovery()
        try:
            return self._verify_root(self._state_root)
        except StateRecoveryError as error:
            if error.code == "CORE_STATE_CORRUPT":
                raise
            raise

    def _verify_root(self, root: Path) -> str:
        if not self._regular_directory(root):
            raise StateRecoveryError("CORE_STATE_CORRUPT")
        try:
            from .state import StateRoot

            root_settings = self._settings_at_root(root)
            StateRoot(root_settings).validate_sealed()
            reference_store = ValidatedReferenceStore(
                root_settings.artifact_root,
                release_candidate_id=root_settings.release_candidate_id,
                runtime_fingerprint=root_settings.runtime_fingerprint.model_dump(mode="json"),
            )
            reference_store.validate_current_release_manifest()
            run_root = root_settings.artifact_root / "runs"
            if not self._regular_directory(run_root):
                raise StateRecoveryError("CORE_STATE_CORRUPT")
            for run_path in sorted(run_root.iterdir(), key=lambda item: item.name):
                if not self._regular_directory(run_path):
                    raise StateRecoveryError("CORE_STATE_CORRUPT")
                if (run_path / "manifest.json").is_file():
                    reference_store.verify_analysis_run(run_path.name)
            snapshot = self._snapshot(root)
            return snapshot.state_digest
        except StateRecoveryError:
            raise
        except CoreSafeError as error:
            if error.code is SafeErrorCode.STATE_RELEASE_MISMATCH:
                raise StateRecoveryError(
                    SafeErrorCode.STATE_RELEASE_MISMATCH.value,
                    error.recovery_action,
                ) from error
            raise StateRecoveryError("CORE_STATE_CORRUPT") from error
        except (OSError, ReferenceVerificationError, sqlite3.Error, TypeError, ValueError) as error:
            raise StateRecoveryError("CORE_STATE_CORRUPT") from error

    def _settings_at_root(self, root: Path) -> Settings:
        values = self._settings.model_dump(mode="python")
        values.update(
            {
                "state_root": root,
                "database_path": None,
                "artifact_root": None,
                "validated_reference_root": None,
            }
        )
        return Settings(**values)

    def _assert_no_pending_recovery(self) -> None:
        if self.pending_path.exists():
            raise StateRecoveryError("CORE_STATE_RECOVERY_PENDING")

    def _assert_operator_idle(self, *, allow_pending: bool = False) -> None:
        if not allow_pending:
            self._assert_no_pending_recovery()
        marker_path = self._state_root / "runtime" / "local-fallback-process.json"
        if marker_path.exists():
            raise StateRecoveryError("CORE_STATE_ACTIVE", "STOP_LOCAL_CORE_AND_RETRY")
        database_path = self._state_root / "core.sqlite3"
        if not database_path.is_file():
            return
        connection = sqlite3.connect(database_path, timeout=1.0)
        try:
            rows = connection.execute(
                "SELECT operation_id, state, artifact_state FROM durable_operations"
            ).fetchall()
        except sqlite3.Error as error:
            raise StateRecoveryError("CORE_STATE_CORRUPT") from error
        finally:
            connection.close()
        for _operation_id, state, artifact_state in rows:
            if str(state) in _ACTIVE_OPERATION_STATES:
                raise StateRecoveryError(
                    "CORE_STATE_ACTIVE",
                    "STOP_LOCAL_CORE_AND_RETRY",
                )
            if (
                str(state) == "INTERRUPTED"
                and str(artifact_state) in _RECOVERY_PENDING_ARTIFACT_STATES
            ):
                raise StateRecoveryError("CORE_STATE_RECOVERY_PENDING")

    def _create_baseline(self) -> str:
        self._mkdir(self._recovery_root)
        if self.baseline_root.exists():
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID")
        temporary = self._recovery_root / f".baseline-{uuid4().hex}.tmp"
        try:
            self._copy_tree(self._state_root, temporary / "state")
            snapshot = self._snapshot(temporary / "state")
            manifest = self._snapshot_payload(
                BASELINE_SCHEMA_VERSION,
                BASELINE_ID,
                snapshot,
            )
            (temporary / "baseline-manifest.json").write_text(
                canonical_json(manifest) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            temporary.rename(self.baseline_root)
        except (OSError, TypeError, ValueError) as error:
            self._remove_exact(temporary)
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID") from error
        return BASELINE_ID

    def _copy_current_to_archive(self) -> ArchiveReceipt:
        archive_id = self._new_archive_id()
        archive_dir = self.archive_root / archive_id
        try:
            self._mkdir(archive_dir)
            self._copy_tree(self._state_root, archive_dir / "state")
            snapshot = self._snapshot(archive_dir / "state")
            self._write_snapshot_manifest(
                archive_dir / "archive-manifest.json",
                ARCHIVE_SCHEMA_VERSION,
                archive_id,
                snapshot,
            )
        except (OSError, TypeError, ValueError) as error:
            self._remove_exact(archive_dir)
            raise StateRecoveryError("CORE_STATE_ARCHIVE_FAILED") from error
        return ArchiveReceipt(archive_id, snapshot.state_digest, len(snapshot.files))

    def _move_current_to_archive(self) -> str:
        archive_id = self._new_archive_id()
        archive_dir = self.archive_root / archive_id
        self._mkdir(archive_dir)
        try:
            self._state_root.rename(archive_dir / "state")
            snapshot = self._snapshot(archive_dir / "state")
            self._write_snapshot_manifest(
                archive_dir / "archive-manifest.json",
                ARCHIVE_SCHEMA_VERSION,
                archive_id,
                snapshot,
            )
        except (OSError, TypeError, ValueError) as error:
            raise StateRecoveryError("CORE_STATE_ARCHIVE_FAILED") from error
        return archive_id

    def _replace_with_snapshot(
        self,
        *,
        operation: str,
        source_id: str,
        source_state: Path,
        archive_id: str | None,
        quarantine_id: str | None,
        project_root: Path | None,
        interpreter_path: Path | None,
        preflight: Callable[[], object] | None,
    ) -> RecoveryReceipt:
        temporary = self._recovery_root / f".restore-{uuid4().hex}.tmp"
        try:
            self._copy_tree(source_state, temporary)
            self._verify_root(temporary)
            self._write_pending(operation, source_id, archive_id)
            if self._state_root.exists():
                raise StateRecoveryError("CORE_STATE_RECOVERY_PENDING")
            temporary.rename(self._state_root)
            state_digest = self._verify_root(self._state_root)
        except StateRecoveryError:
            self._remove_exact(temporary)
            raise
        except (OSError, TypeError, ValueError, sqlite3.Error) as error:
            self._remove_exact(temporary)
            raise StateRecoveryError("CORE_STATE_RESTORE_FAILED") from error

        preflight_state = self._run_preflight(
            project_root=project_root,
            interpreter_path=interpreter_path,
            callback=preflight,
        )
        receipt = RecoveryReceipt(
            operation=operation,
            status="RESET" if operation == "RESET" else "RESTORED",
            archive_id=archive_id,
            source_id=source_id,
            quarantine_id=quarantine_id,
            state_digest=state_digest,
            preflight_state=preflight_state,
            recovery_action=(
                "RUN_SETUP_PS1_WHILE_ONLINE"
                if preflight_state == "FAILED"
                else "NONE"
            ),
        )
        self._write_receipt(receipt)
        self.pending_path.unlink(missing_ok=True)
        return receipt

    def _run_preflight(
        self,
        *,
        project_root: Path | None,
        interpreter_path: Path | None,
        callback: Callable[[], object] | None,
    ) -> str:
        if callback is not None:
            try:
                callback()
            except Exception:
                return "FAILED"
            return "VERIFIED"
        if project_root is None or self._settings.profile is not DeliveryProfile.LOCAL_FALLBACK:
            return "VERIFIED"
        try:
            from .local_fallback import preflight_local_fallback

            preflight_local_fallback(
                project_root,
                self._settings,
                interpreter_path=interpreter_path,
            )
        except Exception:
            return "FAILED"
        return "VERIFIED"

    def _archive_state(self, archive_id: str) -> Path:
        if not _IDENTIFIER.fullmatch(archive_id) or not archive_id.startswith("archive-"):
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID")
        path = self.archive_root / archive_id / "state"
        if not self._regular_directory(path):
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID")
        return path

    def _quarantine_current_state(self, reason_code: str) -> str:
        if self._settings.profile is DeliveryProfile.HOSTED:
            raise StateRecoveryError("CORE_STATE_CORRUPT")
        if not self._state_root.exists():
            raise StateRecoveryError("CORE_STATE_CORRUPT")
        quarantine_id = f"state-{uuid4()}"
        quarantine_dir = self.quarantine_root / quarantine_id
        self._mkdir(quarantine_dir)
        try:
            self._state_root.rename(quarantine_dir / "state")
            snapshot = self._snapshot(quarantine_dir / "state")
            manifest = {
                "schema_version": QUARANTINE_SCHEMA_VERSION,
                "quarantine_id": quarantine_id,
                "reason_code": reason_code,
                "recovery_action": RECOVERY_ACTION,
                "quarantined_at": datetime.now(timezone.utc).isoformat(),
                **self._snapshot_payload(
                    QUARANTINE_SCHEMA_VERSION,
                    quarantine_id,
                    snapshot,
                ),
            }
            self._write_json(quarantine_dir / "quarantine-manifest.json", manifest)
        except (OSError, TypeError, ValueError) as error:
            raise StateRecoveryError("CORE_STATE_QUARANTINE_FAILED") from error
        return quarantine_id

    def _quarantine_recovery_snapshot(self, source: Path, reason_code: str) -> str:
        """Move a bad baseline/archive aside without deleting its bytes."""

        if not source.exists():
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID")
        try:
            source.resolve().relative_to(self._recovery_root.resolve())
        except ValueError as error:
            raise StateRecoveryError("CORE_STATE_QUARANTINE_FAILED") from error
        quarantine_id = f"snapshot-{uuid4()}"
        quarantine_dir = self.quarantine_root / quarantine_id
        self._mkdir(quarantine_dir)
        try:
            source.rename(quarantine_dir / "snapshot")
            snapshot = self._snapshot(quarantine_dir / "snapshot")
            self._write_json(
                quarantine_dir / "quarantine-manifest.json",
                {
                    "schema_version": QUARANTINE_SCHEMA_VERSION,
                    "quarantine_id": quarantine_id,
                    "reason_code": reason_code,
                    "recovery_action": RECOVERY_ACTION,
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    **self._snapshot_payload(
                        QUARANTINE_SCHEMA_VERSION,
                        quarantine_id,
                        snapshot,
                    ),
                },
            )
        except (OSError, TypeError, ValueError) as error:
            raise StateRecoveryError("CORE_STATE_QUARANTINE_FAILED") from error
        return quarantine_id

    def _snapshot(self, root: Path) -> _Snapshot:
        files: list[dict[str, object]] = []
        if not self._regular_directory(root):
            raise OSError("snapshot root is unavailable")
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            if path.is_symlink():
                raise OSError("state snapshots cannot contain symlinks")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            files.append(
                {
                    "path": relative,
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        file_tuple = tuple(files)
        digest = sha256({"schema_version": "core-state-snapshot.v1", "files": file_tuple})
        return _Snapshot(state_digest=digest, files=file_tuple)

    def _snapshot_payload(
        self,
        schema_version: str,
        snapshot_id: str,
        snapshot: _Snapshot,
    ) -> dict[str, object]:
        return {
            "schema_version": schema_version,
            "snapshot_id": snapshot_id,
            "state_digest": snapshot.state_digest,
            "files": list(snapshot.files),
        }

    def _write_snapshot_manifest(
        self,
        path: Path,
        schema_version: str,
        snapshot_id: str,
        snapshot: _Snapshot,
    ) -> None:
        self._write_json(path, self._snapshot_payload(schema_version, snapshot_id, snapshot))

    def _validate_snapshot(
        self,
        root: Path,
        manifest_path: Path,
        *,
        expected_schema: str,
        expected_id: str,
    ) -> _Snapshot:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, Mapping):
                raise ValueError("snapshot manifest is not an object")
            if manifest.get("schema_version") != expected_schema:
                raise ValueError("snapshot schema is unsupported")
            if manifest.get("snapshot_id", manifest.get("quarantine_id")) != expected_id:
                raise ValueError("snapshot identity does not match")
            expected_files = manifest.get("files")
            expected_digest = manifest.get("state_digest")
            if not isinstance(expected_files, list) or not isinstance(expected_digest, str):
                raise ValueError("snapshot manifest is incomplete")
            actual = self._snapshot(root)
            if actual.state_digest != expected_digest or list(actual.files) != expected_files:
                raise ValueError("snapshot bytes do not match the manifest")
            return actual
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise StateRecoveryError("CORE_STATE_BACKUP_INVALID") from error

    def _write_pending(
        self,
        operation: str,
        source_id: str,
        archive_id: str | None,
    ) -> None:
        self._mkdir(self._recovery_root)
        payload = {
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "operation": operation,
            "source_id": source_id,
            "archive_id": archive_id,
            "state_root_name": self._state_root.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_json(self.pending_path, payload)

    def _write_receipt(self, receipt: RecoveryReceipt) -> None:
        self._write_json(
            self._recovery_root / "last-recovery.json",
            receipt.as_dict(),
        )

    def _new_archive_id(self) -> str:
        self._mkdir(self.archive_root)
        return f"archive-{uuid4()}"

    @staticmethod
    def _regular_directory(path: Path) -> bool:
        try:
            return path.is_dir() and not path.is_symlink()
        except OSError:
            return False

    def _mkdir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _copy_tree(self, source: Path, destination: Path) -> None:
        if not self._regular_directory(source):
            raise OSError("source state is unavailable")
        if destination.exists():
            raise OSError("destination already exists")
        for path in source.rglob("*"):
            if path.is_symlink():
                raise OSError("state snapshots cannot contain symlinks")
        shutil.copytree(source, destination, symlinks=False)

    def _write_json(self, path: Path, payload: Mapping[str, object]) -> None:
        self._mkdir(path.parent)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(payload))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _remove_exact(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            path.resolve().relative_to(self._recovery_root.resolve())
        except ValueError:
            raise ValueError("recovery cleanup target escaped its root")
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def _settings_from_environment() -> Settings:
    return Settings()


def _command_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Local Core state recovery")
    parser.add_argument(
        "command",
        choices=("archive", "reset", "restore", "restore-baseline", "verify"),
    )
    parser.add_argument("--archive-id", default="")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--interpreter", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _command_parser().parse_args(argv)
        settings = _settings_from_environment()
        recovery = StateRecovery(settings)
        if arguments.command == "archive":
            receipt = recovery.archive()
            payload: Mapping[str, object] = {
                "status": "ARCHIVED",
                "archive_id": receipt.archive_id,
                "state_digest": receipt.state_digest,
                "file_count": receipt.file_count,
            }
        elif arguments.command == "reset":
            receipt = recovery.reset(
                project_root=arguments.project_root or Path.cwd(),
                interpreter_path=arguments.interpreter,
            )
            payload = receipt.as_dict()
        elif arguments.command == "restore":
            if not arguments.archive_id:
                raise StateRecoveryError("CORE_STATE_BACKUP_INVALID", "SUPPLY_ARCHIVE_ID")
            receipt = recovery.restore(
                arguments.archive_id,
                project_root=arguments.project_root or Path.cwd(),
                interpreter_path=arguments.interpreter,
            )
            payload = receipt.as_dict()
        elif arguments.command == "restore-baseline":
            receipt = recovery.restore_baseline(
                project_root=arguments.project_root or Path.cwd(),
                interpreter_path=arguments.interpreter,
            )
            payload = receipt.as_dict()
        else:
            receipt = recovery.verify_current_state()
            payload = receipt.as_dict()
        print(json.dumps(payload, sort_keys=True))
        return 0
    except StateRecoveryError as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "code": error.code,
                    "recovery_action": error.recovery_action,
                    "quarantine_id": error.quarantine_id,
                },
                sort_keys=True,
            )
        )
        return 1
    except CoreSafeError as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "code": getattr(error.code, "value", str(error.code)),
                    "recovery_action": error.recovery_action,
                    "quarantine_id": None,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
