from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import stat
from threading import RLock
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .canonical import canonical_json, sha256
from .artifacts import (
    ArtifactLifecycleError,
    ArtifactReadStatus,
    RunLease,
    ARTIFACT_MUTATION_LOCK,
    artifact_read_status,
    is_analysis_run_quarantined,
    quarantine_analysis_run,
    quarantine_staging_material,
)
from .diagnostics import DiagnosticIntegrityError
from .fixture_boundaries import is_synthetic_fixture_identity
from .validity import publish_validity_results


ARTIFACT_CONTRACT_VERSION = "analysis-run-artifacts.v1"
BUNDLE_MANIFEST_SCHEMA_VERSION = "analysis-run-bundle-manifest.v1"
ARTIFACT_DESCRIPTOR_SCHEMA_VERSION = "analysis-artifact-descriptor.v1"
VERIFICATION_REPORT_SCHEMA_VERSION = "analysis-run-verification.v1"
VALIDATION_ATTESTATION_SCHEMA_VERSION = "analysis-run-validation-attestation.v1"
REPRODUCTION_COMPARISON_SCHEMA_VERSION = "analysis-run-reproduction-comparison.v1"
CACHE_KEY_SCHEMA_VERSION = "analysis-run-cache-key.v1"
REFERENCE_REGISTRY_SCHEMA_VERSION = "validated-analysis-references.v1"
READ_MODEL_SCHEMA_VERSION = "analysis-run-read-model.v1"
REFERENCE_PROMOTION_SCHEMA_VERSION = "validated-reference-promotion.v1"

DEFAULT_REFERENCE_SLOT_ID = "ordinary-demo"
DEFAULT_REFERENCE_INTENDED_ROLE = "semi_synthetic_hero"
SUPPORTED_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/jsonl",
        "application/x-npy",
    }
)
SUPPORTED_CONFIDENTIALITY_CLASSES = frozenset({"public", "public_safe"})
REQUIRED_LOGICAL_ROLES = frozenset(
    {
        "engine_request",
        "runtime_fingerprint",
        "model_recipe_registry",
        "derived_seed_registry",
        "cohort_stage_records",
        "estimator_visible_rows",
        "feature_schema",
        "feature_matrix",
        "fold_assignments",
        "nuisance_predictions",
        "engine_result",
        "diagnostic_artifacts",
        "verification_report",
    }
)
PRODUCER_SCHEMA_BY_ROLE: Mapping[str, tuple[str, str]] = {
    "engine_request": ("causal-engine-input", "v2"),
    "runtime_fingerprint": ("analysis-runtime-fingerprint", "v1"),
    "model_recipe_registry": ("model_recipe_registry", "v1"),
    "derived_seed_registry": ("derived_seed_registry", "v1"),
    "cohort_stage_records": ("cohort_stage_records", "v1"),
    "estimator_visible_rows": ("estimator_visible_rows", "v1"),
    "feature_schema": ("feature_schema", "v1"),
    "feature_matrix": ("feature_matrix", "v1"),
    "fold_assignments": ("fold_assignments", "v1"),
    "nuisance_predictions": ("nuisance_predictions", "v1"),
    "engine_result": ("causal-engine-result", "v1"),
    "diagnostic_artifacts": ("diagnostic_artifacts", "v1"),
    "verification_report": ("analysis-run-verification", "v1"),
    "reproduction_comparison": (
        "analysis-run-reproduction-comparison",
        "v1",
    ),
}
LEGACY_PRODUCER_SCHEMA_BY_ROLE: Mapping[str, tuple[str, str]] = {
    "runtime_fingerprint": ("runtime-fingerprint", "v1"),
}
SCIENTIFIC_CONTENT_DIGEST_ROLES = frozenset(
    REQUIRED_LOGICAL_ROLES
    - {"engine_request", "runtime_fingerprint", "verification_report"}
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RUN_ID = re.compile(
    r"^analysis-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

_MANIFEST_REQUIRED_KEYS = frozenset(
    {
        "manifest_schema_version",
        "artifact_contract_version",
        "analysis_run_id",
        "scientific_request_digest",
        "runtime_fingerprint_digest",
        "cache_key",
        "engine_result_status",
        "started_at",
        "completed_at",
        "producer_application_build_id",
        "artifact_descriptors",
        "bundle_manifest_hash",
    }
)
_MANIFEST_OPTIONAL_KEYS = frozenset(
    {
        "delivery_attempt_id",
        "investigation_request_id",
        "reproduces_run_id",
        "retries_run_id",
    }
)
_DESCRIPTOR_REQUIRED_KEYS = frozenset(
    {
        "descriptor_schema_version",
        "logical_role",
        "logical_id",
        "producer_schema_id",
        "producer_schema_version",
        "media_type",
        "sha256",
        "byte_count",
        "confidentiality_class",
        "evidence_refs",
    }
)
_DESCRIPTOR_OPTIONAL_KEYS = frozenset(
    {
        "scientific_content_digest",
        "record_count",
        "array_shape",
        "array_dtype",
        "array_order",
    }
)
_REGISTRY_REQUIRED_KEYS = frozenset({"entries"})
_REGISTRY_OPTIONAL_KEYS = frozenset(
    {"registry_schema_version", "schema_version", "release_candidate_id", "release_id"}
)
_ENTRY_REQUIRED_KEYS = frozenset(
    {
        "reference_slot_id",
        "analysis_run_id",
        "bundle_manifest_hash",
        "validation_attestation_id",
        "read_model_schema_version",
        "intended_role",
    }
)
_ENTRY_OPTIONAL_KEYS = frozenset(
    {"validation_attestation_ref", "status", "revoked"}
)
_ATTESTATION_REQUIRED_KEYS = frozenset(
    {
        "attestation_schema_version",
        "validation_attestation_id",
        "analysis_run_id",
        "bundle_manifest_hash",
        "scientific_request_digest",
        "runtime_fingerprint_digest",
        "release_candidate_id",
        "reference_slot_id",
        "validation_policy_version",
        "status",
        "checks",
        "validated_at",
    }
)
_ATTESTATION_OPTIONAL_KEYS = frozenset(
    {
        "release_id",
        "developer_actor",
        "availability_state",
        "content_hash",
        "lifecycle",
        "revoked",
        "run_status",
        "run_relationship",
    }
)
_VERIFICATION_REQUIRED_KEYS = frozenset(
    {"schema_version", "validation_policy_version", "status", "checks"}
)


class ReferenceVerificationError(ValueError):
    """A reference failed the closed read-time verification contract."""


class ReferencePromotionError(ReferenceVerificationError):
    """A sealed analysis run cannot become a globally reusable reference."""


@dataclass(frozen=True, slots=True)
class ArtifactMember:
    logical_role: str
    logical_id: str
    producer_schema_id: str
    producer_schema_version: str
    media_type: str
    confidentiality_class: str
    content: bytes
    evidence_refs: tuple[str, ...] = ()
    scientific_content_digest: str | None = None
    record_count: int | None = None
    array_shape: tuple[int, ...] | None = None
    array_dtype: str | None = None
    array_order: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedBundle:
    analysis_run_id: str
    bundle_manifest_hash: str


@dataclass(frozen=True, slots=True)
class ValidatedReference:
    reference_slot_id: str
    analysis_run_id: str
    bundle_manifest_hash: str
    validation_attestation_id: str
    validation_attestation_ref: str
    release_candidate_id: str
    intended_role: str
    engine_result_status: str
    scientific_request_digest: str
    dataset_version_id: str
    cache_key: str
    runtime_fingerprint_digest: str
    validation_policy_version: str
    validated_at: datetime
    completed_at: datetime
    diagnostic_results: tuple[Mapping[str, Any], ...] = ()
    robustness_grade: Mapping[str, Any] | None = None
    evidence_verdict: Mapping[str, Any] | None = None
    delivery_mode: str = "existing_run_reuse"
    verification_state: str = "reference_validated"


@dataclass(frozen=True, slots=True)
class AnalysisRunCacheCandidate:
    """A UI-safe reusable run projection without artifact paths or bytes."""

    analysis_run_id: str
    bundle_manifest_hash: str
    release_candidate_id: str
    intended_role: str
    engine_result_status: str
    scientific_request_digest: str
    dataset_version_id: str
    cache_key: str
    runtime_fingerprint_digest: str
    completed_at: datetime
    delivery_mode: str = "existing_run_reuse"
    verification_state: str = "machine_verified"
    reference_slot_id: str | None = None
    validation_attestation_id: str | None = None
    validation_attestation_ref: str | None = None
    validated_at: datetime | None = None
    run_relationship: str = "fresh"
    reproduces_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReferencePromotion:
    """The safe result of promoting one verified run into the global registry."""

    reference: ValidatedReference
    validation_attestation_id: str
    validation_attestation_ref: str
    created: bool


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceVerificationError(f"{label} must be an object")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
    label: str,
) -> None:
    keys = set(value)
    if not required <= keys or bool(keys - required - optional):
        raise ReferenceVerificationError(f"{label} has an unsupported shape")


def _require_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ReferenceVerificationError(f"{label} is not a supported identifier")
    return value


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ReferenceVerificationError(f"{label} is not a SHA-256 digest")
    return value


def build_cache_key(
    *,
    scientific_request_digest: str,
    runtime_fingerprint_digest: str,
    engine_output_schema_version: str,
) -> str:
    """Build the complete immutable identity used for reusable-run lookup."""

    _require_digest(scientific_request_digest, "scientific request digest")
    _require_digest(runtime_fingerprint_digest, "runtime fingerprint digest")
    _require_identifier(engine_output_schema_version, "engine output schema version")
    return sha256(
        {
            "schema_version": CACHE_KEY_SCHEMA_VERSION,
            "scientific_request_digest": scientific_request_digest,
            "runtime_fingerprint_digest": runtime_fingerprint_digest,
            "engine_output_schema_version": engine_output_schema_version,
            "bundle_manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        }
    )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or _CONTROL.search(value):
        raise ReferenceVerificationError(f"{label} is not safe text")
    return value


def _require_passed_checks(value: object, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ReferenceVerificationError(f"{label} are incomplete")
    check_ids: set[str] = set()
    for check_value in value:
        check = _require_mapping(check_value, f"{label[:-1]} entry")
        _require_exact_keys(
            check,
            frozenset({"check_id", "status", "evidence_digest"}),
            frozenset(),
            f"{label[:-1]} entry",
        )
        check_id = _require_identifier(check["check_id"], "validation check id")
        if check_id in check_ids:
            raise ReferenceVerificationError(f"{label} contain duplicate check ids")
        check_ids.add(check_id)
        if check["status"] != "passed":
            raise ReferenceVerificationError(f"{label} contain a failed check")
        _require_digest(check["evidence_digest"], "validation evidence digest")


def _require_utc_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReferenceVerificationError(f"{label} is not a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReferenceVerificationError(f"{label} is not a timestamp") from error
    if parsed.tzinfo is None:
        raise ReferenceVerificationError(f"{label} is not UTC")
    return parsed.astimezone(timezone.utc)


def _regular_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISREG(info.st_mode)
        and not path.is_symlink()
        and not bool(getattr(info, "st_file_attributes", 0) & reparse_point)
    )


def _regular_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISDIR(info.st_mode)
        and not path.is_symlink()
        and not bool(getattr(info, "st_file_attributes", 0) & reparse_point)
    )


def _under(root: Path, path: Path) -> Path:
    root_lexical = Path(os.path.abspath(str(root)))
    path_lexical = Path(os.path.abspath(str(path)))
    if root.exists() and not _regular_directory(root):
        raise ReferenceVerificationError("artifact root is not a regular directory")
    try:
        relative = path_lexical.relative_to(root_lexical)
    except ValueError as error:
        raise ReferenceVerificationError("derived artifact path escapes its root") from error
    current = root_lexical
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for part in relative.parts:
        current /= part
        if not current.exists():
            continue
        try:
            info = current.lstat()
        except OSError as error:
            raise ReferenceVerificationError("derived artifact path is unavailable") from error
        if path_lexical == current:
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise ReferenceVerificationError("derived artifact path is not traversable")
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ReferenceVerificationError("derived artifact path is not traversable")
        if current.is_symlink() or bool(
            getattr(info, "st_file_attributes", 0) & reparse_point
        ):
            raise ReferenceVerificationError("derived artifact path uses a link or reparse point")
    root_resolved = root.resolve(strict=False)
    path_resolved = path.resolve(strict=False)
    if not path_resolved.is_relative_to(root_resolved):
        raise ReferenceVerificationError("derived artifact path escapes its root")
    return path_resolved


def _canonical_bytes(value: object) -> bytes:
    try:
        return canonical_json(value).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise ReferenceVerificationError("artifact JSON is not canonical-safe") from error


def _parse_json_bytes(content: bytes, label: str) -> object:
    candidate = content[:-1] if content.endswith(b"\n") else content
    if not candidate or candidate.endswith(b"\n") or candidate.endswith(b"\r"):
        raise ReferenceVerificationError(f"{label} is not canonical JSON")
    try:
        value = json.loads(candidate.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReferenceVerificationError(f"{label} is not JSON") from error
    if _canonical_bytes(value) != candidate:
        raise ReferenceVerificationError(f"{label} is not canonical JSON")
    return value


def _parse_jsonl_bytes(content: bytes, label: str) -> list[object]:
    if not content or content.endswith(b"\n") or content.endswith(b"\r"):
        raise ReferenceVerificationError(f"{label} is not canonical JSONL")
    records: list[object] = []
    for index, line in enumerate(content.split(b"\n")):
        records.append(_parse_json_bytes(line, f"{label} record {index}"))
    return records


def _verify_npy(content: bytes, descriptor: Mapping[str, Any], label: str) -> None:
    if not content.startswith(b"\x93NUMPY"):
        raise ReferenceVerificationError(f"{label} is not a NumPy array")
    if len(content) < 10:
        raise ReferenceVerificationError(f"{label} has no complete NumPy header")
    try:
        import io
        import numpy as np

        array = np.load(
            io.BytesIO(content),
            allow_pickle=False,
            max_header_size=10_000,
        )
        if not isinstance(array, np.ndarray):
            raise ReferenceVerificationError(f"{label} is not a dense array")
        if array.dtype.kind not in "biufc":
            raise ReferenceVerificationError(f"{label} uses an unsafe dtype")
        if array.dtype.hasobject or array.dtype.fields is not None:
            raise ReferenceVerificationError(f"{label} uses an unsafe dtype")
        if tuple(int(item) for item in array.shape) != tuple(descriptor["array_shape"]):
            raise ReferenceVerificationError(f"{label} shape does not match")
        if str(array.dtype) != descriptor["array_dtype"]:
            raise ReferenceVerificationError(f"{label} dtype does not match")
        expected_order = descriptor["array_order"]
        if expected_order == "C" and not array.flags.c_contiguous:
            raise ReferenceVerificationError(f"{label} order does not match")
        if expected_order == "F" and not array.flags.f_contiguous:
            raise ReferenceVerificationError(f"{label} order does not match")
        if not bool(np.isfinite(array).all()):
            raise ReferenceVerificationError(f"{label} contains non-finite values")
    except ReferenceVerificationError:
        raise
    except Exception as error:
        raise ReferenceVerificationError(f"{label} is not a safe NumPy array") from error


def _verify_media(
    content: bytes,
    descriptor: Mapping[str, Any],
    label: str,
) -> object | list[object] | None:
    media_type = descriptor["media_type"]
    if media_type == "application/json":
        if any(key in descriptor for key in ("record_count", "array_shape", "array_dtype", "array_order")):
            raise ReferenceVerificationError(f"{label} has invalid JSON descriptor fields")
        return _parse_json_bytes(content, label)
    if media_type == "application/jsonl":
        if any(key in descriptor for key in ("array_shape", "array_dtype", "array_order")):
            raise ReferenceVerificationError(f"{label} has invalid JSONL descriptor fields")
        records = _parse_jsonl_bytes(content, label)
        if descriptor["record_count"] != len(records):
            raise ReferenceVerificationError(f"{label} record count does not match")
        return records
    if media_type == "application/x-npy":
        if not all(key in descriptor for key in ("array_shape", "array_dtype", "array_order")):
            raise ReferenceVerificationError(f"{label} has incomplete NumPy metadata")
        _verify_npy(content, descriptor, label)
        return None
    raise ReferenceVerificationError(f"{label} uses an unsupported media type")


def _verify_role_payload(
    descriptor: Mapping[str, Any],
    payload: object | list[object] | None,
) -> None:
    role = str(descriptor["logical_role"])
    if payload is None:
        return
    expected_schema = f"{descriptor['producer_schema_id']}.{descriptor['producer_schema_version']}"
    if isinstance(payload, list):
        if role == "engine_request":
            raise ReferenceVerificationError("engine request must be one JSON object")
        for record in payload:
            record_mapping = _require_mapping(record, f"artifact {role} record")
            if record_mapping.get("schema_version") != expected_schema:
                raise ReferenceVerificationError(f"{role} payload schema does not match")
        return
    mapping = _require_mapping(payload, f"artifact {role} payload")
    if role == "engine_request":
        if mapping.get("engine_input_schema_version") not in {
            expected_schema,
            "causal-engine-suite-request.v2",
        }:
            raise ReferenceVerificationError("engine request payload schema does not match")
        _require_identifier(mapping.get("dataset_version_id"), "engine request dataset version")
        _require_identifier(mapping.get("intended_role"), "engine request intended role")
        return
    if role == "runtime_fingerprint" and mapping.get("schema_version") in {
        "analysis-runtime-fingerprint.v1",
        "runtime-fingerprint.v1",
    }:
        return
    if role == "engine_result" and mapping.get("schema_version") in {
        "causal-engine-result.v1",
        "causal-engine-suite-result.v2",
    }:
        return
    if mapping.get("schema_version") != expected_schema:
        raise ReferenceVerificationError(f"{role} payload schema does not match")


def _object_path(artifact_root: Path, descriptor: Mapping[str, Any]) -> Path:
    digest = descriptor["sha256"][7:]
    class_root = descriptor["confidentiality_class"]
    path = artifact_root / "objects" / class_root / "sha256" / digest[:2] / digest[2:]
    return _under(artifact_root, path)


def _attestation_path(
    artifact_root: Path,
    validation_attestation_id: str,
    validation_attestation_ref: str | None = None,
) -> Path:
    if validation_attestation_ref is not None and _DIGEST.fullmatch(
        validation_attestation_ref
    ) is not None:
        digest = validation_attestation_ref[7:]
        return _under(
            artifact_root,
            artifact_root / "attestations" / "sha256" / digest[:2] / digest[2:],
        )
    _require_identifier(validation_attestation_id, "validation attestation id")
    return _under(
        artifact_root,
        artifact_root / "attestations" / f"{validation_attestation_id}.json",
    )


def _run_is_quarantined(artifact_root: Path, analysis_run_id: str) -> bool:
    try:
        return is_analysis_run_quarantined(artifact_root, analysis_run_id)
    except (ArtifactLifecycleError, OSError):
        return True


def _quarantine_verification_failure(
    artifact_root: Path,
    analysis_run_id: str,
    *,
    reason_code: str = "RUN_ARTIFACT_INTEGRITY_FAILED",
) -> None:
    if _run_is_quarantined(artifact_root, analysis_run_id):
        return
    run_directory = artifact_root / "runs" / analysis_run_id
    if not run_directory.exists():
        return
    try:
        quarantine_analysis_run(
            artifact_root,
            analysis_run_id,
            reason_code=reason_code,
        )
    except (ArtifactLifecycleError, OSError) as error:
        raise ReferenceVerificationError(
            "analysis run quarantine is unavailable"
        ) from error


def _read_canonical_file(path: Path, label: str) -> object:
    if not _regular_file(path):
        raise ReferenceVerificationError(f"{label} is unavailable")
    try:
        return _parse_json_bytes(path.read_bytes(), label)
    except OSError as error:
        raise ReferenceVerificationError(f"{label} is unavailable") from error


def _descriptor_payload(
    artifact_root: Path,
    descriptor: Mapping[str, Any],
) -> object | list[object] | None:
    label = f"artifact {descriptor.get('logical_role', 'unknown')}"
    content_path = _object_path(artifact_root, descriptor)
    if not _regular_file(content_path):
        raise ReferenceVerificationError(f"{label} object is unavailable")
    try:
        content = content_path.read_bytes()
    except OSError as error:
        raise ReferenceVerificationError(f"{label} object is unavailable") from error
    if len(content) != descriptor["byte_count"]:
        raise ReferenceVerificationError(f"{label} byte count does not match")
    if sha256(content) != descriptor["sha256"]:
        raise ReferenceVerificationError(f"{label} hash does not match")
    payload = _verify_media(content, descriptor, label)
    _verify_role_payload(descriptor, payload)
    declared_content_digest = descriptor.get("scientific_content_digest")
    if declared_content_digest is not None:
        if isinstance(payload, list):
            observed_content_digest = sha256(payload)
        elif payload is not None:
            observed_content_digest = sha256(payload)
        else:
            observed_content_digest = None
        if observed_content_digest != declared_content_digest:
            raise ReferenceVerificationError(f"{label} logical digest does not match")
    return payload


def _verify_evidence_refs(
    descriptor: Mapping[str, Any],
    identities: set[tuple[str, str]],
) -> None:
    for reference in descriptor["evidence_refs"]:
        role, separator, logical_id = reference.partition(":")
        if not separator or (role, logical_id) not in identities:
            raise ReferenceVerificationError("artifact evidence reference does not resolve")


def _validate_descriptor_shape(descriptor: Mapping[str, Any]) -> None:
    _require_exact_keys(
        descriptor,
        _DESCRIPTOR_REQUIRED_KEYS,
        _DESCRIPTOR_OPTIONAL_KEYS,
        "artifact descriptor",
    )
    if descriptor["descriptor_schema_version"] != ARTIFACT_DESCRIPTOR_SCHEMA_VERSION:
        raise ReferenceVerificationError("artifact descriptor schema is unsupported")
    role = _require_identifier(descriptor["logical_role"], "logical role")
    if role not in REQUIRED_LOGICAL_ROLES and role != "reproduction_comparison":
        raise ReferenceVerificationError("logical role is unsupported")
    expected_producer_schema = PRODUCER_SCHEMA_BY_ROLE.get(role)
    observed_producer_schema = (
        descriptor["producer_schema_id"],
        descriptor["producer_schema_version"],
    )
    if expected_producer_schema is None or (
        observed_producer_schema != expected_producer_schema
        and observed_producer_schema != LEGACY_PRODUCER_SCHEMA_BY_ROLE.get(role)
    ):
        raise ReferenceVerificationError("producer schema is unsupported for logical role")
    _require_identifier(descriptor["logical_id"], "logical id")
    _require_identifier(descriptor["producer_schema_id"], "producer schema id")
    _require_identifier(descriptor["producer_schema_version"], "producer schema version")
    if descriptor["media_type"] not in SUPPORTED_MEDIA_TYPES:
        raise ReferenceVerificationError("artifact media type is unsupported")
    _require_digest(descriptor["sha256"], "artifact hash")
    if not isinstance(descriptor["byte_count"], int) or descriptor["byte_count"] < 0:
        raise ReferenceVerificationError("artifact byte count is invalid")
    if descriptor["confidentiality_class"] not in SUPPORTED_CONFIDENTIALITY_CLASSES:
        raise ReferenceVerificationError("artifact confidentiality class is unsupported")
    refs = descriptor["evidence_refs"]
    if not isinstance(refs, list) or any(
        not isinstance(ref, str) or not ref or _CONTROL.search(ref) for ref in refs
    ):
        raise ReferenceVerificationError("artifact evidence references are invalid")
    if "scientific_content_digest" in descriptor:
        _require_digest(descriptor["scientific_content_digest"], "scientific content digest")
    if descriptor["media_type"] == "application/jsonl":
        if not isinstance(descriptor.get("record_count"), int) or descriptor["record_count"] < 0:
            raise ReferenceVerificationError("JSONL record count is invalid")
    elif "record_count" in descriptor:
        raise ReferenceVerificationError("record count is only valid for JSONL")
    if descriptor["media_type"] == "application/x-npy":
        shape = descriptor.get("array_shape")
        if (
            not isinstance(shape, list)
            or any(not isinstance(item, int) or item < 0 for item in shape)
            or not isinstance(descriptor.get("array_dtype"), str)
            or descriptor["array_dtype"] not in {"bool", "float32", "float64", "int8", "int16", "int32", "int64"}
            or descriptor.get("array_order") not in {"C", "F"}
        ):
            raise ReferenceVerificationError("NumPy descriptor metadata is invalid")
    elif any(key in descriptor for key in ("array_shape", "array_dtype", "array_order")):
        raise ReferenceVerificationError("array metadata is only valid for NumPy")
    if (
        role in SCIENTIFIC_CONTENT_DIGEST_ROLES
        and descriptor["media_type"] in {"application/json", "application/jsonl"}
        and "scientific_content_digest" not in descriptor
    ):
        raise ReferenceVerificationError("scientific content digest is required")


def _verify_bundle(
    artifact_root: Path,
    analysis_run_id: str,
    expected_build_id: str,
    expected_runtime: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object | list[object] | None]]:
    if _RUN_ID.fullmatch(analysis_run_id) is None:
        raise ReferenceVerificationError("analysis run id is unsupported")
    run_dir = _under(artifact_root, artifact_root / "runs" / analysis_run_id)
    if not _regular_directory(run_dir):
        raise ReferenceVerificationError("analysis run directory is unavailable")
    try:
        children = list(run_dir.iterdir())
    except OSError as error:
        raise ReferenceVerificationError("analysis run directory is unavailable") from error
    if any(child.name != "manifest.json" for child in children):
        raise ReferenceVerificationError("analysis run contains unsupported material")
    manifest_path = run_dir / "manifest.json"
    manifest = _require_mapping(_read_canonical_file(manifest_path, "bundle manifest"), "bundle manifest")
    _require_exact_keys(
        manifest,
        _MANIFEST_REQUIRED_KEYS,
        _MANIFEST_OPTIONAL_KEYS,
        "bundle manifest",
    )
    if manifest["manifest_schema_version"] != BUNDLE_MANIFEST_SCHEMA_VERSION:
        raise ReferenceVerificationError("bundle manifest schema is unsupported")
    if manifest["artifact_contract_version"] != ARTIFACT_CONTRACT_VERSION:
        raise ReferenceVerificationError("artifact contract is unsupported")
    if manifest["analysis_run_id"] != analysis_run_id:
        raise ReferenceVerificationError("bundle run identity does not match its path")
    _require_digest(manifest["scientific_request_digest"], "scientific request digest")
    _require_digest(manifest["runtime_fingerprint_digest"], "runtime fingerprint digest")
    _require_digest(manifest["cache_key"], "cache key")
    if manifest["engine_result_status"] not in {"estimated", "abstained"}:
        raise ReferenceVerificationError("bundle result status is unsupported")
    _require_utc_timestamp(manifest["started_at"], "bundle start time")
    _require_utc_timestamp(manifest["completed_at"], "bundle completion time")
    if manifest["producer_application_build_id"] != expected_build_id:
        raise ReferenceVerificationError("bundle build identity does not match")
    for key in ("delivery_attempt_id", "investigation_request_id"):
        if key in manifest:
            _require_identifier(manifest[key], key)
    for key in ("reproduces_run_id", "retries_run_id"):
        if key in manifest and _RUN_ID.fullmatch(str(manifest[key])) is None:
            raise ReferenceVerificationError(f"{key} is unsupported")
    descriptors = manifest["artifact_descriptors"]
    if not isinstance(descriptors, list) or not descriptors:
        raise ReferenceVerificationError("bundle descriptors are unavailable")
    descriptor_mappings: list[Mapping[str, Any]] = []
    for descriptor_value in descriptors:
        descriptor = _require_mapping(descriptor_value, "artifact descriptor")
        _validate_descriptor_shape(descriptor)
        descriptor_mappings.append(descriptor)
    expected_order = sorted(
        descriptor_mappings,
        key=lambda item: (item["logical_role"], item["logical_id"], item["sha256"]),
    )
    if descriptor_mappings != expected_order:
        raise ReferenceVerificationError("bundle descriptors are not canonically ordered")
    identities = [(item["logical_role"], item["logical_id"]) for item in descriptor_mappings]
    if len(set(identities)) != len(identities):
        raise ReferenceVerificationError("bundle descriptor identities are duplicated")
    identity_set = set(identities)
    for descriptor in descriptor_mappings:
        _verify_evidence_refs(descriptor, identity_set)
    roles = {item["logical_role"] for item in descriptor_mappings}
    if len(roles) != len(descriptor_mappings):
        raise ReferenceVerificationError("bundle logical roles are duplicated")
    if not REQUIRED_LOGICAL_ROLES <= roles:
        raise ReferenceVerificationError("bundle required role is missing")
    if "reproduces_run_id" in manifest and "reproduction_comparison" not in roles:
        raise ReferenceVerificationError("bundle reproduction comparison is missing")
    if "reproduction_comparison" in roles and "reproduces_run_id" not in manifest:
        raise ReferenceVerificationError("bundle reproduction comparison is unexpected")

    core = {key: value for key, value in manifest.items() if key != "bundle_manifest_hash"}
    if manifest["bundle_manifest_hash"] != sha256(core):
        raise ReferenceVerificationError("bundle manifest hash does not match")

    payloads: dict[str, object | list[object] | None] = {}
    for descriptor in descriptor_mappings:
        role = str(descriptor["logical_role"])
        payloads[role] = _descriptor_payload(artifact_root, descriptor)

    request = _require_mapping(payloads["engine_request"], "engine request")
    from .analysis_runs import scientific_sha256

    if manifest["scientific_request_digest"] not in {
        sha256(request),
        scientific_sha256(request),
    }:
        raise ReferenceVerificationError("scientific request digest does not match")
    _require_text(request.get("engine_input_schema_version"), "engine input schema")
    dataset_version_id = _require_identifier(
        request.get("dataset_version_id"), "dataset version"
    )
    intended_role = _require_identifier(request.get("intended_role"), "intended role")
    payloads["dataset_version_id"] = dataset_version_id
    payloads["intended_role"] = intended_role

    runtime = _require_mapping(payloads["runtime_fingerprint"], "runtime fingerprint")
    if manifest["runtime_fingerprint_digest"] not in {
        sha256(runtime),
        scientific_sha256(runtime),
    }:
        raise ReferenceVerificationError("runtime fingerprint digest does not match")
    if dict(runtime) != dict(expected_runtime):
        raise ReferenceVerificationError("runtime fingerprint does not match current release")

    result = _require_mapping(payloads["engine_result"], "engine result")
    result_status = result.get("status", result.get("engine_result_status"))
    if result_status != manifest["engine_result_status"]:
        raise ReferenceVerificationError("engine result status does not match")
    engine_output_schema_version = _require_text(
        result.get("schema_version"), "engine result schema"
    )
    expected_cache_key = build_cache_key(
        scientific_request_digest=str(manifest["scientific_request_digest"]),
        runtime_fingerprint_digest=str(manifest["runtime_fingerprint_digest"]),
        engine_output_schema_version=engine_output_schema_version,
    )
    if expected_cache_key != manifest["cache_key"]:
        raise ReferenceVerificationError("cache key does not match bundle identity")

    report = _require_mapping(payloads["verification_report"], "verification report")
    _require_exact_keys(
        report,
        _VERIFICATION_REQUIRED_KEYS,
        frozenset(),
        "verification report",
    )
    if report["schema_version"] != VERIFICATION_REPORT_SCHEMA_VERSION:
        raise ReferenceVerificationError("verification report schema is unsupported")
    _require_identifier(report["validation_policy_version"], "validation policy version")
    if report["status"] != "passed":
        raise ReferenceVerificationError("verification report did not pass")
    _require_passed_checks(report["checks"], "verification checks")
    if "reproduction_comparison" in roles:
        comparison = _require_mapping(
            payloads["reproduction_comparison"], "reproduction comparison"
        )
        if comparison.get("schema_version") != REPRODUCTION_COMPARISON_SCHEMA_VERSION:
            raise ReferenceVerificationError("reproduction comparison schema is unsupported")
        if comparison.get("status") != "passed":
            raise ReferenceVerificationError("reproduction comparison did not pass")
        if comparison.get("target_run_id") != manifest.get("reproduces_run_id"):
            raise ReferenceVerificationError("reproduction target binding does not match")
        if comparison.get("scientific_request_digest") != manifest.get(
            "scientific_request_digest"
        ) or comparison.get("runtime_fingerprint_digest") != manifest.get(
            "runtime_fingerprint_digest"
        ):
            raise ReferenceVerificationError("reproduction identity does not match")
        declared_tolerances = comparison.get("declared_tolerances")
        from .analysis_runs import (
            NUMERIC_TOLERANCE_REGISTRY,
            REPRODUCTION_PROJECTION_SCHEMA_VERSION,
            build_reproduction_projection,
            compare_reproduction_projections,
        )

        if declared_tolerances != NUMERIC_TOLERANCE_REGISTRY:
            raise ReferenceVerificationError("reproduction tolerances are unsupported")
        expected_projection = comparison.get("expected_projection")
        observed_projection = comparison.get("observed_projection")
        if not isinstance(expected_projection, Mapping) or not isinstance(
            observed_projection, Mapping
        ) or expected_projection.get("schema_version") != REPRODUCTION_PROJECTION_SCHEMA_VERSION or observed_projection.get(
            "schema_version"
        ) != REPRODUCTION_PROJECTION_SCHEMA_VERSION:
            raise ReferenceVerificationError("reproduction projections are unsupported")
        for projection in (expected_projection, observed_projection):
            projection_values = projection.get("projections")
            role_digests = projection.get("role_digests")
            if not isinstance(projection_values, Mapping) or not isinstance(
                role_digests, Mapping
            ):
                raise ReferenceVerificationError(
                    "reproduction projection values are unsupported"
                )
            recomputed_projection = build_reproduction_projection(projection_values)
            if (
                projection.get("roles") != recomputed_projection["roles"]
                or role_digests != recomputed_projection["role_digests"]
                or projection.get("projection_digest")
                != recomputed_projection["projection_digest"]
            ):
                raise ReferenceVerificationError(
                    "reproduction projection identity is inconsistent"
                )
        checked_comparison = compare_reproduction_projections(
            expected_projection,
            observed_projection,
            expected_member_hashes=expected_projection["role_digests"],
            observed_member_hashes=observed_projection["role_digests"],
        )
        if checked_comparison["status"] != "passed":
            raise ReferenceVerificationError("reproduction comparison is inconsistent")
        if comparison.get("member_hashes") != {
            "expected": dict(expected_projection["role_digests"]),
            "observed": dict(observed_projection["role_digests"]),
        }:
            raise ReferenceVerificationError("reproduction member hashes are inconsistent")
        if comparison.get("comparison_classes") != checked_comparison["comparison_classes"]:
            raise ReferenceVerificationError("reproduction comparison identity is inconsistent")
    if is_synthetic_fixture_identity(manifest) or is_synthetic_fixture_identity(payloads):
        raise ReferenceVerificationError(
            "synthetic conformance fixtures cannot enter analysis evidence paths"
        )
    return manifest, payloads


def _registry_entries(
    artifact_root: Path,
    release_candidate_id: str,
    *,
    include_inactive: bool = False,
) -> list[Mapping[str, Any]]:
    registry_path = _under(
        artifact_root,
        artifact_root / "releases" / release_candidate_id / "validated-references.json",
    )
    if not _regular_file(registry_path):
        return []
    registry = _require_mapping(
        _read_canonical_file(registry_path, "validated reference registry"),
        "validated reference registry",
    )
    _require_exact_keys(
        registry,
        _REGISTRY_REQUIRED_KEYS,
        _REGISTRY_OPTIONAL_KEYS,
        "validated reference registry",
    )
    schema = registry.get("registry_schema_version", registry.get("schema_version"))
    if schema != REFERENCE_REGISTRY_SCHEMA_VERSION:
        raise ReferenceVerificationError("validated reference registry schema is unsupported")
    if "registry_schema_version" in registry and "schema_version" in registry and registry["registry_schema_version"] != registry["schema_version"]:
        raise ReferenceVerificationError("validated reference registry schema disagrees")
    for key in ("release_candidate_id", "release_id"):
        if key in registry and registry[key] != release_candidate_id:
            raise ReferenceVerificationError("validated reference release does not match")
    entries = registry["entries"]
    if not isinstance(entries, list) or not entries:
        raise ReferenceVerificationError("validated reference registry is empty")
    normalized: list[Mapping[str, Any]] = []
    for entry_value in entries:
        entry = _require_mapping(entry_value, "validated reference entry")
        _require_exact_keys(entry, _ENTRY_REQUIRED_KEYS, _ENTRY_OPTIONAL_KEYS, "validated reference entry")
        _require_identifier(entry["reference_slot_id"], "reference slot")
        if _RUN_ID.fullmatch(str(entry["analysis_run_id"])) is None:
            raise ReferenceVerificationError("validated reference run id is unsupported")
        _require_digest(entry["bundle_manifest_hash"], "validated reference bundle hash")
        _require_identifier(entry["validation_attestation_id"], "validation attestation id")
        if "validation_attestation_ref" in entry:
            attestation_ref = entry["validation_attestation_ref"]
            if _DIGEST.fullmatch(str(attestation_ref)) is None:
                _require_identifier(attestation_ref, "validation attestation reference")
            if (
                _DIGEST.fullmatch(str(attestation_ref)) is None
                and attestation_ref != entry["validation_attestation_id"]
            ):
                raise ReferenceVerificationError("validated reference attestation binding does not match")
        if entry["read_model_schema_version"] != READ_MODEL_SCHEMA_VERSION:
            raise ReferenceVerificationError("validated reference read model is unsupported")
        _require_identifier(entry["intended_role"], "validated reference intended role")
        if (
            not include_inactive
            and (entry.get("status", "active") != "active" or bool(entry.get("revoked", False)))
        ):
            continue
        normalized.append(entry)
    if len({entry["reference_slot_id"] for entry in normalized}) != len(normalized):
        raise ReferenceVerificationError("validated reference slots are duplicated")
    return normalized


class ValidatedReferenceStore:
    """Verifier, promoter, and deterministic selector for reusable runs."""

    def __init__(
        self,
        artifact_root: Path,
        *,
        release_candidate_id: str,
        runtime_fingerprint: Mapping[str, Any],
    ) -> None:
        self._artifact_root = artifact_root
        self._release_candidate_id = release_candidate_id
        self._runtime_fingerprint = dict(runtime_fingerprint)
        self._lock = RLock()

    @property
    def registry_path(self) -> Path:
        return self._artifact_root / "releases" / self._release_candidate_id / "validated-references.json"

    @property
    def registry_present(self) -> bool:
        return _regular_file(self.registry_path)

    @property
    def expected_build_id(self) -> str:
        build_id = self._runtime_fingerprint.get("build_manifest_id")
        if isinstance(build_id, str) and build_id:
            return build_id
        application_build_id = self._runtime_fingerprint.get("application_build_id")
        if isinstance(application_build_id, str) and application_build_id:
            return application_build_id
        return ""

    def _verify_run(
        self,
        analysis_run_id: str,
        *,
        quarantine_on_failure: bool = True,
    ) -> tuple[Mapping[str, Any], dict[str, object | list[object] | None]]:
        if self._runtime_fingerprint.get("release_candidate_id") != self._release_candidate_id:
            raise ReferenceVerificationError("runtime release does not match current release")
        if _run_is_quarantined(self._artifact_root, analysis_run_id):
            raise ReferenceVerificationError("analysis run is quarantined")
        try:
            return _verify_bundle(
                self._artifact_root,
                analysis_run_id,
                self.expected_build_id,
                self._runtime_fingerprint,
            )
        except ReferenceVerificationError:
            if quarantine_on_failure:
                _quarantine_verification_failure(
                    self._artifact_root,
                    analysis_run_id,
                )
            raise

    def _verify_entry(
        self,
        entry: Mapping[str, Any],
        *,
        quarantine_on_failure: bool = True,
    ) -> ValidatedReference:
        manifest, payloads = self._verify_run(
            str(entry["analysis_run_id"]),
            quarantine_on_failure=quarantine_on_failure,
        )
        if is_synthetic_fixture_identity(payloads) or is_synthetic_fixture_identity(entry):
            raise ReferenceVerificationError(
                "synthetic conformance fixtures cannot enter the reference registry"
            )
        if manifest["bundle_manifest_hash"] != entry["bundle_manifest_hash"]:
            raise ReferenceVerificationError("validated reference bundle binding does not match")
        if payloads.get("intended_role") != entry["intended_role"]:
            raise ReferenceVerificationError("validated reference role does not match")

        attestation_ref = entry.get("validation_attestation_ref")
        if attestation_ref is not None and _DIGEST.fullmatch(str(attestation_ref)) is None:
            _require_identifier(attestation_ref, "validation attestation reference")
        attestation_path = _attestation_path(
            self._artifact_root,
            str(entry["validation_attestation_id"]),
            str(attestation_ref) if attestation_ref is not None else None,
        )
        attestation = _require_mapping(
            _read_canonical_file(attestation_path, "validation attestation"),
            "validation attestation",
        )
        if attestation_ref is not None:
            try:
                attestation_bytes = attestation_path.read_bytes()
            except OSError as error:
                raise ReferenceVerificationError("validation attestation is unavailable") from error
            if sha256(attestation_bytes) != attestation_ref:
                raise ReferenceVerificationError("validation attestation content hash does not match")
        _require_exact_keys(
            attestation,
            _ATTESTATION_REQUIRED_KEYS,
            _ATTESTATION_OPTIONAL_KEYS,
            "validation attestation",
        )
        if attestation["attestation_schema_version"] != VALIDATION_ATTESTATION_SCHEMA_VERSION:
            raise ReferenceVerificationError("validation attestation schema is unsupported")
        if attestation["validation_attestation_id"] != entry["validation_attestation_id"]:
            raise ReferenceVerificationError("validation attestation identity does not match")
        if attestation["analysis_run_id"] != entry["analysis_run_id"]:
            raise ReferenceVerificationError("validation attestation run does not match")
        for key in ("bundle_manifest_hash", "scientific_request_digest", "runtime_fingerprint_digest"):
            if attestation[key] != manifest[key]:
                raise ReferenceVerificationError("validation attestation bundle identity does not match")
        if attestation["release_candidate_id"] != self._release_candidate_id:
            raise ReferenceVerificationError("validation attestation release does not match")
        if attestation.get("release_id", self._release_candidate_id) != self._release_candidate_id:
            raise ReferenceVerificationError("validation attestation release does not match")
        if attestation["reference_slot_id"] != entry["reference_slot_id"]:
            raise ReferenceVerificationError("validation attestation slot does not match")
        if attestation["status"] != "passed":
            raise ReferenceVerificationError("validation attestation did not pass")
        _require_identifier(
            attestation["validation_policy_version"], "validation policy version"
        )
        _require_passed_checks(attestation["checks"], "validation attestation checks")
        if attestation.get("content_hash") is not None:
            _require_digest(attestation["content_hash"], "validation attestation content hash")
            if attestation["content_hash"] != attestation_ref:
                raise ReferenceVerificationError("validation attestation content hash does not match")
        for key, expected in (
            ("run_status", "SUCCEEDED"),
            ("lifecycle", "sealed"),
            ("availability_state", "available"),
        ):
            if key in attestation and attestation[key] != expected:
                raise ReferenceVerificationError("validation attestation run state is unusable")
        if bool(attestation.get("revoked", False)):
            raise ReferenceVerificationError("validation attestation is revoked")
        report = _require_mapping(payloads["verification_report"], "verification report")
        if report["validation_policy_version"] != attestation["validation_policy_version"]:
            raise ReferenceVerificationError("validation policy does not match")
        validated_at = _require_utc_timestamp(attestation["validated_at"], "validation timestamp")
        diagnostic_descriptor = next(
            descriptor
            for descriptor in manifest["artifact_descriptors"]
            if descriptor["logical_role"] == "diagnostic_artifacts"
        )
        try:
            diagnostic_payload = payloads.get("diagnostic_artifacts")
            if diagnostic_payload is not None and not isinstance(
                diagnostic_payload, (Mapping, list)
            ):
                raise DiagnosticIntegrityError("diagnostic payload is unsupported")
            validity_results = publish_validity_results(
                diagnostic_payload,
                analysis_run_id=str(entry["analysis_run_id"]),
                bundle_manifest_hash=str(entry["bundle_manifest_hash"]),
                evidence_refs=diagnostic_descriptor["evidence_refs"],
                input_refs=["diagnostic_artifacts:" + str(diagnostic_descriptor["logical_id"])],
            )
        except DiagnosticIntegrityError as error:
            raise ReferenceVerificationError("diagnostic artifact is invalid") from error
        except ValueError as error:
            raise ReferenceVerificationError("validity artifact is invalid") from error
        return ValidatedReference(
            reference_slot_id=str(entry["reference_slot_id"]),
            analysis_run_id=str(entry["analysis_run_id"]),
            bundle_manifest_hash=str(entry["bundle_manifest_hash"]),
            validation_attestation_id=str(entry["validation_attestation_id"]),
            validation_attestation_ref=str(
                entry.get("validation_attestation_ref", entry["validation_attestation_id"])
            ),
            release_candidate_id=self._release_candidate_id,
            intended_role=str(entry["intended_role"]),
            engine_result_status=str(manifest["engine_result_status"]),
            scientific_request_digest=str(manifest["scientific_request_digest"]),
            dataset_version_id=str(payloads["dataset_version_id"]),
            cache_key=str(manifest["cache_key"]),
            runtime_fingerprint_digest=str(manifest["runtime_fingerprint_digest"]),
            validation_policy_version=str(attestation["validation_policy_version"]),
            validated_at=validated_at,
            completed_at=_require_utc_timestamp(manifest["completed_at"], "bundle completion time"),
            diagnostic_results=tuple(validity_results["diagnostics"]),
            robustness_grade=validity_results["robustness_grade"],
            evidence_verdict=validity_results["evidence_verdict"],
        )

    def validate_current_release_manifest(self) -> tuple[ValidatedReference, ...]:
        """Verify every active current-release reference before local startup."""

        with self._lock:
            if not self.registry_present:
                return ()
            entries = _registry_entries(self._artifact_root, self._release_candidate_id)
            verified = tuple(
                self._verify_entry(entry, quarantine_on_failure=False)
                for entry in entries
            )
            if not verified:
                raise ReferenceVerificationError(
                    "validated reference registry has no active verified entries"
                )
            return tuple(sorted(verified, key=lambda item: (item.completed_at, item.analysis_run_id)))

    def list_verified_references(self) -> list[ValidatedReference]:
        with self._lock:
            if not self.registry_present:
                return []
            try:
                entries = _registry_entries(self._artifact_root, self._release_candidate_id)
            except ReferenceVerificationError:
                return []
            verified: list[ValidatedReference] = []
            for entry in entries:
                if is_synthetic_fixture_identity(entry):
                    continue
                try:
                    verified.append(self._verify_entry(entry))
                except ReferenceVerificationError:
                    try:
                        _quarantine_verification_failure(
                            self._artifact_root,
                            str(entry["analysis_run_id"]),
                        )
                    except ReferenceVerificationError:
                        pass
                    continue
            return sorted(
                verified,
                key=lambda item: (item.completed_at, item.analysis_run_id),
            )

    def list_verified_runs(self) -> list[AnalysisRunCacheCandidate]:
        """Return sealed current-release runs eligible for deterministic reuse."""

        with self._lock:
            runs_root = self._artifact_root / "runs"
            if not _regular_directory(runs_root):
                return []
            try:
                run_directories = sorted(runs_root.iterdir(), key=lambda path: path.name)
            except OSError:
                return []
            verified: list[AnalysisRunCacheCandidate] = []
            for run_directory in run_directories:
                if not _regular_directory(run_directory) or _RUN_ID.fullmatch(run_directory.name) is None:
                    continue
                try:
                    manifest, payloads = self._verify_run(run_directory.name)
                    if is_synthetic_fixture_identity(manifest) or is_synthetic_fixture_identity(
                        payloads
                    ):
                        continue
                    verified.append(
                        AnalysisRunCacheCandidate(
                            analysis_run_id=run_directory.name,
                            bundle_manifest_hash=str(manifest["bundle_manifest_hash"]),
                            release_candidate_id=self._release_candidate_id,
                            intended_role=str(payloads["intended_role"]),
                            engine_result_status=str(manifest["engine_result_status"]),
                            scientific_request_digest=str(
                                manifest["scientific_request_digest"]
                            ),
                            dataset_version_id=str(payloads["dataset_version_id"]),
                            cache_key=str(manifest["cache_key"]),
                            runtime_fingerprint_digest=str(
                                manifest["runtime_fingerprint_digest"]
                            ),
                            completed_at=_require_utc_timestamp(
                                manifest["completed_at"], "bundle completion time"
                            ),
                            run_relationship=(
                                "reproduction"
                                if isinstance(manifest.get("reproduces_run_id"), str)
                                else "fresh"
                            ),
                            reproduces_run_id=(
                                manifest.get("reproduces_run_id")
                                if isinstance(manifest.get("reproduces_run_id"), str)
                                else None
                            ),
                        )
                    )
                except (OSError, TypeError, ValueError, ReferenceVerificationError):
                    continue
            return sorted(
                verified,
                key=lambda item: (item.completed_at, item.analysis_run_id),
            )

    @staticmethod
    def _matches_candidate(
        candidate: AnalysisRunCacheCandidate | ValidatedReference,
        reference_slot_id: str | None,
        intended_role: str | None,
        scientific_request_digest: str | None,
        cache_key: str | None,
    ) -> bool:
        if (
            reference_slot_id is not None
            and candidate.reference_slot_id is not None
            and candidate.reference_slot_id != reference_slot_id
        ):
            return False
        if intended_role is not None and candidate.intended_role != intended_role:
            return False
        if (
            scientific_request_digest is not None
            and candidate.scientific_request_digest != scientific_request_digest
        ):
            return False
        if cache_key is not None and candidate.cache_key != cache_key:
            return False
        return True

    def select_cache_candidate(
        self,
        reference_slot_id: str | None = None,
        *,
        intended_role: str | None = None,
        scientific_request_digest: str | None = None,
        cache_key: str | None = None,
    ) -> AnalysisRunCacheCandidate | ValidatedReference | None:
        """Select a reference first, then the earliest verified current-release run."""

        if scientific_request_digest is not None:
            _require_digest(scientific_request_digest, "scientific request digest")
        if cache_key is not None:
            _require_digest(cache_key, "cache key")

        references = [
            item
            for item in self.list_verified_references()
            if self._matches_candidate(
                item,
                reference_slot_id,
                intended_role,
                scientific_request_digest,
                cache_key,
            )
        ]
        if references:
            return references[0]

        runs = [
            item
            for item in self.list_verified_runs()
            if self._matches_candidate(
                item,
                reference_slot_id,
                intended_role,
                scientific_request_digest,
                cache_key,
            )
        ]
        return runs[0] if runs else None

    def read_cache_model(
        self,
        reference_slot_id: str | None = None,
        *,
        intended_role: str | None = None,
        scientific_request_digest: str | None = None,
        cache_key: str | None = None,
    ) -> AnalysisRunCacheCandidate | ValidatedReference | None:
        """Return only the identity-safe cache projection used by delivery code."""

        return self.select_cache_candidate(
            reference_slot_id,
            intended_role=intended_role,
            scientific_request_digest=scientific_request_digest,
            cache_key=cache_key,
        )

    def read_artifact_status(self, analysis_run_id: str) -> ArtifactReadStatus:
        """Return an identity-safe lifecycle projection for one analysis run."""

        bundle_manifest_hash: str | None = None
        with self._lock:
            try:
                manifest, _ = self._verify_run(analysis_run_id)
                bundle_manifest_hash = str(manifest["bundle_manifest_hash"])
            except (ReferenceVerificationError, OSError, TypeError, ValueError):
                pass
            return artifact_read_status(
                self._artifact_root,
                analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
            )

    def verify_analysis_run(self, analysis_run_id: str) -> str:
        """Verify one sealed run for operator recovery without exposing artifact bytes."""

        with self._lock:
            try:
                manifest, _ = self._verify_run(
                    analysis_run_id,
                    quarantine_on_failure=False,
                )
            except (ReferenceVerificationError, OSError, TypeError, ValueError) as error:
                raise ReferenceVerificationError(
                    "analysis run failed recovery verification"
                ) from error
            bundle_manifest_hash = manifest.get("bundle_manifest_hash")
            if not isinstance(bundle_manifest_hash, str):
                raise ReferenceVerificationError(
                    "analysis run bundle identity is unavailable"
                )
            return bundle_manifest_hash

    def promote_reference(
        self,
        analysis_run_id: str,
        reference_slot_id: str,
        *,
        now: datetime | None = None,
        intended_role: str | None = None,
    ) -> ReferencePromotion:
        """Promote one fully verified, reproducible run without mutating its bundle."""

        with self._lock:
            try:
                manifest, payloads = self._verify_run(analysis_run_id)
            except ReferenceVerificationError as error:
                raise ReferencePromotionError(str(error)) from error

            report = _require_mapping(payloads["verification_report"], "verification report")
            checks = report.get("checks")
            if not isinstance(checks, list):
                raise ReferencePromotionError("reference verification gates are incomplete")
            check_ids = {
                str(check.get("check_id"))
                for check in checks
                if isinstance(check, Mapping)
            }
            if not {"provenance", "provenance_integrity"} & check_ids:
                raise ReferencePromotionError("reference provenance gate is incomplete")
            if not (
                {"reproduction", "reproducibility", "reproduction_integrity"} & check_ids
                or isinstance(manifest.get("reproduces_run_id"), str)
            ):
                raise ReferencePromotionError("reference reproduction gate is incomplete")

            observed_role = str(payloads["intended_role"])
            if intended_role is not None and intended_role != observed_role:
                raise ReferencePromotionError("reference intended role does not match")
            if manifest.get("investigation_request_id") is None:
                raise ReferencePromotionError("reference provenance identity is unavailable")
            try:
                investigation_request_id = _require_identifier(
                    manifest["investigation_request_id"],
                    "investigation request identity",
                )
            except ReferenceVerificationError as error:
                raise ReferencePromotionError(str(error)) from error

            completed_at = _require_utc_timestamp(
                manifest["completed_at"], "bundle completion time"
            )
            validation_time = now or datetime.now(timezone.utc)
            if validation_time.tzinfo is None:
                validation_time = validation_time.replace(tzinfo=timezone.utc)
            else:
                validation_time = validation_time.astimezone(timezone.utc)
            if validation_time < completed_at:
                raise ReferencePromotionError("reference run is stale at validation time")

            registry_path = self.registry_path
            existing_entries: list[Mapping[str, Any]] = []
            existing_registry: Mapping[str, Any] | None = None
            if registry_path.exists():
                try:
                    existing_registry = _require_mapping(
                        _read_canonical_file(registry_path, "validated reference registry"),
                        "validated reference registry",
                    )
                    existing_entries = _registry_entries(
                        self._artifact_root,
                        self._release_candidate_id,
                        include_inactive=True,
                    )
                except ReferenceVerificationError as error:
                    raise ReferencePromotionError(str(error)) from error

            request_digest = str(manifest["scientific_request_digest"])
            runtime_digest = str(manifest["runtime_fingerprint_digest"])
            bundle_hash = str(manifest["bundle_manifest_hash"])
            for entry in existing_entries:
                same_run = entry.get("analysis_run_id") == analysis_run_id
                if not same_run:
                    continue
                if entry.get("status", "active") != "active" or bool(
                    entry.get("revoked", False)
                ):
                    raise ReferencePromotionError("reference source run is revoked")
                if (
                    entry.get("reference_slot_id") == reference_slot_id
                    and entry.get("bundle_manifest_hash") == bundle_hash
                ):
                    try:
                        reference = self._verify_entry(entry)
                    except ReferenceVerificationError as error:
                        raise ReferencePromotionError(str(error)) from error
                    return ReferencePromotion(
                        reference=reference,
                        validation_attestation_id=reference.validation_attestation_id,
                        validation_attestation_ref=reference.validation_attestation_ref,
                        created=False,
                    )
                raise ReferencePromotionError("reference source run is already promoted")
            if existing_registry is not None:
                raise ReferencePromotionError("validated reference registry is immutable")

            gate_checks = [
                {
                    "check_id": "release_identity",
                    "status": "passed",
                    "evidence_digest": sha256(
                        {
                            "release_candidate_id": self._release_candidate_id,
                            "build_manifest_id": self.expected_build_id,
                        }
                    ),
                },
                {
                    "check_id": "scientific_request_identity",
                    "status": "passed",
                    "evidence_digest": sha256(
                        {
                            "scientific_request_digest": request_digest,
                            "dataset_version_id": payloads["dataset_version_id"],
                            "intended_role": observed_role,
                        }
                    ),
                },
                {
                    "check_id": "runtime_fingerprint",
                    "status": "passed",
                    "evidence_digest": sha256(
                        {
                            "runtime_fingerprint_digest": runtime_digest,
                            "runtime_fingerprint": self._runtime_fingerprint,
                        }
                    ),
                },
                {
                    "check_id": "verification_report",
                    "status": "passed",
                    "evidence_digest": sha256(report),
                },
                {
                    "check_id": "reproduction",
                    "status": "passed",
                    "evidence_digest": sha256(
                        {
                            "reproduces_run_id": manifest.get("reproduces_run_id"),
                            "verification_check_ids": sorted(check_ids),
                        }
                    ),
                },
                {
                    "check_id": "provenance",
                    "status": "passed",
                    "evidence_digest": sha256(
                        {
                            "investigation_request_id": investigation_request_id,
                            "dataset_version_id": payloads["dataset_version_id"],
                            "bundle_manifest_hash": bundle_hash,
                        }
                    ),
                },
            ]
            validation_policy_version = report.get("validation_policy_version")
            try:
                policy_version = _require_identifier(
                    validation_policy_version,
                    "validation policy version",
                )
            except ReferenceVerificationError as error:
                raise ReferencePromotionError(str(error)) from error
            attestation_basis = {
                "schema_version": REFERENCE_PROMOTION_SCHEMA_VERSION,
                "analysis_run_id": analysis_run_id,
                "bundle_manifest_hash": bundle_hash,
                "scientific_request_digest": request_digest,
                "runtime_fingerprint_digest": runtime_digest,
                "release_candidate_id": self._release_candidate_id,
                "reference_slot_id": reference_slot_id,
                "validation_policy_version": policy_version,
                "validated_at": validation_time.isoformat(),
                "checks": gate_checks,
            }
            validation_attestation_id = "attestation-" + sha256(attestation_basis)[7:]
            attestation = {
                "attestation_schema_version": VALIDATION_ATTESTATION_SCHEMA_VERSION,
                "validation_attestation_id": validation_attestation_id,
                "analysis_run_id": analysis_run_id,
                "bundle_manifest_hash": bundle_hash,
                "scientific_request_digest": request_digest,
                "runtime_fingerprint_digest": runtime_digest,
                "release_candidate_id": self._release_candidate_id,
                "release_id": self._release_candidate_id,
                "reference_slot_id": reference_slot_id,
                "validation_policy_version": policy_version,
                "status": "passed",
                "checks": gate_checks,
                "validated_at": validation_time.isoformat(),
                "run_status": "SUCCEEDED",
                "lifecycle": "sealed",
                "availability_state": "available",
                "run_relationship": (
                    "reproduction"
                    if isinstance(manifest.get("reproduces_run_id"), str)
                    else "fresh"
                ),
            }
            attestation_bytes = _canonical_bytes(attestation)
            attestation_ref = sha256(attestation_bytes)
            attestation_path = _attestation_path(
                self._artifact_root,
                validation_attestation_id,
                attestation_ref,
            )
            if attestation_path.exists():
                try:
                    if attestation_path.read_bytes() != attestation_bytes:
                        raise ReferencePromotionError(
                            "validation attestation content collision"
                        )
                except OSError as error:
                    raise ReferencePromotionError(
                        "validation attestation is unavailable"
                    ) from error
            else:
                _write_atomic(attestation_path, attestation_bytes)

            entry: dict[str, Any] = {
                "reference_slot_id": reference_slot_id,
                "analysis_run_id": analysis_run_id,
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": validation_attestation_id,
                "validation_attestation_ref": attestation_ref,
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": observed_role,
                "status": "active",
                "revoked": False,
            }
            try:
                reference = self._verify_entry(entry)
            except ReferenceVerificationError as error:
                raise ReferencePromotionError(str(error)) from error

            new_entries = list(existing_entries)
            new_entries.append(entry)
            new_entries.sort(
                key=lambda item: (
                    str(item["reference_slot_id"]),
                    str(item["analysis_run_id"]),
                    str(item["bundle_manifest_hash"]),
                    str(item["validation_attestation_ref"]),
                )
            )
            registry = {
                "registry_schema_version": REFERENCE_REGISTRY_SCHEMA_VERSION,
                "release_candidate_id": self._release_candidate_id,
                "release_id": self._release_candidate_id,
                "entries": new_entries,
            }
            _write_atomic(registry_path, _canonical_bytes(registry))
            try:
                verified_reference = self._verify_entry(entry)
            except ReferenceVerificationError as error:
                raise ReferencePromotionError(str(error)) from error
            return ReferencePromotion(
                reference=verified_reference,
                validation_attestation_id=validation_attestation_id,
                validation_attestation_ref=attestation_ref,
                created=True,
            )

    def select_reference(
        self,
        reference_slot_id: str | None = None,
        *,
        intended_role: str | None = None,
        scientific_request_digest: str | None = None,
        cache_key: str | None = None,
    ) -> ValidatedReference | None:
        references = self.list_verified_references()
        if reference_slot_id is not None:
            references = [
                item for item in references if item.reference_slot_id == reference_slot_id
            ]
        if intended_role is not None:
            references = [item for item in references if item.intended_role == intended_role]
        if scientific_request_digest is not None:
            _require_digest(scientific_request_digest, "scientific request digest")
            references = [
                item
                for item in references
                if item.scientific_request_digest == scientific_request_digest
            ]
        if cache_key is not None:
            _require_digest(cache_key, "cache key")
            references = [item for item in references if item.cache_key == cache_key]
        return references[0] if references else None

    def read_model(
        self,
        reference_slot_id: str | None = None,
        *,
        intended_role: str | None = None,
        scientific_request_digest: str | None = None,
        cache_key: str | None = None,
    ) -> ValidatedReference | None:
        """Return only the closed reference delivery DTO, never artifact bytes or paths."""

        selected = self.select_reference(
            reference_slot_id,
            intended_role=intended_role,
            scientific_request_digest=scientific_request_digest,
            cache_key=cache_key,
        )
        if selected is not None or reference_slot_id is None:
            return selected
        return self.select_reference(
            intended_role=intended_role,
            scientific_request_digest=scientific_request_digest,
            cache_key=cache_key,
        )

    def is_verified(self, reference_slot_id: str) -> bool:
        return self.select_reference(reference_slot_id) is not None


def promote_validated_reference(
    artifact_root: Path,
    *,
    analysis_run_id: str,
    reference_slot_id: str,
    release_candidate_id: str,
    runtime_fingerprint: Mapping[str, Any],
    now: datetime | None = None,
    intended_role: str | None = None,
) -> ReferencePromotion:
    """Promote a run using the same verifier used for every later read."""

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=release_candidate_id,
        runtime_fingerprint=runtime_fingerprint,
    )
    return store.promote_reference(
        analysis_run_id,
        reference_slot_id,
        now=now,
        intended_role=intended_role,
    )


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _member_descriptor(member: ArtifactMember) -> dict[str, Any]:
    if not isinstance(member.content, bytes):
        raise ValueError("artifact member content must be bytes")
    descriptor: dict[str, Any] = {
        "descriptor_schema_version": ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
        "logical_role": member.logical_role,
        "logical_id": member.logical_id,
        "producer_schema_id": member.producer_schema_id,
        "producer_schema_version": member.producer_schema_version,
        "media_type": member.media_type,
        "sha256": sha256(member.content),
        "byte_count": len(member.content),
        "confidentiality_class": member.confidentiality_class,
        "evidence_refs": list(member.evidence_refs),
    }
    if member.scientific_content_digest is not None:
        descriptor["scientific_content_digest"] = member.scientific_content_digest
    if member.record_count is not None:
        descriptor["record_count"] = member.record_count
    if member.array_shape is not None:
        descriptor["array_shape"] = list(member.array_shape)
    if member.array_dtype is not None:
        descriptor["array_dtype"] = member.array_dtype
    if member.array_order is not None:
        descriptor["array_order"] = member.array_order
    return descriptor


def publish_analysis_bundle(
    artifact_root: Path,
    *,
    analysis_run_id: str,
    manifest: Mapping[str, Any],
    members: Iterable[ArtifactMember],
) -> PublishedBundle:
    """Publish verified member bytes and seal their manifest last on one filesystem."""

    if _RUN_ID.fullmatch(analysis_run_id) is None:
        raise ValueError("analysis run id is unsupported")
    if is_analysis_run_quarantined(artifact_root, analysis_run_id):
        raise ValueError("analysis run is quarantined")
    if "artifact_descriptors" in manifest or "bundle_manifest_hash" in manifest:
        raise ValueError("publisher accepts only the manifest core")
    manifest_core = dict(manifest)
    manifest_core["analysis_run_id"] = analysis_run_id
    if is_synthetic_fixture_identity(manifest_core):
        raise ValueError("synthetic conformance fixtures cannot be published as analysis evidence")
    missing = _MANIFEST_REQUIRED_KEYS - {"artifact_descriptors", "bundle_manifest_hash"} - set(manifest_core)
    if missing:
        raise ValueError("manifest core is incomplete")
    if manifest["manifest_schema_version"] != BUNDLE_MANIFEST_SCHEMA_VERSION:
        raise ValueError("bundle manifest schema is unsupported")
    if manifest["artifact_contract_version"] != ARTIFACT_CONTRACT_VERSION:
        raise ValueError("artifact contract is unsupported")
    if manifest["engine_result_status"] not in {"estimated", "abstained"}:
        raise ValueError("bundle result status is unsupported")
    descriptors: list[dict[str, Any]] = []
    member_bytes: dict[tuple[str, str], bytes] = {}
    for member in members:
        descriptor = _member_descriptor(member)
        _validate_descriptor_shape(descriptor)
        payload = _verify_media(member.content, descriptor, f"artifact {member.logical_role}")
        try:
            _verify_role_payload(descriptor, payload)
        except ReferenceVerificationError as error:
            raise ValueError(str(error)) from error
        if is_synthetic_fixture_identity(descriptor) or is_synthetic_fixture_identity(payload):
            raise ValueError("synthetic conformance fixtures cannot be published as analysis evidence")
        if member.scientific_content_digest is not None:
            observed_digest = sha256(payload) if payload is not None else None
            if observed_digest != member.scientific_content_digest:
                raise ValueError("artifact logical digest does not match")
        identity = (str(descriptor["logical_role"]), str(descriptor["logical_id"]))
        if identity in member_bytes:
            raise ValueError("artifact member identity is duplicated")
        member_bytes[identity] = member.content
        descriptors.append(descriptor)
    descriptors.sort(key=lambda item: (item["logical_role"], item["logical_id"], item["sha256"]))
    descriptor_identities = {
        (str(item["logical_role"]), str(item["logical_id"])) for item in descriptors
    }
    for descriptor in descriptors:
        _verify_evidence_refs(descriptor, descriptor_identities)
    core = manifest_core
    core["artifact_descriptors"] = descriptors
    bundle_manifest_hash = sha256(core)
    full_manifest = dict(core)
    full_manifest["bundle_manifest_hash"] = bundle_manifest_hash

    artifact_root.mkdir(parents=True, exist_ok=True)
    temporary_root = artifact_root / "temporary"
    runs_root = artifact_root / "runs"
    temporary_root.mkdir(parents=True, exist_ok=True)
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = _under(artifact_root, runs_root / analysis_run_id)
    lease = RunLease(
        artifact_root,
        analysis_run_id,
        owner_id=f"publisher-{uuid4().hex}",
    )
    ARTIFACT_MUTATION_LOCK.acquire()
    try:
        lease.acquire()
    except Exception:
        ARTIFACT_MUTATION_LOCK.release()
        raise
    stage_root: Path | None = None
    moved_global_objects: list[Path] = []
    published = False
    try:
        stage_root = _under(
            artifact_root,
            temporary_root / f".{analysis_run_id}.{uuid4().hex}",
        )
        stage_root.mkdir()
        for descriptor in descriptors:
            object_path = _object_path(stage_root, descriptor)
            content = member_bytes[(descriptor["logical_role"], descriptor["logical_id"])]
            _write_atomic(object_path, content)
        stage_manifest = _under(
            stage_root,
            stage_root / "runs" / analysis_run_id / "manifest.json",
        )
        _write_atomic(stage_manifest, _canonical_bytes(full_manifest))
        runtime_descriptor = next(
            descriptor
            for descriptor in descriptors
            if descriptor["logical_role"] == "runtime_fingerprint"
        )
        runtime = _require_mapping(
            _descriptor_payload(stage_root, runtime_descriptor),
            "runtime fingerprint",
        )
        _verify_bundle(
            stage_root,
            analysis_run_id,
            str(manifest_core["producer_application_build_id"]),
            runtime,
        )

        global_objects: list[tuple[Path, Path, bytes]] = []
        for descriptor in descriptors:
            stage_object = _object_path(stage_root, descriptor)
            global_object = _object_path(artifact_root, descriptor)
            content = member_bytes[(descriptor["logical_role"], descriptor["logical_id"])]
            if global_object.exists() and (
                not _regular_file(global_object) or global_object.read_bytes() != content
            ):
                raise ValueError("content-addressed object collision")
            global_objects.append((stage_object, global_object, content))
        if run_dir.exists():
            raise ValueError("analysis run already exists")
        run_dir.mkdir()
        for stage_object, global_object, content in global_objects:
            if global_object.exists():
                continue
            global_object.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage_object, global_object)
            moved_global_objects.append(global_object)
        os.replace(stage_manifest, run_dir / "manifest.json")
        published = True
    except Exception as error:
        quarantine_error: Exception | None = None
        if stage_root is not None and stage_root.exists():
            try:
                quarantine_staging_material(
                    artifact_root,
                    stage_root,
                    analysis_run_id,
                    reason_code="RUN_ARTIFACT_PUBLICATION_FAILED",
                    published_object_paths=tuple(moved_global_objects),
                )
            except Exception as quarantine_failure:
                quarantine_error = quarantine_failure
        if run_dir.exists() and not (run_dir / "manifest.json").exists():
            try:
                quarantine_analysis_run(
                    artifact_root,
                    analysis_run_id,
                    reason_code="RUN_ARTIFACT_PUBLICATION_FAILED",
                )
            except Exception as quarantine_failure:
                quarantine_error = quarantine_failure
        if quarantine_error is not None:
            raise ValueError("analysis run quarantine is unavailable") from error
        raise
    finally:
        if published and stage_root is not None and stage_root.exists():
            shutil.rmtree(stage_root, ignore_errors=True)
        lease.release()
        ARTIFACT_MUTATION_LOCK.release()
    return PublishedBundle(analysis_run_id, bundle_manifest_hash)


def verify_published_analysis_bundle(
    artifact_root: Path,
    *,
    analysis_run_id: str,
    expected_build_id: str,
    expected_runtime: Mapping[str, Any],
) -> PublishedBundle:
    """Verify a bundle again after its manifest has been published."""

    try:
        manifest, _ = _verify_bundle(
            artifact_root,
            analysis_run_id,
            expected_build_id,
            expected_runtime,
        )
    except ReferenceVerificationError:
        _quarantine_verification_failure(artifact_root, analysis_run_id)
        raise
    return PublishedBundle(
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=str(manifest["bundle_manifest_hash"]),
    )


def read_verified_analysis_bundle(
    artifact_root: Path,
    *,
    analysis_run_id: str,
    expected_build_id: str,
    expected_runtime: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Read a verified manifest and its safe payloads for reproduction only."""

    try:
        return _verify_bundle(
            artifact_root,
            analysis_run_id,
            expected_build_id,
            expected_runtime,
        )
    except ReferenceVerificationError:
        _quarantine_verification_failure(artifact_root, analysis_run_id)
        raise
