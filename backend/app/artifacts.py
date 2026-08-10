from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

from .canonical import canonical_json, sha256, timestamp


ARTIFACT_LIFECYCLE_SCHEMA_VERSION = "analysis-artifact-lifecycle.v1"
QUARANTINE_MANIFEST_SCHEMA_VERSION = "analysis-run-quarantine-manifest.v1"
LEASE_SCHEMA_VERSION = "analysis-run-lease.v1"
CLEANUP_SCHEMA_VERSION = "analysis-artifact-cleanup.v1"

RECOVERY_ACTION = "EXPLICIT_RETRY_AS_NEW_OPERATION"
ARTIFACT_MUTATION_LOCK = RLock()
_RUN_ID = re.compile(
    r"^analysis-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_RUN_ID_IN_TEXT = re.compile(
    r"analysis-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_DIGEST_IN_TEXT = re.compile(r"sha256:[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ArtifactLifecycleError(RuntimeError):
    """A safe, typed lifecycle failure without local path details."""

    def __init__(self, code: str, recovery_action: str | None = None) -> None:
        self.code = code
        self.recovery_action = recovery_action
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArtifactReadStatus:
    schema_version: str
    analysis_run_id: str
    lifecycle: str
    availability_state: str
    reason_code: str | None
    recovery_action: str | None
    bundle_manifest_hash: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactPinSet:
    schema_version: str
    run_ids: tuple[str, ...]
    object_digests: tuple[str, ...]
    attestation_refs: tuple[str, ...]
    pin_set_digest: str


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    schema_version: str
    operation_id: str
    status: str
    pin_set_digest: str | None
    pinned_material_count: int
    deleted_run_count: int
    deleted_object_count: int
    deleted_quarantine_count: int
    skipped_pinned_count: int
    skipped_ineligible_count: int
    recovery_action: str | None


class RunLease:
    """Create-only per-run publication ownership."""

    def __init__(self, artifact_root: Path, analysis_run_id: str, *, owner_id: str) -> None:
        _require_run_id(analysis_run_id)
        _require_identifier(owner_id, "lease owner")
        self._artifact_root = Path(artifact_root)
        self.analysis_run_id = analysis_run_id
        self.owner_id = owner_id
        self._lease_directory = self._artifact_root / "leases" / analysis_run_id
        self._lease_path = self._lease_directory / "lease.json"
        self._acquired = False

    @property
    def lease_path(self) -> Path:
        return self._lease_path

    def acquire(self, *, now: datetime | None = None) -> None:
        if self._acquired:
            return
        self._lease_directory.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._lease_directory.mkdir()
        except FileExistsError as error:
            raise ArtifactLifecycleError(
                "RUN_LEASE_CONFLICT",
                "WAIT_FOR_THE_CURRENT_RUN_TO_FINISH",
            ) from error
        try:
            _write_create_only_json(
                self._lease_path,
                {
                    "schema_version": LEASE_SCHEMA_VERSION,
                    "analysis_run_id": self.analysis_run_id,
                    "owner_id": self.owner_id,
                    "acquired_at": timestamp(now or datetime.now(timezone.utc)),
                },
            )
        except Exception:
            # Leaving the directory in place is conservative: a future publisher
            # must not assume ownership after a partially written lease.
            raise
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self._lease_path.unlink(missing_ok=True)
            self._lease_directory.rmdir()
        except OSError:
            # A lease is never replaced or recursively removed during release.
            pass
        finally:
            self._acquired = False

    def __enter__(self) -> "RunLease":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def _require_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ArtifactLifecycleError("ARTIFACT_IDENTITY_INVALID")


def _require_run_id(value: str) -> None:
    if not isinstance(value, str) or _RUN_ID.fullmatch(value) is None:
        raise ArtifactLifecycleError("ANALYSIS_RUN_ID_INVALID")


def _write_create_only_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (canonical_json(payload) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            try:
                if path.read_bytes() != content:
                    raise ArtifactLifecycleError("IMMUTABLE_METADATA_CONFLICT")
            except OSError as error:
                raise ArtifactLifecycleError("ARTIFACT_METADATA_UNAVAILABLE") from error
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> object | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError):
        return None
    return value


def _quarantine_target(quarantine_root: Path, identity: str) -> Path:
    quarantine_root.mkdir(parents=True, exist_ok=True)
    target = quarantine_root / identity
    if not target.exists():
        return target
    return quarantine_root / f"{identity}.event-{uuid4().hex}"


def _move_if_present(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if target.exists():
        raise OSError("quarantine destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    return True


def _quarantine_manifest(
    root: Path,
    *,
    analysis_run_id: str | None,
    operation_id: str | None,
    reason_code: str,
    material_kind: str,
    now: datetime | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": QUARANTINE_MANIFEST_SCHEMA_VERSION,
        "reason_code": reason_code,
        "recovery_action": RECOVERY_ACTION,
        "material_kind": material_kind,
        "cleanup_eligible": True,
        "created_at": timestamp(now or datetime.now(timezone.utc)),
    }
    if analysis_run_id is not None:
        payload["analysis_run_id"] = analysis_run_id
    if operation_id is not None:
        payload["operation_id"] = operation_id
    _write_create_only_json(root / "quarantine-manifest.json", payload)


def quarantine_operation_material(
    layout: Any,
    operation_id: str,
    *,
    reason_code: str,
) -> None:
    """Move all partial operation material into an immutable quarantine event."""

    _require_identifier(operation_id, "operation id")
    temporary_root = Path(layout.temporary_root) / operation_id
    published_root = Path(layout.run_root) / operation_id
    quarantine_parent = Path(layout.quarantine_root)
    direct_quarantine_root = quarantine_parent / operation_id
    if direct_quarantine_root.exists() and not temporary_root.exists() and not published_root.exists():
        manifest = _read_json(direct_quarantine_root / "quarantine-manifest.json")
        if (
            isinstance(manifest, Mapping)
            and manifest.get("schema_version") == QUARANTINE_MANIFEST_SCHEMA_VERSION
            and manifest.get("operation_id") == operation_id
            and manifest.get("material_kind") == "durable-operation"
        ):
            return
        raise ArtifactLifecycleError("QUARANTINE_INTEGRITY_UNAVAILABLE")
    quarantine_root = _quarantine_target(quarantine_parent, operation_id)
    quarantine_root.mkdir(parents=True, exist_ok=False)
    _move_if_present(temporary_root, quarantine_root / "temporary")
    _move_if_present(published_root, quarantine_root / "published")
    _quarantine_manifest(
        quarantine_root,
        analysis_run_id=(
            "analysis-run-" + operation_id.removeprefix("operation-")
            if operation_id.startswith("operation-")
            else None
        ),
        operation_id=operation_id,
        reason_code=reason_code,
        material_kind="durable-operation",
    )


def quarantine_analysis_run(
    artifact_root: Path,
    analysis_run_id: str,
    *,
    reason_code: str,
    operation_id: str | None = None,
) -> Path:
    """Retain a bad sealed run and publish only a safe quarantine marker."""

    _require_run_id(analysis_run_id)
    if operation_id is not None:
        _require_identifier(operation_id, "operation id")
    artifact_root = Path(artifact_root)
    run_root = artifact_root / "runs" / analysis_run_id
    quarantine_root = _quarantine_target(artifact_root / "quarantine", analysis_run_id)
    quarantine_root.mkdir(parents=True, exist_ok=False)
    _move_if_present(run_root, quarantine_root / "published")
    _quarantine_manifest(
        quarantine_root,
        analysis_run_id=analysis_run_id,
        operation_id=operation_id,
        reason_code=reason_code,
        material_kind="analysis-run",
    )
    return quarantine_root


def quarantine_staging_material(
    artifact_root: Path,
    stage_root: Path,
    analysis_run_id: str,
    *,
    reason_code: str,
    published_object_paths: tuple[Path, ...] = (),
) -> Path | None:
    """Retain failed publication staging material instead of deleting it."""

    _require_run_id(analysis_run_id)
    stage_root = Path(stage_root)
    if not stage_root.exists():
        return None
    quarantine_parent = artifact_root / "quarantine" / "staging"
    quarantine_parent.mkdir(parents=True, exist_ok=True)
    target = quarantine_parent / f"{analysis_run_id}-{uuid4().hex}"
    os.replace(stage_root, target)
    for object_path in published_object_paths:
        if not object_path.exists():
            continue
        relative = object_path.relative_to(artifact_root)
        object_target = target / "published-objects" / relative
        object_target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(object_path, object_target)
    _quarantine_manifest(
        target,
        analysis_run_id=analysis_run_id,
        operation_id=None,
        reason_code=reason_code,
        material_kind="analysis-run-staging",
    )
    return target


def _quarantine_payload(artifact_root: Path, analysis_run_id: str) -> Mapping[str, Any] | None:
    quarantine_root = Path(artifact_root) / "quarantine"
    if not quarantine_root.is_dir():
        return None
    direct = quarantine_root / analysis_run_id
    candidates: list[Path] = []
    if direct.is_dir():
        candidates.append(direct / "quarantine-manifest.json")
    try:
        candidates.extend(quarantine_root.rglob("quarantine-manifest.json"))
    except OSError:
        return {
            "reason_code": "RUN_ARTIFACT_QUARANTINED",
            "recovery_action": RECOVERY_ACTION,
        }
    for path in candidates:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        if payload.get("analysis_run_id") == analysis_run_id:
            return payload
        operation_id = payload.get("operation_id")
        if operation_id == "operation-" + analysis_run_id.removeprefix("analysis-run-"):
            return payload
    if direct.exists():
        return {
            "reason_code": "RUN_ARTIFACT_QUARANTINED",
            "recovery_action": RECOVERY_ACTION,
        }
    return None


def is_analysis_run_quarantined(artifact_root: Path, analysis_run_id: str) -> bool:
    _require_run_id(analysis_run_id)
    return _quarantine_payload(artifact_root, analysis_run_id) is not None


def artifact_read_status(
    artifact_root: Path,
    analysis_run_id: str,
    *,
    bundle_manifest_hash: str | None = None,
) -> ArtifactReadStatus:
    _require_run_id(analysis_run_id)
    quarantine = _quarantine_payload(artifact_root, analysis_run_id)
    if quarantine is not None:
        return ArtifactReadStatus(
            schema_version=ARTIFACT_LIFECYCLE_SCHEMA_VERSION,
            analysis_run_id=analysis_run_id,
            lifecycle="quarantined",
            availability_state="suppressed",
            reason_code=(
                str(quarantine.get("reason_code"))
                if isinstance(quarantine.get("reason_code"), str)
                else "RUN_ARTIFACT_QUARANTINED"
            ),
            recovery_action=(
                str(quarantine.get("recovery_action"))
                if isinstance(quarantine.get("recovery_action"), str)
                else RECOVERY_ACTION
            ),
            bundle_manifest_hash=bundle_manifest_hash,
        )
    if not (Path(artifact_root) / "runs" / analysis_run_id).is_dir():
        return ArtifactReadStatus(
            schema_version=ARTIFACT_LIFECYCLE_SCHEMA_VERSION,
            analysis_run_id=analysis_run_id,
            lifecycle="unavailable",
            availability_state="suppressed",
            reason_code="RUN_ARTIFACT_UNAVAILABLE",
            recovery_action=RECOVERY_ACTION,
            bundle_manifest_hash=bundle_manifest_hash,
        )
    return ArtifactReadStatus(
        schema_version=ARTIFACT_LIFECYCLE_SCHEMA_VERSION,
        analysis_run_id=analysis_run_id,
        lifecycle="sealed",
        availability_state="available",
        reason_code=None,
        recovery_action=None,
        bundle_manifest_hash=bundle_manifest_hash,
    )


def _collect_reference_tokens(value: object, run_ids: set[str], digests: set[str]) -> None:
    if isinstance(value, str):
        run_ids.update(_RUN_ID_IN_TEXT.findall(value))
        digests.update(_DIGEST_IN_TEXT.findall(value))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _collect_reference_tokens(key, run_ids, digests)
            _collect_reference_tokens(item, run_ids, digests)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_reference_tokens(item, run_ids, digests)


def _collect_file_tokens(path: Path, run_ids: set[str], digests: set[str]) -> None:
    payload = _read_json(path)
    if payload is not None:
        _collect_reference_tokens(payload, run_ids, digests)


def _collect_reference_files(root: Path, run_ids: set[str], digests: set[str]) -> None:
    excluded = {"runs", "objects", "temporary", "quarantine", "cleanup"}
    try:
        files = root.rglob("*.json")
    except OSError:
        return
    for path in files:
        if any(part in excluded for part in path.relative_to(root).parts[:-1]):
            continue
        _collect_file_tokens(path, run_ids, digests)


def _collect_database_tokens(
    database_path: Path | None,
    run_ids: set[str],
    digests: set[str],
) -> None:
    if database_path is None or not Path(database_path).is_file():
        return
    try:
        database_uri = Path(database_path).resolve().as_posix()
        connection = sqlite3.connect(f"file:{database_uri}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for table_row in table_rows:
            table_name = str(table_row[0])
            if table_name.startswith("sqlite_"):
                continue
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            for row in connection.execute(f"SELECT * FROM {quoted_table}"):
                for value in row:
                    if isinstance(value, str):
                        _collect_reference_tokens(value, run_ids, digests)
        connection.close()
    except (OSError, sqlite3.Error, ValueError):
        raise ArtifactLifecycleError(
            "ARTIFACT_PIN_SET_UNAVAILABLE",
            "RESTORE_CORE_STATE_AND_RETRY",
        )


def _object_digest_from_path(objects_root: Path, path: Path) -> str | None:
    try:
        relative = path.relative_to(objects_root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) != 4 or parts[1] != "sha256":
        return None
    if len(parts[2]) != 2 or re.fullmatch(r"[0-9a-f]{2}", parts[2]) is None:
        return None
    if re.fullmatch(r"[0-9a-f]{62}", parts[3]) is None:
        return None
    return "sha256:" + parts[2] + parts[3]


def _run_manifest(path: Path) -> Mapping[str, Any] | None:
    payload = _read_json(path)
    return payload if isinstance(payload, Mapping) else None


def build_artifact_pin_set(
    artifact_root: Path,
    *,
    release_candidate_id: str | None = None,
    database_path: Path | None = None,
) -> ArtifactPinSet:
    """Resolve direct and transitive references before any retention decision."""

    artifact_root = Path(artifact_root)
    run_ids: set[str] = set()
    referenced_digests: set[str] = set()
    _collect_reference_files(artifact_root, run_ids, referenced_digests)
    _collect_database_tokens(database_path, run_ids, referenced_digests)
    if release_candidate_id is not None:
        registry = (
            artifact_root
            / "releases"
            / release_candidate_id
            / "validated-references.json"
        )
        if registry.is_file():
            _collect_file_tokens(registry, run_ids, referenced_digests)

    manifests: dict[str, Mapping[str, Any]] = {}
    runs_root = artifact_root / "runs"
    if runs_root.is_dir():
        for run_directory in runs_root.iterdir():
            if not run_directory.is_dir() or _RUN_ID.fullmatch(run_directory.name) is None:
                continue
            manifest = _run_manifest(run_directory / "manifest.json")
            if manifest is not None:
                manifests[run_directory.name] = manifest

    bundle_run_ids = {
        str(manifest["bundle_manifest_hash"]): run_id
        for run_id, manifest in manifests.items()
        if isinstance(manifest.get("bundle_manifest_hash"), str)
    }
    for digest in tuple(referenced_digests):
        referenced_run_id = bundle_run_ids.get(digest)
        if referenced_run_id is not None:
            run_ids.add(referenced_run_id)

    pending = list(run_ids)
    while pending:
        run_id = pending.pop()
        manifest = manifests.get(run_id)
        if manifest is None:
            continue
        discovered_runs: set[str] = set()
        discovered_digests: set[str] = set()
        _collect_reference_tokens(manifest, discovered_runs, discovered_digests)
        new_runs = discovered_runs - run_ids
        run_ids.update(new_runs)
        pending.extend(new_runs)
        referenced_digests.update(discovered_digests)
        descriptors = manifest.get("artifact_descriptors")
        if isinstance(descriptors, list):
            for descriptor in descriptors:
                if isinstance(descriptor, Mapping):
                    digest = descriptor.get("sha256")
                    if isinstance(digest, str) and _DIGEST_IN_TEXT.fullmatch(digest):
                        referenced_digests.add(digest)

    object_digests: set[str] = set(referenced_digests)
    attestation_refs = set(referenced_digests)
    payload = {
        "schema_version": ARTIFACT_LIFECYCLE_SCHEMA_VERSION,
        "run_ids": sorted(run_ids),
        "object_digests": sorted(object_digests),
        "attestation_refs": sorted(attestation_refs),
    }
    return ArtifactPinSet(
        schema_version=ARTIFACT_LIFECYCLE_SCHEMA_VERSION,
        run_ids=tuple(payload["run_ids"]),
        object_digests=tuple(payload["object_digests"]),
        attestation_refs=tuple(payload["attestation_refs"]),
        pin_set_digest=sha256(payload),
    )


def _parse_cutoff(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _eligible_file(path: Path, cutoff: datetime) -> bool:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return False
    return modified <= cutoff


def _cleanup_result(
    operation_id: str,
    *,
    status: str,
    pin_set_digest: str | None,
    pinned_material_count: int = 0,
    deleted_run_count: int = 0,
    deleted_object_count: int = 0,
    deleted_quarantine_count: int = 0,
    skipped_pinned_count: int = 0,
    skipped_ineligible_count: int = 0,
    recovery_action: str | None = None,
) -> CleanupReceipt:
    return CleanupReceipt(
        schema_version=CLEANUP_SCHEMA_VERSION,
        operation_id=operation_id,
        status=status,
        pin_set_digest=pin_set_digest,
        pinned_material_count=pinned_material_count,
        deleted_run_count=deleted_run_count,
        deleted_object_count=deleted_object_count,
        deleted_quarantine_count=deleted_quarantine_count,
        skipped_pinned_count=skipped_pinned_count,
        skipped_ineligible_count=skipped_ineligible_count,
        recovery_action=recovery_action,
    )


def cleanup_artifacts(
    artifact_root: Path,
    *,
    eligible_before: datetime,
    release_candidate_id: str | None = None,
    database_path: Path | None = None,
    now: datetime | None = None,
    operation_id: str | None = None,
) -> CleanupReceipt:
    """Run an explicit, auditable retention operation over unpinned material."""

    artifact_root = Path(artifact_root)
    cleanup_root = artifact_root / "cleanup"
    cleanup_root.mkdir(parents=True, exist_ok=True)
    operation_id = operation_id or f"cleanup-{uuid4().hex}"
    _require_identifier(operation_id, "cleanup operation id")
    cutoff = (
        eligible_before.astimezone(timezone.utc)
        if eligible_before.tzinfo
        else eligible_before.replace(tzinfo=timezone.utc)
    )
    requested_at = timestamp(now or datetime.now(timezone.utc))
    intent = {
        "schema_version": CLEANUP_SCHEMA_VERSION,
        "operation_id": operation_id,
        "requested_at": requested_at,
        "eligible_before": timestamp(cutoff),
        "release_candidate_id": release_candidate_id,
        "scope": "unpinned-completed-runs-and-content-addressed-objects",
    }
    intent_path = cleanup_root / f"{operation_id}.intent.json"
    result_path = cleanup_root / f"{operation_id}.result.json"
    _write_create_only_json(intent_path, intent)

    ARTIFACT_MUTATION_LOCK.acquire()
    try:
        pins = build_artifact_pin_set(
            artifact_root,
            release_candidate_id=release_candidate_id,
            database_path=database_path,
        )
    except Exception:
        receipt = _cleanup_result(
            operation_id,
            status="UNAVAILABLE",
            pin_set_digest=None,
            recovery_action="RESTORE_CORE_STATE_AND_RETRY",
        )
        try:
            _write_create_only_json(result_path, asdict(receipt))
        finally:
            ARTIFACT_MUTATION_LOCK.release()
        return receipt

    deleted_runs = 0
    deleted_objects = 0
    deleted_quarantine = 0
    skipped_pinned = 0
    skipped_ineligible = 0
    try:
        runs_root = artifact_root / "runs"
        if runs_root.is_dir():
            for run_directory in list(runs_root.iterdir()):
                if not run_directory.is_dir() or _RUN_ID.fullmatch(run_directory.name) is None:
                    continue
                if run_directory.name in pins.run_ids:
                    skipped_pinned += 1
                    continue
                manifest = _run_manifest(run_directory / "manifest.json")
                completed_at = _parse_cutoff(manifest.get("completed_at")) if manifest else None
                if completed_at is None or completed_at > cutoff:
                    skipped_ineligible += 1
                    continue
                shutil.rmtree(run_directory)
                deleted_runs += 1

        objects_root = artifact_root / "objects"
        if objects_root.is_dir():
            for object_path in list(objects_root.rglob("*")):
                if not object_path.is_file() or not _eligible_file(object_path, cutoff):
                    continue
                digest = _object_digest_from_path(objects_root, object_path)
                if digest is None:
                    skipped_ineligible += 1
                    continue
                if digest in pins.object_digests:
                    skipped_pinned += 1
                    continue
                object_path.unlink()
                deleted_objects += 1

        quarantine_root = artifact_root / "quarantine"
        if quarantine_root.is_dir():
            quarantine_items: list[Path] = []
            for quarantine_item in list(quarantine_root.iterdir()):
                if not quarantine_item.is_dir():
                    continue
                if quarantine_item.name == "staging":
                    quarantine_items.extend(
                        child
                        for child in quarantine_item.iterdir()
                        if child.is_dir()
                    )
                    continue
                quarantine_items.append(quarantine_item)
            for quarantine_item in quarantine_items:
                manifests = list(quarantine_item.rglob("quarantine-manifest.json"))
                eligible = False
                item_pinned = False
                for manifest_path in manifests:
                    manifest = _read_json(manifest_path)
                    if not isinstance(manifest, Mapping) or manifest.get("cleanup_eligible") is not True:
                        continue
                    created_at = _parse_cutoff(manifest.get("created_at"))
                    if created_at is None or created_at > cutoff:
                        continue
                    eligible = True
                    run_id = manifest.get("analysis_run_id")
                    if isinstance(run_id, str) and run_id in pins.run_ids:
                        item_pinned = True
                if item_pinned:
                    skipped_pinned += 1
                elif eligible:
                    shutil.rmtree(quarantine_item)
                    deleted_quarantine += 1
                else:
                    skipped_ineligible += 1
        receipt = _cleanup_result(
            operation_id,
            status="SUCCEEDED",
            pin_set_digest=pins.pin_set_digest,
            pinned_material_count=len(pins.run_ids) + len(pins.object_digests) + len(pins.attestation_refs),
            deleted_run_count=deleted_runs,
            deleted_object_count=deleted_objects,
            deleted_quarantine_count=deleted_quarantine,
            skipped_pinned_count=skipped_pinned,
            skipped_ineligible_count=skipped_ineligible,
        )
    except Exception:
        receipt = _cleanup_result(
            operation_id,
            status="PARTIAL",
            pin_set_digest=pins.pin_set_digest,
            pinned_material_count=len(pins.run_ids) + len(pins.object_digests) + len(pins.attestation_refs),
            deleted_run_count=deleted_runs,
            deleted_object_count=deleted_objects,
            deleted_quarantine_count=deleted_quarantine,
            skipped_pinned_count=skipped_pinned,
            skipped_ineligible_count=skipped_ineligible,
            recovery_action="RESTORE_CORE_STATE_AND_RETRY",
        )
    try:
        _write_create_only_json(result_path, asdict(receipt))
    finally:
        ARTIFACT_MUTATION_LOCK.release()
    return receipt
