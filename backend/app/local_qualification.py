from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

from .canonical import canonical_json, sha256


LOCAL_FALLBACK_QUALIFICATION_SCHEMA_VERSION = "local-fallback-qualification.v1"
LOCAL_FALLBACK_QUALIFICATION_KIND = "LOCAL_FALLBACK_QUALIFICATION"
LOCAL_FALLBACK_QUALIFICATION_FILENAME = "local-fallback-qualification.json"
LOCAL_FALLBACK_QUALIFICATION_SIDECAR = "local-fallback-qualification.sha256"
FRESH_RUN_CAPABILITY_SCHEMA_VERSION = "fresh-run-capability.v1"

QUALIFICATION_STATUSES = frozenset({"QUALIFIED", "BLOCKED"})
CHECK_STATUSES = frozenset({"VERIFIED", "BLOCKED", "UNAVAILABLE", "NOT_RUN"})

REQUIRED_LOCAL_CHECK_IDS = (
    "online_setup",
    "offline_startup",
    "browser_reference_journey",
    "browser_abstention_boundary",
    "fresh_runs_under_five_minutes",
    "synthetic_fixture_boundary",
    "mandatory_claims",
    "artifact_integrity",
    "recovery_and_fallback",
    "accessibility",
    "relevant_test_suites",
)
REQUIRED_LOCAL_FALLBACK_CHECK_IDS = REQUIRED_LOCAL_CHECK_IDS

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class LocalQualificationError(ValueError):
    """A local-fallback qualification statement failed its contract."""


def build_local_qualification(
    *,
    source_commit: str,
    release_candidate_id: str,
    build_manifest_id: str,
    target: Mapping[str, Any],
    checks: Iterable[Mapping[str, Any]],
    commands: Iterable[Mapping[str, Any]],
    platform: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    """Build one immutable local-fallback qualification statement."""

    _validate_identity(source_commit, release_candidate_id, build_manifest_id)
    normalized_target = _normalize_target(target)
    _validate_timestamp(observed_at, "OBSERVED_AT")
    normalized_checks = _normalize_checks(checks)
    normalized_commands = _normalize_commands(commands)
    normalized_platform = _normalize_platform(platform)
    qualification_status = (
        "QUALIFIED"
        if all(item["status"] == "VERIFIED" for item in normalized_checks)
        else "BLOCKED"
    )
    payload: dict[str, Any] = {
        "schema_version": LOCAL_FALLBACK_QUALIFICATION_SCHEMA_VERSION,
        "qualification_kind": LOCAL_FALLBACK_QUALIFICATION_KIND,
        "qualification_status": qualification_status,
        "fresh_demo_control": (
            "ENABLED" if qualification_status == "QUALIFIED" else "DISABLED"
        ),
        "source_commit": source_commit,
        "release_candidate_id": release_candidate_id,
        "build_manifest_id": build_manifest_id,
        "target": normalized_target,
        "checks": normalized_checks,
        "commands": normalized_commands,
        "platform": normalized_platform,
        "observed_at": observed_at,
    }
    payload["content_hash"] = _content_hash(payload)
    validate_local_qualification(payload)
    return payload


def validate_local_qualification(payload: Mapping[str, Any]) -> None:
    """Validate a parsed qualification statement without filesystem access."""

    if not isinstance(payload, Mapping):
        raise LocalQualificationError("QUALIFICATION_SCHEMA_INVALID")
    if payload.get("schema_version") != LOCAL_FALLBACK_QUALIFICATION_SCHEMA_VERSION:
        raise LocalQualificationError("QUALIFICATION_SCHEMA_UNSUPPORTED")
    if payload.get("qualification_kind") != LOCAL_FALLBACK_QUALIFICATION_KIND:
        raise LocalQualificationError("QUALIFICATION_KIND_INVALID")
    source_commit = payload.get("source_commit")
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise LocalQualificationError("SOURCE_COMMIT_INVALID")
    for key in ("release_candidate_id", "build_manifest_id"):
        value = payload.get(key)
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise LocalQualificationError(f"{key.upper()}_INVALID")

    target = payload.get("target")
    if not isinstance(target, Mapping):
        raise LocalQualificationError("LOCAL_TARGET_INVALID")
    _normalize_target(target)

    observed_at = payload.get("observed_at")
    if not isinstance(observed_at, str):
        raise LocalQualificationError("OBSERVED_AT_INVALID")
    _validate_timestamp(observed_at, "OBSERVED_AT")

    checks = payload.get("checks")
    normalized_checks = _normalize_checks(checks if isinstance(checks, list) else ())
    expected_status = (
        "QUALIFIED"
        if all(item["status"] == "VERIFIED" for item in normalized_checks)
        else "BLOCKED"
    )
    if payload.get("qualification_status") != expected_status:
        raise LocalQualificationError("QUALIFICATION_STATUS_MISMATCH")
    expected_control = "ENABLED" if expected_status == "QUALIFIED" else "DISABLED"
    if payload.get("fresh_demo_control") != expected_control:
        raise LocalQualificationError("FRESH_DEMO_CONTROL_MISMATCH")

    commands = payload.get("commands")
    if not isinstance(commands, list):
        raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
    _normalize_commands(commands)
    platform = payload.get("platform")
    if not isinstance(platform, Mapping):
        raise LocalQualificationError("PLATFORM_EVIDENCE_INVALID")
    _normalize_platform(platform)

    declared_hash = payload.get("content_hash")
    if not isinstance(declared_hash, str) or not _DIGEST.fullmatch(declared_hash):
        raise LocalQualificationError("QUALIFICATION_CONTENT_HASH_INVALID")
    if declared_hash != _content_hash(payload):
        raise LocalQualificationError("QUALIFICATION_CONTENT_HASH_MISMATCH")


def write_local_qualification(
    output_dir: Path,
    payload: Mapping[str, Any],
) -> Path:
    """Write one canonical qualification statement and immutable file digest."""

    validate_local_qualification(payload)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / LOCAL_FALLBACK_QUALIFICATION_FILENAME
    sidecar = output_dir / LOCAL_FALLBACK_QUALIFICATION_SIDECAR
    body = canonical_json(dict(payload)).encode("utf-8") + b"\n"
    file_digest = sha256(body)
    if path.exists() or sidecar.exists():
        if path.is_file() and path.read_bytes() == body and sidecar.is_file():
            if sidecar.read_text(encoding="utf-8") == f"{file_digest}\n":
                return path
        raise LocalQualificationError("QUALIFICATION_ALREADY_EXISTS")

    temporary_paths: list[Path] = []
    try:
        for destination, content in (
            (sidecar, f"{file_digest}\n".encode("utf-8")),
            (path, body),
        ):
            temporary = output_dir / f".{destination.name}.{uuid4().hex}.tmp"
            temporary_paths.append(temporary)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise
            os.replace(temporary, destination)
            temporary_paths.remove(temporary)
    except FileExistsError as error:
        raise LocalQualificationError("QUALIFICATION_ALREADY_EXISTS") from error
    except OSError as error:
        raise LocalQualificationError("QUALIFICATION_WRITE_FAILED") from error
    finally:
        for temporary in temporary_paths:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    return path


def verify_local_qualification(path: Path) -> dict[str, Any]:
    """Read and verify one canonical qualification statement and sidecar."""

    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise LocalQualificationError("QUALIFICATION_READ_FAILED") from error
    if not isinstance(payload, dict):
        raise LocalQualificationError("QUALIFICATION_SCHEMA_INVALID")
    if raw != canonical_json(payload).encode("utf-8") + b"\n":
        raise LocalQualificationError("QUALIFICATION_NOT_CANONICAL")
    validate_local_qualification(payload)
    sidecar = path.with_name(LOCAL_FALLBACK_QUALIFICATION_SIDECAR)
    if not sidecar.is_file():
        raise LocalQualificationError("QUALIFICATION_DIGEST_UNAVAILABLE")
    try:
        expected = sidecar.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LocalQualificationError("QUALIFICATION_DIGEST_READ_FAILED") from error
    if expected != f"{sha256(raw)}\n":
        raise LocalQualificationError("QUALIFICATION_FILE_HASH_MISMATCH")
    return payload


def fresh_run_capability(
    path: Path,
    *,
    required: bool,
    expected_release_candidate_id: str,
    expected_build_manifest_id: str,
) -> dict[str, Any]:
    """Return a safe public capability without exposing validation internals."""

    if not required:
        return {
            "schema_version": FRESH_RUN_CAPABILITY_SCHEMA_VERSION,
            "state": "available",
            "code": "FRESH_RUN_QUALIFICATION_NOT_REQUIRED",
            "control": "enabled",
            "qualification_hash": None,
        }
    try:
        payload = verify_local_qualification(path)
        if (
            payload["qualification_status"] != "QUALIFIED"
            or payload["fresh_demo_control"] != "ENABLED"
            or payload["target"]["profile"] != "LOCAL_FALLBACK"
            or payload["release_candidate_id"] != expected_release_candidate_id
            or payload["build_manifest_id"] != expected_build_manifest_id
        ):
            raise LocalQualificationError("QUALIFICATION_IDENTITY_INVALID")
    except (LocalQualificationError, OSError, TypeError, ValueError, KeyError):
        return {
            "schema_version": FRESH_RUN_CAPABILITY_SCHEMA_VERSION,
            "state": "unavailable",
            "code": "FRESH_RUN_UNAVAILABLE",
            "control": "disabled",
            "qualification_hash": None,
        }
    return {
        "schema_version": FRESH_RUN_CAPABILITY_SCHEMA_VERSION,
        "state": "available",
        "code": "FRESH_RUN_QUALIFIED",
        "control": "enabled",
        "qualification_hash": payload["content_hash"],
    }


def _validate_identity(
    source_commit: str,
    release_candidate_id: str,
    build_manifest_id: str,
) -> None:
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise LocalQualificationError("SOURCE_COMMIT_INVALID")
    for value, label in (
        (release_candidate_id, "RELEASE_CANDIDATE_ID"),
        (build_manifest_id, "BUILD_MANIFEST_ID"),
    ):
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise LocalQualificationError(f"{label}_INVALID")


def _normalize_target(target: Mapping[str, Any]) -> dict[str, Any]:
    if target.get("profile") != "LOCAL_FALLBACK":
        raise LocalQualificationError("LOCAL_FALLBACK_TARGET_REQUIRED")
    if target.get("host") != "Windows":
        raise LocalQualificationError("WINDOWS_LOCAL_FALLBACK_REQUIRED")
    origin = target.get("origin")
    if not isinstance(origin, str):
        raise LocalQualificationError("LOCAL_ORIGIN_INVALID")
    parsed = urlsplit(origin.rstrip("/"))
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 8000
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise LocalQualificationError("LOCAL_ORIGIN_INVALID")
    return dict(target)


def _validate_timestamp(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise LocalQualificationError(f"{label}_INVALID") from error
    if parsed.tzinfo is None:
        raise LocalQualificationError(f"{label}_TIMEZONE_REQUIRED")


def _normalize_checks(checks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        values = list(checks)
    except TypeError as error:
        raise LocalQualificationError("CHECKS_INVALID") from error
    if len(values) != len(REQUIRED_LOCAL_CHECK_IDS):
        raise LocalQualificationError("REQUIRED_CHECK_SET_INCOMPLETE")
    by_id: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, Mapping):
            raise LocalQualificationError("CHECK_INVALID")
        check_id = item.get("check_id")
        status = item.get("status")
        code = item.get("code")
        evidence = item.get("evidence")
        if (
            not isinstance(check_id, str)
            or check_id not in REQUIRED_LOCAL_CHECK_IDS
            or check_id in by_id
            or not isinstance(status, str)
            or status not in CHECK_STATUSES
            or not isinstance(code, str)
            or not _IDENTIFIER.fullmatch(code)
            or not isinstance(evidence, Mapping)
        ):
            raise LocalQualificationError("CHECK_INVALID")
        by_id[check_id] = {
            "check_id": check_id,
            "status": status,
            "code": code,
            "evidence": dict(evidence),
        }
    if set(by_id) != set(REQUIRED_LOCAL_CHECK_IDS):
        raise LocalQualificationError("REQUIRED_CHECK_SET_INCOMPLETE")
    return [by_id[check_id] for check_id in REQUIRED_LOCAL_CHECK_IDS]


def _normalize_commands(commands: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        values = list(commands)
    except TypeError as error:
        raise LocalQualificationError("COMMAND_PROVENANCE_INVALID") from error
    if not values:
        raise LocalQualificationError("COMMAND_PROVENANCE_INCOMPLETE")
    normalized: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, Mapping):
            raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
        required_strings = ("command", "cli", "version", "target")
        if any(
            not isinstance(item.get(key), str) or not item[key].strip()
            for key in required_strings
        ):
            raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
        if not isinstance(item.get("exit_status"), int) or isinstance(
            item.get("exit_status"), bool
        ):
            raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
        if not isinstance(item.get("duration_ms"), int) or isinstance(
            item.get("duration_ms"), bool
        ) or item["duration_ms"] < 0:
            raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
        for key in ("started_at", "finished_at"):
            value = item.get(key)
            if not isinstance(value, str):
                raise LocalQualificationError("COMMAND_PROVENANCE_INVALID")
            _validate_timestamp(value, "COMMAND_TIMESTAMP")
        output_digest = item.get("redacted_output_digest")
        if not isinstance(output_digest, str) or not _DIGEST.fullmatch(output_digest):
            raise LocalQualificationError("COMMAND_OUTPUT_DIGEST_INVALID")
        if "output" in item or "raw_output" in item:
            raise LocalQualificationError("UNREDACTED_COMMAND_OUTPUT_FORBIDDEN")
        artifact_hashes = item.get("artifact_hashes", [])
        if not isinstance(artifact_hashes, list) or any(
            not isinstance(value, str) or not _DIGEST.fullmatch(value)
            for value in artifact_hashes
        ):
            raise LocalQualificationError("COMMAND_ARTIFACT_HASH_INVALID")
        normalized.append(dict(item))
    return normalized


def _normalize_platform(platform: Mapping[str, Any]) -> dict[str, Any]:
    required = ("os", "python_version", "node_version", "playwright_version")
    if any(not isinstance(platform.get(key), str) or not platform[key].strip() for key in required):
        raise LocalQualificationError("PLATFORM_EVIDENCE_INVALID")
    if platform.get("os") != "Windows":
        raise LocalQualificationError("WINDOWS_PLATFORM_REQUIRED")
    network_state = platform.get("network_state")
    if network_state not in {"EXTERNAL_NETWORK_UNAVAILABLE", "OFFLINE"}:
        raise LocalQualificationError("OFFLINE_NETWORK_EVIDENCE_INVALID")
    return dict(platform)


def _content_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "content_hash"}
    return sha256(canonical_json(body).encode("utf-8"))
