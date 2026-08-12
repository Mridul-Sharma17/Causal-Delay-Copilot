from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

from .canonical import canonical_json, sha256


HOSTED_DELIVERY_ATTESTATION_SCHEMA_VERSION = "hosted-delivery-attestation.v1"
HOSTED_DELIVERY_ATTESTATION_KIND = "HOSTED_DELIVERY_QUALIFICATION"

QUALIFICATION_STATUSES = frozenset({"QUALIFIED", "BLOCKED"})
CHECK_STATUSES = frozenset({"VERIFIED", "BLOCKED", "UNAVAILABLE", "NOT_RUN"})

REQUIRED_HOSTED_CHECK_IDS = (
    "browser_reference_journey",
    "browser_abstention_boundary",
    "workspace_isolation",
    "mutation_rate_and_quota_limits",
    "queue_saturation",
    "restart_recovery",
    "release_mismatch_refusal",
    "persistent_volume",
    "one_writer_process_limits",
    "disk_thresholds",
    "no_store_behavior",
    "security_headers",
    "redacted_health_log_surfaces",
    "serverless_disabled",
    "judging_availability",
    "budget_alert_recorded",
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class HostedQualificationError(ValueError):
    """A hosted-delivery attestation failed its immutable contract."""


def build_hosted_attestation(
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
    """Build one content-addressed hosted qualification statement.

    Qualification is deliberately derived from the required check states. A
    caller cannot mark a run qualified while leaving a required check absent,
    unavailable, or blocked.
    """

    _validate_identity(source_commit, release_candidate_id, build_manifest_id)
    _validate_target(target)
    _validate_timestamp(observed_at)
    normalized_checks = _normalize_checks(checks)
    normalized_commands = _normalize_commands(commands)
    normalized_platform = _normalize_platform(platform)
    _validate_check_platform_binding(normalized_checks, normalized_platform)
    qualification_status = (
        "QUALIFIED"
        if all(item["status"] == "VERIFIED" for item in normalized_checks)
        else "BLOCKED"
    )
    payload: dict[str, Any] = {
        "schema_version": HOSTED_DELIVERY_ATTESTATION_SCHEMA_VERSION,
        "attestation_kind": HOSTED_DELIVERY_ATTESTATION_KIND,
        "qualification_status": qualification_status,
        "source_commit": source_commit,
        "release_candidate_id": release_candidate_id,
        "build_manifest_id": build_manifest_id,
        "target": dict(target),
        "checks": normalized_checks,
        "commands": normalized_commands,
        "platform": normalized_platform,
        "observed_at": observed_at,
    }
    payload["content_hash"] = _content_hash(payload)
    validate_hosted_attestation(payload)
    return payload


def validate_hosted_attestation(payload: Mapping[str, Any]) -> None:
    """Validate a parsed attestation without reading or writing files."""

    if not isinstance(payload, Mapping):
        raise HostedQualificationError("ATTESTATION_SCHEMA_INVALID")
    if payload.get("schema_version") != HOSTED_DELIVERY_ATTESTATION_SCHEMA_VERSION:
        raise HostedQualificationError("ATTESTATION_SCHEMA_UNSUPPORTED")
    if payload.get("attestation_kind") != HOSTED_DELIVERY_ATTESTATION_KIND:
        raise HostedQualificationError("ATTESTATION_KIND_INVALID")
    source_commit = payload.get("source_commit")
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise HostedQualificationError("SOURCE_COMMIT_INVALID")
    for key in ("release_candidate_id", "build_manifest_id"):
        value = payload.get(key)
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise HostedQualificationError(f"{key.upper()}_INVALID")
    target = payload.get("target")
    if not isinstance(target, Mapping):
        raise HostedQualificationError("HOSTED_TARGET_INVALID")
    _validate_target(target)
    observed_at = payload.get("observed_at")
    if not isinstance(observed_at, str):
        raise HostedQualificationError("OBSERVED_AT_INVALID")
    _validate_timestamp(observed_at)

    checks = payload.get("checks")
    normalized_checks = _normalize_checks(checks if isinstance(checks, list) else ())
    expected_status = (
        "QUALIFIED"
        if all(item["status"] == "VERIFIED" for item in normalized_checks)
        else "BLOCKED"
    )
    if payload.get("qualification_status") != expected_status:
        raise HostedQualificationError("QUALIFICATION_STATUS_MISMATCH")

    commands = payload.get("commands")
    if not isinstance(commands, list):
        raise HostedQualificationError("COMMAND_PROVENANCE_INVALID")
    _normalize_commands(commands)
    platform = payload.get("platform")
    if not isinstance(platform, Mapping):
        raise HostedQualificationError("PLATFORM_EVIDENCE_INVALID")
    normalized_platform = _normalize_platform(platform)
    _validate_check_platform_binding(normalized_checks, normalized_platform)

    declared_hash = payload.get("content_hash")
    if not isinstance(declared_hash, str) or not _DIGEST.fullmatch(declared_hash):
        raise HostedQualificationError("ATTESTATION_CONTENT_HASH_INVALID")
    if declared_hash != _content_hash(payload):
        raise HostedQualificationError("ATTESTATION_CONTENT_HASH_MISMATCH")


def write_hosted_attestation(
    output_dir: Path,
    payload: Mapping[str, Any],
) -> Path:
    """Write one immutable JSON attestation and its content-addressed sidecar."""

    validate_hosted_attestation(payload)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "hosted-delivery-attestation.json"
    sidecar = output_dir / "hosted-delivery-attestation.sha256"
    body = canonical_json(dict(payload)).encode("utf-8") + b"\n"
    file_digest = sha256(body)
    if path.exists() or sidecar.exists():
        if path.is_file() and path.read_bytes() == body and sidecar.is_file():
            if sidecar.read_text(encoding="utf-8") == f"{file_digest}\n":
                return path
        raise HostedQualificationError("ATTESTATION_ALREADY_EXISTS")

    temporary_paths: list[Path] = []
    try:
        for destination, content in (
            (sidecar, f"{file_digest}\n".encode("utf-8")),
            (path, body),
        ):
            temporary = output_dir / f".{destination.name}.{uuid4().hex}.tmp"
            temporary_paths.append(temporary)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(temporary, flags)
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
            os.rename(temporary, destination)
            temporary_paths.remove(temporary)
    except FileExistsError as error:
        raise HostedQualificationError("ATTESTATION_ALREADY_EXISTS") from error
    except OSError as error:
        raise HostedQualificationError("ATTESTATION_WRITE_FAILED") from error
    finally:
        for temporary in temporary_paths:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    return path


def verify_hosted_attestation(path: Path) -> dict[str, Any]:
    """Read and verify an immutable attestation and its required sidecar."""

    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise HostedQualificationError("ATTESTATION_READ_FAILED") from error
    if not isinstance(payload, dict):
        raise HostedQualificationError("ATTESTATION_SCHEMA_INVALID")
    if raw != (canonical_json(payload).encode("utf-8") + b"\n"):
        raise HostedQualificationError("ATTESTATION_NOT_CANONICAL")
    validate_hosted_attestation(payload)
    sidecar = path.with_name("hosted-delivery-attestation.sha256")
    if not sidecar.is_file():
        raise HostedQualificationError("ATTESTATION_DIGEST_UNAVAILABLE")
    try:
        expected = sidecar.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise HostedQualificationError("ATTESTATION_DIGEST_READ_FAILED") from error
    if expected != f"{sha256(raw)}\n":
        raise HostedQualificationError("ATTESTATION_FILE_HASH_MISMATCH")
    return payload


def _validate_identity(
    source_commit: str,
    release_candidate_id: str,
    build_manifest_id: str,
) -> None:
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise HostedQualificationError("SOURCE_COMMIT_INVALID")
    for value, label in (
        (release_candidate_id, "RELEASE_CANDIDATE_ID"),
        (build_manifest_id, "BUILD_MANIFEST_ID"),
    ):
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise HostedQualificationError(f"{label}_INVALID")


def _validate_target(target: Mapping[str, Any]) -> None:
    if target.get("profile") != "HOSTED":
        raise HostedQualificationError("HOSTED_TARGET_REQUIRED")
    if target.get("fallback_used") is True or target.get("static_fallback") is True:
        raise HostedQualificationError("FALLBACK_EVIDENCE_FORBIDDEN")
    for key in ("vercel_origin", "railway_origin"):
        value = target.get(key)
        if not isinstance(value, str):
            raise HostedQualificationError("HOSTED_ORIGIN_INVALID")
        parsed = urlsplit(value.rstrip("/"))
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise HostedQualificationError("HOSTED_ORIGIN_INVALID")


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise HostedQualificationError("OBSERVED_AT_INVALID") from error
    if parsed.tzinfo is None:
        raise HostedQualificationError("OBSERVED_AT_TIMEZONE_REQUIRED")


def _normalize_checks(checks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        values = list(checks)
    except TypeError as error:
        raise HostedQualificationError("CHECKS_INVALID") from error
    if len(values) != len(REQUIRED_HOSTED_CHECK_IDS):
        raise HostedQualificationError("REQUIRED_CHECK_SET_INCOMPLETE")
    by_id: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, Mapping):
            raise HostedQualificationError("CHECK_INVALID")
        check_id = item.get("check_id")
        status = item.get("status")
        code = item.get("code")
        evidence = item.get("evidence")
        if (
            not isinstance(check_id, str)
            or check_id not in REQUIRED_HOSTED_CHECK_IDS
            or check_id in by_id
            or not isinstance(status, str)
            or status not in CHECK_STATUSES
            or not isinstance(code, str)
            or not _IDENTIFIER.fullmatch(code)
            or not isinstance(evidence, Mapping)
        ):
            raise HostedQualificationError("CHECK_INVALID")
        by_id[check_id] = {
            "check_id": check_id,
            "status": status,
            "code": code,
            "evidence": dict(evidence),
        }
    if set(by_id) != set(REQUIRED_HOSTED_CHECK_IDS):
        raise HostedQualificationError("REQUIRED_CHECK_SET_INCOMPLETE")
    return [by_id[check_id] for check_id in REQUIRED_HOSTED_CHECK_IDS]


def _normalize_commands(commands: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try:
        values = list(commands)
    except TypeError as error:
        raise HostedQualificationError("COMMAND_PROVENANCE_INVALID") from error
    if not values:
        raise HostedQualificationError("COMMAND_PROVENANCE_INCOMPLETE")
    normalized: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, Mapping):
            raise HostedQualificationError("COMMAND_PROVENANCE_INVALID")
        required = ("command", "cli", "version", "target", "exit_status")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required[:4]):
            raise HostedQualificationError("COMMAND_PROVENANCE_INVALID")
        if not isinstance(item.get("exit_status"), int):
            raise HostedQualificationError("COMMAND_PROVENANCE_INVALID")
        output_digest = item.get("redacted_output_digest")
        if output_digest is not None and (
            not isinstance(output_digest, str) or not _DIGEST.fullmatch(output_digest)
        ):
            raise HostedQualificationError("COMMAND_OUTPUT_DIGEST_INVALID")
        if "output" in item or "raw_output" in item:
            raise HostedQualificationError("UNREDACTED_COMMAND_OUTPUT_FORBIDDEN")
        normalized.append(dict(item))
    return normalized


def _normalize_platform(platform: Mapping[str, Any]) -> dict[str, Any]:
    budget = platform.get("budget_alert")
    if not isinstance(budget, Mapping):
        raise HostedQualificationError("BUDGET_ALERT_EVIDENCE_INVALID")
    state = budget.get("state")
    if state not in {"VERIFIED", "RECORDED", "BLOCKED", "UNAVAILABLE"}:
        raise HostedQualificationError("BUDGET_ALERT_EVIDENCE_INVALID")
    if not isinstance(budget.get("hard_cap"), bool):
        raise HostedQualificationError("BUDGET_ALERT_HARD_CAP_INVALID")
    if state in {"VERIFIED", "RECORDED"} and budget.get("hard_cap") is not False:
        raise HostedQualificationError("BUDGET_ALERT_MUST_NOT_BE_HARD_CAP")
    if state in {"VERIFIED", "RECORDED"}:
        if budget.get("threshold_usd") != 4:
            raise HostedQualificationError("BUDGET_ALERT_THRESHOLD_INVALID")
        for key in ("record_ref", "actor", "source", "cli_gap"):
            if not isinstance(budget.get(key), str) or not budget[key].strip():
                raise HostedQualificationError("BUDGET_ALERT_EVIDENCE_INVALID")
        if budget.get("source") != "operator-recorded-Railway-billing-alert":
            raise HostedQualificationError("BUDGET_ALERT_SOURCE_INVALID")
        if state == "RECORDED" and budget.get("external_verification") != "UNAVAILABLE":
            raise HostedQualificationError("BUDGET_ALERT_EXTERNAL_VERIFICATION_INVALID")
        try:
            _validate_timestamp(str(budget["observed_at"]))
        except HostedQualificationError as error:
            raise HostedQualificationError("BUDGET_ALERT_OBSERVED_AT_INVALID") from error
    return dict(platform)


def _validate_check_platform_binding(
    checks: Iterable[Mapping[str, Any]],
    platform: Mapping[str, Any],
) -> None:
    checks_by_id = {item["check_id"]: item for item in checks}
    budget = platform["budget_alert"]
    check_state = checks_by_id["budget_alert_recorded"]["status"]
    platform_state = budget["state"]
    platform_recorded = platform_state in {"VERIFIED", "RECORDED"}
    if (check_state == "VERIFIED") != platform_recorded:
        raise HostedQualificationError("BUDGET_ALERT_CHECK_MISMATCH")


def _content_hash(payload: Mapping[str, Any]) -> str:
    body = {
        key: value
        for key, value in payload.items()
        if key != "content_hash"
    }
    return sha256(canonical_json(body).encode("utf-8"))
