from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid4, uuid5

from .audit import AuditStoreUnavailable
from .canonical import (
    Temporal as _Temporal,
    canonical_json as _canonical_json,
    compare_temporal as _compare,
    equal_temporal as _equal_temporal,
    field as _field,
    normalise_temporal as _normalise_temporal,
    safe_sha256 as _safe_sha256,
    sha256 as _sha256,
    timestamp as _timestamp,
)
from .contracts import (
    ProactiveProposalFixtureResponse,
    ProactiveProposalRequest,
    ProactiveProposalPreviewResponse,
    RiskSignalAdvisoryContextRequest,
    RiskSignalFixtureResponse,
    RiskSignalPreviewResponse,
    RiskSignalRequest,
)
RISK_SIGNAL_SCHEMA_VERSION = "risk-signal.v1"
PROACTIVE_PROPOSAL_SCHEMA_VERSION = "proactive-proposal.v1"
TRIGGER_SOURCE_SCHEMA_VERSION = "trigger-source-envelope.v1"
CAUSAL_INPUT_SCHEMA_VERSION = "causal-input-projection.v2"
CAUSAL_QUESTION_VERSION = "supplier-load-slippage.v1"
ENGINE_CONFIGURATION_REF = "causal-engine-config.v1"
TARGET_DEFINITION_ID = "supplier_milestone_miss.v1"
SCORE_SEMANTIC = "probability_supplier_milestone_miss"
CONFIGURED_TARGET_MILESTONE_KIND = "supplier_handoff"
CANONICAL_SLIPPAGE_DURATION_BASIS = "CALENDAR_DAY"
TEMPORAL_ELIGIBILITY_RELEASE_REF = "temporal-eligibility-release.v1"
ESTIMATOR_WINDOW_SELECTOR_VERSION = "estimator-window.v1"
HISTORY_LOOKBACK_SELECTOR_VERSION = "history-lookback.v1"
SOURCE_NAMESPACE = "semi-synthetic-hero"
SOURCE_SYSTEM = "bundled-predictive-stub"
PROACTIVE_SOURCE_SYSTEM = "bundled-pre-award-hook"
FIXTURE_FILE = Path(__file__).with_name("data") / "risk_signal_fixtures.json"
PROACTIVE_FIXTURE_FILE = (
    Path(__file__).with_name("data") / "proactive_proposal_fixtures.json"
)
PROTECTED_SOURCE_FILE = Path(__file__).with_name("data") / "risk_signal_protected_sources.json"
PREDICTIVE_FIXTURE_FILE = (
    Path(__file__).with_name("data") / "predictive_risk_signal_fixture.json"
)
PREDICTIVE_PROTECTED_SOURCE_FILE = (
    Path(__file__).with_name("data") / "predictive_protected_sources.json"
)
PREDICTIVE_ATTRIBUTION_FILE = (
    Path(__file__).with_name("data") / "predictive_attributions.json"
)
PREDICTIVE_RECORD_FILE = (
    Path(__file__).with_name("data") / "predictive_prediction_records.json"
)
PREDICTIVE_ARTIFACT_FILE = (
    Path(__file__).with_name("data") / "predictive_baseline.joblib"
)
PREDICTIVE_REPORT_FILE = (
    Path(__file__).with_name("data") / "predictive_baseline_report.json"
)
PREDICTIVE_FIXTURE_ID = "hero-reactive-risk-predictive-baseline-v1"
PROACTIVE_FIXTURE_ID = "hero-proactive-proposal-v1"
TEMPORAL_ELIGIBILITY_RELEASE_FILE = (
    Path(__file__).with_name("data") / "temporal_eligibility_release.json"
)

CAUSAL_QUESTION_REGISTRY = frozenset({CAUSAL_QUESTION_VERSION})
ENGINE_CONFIGURATION_REGISTRY = {
    ENGINE_CONFIGURATION_REF: {
        "canonical_slippage_duration_basis": CANONICAL_SLIPPAGE_DURATION_BASIS,
        "temporal_eligibility_release_ref": TEMPORAL_ELIGIBILITY_RELEASE_REF,
        "estimator_window_selector_version": ESTIMATOR_WINDOW_SELECTOR_VERSION,
        "history_lookback_selector_version": HISTORY_LOOKBACK_SELECTOR_VERSION,
    }
}

_LOAD_EXPOSURE_VARIANTS = (
    ("primary", 0.67, 10, "nearest-rank-percentile-0.67.v1"),
    ("stricter_threshold", 0.75, 10, "nearest-rank-percentile-0.75.v1"),
    ("short_history", 0.67, 5, "nearest-rank-percentile-0.67.v1"),
    ("long_history", 0.67, 20, "nearest-rank-percentile-0.67.v1"),
)
_PRIMARY_LOAD_MINIMUM_HISTORY = 10
_LOAD_EXPOSURE_SCHEMA_VERSION = "supplier-load-exposure.v1"

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_RISK_SIGNAL_CODES = (
    "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
    "RISK_SIGNAL_INTEGRITY_FAILED",
    "RISK_SIGNAL_REVISION_CONFLICT",
    "RISK_SIGNAL_CLOCK_UNUSABLE",
    "RISK_SIGNAL_SUBJECT_UNRESOLVED",
    "RISK_SIGNAL_SUBJECT_AMBIGUOUS",
    "RISK_SIGNAL_SUBJECT_NOT_OPEN",
    "LOAD_SNAPSHOT_UNRESOLVABLE",
    "COMMITMENT_CUTOFF_UNUSABLE",
    "RISK_SIGNAL_TARGET_MISMATCH",
    "RISK_SIGNAL_SCORE_UNUSABLE",
    "RISK_SIGNAL_CONTEXT_CONFLICT",
    "RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
    "RISK_SIGNAL_MODE_MISMATCH",
    "CAUSAL_QUESTION_VERSION_UNAVAILABLE",
    "ENGINE_CONFIGURATION_UNAVAILABLE",
    "SLIPPAGE_DURATION_BASIS_MIXED",
    "PREDICTOR_ARTIFACT_UNAVAILABLE",
    "PREDICTIVE_ATTRIBUTION_UNAVAILABLE",
    "PROACTIVE_SCHEMA_UNSUPPORTED",
    "PROACTIVE_INTEGRITY_FAILED",
    "PROACTIVE_REVISION_CONFLICT",
    "PROACTIVE_DATASET_UNAVAILABLE",
    "FROZEN_PROMISE_UNAVAILABLE",
    "FROZEN_PROMISE_CONFLICT",
    "FROZEN_PROMISE_TEMPORALLY_INVALID",
)

REACTIVE_INGRESS_ATTEMPTS_TABLE = """
    CREATE TABLE IF NOT EXISTS reactive_ingress_attempts (
        attempt_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        source_system TEXT NOT NULL,
        source_signal_id TEXT NOT NULL,
        source_revision TEXT NOT NULL,
        source_payload_sha256 TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('accepted', 'duplicate', 'rejected', 'accepted_with_warning')
        ),
        primary_code TEXT NOT NULL,
        investigation_request_id TEXT,
        occurrence_id TEXT NOT NULL UNIQUE,
        event_seq INTEGER NOT NULL,
        received_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
"""
REACTIVE_INGRESS_ATTEMPTS_COLUMNS = [
    "attempt_id",
    "workspace_id",
    "idempotency_key",
    "source_system",
    "source_signal_id",
    "source_revision",
    "source_payload_sha256",
    "content_hash",
    "status",
    "primary_code",
    "investigation_request_id",
    "occurrence_id",
    "event_seq",
    "received_at",
    "payload_json",
]

PROACTIVE_INGRESS_ATTEMPTS_TABLE = """
    CREATE TABLE IF NOT EXISTS proactive_ingress_attempts (
        attempt_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        idempotency_key TEXT NOT NULL,
        source_system TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        proposal_revision TEXT NOT NULL,
        source_payload_sha256 TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('accepted', 'duplicate', 'rejected', 'accepted_with_warning')
        ),
        primary_code TEXT NOT NULL,
        investigation_request_id TEXT,
        occurrence_id TEXT NOT NULL UNIQUE,
        event_seq INTEGER NOT NULL,
        received_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
"""
PROACTIVE_INGRESS_ATTEMPTS_COLUMNS = [
    "attempt_id",
    "workspace_id",
    "idempotency_key",
    "source_system",
    "proposal_id",
    "proposal_revision",
    "source_payload_sha256",
    "content_hash",
    "status",
    "primary_code",
    "investigation_request_id",
    "occurrence_id",
    "event_seq",
    "received_at",
    "payload_json",
]

INVESTIGATION_REQUESTS_TABLE = """
    CREATE TABLE IF NOT EXISTS investigation_requests (
        investigation_request_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        attempt_id TEXT NOT NULL UNIQUE,
        content_hash TEXT NOT NULL,
        accepted_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
"""
INVESTIGATION_REQUESTS_COLUMNS = [
    "investigation_request_id",
    "workspace_id",
    "attempt_id",
    "content_hash",
    "accepted_at",
    "payload_json",
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
        raise sqlite3.DatabaseError(
            f"{table_name} schema is not the locked ingress schema"
        )


def ensure_risk_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    _ensure_table(
        connection,
        "reactive_ingress_attempts",
        REACTIVE_INGRESS_ATTEMPTS_TABLE,
        REACTIVE_INGRESS_ATTEMPTS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "investigation_requests",
        INVESTIGATION_REQUESTS_TABLE,
        INVESTIGATION_REQUESTS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "proactive_ingress_attempts",
        PROACTIVE_INGRESS_ATTEMPTS_TABLE,
        PROACTIVE_INGRESS_ATTEMPTS_COLUMNS,
        create=create,
    )
    if create:
        for table_name in (
            "reactive_ingress_attempts",
            "proactive_ingress_attempts",
            "investigation_requests",
        ):
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'reactive ingress records are immutable');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'reactive ingress records are immutable');
                END
                """
            )


@dataclass(frozen=True, slots=True)
class StoredReactiveIngress:
    result: str
    attempt: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StoredProactiveIngress:
    result: str
    attempt: dict[str, Any]


class RiskSignalFixtureUnavailable(Exception):
    """A requested protected bundled fixture is not available to this version."""


class ProactiveProposalFixtureUnavailable(Exception):
    """A requested protected bundled proposal is not available to this version."""


def _finding(
    *,
    code: str,
    severity: str,
    disposition: str,
    affected_refs: list[str],
    message: str,
    remediation: str,
    phase: int,
) -> dict[str, Any]:
    finding_id = _sha256(
        {
            "code": code,
            "affected_refs": affected_refs,
            "message": message,
        }
    )
    return {
        "finding_id": finding_id,
        "code": code,
        "severity": severity,
        "disposition": disposition,
        "affected_refs": affected_refs,
        "message": message,
        "remediation": remediation,
        "_phase": phase,
        "_code_order": _RISK_SIGNAL_CODES.index(code)
        if code in _RISK_SIGNAL_CODES
        else len(_RISK_SIGNAL_CODES),
    }


_RECOVERY_ACTIONS = {
    "RISK_SIGNAL_ACCEPTED": "CONTINUE_TO_ELIGIBILITY_REVIEW",
    "RISK_SIGNAL_SCHEMA_UNSUPPORTED": "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
    "RISK_SIGNAL_INTEGRITY_FAILED": "REPAIR_PROTECTED_SIGNAL_AND_RETRY",
    "RISK_SIGNAL_REVISION_CONFLICT": "SUBMIT_A_NEW_SOURCE_REVISION",
    "RISK_SIGNAL_CLOCK_UNUSABLE": "PROVIDE_COMPARABLE_GENERATED_AND_KNOWN_CLOCKS",
    "RISK_SIGNAL_SUBJECT_UNRESOLVED": "SELECT_ONE_PUBLISHED_DATASET_VERSION_AND_SOURCE_ORDER_LINE",
    "RISK_SIGNAL_SUBJECT_AMBIGUOUS": "SELECT_EXACT_VERSION_AND_SOURCE_ORDER_LINE",
    "RISK_SIGNAL_SUBJECT_NOT_OPEN": "USE_AN_OPEN_ORDER_LINE_SIGNAL",
    "LOAD_SNAPSHOT_UNRESOLVABLE": "WAIT_FOR_POINT_IN_TIME_LINEAGE",
    "COMMITMENT_CUTOFF_UNUSABLE": "REPAIR_COMMITMENT_CLOCKS_AND_RETRY",
    "RISK_SIGNAL_TARGET_MISMATCH": "USE_CONFIGURED_SUPPLIER_MILESTONE_TARGET",
    "RISK_SIGNAL_SCORE_UNUSABLE": "REPAIR_SCORE_THRESHOLD_AND_FLAG",
    "RISK_SIGNAL_CONTEXT_CONFLICT": "REVIEW_SOURCE_CONTEXT_AGAINST_CANONICAL_LINE",
    "RISK_SIGNAL_CONTEXT_UNVERIFIABLE": "CONTINUE_WITH_CANONICAL_FACTS_ONLY",
    "RISK_SIGNAL_MODE_MISMATCH": "USE_THE_REACTIVE_RISK_SIGNAL_ROUTE",
    "PROACTIVE_ACCEPTED": "CONTINUE_TO_ELIGIBILITY_REVIEW",
    "PROACTIVE_SCHEMA_UNSUPPORTED": "USE_SUPPORTED_PROACTIVE_PROPOSAL_SCHEMA",
    "PROACTIVE_INTEGRITY_FAILED": "REPAIR_PROTECTED_PROPOSAL_AND_RETRY",
    "PROACTIVE_REVISION_CONFLICT": "SUBMIT_A_NEW_PROPOSAL_REVISION",
    "PROACTIVE_DATASET_UNAVAILABLE": "SELECT_A_FROZEN_DATASET_VERSION_AND_RETRY",
    "CAUSAL_QUESTION_VERSION_UNAVAILABLE": "RESTORE_VERSIONED_CORE_CONFIGURATION",
    "ENGINE_CONFIGURATION_UNAVAILABLE": "RESTORE_VERSIONED_CORE_CONFIGURATION",
    "SLIPPAGE_DURATION_BASIS_MIXED": "WAIT_FOR_ONE_RELEASED_DURATION_BASIS",
    "FROZEN_PROMISE_UNAVAILABLE": "REVIEW_CANONICAL_PROMISE_HISTORY_AND_RETRY",
    "FROZEN_PROMISE_CONFLICT": "REPAIR_CANONICAL_PROMISE_HISTORY_AND_RETRY",
    "FROZEN_PROMISE_TEMPORALLY_INVALID": "REPAIR_CANONICAL_PROMISE_CLOCKS_AND_RETRY",
}


def _is_rejection(finding: Mapping[str, Any]) -> bool:
    return finding.get("disposition") == "reject"


def _clean_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in finding.items()
        if not key.startswith("_")
    }


def _protected_signal_payload(signal_payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(signal_payload))
    source = payload.get("source")
    if isinstance(source, dict):
        source.pop("source_payload_sha256", None)
    return payload


def _protected_source_bytes(locator: str) -> bytes | None:
    """Resolve a bundled protected locator to its frozen source bytes."""
    for source_file in (PROTECTED_SOURCE_FILE, PREDICTIVE_PROTECTED_SOURCE_FILE):
        try:
            with source_file.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(raw, Mapping) or raw.get("schema_version") != (
            "risk-signal-protected-source-bytes.v1"
        ):
            continue
        items = raw.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, Mapping) or item.get("locator") != locator:
                continue
            encoded = item.get("bytes_base64")
            if not isinstance(encoded, str) or not encoded:
                continue
            try:
                return base64.b64decode(encoded, validate=True)
            except (ValueError, base64.binascii.Error):
                continue
    return None


def _fixture_protected_source_digest(signal: RiskSignalRequest) -> str:
    """Return the bundled adapter's frozen protected-source byte digest.

    The protected locator resolves to bytes shipped by the bundled adapter;
    ingress never replaces its declared digest with a digest of submitted
    content.
    """
    protected_bytes = _protected_source_bytes(signal.source.protected_source_locator)
    return _sha256(protected_bytes) if protected_bytes is not None else ""


def _source_key(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return value
    return []


def _dataset_namespace(dataset_id: str):
    return uuid5(NAMESPACE_URL, f"causal-delay-copilot:dataset:{dataset_id}")


def _canonical_id(dataset_id: str, kind: str, source_key: str) -> str:
    return uuid5(_dataset_namespace(dataset_id), f"{kind}:{source_key}").hex


def _canonical_identity_from_mapping(
    dataset_id: str,
    mapping_manifest: Mapping[str, Any],
    identity_name: str,
    source_key: str,
) -> str | None:
    mappings = mapping_manifest.get("identity_mappings")
    if not isinstance(mappings, Mapping):
        return None
    mapping = mappings.get(identity_name)
    if not isinstance(mapping, Mapping):
        return None
    expected_rule = {
        "order_line_id": "uuid5.dataset.order-line.v1",
        "order_group_id": "uuid5.dataset.order-group.v1",
        "supplier_id": "uuid5.dataset.supplier.v1",
    }.get(identity_name)
    if (
        expected_rule is None
        or mapping.get("rule_id") != expected_rule
        or mapping.get("rule_version") != "1"
    ):
        return None
    kind = identity_name.removesuffix("_id").replace("_", "-")
    return _canonical_id(dataset_id, kind, source_key)


def _source_signal_identity(signal_payload: Mapping[str, Any]) -> str | None:
    dataset_version_id = signal_payload.get("scored_dataset_version_ref")
    source_ref = signal_payload.get("source_order_line_ref")
    predictor_id = signal_payload.get("predictor_id")
    predictor_version = signal_payload.get("predictor_version")
    target_milestone_kind = signal_payload.get("target_milestone_kind")
    generated_at = signal_payload.get("generated_at")
    if not all(
        isinstance(value, str) and value
        for value in (
            dataset_version_id,
            predictor_id,
            predictor_version,
            target_milestone_kind,
        )
    ) or not isinstance(source_ref, Mapping):
        return None
    source_keys = _source_key(source_ref.get("key"))
    if len(source_keys) != 1:
        return None
    generated = _normalise_temporal(generated_at)
    if generated.field.get("state") != "present":
        return None
    return "bundled-risk-" + _sha256(
        {
            "dataset_version_id": dataset_version_id,
            "order_line_id": _canonical_id(
                SOURCE_NAMESPACE,
                "order-line",
                source_keys[0],
            ),
            "predictor_id": predictor_id,
            "predictor_version": predictor_version,
            "target_milestone_kind": target_milestone_kind,
            "generated_at": generated.field,
        }
    )[7:]


def _temporal_from_record(record: Any) -> _Temporal:
    if not isinstance(record, Mapping):
        return _Temporal(_field("invalid"), None)
    state = record.get("state")
    if state != "present":
        return _Temporal(_field(str(state or "unresolved")), None)
    value = record.get("value")
    if not isinstance(value, Mapping):
        return _Temporal(_field("invalid"), None)
    return _normalise_temporal(value)


def _field_from_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return _field("unresolved")
    state = record.get("state")
    if state == "present":
        return _field("present", record.get("value"))
    if state in {"missing", "not_applicable", "invalid", "unresolved"}:
        return _field(str(state))
    return _field("unresolved")


def _normalise_proactive_temporal(field: Any) -> _Temporal:
    if not hasattr(field, "state") or field.state != "present":
        return _Temporal(_field(str(getattr(field, "state", "unresolved"))), None)
    value = getattr(field, "value", None)
    if not isinstance(value, Mapping):
        return _Temporal(_field("invalid"), None)
    return _normalise_temporal(value)


def _proactive_target_field(field: Any) -> dict[str, Any]:
    if field.state != "present":
        return _field(field.state)
    if not isinstance(field.value, str) or field.value not in {
        "supplier_completion",
        "supplier_handoff",
    }:
        return _field("invalid")
    return _field("present", field.value)


def _proactive_source_reference(
    field: Any,
    *,
    dataset_id: str,
    mapping_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if field.state != "present":
        return _field(field.state)
    if not isinstance(field.value, Mapping):
        return _field("invalid")
    if field.value.get("namespace") != SOURCE_NAMESPACE:
        return _field("unresolved")
    keys = _source_key(field.value.get("key"))
    if len(keys) != 1:
        return _field("unresolved")
    canonical = _canonical_identity_from_mapping(
        dataset_id,
        mapping_manifest,
        "supplier_id",
        keys[0],
    )
    return _field("present", canonical) if canonical is not None else _field("unresolved")


def _proactive_projection_field(
    field: Any,
    cutoff: _Temporal,
    *,
    value: Any | None = None,
    state: str | None = None,
    temporal: _Temporal | None = None,
) -> dict[str, Any]:
    field_state = state or field.state
    if field_state != "present":
        return _field(field_state)
    if field.state != "present":
        return _field(field.state)
    if field.known_at is None:
        return _field("unresolved")
    known_at = _normalise_temporal(field.known_at.model_dump(mode="json"))
    if _compare(known_at, cutoff) not in {-1, 0}:
        return _field("unresolved")
    if temporal is not None:
        return temporal.field
    if value is None and field.value is None:
        return _field("invalid")
    return _field("present", field.value if value is None else value)


def _proactive_subject_input(
    source_field: Any,
    normalised_field: Mapping[str, Any],
    *,
    temporal: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "state": normalised_field.get("state", "unresolved"),
    }
    if payload["state"] == "present":
        payload["value"] = normalised_field.get("value")
    if source_field.known_at is not None:
        payload["known_at"] = source_field.known_at.model_dump(mode="json")
    if source_field.lineage_ref is not None:
        payload["lineage_ref"] = source_field.lineage_ref
    if temporal and source_field.state != "present":
        payload["state"] = source_field.state
    return payload


def _resolve_commitment_event(
    events: list[Mapping[str, Any]],
    *,
    known_cutoff: _Temporal | None = None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    commitments = [event for event in events if event.get("kind") == "committed"]
    if len(commitments) == 0:
        return None, "COMMITMENT_CUTOFF_UNUSABLE"

    by_id: dict[str, Mapping[str, Any]] = {}
    for event in commitments:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in by_id:
            return None, "COMMITMENT_CUTOFF_UNUSABLE"
        by_id[event_id] = event

    parents: dict[str, str] = {}
    children: set[str] = set()
    for event_id, event in by_id.items():
        supersedes = (
            _field("missing")
            if "supersedes_event_id" not in event
            else _field_from_record(event.get("supersedes_event_id"))
        )
        if supersedes.get("state") in {"missing", "not_applicable"}:
            continue
        if supersedes.get("state") != "present":
            return None, "COMMITMENT_CUTOFF_UNUSABLE"
        parent_id = supersedes.get("value")
        parent = by_id.get(parent_id) if isinstance(parent_id, str) else None
        if (
            parent is None
            or parent_id == event_id
            or parent.get("kind") != event.get("kind")
            or parent.get("order_line_id") != event.get("order_line_id")
        ):
            return None, "COMMITMENT_CUTOFF_UNUSABLE"
        parents[event_id] = parent_id
        if parent_id in children:
            return None, "COMMITMENT_CUTOFF_UNUSABLE"
        children.add(parent_id)

    for start in parents:
        seen: set[str] = set()
        current = start
        while current in parents:
            if current in seen:
                return None, "COMMITMENT_CUTOFF_UNUSABLE"
            seen.add(current)
            current = parents[current]

    heads = [event_id for event_id in by_id if event_id not in children]
    if len(heads) != 1:
        return None, "COMMITMENT_CUTOFF_UNUSABLE"
    commitment = by_id[heads[0]]
    if known_cutoff is not None:
        current_id = heads[0]
        while current_id in by_id:
            current = by_id[current_id]
            current_known = _temporal_from_record(
                current.get("clocks", {}).get("known_at")
            )
            known_order = _compare(current_known, known_cutoff)
            if known_order is None or known_order == 1:
                return None, "COMMITMENT_CUTOFF_UNUSABLE"
            parent_id = parents.get(current_id)
            if parent_id is None:
                break
            current_id = parent_id
    occurred = _temporal_from_record(
        commitment.get("clocks", {}).get("occurred_at")
    )
    known = _temporal_from_record(commitment.get("clocks", {}).get("known_at"))
    comparison = _compare(known, occurred)
    if comparison is None or comparison == 1:
        return None, "COMMITMENT_CUTOFF_UNUSABLE"
    return commitment, None


def resolve_commitment_cutoff(
    events: list[Mapping[str, Any]],
    *,
    known_cutoff: _Temporal | None = None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Validate and resolve the public commitment-cutoff contract seam."""
    return _resolve_commitment_event(events, known_cutoff=known_cutoff)


@dataclass(frozen=True, slots=True)
class FrozenPromiseResolution:
    value: _Temporal | None
    code: str | None


def _lineage_observation_refs(
    lineage: Mapping[str, Any],
    order_line_id: str,
    event_ids: list[str],
    *,
    known_at: _Temporal | None = None,
) -> list[str]:
    records = lineage.get("source_observations", [])
    if not isinstance(records, list):
        return []
    allowed = {order_line_id, *event_ids}
    refs = {
        str(record["source_observation_id"])
        for record in records
        if isinstance(record, Mapping)
        and record.get("target_record_id") in allowed
        and isinstance(record.get("source_observation_id"), str)
        and (
            known_at is None
            or _known_by_cutoff(record, known_at)
        )
    }
    return sorted(refs)


def _lineage_mapping_refs(
    lineage: Mapping[str, Any],
    *,
    include_advisory: bool = False,
) -> list[str]:
    manifest = lineage.get("mapping_manifest")
    if not isinstance(manifest, Mapping):
        return []
    refs: set[str] = set()
    manifest_id = manifest.get("mapping_manifest_id")
    if isinstance(manifest_id, str) and manifest_id:
        refs.add(f"mapping-manifest:{manifest_id}")
    used_mapping_names = {
        "identity_mappings": {"order_line_id", "supplier_id"},
        "field_mappings": {
            "material_class",
            "complexity_class",
            "quantity",
            "value",
            "project_id",
            "project_phase",
            "urgency_class",
            "geography_code",
            "contract_form",
        },
        "advisory_context_mappings": (
            {"material_or_equipment"} if include_advisory else set()
        ),
    }
    for mapping_group, names in used_mapping_names.items():
        mappings = manifest.get(mapping_group)
        if not isinstance(mappings, Mapping):
            continue
        for name in names:
            mapping = mappings.get(name)
            if not isinstance(mapping, Mapping):
                continue
            rule_id = mapping.get("rule_id")
            rule_version = mapping.get("rule_version")
            if isinstance(rule_id, str) and isinstance(rule_version, str):
                refs.add(f"mapping-rule:{rule_id}:{rule_version}")

    entries = manifest.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, Mapping) or entry.get("canonical") not in {
                "order_line_event",
                "source_observation",
            }:
                continue
            rule_id = entry.get("rule_id")
            rule_version = entry.get("rule_version")
            if isinstance(rule_id, str) and isinstance(rule_version, str):
                refs.add(f"mapping-rule:{rule_id}:{rule_version}")
    return sorted(refs)


def _lineage_evidence_refs(
    lineage: Mapping[str, Any],
    observation_ids: list[str],
) -> list[str]:
    selected = set(observation_ids)
    refs: set[str] = set()
    for observation in lineage.get("source_observations", []):
        if not isinstance(observation, Mapping):
            continue
        if observation.get("source_observation_id") not in selected:
            continue
        evidence_refs = observation.get("evidence_refs", [])
        if isinstance(evidence_refs, list):
            refs.update(
                str(reference)
                for reference in evidence_refs
                if isinstance(reference, str) and reference
            )
    return sorted(refs)


def _selected_order_line_ids(
    lineage: Mapping[str, Any],
    *,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: _Temporal,
    target_milestone_kind: str,
) -> tuple[list[str], str | None]:
    selected: list[str] = []
    for order_line in lineage.get("order_lines", []):
        if not isinstance(order_line, Mapping):
            continue
        order_line_id = order_line.get("order_line_id")
        if not isinstance(order_line_id, str):
            continue
        commitments = [
            event
            for event in lineage.get("order_line_events", [])
            if isinstance(event, Mapping)
            and event.get("order_line_id") == order_line_id
            and event.get("kind") == "committed"
        ]
        if not commitments:
            continue
        commitment, commitment_error = _resolve_commitment_event(
            commitments,
        )
        if commitment is None or commitment_error is not None:
            return [], "COMMITMENT_CUTOFF_UNUSABLE"
        commitment_occurred_at = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        commitment_known_at = _temporal_from_record(
            commitment.get("clocks", {}).get("known_at")
        )
        commitment_known_order = _compare(commitment_known_at, decision_cutoff)
        commitment_order = _compare(commitment_occurred_at, decision_cutoff)
        if commitment_order is None:
            return [], "COMMITMENT_CUTOFF_UNUSABLE"
        if (
            order_line_id == subject_id and commitment_order != 0
        ) or (order_line_id != subject_id and commitment_order != -1):
            continue
        if commitment_known_order is None or commitment_known_order == 1:
            return [], "COMMITMENT_CUTOFF_UNUSABLE"
        supplier = _subject_field_as_of(
            lineage,
            order_line_id=order_line_id,
            field_path="supplier_id",
            canonical_value={
                "state": "present",
                "value": order_line.get("supplier_id"),
            },
            cutoff=commitment_occurred_at,
        )
        if supplier.get("state") != "present":
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        if supplier.get("value") != subject_supplier_id:
            continue

        unresolved_closure = False
        closed = False
        for event in lineage.get("order_line_events", []):
            if not isinstance(event, Mapping) or event.get("order_line_id") != order_line_id:
                continue
            if event.get("kind") not in {"milestone_reached", "cancelled"}:
                continue
            if event.get("kind") == "milestone_reached" and _field_from_record(
                event.get("milestone_kind")
            ).get("value") != target_milestone_kind:
                continue
            event_occurred_at = _temporal_from_record(
                event.get("clocks", {}).get("occurred_at")
            )
            event_known_at = _temporal_from_record(
                event.get("clocks", {}).get("known_at")
            )
            event_known_order = _compare(event_known_at, decision_cutoff)
            if event_known_order is None:
                unresolved_closure = True
                break
            if event_known_order == 1:
                continue
            event_order = _compare(event_occurred_at, decision_cutoff)
            if event_order is None:
                unresolved_closure = True
                break
            if event_order in {-1, 0}:
                closed = True
                break
        if not unresolved_closure and not closed:
            selected.append(order_line_id)
        elif unresolved_closure:
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
    return sorted(selected), None


def _window_ref(
    *,
    selector_version: str,
    selected_ids: list[str],
    observation_cutoff: _Temporal,
    subject_id: str,
    remove_subject: bool,
) -> dict[str, Any]:
    post_subject_ids = [item for item in selected_ids if item != subject_id]
    return {
        "selector_version": selector_version,
        "bounds": {
            "known_at_lower": "unbounded",
            "known_at_upper": observation_cutoff.field,
        },
        "selected_identity_hash": _sha256(selected_ids),
        "selected_count": len(selected_ids),
        "subject_removal": {
            "subject_identity": subject_id,
            "removed": remove_subject and subject_id in selected_ids,
            "post_subject_identity_hash": _sha256(post_subject_ids),
        },
    }


def _historical_population_digest(
    lineage: Mapping[str, Any],
    selected_ids: list[str],
    *,
    decision_cutoff: _Temporal,
) -> str:
    lines = {
        str(item.get("order_line_id")): item
        for item in lineage.get("order_lines", [])
        if isinstance(item, Mapping) and isinstance(item.get("order_line_id"), str)
    }
    population = []
    for order_line_id in selected_ids:
        if order_line_id not in lines:
            continue
        line_events = [
            event
            for event in lineage.get("order_line_events", [])
            if isinstance(event, Mapping)
            and event.get("order_line_id") == order_line_id
        ]
        commitment, commitment_error = _resolve_commitment_event(
            line_events,
            known_cutoff=decision_cutoff,
        )
        if commitment is None or commitment_error is not None:
            continue
        commitment_cutoff = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        supplier = _subject_field_as_of(
            lineage,
            order_line_id=order_line_id,
            field_path="supplier_id",
            canonical_value={
                "state": "present",
                "value": lines[order_line_id].get("supplier_id"),
            },
            cutoff=commitment_cutoff,
        )
        population.append(
            {
                "order_line_id": order_line_id,
                "supplier_id": supplier,
                "commitment_cutoff": commitment_cutoff.field,
                "included_by_cutoff": _compare(
                    commitment_cutoff,
                    decision_cutoff,
                )
                in {-1, 0},
            }
        )
    return _sha256(population)


def _known_by_cutoff(record: Mapping[str, Any], cutoff: _Temporal) -> bool:
    return _compare(
        _temporal_from_record(record.get("known_at")),
        cutoff,
    ) in {-1, 0}


def _subject_field_as_of(
    lineage: Mapping[str, Any],
    *,
    order_line_id: str,
    field_path: str,
    canonical_value: Any,
    cutoff: _Temporal,
) -> dict[str, Any]:
    observations = [
        observation
        for observation in lineage.get("source_observations", [])
        if isinstance(observation, Mapping)
        and observation.get("target_record_id") == order_line_id
        and observation.get("target_field_path") == field_path
    ]
    canonical = _field_from_record(canonical_value)
    if not observations:
        return canonical if canonical.get("state") != "present" else _field("unresolved")

    known_orders = [
        _compare(_temporal_from_record(observation.get("known_at")), cutoff)
        for observation in observations
    ]
    # A final canonical record is usable as-of a cutoff only when every
    # observation for that field is resolved at or before the cutoff. If a
    # later or unknown observation exists, the final value cannot stand in for
    # the historical value without a governed snapshot.
    if any(order is None or order == 1 for order in known_orders):
        return _field("unresolved")

    value_tokens: list[str] = []
    for observation in observations:
        token = observation.get("canonical_value")
        if token is None:
            token = observation.get("source_value_fingerprint")
        if token is None:
            return _field("unresolved")
        try:
            value_tokens.append(_canonical_json(token))
        except (TypeError, ValueError):
            return _field("unresolved")
    if len(set(value_tokens)) != 1:
        return _field("unresolved")
    return canonical


def _resolve_frozen_promise(
    events: list[Mapping[str, Any]],
    *,
    target_milestone_kind: str,
    commitment_cutoff: _Temporal,
) -> FrozenPromiseResolution:
    all_promises: dict[str, Mapping[str, Any]] = {}
    for event in events:
        if event.get("kind") not in {"promise_recorded", "promise_revised"}:
            continue
        if _field_from_record(event.get("milestone_kind")).get("value") != (
            target_milestone_kind
        ):
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in all_promises:
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
        all_promises[event_id] = event

    # A correction remains evidence even when it was learned after the
    # commitment cutoff. A contradictory supersession cannot silently rewrite
    # the frozen baseline or disappear behind the point-in-time filter.
    for event_id, event in all_promises.items():
        supersedes = (
            _field("missing")
            if "supersedes_event_id" not in event
            else _field_from_record(event.get("supersedes_event_id"))
        )
        if supersedes.get("state") != "present":
            if supersedes.get("state") not in {"missing", "not_applicable"}:
                return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
            continue
        parent_id = supersedes.get("value")
        parent = all_promises.get(parent_id) if isinstance(parent_id, str) else None
        if (
            parent is None
            or parent_id == event_id
            or parent.get("order_line_id") != event.get("order_line_id")
        ):
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
        parent_promise = _temporal_from_record(parent.get("promised_for"))
        corrected_promise = _temporal_from_record(event.get("promised_for"))
        if _equal_temporal(parent_promise, corrected_promise) is not True:
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")

    eligible: dict[str, Mapping[str, Any]] = {}
    for event_id, event in all_promises.items():
        occurred_at = _temporal_from_record(
            event.get("clocks", {}).get("occurred_at")
        )
        known_at = _temporal_from_record(event.get("clocks", {}).get("known_at"))
        if (
            _compare(occurred_at, commitment_cutoff) not in {-1, 0}
            or _compare(known_at, commitment_cutoff) not in {-1, 0}
        ):
            continue
        promised_for = _temporal_from_record(event.get("promised_for"))
        if promised_for.field.get("state") != "present":
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_TEMPORALLY_INVALID")
        promise_order = _compare(promised_for, commitment_cutoff)
        if promise_order is None or promise_order != 1:
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_TEMPORALLY_INVALID")
        eligible[event_id] = event

    if not eligible:
        return FrozenPromiseResolution(None, "FROZEN_PROMISE_UNAVAILABLE")
    children: set[str] = set()
    for event_id, event in eligible.items():
        parent = (
            _field("missing")
            if "revises_promise_event_id" not in event
            else _field_from_record(event.get("revises_promise_event_id"))
        )
        supersedes = (
            _field("missing")
            if "supersedes_event_id" not in event
            else _field_from_record(event.get("supersedes_event_id"))
        )
        if parent.get("state") == "present":
            parent_id = parent.get("value")
            if not isinstance(parent_id, str) or parent_id not in eligible:
                return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
            children.add(parent_id)
        elif parent.get("state") not in {"missing", "not_applicable"}:
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
        if supersedes.get("state") == "present":
            parent_id = supersedes.get("value")
            if not isinstance(parent_id, str) or parent_id not in eligible:
                return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
            children.add(parent_id)
        elif supersedes.get("state") not in {"missing", "not_applicable"}:
            return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
    heads = [event_id for event_id in eligible if event_id not in children]
    if len(heads) != 1:
        return FrozenPromiseResolution(None, "FROZEN_PROMISE_CONFLICT")
    return FrozenPromiseResolution(
        _temporal_from_record(eligible[heads[0]].get("promised_for")),
        None,
    )


def resolve_frozen_promise(
    events: list[Mapping[str, Any]],
    *,
    target_milestone_kind: str,
    commitment_cutoff: _Temporal,
) -> FrozenPromiseResolution:
    """Resolve the public frozen-promise validation contract seam."""
    return _resolve_frozen_promise(
        events,
        target_milestone_kind=target_milestone_kind,
        commitment_cutoff=commitment_cutoff,
    )


def evaluate_supplier_load_exposure(
    *,
    current_load_count: int,
    history_load_counts: list[int],
    duration_basis: str,
) -> dict[str, Any]:
    """Evaluate the locked load threshold rules at their public seam."""
    result: dict[str, Any] = {
        "schema_version": _LOAD_EXPOSURE_SCHEMA_VERSION,
        "duration_basis": duration_basis,
        "current_load_count": current_load_count,
        "valid_history_count": len(history_load_counts),
        "history_load_counts": sorted(history_load_counts),
        "variants": {},
    }
    if duration_basis not in {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}:
        result["primary"] = {
            "state": "unresolved",
            "eligibility_codes": ["SLIPPAGE_DURATION_BASIS_MIXED"],
        }
        result["variants"]["placebo_treatment_within_supplier"] = {
            "state": "not_run",
            "rule_id": "placebo-treatment-within-supplier.v1",
            "replaces_primary": False,
        }
        return result
    if (
        not isinstance(current_load_count, int)
        or isinstance(current_load_count, bool)
        or current_load_count < 0
        or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            for value in history_load_counts
        )
    ):
        result["primary"] = {
            "state": "unresolved",
            "eligibility_codes": ["LOAD_SNAPSHOT_UNRESOLVABLE"],
        }
        result["variants"]["placebo_treatment_within_supplier"] = {
            "state": "not_run",
            "rule_id": "placebo-treatment-within-supplier.v1",
            "replaces_primary": False,
        }
        return result

    sorted_history = sorted(history_load_counts)
    result["history_load_counts"] = sorted_history
    for variant_id, percentile, minimum_history, rule_id in _LOAD_EXPOSURE_VARIANTS:
        variant: dict[str, Any] = {
            "state": "ineligible",
            "variant_id": variant_id,
            "threshold_rule_id": rule_id,
            "percentile": percentile,
            "minimum_history": minimum_history,
            "valid_history_count": len(sorted_history),
            "threshold_rank": None,
            "threshold": None,
            "high_load_exposure": None,
            "load_percentile": None,
            "eligibility_codes": [],
            "replaces_primary": variant_id == "primary",
        }
        if len(sorted_history) < minimum_history:
            variant["eligibility_codes"] = ["SUPPLIER_HISTORY_INSUFFICIENT"]
        else:
            rank = math.ceil(percentile * len(sorted_history))
            threshold = sorted_history[rank - 1]
            variant.update(
                {
                    "state": "present",
                    "threshold_rank": rank,
                    "threshold": threshold,
                    "high_load_exposure": current_load_count > threshold,
                    "load_percentile": (
                        sum(value < current_load_count for value in sorted_history)
                        + 0.5
                        * sum(value == current_load_count for value in sorted_history)
                    )
                    / len(sorted_history),
                }
            )
        result[variant_id] = variant
        result["variants"][variant_id] = variant

    continuous = {
        "state": "ineligible",
        "variant_id": "continuous_load",
        "rule_id": "history-midranks.v1",
        "minimum_history": _PRIMARY_LOAD_MINIMUM_HISTORY,
        "valid_history_count": len(sorted_history),
        "load_percentile": None,
        "reuses_primary_first_exposure_block": True,
        "eligibility_codes": [],
        "replaces_primary": False,
    }
    if len(sorted_history) < _PRIMARY_LOAD_MINIMUM_HISTORY:
        continuous["eligibility_codes"] = ["SUPPLIER_HISTORY_INSUFFICIENT"]
    else:
        continuous["state"] = "present"
        continuous["load_percentile"] = result["primary"]["load_percentile"]
    result["variants"]["continuous_load"] = continuous
    result["variants"]["placebo_treatment_within_supplier"] = {
        "state": "not_run",
        "variant_id": "placebo_treatment_within_supplier",
        "rule_id": "placebo-treatment-within-supplier.v1",
        "replaces_primary": False,
        "eligibility_codes": [],
    }
    return result


def _event_reference(event: Mapping[str, Any], field_name: str) -> str | None:
    raw = event.get(field_name)
    if isinstance(raw, str) and raw:
        return raw
    value = _field_from_record(raw)
    if value.get("state") == "present" and isinstance(value.get("value"), str):
        return str(value["value"])
    return None


def _visible_terminal_events(
    events: list[Mapping[str, Any]],
    *,
    cutoff: _Temporal,
    target_milestone_kind: str,
) -> tuple[list[Mapping[str, Any]], str | None]:
    visible: dict[str, Mapping[str, Any]] = {}
    for event in events:
        kind = event.get("kind")
        if kind not in {"milestone_reached", "cancelled"}:
            continue
        if kind == "milestone_reached":
            milestone = _field_from_record(event.get("milestone_kind"))
            if milestone.get("state") == "present":
                if milestone.get("value") != target_milestone_kind:
                    continue
            elif milestone.get("state") in {"missing", "not_applicable"}:
                known = _temporal_from_record(event.get("clocks", {}).get("known_at"))
                known_order = _compare(known, cutoff)
                if known_order == 1:
                    continue
                return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
            else:
                known = _temporal_from_record(event.get("clocks", {}).get("known_at"))
                if _compare(known, cutoff) == 1:
                    continue
                return [], "LOAD_SNAPSHOT_UNRESOLVABLE"

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in visible:
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        known = _temporal_from_record(event.get("clocks", {}).get("known_at"))
        known_order = _compare(known, cutoff)
        if known_order is None:
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        if known_order == 1:
            continue
        occurred = _temporal_from_record(event.get("clocks", {}).get("occurred_at"))
        occurred_order = _compare(occurred, cutoff)
        if occurred_order is None or _compare(known, occurred) == -1:
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        visible[event_id] = event

    superseded: set[str] = set()
    for event_id, event in visible.items():
        parent_id = _event_reference(event, "supersedes_event_id")
        raw_parent = event.get("supersedes_event_id")
        parent_state = _field_from_record(raw_parent).get("state")
        if isinstance(raw_parent, str) and raw_parent:
            parent_state = "present"
        if parent_state in {"missing", "not_applicable"}:
            continue
        if parent_state != "present" or parent_id is None:
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        parent = visible.get(parent_id)
        if (
            parent is None
            or parent.get("kind") != event.get("kind")
            or parent.get("order_line_id") != event.get("order_line_id")
        ):
            return [], "LOAD_SNAPSHOT_UNRESOLVABLE"
        superseded.add(parent_id)

    return [event for event_id, event in visible.items() if event_id not in superseded], None


def _load_snapshot_failure(
    *,
    code: str,
    duration_basis: str,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: _Temporal,
) -> dict[str, Any]:
    identity = {
        "subject_id": subject_id,
        "subject_supplier_id": subject_supplier_id,
        "decision_cutoff": decision_cutoff.field,
        "duration_basis": duration_basis,
        "eligibility_codes": [code],
    }
    return {
        "schema_version": "supplier-load-snapshot.v1",
        "state": "unresolved",
        "duration_basis": duration_basis,
        "decision_cutoff": decision_cutoff.field,
        "concurrent_load_count": None,
        "contributing_order_line_ids": [],
        "lineage_refs": [],
        "eligibility_codes": [code],
        "snapshot_hash": _sha256(identity),
    }


def _has_commitment_at_or_before(
    events: list[Mapping[str, Any]],
    cutoff: _Temporal,
) -> bool | None:
    commitments = [event for event in events if event.get("kind") == "committed"]
    if not commitments:
        return False
    candidate = False
    for commitment in commitments:
        occurred = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        order = _compare(occurred, cutoff)
        if order is None:
            return None
        candidate = candidate or order in {-1, 0}
    return candidate


def resolve_supplier_load_snapshot(
    lineage: Mapping[str, Any],
    *,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: _Temporal,
    target_milestone_kind: str,
    duration_basis: str,
) -> dict[str, Any]:
    """Resolve one canonical point-in-time Supplier Load Snapshot."""
    if duration_basis not in {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}:
        return _load_snapshot_failure(
            code="SLIPPAGE_DURATION_BASIS_MIXED",
            duration_basis=duration_basis,
            subject_id=subject_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=decision_cutoff,
        )
    if target_milestone_kind not in {"supplier_completion", "supplier_handoff"}:
        return _load_snapshot_failure(
            code="LOAD_SNAPSHOT_UNRESOLVABLE",
            duration_basis=duration_basis,
            subject_id=subject_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=decision_cutoff,
        )
    if (
        not subject_id
        or not subject_supplier_id
        or decision_cutoff.field.get("state") != "present"
    ):
        return _load_snapshot_failure(
            code="LOAD_SNAPSHOT_UNRESOLVABLE",
            duration_basis=duration_basis,
            subject_id=subject_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=decision_cutoff,
        )

    contributing: list[str] = []
    evidence_refs: set[str] = set()
    order_lines = lineage.get("order_lines", [])
    if not isinstance(order_lines, list):
        return _load_snapshot_failure(
            code="LOAD_SNAPSHOT_UNRESOLVABLE",
            duration_basis=duration_basis,
            subject_id=subject_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=decision_cutoff,
        )
    events_by_line: dict[str, list[Mapping[str, Any]]] = {}
    for event in lineage.get("order_line_events", []):
        if not isinstance(event, Mapping):
            continue
        order_line_id = event.get("order_line_id")
        if isinstance(order_line_id, str) and order_line_id:
            events_by_line.setdefault(order_line_id, []).append(event)

    seen_order_line_ids: set[str] = set()
    for order_line in order_lines:
        if not isinstance(order_line, Mapping):
            return _load_snapshot_failure(
                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        order_line_id = order_line.get("order_line_id")
        if not isinstance(order_line_id, str) or not order_line_id:
            return _load_snapshot_failure(
                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        if order_line_id in seen_order_line_ids:
            return _load_snapshot_failure(
                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        seen_order_line_ids.add(order_line_id)
        if order_line_id == subject_id:
            continue

        line_events = events_by_line.get(order_line_id, [])
        candidate = _has_commitment_at_or_before(line_events, decision_cutoff)
        if candidate is None:
            return _load_snapshot_failure(
                code="COMMITMENT_CUTOFF_UNUSABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        if not candidate:
            continue
        commitment, commitment_error = _resolve_commitment_event(
            line_events,
            known_cutoff=decision_cutoff,
        )
        if commitment is None:
            return _load_snapshot_failure(
                code=commitment_error or "COMMITMENT_CUTOFF_UNUSABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        commitment_occurred = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        commitment_known = _temporal_from_record(
            commitment.get("clocks", {}).get("known_at")
        )
        if _compare(commitment_occurred, decision_cutoff) is None:
            return _load_snapshot_failure(
                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        if _compare(commitment_known, decision_cutoff) is None:
            return _load_snapshot_failure(
                code="COMMITMENT_CUTOFF_UNUSABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        if (
            _compare(commitment_occurred, decision_cutoff) != -1
            or _compare(commitment_known, decision_cutoff) == 1
        ):
            continue

        supplier = _subject_field_as_of(
            lineage,
            order_line_id=order_line_id,
            field_path="supplier_id",
            canonical_value={"state": "present", "value": order_line.get("supplier_id")},
            cutoff=decision_cutoff,
        )
        if supplier.get("state") != "present":
            return _load_snapshot_failure(
                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        if supplier.get("value") != subject_supplier_id:
            continue

        terminal_events, terminal_error = _visible_terminal_events(
            line_events,
            cutoff=decision_cutoff,
            target_milestone_kind=target_milestone_kind,
        )
        if terminal_error is not None:
            return _load_snapshot_failure(
                code=terminal_error,
                duration_basis=duration_basis,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision_cutoff,
            )
        closed = False
        for terminal in terminal_events:
            occurred = _temporal_from_record(
                terminal.get("clocks", {}).get("occurred_at")
            )
            relative_to_commitment = _compare(occurred, commitment_occurred)
            relative_to_cutoff = _compare(occurred, decision_cutoff)
            if relative_to_commitment is None or relative_to_cutoff is None:
                return _load_snapshot_failure(
                    code="LOAD_SNAPSHOT_UNRESOLVABLE",
                    duration_basis=duration_basis,
                    subject_id=subject_id,
                    subject_supplier_id=subject_supplier_id,
                    decision_cutoff=decision_cutoff,
                )
            if relative_to_commitment != 1:
                return _load_snapshot_failure(
                    code="LOAD_SNAPSHOT_UNRESOLVABLE",
                    duration_basis=duration_basis,
                    subject_id=subject_id,
                    subject_supplier_id=subject_supplier_id,
                    decision_cutoff=decision_cutoff,
                )
            if relative_to_cutoff in {-1, 0}:
                closed = True
                break
        if not closed:
            contributing.append(order_line_id)
            event_ids = [
                str(item.get("event_id"))
                for item in line_events
                if isinstance(item.get("event_id"), str)
            ]
            refs = _lineage_observation_refs(
                lineage,
                order_line_id,
                event_ids,
                known_at=decision_cutoff,
            )
            evidence_refs.update(refs)
            evidence_refs.update(_lineage_evidence_refs(lineage, refs))

    contributing.sort()
    identity = {
        "subject_id": subject_id,
        "subject_supplier_id": subject_supplier_id,
        "decision_cutoff": decision_cutoff.field,
        "target_milestone_kind": target_milestone_kind,
        "duration_basis": duration_basis,
        "contributing_order_line_ids": contributing,
        "lineage_refs": sorted(evidence_refs),
    }
    return {
        "schema_version": "supplier-load-snapshot.v1",
        "state": "present",
        "duration_basis": duration_basis,
        "decision_cutoff": decision_cutoff.field,
        "concurrent_load_count": len(contributing),
        "contributing_order_line_ids": contributing,
        "lineage_refs": sorted(evidence_refs),
        "eligibility_codes": [],
        "snapshot_hash": _sha256(identity),
    }


def _unresolved_load_exposure(
    *,
    trigger_mode: str,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: _Temporal,
    duration_basis: str,
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    code_values = snapshot.get("eligibility_codes", [])
    codes = sorted(
        {
            str(code)
            for code in code_values
            if isinstance(code, str) and code
        }
    )
    result: dict[str, Any] = {
        "schema_version": _LOAD_EXPOSURE_SCHEMA_VERSION,
        "state": "unresolved",
        "trigger_mode": trigger_mode,
        "subject_id": subject_id,
        "subject_supplier_id": subject_supplier_id,
        "decision_cutoff": decision_cutoff.field,
        "cutoff_source": (
            "proactive_decision"
            if trigger_mode == "proactive"
            else "canonical_commitment"
        ),
        "duration_basis": duration_basis,
        "eligibility_codes": codes,
        "history": {
            "state": "unavailable",
            "load_counts": [],
            "valid_history_count": 0,
            "qualifying_snapshots": [],
            "identity_hash": _sha256([]),
            "selector": {
                "selector_version": HISTORY_LOOKBACK_SELECTOR_VERSION,
                "selected_identity_hash": _sha256([]),
                "selected_count": 0,
            },
            "eligibility_codes": codes,
        },
        "variants": {
            "placebo_treatment_within_supplier": {
                "state": "not_run",
                "variant_id": "placebo_treatment_within_supplier",
                "rule_id": "placebo-treatment-within-supplier.v1",
                "replaces_primary": False,
                "eligibility_codes": [],
            }
        },
    }
    if trigger_mode == "proactive":
        result["provisional_load_snapshot"] = _preview_snapshot(snapshot)
    else:
        result["load_snapshot"] = snapshot
    result["derivation_hash"] = _sha256(result)
    return result


def _preview_variant(variant: Mapping[str, Any]) -> dict[str, Any]:
    preview = deepcopy(dict(variant))
    if "high_load_exposure" in preview:
        preview["provisional_high_load_preview"] = preview.pop("high_load_exposure")
    return preview


def _preview_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    preview = deepcopy(dict(snapshot))
    identities = preview.pop("contributing_order_line_ids", [])
    preview["contributing_canonical_line_identities"] = identities
    return preview


def _preview_history(history: Mapping[str, Any]) -> dict[str, Any]:
    preview = deepcopy(dict(history))
    snapshots = []
    for snapshot in preview.get("qualifying_snapshots", []):
        if not isinstance(snapshot, Mapping):
            continue
        item = dict(snapshot)
        if "order_line_id" in item:
            item["canonical_line_identity"] = item.pop("order_line_id")
        snapshots.append(item)
    preview["qualifying_snapshots"] = snapshots
    return preview


def derive_supplier_load_exposure(
    lineage: Mapping[str, Any],
    *,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: _Temporal,
    target_milestone_kind: str,
    duration_basis: str,
    trigger_mode: str,
) -> dict[str, Any]:
    """Derive a canonical exposure or a preview from frozen lineage facts."""
    snapshot = resolve_supplier_load_snapshot(
        lineage,
        subject_id=subject_id,
        subject_supplier_id=subject_supplier_id,
        decision_cutoff=decision_cutoff,
        target_milestone_kind=target_milestone_kind,
        duration_basis=duration_basis,
    )
    if snapshot.get("state") != "present":
        return _unresolved_load_exposure(
            trigger_mode=trigger_mode,
            subject_id=subject_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=decision_cutoff,
            duration_basis=duration_basis,
            snapshot=snapshot,
        )

    lines_by_id: dict[str, Mapping[str, Any]] = {}
    for order_line in lineage.get("order_lines", []):
        if not isinstance(order_line, Mapping):
            continue
        order_line_id = order_line.get("order_line_id")
        if isinstance(order_line_id, str) and order_line_id:
            lines_by_id[order_line_id] = order_line
    events_by_line: dict[str, list[Mapping[str, Any]]] = {}
    for event in lineage.get("order_line_events", []):
        if not isinstance(event, Mapping):
            continue
        order_line_id = event.get("order_line_id")
        if isinstance(order_line_id, str) and order_line_id:
            events_by_line.setdefault(order_line_id, []).append(event)

    history: list[dict[str, Any]] = []
    candidate_ids: list[str] = []
    history_codes: set[str] = set()
    for order_line_id, order_line in lines_by_id.items():
        if trigger_mode == "reactive" and order_line_id == subject_id:
            continue
        line_events = events_by_line.get(order_line_id, [])
        candidate = _has_commitment_at_or_before(line_events, decision_cutoff)
        if candidate is None:
            history_codes.add("COMMITMENT_CUTOFF_UNUSABLE")
            continue
        if not candidate:
            continue
        commitment, commitment_error = _resolve_commitment_event(
            line_events,
            known_cutoff=decision_cutoff,
        )
        if commitment is None:
            history_codes.add(commitment_error or "COMMITMENT_CUTOFF_UNUSABLE")
            continue

        commitment_cutoff = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        commitment_known = _temporal_from_record(
            commitment.get("clocks", {}).get("known_at")
        )
        commitment_order = _compare(commitment_cutoff, decision_cutoff)
        known_order = _compare(commitment_known, decision_cutoff)
        if commitment_order is None or known_order is None:
            history_codes.add("COMMITMENT_CUTOFF_UNUSABLE")
            continue
        if commitment_order != -1 or known_order == 1:
            continue

        supplier = _subject_field_as_of(
            lineage,
            order_line_id=order_line_id,
            field_path="supplier_id",
            canonical_value={
                "state": "present",
                "value": order_line.get("supplier_id"),
            },
            cutoff=commitment_cutoff,
        )
        if supplier.get("state") != "present":
            history_codes.add("LOAD_SNAPSHOT_UNRESOLVABLE")
            continue
        if supplier.get("value") != subject_supplier_id:
            continue

        candidate_ids.append(order_line_id)
        prior_snapshot = resolve_supplier_load_snapshot(
            lineage,
            subject_id=order_line_id,
            subject_supplier_id=subject_supplier_id,
            decision_cutoff=commitment_cutoff,
            target_milestone_kind=target_milestone_kind,
            duration_basis=duration_basis,
        )
        if prior_snapshot.get("state") != "present":
            history_codes.update(
                str(code)
                for code in prior_snapshot.get("eligibility_codes", [])
                if isinstance(code, str) and code
            )
            continue
        history.append(
            {
                "order_line_id": order_line_id,
                "commitment_cutoff": commitment_cutoff.field,
                "concurrent_load_count": prior_snapshot["concurrent_load_count"],
                "snapshot_hash": prior_snapshot["snapshot_hash"],
                "lineage_refs": prior_snapshot.get("lineage_refs", []),
            }
        )

    history.sort(
        key=lambda item: (
            _canonical_json(item["commitment_cutoff"]),
            item["order_line_id"],
        )
    )
    history_counts = [int(item["concurrent_load_count"]) for item in history]
    history_identity = {
        "subject_id": subject_id,
        "subject_supplier_id": subject_supplier_id,
        "decision_cutoff": decision_cutoff.field,
        "duration_basis": duration_basis,
        "qualifying_snapshots": history,
    }
    history_hash = _sha256(history_identity)
    rule_result = evaluate_supplier_load_exposure(
        current_load_count=int(snapshot["concurrent_load_count"]),
        history_load_counts=history_counts,
        duration_basis=duration_basis,
    )
    history_state = "present" if not history_codes else "present_with_exclusions"
    history_output = {
        "state": history_state,
        "load_counts": sorted(history_counts),
        "valid_history_count": len(history),
        "qualifying_snapshots": history,
        "identity_hash": history_hash,
        "selector": {
            "selector_version": HISTORY_LOOKBACK_SELECTOR_VERSION,
            "selected_identity_hash": _sha256(sorted(candidate_ids)),
            "selected_count": len(candidate_ids),
        },
        "eligibility_codes": sorted(history_codes),
    }
    variants = {
        variant_id: {
            **deepcopy(dict(variant)),
            "duration_basis": duration_basis,
            "history_identity_hash": history_hash,
        }
        for variant_id, variant in rule_result["variants"].items()
    }
    primary = {
        **deepcopy(dict(rule_result["primary"])),
        "duration_basis": duration_basis,
        "history_identity_hash": history_hash,
    }
    if trigger_mode == "proactive":
        primary = _preview_variant(primary)
        variants = {
            variant_id: _preview_variant(variant)
            for variant_id, variant in variants.items()
        }
        history_output = _preview_history(history_output)

    root: dict[str, Any] = {
        "schema_version": _LOAD_EXPOSURE_SCHEMA_VERSION,
        "state": "present",
        "trigger_mode": trigger_mode,
        "subject_id": subject_id,
        "subject_supplier_id": subject_supplier_id,
        "decision_cutoff": decision_cutoff.field,
        "cutoff_source": (
            "proactive_decision"
            if trigger_mode == "proactive"
            else "canonical_commitment"
        ),
        "duration_basis": duration_basis,
        "history": history_output,
        "valid_history_count": len(history),
        "primary": primary,
        "variants": variants,
        "eligibility_codes": sorted(
            set(history_codes)
            | {
                str(code)
                for code in primary.get("eligibility_codes", [])
                if isinstance(code, str)
            }
        ),
    }
    if trigger_mode == "proactive":
        root.update(
            {
                "provisional_load_snapshot": _preview_snapshot(snapshot),
                "provisional_concurrent_load_count": snapshot[
                    "concurrent_load_count"
                ],
                "provisional_load_percentile": primary.get("load_percentile"),
                "provisional_high_load_preview": primary.get(
                    "provisional_high_load_preview"
                ),
            }
        )
    else:
        root.update(
            {
                "load_snapshot": snapshot,
                "concurrent_load_count": snapshot["concurrent_load_count"],
                "load_percentile": primary.get("load_percentile"),
                "high_load_exposure": primary.get("high_load_exposure"),
            }
        )
    root["selector"] = {
        "history_lookback": history_output["selector"],
        "duration_basis": duration_basis,
    }
    root["hashes"] = {
        "load_snapshot": snapshot["snapshot_hash"],
        "qualifying_history": history_hash,
        "derivation_inputs": _sha256(
            {
                "snapshot_hash": snapshot["snapshot_hash"],
                "history_hash": history_hash,
                "selector": root["selector"],
                "duration_basis": duration_basis,
            }
        ),
    }
    root["derivation_hash"] = _sha256(root)
    return root


def _duration_basis_at_cutoff(
    configuration: Mapping[str, Any],
    *,
    dataset_version_id: str | None = None,
) -> dict[str, Any]:
    release_ref = configuration.get("temporal_eligibility_release_ref")
    released_rows = configuration.get("released_s8_rows")
    if not isinstance(released_rows, list):
        try:
            with TEMPORAL_ELIGIBILITY_RELEASE_FILE.open(
                "r", encoding="utf-8"
            ) as handle:
                release_manifest = json.load(handle)
        except (OSError, TypeError, ValueError):
            release_manifest = None
        if isinstance(release_manifest, Mapping) and release_manifest.get(
            "schema_version"
        ) == "temporal-eligibility-release-manifest.v1":
            manifest_dataset = release_manifest.get("dataset_version_ref")
            manifest_release = release_manifest.get("release_ref")
            if (
                manifest_release == release_ref
                and (
                    dataset_version_id is None
                    or manifest_dataset == dataset_version_id
                )
            ):
                released_rows = []
                variants = release_manifest.get("variants")
                if isinstance(variants, list):
                    for variant in variants:
                        if not isinstance(variant, Mapping) or variant.get(
                            "release_state"
                        ) != "releasable":
                            continue
                        rows = variant.get("released_s8_rows")
                        if isinstance(rows, list):
                            released_rows.extend(rows)
    active: dict[str, list[str]] = {}
    if isinstance(release_ref, str) and release_ref and isinstance(released_rows, list):
        for row in released_rows:
            if not isinstance(row, Mapping):
                continue
            if row.get("release_ref") != release_ref or row.get("release_state") != "releasable":
                continue
            basis = row.get("supplier_milestone_slippage_duration_basis")
            row_identity = row.get("row_identity")
            if not isinstance(basis, str) or not isinstance(row_identity, str):
                continue
            active.setdefault(basis, []).append(row_identity)
    for identities in active.values():
        identities.sort()
    return {
        "basis": next(iter(active)) if len(active) == 1 else None,
        "counts": {basis: len(identities) for basis, identities in active.items()},
        "identity_hashes": {
            basis: _sha256(identities) for basis, identities in active.items()
        },
    }


def resolve_duration_basis(
    configuration: Mapping[str, Any],
    *,
    dataset_version_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the public released-duration-basis contract seam."""
    return _duration_basis_at_cutoff(
        configuration,
        dataset_version_id=dataset_version_id,
    )


def _resolve_advisory_material_key(
    value: Mapping[str, Any],
    mapping_manifest: Mapping[str, Any],
) -> str | None:
    mappings = mapping_manifest.get("advisory_context_mappings")
    if not isinstance(mappings, Mapping):
        return None
    mapping = mappings.get("material_or_equipment")
    if not isinstance(mapping, Mapping):
        return None
    if (
        mapping.get("rule_id") != "source-material-key-to-material-class.v1"
        or mapping.get("rule_version") != "1"
        or mapping.get("source_namespace") != SOURCE_NAMESPACE
        or mapping.get("source_namespace") != value.get("namespace")
        or mapping.get("target_field") != "fields.material_class"
        or mapping.get("resolution_kind") != "canonical_field_value"
    ):
        return None
    keys = _source_key(value.get("key"))
    if len(keys) != 1:
        return None
    source_key = keys[0]
    # This is the reviewed bundled adapter rule, not a generic trust of the
    # advisory key. Its only supported transformation is the canonical
    # material-class key preserved by the semi-synthetic mapping.
    return source_key


def resolve_field_as_of(
    lineage: Mapping[str, Any],
    *,
    order_line_id: str,
    field_path: str,
    canonical_value: Any,
    cutoff: _Temporal,
) -> dict[str, Any]:
    """Resolve one canonical field through its point-in-time lineage seam."""
    return _subject_field_as_of(
        lineage,
        order_line_id=order_line_id,
        field_path=field_path,
        canonical_value=canonical_value,
        cutoff=cutoff,
    )


def _fixture_signal_payloads(dataset_version_id: str) -> list[dict[str, Any]]:
    with FIXTURE_FILE.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ValueError("risk signal fixture bundle is invalid")
    fixtures: list[dict[str, Any]] = []
    for item in raw["items"]:
        if not isinstance(item, dict):
            raise ValueError("risk signal fixture is invalid")
        signal_payload = deepcopy(item.get("signal"))
        if not isinstance(signal_payload, dict):
            raise ValueError("risk signal fixture has no signal")
        if signal_payload.get("scored_dataset_version_ref") != dataset_version_id:
            raise ValueError("risk signal fixture is bound to another Dataset Version")
        signal = RiskSignalRequest.model_validate(signal_payload)
        expected_source_signal_id = _source_signal_identity(signal.model_dump(mode="json"))
        if signal.source_signal_id != expected_source_signal_id:
            raise ValueError("risk signal fixture has an invalid deterministic identity")
        protected_bytes = _protected_source_bytes(
            signal.source.protected_source_locator
        )
        if protected_bytes is None or protected_bytes != _canonical_json(
            _protected_signal_payload(signal.model_dump(mode="json"))
        ).encode("utf-8"):
            raise ValueError("risk signal fixture does not match its protected source bytes")
        if signal.source.source_payload_sha256 != _fixture_protected_source_digest(signal):
            raise ValueError("risk signal fixture has an invalid protected source digest")
        fixtures.append(
            {
                "fixture_id": str(item.get("fixture_id", "")),
                "label": str(item.get("label", "")),
                "signal": signal.model_dump(mode="json"),
            }
        )
    return fixtures


def _predictive_risk_status() -> dict[str, Any]:
    """Expose a safe predictive-artifact status without leaking internals."""
    try:
        from .predictive import (
            load_predictive_attribution_bundle,
            load_predictive_baseline,
            load_prediction_record_bundle,
            validate_prediction_record_attribution_bindings,
        )

        baseline = load_predictive_baseline(
            PREDICTIVE_ARTIFACT_FILE,
            PREDICTIVE_REPORT_FILE,
        )
        attributions = load_predictive_attribution_bundle(
            PREDICTIVE_ATTRIBUTION_FILE,
            expected_model_artifact_ref=baseline.artifact_ref,
        )
        prediction_records = load_prediction_record_bundle(
            PREDICTIVE_RECORD_FILE,
            expected_model_artifact_ref=baseline.artifact_ref,
        )
        validate_prediction_record_attribution_bindings(prediction_records, attributions)
    except Exception as error:
        code = getattr(error, "code", "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE")
        return {
            "state": "unavailable",
            "code": str(code),
            "message": "Verified predictive artifacts are unavailable; no generated Risk Signal was emitted.",
            "manual_investigation_available": True,
        }
    return {
        "state": "verified",
        "code": "PREDICTIVE_ARTIFACTS_VERIFIED",
        "message": "The bundled predictive artifact, attribution bundle, and prediction records passed integrity checks.",
        "manual_investigation_available": True,
    }


def _predictive_fixture_signal_payloads(dataset_version_id: str) -> list[dict[str, Any]]:
    """Return generated signals only while all local predictive artifacts verify."""
    try:
        from .predictive import (
            PredictiveSubject,
            load_predictive_attribution_bundle,
            load_predictive_baseline,
            load_prediction_record_bundle,
            score_predictive_subject,
            validate_prediction_record_attribution_bindings,
            validate_predictive_attribution,
        )

        baseline = load_predictive_baseline(
            PREDICTIVE_ARTIFACT_FILE,
            PREDICTIVE_REPORT_FILE,
        )
        attributions = load_predictive_attribution_bundle(
            PREDICTIVE_ATTRIBUTION_FILE,
            expected_model_artifact_ref=baseline.artifact_ref,
        )
        prediction_records = load_prediction_record_bundle(
            PREDICTIVE_RECORD_FILE,
            expected_model_artifact_ref=baseline.artifact_ref,
        )
        validate_prediction_record_attribution_bindings(prediction_records, attributions)
        with PREDICTIVE_FIXTURE_FILE.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, Mapping) or not isinstance(raw.get("items"), list):
            return []
        fixtures: list[dict[str, Any]] = []
        for item in raw["items"]:
            if not isinstance(item, Mapping) or item.get("fixture_id") != PREDICTIVE_FIXTURE_ID:
                continue
            signal_payload = deepcopy(item.get("signal"))
            if not isinstance(signal_payload, Mapping):
                continue
            signal = RiskSignalRequest.model_validate(signal_payload)
            if signal.scored_dataset_version_ref != dataset_version_id:
                continue
            if signal.predictor_artifact_ref.value != baseline.artifact_ref:
                continue
            attribution_ref = signal.predictive_attribution_ref.value
            score_value = signal.score_value
            if not isinstance(attribution_ref, str) or attribution_ref not in attributions:
                continue
            source_keys = _source_key(signal.source_order_line_ref.key)
            expected_order_line_id = (
                _canonical_id(SOURCE_NAMESPACE, "order-line", source_keys[0])
                if len(source_keys) == 1
                else None
            )
            delivery_metadata = signal.prediction_delivery_metadata.value
            expected_prediction_record_id = (
                delivery_metadata.get("prediction_record_id")
                if isinstance(delivery_metadata, Mapping)
                else None
            )
            if not isinstance(expected_prediction_record_id, str):
                continue
            attribution = attributions[attribution_ref]
            prediction_record = prediction_records.get(expected_prediction_record_id)
            if prediction_record is None:
                continue
            validate_predictive_attribution(
                attribution,
                expected_score=score_value,
                expected_model_artifact_ref=baseline.artifact_ref,
                expected_prediction_record_id=expected_prediction_record_id,
                expected_dataset_version_id=signal.scored_dataset_version_ref,
                expected_order_line_id=expected_order_line_id,
                expected_background_identity_hash=baseline.report[
                    "background_selector"
                ]["identity_hash"],
            )
            feature_values = attribution.get("feature_values")
            generated_at = attribution.get("generated_at")
            if not isinstance(feature_values, list) or not isinstance(generated_at, str):
                continue
            features = {
                item["name"]: item["value"]
                for item in feature_values
                if isinstance(item, Mapping)
                and isinstance(item.get("name"), str)
                and isinstance(item.get("value"), (int, float))
            }
            if len(features) != len(feature_values):
                continue
            recomputed = score_predictive_subject(
                baseline,
                PredictiveSubject(
                    prediction_record_id=str(attribution["prediction_record_id"]),
                    dataset_version_id=str(attribution["dataset_version_id"]),
                    order_line_id=str(attribution["order_line_id"]),
                    generated_at=datetime.fromisoformat(generated_at),
                    features=features,
                ),
            )
            if (
                recomputed.prediction_record != prediction_record
                or prediction_record["dataset_version_id"]
                != signal.scored_dataset_version_ref
                or prediction_record["order_line_id"] != expected_order_line_id
                or recomputed.prediction_record["score_value"] != score_value
                or recomputed.attribution["artifact_ref"] != attribution_ref
            ):
                continue
            if signal.source.source_payload_sha256 != _fixture_protected_source_digest(signal):
                continue
            protected_bytes = _protected_source_bytes(
                signal.source.protected_source_locator
            )
            if protected_bytes is None or protected_bytes != _canonical_json(
                _protected_signal_payload(signal.model_dump(mode="json"))
            ).encode("utf-8"):
                continue
            expected_source_signal_id = _source_signal_identity(
                signal.model_dump(mode="json")
            )
            if signal.source_signal_id != expected_source_signal_id:
                continue
            fixtures.append(
                {
                    "fixture_id": str(item.get("fixture_id", "")),
                    "label": str(item.get("label", "")),
                    "signal": signal.model_dump(mode="json"),
                }
            )
        return fixtures
    except Exception:
        return []


def _fixture_preview_payloads(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for fixture in fixtures:
        preview_payload = deepcopy(fixture["signal"])
        source = preview_payload.get("source")
        if isinstance(source, dict):
            preview_payload["source"] = {
                key: source[key]
                for key in ("schema_version", "source_system", "data_classification")
            }
        payloads.append(
            RiskSignalFixtureResponse(
                fixture_id=fixture["fixture_id"],
                label=fixture["label"],
                signal=RiskSignalPreviewResponse.model_validate(preview_payload),
            ).model_dump(mode="json")
        )
    return payloads


def _fixture_payloads(dataset_version_id: str) -> list[dict[str, Any]]:
    return _fixture_preview_payloads(_fixture_signal_payloads(dataset_version_id))


def _protected_proactive_payload(proposal_payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(proposal_payload))
    source = payload.get("source")
    if isinstance(source, dict):
        source.pop("source_payload_sha256", None)
    return payload


def _proactive_proposal_payloads(dataset_version_id: str) -> list[dict[str, Any]]:
    with PROACTIVE_FIXTURE_FILE.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ValueError("proactive proposal fixture bundle is invalid")
    fixtures: list[dict[str, Any]] = []
    for item in raw["items"]:
        if not isinstance(item, dict):
            raise ValueError("proactive proposal fixture is invalid")
        proposal_payload = deepcopy(item.get("proposal"))
        if not isinstance(proposal_payload, dict):
            raise ValueError("proactive proposal fixture has no proposal")
        proposal = ProactiveProposalRequest.model_validate(proposal_payload)
        if proposal.dataset_version_id != dataset_version_id:
            raise ValueError("proactive proposal fixture is bound to another Dataset Version")
        protected_payload = _protected_proactive_payload(
            proposal.model_dump(mode="json")
        )
        protected_hash = _sha256(_canonical_json(protected_payload).encode("utf-8"))
        if proposal.source.source_payload_sha256 != protected_hash:
            raise ValueError("proactive proposal fixture has an invalid protected source digest")
        fixtures.append(
            {
                "fixture_id": str(item.get("fixture_id", "")),
                "label": str(item.get("label", "")),
                "proposal": proposal.model_dump(mode="json"),
            }
        )
    return fixtures


def _proactive_proposal_preview_payloads(
    fixtures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for fixture in fixtures:
        proposal_payload = deepcopy(fixture["proposal"])
        source = proposal_payload.get("source")
        if isinstance(source, dict):
            proposal_payload["source"] = {
                key: source[key]
                for key in ("schema_version", "source_system", "data_classification")
            }
        proposal_payload.pop("requester_ref", None)
        payloads.append(
            ProactiveProposalFixtureResponse(
                fixture_id=fixture["fixture_id"],
                label=fixture["label"],
                proposal=ProactiveProposalPreviewResponse.model_validate(
                    proposal_payload
                ),
            ).model_dump(mode="json")
        )
    return payloads


def _matches_bundled_proactive_proposal(
    proposal: ProactiveProposalRequest,
) -> bool:
    try:
        for fixture in _proactive_proposal_payloads(proposal.dataset_version_id):
            fixture_proposal = ProactiveProposalRequest.model_validate(
                fixture["proposal"]
            )
            if (
                _protected_proactive_payload(proposal.model_dump(mode="json"))
                == _protected_proactive_payload(fixture_proposal.model_dump(mode="json"))
                and proposal.source.source_payload_sha256
                == fixture_proposal.source.source_payload_sha256
            ):
                return True
    except (OSError, TypeError, ValueError):
        return False
    return False


def _matches_bundled_fixture_payload(signal: RiskSignalRequest) -> bool:
    protected_bytes = _protected_source_bytes(
        signal.source.protected_source_locator
    )
    if protected_bytes is None:
        return False
    try:
        submitted_bytes = _canonical_json(
            _protected_signal_payload(signal.model_dump(mode="json"))
        ).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return submitted_bytes == protected_bytes and _sha256(protected_bytes) == (
        signal.source.source_payload_sha256
    )


_BUNDLED_DATASET_BINDING_FIELDS = (
    "dataset_id",
    "dataset_version_id",
    "source_kind",
    "intended_role",
    "canonical_schema_version",
    "adapter_id",
    "adapter_version",
    "source_schema_id",
    "source_schema_version",
    "mapping_manifest_id",
    "input_hashes",
    "semantic_payload_hashes",
    "output_hashes",
    "record_counts",
    "mapping_assumptions",
    "validation_summary",
    "license_and_attribution_ref",
    "data_classification",
    "raw_redistribution_policy",
    "derived_redistribution_policy",
    "provenance_summary",
    "generator_metadata",
    "mapping_manifest",
)


def _expected_bundled_dataset_version(
    *,
    first_published_by_run_id: str,
    first_published_at: str,
) -> dict[str, Any]:
    from .ingestion import _build_bundle

    return _build_bundle(
        ingestion_run_id=first_published_by_run_id,
        started_at=first_published_at,
    )["dataset_version"]


class ReactiveInvestigationMixin:
    """Workspace-owned reactive ingress on the single Core SQLite writer."""

    def _is_bundled_dataset_version(self, dataset_version_id: str) -> bool:
        from .ingestion import DatasetVersionUnavailable

        try:
            lineage = self.get_lineage(dataset_version_id)
        except DatasetVersionUnavailable:
            return False
        dataset = lineage.get("dataset_version")
        if not isinstance(dataset, Mapping):
            return False
        first_published_by_run_id = dataset.get("first_published_by_run_id")
        first_published_at = dataset.get("first_published_at")
        if not isinstance(first_published_by_run_id, str) or not isinstance(
            first_published_at, str
        ):
            return False
        try:
            expected = _expected_bundled_dataset_version(
                first_published_by_run_id=first_published_by_run_id,
                first_published_at=first_published_at,
            )
        except (OSError, TypeError, ValueError):
            return False
        return all(
            dataset.get(field_name) == expected.get(field_name)
            for field_name in _BUNDLED_DATASET_BINDING_FIELDS
        ) and dataset.get("dataset_version_id") == dataset_version_id

    def _matches_bundled_fixture(self, signal: RiskSignalRequest) -> bool:
        return self._is_bundled_dataset_version(
            signal.scored_dataset_version_ref
        ) and _matches_bundled_fixture_payload(signal)

    def list_risk_signal_fixtures(self, dataset_version_id: str) -> list[dict[str, Any]]:
        self.get_lineage(dataset_version_id)
        if not self._is_bundled_dataset_version(dataset_version_id):
            return []
        generated = _predictive_fixture_signal_payloads(dataset_version_id)
        return _fixture_preview_payloads(generated) + _fixture_payloads(dataset_version_id)

    def list_proactive_proposal_fixtures(
        self,
        dataset_version_id: str,
    ) -> list[dict[str, Any]]:
        self.get_lineage(dataset_version_id)
        if not self._is_bundled_dataset_version(dataset_version_id):
            return []
        return _proactive_proposal_preview_payloads(
            _proactive_proposal_payloads(dataset_version_id)
        )

    def predictive_risk_status(self) -> dict[str, Any]:
        return _predictive_risk_status()

    def get_risk_signal_fixture(
        self,
        dataset_version_id: str,
        fixture_id: str,
    ) -> RiskSignalRequest:
        if not self._is_bundled_dataset_version(dataset_version_id):
            raise RiskSignalFixtureUnavailable
        fixtures = [
            *_predictive_fixture_signal_payloads(dataset_version_id),
            *_fixture_signal_payloads(dataset_version_id),
        ]
        for fixture in fixtures:
            if fixture["fixture_id"] == fixture_id:
                return RiskSignalRequest.model_validate(fixture["signal"])
        raise RiskSignalFixtureUnavailable

    def get_proactive_proposal_fixture(
        self,
        dataset_version_id: str,
        fixture_id: str,
    ) -> ProactiveProposalRequest:
        if not self._is_bundled_dataset_version(dataset_version_id):
            raise ProactiveProposalFixtureUnavailable
        for fixture in _proactive_proposal_payloads(dataset_version_id):
            if fixture["fixture_id"] == fixture_id:
                return ProactiveProposalRequest.model_validate(fixture["proposal"])
        raise ProactiveProposalFixtureUnavailable

    def create_reactive_fixture_investigation(
        self,
        fixture_id: str,
        dataset_version_id: str,
        workspace_id: str,
        *,
        now: datetime | None = None,
    ) -> StoredReactiveIngress:
        signal = self.get_risk_signal_fixture(dataset_version_id, fixture_id)
        return self.create_reactive_investigation(signal, workspace_id, now=now)

    def create_proactive_fixture_investigation(
        self,
        fixture_id: str,
        dataset_version_id: str,
        workspace_id: str,
        *,
        now: datetime | None = None,
    ) -> StoredProactiveIngress:
        proposal = self.get_proactive_proposal_fixture(dataset_version_id, fixture_id)
        return self.create_proactive_investigation(proposal, workspace_id, now=now)

    def _persist_ingress_attempt_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        idempotency_key: str,
        content_hash: str,
        attempt: dict[str, Any],
        request: dict[str, Any] | None,
        attempt_id: str,
        audit_idempotency_key: str,
    ) -> dict[str, Any]:
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:reactive-audit:{workspace_id}:{audit_idempotency_key}",
        ).hex
        cursor = connection.execute(
            """
            INSERT INTO audit_events (
                workspace_id, occurrence_id, idempotency_key,
                occurrence_kind, outcome_code, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                occurrence_id,
                audit_idempotency_key,
                "REACTIVE_INGRESS",
                attempt["primary_code"],
                content_hash,
                attempt["received_at"],
            ),
        )
        if cursor.lastrowid is None:
            raise sqlite3.DatabaseError("reactive ingress audit event was not sequenced")
        attempt["attempt_id"] = attempt_id
        attempt["audit"] = {
            "occurrence_id": occurrence_id,
            "event_seq": int(cursor.lastrowid),
        }
        if request is not None:
            connection.execute(
                """
                INSERT INTO investigation_requests (
                    investigation_request_id, workspace_id, attempt_id,
                    content_hash, accepted_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request["investigation_request_id"],
                    workspace_id,
                    attempt_id,
                    request["content_hash"],
                    request["accepted_at"],
                    _canonical_json(request),
                ),
            )
        connection.execute(
            """
            INSERT INTO reactive_ingress_attempts (
                attempt_id, workspace_id, idempotency_key,
                source_system, source_signal_id, source_revision,
                source_payload_sha256, content_hash, status, primary_code,
                investigation_request_id, occurrence_id, event_seq,
                received_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                workspace_id,
                idempotency_key,
                attempt["source_system"],
                attempt["source_signal_id"],
                attempt["source_revision"],
                attempt["source_payload_sha256"],
                content_hash,
                attempt["status"],
                attempt["primary_code"],
                attempt["investigation_request_id"],
                occurrence_id,
                int(cursor.lastrowid),
                attempt["received_at"],
                _canonical_json(attempt),
            ),
        )
        return attempt

    def _persist_proactive_ingress_attempt_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        idempotency_key: str,
        content_hash: str,
        attempt: dict[str, Any],
        request: dict[str, Any] | None,
        attempt_id: str,
        audit_idempotency_key: str,
    ) -> dict[str, Any]:
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:proactive-audit:{workspace_id}:{audit_idempotency_key}",
        ).hex
        cursor = connection.execute(
            """
            INSERT INTO audit_events (
                workspace_id, occurrence_id, idempotency_key,
                occurrence_kind, outcome_code, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                occurrence_id,
                audit_idempotency_key,
                "PROACTIVE_INGRESS",
                attempt["primary_code"],
                content_hash,
                attempt["received_at"],
            ),
        )
        if cursor.lastrowid is None:
            raise sqlite3.DatabaseError("proactive ingress audit event was not sequenced")
        attempt["attempt_id"] = attempt_id
        attempt["audit"] = {
            "occurrence_id": occurrence_id,
            "event_seq": int(cursor.lastrowid),
        }
        if request is not None:
            connection.execute(
                """
                INSERT INTO investigation_requests (
                    investigation_request_id, workspace_id, attempt_id,
                    content_hash, accepted_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request["investigation_request_id"],
                    workspace_id,
                    attempt_id,
                    request["content_hash"],
                    request["accepted_at"],
                    _canonical_json(request),
                ),
            )
        connection.execute(
            """
            INSERT INTO proactive_ingress_attempts (
                attempt_id, workspace_id, idempotency_key,
                source_system, proposal_id, proposal_revision,
                source_payload_sha256, content_hash, status, primary_code,
                investigation_request_id, occurrence_id, event_seq,
                received_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                workspace_id,
                idempotency_key,
                attempt["source_system"],
                attempt["proposal_id"],
                attempt["proposal_revision"],
                attempt["source_payload_sha256"],
                content_hash,
                attempt["status"],
                attempt["primary_code"],
                attempt["investigation_request_id"],
                occurrence_id,
                int(cursor.lastrowid),
                attempt["received_at"],
                _canonical_json(attempt),
            ),
        )
        return attempt

    def record_proactive_schema_failure(
        self,
        workspace_id: str,
        *,
        request_body: bytes,
        now: datetime | None = None,
    ) -> None:
        received_at = now or datetime.now(timezone.utc)
        content_hash = _sha256(request_body)
        attempt_id = "attempt_" + uuid4().hex
        idempotency_key = _sha256(
            {
                "schema_failure": content_hash,
                "attempt_id": attempt_id,
            }
        )
        attempt = {
            "attempt_id": "attempt_pending",
            "status": "rejected",
            "scope": "proactive_ingress",
            "source_system": "unavailable",
            "proposal_id": "unavailable",
            "proposal_revision": "unavailable",
            "source_payload_sha256": content_hash,
            "primary_code": "PROACTIVE_SCHEMA_UNSUPPORTED",
            "findings": [
                _clean_finding(
                    _finding(
                        code="PROACTIVE_SCHEMA_UNSUPPORTED",
                        severity="error",
                        disposition="reject",
                        affected_refs=[],
                        message="The proactive proposal body did not match the supported schema.",
                        remediation="Use the versioned bundled Proactive Proposal contract.",
                        phase=1,
                    )
                )
            ],
            "evidence_refs": [],
            "retryable": False,
            "recovery_action": _RECOVERY_ACTIONS["PROACTIVE_SCHEMA_UNSUPPORTED"],
            "received_at": _timestamp(received_at),
            "investigation_request_id": None,
            "investigation_request": None,
            "audit": {"occurrence_id": "pending", "event_seq": 0},
        }
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=f"proactive-schema:{idempotency_key}",
                    mutation_kind="PROACTIVE_INGRESS",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=received_at,
                )
                if mutation.replayed:
                    connection.commit()
                    return
                self._persist_proactive_ingress_attempt_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    content_hash=content_hash,
                    attempt=attempt,
                    request=None,
                    attempt_id=attempt_id,
                    audit_idempotency_key=f"proactive-schema:{idempotency_key}",
                )
                connection.commit()
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def record_reactive_schema_failure(
        self,
        workspace_id: str,
        *,
        request_body: bytes,
        now: datetime | None = None,
    ) -> None:
        received_at = now or datetime.now(timezone.utc)
        content_hash = _sha256(request_body)
        attempt_id = "attempt_" + uuid4().hex
        idempotency_key = _sha256(
            {
                "schema_failure": content_hash,
                "attempt_id": attempt_id,
            }
        )
        attempt = {
            "attempt_id": "attempt_pending",
            "status": "rejected",
            "scope": "reactive_ingress",
            "source_system": "unavailable",
            "source_signal_id": "unavailable",
            "source_revision": "unavailable",
            "source_payload_sha256": content_hash,
            "primary_code": "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
            "findings": [
                _clean_finding(
                    _finding(
                        code="RISK_SIGNAL_SCHEMA_UNSUPPORTED",
                        severity="error",
                        disposition="reject",
                        affected_refs=[],
                        message="The reactive Risk Signal body did not match the supported schema.",
                        remediation="Use the versioned bundled Risk Signal contract.",
                        phase=1,
                    )
                )
            ],
            "evidence_refs": [],
            "retryable": False,
            "recovery_action": _RECOVERY_ACTIONS["RISK_SIGNAL_SCHEMA_UNSUPPORTED"],
            "received_at": _timestamp(received_at),
            "investigation_request_id": None,
            "investigation_request": None,
            "audit": {"occurrence_id": "pending", "event_seq": 0},
        }
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=f"reactive-schema:{idempotency_key}",
                    mutation_kind="REACTIVE_INGRESS",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=received_at,
                )
                if mutation.replayed:
                    connection.commit()
                    return
                self._persist_ingress_attempt_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    content_hash=content_hash,
                    attempt=attempt,
                    request=None,
                    attempt_id=attempt_id,
                    audit_idempotency_key=f"reactive-schema:{idempotency_key}",
                )
                connection.commit()
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def create_reactive_investigation(
        self,
        signal: RiskSignalRequest,
        workspace_id: str,
        *,
        now: datetime | None = None,
    ) -> StoredReactiveIngress:
        received_at = now or datetime.now(timezone.utc)
        signal_payload = signal.model_dump(mode="json")
        source = signal.source
        source_payload_hash = source.source_payload_sha256
        content_hash = _safe_sha256(signal_payload)
        idempotency_key = _sha256(
            {
                "source_system": source.source_system,
                "source_signal_id": signal.source_signal_id,
                "source_revision": signal.source_revision,
                "source_payload_sha256": source_payload_hash,
                "scored_dataset_version_ref": signal.scored_dataset_version_ref,
                "target_milestone_kind": signal.target_milestone_kind,
                "trigger_mode": signal.trigger_mode,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "content_hash": content_hash,
            }
        )

        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT payload_json, attempt_id
                    FROM reactive_ingress_attempts
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    replay = json.loads(str(existing["payload_json"]))
                    duplicate_attempt_id = "attempt_" + uuid4().hex
                    replay["status"] = "duplicate"
                    replay["received_at"] = _timestamp(received_at)
                    replay["audit"] = {"occurrence_id": "pending", "event_seq": 0}
                    duplicate_mutation = self._record_mutation_locked(
                        workspace_id,
                        idempotency_key=f"reactive-duplicate:{duplicate_attempt_id}",
                        mutation_kind="REACTIVE_INGRESS",
                        content_hash=content_hash,
                        terminal_fresh_bundle=False,
                        now=received_at,
                    )
                    if duplicate_mutation.replayed:
                        raise sqlite3.DatabaseError(
                            "reactive duplicate mutation was unexpectedly replayed"
                        )
                    self._persist_ingress_attempt_locked(
                        connection,
                        workspace_id=workspace_id,
                        idempotency_key=idempotency_key,
                        content_hash=content_hash,
                        attempt=replay,
                        request=None,
                        attempt_id=duplicate_attempt_id,
                        audit_idempotency_key=(
                            f"reactive-duplicate:{duplicate_attempt_id}"
                        ),
                    )
                    connection.commit()
                    return StoredReactiveIngress("IDEMPOTENT_REPLAY", replay)

                revision_conflict = connection.execute(
                    """
                    SELECT 1
                    FROM reactive_ingress_attempts
                    WHERE workspace_id = ?
                      AND source_system = ?
                      AND source_signal_id = ?
                      AND source_revision = ?
                      AND source_payload_sha256 != ?
                    LIMIT 1
                    """,
                    (
                        workspace_id,
                        source.source_system,
                        signal.source_signal_id,
                        signal.source_revision,
                        source_payload_hash,
                    ),
                ).fetchone() is not None

                attempt, request = self._normalise_reactive_signal(
                    signal,
                    received_at=received_at,
                    revision_conflict=revision_conflict,
                    workspace_id=workspace_id,
                )
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="REACTIVE_INGRESS",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=received_at,
                )
                if mutation.replayed:
                    raise sqlite3.DatabaseError("reactive ingress mutation was unexpectedly replayed")

                attempt_id = "attempt_" + uuid5(
                    NAMESPACE_URL,
                    f"causal-delay-copilot:reactive-attempt:{workspace_id}:{idempotency_key}",
                ).hex
                self._persist_ingress_attempt_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    content_hash=content_hash,
                    attempt=attempt,
                    request=request,
                    attempt_id=attempt_id,
                    audit_idempotency_key=f"reactive:{idempotency_key}",
                )
                connection.commit()
                return StoredReactiveIngress("CREATED", attempt)
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def create_proactive_investigation(
        self,
        proposal: ProactiveProposalRequest,
        workspace_id: str,
        *,
        now: datetime | None = None,
    ) -> StoredProactiveIngress:
        received_at = now or datetime.now(timezone.utc)
        proposal_payload = proposal.model_dump(mode="json")
        source = proposal.source
        source_payload_hash = source.source_payload_sha256
        content_hash = _safe_sha256(proposal_payload)
        idempotency_key = _sha256(
            {
                "source_system": source.source_system,
                "proposal_id": proposal.proposal_id,
                "proposal_revision": proposal.proposal_revision,
                "source_payload_sha256": source_payload_hash,
                "dataset_version_id": proposal.dataset_version_id,
                "trigger_mode": proposal.trigger_mode,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "content_hash": content_hash,
            }
        )

        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT payload_json
                    FROM proactive_ingress_attempts
                    WHERE workspace_id = ? AND idempotency_key = ?
                    """,
                    (workspace_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    replay = json.loads(str(existing["payload_json"]))
                    duplicate_attempt_id = "attempt_" + uuid4().hex
                    replay["status"] = "duplicate"
                    replay["received_at"] = _timestamp(received_at)
                    replay["audit"] = {"occurrence_id": "pending", "event_seq": 0}
                    duplicate_mutation = self._record_mutation_locked(
                        workspace_id,
                        idempotency_key=f"proactive-duplicate:{duplicate_attempt_id}",
                        mutation_kind="PROACTIVE_INGRESS",
                        content_hash=content_hash,
                        terminal_fresh_bundle=False,
                        now=received_at,
                    )
                    if duplicate_mutation.replayed:
                        raise sqlite3.DatabaseError(
                            "proactive duplicate mutation was unexpectedly replayed"
                        )
                    self._persist_proactive_ingress_attempt_locked(
                        connection,
                        workspace_id=workspace_id,
                        idempotency_key=idempotency_key,
                        content_hash=content_hash,
                        attempt=replay,
                        request=None,
                        attempt_id=duplicate_attempt_id,
                        audit_idempotency_key=f"proactive-duplicate:{duplicate_attempt_id}",
                    )
                    connection.commit()
                    return StoredProactiveIngress("IDEMPOTENT_REPLAY", replay)

                revision_conflict = connection.execute(
                    """
                    SELECT 1
                    FROM proactive_ingress_attempts
                    WHERE workspace_id = ?
                      AND source_system = ?
                      AND proposal_id = ?
                      AND proposal_revision = ?
                      AND source_payload_sha256 != ?
                    LIMIT 1
                    """,
                    (
                        workspace_id,
                        source.source_system,
                        proposal.proposal_id,
                        proposal.proposal_revision,
                        source_payload_hash,
                    ),
                ).fetchone() is not None

                attempt, request = self._normalise_proactive_proposal(
                    proposal,
                    received_at=received_at,
                    revision_conflict=revision_conflict,
                    workspace_id=workspace_id,
                )
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="PROACTIVE_INGRESS",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=received_at,
                )
                if mutation.replayed:
                    raise sqlite3.DatabaseError(
                        "proactive ingress mutation was unexpectedly replayed"
                    )

                attempt_id = "attempt_" + uuid5(
                    NAMESPACE_URL,
                    f"causal-delay-copilot:proactive-attempt:{workspace_id}:{idempotency_key}",
                ).hex
                self._persist_proactive_ingress_attempt_locked(
                    connection,
                    workspace_id=workspace_id,
                    idempotency_key=idempotency_key,
                    content_hash=content_hash,
                    attempt=attempt,
                    request=request,
                    attempt_id=attempt_id,
                    audit_idempotency_key=f"proactive:{idempotency_key}",
                )
                connection.commit()
                return StoredProactiveIngress("CREATED", attempt)
            except sqlite3.Error as error:
                connection.rollback()
                raise AuditStoreUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def _normalise_reactive_signal(
        self,
        signal: RiskSignalRequest,
        *,
        received_at: datetime,
        revision_conflict: bool,
        workspace_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        source = signal.source
        findings: list[dict[str, Any]] = []
        schema_invalid = False
        integrity_invalid = False

        if signal.schema_version != RISK_SIGNAL_SCHEMA_VERSION or (
            source.schema_version != TRIGGER_SOURCE_SCHEMA_VERSION
        ):
            schema_invalid = True
            findings.append(
                _finding(
                    code="RISK_SIGNAL_SCHEMA_UNSUPPORTED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The reactive Risk Signal schema is not supported by this Core release.",
                    remediation="Use the versioned bundled Risk Signal contract.",
                    phase=1,
                )
            )
        if signal.trigger_mode != "reactive":
            findings.append(
                _finding(
                    code="RISK_SIGNAL_MODE_MISMATCH",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The reactive intake accepts only reactive trigger mode.",
                    remediation="Submit a reactive Risk Signal to this intake route.",
                    phase=1,
                )
            )

        if (
            not _SHA256_PATTERN.fullmatch(source.source_payload_sha256)
            or not source.protected_source_locator.startswith("bundled://risk-signal/")
            or source.source_system != SOURCE_SYSTEM
            or not self._matches_bundled_fixture(signal)
        ):
            integrity_invalid = True
            findings.append(
                _finding(
                    code="RISK_SIGNAL_INTEGRITY_FAILED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The protected Risk Signal envelope failed its integrity check.",
                    remediation="Use an unmodified bundled signal and retry.",
                    phase=2,
                )
            )

        if revision_conflict:
            findings.append(
                _finding(
                    code="RISK_SIGNAL_REVISION_CONFLICT",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The source signal identity and revision already carry different protected content.",
                    remediation="Submit a new immutable source revision.",
                    phase=3,
                )
            )

        generated = _normalise_temporal(signal.generated_at.model_dump(mode="json"))
        known = _normalise_temporal(signal.known_at.model_dump(mode="json"))
        received_temporal = _Temporal(
            _field(
                "present",
                {
                    "kind": "instant",
                    "source_value": _timestamp(received_at),
                    "normalized_value": _timestamp(received_at),
                    "precision": "microsecond",
                    "timezone_status": "known",
                    "source_timezone": _field("present", "UTC"),
                },
            ),
            received_at.astimezone(timezone.utc),
        )
        if (
            _compare(generated, known) is None
            or _compare(generated, known) == 1
            or _compare(known, received_temporal) is None
            or _compare(known, received_temporal) == 1
        ):
            findings.append(
                _finding(
                    code="RISK_SIGNAL_CLOCK_UNUSABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="Generated, known, and receipt clocks cannot establish the required order.",
                    remediation="Provide comparable generated and known clocks; receipt time is adapter-assigned.",
                    phase=4,
                )
            )

        target_valid = (
            signal.target_definition_id == TARGET_DEFINITION_ID
            and signal.target_milestone_kind == CONFIGURED_TARGET_MILESTONE_KIND
            and signal.score_semantic == SCORE_SEMANTIC
        )
        if not target_valid:
            findings.append(
                _finding(
                    code="RISK_SIGNAL_TARGET_MISMATCH",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The Risk Signal target does not match the configured supplier milestone question.",
                    remediation="Use the configured supplier milestone target.",
                    phase=6,
                )
            )

        score_valid = (
            math.isfinite(signal.score_value)
            and math.isfinite(signal.alert_threshold)
            and 0 <= signal.score_value <= 1
            and 0 <= signal.alert_threshold <= 1
            and signal.flagged is (signal.score_value >= signal.alert_threshold)
        )
        if not score_valid:
            findings.append(
                _finding(
                    code="RISK_SIGNAL_SCORE_UNUSABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The prediction score, threshold, or flagged state is inconsistent.",
                    remediation="Repair the finite score, threshold, and threshold comparison.",
                    phase=7,
                )
            )

        for field, code, label in (
            (
                signal.predictor_artifact_ref,
                "PREDICTOR_ARTIFACT_UNAVAILABLE",
                "predictor artifact",
            ),
            (
                signal.predictive_attribution_ref,
                "PREDICTIVE_ATTRIBUTION_UNAVAILABLE",
                "predictive attribution",
            ),
        ):
            if field.state != "present" or not isinstance(field.value, str) or not field.value:
                findings.append(
                    _finding(
                        code=code,
                        severity="warning",
                        disposition="advisory",
                        affected_refs=[],
                        message=f"The {label} reference is unavailable; prediction comparison is suppressed.",
                        remediation="Continue with the reactive investigation without predictive comparison metadata.",
                        phase=9,
                    )
                )

        lineage: dict[str, Any] | None = None
        order_line: dict[str, Any] | None = None
        canonical_order_line_id: str | None = None
        dataset_id = ""
        commitment_event: dict[str, Any] | None = None
        original_promise: _Temporal | None = None
        events: list[Mapping[str, Any]] = []
        event_ids: list[str] = []
        lineage_refs: list[str] = []
        mapping_refs: list[str] = []
        evidence_refs: list[str] = []
        subject_rejected = False
        selected_ids: list[str] = []
        load_snapshot_error: str | None = None
        load_exposure: dict[str, Any] | None = None
        duration_basis: str | None = None
        duration_basis_evidence: dict[str, Any] = {
            "counts": {},
            "identity_hashes": {},
        }
        if not schema_invalid and not integrity_invalid and not revision_conflict:
            from .ingestion import DatasetVersionUnavailable

            try:
                lineage = self.get_lineage(signal.scored_dataset_version_ref)
            except DatasetVersionUnavailable:
                findings.append(
                    _finding(
                        code="RISK_SIGNAL_SUBJECT_UNRESOLVED",
                        severity="error",
                        disposition="reject",
                        affected_refs=[],
                        message="The scored Dataset Version is not a published Core version.",
                        remediation="Select one published Dataset Version and retry.",
                        phase=5,
                    )
                )
                subject_rejected = True

            if lineage is not None:
                dataset_id = str(lineage.get("dataset_version", {}).get("dataset_id", ""))
                mapping_manifest = lineage.get("mapping_manifest", {})
                mapping_refs = _lineage_mapping_refs(
                    lineage,
                    include_advisory=signal.advisory_context is not None,
                )
                source_ref = signal.source_order_line_ref
                candidates = _source_key(source_ref.key)
                source_reference = f"source-order-line:{source_ref.namespace}:{','.join(candidates)}"
                if source_ref.namespace != SOURCE_NAMESPACE or not candidates:
                    findings.append(
                        _finding(
                            code="RISK_SIGNAL_SUBJECT_UNRESOLVED",
                            severity="error",
                            disposition="reject",
                            affected_refs=[source_reference],
                            message="The source Order Line reference has no reviewed mapping in this Dataset Version.",
                            remediation="Use one reviewed source Order Line reference.",
                            phase=5,
                        )
                    )
                    subject_rejected = True
                elif len(candidates) != 1:
                    findings.append(
                        _finding(
                            code="RISK_SIGNAL_SUBJECT_AMBIGUOUS",
                            severity="error",
                            disposition="reject",
                            affected_refs=[source_reference],
                            message="The source Order Line reference resolves to more than one candidate.",
                            remediation="Select one exact source Order Line identity.",
                            phase=5,
                        )
                    )
                    subject_rejected = True
                else:
                    canonical_order_line_id = _canonical_identity_from_mapping(
                        dataset_id,
                        mapping_manifest,
                        "order_line_id",
                        candidates[0],
                    )
                    if canonical_order_line_id is None:
                        findings.append(
                            _finding(
                                code="RISK_SIGNAL_SUBJECT_UNRESOLVED",
                                severity="error",
                                disposition="reject",
                                affected_refs=[source_reference, *mapping_refs],
                                message="The frozen Dataset Version has no executable Order Line identity mapping.",
                                remediation="Restore the reviewed identity mapping and retry.",
                                phase=5,
                            )
                        )
                        subject_rejected = True
                        canonical_order_line_id = source_reference
                    if canonical_order_line_id is None:
                        matches = []
                    else:
                        matches = [
                            item
                            for item in lineage.get("order_lines", [])
                            if isinstance(item, Mapping)
                            and item.get("order_line_id") == canonical_order_line_id
                        ]
                    if len(matches) == 0:
                        findings.append(
                            _finding(
                                code="RISK_SIGNAL_SUBJECT_UNRESOLVED",
                                severity="error",
                                disposition="reject",
                                affected_refs=[source_reference],
                                message="The source Order Line does not resolve in the frozen Dataset Version.",
                                remediation="Select one source Order Line present in the frozen Dataset Version.",
                                phase=5,
                            )
                        )
                        subject_rejected = True
                    elif len(matches) > 1:
                        findings.append(
                            _finding(
                                code="RISK_SIGNAL_SUBJECT_AMBIGUOUS",
                                severity="error",
                                disposition="reject",
                                affected_refs=[source_reference],
                                message="The source Order Line resolves to multiple canonical records.",
                                remediation="Select a source reference with one canonical resolution.",
                                phase=5,
                            )
                        )
                        subject_rejected = True
                    else:
                        order_line = matches[0]
                        events = [
                            item
                            for item in lineage.get("order_line_events", [])
                            if isinstance(item, Mapping)
                            and item.get("order_line_id") == canonical_order_line_id
                        ]
                        commitment_events = [
                            item for item in events if item.get("kind") == "committed"
                        ]
                        commitment_event, commitment_error = _resolve_commitment_event(
                            commitment_events,
                            known_cutoff=generated,
                        )
                        if commitment_event is None or commitment_error is not None:
                            findings.append(
                                _finding(
                                    code=commitment_error or "COMMITMENT_CUTOFF_UNUSABLE",
                                    severity="error",
                                    disposition="reject",
                                    affected_refs=[canonical_order_line_id],
                                    message="The canonical commitment cutoff is absent, ambiguous, or temporally invalid.",
                                    remediation="Repair the canonical commitment history and clocks before retrying.",
                                    phase=5,
                                )
                            )
                            subject_rejected = True
                        else:
                            event_ids = [str(item.get("event_id")) for item in events]
                            commitment_occurrence = _temporal_from_record(
                                commitment_event.get("clocks", {}).get("occurred_at")
                            )
                            commitment_known = _temporal_from_record(
                                commitment_event.get("clocks", {}).get("known_at")
                            )
                            if (
                                _compare(commitment_known, generated) is None
                                or _compare(commitment_known, generated) == 1
                            ):
                                findings.append(
                                    _finding(
                                        code="COMMITMENT_CUTOFF_UNUSABLE",
                                        severity="error",
                                        disposition="reject",
                                        affected_refs=[canonical_order_line_id],
                                        message="The canonical commitment was not known by the signal scoring clock.",
                                        remediation="Use a signal with a point-in-time canonical subject snapshot.",
                                        phase=5,
                                    )
                                )
                                subject_rejected = True
                            elif (
                                _compare(commitment_occurrence, generated) is None
                                or _compare(commitment_occurrence, generated) == 1
                            ):
                                findings.append(
                                    _finding(
                                        code="RISK_SIGNAL_SUBJECT_NOT_OPEN",
                                        severity="error",
                                        disposition="reject",
                                        affected_refs=[canonical_order_line_id],
                                        message="The canonical Order Line was not open at the signal scoring clock.",
                                        remediation="Use a signal generated while the Order Line was open.",
                                        phase=5,
                                    )
                                )
                                subject_rejected = True
                            else:
                                supplier = _subject_field_as_of(
                                    lineage,
                                    order_line_id=canonical_order_line_id,
                                    field_path="supplier_id",
                                    canonical_value={
                                        "state": "present",
                                        "value": order_line.get("supplier_id"),
                                    },
                                    cutoff=commitment_occurrence,
                                )
                                if supplier.get("state") != "present":
                                    findings.append(
                                        _finding(
                                            code="RISK_SIGNAL_SUBJECT_UNRESOLVED",
                                            severity="error",
                                            disposition="reject",
                                            affected_refs=[canonical_order_line_id],
                                            message="The canonical supplier identity was not known at the commitment cutoff.",
                                            remediation="Use a Dataset Version with a point-in-time supplier mapping.",
                                            phase=5,
                                        )
                                    )
                                    subject_rejected = True
                                for event in events:
                                    if subject_rejected:
                                        break
                                    if event.get("kind") not in {"milestone_reached", "cancelled"}:
                                        continue
                                    if event.get("kind") == "milestone_reached":
                                        milestone = _field_from_record(event.get("milestone_kind"))
                                        if milestone.get("value") != signal.target_milestone_kind:
                                            continue
                                    occurred = _temporal_from_record(
                                        event.get("clocks", {}).get("occurred_at")
                                    )
                                    known_at = _temporal_from_record(
                                        event.get("clocks", {}).get("known_at")
                                    )
                                    known_order = _compare(known_at, generated)
                                    if known_order is None:
                                        findings.append(
                                            _finding(
                                                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                                                severity="error",
                                                disposition="reject",
                                                affected_refs=[canonical_order_line_id],
                                                message="A closure event has no comparable point-in-time knowledge clock.",
                                                remediation="Repair the canonical closure clocks before retrying.",
                                                phase=5,
                                            )
                                        )
                                        subject_rejected = True
                                        break
                                    if known_order == 1:
                                        continue
                                    occurred_order = _compare(occurred, generated)
                                    if occurred_order is None:
                                        findings.append(
                                            _finding(
                                                code="LOAD_SNAPSHOT_UNRESOLVABLE",
                                                severity="error",
                                                disposition="reject",
                                                affected_refs=[canonical_order_line_id],
                                                message="A closure event has no comparable occurrence clock at the scoring cutoff.",
                                                remediation="Repair the canonical closure clocks before retrying.",
                                                phase=5,
                                            )
                                        )
                                        subject_rejected = True
                                        break
                                    if occurred_order <= 0:
                                        findings.append(
                                            _finding(
                                                code="RISK_SIGNAL_SUBJECT_NOT_OPEN",
                                                severity="error",
                                                disposition="reject",
                                                affected_refs=[canonical_order_line_id],
                                                message="The canonical Order Line was already closed at the signal scoring clock.",
                                                remediation="Use a signal generated while the Order Line was open.",
                                                phase=5,
                                            )
                                        )
                                        subject_rejected = True
                                        break
                                if signal.target_milestone_kind == CONFIGURED_TARGET_MILESTONE_KIND:
                                    promise_resolution = _resolve_frozen_promise(
                                        events,
                                        target_milestone_kind=signal.target_milestone_kind,
                                        commitment_cutoff=commitment_occurrence,
                                    )
                                    original_promise = promise_resolution.value
                                    if promise_resolution.code is not None:
                                        findings.append(
                                            _finding(
                                                code=promise_resolution.code,
                                                severity="error",
                                                disposition="reject",
                                                affected_refs=[canonical_order_line_id],
                                                message="The canonical original promise cannot be frozen at the commitment cutoff.",
                                                remediation="Repair the canonical promise chain and clocks before retrying.",
                                                phase=5,
                                            )
                                        )
                                        subject_rejected = True

        if (
            lineage is not None
            and canonical_order_line_id is not None
            and commitment_event is not None
            and event_ids
        ):
            commitment_cutoff_for_refs = _temporal_from_record(
                commitment_event.get("clocks", {}).get("occurred_at")
            )
            lineage_refs = _lineage_observation_refs(
                lineage,
                canonical_order_line_id,
                event_ids,
                known_at=commitment_cutoff_for_refs,
            )
            evidence_refs = _lineage_evidence_refs(lineage, lineage_refs)

        configuration = ENGINE_CONFIGURATION_REGISTRY.get(ENGINE_CONFIGURATION_REF)
        if lineage is not None and configuration is not None:
            duration_basis_evidence = _duration_basis_at_cutoff(
                configuration,
                dataset_version_id=signal.scored_dataset_version_ref,
            )
            duration_basis = duration_basis_evidence["basis"]

        if (
            lineage is not None
            and order_line is not None
            and canonical_order_line_id is not None
            and commitment_event is not None
            and not subject_rejected
        ):
            commitment_cutoff = _temporal_from_record(
                commitment_event.get("clocks", {}).get("occurred_at")
            )
            selected_ids, load_snapshot_error = _selected_order_line_ids(
                lineage,
                subject_id=canonical_order_line_id,
                subject_supplier_id=str(order_line.get("supplier_id", "")),
                decision_cutoff=commitment_cutoff,
                target_milestone_kind=signal.target_milestone_kind,
            )
            if load_snapshot_error is not None:
                findings.append(
                    _finding(
                        code=load_snapshot_error,
                        severity="error",
                        disposition="reject",
                        affected_refs=[canonical_order_line_id],
                        message="The point-in-time supplier load snapshot contains an unresolved membership fact.",
                        remediation="Repair the canonical clocks and field-level lineage before retrying.",
                        phase=9,
                    )
                )
                subject_rejected = True
            elif duration_basis is not None:
                load_exposure = derive_supplier_load_exposure(
                    lineage,
                    subject_id=canonical_order_line_id,
                    subject_supplier_id=str(order_line.get("supplier_id", "")),
                    decision_cutoff=commitment_cutoff,
                    target_milestone_kind=signal.target_milestone_kind,
                    duration_basis=duration_basis,
                    trigger_mode="reactive",
                )
                exposure_codes = load_exposure.get("eligibility_codes", [])
                blocking_exposure_codes = {
                    str(code)
                    for code in exposure_codes
                    if isinstance(code, str)
                }.intersection(
                    {"LOAD_SNAPSHOT_UNRESOLVABLE", "COMMITMENT_CUTOFF_UNUSABLE"}
                )
                if blocking_exposure_codes:
                    code = sorted(blocking_exposure_codes)[0]
                    findings.append(
                        _finding(
                            code=code,
                            severity="error",
                            disposition="reject",
                            affected_refs=[canonical_order_line_id],
                            message="The point-in-time supplier load derivation contains an unresolved membership fact.",
                            remediation="Repair the canonical clocks and field-level lineage before retrying.",
                            phase=9,
                        )
                    )
                    subject_rejected = True

        if (
            lineage is not None
            and order_line is not None
            and canonical_order_line_id is not None
            and not subject_rejected
        ):
            self._validate_advisory_context(
                signal,
                dataset_id=dataset_id,
                order_line=order_line,
                mapping_manifest=lineage.get("mapping_manifest", {}),
                events=events,
                generated=generated,
                known=known,
                findings=findings,
            )

        if CAUSAL_QUESTION_VERSION not in CAUSAL_QUESTION_REGISTRY:
            findings.append(
                _finding(
                    code="CAUSAL_QUESTION_VERSION_UNAVAILABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The fixed causal question version is unavailable in this Core release.",
                    remediation="Restore the versioned Core causal-question configuration.",
                    phase=9,
                )
            )
        if ENGINE_CONFIGURATION_REF not in ENGINE_CONFIGURATION_REGISTRY:
            findings.append(
                _finding(
                    code="ENGINE_CONFIGURATION_UNAVAILABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The fixed causal engine configuration is unavailable in this Core release.",
                    remediation="Restore the versioned Core engine configuration.",
                    phase=9,
                )
            )
        if lineage is not None and configuration is not None and duration_basis is None:
            findings.append(
                _finding(
                    code="SLIPPAGE_DURATION_BASIS_MIXED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[
                        f"{basis}:{duration_basis_evidence['counts'][basis]}:{duration_basis_evidence['identity_hashes'][basis]}"
                        for basis in sorted(duration_basis_evidence["counts"])
                    ],
                    message="Released target rows do not share one canonical slippage duration basis.",
                    remediation="Wait for a released Dataset Version with one duration basis before creating an engine request.",
                    phase=9,
                )
            )

        findings.sort(key=lambda finding: (finding["_phase"], finding["_code_order"]))
        rejecting = [finding for finding in findings if _is_rejection(finding)]
        cleaned_findings = [_clean_finding(finding) for finding in findings]
        primary_code = (
            _clean_finding(rejecting[0])["code"]
            if rejecting
            else "RISK_SIGNAL_ACCEPTED"
        )
        status = (
            "rejected"
            if rejecting
            else "accepted_with_warning"
            if findings
            else "accepted"
        )
        request: dict[str, Any] | None = None
        if (
            not rejecting
            and lineage is not None
            and order_line is not None
            and commitment_event is not None
            and canonical_order_line_id is not None
            and duration_basis is not None
        ):
            commitment_cutoff = _temporal_from_record(
                commitment_event.get("clocks", {}).get("occurred_at")
            )
            commitment_known = _temporal_from_record(
                commitment_event.get("clocks", {}).get("known_at")
            )
            target_field = _field("present", signal.target_milestone_kind)
            event_ids = event_ids or []
            lineage_refs = _lineage_observation_refs(
                lineage,
                canonical_order_line_id,
                event_ids,
                known_at=commitment_cutoff,
            )
            mapping_refs = _lineage_mapping_refs(
                lineage,
                include_advisory=signal.advisory_context is not None,
            )
            evidence_refs = _lineage_evidence_refs(lineage, lineage_refs)
            configuration = ENGINE_CONFIGURATION_REGISTRY[ENGINE_CONFIGURATION_REF]
            adjustment_fields = {
                name: _subject_field_as_of(
                    lineage,
                    order_line_id=canonical_order_line_id,
                    field_path=f"fields.{name}",
                    canonical_value=order_line.get("fields", {}).get(name),
                    cutoff=commitment_cutoff,
                )
                for name in (
                    "material_class",
                    "complexity_class",
                    "quantity",
                    "value",
                    "project_id",
                    "project_phase",
                    "urgency_class",
                    "geography_code",
                    "contract_form",
                )
            }
            projection = {
                "causal_input_schema_version": CAUSAL_INPUT_SCHEMA_VERSION,
                "dataset_version_id": signal.scored_dataset_version_ref,
                "subject_analytical_values": {
                    "supplier_id": _subject_field_as_of(
                        lineage,
                        order_line_id=canonical_order_line_id,
                        field_path="supplier_id",
                        canonical_value={
                            "state": "present",
                            "value": order_line.get("supplier_id"),
                        },
                        cutoff=commitment_cutoff,
                    ),
                    "original_promise": original_promise.field
                    if original_promise is not None
                    else _field("unresolved"),
                    "adjustment_inputs": adjustment_fields,
                    "subject_exclusion_identity": canonical_order_line_id,
                },
                "decision_cutoff": commitment_cutoff.field,
                "observation_cutoff": known.field,
                "target_milestone_kind": target_field,
                "canonical_slippage_duration_basis": duration_basis,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "supplier_load_exposure": load_exposure,
                "estimator_window_ref": _window_ref(
                    selector_version=configuration[
                        "estimator_window_selector_version"
                    ],
                    selected_ids=selected_ids,
                    observation_cutoff=known,
                    subject_id=canonical_order_line_id,
                    remove_subject=True,
                ),
                "history_lookback_ref": _window_ref(
                    selector_version=configuration[
                        "history_lookback_selector_version"
                    ],
                    selected_ids=selected_ids,
                    observation_cutoff=known,
                    subject_id=canonical_order_line_id,
                    remove_subject=False,
                ),
                "historical_population_digest": _historical_population_digest(
                    lineage,
                    [
                        item
                        for item in selected_ids
                        if item != canonical_order_line_id
                    ],
                    decision_cutoff=commitment_cutoff,
                ),
                "analytical_fact_lineage_refs": sorted(
                    {*lineage_refs, *mapping_refs, *evidence_refs}
                ),
            }
            causal_input_digest = _sha256(projection)
            source_ref = signal.source_order_line_ref.model_dump(mode="json")
            prediction_metadata = _field(
                "present",
                {
                    "predictor_id": signal.predictor_id,
                    "predictor_version": signal.predictor_version,
                    "feature_contract_version": signal.feature_contract_version,
                    "target_definition_id": signal.target_definition_id,
                    "score_semantic": signal.score_semantic,
                    "score_value": signal.score_value,
                    "alert_threshold": signal.alert_threshold,
                    "flagged": signal.flagged,
                    "generated_at": generated.field,
                    "known_at": known.field,
                    "predictor_artifact_ref": signal.predictor_artifact_ref.model_dump(
                        mode="json"
                    ),
                    "predictive_attribution_ref": signal.predictive_attribution_ref.model_dump(
                        mode="json"
                    ),
                    "prediction_explanation_ref": signal.prediction_explanation_ref.model_dump(
                        mode="json"
                    ),
                    "prediction_calibration_ref": signal.prediction_calibration_ref.model_dump(
                        mode="json"
                    ),
                    "prediction_ranking_ref": signal.prediction_ranking_ref.model_dump(
                        mode="json"
                    ),
                    "prediction_delivery_metadata": signal.prediction_delivery_metadata.model_dump(
                        mode="json"
                    ),
                    "advisory_context": signal.advisory_context.model_dump(mode="json")
                    if signal.advisory_context is not None
                    else _field("missing"),
                },
            )
            accepted_at = _timestamp(received_at)
            ingress_ref = {
                "kind": "RiskSignal",
                "source_system": source.source_system,
                "source_signal_id": signal.source_signal_id,
                "source_revision": signal.source_revision,
                "source_payload_sha256": source.source_payload_sha256,
                "source_order_line_ref": source_ref,
            }
            request_id = "ir_" + uuid5(
                NAMESPACE_URL,
                f"causal-delay-copilot:investigation:{workspace_id}:{source.source_system}:{signal.source_signal_id}:{signal.source_revision}:{causal_input_digest}",
            ).hex
            request = {
                "investigation_request_id": request_id,
                "schema_version": "investigation-request.v1",
                "trigger_mode": "reactive",
                "ingress_ref": ingress_ref,
                "rerun_of_request_id": _field("missing"),
                "dataset_version_id": signal.scored_dataset_version_ref,
                "subject": {"order_line_id": canonical_order_line_id},
                "decision_cutoff": commitment_cutoff.field,
                "decision_cutoff_source": "canonical_commitment",
                "observation_cutoff": known.field,
                "target_milestone_kind": target_field,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "ingress_validation_refs": [
                    finding["finding_id"] for finding in cleaned_findings
                ],
                "provenance_refs": [
                    f"risk-signal:{source.source_system}:{signal.source_signal_id}:{signal.source_revision}",
                    *mapping_refs,
                    *evidence_refs,
                    *lineage_refs,
                ],
                "prediction_metadata": prediction_metadata,
                "accepted_at": accepted_at,
                "causal_engine_input": projection,
                "causal_input_digest": causal_input_digest,
            }
            request["content_hash"] = _sha256(
                {
                    key: value
                    for key, value in request.items()
                    if key not in {"accepted_at", "content_hash"}
                }
            )

        attempt_id = "attempt_pending"
        attempt = {
            "attempt_id": attempt_id,
            "status": status,
            "scope": "reactive_ingress",
            "source_system": source.source_system,
            "source_signal_id": signal.source_signal_id,
            "source_revision": signal.source_revision,
            "source_payload_sha256": source.source_payload_sha256,
            "primary_code": primary_code,
            "findings": cleaned_findings,
            "evidence_refs": sorted(
                set(
                    request["provenance_refs"]
                    if request is not None
                    else [*mapping_refs, *lineage_refs, *evidence_refs]
                )
            ),
            "retryable": primary_code
            in {
                "RISK_SIGNAL_INTEGRITY_FAILED",
                "RISK_SIGNAL_CLOCK_UNUSABLE",
                "RISK_SIGNAL_SUBJECT_UNRESOLVED",
                "RISK_SIGNAL_SUBJECT_AMBIGUOUS",
                "RISK_SIGNAL_CONTEXT_CONFLICT",
                "COMMITMENT_CUTOFF_UNUSABLE",
                "FROZEN_PROMISE_UNAVAILABLE",
                "FROZEN_PROMISE_CONFLICT",
                "FROZEN_PROMISE_TEMPORALLY_INVALID",
            },
            "recovery_action": _RECOVERY_ACTIONS[primary_code],
            "received_at": _timestamp(received_at),
            "investigation_request_id": (
                request["investigation_request_id"] if request is not None else None
            ),
            "investigation_request": request,
            "audit": {"occurrence_id": "pending", "event_seq": 0},
        }
        return attempt, request

    def _normalise_proactive_proposal(
        self,
        proposal: ProactiveProposalRequest,
        *,
        received_at: datetime,
        revision_conflict: bool,
        workspace_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        source = proposal.source
        findings: list[dict[str, Any]] = []
        schema_invalid = False
        integrity_invalid = False

        if proposal.schema_version != PROACTIVE_PROPOSAL_SCHEMA_VERSION or (
            source.schema_version != TRIGGER_SOURCE_SCHEMA_VERSION
        ) or proposal.trigger_mode != "proactive":
            schema_invalid = True
            findings.append(
                _finding(
                    code="PROACTIVE_SCHEMA_UNSUPPORTED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The proactive proposal schema or trigger mode is not supported by this Core release.",
                    remediation="Use the versioned bundled Proactive Proposal contract.",
                    phase=1,
                )
            )

        if (
            not _SHA256_PATTERN.fullmatch(source.source_payload_sha256)
            or not source.protected_source_locator.startswith(
                "bundled://proactive-proposal/"
            )
            or source.source_system != PROACTIVE_SOURCE_SYSTEM
            or not _matches_bundled_proactive_proposal(proposal)
        ):
            integrity_invalid = True
            findings.append(
                _finding(
                    code="PROACTIVE_INTEGRITY_FAILED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The protected Proactive Proposal envelope failed its integrity check.",
                    remediation="Use an unmodified bundled proposal and retry.",
                    phase=2,
                )
            )

        if revision_conflict:
            findings.append(
                _finding(
                    code="PROACTIVE_REVISION_CONFLICT",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The proposal identity and revision already carry different protected content.",
                    remediation="Submit a new immutable proposal revision.",
                    phase=3,
                )
            )

        lineage: dict[str, Any] | None = None
        mapping_refs: list[str] = []
        field_lineage_refs = sorted(
            {
                f"proactive-field:{field.lineage_ref}"
                for field in (
                    proposal.proposed_supplier_ref,
                    proposal.target_milestone_kind,
                    proposal.proposed_original_promise,
                    proposal.decision_at,
                    *proposal.adjustment_inputs.values(),
                )
                if field.lineage_ref is not None
            }
        )
        dataset_id = ""
        if not schema_invalid and not integrity_invalid and not revision_conflict:
            from .ingestion import DatasetVersionUnavailable

            try:
                if not self._is_bundled_dataset_version(proposal.dataset_version_id):
                    raise DatasetVersionUnavailable
                lineage = self.get_lineage(proposal.dataset_version_id)
            except DatasetVersionUnavailable:
                findings.append(
                    _finding(
                        code="PROACTIVE_DATASET_UNAVAILABLE",
                        severity="error",
                        disposition="reject",
                        affected_refs=[proposal.dataset_version_id],
                        message="The frozen Dataset Version is not an authorized bundled Core version.",
                        remediation="Select one frozen bundled Dataset Version and retry.",
                        phase=5,
                    )
                )
            if lineage is not None:
                dataset = lineage.get("dataset_version", {})
                dataset_id = str(dataset.get("dataset_id", ""))
                mapping_refs = _lineage_mapping_refs(lineage)

        decision = _normalise_proactive_temporal(proposal.decision_at)
        supplier_source = _proactive_source_reference(
            proposal.proposed_supplier_ref,
            dataset_id=dataset_id,
            mapping_manifest=(lineage or {}).get("mapping_manifest", {}),
        )
        target = _proactive_target_field(proposal.target_milestone_kind)
        promise = _normalise_proactive_temporal(proposal.proposed_original_promise)
        if promise.comparable is not None and decision.comparable is not None:
            promise_order = _compare(promise, decision)
            if promise_order == -1:
                promise = _Temporal(_field("invalid"), None)
        preview_subject_digest = _sha256(
            {
                "source_system": source.source_system,
                "proposal_id": proposal.proposal_id,
                "proposal_revision": proposal.proposal_revision,
                "dataset_version_id": proposal.dataset_version_id,
                "proposed_supplier_ref": proposal.proposed_supplier_ref.model_dump(
                    mode="json"
                ),
                "resolved_supplier_id": supplier_source,
                "decision_at": proposal.decision_at.model_dump(mode="json"),
                "target_milestone_kind": proposal.target_milestone_kind.model_dump(
                    mode="json"
                ),
                "proposed_original_promise": proposal.proposed_original_promise.model_dump(
                    mode="json"
                ),
                "adjustment_inputs": {
                    name: field.model_dump(mode="json")
                    for name, field in sorted(proposal.adjustment_inputs.items())
                },
            }
        )

        adjustment_fields: dict[str, Any] = {}
        subject_adjustments: dict[str, dict[str, Any]] = {}
        registered_adjustments = (
            "material_class",
            "complexity_class",
            "quantity",
            "value",
            "project_id",
            "project_phase",
            "urgency_class",
            "geography_code",
            "contract_form",
        )
        for name in registered_adjustments:
            field = proposal.adjustment_inputs.get(name)
            if field is None:
                subject_adjustments[name] = {"state": "missing"}
                adjustment_fields[name] = _field("missing")
                continue
            subject_adjustments[name] = field.model_dump(mode="json")
            adjustment_fields[name] = _proactive_projection_field(field, decision)
        if set(proposal.adjustment_inputs).difference(registered_adjustments):
            findings.append(
                _finding(
                    code="PROACTIVE_SCHEMA_UNSUPPORTED",
                    severity="error",
                    disposition="reject",
                    affected_refs=sorted(
                        set(proposal.adjustment_inputs).difference(registered_adjustments)
                    ),
                    message="The proposal contains an adjustment input outside the registered subject set.",
                    remediation="Submit only the versioned registered adjustment inputs.",
                    phase=1,
                )
            )

        resolved_supplier_field = _proactive_projection_field(
            proposal.proposed_supplier_ref,
            decision,
            value=supplier_source.get("value"),
            state=supplier_source.get("state"),
        )
        target_field = _proactive_projection_field(
            proposal.target_milestone_kind,
            decision,
            value=target.get("value"),
            state=target.get("state"),
        )
        original_promise_field = _proactive_projection_field(
            proposal.proposed_original_promise,
            decision,
            temporal=promise,
        )

        selected_ids: list[str] = []
        load_snapshot_error: str | None = None
        load_exposure: dict[str, Any] | None = None
        duration_basis: str | None = None
        duration_basis_evidence: dict[str, Any] = {
            "counts": {},
            "identity_hashes": {},
        }
        configuration = ENGINE_CONFIGURATION_REGISTRY.get(ENGINE_CONFIGURATION_REF)
        if lineage is not None and configuration is not None:
            duration_basis_evidence = _duration_basis_at_cutoff(
                configuration,
                dataset_version_id=proposal.dataset_version_id,
            )
            duration_basis = duration_basis_evidence["basis"]
            if (
                decision.comparable is not None
                and resolved_supplier_field.get("state") == "present"
                and target_field.get("state") == "present"
            ):
                selected_ids, load_snapshot_error = _selected_order_line_ids(
                    lineage,
                    subject_id=preview_subject_digest,
                    subject_supplier_id=str(resolved_supplier_field.get("value")),
                    decision_cutoff=decision,
                    target_milestone_kind=str(target_field.get("value")),
                )
                if load_snapshot_error is not None:
                    findings.append(
                        _finding(
                            code=load_snapshot_error,
                            severity="error",
                            disposition="reject",
                            affected_refs=[preview_subject_digest],
                            message="The point-in-time supplier history contains an unresolved membership fact.",
                            remediation="Repair the frozen canonical clocks and retry the proposal.",
                            phase=9,
                        )
                    )
                elif duration_basis is not None:
                    load_exposure = derive_supplier_load_exposure(
                        lineage,
                        subject_id=preview_subject_digest,
                        subject_supplier_id=str(resolved_supplier_field.get("value")),
                        decision_cutoff=decision,
                        target_milestone_kind=str(target_field.get("value")),
                        duration_basis=duration_basis,
                        trigger_mode="proactive",
                    )
                    exposure_codes = load_exposure.get("eligibility_codes", [])
                    blocking_exposure_codes = {
                        str(code)
                        for code in exposure_codes
                        if isinstance(code, str)
                    }.intersection(
                        {"LOAD_SNAPSHOT_UNRESOLVABLE", "COMMITMENT_CUTOFF_UNUSABLE"}
                    )
                    if blocking_exposure_codes:
                        code = sorted(blocking_exposure_codes)[0]
                        findings.append(
                            _finding(
                                code=code,
                                severity="error",
                                disposition="reject",
                                affected_refs=[preview_subject_digest],
                                message="The point-in-time supplier preview contains an unresolved membership fact.",
                                remediation="Repair the frozen canonical clocks and retry the proposal.",
                                phase=9,
                            )
                        )

        if CAUSAL_QUESTION_VERSION not in CAUSAL_QUESTION_REGISTRY:
            findings.append(
                _finding(
                    code="CAUSAL_QUESTION_VERSION_UNAVAILABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The fixed causal question version is unavailable in this Core release.",
                    remediation="Restore the versioned Core causal-question configuration.",
                    phase=9,
                )
            )
        if ENGINE_CONFIGURATION_REF not in ENGINE_CONFIGURATION_REGISTRY:
            findings.append(
                _finding(
                    code="ENGINE_CONFIGURATION_UNAVAILABLE",
                    severity="error",
                    disposition="reject",
                    affected_refs=[],
                    message="The fixed causal engine configuration is unavailable in this Core release.",
                    remediation="Restore the versioned Core engine configuration.",
                    phase=9,
                )
            )
        if lineage is not None and configuration is not None and duration_basis is None:
            findings.append(
                _finding(
                    code="SLIPPAGE_DURATION_BASIS_MIXED",
                    severity="error",
                    disposition="reject",
                    affected_refs=[
                        f"{basis}:{duration_basis_evidence['counts'][basis]}:{duration_basis_evidence['identity_hashes'][basis]}"
                        for basis in sorted(duration_basis_evidence["counts"])
                    ],
                    message="Released target rows do not share one canonical slippage duration basis.",
                    remediation="Wait for a released Dataset Version with one duration basis before creating an engine request.",
                    phase=9,
                )
            )

        findings.sort(key=lambda finding: (finding["_phase"], finding["_code_order"]))
        rejecting = [finding for finding in findings if _is_rejection(finding)]
        cleaned_findings = [_clean_finding(finding) for finding in findings]
        primary_code = (
            rejecting[0]["code"] if rejecting else "PROACTIVE_ACCEPTED"
        )
        status = (
            "rejected"
            if rejecting
            else "accepted_with_warning"
            if findings
            else "accepted"
        )
        request: dict[str, Any] | None = None
        if (
            not rejecting
            and lineage is not None
            and duration_basis is not None
            and configuration is not None
        ):
            projection = {
                "causal_input_schema_version": CAUSAL_INPUT_SCHEMA_VERSION,
                "dataset_version_id": proposal.dataset_version_id,
                "subject_analytical_values": {
                    "supplier_id": resolved_supplier_field,
                    "original_promise": original_promise_field,
                    "adjustment_inputs": adjustment_fields,
                    "subject_exclusion_identity": preview_subject_digest,
                },
                "decision_cutoff": decision.field,
                "observation_cutoff": decision.field,
                "target_milestone_kind": target_field,
                "canonical_slippage_duration_basis": duration_basis,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "supplier_load_exposure": load_exposure,
                "estimator_window_ref": _window_ref(
                    selector_version=configuration["estimator_window_selector_version"],
                    selected_ids=selected_ids,
                    observation_cutoff=decision,
                    subject_id=preview_subject_digest,
                    remove_subject=False,
                ),
                "history_lookback_ref": _window_ref(
                    selector_version=configuration["history_lookback_selector_version"],
                    selected_ids=selected_ids,
                    observation_cutoff=decision,
                    subject_id=preview_subject_digest,
                    remove_subject=False,
                ),
                "historical_population_digest": _historical_population_digest(
                    lineage,
                    selected_ids,
                    decision_cutoff=decision,
                ),
                "analytical_fact_lineage_refs": sorted(
                    {*mapping_refs, *field_lineage_refs}
                ),
            }
            causal_input_digest = _sha256(projection)
            subject = {
                "kind": "proactive_preview",
                "preview_subject_digest": preview_subject_digest,
                "proposal_id": proposal.proposal_id,
                "proposal_revision": proposal.proposal_revision,
                "supplier_id": _proactive_subject_input(
                    proposal.proposed_supplier_ref,
                    resolved_supplier_field,
                ),
                "target_milestone_kind": _proactive_subject_input(
                    proposal.target_milestone_kind,
                    target,
                ),
                "original_promise": _proactive_subject_input(
                    proposal.proposed_original_promise,
                    promise.field,
                    temporal=True,
                ),
                "adjustment_inputs": {
                    name: _proactive_subject_input(
                        proposal.adjustment_inputs[name],
                        _field(
                            proposal.adjustment_inputs[name].state,
                            proposal.adjustment_inputs[name].value,
                        ),
                    )
                    if name in proposal.adjustment_inputs
                    else {"state": "missing"}
                    for name in registered_adjustments
                },
            }
            request = {
                "investigation_request_id": "ir_" + uuid5(
                    NAMESPACE_URL,
                    f"causal-delay-copilot:investigation:{workspace_id}:{source.source_system}:{proposal.proposal_id}:{proposal.proposal_revision}:{causal_input_digest}",
                ).hex,
                "schema_version": "investigation-request.v1",
                "trigger_mode": "proactive",
                "ingress_ref": {
                    "kind": "ProactiveProposal",
                    "source_system": source.source_system,
                    "proposal_id": proposal.proposal_id,
                    "proposal_revision": proposal.proposal_revision,
                    "source_payload_sha256": source.source_payload_sha256,
                },
                "rerun_of_request_id": _field("missing"),
                "dataset_version_id": proposal.dataset_version_id,
                "subject": subject,
                "decision_cutoff": decision.field,
                "decision_cutoff_source": "proactive_decision",
                "observation_cutoff": decision.field,
                "target_milestone_kind": target_field,
                "causal_question_version": CAUSAL_QUESTION_VERSION,
                "engine_configuration_ref": ENGINE_CONFIGURATION_REF,
                "ingress_validation_refs": [
                    finding["finding_id"] for finding in cleaned_findings
                ],
                "provenance_refs": [
                    f"proactive-proposal:{source.source_system}:{proposal.proposal_id}:{proposal.proposal_revision}",
                    *mapping_refs,
                    *field_lineage_refs,
                ],
                "prediction_metadata": _field("not_applicable"),
                "accepted_at": _timestamp(received_at),
                "causal_engine_input": projection,
                "causal_input_digest": causal_input_digest,
            }
            request["content_hash"] = _sha256(
                {
                    key: value
                    for key, value in request.items()
                    if key not in {"accepted_at", "content_hash"}
                }
            )

        attempt = {
            "attempt_id": "attempt_pending",
            "status": status,
            "scope": "proactive_ingress",
            "source_system": source.source_system,
            "proposal_id": proposal.proposal_id,
            "proposal_revision": proposal.proposal_revision,
            "source_payload_sha256": source.source_payload_sha256,
            "primary_code": primary_code,
            "findings": cleaned_findings,
            "evidence_refs": sorted(
                set(
                    request["provenance_refs"]
                    if request is not None
                    else [*mapping_refs, *field_lineage_refs]
                )
            ),
            "retryable": primary_code
            in {
                "PROACTIVE_INTEGRITY_FAILED",
                "PROACTIVE_DATASET_UNAVAILABLE",
                "COMMITMENT_CUTOFF_UNUSABLE",
                "LOAD_SNAPSHOT_UNRESOLVABLE",
                "SLIPPAGE_DURATION_BASIS_MIXED",
            },
            "recovery_action": _RECOVERY_ACTIONS.get(
                primary_code,
                "RESTORE_VERSIONED_CORE_CONFIGURATION",
            ),
            "received_at": _timestamp(received_at),
            "investigation_request_id": (
                request["investigation_request_id"] if request is not None else None
            ),
            "investigation_request": request,
            "audit": {"occurrence_id": "pending", "event_seq": 0},
        }
        return attempt, request

    def _validate_advisory_context(
        self,
        signal: RiskSignalRequest,
        *,
        dataset_id: str,
        order_line: Mapping[str, Any],
        mapping_manifest: Mapping[str, Any],
        events: list[Mapping[str, Any]],
        generated: _Temporal,
        known: _Temporal,
        findings: list[dict[str, Any]],
    ) -> None:
        context = signal.advisory_context
        if context is None or context.state != "present":
            findings.append(
                _finding(
                    code="RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
                    severity="warning",
                    disposition="advisory",
                    affected_refs=[],
                    message="Advisory Risk Signal context was not comparable and was excluded from canonical facts.",
                    remediation="Continue with canonical Order Line facts only.",
                    phase=8,
                )
            )
            return
        context_reference = f"canonical-order-line:{order_line.get('order_line_id', 'unresolved')}"
        if not isinstance(context.value, Mapping):
            findings.append(
                _finding(
                    code="RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
                    severity="warning",
                    disposition="advisory",
                    affected_refs=[context_reference],
                    message="Advisory Risk Signal context could not be resolved and was ignored.",
                    remediation="Continue with canonical Order Line facts only.",
                    phase=8,
                )
            )
            return
        try:
            advisory = RiskSignalAdvisoryContextRequest.model_validate(context.value)
        except ValueError:
            findings.append(
                _finding(
                    code="RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
                    severity="warning",
                    disposition="advisory",
                    affected_refs=[context_reference],
                    message="Advisory Risk Signal context contains no reviewed comparable shape.",
                    remediation="Continue with canonical Order Line facts only.",
                    phase=8,
                )
            )
            return

        def warning() -> None:
            findings.append(
                _finding(
                    code="RISK_SIGNAL_CONTEXT_UNVERIFIABLE",
                    severity="warning",
                    disposition="advisory",
                    affected_refs=[context_reference],
                    message="One advisory Risk Signal context member was not comparable and was ignored.",
                    remediation="Continue with canonical Order Line facts only.",
                    phase=8,
                )
            )

        supplier_ref = advisory.source_supplier_ref
        if supplier_ref is not None and supplier_ref.state == "present":
            if not isinstance(supplier_ref.value, Mapping):
                warning()
            else:
                namespace = supplier_ref.value.get("namespace")
                keys = _source_key(supplier_ref.value.get("key"))
                if namespace != SOURCE_NAMESPACE or len(keys) != 1:
                    warning()
                else:
                    expected_supplier = _canonical_identity_from_mapping(
                        dataset_id,
                        mapping_manifest,
                        "supplier_id",
                        keys[0],
                    )
                    if expected_supplier is None:
                        warning()
                    elif expected_supplier != order_line.get("supplier_id"):
                        findings.append(
                            _finding(
                                code="RISK_SIGNAL_CONTEXT_CONFLICT",
                                severity="error",
                                disposition="reject",
                                affected_refs=[context_reference],
                                message="Advisory supplier context conflicts with the canonical Order Line supplier.",
                                remediation="Review advisory context against the frozen canonical Order Line.",
                                phase=8,
                            )
                        )
        elif supplier_ref is not None:
            warning()

        material_ref = advisory.source_material_or_equipment_ref
        if material_ref is not None and material_ref.state == "present":
            if not isinstance(material_ref.value, Mapping):
                warning()
            else:
                namespace = material_ref.value.get("namespace")
                keys = _source_key(material_ref.value.get("key"))
                canonical_material = _field_from_record(
                    order_line.get("fields", {}).get("material_class")
                )
                material_mapping = mapping_manifest.get(
                    "advisory_context_mappings", {}
                )
                material_mapping = (
                    material_mapping.get("material_or_equipment")
                    if isinstance(material_mapping, Mapping)
                    else None
                )
                if namespace != SOURCE_NAMESPACE or len(keys) != 1:
                    warning()
                elif not (
                    isinstance(material_mapping, Mapping)
                    and isinstance(material_mapping.get("rule_id"), str)
                    and isinstance(material_mapping.get("rule_version"), str)
                ):
                    warning()
                elif _resolve_advisory_material_key(
                    material_ref.value,
                    mapping_manifest,
                ) is None:
                    warning()
                elif (
                    canonical_material.get("state") == "present"
                    and _resolve_advisory_material_key(
                        material_ref.value,
                        mapping_manifest,
                    )
                    != canonical_material.get("value")
                ):
                    findings.append(
                        _finding(
                            code="RISK_SIGNAL_CONTEXT_CONFLICT",
                            severity="error",
                            disposition="reject",
                            affected_refs=[context_reference],
                            message="Advisory material or equipment context conflicts with the canonical Order Line material.",
                            remediation="Review advisory context against the frozen canonical Order Line.",
                            phase=8,
                        )
                    )
                elif canonical_material.get("state") != "present":
                    warning()
        elif material_ref is not None:
            warning()

        target_ref = advisory.source_target_milestone_kind
        if target_ref is not None:
            if target_ref.state == "present" and target_ref.value != CONFIGURED_TARGET_MILESTONE_KIND:
                findings.append(
                    _finding(
                        code="RISK_SIGNAL_CONTEXT_CONFLICT",
                        severity="error",
                        disposition="reject",
                        affected_refs=[context_reference],
                        message="Advisory target milestone conflicts with the configured target.",
                        remediation="Review advisory context against the configured milestone.",
                        phase=8,
                    )
                )
            elif target_ref.state != "present":
                warning()

        timeline_cutoff = generated
        timeline_usable = True
        timeline_ref = advisory.timeline_snapshot_as_of
        if timeline_ref is not None:
            if timeline_ref.state != "present" or not isinstance(timeline_ref.value, Mapping):
                warning()
                timeline_usable = False
            else:
                timeline = _normalise_temporal(timeline_ref.value)
                if (
                    _compare(timeline, generated) is None
                    or _compare(timeline, known) is None
                ):
                    warning()
                    timeline_usable = False
                elif _compare(timeline, generated) == 1 or _compare(timeline, known) == 1:
                    findings.append(
                        _finding(
                            code="RISK_SIGNAL_CONTEXT_CONFLICT",
                            severity="error",
                            disposition="reject",
                            affected_refs=[context_reference],
                            message="The advisory timeline snapshot is later than the signal clocks.",
                            remediation="Use a snapshot cutoff no later than signal generation and availability.",
                            phase=8,
                        )
                    )
                    timeline_usable = False
                else:
                    timeline_cutoff = timeline

        promise_ref = advisory.source_original_promise
        if promise_ref is not None:
            if promise_ref.state != "present" or not isinstance(promise_ref.value, Mapping):
                warning()
            else:
                promise = _normalise_temporal(promise_ref.value)
                canonical_promise = (
                    _resolve_frozen_promise(
                        events,
                        target_milestone_kind=signal.target_milestone_kind,
                        commitment_cutoff=timeline_cutoff,
                    ).value
                    if timeline_usable
                    else None
                )
                equal = _equal_temporal(promise, canonical_promise)
                if equal is False:
                    findings.append(
                        _finding(
                            code="RISK_SIGNAL_CONTEXT_CONFLICT",
                            severity="error",
                            disposition="reject",
                            affected_refs=[context_reference],
                            message="Advisory promise context conflicts with the canonical timeline snapshot.",
                            remediation="Review advisory context against the frozen canonical promise.",
                            phase=8,
                        )
                    )
                elif equal is None:
                    warning()
