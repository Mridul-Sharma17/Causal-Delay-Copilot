from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import sqlite3
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from .canonical import canonical_json as _canonical_json
from .canonical import normalise_temporal, sha256 as _sha256


CURRENTNESS_POLICY_IDENTIFIER = "decision-support-advice-currentness"
CURRENTNESS_POLICY_VERSION = "1"
CURRENTNESS_POLICY_IDENTIFIER_AND_VERSION = {
    "identifier": CURRENTNESS_POLICY_IDENTIFIER,
    "version": CURRENTNESS_POLICY_VERSION,
}
CURRENTNESS_OPERATION_SCHEMA_IDENTIFIER = "advice-currentness-operation"
CURRENTNESS_CHECK_SCHEMA_IDENTIFIER = "advice-currentness-check"
CURRENTNESS_INVALIDATION_SCHEMA_IDENTIFIER = "advice-currentness-invalidation"
CURRENT_ADVICE_RENDER_REQUEST_SCHEMA_IDENTIFIER = "current-advice-render-request"
CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER = "current-advice-render-result"
CURRENTNESS_SCHEMA_VERSION = "1"

CURRENTNESS_OPERATION_KINDS = frozenset(
    {
        "CURRENT_ADVICE_RENDER",
        "TRADEOFF_SELECTION_ACCEPTANCE",
        "MANAGER_AUTHORIZATION",
        "MONITORING_TRIGGER_MATCH",
    }
)

CURRENTNESS_CONSUMING_RESULT_BY_OPERATION_KIND = {
    "CURRENT_ADVICE_RENDER": CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER,
    "TRADEOFF_SELECTION_ACCEPTANCE": "tradeoff-selection-result",
    "MANAGER_AUTHORIZATION": "authorization-currentness-result",
    "MONITORING_TRIGGER_MATCH": "monitoring-match-result",
}
CURRENTNESS_CONSUMING_RESULT_SCHEMA_VERSION = "1"
CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_KIND = (
    "DECISION_SUPPORT_CURRENTNESS_SOURCE_OCCURRENCE"
)
CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_OUTCOME = "CURRENTNESS_SOURCE_REGISTERED"
CURRENTNESS_AUTHORITY_AUDIT_KIND = "DECISION_SUPPORT_CURRENTNESS_AUTHORITY"
CURRENTNESS_AUTHORITY_AUDIT_OUTCOME = "CURRENTNESS_AUTHORITY_UPDATED"
CURRENTNESS_SOURCE_SCHEMAS = frozenset(
    {
        "tradeoff-selection-delivery-attempt",
        "manager-authorization-attempt",
        "monitoring-observation",
    }
)

CURRENTNESS_OUTCOMES = frozenset(
    {
        "CURRENTNESS_PROVEN_AT_CHECK",
        "CURRENTNESS_NOT_AUTHORITATIVE_HEAD",
        "ADVICE_CURRENTNESS_INVALIDATION",
    }
)

CURRENTNESS_REASON_PRIORITY = {
    "GOVERNED_DEPENDENCY_NOT_CURRENT": 100,
    "OPERATIONAL_FACT_EXPIRED": 200,
    "CURRENTNESS_COMPARISON_UNRESOLVED": 300,
}


class DecisionSupportCurrentnessUnavailable(RuntimeError):
    """A currentness envelope or stored proof failed its closed contract."""


class DecisionSupportCurrentnessConflict(RuntimeError):
    """One logical currentness occurrence was redelivered with different content."""


class DecisionSupportCurrentnessOperationMismatch(RuntimeError):
    """A valid operation was presented through a different bound consumer."""


class _CurrentnessFinalHeadRace(RuntimeError):
    """The invalidation compare-and-publish lost after staging its check."""


@dataclass(frozen=True, slots=True)
class StoredCurrentnessResult:
    result: str
    operation: dict[str, Any]
    currentness: dict[str, Any]
    terminal_claim: dict[str, Any]
    render: dict[str, Any] | None
    consuming_result: dict[str, Any] | None
    head: dict[str, Any]


CURRENTNESS_OPERATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_currentness_operations (
        operation_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        currentness_operation_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        operation_kind TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        evaluation_occurrence_id TEXT NOT NULL,
        evaluation_digest TEXT NOT NULL,
        terminal_result_ref TEXT NOT NULL,
        terminal_result_hash TEXT NOT NULL,
        recommendation_ref TEXT,
        recommendation_hash TEXT,
        selection_claim_ref TEXT,
        selection_claim_hash TEXT,
        operation_payload_ref TEXT NOT NULL,
        operation_payload_hash TEXT NOT NULL,
        currentness_checked_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, currentness_operation_key)
    )
"""
CURRENTNESS_OPERATIONS_COLUMNS = [
    "operation_occurrence_id",
    "workspace_id",
    "currentness_operation_key",
    "content_hash",
    "operation_kind",
    "evaluation_series_id",
    "evaluation_occurrence_id",
    "evaluation_digest",
    "terminal_result_ref",
    "terminal_result_hash",
    "recommendation_ref",
    "recommendation_hash",
    "selection_claim_ref",
    "selection_claim_hash",
    "operation_payload_ref",
    "operation_payload_hash",
    "currentness_checked_at",
    "created_at",
    "payload_json",
]

CURRENTNESS_CHECKS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_currentness_checks (
        currentness_check_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        currentness_check_key TEXT NOT NULL,
        currentness_operation_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        currentness_outcome TEXT NOT NULL,
        currentness_checked_at TEXT NOT NULL,
        currentness_evidence_digest TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, currentness_check_key),
        FOREIGN KEY (workspace_id, currentness_operation_key)
            REFERENCES decision_support_currentness_operations(
                workspace_id, currentness_operation_key
            )
    )
"""
CURRENTNESS_CHECKS_COLUMNS = [
    "currentness_check_occurrence_id",
    "workspace_id",
    "currentness_check_key",
    "currentness_operation_key",
    "content_hash",
    "currentness_outcome",
    "currentness_checked_at",
    "currentness_evidence_digest",
    "created_at",
    "payload_json",
]

CURRENTNESS_CLAIMS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_currentness_terminal_claims (
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        currentness_operation_key TEXT NOT NULL,
        operation_occurrence_id TEXT NOT NULL,
        currentness_check_key TEXT NOT NULL,
        terminal_currentness_ref TEXT NOT NULL,
        terminal_currentness_hash TEXT NOT NULL,
        currentness_outcome TEXT NOT NULL,
        consuming_result_kind TEXT NOT NULL,
        consuming_result_ref TEXT,
        consuming_result_hash TEXT,
        refusal_result_ref TEXT,
        refusal_result_hash TEXT,
        installed_invalidation_head_ref TEXT,
        installed_invalidation_head_hash TEXT,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (workspace_id, currentness_operation_key),
        FOREIGN KEY (operation_occurrence_id)
            REFERENCES decision_support_currentness_operations(operation_occurrence_id),
        FOREIGN KEY (workspace_id, currentness_check_key)
            REFERENCES decision_support_currentness_checks(workspace_id, currentness_check_key)
    )
"""
CURRENTNESS_CLAIMS_COLUMNS = [
    "workspace_id",
    "currentness_operation_key",
    "operation_occurrence_id",
    "currentness_check_key",
    "terminal_currentness_ref",
    "terminal_currentness_hash",
    "currentness_outcome",
    "consuming_result_kind",
    "consuming_result_ref",
    "consuming_result_hash",
    "refusal_result_ref",
    "refusal_result_hash",
    "installed_invalidation_head_ref",
    "installed_invalidation_head_hash",
    "content_hash",
    "created_at",
    "payload_json",
]

CURRENT_ADVICE_RENDER_REQUESTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_current_advice_render_requests (
        render_request_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        current_advice_render_request_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        evaluation_occurrence_id TEXT NOT NULL,
        available_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, current_advice_render_request_key)
    )
"""
CURRENT_ADVICE_RENDER_REQUESTS_COLUMNS = [
    "render_request_occurrence_id",
    "workspace_id",
    "current_advice_render_request_key",
    "content_hash",
    "evaluation_series_id",
    "evaluation_occurrence_id",
    "available_at",
    "created_at",
    "payload_json",
]

CURRENT_ADVICE_RENDER_RESULTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_current_advice_render_results (
        render_result_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        current_advice_render_result_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        render_request_ref TEXT NOT NULL,
        render_request_hash TEXT NOT NULL,
        currentness_check_ref TEXT NOT NULL,
        currentness_check_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, current_advice_render_result_key)
    )
"""
CURRENT_ADVICE_RENDER_RESULTS_COLUMNS = [
    "render_result_occurrence_id",
    "workspace_id",
    "current_advice_render_result_key",
    "content_hash",
    "render_request_ref",
    "render_request_hash",
    "currentness_check_ref",
    "currentness_check_hash",
    "created_at",
    "payload_json",
]

CURRENTNESS_CONSUMING_RESULTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_currentness_consuming_results (
        consuming_result_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        consuming_result_key TEXT NOT NULL,
        consuming_result_kind TEXT NOT NULL,
        currentness_operation_key TEXT NOT NULL,
        currentness_check_ref TEXT NOT NULL,
        currentness_check_hash TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, consuming_result_key)
    )
"""
CURRENTNESS_CONSUMING_RESULTS_COLUMNS = [
    "consuming_result_occurrence_id",
    "workspace_id",
    "consuming_result_key",
    "consuming_result_kind",
    "currentness_operation_key",
    "currentness_check_ref",
    "currentness_check_hash",
    "content_hash",
    "created_at",
    "payload_json",
]

CURRENTNESS_AUTHORITIES_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_currentness_authorities (
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        evaluation_series_id TEXT NOT NULL,
        dependency_kind TEXT NOT NULL,
        dependency_id TEXT NOT NULL,
        dependency_version TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (
            workspace_id, evaluation_series_id,
            dependency_kind, dependency_id, dependency_version
        )
    )
"""
CURRENTNESS_AUTHORITIES_COLUMNS = [
    "workspace_id",
    "evaluation_series_id",
    "dependency_kind",
    "dependency_id",
    "dependency_version",
    "content_hash",
    "updated_at",
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
            f"{table_name} schema is not the locked currentness schema"
        )


def ensure_currentness_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    tables = (
        (
            "decision_support_currentness_operations",
            CURRENTNESS_OPERATIONS_TABLE,
            CURRENTNESS_OPERATIONS_COLUMNS,
        ),
        (
            "decision_support_currentness_checks",
            CURRENTNESS_CHECKS_TABLE,
            CURRENTNESS_CHECKS_COLUMNS,
        ),
        (
            "decision_support_currentness_terminal_claims",
            CURRENTNESS_CLAIMS_TABLE,
            CURRENTNESS_CLAIMS_COLUMNS,
        ),
        (
            "decision_support_current_advice_render_requests",
            CURRENT_ADVICE_RENDER_REQUESTS_TABLE,
            CURRENT_ADVICE_RENDER_REQUESTS_COLUMNS,
        ),
        (
            "decision_support_current_advice_render_results",
            CURRENT_ADVICE_RENDER_RESULTS_TABLE,
            CURRENT_ADVICE_RENDER_RESULTS_COLUMNS,
        ),
        (
            "decision_support_currentness_consuming_results",
            CURRENTNESS_CONSUMING_RESULTS_TABLE,
            CURRENTNESS_CONSUMING_RESULTS_COLUMNS,
        ),
        (
            "decision_support_currentness_authorities",
            CURRENTNESS_AUTHORITIES_TABLE,
            CURRENTNESS_AUTHORITIES_COLUMNS,
        ),
    )
    for table_name, create_sql, columns in tables:
        _ensure_table(connection, table_name, create_sql, columns, create=create)
    if create:
        for table_name in (
            "decision_support_currentness_operations",
            "decision_support_currentness_checks",
            "decision_support_currentness_terminal_claims",
            "decision_support_current_advice_render_requests",
            "decision_support_current_advice_render_results",
            "decision_support_currentness_consuming_results",
        ):
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'Decision Support currentness records are immutable');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'Decision Support currentness records are immutable');
                END
                """
            )


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _hash_without_content_hash(value: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(value))
    payload.pop("content_hash", None)
    return _sha256(payload)


def _is_hash(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == len("sha256:") + 64
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _ref_and_hash(value: object) -> dict[str, str] | None:
    candidate = _mapping(value)
    if candidate is None:
        return None
    reference = candidate.get("reference")
    content_hash = candidate.get("content_hash")
    if (
        not isinstance(reference, str)
        or not reference
        or not isinstance(content_hash, str)
        or not _is_hash(content_hash)
    ):
        return None
    return {"reference": reference, "content_hash": content_hash}


def _policy(value: object) -> dict[str, str]:
    if value is None:
        raise DecisionSupportCurrentnessUnavailable(
            "currentness policy binding is missing"
        )
    if isinstance(value, str) and value == (
        f"{CURRENTNESS_POLICY_IDENTIFIER}:{CURRENTNESS_POLICY_VERSION}"
    ):
        return deepcopy(CURRENTNESS_POLICY_IDENTIFIER_AND_VERSION)
    candidate = _mapping(value)
    if candidate is None:
        raise DecisionSupportCurrentnessUnavailable(
            "currentness policy binding is invalid"
        )
    identifier = candidate.get("identifier")
    version = candidate.get("version")
    if identifier != CURRENTNESS_POLICY_IDENTIFIER or version != CURRENTNESS_POLICY_VERSION:
        raise DecisionSupportCurrentnessUnavailable(
            "currentness policy version is unsupported"
        )
    return {"identifier": str(identifier), "version": str(version)}


def _time(value: object) -> tuple[object, date | datetime] | None:
    if isinstance(value, Mapping):
        parsed = normalise_temporal(value)
        if parsed.comparable is None or parsed.field.get("state") != "present":
            return None
        return value, parsed.comparable
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        if "T" not in candidate:
            return value, date.fromisoformat(candidate)
        parsed_datetime = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed_datetime.tzinfo is None:
        return None
    return value, parsed_datetime.astimezone(timezone.utc)


def _time_compare(left: object, right: object) -> int | None:
    left_parsed = _time(left)
    right_parsed = _time(right)
    if left_parsed is None or right_parsed is None:
        return None
    left_value = left_parsed[1]
    right_value = right_parsed[1]
    if isinstance(left_value, datetime) and isinstance(right_value, date) and not isinstance(
        right_value, datetime
    ):
        right_value = datetime(
            right_value.year,
            right_value.month,
            right_value.day,
            tzinfo=timezone.utc,
        )
    if isinstance(right_value, datetime) and isinstance(left_value, date) and not isinstance(
        left_value, datetime
    ):
        left_value = datetime(
            left_value.year,
            left_value.month,
            left_value.day,
            tzinfo=timezone.utc,
        )
    if type(left_value) is not type(right_value):
        return None
    if left_value < right_value:
        return -1
    if left_value > right_value:
        return 1
    return 0


def _time_equal(left: object, right: object) -> bool:
    return _time_compare(left, right) == 0 and _canonical_json(left) == _canonical_json(right)


def _canonical_time(value: object) -> object:
    parsed = _time(value)
    if parsed is None:
        raise DecisionSupportCurrentnessUnavailable("currentness time is invalid")
    return deepcopy(value)


def _record_id(record: Mapping[str, Any]) -> str | None:
    for key in (
        "reference",
        "record_id",
        "occurrence_id",
        "attempt_occurrence_id",
        "delivery_attempt_occurrence_id",
        "authorization_attempt_occurrence_id",
        "observation_occurrence_id",
        "monitoring_observation_occurrence_id",
        "render_request_occurrence_id",
    ):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _record_content_hash(record: Mapping[str, Any]) -> str | None:
    payload = deepcopy(dict(record))
    supplied = payload.pop("content_hash", None)
    try:
        computed = _sha256(payload)
    except (TypeError, ValueError, OverflowError):
        return None
    if supplied is None:
        return computed
    if not _is_hash(supplied) or supplied != computed:
        return None
    return str(supplied)


def _ref_from_record(record: object) -> dict[str, str] | None:
    candidate = _mapping(record)
    if candidate is None:
        return None
    reference = _record_id(candidate)
    content_hash = _record_content_hash(candidate)
    if reference is None or content_hash is None:
        return None
    return {"reference": reference, "content_hash": content_hash}


def _ordered_dependencies(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DecisionSupportCurrentnessUnavailable(
            "advice currentness dependency set is invalid"
        )
    dependencies: list[dict[str, Any]] = []
    seen_identities: set[tuple[str, str, str]] = set()
    for item in value:
        candidate = _mapping(item)
        if candidate is None:
            raise DecisionSupportCurrentnessUnavailable(
                "advice currentness dependency is invalid"
            )
        dependency = deepcopy(dict(candidate))
        kind = dependency.get("dependency_kind")
        identifier = dependency.get("id") or dependency.get("reference")
        version = dependency.get("version")
        content_hash = dependency.get("content_hash")
        consumed_disposition = dependency.get("consumed_disposition")
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(identifier, str)
            or not identifier
            or not isinstance(version, str)
            or not version
            or not _is_hash(content_hash)
            or not isinstance(consumed_disposition, str)
            or not consumed_disposition
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "advice currentness dependency is incomplete"
            )
        dependency["id"] = identifier
        dependency["version"] = version
        identity = (kind, identifier, version)
        if identity in seen_identities:
            raise DecisionSupportCurrentnessUnavailable(
                "advice currentness dependency identities are duplicated"
            )
        seen_identities.add(identity)
        dependencies.append(dependency)
    return sorted(
        dependencies,
        key=lambda item: _canonical_json(
            {
                "dependency_kind": item["dependency_kind"],
                "id": item["id"],
                "version": item["version"],
                "content_hash": item["content_hash"],
            }
        ),
    )


def _ordered_horizons(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DecisionSupportCurrentnessUnavailable(
            "consumed operational horizons are invalid"
        )
    horizons: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in value:
        candidate = _mapping(item)
        if candidate is None:
            raise DecisionSupportCurrentnessUnavailable(
                "consumed operational horizon is invalid"
            )
        horizon = deepcopy(dict(candidate))
        valid_through = horizon.get("valid_through")
        if valid_through is None:
            raise DecisionSupportCurrentnessUnavailable(
                "consumed operational horizon is missing valid_through"
            )
        if valid_through != "NO_EXPIRY":
            _canonical_time(valid_through)
        reference = horizon.get("reference") or horizon.get("source_record_ref")
        content_hash = horizon.get("content_hash")
        if (
            not isinstance(reference, str)
            or not reference
            or not _is_hash(content_hash)
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "consumed operational horizon is missing its evidence binding"
            )
        horizon["reference"] = reference
        input_path = horizon.get("input_path")
        if not isinstance(input_path, str) or not input_path:
            raise DecisionSupportCurrentnessUnavailable(
                "consumed operational horizon is missing input_path"
            )
        if input_path in seen_paths:
            raise DecisionSupportCurrentnessUnavailable(
                "consumed operational horizon input paths are duplicated"
            )
        seen_paths.add(input_path)
        horizon["input_path"] = input_path
        horizons.append(horizon)
    return sorted(horizons, key=lambda item: str(item["input_path"]))


def _minimum_horizon(horizons: list[Mapping[str, Any]]) -> object:
    finite = [item.get("valid_through") for item in horizons if item.get("valid_through") != "NO_EXPIRY"]
    if not finite:
        return "NO_EXPIRY"
    earliest = finite[0]
    for candidate in finite[1:]:
        comparison = _time_compare(candidate, earliest)
        if comparison is None:
            raise DecisionSupportCurrentnessUnavailable(
                "operational validity horizons are not comparable"
            )
        if comparison < 0:
            earliest = candidate
    return deepcopy(earliest)


def _currentness_metadata(
    evaluation: Mapping[str, Any],
    identity_binding: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], object]:
    dependencies_value = evaluation.get("advice_currentness_dependency_set")
    if dependencies_value is None:
        governed = _mapping(identity_binding.get("governed_records")) or {}
        dependencies_value = governed.get("advice_currentness_dependency_set", [])
    horizons_value = evaluation.get("consumed_operational_horizons")
    if horizons_value is None:
        snapshot = _mapping(identity_binding.get("operational_snapshot")) or {}
        horizons_value = snapshot.get("consumed_operational_horizons")
        if horizons_value is None:
            facts = snapshot.get("facts")
            if isinstance(facts, list):
                snapshot_reference = snapshot.get("snapshot_id") or snapshot.get(
                    "record_id"
                )
                snapshot_hash = snapshot.get("content_hash")
                snapshot_binding_available = (
                    isinstance(snapshot_reference, str)
                    and bool(snapshot_reference)
                    and _is_hash(snapshot_hash)
                )
                converted: list[dict[str, Any]] = []
                for index, fact_value in enumerate(facts):
                    fact = _mapping(fact_value)
                    if fact is None:
                        raise DecisionSupportCurrentnessUnavailable(
                            "operational snapshot fact is invalid"
                        )
                    reference = fact.get("source_record_ref") or fact.get("provenance_ref")
                    content_hash = fact.get("content_hash")
                    if not isinstance(content_hash, str):
                        binding = _mapping(fact.get("source_record_ref_and_hash"))
                        if binding is not None:
                            reference = binding.get("reference") or reference
                            content_hash = binding.get("content_hash")
                    if not (_is_hash(content_hash) and isinstance(reference, str)):
                        value_binding = _mapping(fact.get("value"))
                        if value_binding is not None and _ref_and_hash(value_binding) is not None:
                            reference = value_binding["reference"]
                            content_hash = value_binding["content_hash"]
                    if not (_is_hash(content_hash) and isinstance(reference, str)):
                        if not snapshot_binding_available:
                            raise DecisionSupportCurrentnessUnavailable(
                                "operational snapshot fact lacks an integrity binding"
                            )
                        reference = str(snapshot_reference)
                        content_hash = str(snapshot_hash)
                    converted.append(
                        {
                            "input_path": f"operational_snapshot.facts[{index}]",
                            "reference": reference,
                            "content_hash": content_hash,
                            "valid_through": fact.get("valid_through"),
                        }
                    )
                horizons_value = converted
    dependencies = _ordered_dependencies(dependencies_value)
    horizons = _ordered_horizons(horizons_value)
    supplied_horizon = evaluation.get("advice_valid_through")
    if supplied_horizon is None:
        supplied_horizon = _minimum_horizon(horizons)
    elif supplied_horizon != "NO_EXPIRY":
        _canonical_time(supplied_horizon)
    derived_horizon = _minimum_horizon(horizons)
    if _canonical_json(supplied_horizon) != _canonical_json(derived_horizon):
        raise DecisionSupportCurrentnessUnavailable(
            "advice validity horizon does not match its consumed inputs"
        )
    return dependencies, horizons, deepcopy(supplied_horizon)


def derive_advice_currentness_metadata(
    evaluation: Mapping[str, Any],
    identity_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize the frozen currentness inputs on every published evaluation result."""

    dependencies, horizons, advice_valid_through = _currentness_metadata(
        evaluation,
        identity_binding,
    )
    return {
        "advice_currentness_dependency_set": dependencies,
        "consumed_operational_horizons": horizons,
        "advice_valid_through": advice_valid_through,
        "advice_currentness_metadata_state": _metadata_source_state(
            evaluation,
            identity_binding,
        ),
    }


def _metadata_source_state(
    evaluation: Mapping[str, Any],
    identity_binding: Mapping[str, Any],
) -> dict[str, str]:
    governed_records = _mapping(identity_binding.get("governed_records")) or {}
    snapshot = _mapping(identity_binding.get("operational_snapshot")) or {}
    if "advice_currentness_dependency_set" in evaluation:
        dependency_source = "EVALUATION_ENVELOPE"
    elif "advice_currentness_dependency_set" in governed_records:
        dependency_source = "GOVERNED_REGISTRY"
    else:
        dependency_source = "UNAVAILABLE"
    if "consumed_operational_horizons" in evaluation:
        horizon_source = "EVALUATION_ENVELOPE"
    elif "consumed_operational_horizons" in snapshot:
        horizon_source = "OPERATIONAL_SNAPSHOT"
    elif isinstance(snapshot.get("facts"), list):
        horizon_source = "OPERATIONAL_SNAPSHOT_FACTS"
    else:
        horizon_source = "UNAVAILABLE"
    return {
        "state": (
            "COMPLETE"
            if dependency_source != "UNAVAILABLE" and horizon_source != "UNAVAILABLE"
            else "UNAVAILABLE"
        ),
        "dependency_source": dependency_source,
        "horizon_source": horizon_source,
    }


def _key_fields(operation: Mapping[str, Any]) -> dict[str, Any]:
    if operation.get("schema_identifier") != CURRENTNESS_OPERATION_SCHEMA_IDENTIFIER:
        raise DecisionSupportCurrentnessUnavailable(
            "currentness operation schema is unsupported"
        )
    if operation.get("schema_version") != CURRENTNESS_SCHEMA_VERSION:
        raise DecisionSupportCurrentnessUnavailable(
            "currentness operation schema version is unsupported"
        )
    policy = _policy(operation.get("currentness_policy_identifier_and_version"))
    operation_kind = operation.get("operation_kind")
    if operation_kind not in CURRENTNESS_OPERATION_KINDS:
        raise DecisionSupportCurrentnessUnavailable("currentness operation kind is invalid")
    series_id = operation.get("evaluation_series_id")
    occurrence_id = operation.get("evaluation_occurrence_id")
    evaluation_digest = operation.get("evaluation_digest")
    terminal = _ref_and_hash(operation.get("terminal_result_ref_and_hash"))
    payload = _ref_and_hash(operation.get("operation_payload_ref_and_hash"))
    if (
        not isinstance(series_id, str)
        or not series_id
        or not isinstance(occurrence_id, str)
        or not occurrence_id
        or not _is_hash(evaluation_digest)
        or terminal is None
        or payload is None
    ):
        raise DecisionSupportCurrentnessUnavailable("currentness operation binding is incomplete")
    recommendation = operation.get(
        "recommendation_ref_and_hash_or_null",
        operation.get("recommendation_ref_and_hash"),
    )
    if recommendation is not None:
        recommendation = _ref_and_hash(recommendation)
        if recommendation is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness recommendation binding is invalid"
            )
    selection_claim = operation.get(
        "accepted_selection_claim_ref_and_hash_or_null",
        operation.get("accepted_selection_claim_ref_and_hash"),
    )
    if selection_claim is not None:
        selection_claim = _ref_and_hash(selection_claim)
        if selection_claim is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness selection claim binding is invalid"
            )
    checked_at = operation.get("currentness_checked_at")
    if checked_at is None:
        raise DecisionSupportCurrentnessUnavailable("currentness check time is missing")
    checked_at = _canonical_time(checked_at)
    return {
        "currentness_policy_identifier_and_version": policy,
        "operation_kind": operation_kind,
        "evaluation_series_id": series_id,
        "evaluation_occurrence_id": occurrence_id,
        "evaluation_digest": evaluation_digest,
        "terminal_result_ref_and_hash": terminal,
        "recommendation_ref_and_hash_or_null": recommendation,
        "accepted_selection_claim_ref_and_hash_or_null": selection_claim,
        "operation_payload_ref_and_hash": payload,
        "currentness_checked_at": checked_at,
    }


def currentness_operation_key_for(operation: Mapping[str, Any]) -> str:
    if all(
        key in operation
        for key in (
            "currentness_policy_identifier_and_version",
            "operation_kind",
            "evaluation_series_id",
            "evaluation_occurrence_id",
            "evaluation_digest",
            "terminal_result_ref_and_hash",
            "recommendation_ref_and_hash_or_null",
            "accepted_selection_claim_ref_and_hash_or_null",
            "operation_payload_ref_and_hash",
            "currentness_checked_at",
        )
    ):
        fields = operation
    else:
        fields = _key_fields(operation)
    return _sha256(
        {
            "currentness_policy_identifier_and_version": fields[
                "currentness_policy_identifier_and_version"
            ],
            "operation_kind": fields["operation_kind"],
            "evaluation_series_id": fields["evaluation_series_id"],
            "evaluation_occurrence_id": fields["evaluation_occurrence_id"],
            "terminal_result_ref_and_hash": fields["terminal_result_ref_and_hash"],
            "recommendation_ref_and_hash_or_null": fields[
                "recommendation_ref_and_hash_or_null"
            ],
            "accepted_selection_claim_ref_and_hash_or_null": fields[
                "accepted_selection_claim_ref_and_hash_or_null"
            ],
            "operation_payload_ref_and_hash": fields["operation_payload_ref_and_hash"],
            "currentness_checked_at": fields["currentness_checked_at"],
        }
    )


def currentness_check_key_for(operation: Mapping[str, Any]) -> str:
    operation_key = operation.get("currentness_operation_key")
    if not isinstance(operation_key, str) or not _is_hash(operation_key):
        operation_key = currentness_operation_key_for(operation)
    return _sha256({"currentness_operation_key": operation_key})


def _operation_record_for(
    fields: Mapping[str, Any],
    payload: Mapping[str, Any],
    operation_key: str,
) -> dict[str, Any]:
    operation_occurrence_id = uuid5(
        NAMESPACE_URL,
        f"causal-delay-copilot:currentness-operation:{operation_key}",
    ).hex
    record: dict[str, Any] = {
        "schema_identifier": CURRENTNESS_OPERATION_SCHEMA_IDENTIFIER,
        "schema_version": CURRENTNESS_SCHEMA_VERSION,
        "operation_occurrence_id": operation_occurrence_id,
        "currentness_operation_key": operation_key,
        "currentness_policy_identifier_and_version": deepcopy(
            fields["currentness_policy_identifier_and_version"]
        ),
        "operation_kind": fields["operation_kind"],
        "evaluation_series_id": fields["evaluation_series_id"],
        "evaluation_occurrence_id": fields["evaluation_occurrence_id"],
        "evaluation_digest": fields["evaluation_digest"],
        "terminal_result_ref_and_hash": deepcopy(
            fields["terminal_result_ref_and_hash"]
        ),
        "recommendation_ref_and_hash_or_null": deepcopy(
            fields["recommendation_ref_and_hash_or_null"]
        ),
        "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
            fields["accepted_selection_claim_ref_and_hash_or_null"]
        ),
        "operation_payload_ref_and_hash": deepcopy(
            fields["operation_payload_ref_and_hash"]
        ),
        "currentness_checked_at": deepcopy(fields["currentness_checked_at"]),
        "operation_payload": deepcopy(dict(payload)),
    }
    record["content_hash"] = _hash_without_content_hash(record)
    return record


def _json_mapping(value: object, message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise DecisionSupportCurrentnessUnavailable(message) from error
    if not isinstance(parsed, Mapping):
        raise DecisionSupportCurrentnessUnavailable(message)
    return deepcopy(dict(parsed))


def _audit_locked(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
    idempotency_key: str,
    occurrence_kind: str,
    outcome_code: str,
    content_hash: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (
            workspace_id, occurrence_id, idempotency_key,
            occurrence_kind, outcome_code, content_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            occurrence_id,
            idempotency_key,
            occurrence_kind,
            outcome_code,
            content_hash,
            created_at,
        ),
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _head_projection(head: sqlite3.Row) -> dict[str, Any]:
    return {
        "evaluation_series_id": str(head["evaluation_series_id"]),
        "head_kind": str(head["head_kind"]),
        "head_occurrence_id": str(head["head_occurrence_id"]),
        "head_digest": str(head["head_digest"]),
        "head_result_hash": str(head["head_result_hash"]),
        "head_record_ref_and_hash": {
            "reference": str(head["head_occurrence_id"]),
            "content_hash": str(head["head_record_hash"]),
        },
    }


def _head_ref_and_hash(head: Mapping[str, Any]) -> dict[str, str]:
    reference = head.get("head_occurrence_id")
    content_hash = _mapping(head.get("head_record_ref_and_hash"))
    record_hash = None if content_hash is None else content_hash.get("content_hash")
    if not isinstance(reference, str) or not isinstance(record_hash, str):
        raise DecisionSupportCurrentnessUnavailable("authoritative head binding is invalid")
    return {"reference": reference, "content_hash": record_hash}


def _expected_evaluation_head(
    evaluation_row: sqlite3.Row,
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "evaluation_series_id": fields["evaluation_series_id"],
        "head_kind": "EVALUATION",
        "head_occurrence_id": fields["evaluation_occurrence_id"],
        "head_digest": fields["evaluation_digest"],
        "head_result_hash": fields["terminal_result_ref_and_hash"]["content_hash"],
        "head_record_ref_and_hash": {
            "reference": fields["evaluation_occurrence_id"],
            "content_hash": str(evaluation_row["content_hash"]),
        },
        "advice_state": "current",
        "current": True,
        "updated_at": str(evaluation_row["evaluation_published_at"]),
    }


def _historical_head_from_check(check: Mapping[str, Any]) -> dict[str, Any]:
    observed_ref = _mapping(check.get("observed_authoritative_head_ref_and_hash"))
    observed_kind = check.get("observed_authoritative_head_kind")
    observed_digest = check.get("observed_authoritative_head_digest")
    observed_result_hash = check.get("observed_authoritative_head_result_hash")
    updated_at = check.get("observed_authoritative_head_updated_at")
    if (
        observed_ref is None
        or not isinstance(observed_ref.get("reference"), str)
        or not isinstance(observed_ref.get("content_hash"), str)
        or not isinstance(observed_kind, str)
        or not isinstance(observed_digest, str)
        or not isinstance(observed_result_hash, str)
    ):
        raise DecisionSupportCurrentnessUnavailable(
            "stored currentness check lacks its observed head projection"
        )
    return {
        "schema_version": "decision-support-evaluation-series-head.v1",
        "evaluation_series_id": check["evaluation_series_id"],
        "head_kind": observed_kind,
        "head_occurrence_id": observed_ref["reference"],
        "head_digest": observed_digest,
        "head_result_hash": observed_result_hash,
        "head_record_ref_and_hash": deepcopy(dict(observed_ref)),
        "predecessor_occurrence_id": None,
        "advice_state": "current" if observed_kind == "EVALUATION" else "invalidated",
        "current": observed_kind == "EVALUATION",
        "updated_at": updated_at,
    }


def _recommendation_ref(result: Mapping[str, Any]) -> dict[str, str] | None:
    recommendation = _mapping(result.get("action_recommendation"))
    if recommendation is None:
        return None
    occurrence_id = recommendation.get("occurrence_id")
    content_hash = recommendation.get("content_hash")
    if not isinstance(occurrence_id, str) or not _is_hash(content_hash):
        raise DecisionSupportCurrentnessUnavailable(
            "stored Action Recommendation binding is invalid"
        )
    return {"reference": occurrence_id, "content_hash": content_hash}


def _same_ref(left: object, right: object) -> bool:
    return _canonical_json(left) == _canonical_json(right)


def _selection_claim_is_complete(
    claim: Mapping[str, Any],
    *,
    claim_ref: Mapping[str, Any],
    fields: Mapping[str, Any],
    payload: Mapping[str, Any],
    recommendation: Mapping[str, Any] | None,
) -> bool:
    """Validate the immutable selection claim without accepting a partial projection."""

    claim_hash = claim.get("content_hash")
    if (
        claim.get("schema_identifier") != "tradeoff-selection-claim"
        or claim.get("schema_version") != "1"
        or not isinstance(claim_hash, str)
        or not _is_hash(claim_hash)
        or _record_id(claim) != claim_ref.get("reference")
        or claim_hash != claim_ref.get("content_hash")
        or _record_content_hash(claim) != claim_hash
        or claim.get("evaluation_series_id") != fields["evaluation_series_id"]
        or claim.get("evaluation_occurrence_id") != fields["evaluation_occurrence_id"]
        or claim.get("evaluation_digest") != fields["evaluation_digest"]
        or not _same_ref(
            claim.get("terminal_result_ref_and_hash"),
            fields["terminal_result_ref_and_hash"],
        )
    ):
        return False

    selection_ref = _ref_and_hash(
        claim.get("tradeoff_selection_ref_and_hash")
        or claim.get("accepted_selection_ref_and_hash")
        or claim.get("selection_ref_and_hash")
    )
    candidate_ref = claim.get("selected_candidate_ref") or claim.get("candidate_ref")
    creation_operation_ref = _ref_and_hash(
        claim.get("creation_currentness_operation_ref_and_hash")
    )
    creation_check_ref = _ref_and_hash(
        claim.get("creation_currentness_check_ref_and_hash")
    )
    creation_checked_at = claim.get("creation_currentness_checked_at")
    if (
        selection_ref is None
        or not isinstance(candidate_ref, str)
        or not candidate_ref
        or creation_operation_ref is None
        or not creation_operation_ref["reference"].startswith("currentness-operation:")
        or creation_check_ref is None
        or not creation_check_ref["reference"].startswith("currentness-check:")
        or creation_checked_at is None
        or not _time_equal(claim.get("published_at"), creation_checked_at)
    ):
        return False

    payload_selection_ref = payload.get("tradeoff_selection_ref_and_hash") or payload.get(
        "accepted_selection_ref_and_hash"
    )
    if payload_selection_ref is not None and not _same_ref(
        selection_ref, payload_selection_ref
    ):
        return False
    payload_candidate_ref = payload.get("selected_candidate_ref")
    if payload_candidate_ref is not None and candidate_ref != payload_candidate_ref:
        return False

    if recommendation is None:
        return False
    recommendation_ref = _ref_and_hash(
        claim.get("action_recommendation_ref_and_hash")
        or claim.get("recommendation_ref_and_hash")
    )
    if recommendation_ref is None or not _same_ref(
        recommendation_ref,
        {
            "reference": recommendation.get("occurrence_id"),
            "content_hash": recommendation.get("content_hash"),
        },
    ):
        return False
    recommendation_key = recommendation.get("action_recommendation_key")
    if recommendation_key is not None:
        claim_key = claim.get("action_recommendation_key") or claim.get(
            "recommendation_key"
        )
        if claim_key != recommendation_key:
            return False
    return True


def _dependency_current(
    consumed: Mapping[str, Any],
    current: Mapping[str, Any] | None,
) -> bool | None:
    if current is None:
        return False
    kind = consumed.get("dependency_kind")
    if not isinstance(kind, str) or not kind:
        return None
    current_record = _mapping(current.get("current")) or current
    for key in ("id", "version", "content_hash"):
        if current_record.get(key) != consumed.get(key):
            return False
    optional_lifecycle_fields = (
        "applicable",
        "effective",
        "effective_successor",
        "fully_specified",
        "retired",
        "supported",
        "unique_unsuperseded_head",
        "superseded_by",
        "known_result",
        "satisfied_result",
        "supported_result",
    )
    for key in optional_lifecycle_fields:
        if key in consumed and key not in current_record:
            return None
    if current_record.get("superseded_by") not in (None, "NOT_APPLICABLE"):
        return False
    if current_record.get("effective_successor") not in (None, False, "NOT_APPLICABLE"):
        return False

    consumed_disposition = consumed.get("consumed_disposition")
    current_disposition = (
        current_record.get("disposition")
        or current_record.get("lifecycle_status")
        or current_record.get("review_status")
        or current_record.get("state")
        or current_record.get("outcome")
    )
    if not isinstance(consumed_disposition, str) or not isinstance(
        current_disposition, str
    ):
        return None

    def required_consumed_fields(*keys: str) -> bool:
        return all(key in consumed for key in keys)

    def current_bool(key: str) -> bool | None:
        value = current_record.get(key)
        return value if isinstance(value, bool) else None

    required_by_kind = {
        "INTERVENTION_LIBRARY_VERSION": (
            "unique_unsuperseded_head",
            "supported",
        ),
        "INTERVENTION_OPTION_VERSION": (
            "effective",
            "unique_unsuperseded_head",
        ),
        "DRIVER_ACTION_LINK_VERSION": (
            "effective",
            "unique_unsuperseded_head",
        ),
        "MONITORING_ESCALATION_TRIGGER_VERSION": (
            "effective",
            "unique_unsuperseded_head",
            "applicable",
        ),
        "ADVISORY_RUBRIC_VERSION": (
            "effective",
            "unique_unsuperseded_head",
            "applicable",
        ),
        "COMPOSITE_COMPATIBILITY_REVIEW_VERSION": (
            "effective",
            "unique_unsuperseded_head",
        ),
    }
    if kind in required_by_kind and not required_consumed_fields(
        *required_by_kind[kind]
    ):
        return None

    for key in (
        "applicable",
        "effective",
        "fully_specified",
        "retired",
        "supported",
        "unique_unsuperseded_head",
        "known_result",
        "satisfied_result",
        "supported_result",
    ):
        if key in consumed:
            consumed_value = consumed.get(key)
            current_value = current_bool(key)
            if not isinstance(consumed_value, bool) or current_value is None:
                return None
            if current_value is not consumed_value:
                return False

    if kind == "GOVERNED_VERSION_ENVELOPE":
        if current_disposition != consumed_disposition:
            return False
        if consumed.get("known_result") is True and current_disposition != "APPROVED":
            return False
        if consumed.get("known_result") is True or consumed.get("applicable") is True:
            if not required_consumed_fields("applicable"):
                return None
            if current_record.get("applicable") is not True:
                return False
        return True
    if kind == "INTERVENTION_LIBRARY_VERSION":
        if not required_consumed_fields("unique_unsuperseded_head", "supported"):
            return None
        unique_head = current_bool("unique_unsuperseded_head")
        supported = current_bool("supported")
        if unique_head is None or supported is None:
            return None
        if unique_head is False:
            return False
        if supported is False:
            return False
        return current_disposition == consumed_disposition
    if kind == "INTERVENTION_OPTION_VERSION":
        if not required_consumed_fields("effective"):
            return None
        effective = current_bool("effective")
        if effective is None:
            return None
        if effective is False:
            return False
        if consumed.get("supported_result") is True:
            return current_disposition == "ACTIVE"
        return current_disposition == consumed_disposition
    if kind == "DRIVER_ACTION_LINK_VERSION":
        if not required_consumed_fields("effective"):
            return None
        effective = current_bool("effective")
        if effective is None:
            return None
        if effective is False:
            return False
        if consumed.get("supported_result") is True:
            return current_disposition == "APPROVED"
        return current_disposition == consumed_disposition
    if kind == "MONITORING_ESCALATION_TRIGGER_VERSION":
        if not required_consumed_fields("effective"):
            return None
        effective = current_bool("effective")
        if effective is None:
            return None
        if effective is False:
            return False
        if consumed.get("supported_result") is True:
            if not required_consumed_fields("fully_specified", "retired"):
                return None
            fully_specified = current_bool("fully_specified")
            retired = current_bool("retired")
            if fully_specified is None or retired is None:
                return None
            return (
                current_disposition == "APPROVED"
                and fully_specified is True
                and retired is False
            )
        return current_disposition == consumed_disposition
    if kind == "ADVISORY_RUBRIC_VERSION":
        if not required_consumed_fields("effective"):
            return None
        effective = current_bool("effective")
        if effective is None:
            return None
        if effective is False:
            return False
        if consumed.get("known_result") is True:
            return current_disposition == "APPROVED"
        return current_disposition == consumed_disposition
    if kind == "COMPOSITE_COMPATIBILITY_REVIEW_VERSION":
        if not required_consumed_fields("effective"):
            return None
        effective = current_bool("effective")
        if effective is None:
            return None
        if effective is False:
            return False
        if consumed.get("satisfied_result") is True or consumed.get("known_result") is True:
            if not required_consumed_fields("fully_specified"):
                return None
            fully_specified = current_bool("fully_specified")
            if fully_specified is None:
                return None
            return current_disposition == "APPROVED"
        return current_disposition == consumed_disposition
    return None


def _operation_payload_error(
    operation: Mapping[str, Any],
    fields: Mapping[str, Any],
) -> str | None:
    payload = _mapping(operation.get("operation_payload"))
    if payload is None:
        return "currentness operation payload is unavailable"
    payload_hash = _record_content_hash(payload)
    expected_hash = fields["operation_payload_ref_and_hash"]["content_hash"]
    if payload_hash != expected_hash:
        return "currentness operation payload integrity does not match its binding"
    payload_reference = fields["operation_payload_ref_and_hash"]["reference"]
    identifiers = _payload_references(payload)
    identifiers.discard(None)
    if payload_reference not in identifiers:
        return "currentness operation payload reference does not match its record"
    available_at = payload.get("available_at")
    if not _time_equal(available_at, fields["currentness_checked_at"]):
        return "currentness operation time is not the payload availability time"
    return None


def _operation_payload_shape_error(
    operation: Mapping[str, Any],
    fields: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> str | None:
    operation_kind = fields["operation_kind"]
    if operation_kind == "CURRENT_ADVICE_RENDER":
        try:
            request_fields = _render_request_key_fields(payload)
        except DecisionSupportCurrentnessUnavailable:
            return "current-advice render request payload is invalid"
        for key in (
            "evaluation_series_id",
            "evaluation_occurrence_id",
            "evaluation_digest",
            "terminal_result_ref_and_hash",
            "recommendation_ref_and_hash_or_null",
            "accepted_selection_claim_ref_and_hash_or_null",
        ):
            if not _same_ref(request_fields.get(key), fields.get(key)):
                return "currentness operation is not bound to its render request"
        chain_kind = request_fields["advice_chain_kind"]
        recommendation = request_fields["recommendation_ref_and_hash_or_null"]
        selection_claim = request_fields[
            "accepted_selection_claim_ref_and_hash_or_null"
        ]
        if chain_kind == "EVALUATION_ONLY_NO_RECOMMENDATION" and (
            recommendation is not None or selection_claim is not None
        ):
            return "evaluation-only advice render cannot carry a recommendation or claim"
        if chain_kind == "IMMEDIATE_EVALUATION_RECOMMENDATION" and (
            recommendation is None or selection_claim is not None
        ):
            return "immediate advice render has an invalid recommendation cardinality"
        if chain_kind == "ACCEPTED_TRADEOFF_SELECTION" and (
            recommendation is None or selection_claim is None
        ):
            return "accepted trade-off advice render has an invalid claim cardinality"
        if chain_kind == "ACCEPTED_TRADEOFF_SELECTION":
            return (
                "accepted trade-off advice render requires the downstream immutable "
                "selection-claim resolver"
            )
        return None
    if operation_kind not in {
        "TRADEOFF_SELECTION_ACCEPTANCE",
        "MANAGER_AUTHORIZATION",
        "MONITORING_TRIGGER_MATCH",
    }:
        return "currentness operation kind is unsupported"
    expected_payload_schema = {
        "TRADEOFF_SELECTION_ACCEPTANCE": "tradeoff-selection-delivery-attempt",
        "MANAGER_AUTHORIZATION": "manager-authorization-attempt",
        "MONITORING_TRIGGER_MATCH": "monitoring-observation",
    }[operation_kind]
    if (
        payload.get("schema_identifier") != expected_payload_schema
        or payload.get("schema_version") != "1"
        or not isinstance(_record_id(payload), str)
        or not isinstance(payload.get("content_hash"), str)
        or _record_content_hash(payload) != payload.get("content_hash")
    ):
        return "currentness operation payload occurrence is not immutable"
    for key in (
        "evaluation_series_id",
        "evaluation_occurrence_id",
        "evaluation_digest",
    ):
        if payload.get(key) != fields[key]:
            return "currentness operation is not bound to its evaluation"
    if not _same_ref(
        payload.get("terminal_result_ref_and_hash"),
        fields["terminal_result_ref_and_hash"],
    ):
        return "currentness operation is not bound to its terminal result"
    if not _same_ref(
        payload.get(
            "recommendation_ref_and_hash",
            payload.get("recommendation_ref_and_hash_or_null"),
        ),
        fields["recommendation_ref_and_hash_or_null"],
    ):
        return "currentness operation is not bound to its recommendation"
    if not _same_ref(
        payload.get(
            "accepted_selection_claim_ref_and_hash",
            payload.get("accepted_selection_claim_ref_and_hash_or_null"),
        ),
        fields["accepted_selection_claim_ref_and_hash_or_null"],
    ):
        return "currentness operation is not bound to its selection claim"
    if payload.get("available_at") is None:
        return "currentness operation availability time is missing"
    if operation_kind == "TRADEOFF_SELECTION_ACCEPTANCE":
        if not isinstance(payload.get("tradeoff_selection_ref_and_hash"), Mapping):
            return "trade-off selection reference is missing"
        if not isinstance(payload.get("selected_candidate_ref"), str):
            return "selected trade-off candidate reference is missing"
        if payload.get("selection_available_at") is None or payload.get("delivered_at") is None:
            return "trade-off selection chronology is incomplete"
    elif operation_kind == "MANAGER_AUTHORIZATION":
        payload_recommendation = payload.get(
            "recommendation_ref_and_hash",
            payload.get("recommendation_ref_and_hash_or_null"),
        )
        if not isinstance(payload_recommendation, Mapping):
            return "manager authorization recommendation reference is missing"
        if not isinstance(_record_id(payload), str):
            return "manager authorization attempt reference is missing"
        if payload.get("advice_chain_published_at") is None or payload.get("requested_at") is None:
            return "manager authorization chronology is incomplete"
    else:
        payload_recommendation = payload.get(
            "recommendation_ref_and_hash",
            payload.get("recommendation_ref_and_hash_or_null"),
        )
        if not isinstance(payload_recommendation, Mapping):
            return "monitoring recommendation reference is missing"
        if not isinstance(_record_id(payload), str):
            return "monitoring observation reference is missing"
        if payload.get("monitoring_activated_at") is None or payload.get("observed_at") is None:
            return "monitoring observation chronology is incomplete"
        if payload.get("trigger_id_and_version") is None:
            return "monitoring trigger identity is missing"
        if payload.get("match_outcome", "NO_REVIEW_REQUEST") != "NO_REVIEW_REQUEST":
            return "Core 31 does not publish monitoring review requests"
    return None


def _payload_references(payload: Mapping[str, Any]) -> set[str]:
    record_id = _record_id(payload)
    schema_identifier = payload.get("schema_identifier")
    identifiers = {
        record_id,
        payload.get("render_request_ref"),
        payload.get("selection_ref"),
        payload.get("tradeoff_selection_ref"),
        payload.get("tradeoff_selection_attempt_ref"),
        payload.get("authorization_attempt_ref"),
        payload.get("manager_authorization_attempt_ref"),
        payload.get("selected_candidate_ref"),
        payload.get("observation_ref"),
        payload.get("monitoring_observation_ref"),
    }
    render_request_occurrence_id = payload.get("render_request_occurrence_id")
    if isinstance(render_request_occurrence_id, str) and render_request_occurrence_id:
        identifiers.add(f"current-advice-render-request:{render_request_occurrence_id}")
    if isinstance(record_id, str) and isinstance(schema_identifier, str):
        identifiers.add(f"{schema_identifier}:{record_id}")
    identifiers.discard(None)
    return {str(identifier) for identifier in identifiers}


def _chain_errors(
    *,
    operation: Mapping[str, Any],
    fields: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    result: Mapping[str, Any],
) -> list[str]:
    payload = _mapping(operation.get("operation_payload"))
    if payload is None:
        return ["CURRENTNESS_COMPARISON_UNRESOLVED"]
    errors: list[str] = []
    operation_kind = fields["operation_kind"]
    if payload.get("evaluation_series_id") != fields["evaluation_series_id"]:
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    if payload.get("evaluation_occurrence_id") != fields["evaluation_occurrence_id"]:
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    if payload.get("evaluation_digest") != fields["evaluation_digest"]:
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    if not _same_ref(payload.get("terminal_result_ref_and_hash"), fields["terminal_result_ref_and_hash"]):
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")

    recommendation = _recommendation_ref(result)
    recommendation_record = _mapping(result.get("action_recommendation"))
    if not _same_ref(
        fields["recommendation_ref_and_hash_or_null"], recommendation
    ):
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")

    selection_claim_ref = fields["accepted_selection_claim_ref_and_hash_or_null"]
    selection_claim = _mapping(operation.get("accepted_selection_claim"))
    if selection_claim_ref is None:
        if selection_claim is not None:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    elif selection_claim is None:
        errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    else:
        claim_record_ref = _record_id(selection_claim)
        claim_record_hash = _record_content_hash(selection_claim)
        if (
            claim_record_ref != selection_claim_ref["reference"]
            or claim_record_hash != selection_claim_ref["content_hash"]
            or not _selection_claim_is_complete(
                selection_claim,
                claim_ref=selection_claim_ref,
                fields=fields,
                payload=payload,
                recommendation=recommendation_record,
            )
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")

    checked_at = fields["currentness_checked_at"]
    available_at = payload.get("available_at")
    if not _time_equal(checked_at, available_at):
        errors.append("CURRENTNESS_COMPARISON_UNRESOLVED")

    if operation_kind == "CURRENT_ADVICE_RENDER":
        if payload.get("render_mode") != "CURRENT_ADVICE":
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        chain_kind = payload.get("advice_chain_kind")
        chain_published_at = payload.get("advice_chain_published_at")
        requested_at = payload.get("requested_at")
        if (
            _time_compare(chain_published_at, requested_at) is None
            or _time_compare(requested_at, available_at) is None
        ):
            errors.append("CURRENTNESS_COMPARISON_UNRESOLVED")
        elif _time_compare(chain_published_at, requested_at) > 0 or _time_compare(
            requested_at, available_at
        ) > 0:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        evaluation_published_at = evaluation.get("evaluation_published_at")
        if chain_kind in {
            "EVALUATION_ONLY_NO_RECOMMENDATION",
            "IMMEDIATE_EVALUATION_RECOMMENDATION",
        } and not _time_equal(chain_published_at, evaluation_published_at):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if chain_kind == "EVALUATION_ONLY_NO_RECOMMENDATION":
            if result.get("outcome") not in {
                "NO_ELIGIBLE_OPTION",
                "TRADEOFF_REQUIRES_MANAGER_CHOICE",
            }:
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
            if recommendation is not None or fields["accepted_selection_claim_ref_and_hash_or_null"] is not None:
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        elif chain_kind == "IMMEDIATE_EVALUATION_RECOMMENDATION":
            if result.get("outcome") != "RECOMMENDATION_AVAILABLE" or recommendation is None:
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
            if fields["accepted_selection_claim_ref_and_hash_or_null"] is not None:
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
            if not _same_ref(
                payload.get("recommendation_ref_and_hash_or_null"), recommendation
            ):
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        elif chain_kind == "ACCEPTED_TRADEOFF_SELECTION":
            claim = _mapping(operation.get("accepted_selection_claim"))
            if (
                result.get("outcome") != "TRADEOFF_REQUIRES_MANAGER_CHOICE"
                or recommendation is None
                or fields["accepted_selection_claim_ref_and_hash_or_null"] is None
                or claim is None
            ):
                errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
            else:
                claim_hash = _record_content_hash(claim)
                claim_ref = _record_id(claim)
                expected_claim = fields["accepted_selection_claim_ref_and_hash_or_null"]
                if claim_hash != expected_claim["content_hash"] or claim_ref != expected_claim["reference"]:
                    errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
                if not _time_equal(chain_published_at, claim.get("published_at")):
                    errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        else:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    elif operation_kind == "TRADEOFF_SELECTION_ACCEPTANCE":
        if payload.get("selected_candidate_ref") is None:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if (
            _time_compare(payload.get("selection_available_at"), payload.get("delivered_at"))
            is None
            or _time_compare(payload.get("delivered_at"), available_at) is None
        ):
            errors.append("CURRENTNESS_COMPARISON_UNRESOLVED")
        elif _time_compare(payload.get("selection_available_at"), payload.get("delivered_at")) > 0 or _time_compare(
            payload.get("delivered_at"), available_at
        ) > 0:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if fields["recommendation_ref_and_hash_or_null"] is not None or fields[
            "accepted_selection_claim_ref_and_hash_or_null"
        ] is not None:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    elif operation_kind == "MANAGER_AUTHORIZATION":
        if payload.get("requested_disposition") != "APPROVE":
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if recommendation is None:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if not isinstance(payload.get("manager_actor_ref"), str) or not payload.get(
            "manager_actor_ref"
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        recommendation_record = _mapping(result.get("action_recommendation"))
        selection_basis = (
            None
            if recommendation_record is None
            else recommendation_record.get("selection_basis")
        )
        if (
            selection_basis == "MANAGER_TRADEOFF_SELECTION"
            and selection_claim_ref is None
        ) or (
            selection_basis != "MANAGER_TRADEOFF_SELECTION"
            and selection_claim_ref is not None
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if (
            _time_compare(payload.get("advice_chain_published_at"), payload.get("requested_at"))
            is None
            or _time_compare(payload.get("requested_at"), available_at) is None
        ):
            errors.append("CURRENTNESS_COMPARISON_UNRESOLVED")
        elif _time_compare(payload.get("advice_chain_published_at"), payload.get("requested_at")) > 0 or _time_compare(
            payload.get("requested_at"), available_at
        ) > 0:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if selection_claim is not None and not _time_equal(
            payload.get("advice_chain_published_at"), selection_claim.get("published_at")
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    elif operation_kind == "MONITORING_TRIGGER_MATCH":
        observation_ref = payload.get("observation_ref") or _record_id(payload)
        if not isinstance(observation_ref, str) or not observation_ref:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        recommendation_record = _mapping(result.get("action_recommendation"))
        selection_basis = (
            None
            if recommendation_record is None
            else recommendation_record.get("selection_basis")
        )
        if (
            selection_basis == "MANAGER_TRADEOFF_SELECTION"
            and selection_claim_ref is None
        ) or (
            selection_basis != "MANAGER_TRADEOFF_SELECTION"
            and selection_claim_ref is not None
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if (
            _time_compare(payload.get("monitoring_activated_at"), payload.get("observed_at"))
            is None
            or _time_compare(payload.get("observed_at"), available_at) is None
        ):
            errors.append("CURRENTNESS_COMPARISON_UNRESOLVED")
        elif _time_compare(payload.get("monitoring_activated_at"), payload.get("observed_at")) > 0 or _time_compare(
            payload.get("observed_at"), available_at
        ) > 0:
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
        if selection_claim is not None and not _time_equal(
            payload.get("advice_chain_published_at"), selection_claim.get("published_at")
        ):
            errors.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
    return errors


def _render_request_key_fields(request: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "render_mode",
        "evaluation_series_id",
        "evaluation_occurrence_id",
        "evaluation_digest",
        "terminal_result_ref_and_hash",
        "advice_chain_kind",
        "recommendation_ref_and_hash_or_null",
        "accepted_selection_claim_ref_and_hash_or_null",
        "advice_chain_published_at",
        "requested_at",
        "available_at",
    )
    allowed = set(required) | {
        "schema_identifier",
        "schema_identifier_and_version",
        "schema_version",
        "render_request_occurrence_id",
        "current_advice_render_request_key",
        "content_hash",
    }
    if set(request).difference(allowed):
        raise DecisionSupportCurrentnessUnavailable(
            "current-advice render request contains unsupported fields"
        )
    if request.get("schema_identifier") != CURRENT_ADVICE_RENDER_REQUEST_SCHEMA_IDENTIFIER:
        raise DecisionSupportCurrentnessUnavailable("render request schema is unsupported")
    if request.get("schema_version") != CURRENTNESS_SCHEMA_VERSION:
        raise DecisionSupportCurrentnessUnavailable("render request schema version is unsupported")
    if request.get("render_mode") != "CURRENT_ADVICE":
        raise DecisionSupportCurrentnessUnavailable("render mode is unsupported")
    if request.get("advice_chain_kind") not in {
        "EVALUATION_ONLY_NO_RECOMMENDATION",
        "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "ACCEPTED_TRADEOFF_SELECTION",
    }:
        raise DecisionSupportCurrentnessUnavailable("advice chain kind is unsupported")
    if any(key not in request for key in required):
        raise DecisionSupportCurrentnessUnavailable("render request is incomplete")
    if not isinstance(request.get("evaluation_series_id"), str) or not request.get(
        "evaluation_series_id"
    ):
        raise DecisionSupportCurrentnessUnavailable("render request series is invalid")
    if not isinstance(request.get("evaluation_occurrence_id"), str) or not request.get(
        "evaluation_occurrence_id"
    ):
        raise DecisionSupportCurrentnessUnavailable("render request evaluation is invalid")
    if not _is_hash(request.get("evaluation_digest")):
        raise DecisionSupportCurrentnessUnavailable("render request evaluation digest is invalid")
    terminal = _ref_and_hash(request.get("terminal_result_ref_and_hash"))
    if terminal is None:
        raise DecisionSupportCurrentnessUnavailable("render request terminal result binding is invalid")
    recommendation = request.get("recommendation_ref_and_hash_or_null")
    if recommendation is not None:
        recommendation = _ref_and_hash(recommendation)
        if recommendation is None:
            raise DecisionSupportCurrentnessUnavailable("render request recommendation binding is invalid")
    claim = request.get("accepted_selection_claim_ref_and_hash_or_null")
    if claim is not None:
        claim = _ref_and_hash(claim)
        if claim is None:
            raise DecisionSupportCurrentnessUnavailable("render request selection claim binding is invalid")
    for key in ("advice_chain_published_at", "requested_at", "available_at"):
        _canonical_time(request.get(key))
    return {
        "schema_identifier_and_version": {
            "identifier": CURRENT_ADVICE_RENDER_REQUEST_SCHEMA_IDENTIFIER,
            "version": CURRENTNESS_SCHEMA_VERSION,
        },
        "render_mode": request["render_mode"],
        "evaluation_series_id": request["evaluation_series_id"],
        "evaluation_occurrence_id": request["evaluation_occurrence_id"],
        "evaluation_digest": request["evaluation_digest"],
        "terminal_result_ref_and_hash": terminal,
        "advice_chain_kind": request["advice_chain_kind"],
        "recommendation_ref_and_hash_or_null": recommendation,
        "accepted_selection_claim_ref_and_hash_or_null": claim,
        "advice_chain_published_at": deepcopy(request["advice_chain_published_at"]),
        "requested_at": deepcopy(request["requested_at"]),
        "available_at": deepcopy(request["available_at"]),
    }


def current_advice_render_request_key_for(request: Mapping[str, Any]) -> str:
    return _sha256(_render_request_key_fields(request))


def _render_request_record_hash(request: Mapping[str, Any]) -> str:
    return _hash_without_content_hash(request)


def _render_request_record_for(request: Mapping[str, Any]) -> dict[str, Any]:
    fields = _render_request_key_fields(request)
    request_key = _sha256(fields)
    occurrence_id = uuid5(
        NAMESPACE_URL,
        f"causal-delay-copilot:current-advice-render-request:{request_key}",
    ).hex
    record: dict[str, Any] = {
        "schema_identifier": CURRENT_ADVICE_RENDER_REQUEST_SCHEMA_IDENTIFIER,
        "schema_version": CURRENTNESS_SCHEMA_VERSION,
        "render_request_occurrence_id": occurrence_id,
        "current_advice_render_request_key": request_key,
        **deepcopy(fields),
    }
    record["content_hash"] = _render_request_record_hash(record)
    return record


def current_advice_render_result_key_for(
    render_request_ref_and_hash: Mapping[str, Any],
    currentness_operation_ref_and_hash: Mapping[str, Any],
    currentness_check_ref_and_hash: Mapping[str, Any],
) -> str:
    return _sha256(
        {
            "render_request_ref_and_hash": deepcopy(dict(render_request_ref_and_hash)),
            "currentness_operation_ref_and_hash": deepcopy(
                dict(currentness_operation_ref_and_hash)
            ),
            "currentness_check_ref_and_hash": deepcopy(dict(currentness_check_ref_and_hash)),
        }
    )


class DecisionSupportCurrentnessMixin:
    """Persist one operation-bound currentness proof for the exact evaluation head."""

    def _currentness_connection(self) -> sqlite3.Connection:
        connection = self._connection_or_raise()  # type: ignore[attr-defined]
        ensure_currentness_schema(connection, create=False)
        return connection

    def _currentness_operation_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored currentness operation is invalid",
        )
        if (
            record.get("schema_identifier") != CURRENTNESS_OPERATION_SCHEMA_IDENTIFIER
            or record.get("schema_version") != CURRENTNESS_SCHEMA_VERSION
            or record.get("operation_occurrence_id") != str(row["operation_occurrence_id"])
            or record.get("currentness_operation_key") != str(row["currentness_operation_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
            or record.get("operation_kind") != str(row["operation_kind"])
            or record.get("evaluation_series_id") != str(row["evaluation_series_id"])
            or record.get("evaluation_occurrence_id")
            != str(row["evaluation_occurrence_id"])
            or record.get("evaluation_digest") != str(row["evaluation_digest"])
            or not _same_ref(
                record.get("terminal_result_ref_and_hash"),
                {
                    "reference": str(row["terminal_result_ref"]),
                    "content_hash": str(row["terminal_result_hash"]),
                },
            )
            or not _same_ref(
                record.get("operation_payload_ref_and_hash"),
                {
                    "reference": str(row["operation_payload_ref"]),
                    "content_hash": str(row["operation_payload_hash"]),
                },
            )
            or _canonical_json(record.get("currentness_checked_at"))
            != str(row["currentness_checked_at"])
        ):
            raise DecisionSupportCurrentnessUnavailable("stored currentness operation failed integrity")
        return record

    def _currentness_check_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored currentness check is invalid",
        )
        if (
            record.get("schema_identifier") != CURRENTNESS_CHECK_SCHEMA_IDENTIFIER
            or record.get("schema_version") != CURRENTNESS_SCHEMA_VERSION
            or record.get("currentness_check_occurrence_id")
            != str(row["currentness_check_occurrence_id"])
            or record.get("currentness_check_key") != str(row["currentness_check_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
            or record.get("currentness_operation_key")
            != str(row["currentness_operation_key"])
            or record.get("currentness_outcome") != str(row["currentness_outcome"])
            or record.get("currentness_evidence_digest")
            != str(row["currentness_evidence_digest"])
            or _canonical_json(record.get("currentness_checked_at"))
            != str(row["currentness_checked_at"])
        ):
            raise DecisionSupportCurrentnessUnavailable("stored currentness check failed integrity")
        return record

    def _currentness_claim_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored currentness terminal claim is invalid",
        )
        consuming_ref = _mapping(record.get("consuming_result_ref_and_hash"))
        if (
            record.get("currentness_operation_key") != str(row["currentness_operation_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
            or record.get("currentness_check_key") != str(row["currentness_check_key"])
            or (_mapping(record.get("terminal_currentness_ref_and_hash")) or {}).get(
                "reference"
            )
            != str(row["terminal_currentness_ref"])
            or (_mapping(record.get("terminal_currentness_ref_and_hash")) or {}).get(
                "content_hash"
            )
            != str(row["terminal_currentness_hash"])
            or record.get("currentness_outcome") != str(row["currentness_outcome"])
            or record.get("consuming_result_kind") != str(row["consuming_result_kind"])
            or (
                consuming_ref is None
                and (
                    row["consuming_result_ref"] is not None
                    or row["consuming_result_hash"] is not None
                )
            )
            or (
                consuming_ref is not None
                and (
                    consuming_ref.get("reference") != row["consuming_result_ref"]
                    or consuming_ref.get("content_hash") != row["consuming_result_hash"]
                )
            )
        ):
            raise DecisionSupportCurrentnessUnavailable("stored currentness terminal claim failed integrity")
        return record

    def _render_request_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored current-advice render request is invalid",
        )
        if (
            record.get("schema_identifier") != CURRENT_ADVICE_RENDER_REQUEST_SCHEMA_IDENTIFIER
            or record.get("schema_version") != CURRENTNESS_SCHEMA_VERSION
            or record.get("render_request_occurrence_id") != str(row["render_request_occurrence_id"])
            or record.get("current_advice_render_request_key")
            != str(row["current_advice_render_request_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _render_request_record_hash(record) != str(row["content_hash"])
            or record.get("evaluation_series_id") != str(row["evaluation_series_id"])
            or record.get("evaluation_occurrence_id")
            != str(row["evaluation_occurrence_id"])
            or _canonical_json(record.get("available_at"))
            != str(row["available_at"])
        ):
            raise DecisionSupportCurrentnessUnavailable("stored current-advice render request failed integrity")
        return record

    def _render_result_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored current-advice render result is invalid",
        )
        if (
            record.get("schema_identifier") != CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER
            or record.get("schema_version") != CURRENTNESS_SCHEMA_VERSION
            or record.get("render_result_occurrence_id") != str(row["render_result_occurrence_id"])
            or record.get("current_advice_render_result_key")
            != str(row["current_advice_render_result_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
            or (_mapping(record.get("render_request_ref_and_hash")) or {}).get(
                "reference"
            )
            != str(row["render_request_ref"])
            or (_mapping(record.get("render_request_ref_and_hash")) or {}).get(
                "content_hash"
            )
            != str(row["render_request_hash"])
            or (_mapping(record.get("currentness_check_ref_and_hash")) or {}).get(
                "reference"
            )
            != str(row["currentness_check_ref"])
            or (_mapping(record.get("currentness_check_ref_and_hash")) or {}).get(
                "content_hash"
            )
            != str(row["currentness_check_hash"])
        ):
            raise DecisionSupportCurrentnessUnavailable("stored current-advice render result failed integrity")
        return record

    def _consuming_result_from_row(
        self,
        row: sqlite3.Row,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        record = _json_mapping(
            row["payload_json"],
            "stored currentness consuming result is invalid",
        )
        operation_ref = _mapping(record.get("currentness_operation_ref_and_hash"))
        check_ref = _mapping(record.get("currentness_check_ref_and_hash"))
        result_kind = str(row["consuming_result_kind"])
        expected_operation_kind = {
            value: key
            for key, value in CURRENTNESS_CONSUMING_RESULT_BY_OPERATION_KIND.items()
        }.get(result_kind)
        valid_monitoring_outcomes = {"NO_REVIEW_REQUEST"}
        if (
            record.get("schema_identifier") != result_kind
            or record.get("schema_version") != CURRENTNESS_CONSUMING_RESULT_SCHEMA_VERSION
            or record.get("consuming_result_occurrence_id")
            != str(row["consuming_result_occurrence_id"])
            or record.get("consuming_result_key") != str(row["consuming_result_key"])
            or record.get("content_hash") != str(row["content_hash"])
            or _hash_without_content_hash(record) != str(row["content_hash"])
            or record.get("currentness_operation_key")
            != str(row["currentness_operation_key"])
            or operation_ref is None
            or check_ref is None
            or check_ref.get("reference") != str(row["currentness_check_ref"])
            or check_ref.get("content_hash") != str(row["currentness_check_hash"])
            or expected_operation_kind is None
            or record.get("operation_kind") != expected_operation_kind
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "stored currentness consuming result failed integrity"
            )
        if not _is_hash(operation_ref.get("content_hash")) or not str(
            operation_ref.get("reference", "")
        ).startswith("currentness-operation:"):
            raise DecisionSupportCurrentnessUnavailable(
                "stored currentness consuming result has an invalid operation binding"
            )
        if connection is not None:
            operation_row = connection.execute(
                """
                SELECT operation_occurrence_id, content_hash
                FROM decision_support_currentness_operations
                WHERE workspace_id = ? AND currentness_operation_key = ?
                """,
                (row["workspace_id"], row["currentness_operation_key"]),
            ).fetchone()
            if operation_row is None or not _same_ref(
                operation_ref,
                {
                    "reference": f"currentness-operation:{operation_row['operation_occurrence_id']}",
                    "content_hash": str(operation_row["content_hash"]),
                },
            ):
                raise DecisionSupportCurrentnessUnavailable(
                    "stored currentness consuming result is not bound to its operation"
                )
        if result_kind == "tradeoff-selection-result":
            if (
                record.get("selection_result") != "CURRENTNESS_PROVEN_AT_CHECK"
                or not isinstance(record.get("selected_candidate_ref"), str)
                or record.get("selection_side_effect")
                != "DEFERRED_TO_TRADEOFF_SELECTION_CONTRACT"
            ):
                raise DecisionSupportCurrentnessUnavailable(
                    "stored trade-off consuming result failed its closed contract"
                )
        elif result_kind == "authorization-currentness-result":
            if (
                record.get("authorization_currentness") != "PROVEN"
                or not isinstance(record.get("manager_actor_ref"), str)
                or record.get("manager_decision") != "NOT_RECORDED_BY_CORE_31"
            ):
                raise DecisionSupportCurrentnessUnavailable(
                    "stored authorization consuming result failed its closed contract"
                )
        elif result_kind == "monitoring-match-result":
            if record.get("match_outcome") not in valid_monitoring_outcomes:
                raise DecisionSupportCurrentnessUnavailable(
                    "stored monitoring consuming result has an unsupported outcome"
                )
            if record.get("monitoring_review_request_ref_and_hash") is not None:
                raise DecisionSupportCurrentnessUnavailable(
                    "Core 31 cannot own a monitoring review request"
                )
        return record

    def _currentness_head_locked(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> tuple[sqlite3.Row, dict[str, Any]] | None:
        row = connection.execute(
            """
            SELECT * FROM decision_support_evaluation_heads
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        ).fetchone()
        if row is None:
            return None
        validated = self._validated_head_read_model(connection, row)  # type: ignore[attr-defined]
        return row, validated

    def register_decision_support_currentness_source(
        self,
        workspace_id: str,
        *,
        payload: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Register one upstream typed occurrence before it can consume advice."""

        if not isinstance(payload, Mapping):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness source occurrence is invalid"
            )
        record = deepcopy(dict(payload))
        schema_identifier = record.get("schema_identifier")
        if schema_identifier not in CURRENTNESS_SOURCE_SCHEMAS:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness source occurrence schema is unsupported"
            )
        if record.get("schema_version") != CURRENTNESS_SCHEMA_VERSION:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness source occurrence schema version is unsupported"
            )
        occurrence_id = _record_id(record)
        supplied_hash = record.get("content_hash")
        if (
            not isinstance(occurrence_id, str)
            or not occurrence_id
            or not isinstance(supplied_hash, str)
            or not _is_hash(supplied_hash)
            or _record_content_hash(record) != supplied_hash
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness source occurrence integrity is invalid"
            )
        try:
            _canonical_time(record.get("available_at"))
            _canonical_json(record)
        except (TypeError, ValueError, OverflowError) as error:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness source occurrence is not canonical"
            ) from error
        created_at = _timestamp(now or datetime.now(timezone.utc))
        with self._lock:  # type: ignore[attr-defined]
            connection = self._currentness_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT occurrence_kind, outcome_code, content_hash
                    FROM audit_events
                    WHERE workspace_id = ? AND occurrence_id = ?
                    """,
                    (workspace_id, occurrence_id),
                ).fetchone()
                if existing is None:
                    _audit_locked(
                        connection,
                        workspace_id=workspace_id,
                        occurrence_id=occurrence_id,
                        idempotency_key=(
                            "decision-support-currentness-source:"
                            f"{schema_identifier}:{occurrence_id}"
                        ),
                        occurrence_kind=CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_KIND,
                        outcome_code=CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_OUTCOME,
                        content_hash=supplied_hash,
                        created_at=created_at,
                    )
                elif (
                    str(existing["occurrence_kind"])
                    != CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_KIND
                    or str(existing["outcome_code"])
                    != CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_OUTCOME
                    or str(existing["content_hash"]) != supplied_hash
                ):
                    raise DecisionSupportCurrentnessConflict(
                        "currentness source occurrence was reused with different content"
                    )
                connection.commit()
                return record
            except (
                DecisionSupportCurrentnessConflict,
                DecisionSupportCurrentnessUnavailable,
            ):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise DecisionSupportCurrentnessConflict from error
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportCurrentnessUnavailable from error
            except Exception:
                connection.rollback()
                raise

    def _require_authoritative_operation_payload_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation_kind: str,
        payload: Mapping[str, Any],
        payload_ref: Mapping[str, Any],
    ) -> None:
        occurrence_id = _record_id(payload)
        if occurrence_id is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation payload occurrence is unavailable"
            )
        if operation_kind == "CURRENT_ADVICE_RENDER":
            expected_kind = "DECISION_SUPPORT_CURRENT_ADVICE_RENDER_REQUEST"
            expected_outcome = "CURRENT_ADVICE"
        else:
            expected_kind = CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_KIND
            expected_outcome = CURRENTNESS_SOURCE_OCCURRENCE_AUDIT_OUTCOME
        row = connection.execute(
            """
            SELECT occurrence_kind, outcome_code, content_hash
            FROM audit_events
            WHERE workspace_id = ? AND occurrence_id = ?
            """,
            (workspace_id, occurrence_id),
        ).fetchone()
        if (
            row is None
            or str(row["occurrence_kind"]) != expected_kind
            or str(row["outcome_code"]) != expected_outcome
            or str(row["content_hash"]) != str(payload_ref["content_hash"])
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation payload is not an authoritative source occurrence"
            )

    def _normalize_operation(
        self,
        operation: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        if not isinstance(operation, Mapping):
            raise DecisionSupportCurrentnessUnavailable("currentness operation is invalid")
        fields = _key_fields(operation)
        payload = _mapping(operation.get("operation_payload"))
        if payload is None:
            raise DecisionSupportCurrentnessUnavailable("currentness operation payload is invalid")
        payload = deepcopy(dict(payload))
        payload_hash = _record_content_hash(payload)
        if payload_hash != fields["operation_payload_ref_and_hash"]["content_hash"]:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation payload hash does not match its reference"
            )
        payload_ref = fields["operation_payload_ref_and_hash"]["reference"]
        if payload_ref not in _payload_references(payload):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation payload reference does not match its record"
            )
        payload_error = _operation_payload_error(operation, fields)
        if payload_error is not None:
            raise DecisionSupportCurrentnessUnavailable(payload_error)
        payload_shape_error = _operation_payload_shape_error(
            operation,
            fields,
            payload,
        )
        if payload_shape_error is not None:
            raise DecisionSupportCurrentnessUnavailable(payload_shape_error)
        if not _time_equal(payload.get("available_at"), fields["currentness_checked_at"]):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation time is not the payload availability time"
            )
        key = currentness_operation_key_for(fields)
        supplied_key = operation.get("currentness_operation_key")
        if supplied_key != key:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation key does not match its deterministic tuple"
            )
        check_key = currentness_check_key_for({**fields, "currentness_operation_key": key})
        expected_record = _operation_record_for(fields, payload, key)
        supplied_occurrence_id = operation.get("operation_occurrence_id")
        if supplied_occurrence_id != expected_record["operation_occurrence_id"]:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation occurrence does not match its deterministic key"
            )
        supplied_content_hash = operation.get("content_hash")
        if supplied_content_hash != expected_record["content_hash"]:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation content hash does not match its immutable envelope"
            )
        return fields, payload, key, check_key

    def _claim_operation_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        fields: Mapping[str, Any],
        payload: Mapping[str, Any],
        operation_key: str,
        check_key: str,
        now: str,
    ) -> dict[str, Any]:
        existing = connection.execute(
            """
            SELECT * FROM decision_support_currentness_operations
            WHERE workspace_id = ? AND currentness_operation_key = ?
            """,
            (workspace_id, operation_key),
        ).fetchone()
        if existing is not None:
            record = self._currentness_operation_from_row(existing)
            if (
                record.get("operation_kind") != fields["operation_kind"]
                or record.get("evaluation_series_id") != fields["evaluation_series_id"]
                or record.get("evaluation_occurrence_id") != fields["evaluation_occurrence_id"]
                or record.get("evaluation_digest") != fields["evaluation_digest"]
                or not _same_ref(
                    record.get("terminal_result_ref_and_hash"),
                    fields["terminal_result_ref_and_hash"],
                )
                or not _same_ref(
                    record.get("recommendation_ref_and_hash_or_null"),
                    fields["recommendation_ref_and_hash_or_null"],
                )
                or not _same_ref(
                    record.get("accepted_selection_claim_ref_and_hash_or_null"),
                    fields["accepted_selection_claim_ref_and_hash_or_null"],
                )
                or not _same_ref(
                    record.get("operation_payload_ref_and_hash"),
                    fields["operation_payload_ref_and_hash"],
                )
                or not _time_equal(record.get("currentness_checked_at"), fields["currentness_checked_at"])
            ):
                raise DecisionSupportCurrentnessConflict(
                    "currentness operation key was reused with different content"
                )
            return record

        record = _operation_record_for(fields, payload, operation_key)
        operation_occurrence_id = str(record["operation_occurrence_id"])
        content_hash = str(record["content_hash"])
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=operation_occurrence_id,
            idempotency_key=f"decision-support-currentness-operation:{operation_key}",
            occurrence_kind="DECISION_SUPPORT_CURRENTNESS_OPERATION",
            outcome_code=str(fields["operation_kind"]),
            content_hash=content_hash,
            created_at=now,
        )
        ref = fields["terminal_result_ref_and_hash"]
        recommendation = fields["recommendation_ref_and_hash_or_null"]
        claim = fields["accepted_selection_claim_ref_and_hash_or_null"]
        payload_ref = fields["operation_payload_ref_and_hash"]
        connection.execute(
            """
            INSERT INTO decision_support_currentness_operations (
                operation_occurrence_id, workspace_id, currentness_operation_key,
                content_hash, operation_kind, evaluation_series_id,
                evaluation_occurrence_id, evaluation_digest, terminal_result_ref,
                terminal_result_hash, recommendation_ref, recommendation_hash,
                selection_claim_ref, selection_claim_hash, operation_payload_ref,
                operation_payload_hash, currentness_checked_at, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operation_occurrence_id,
                workspace_id,
                operation_key,
                content_hash,
                fields["operation_kind"],
                fields["evaluation_series_id"],
                fields["evaluation_occurrence_id"],
                fields["evaluation_digest"],
                ref["reference"],
                ref["content_hash"],
                None if recommendation is None else recommendation["reference"],
                None if recommendation is None else recommendation["content_hash"],
                None if claim is None else claim["reference"],
                None if claim is None else claim["content_hash"],
                payload_ref["reference"],
                payload_ref["content_hash"],
                _canonical_json(fields["currentness_checked_at"]),
                now,
                _canonical_json(record),
            ),
        )
        return record

    def _claim_render_request_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        render_request: Mapping[str, Any],
        now: str,
    ) -> dict[str, Any]:
        fields = _render_request_key_fields(render_request)
        request_key = _sha256(fields)
        expected_record = _render_request_record_for(render_request)
        supplied_request_key = render_request.get("current_advice_render_request_key")
        supplied_occurrence_id = render_request.get("render_request_occurrence_id")
        supplied_content_hash = render_request.get("content_hash")
        if supplied_request_key is not None and supplied_request_key != request_key:
            raise DecisionSupportCurrentnessUnavailable(
                "render request key does not match its deterministic tuple"
            )
        if supplied_occurrence_id is not None and supplied_occurrence_id != expected_record[
            "render_request_occurrence_id"
        ]:
            raise DecisionSupportCurrentnessUnavailable(
                "render request occurrence does not match its deterministic key"
            )
        if supplied_content_hash is not None and supplied_content_hash != expected_record[
            "content_hash"
        ]:
            raise DecisionSupportCurrentnessUnavailable(
                "render request content hash does not match its immutable record"
            )
        existing = connection.execute(
            """
            SELECT * FROM decision_support_current_advice_render_requests
            WHERE workspace_id = ? AND current_advice_render_request_key = ?
            """,
            (workspace_id, request_key),
        ).fetchone()
        if existing is not None:
            record = self._render_request_from_row(existing)
            if record != expected_record:
                raise DecisionSupportCurrentnessConflict(
                    "render request key was reused with different content"
                )
            return record

        record = expected_record
        occurrence_id = str(record["render_request_occurrence_id"])
        payload_hash = str(record["content_hash"])
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            idempotency_key=f"decision-support-current-advice-render-request:{request_key}",
            occurrence_kind="DECISION_SUPPORT_CURRENT_ADVICE_RENDER_REQUEST",
            outcome_code="CURRENT_ADVICE",
            content_hash=payload_hash,
            created_at=now,
        )
        terminal = fields["terminal_result_ref_and_hash"]
        connection.execute(
            """
            INSERT INTO decision_support_current_advice_render_requests (
                render_request_occurrence_id, workspace_id,
                current_advice_render_request_key, content_hash,
                evaluation_series_id, evaluation_occurrence_id, available_at,
                created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                workspace_id,
                request_key,
                payload_hash,
                fields["evaluation_series_id"],
                fields["evaluation_occurrence_id"],
                _canonical_json(fields["available_at"]),
                now,
                _canonical_json(record),
            ),
        )
        return record

    def _load_evaluation_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        evaluation_series_id: str,
        evaluation_occurrence_id: str,
        evaluation_digest: str | None = None,
        terminal_binding: Mapping[str, Any] | None = None,
    ) -> tuple[sqlite3.Row, dict[str, Any], dict[str, Any]]:
        row = connection.execute(
            """
            SELECT * FROM decision_support_evaluations
            WHERE workspace_id = ? AND evaluation_series_id = ?
              AND evaluation_occurrence_id = ?
            """,
            (workspace_id, evaluation_series_id, evaluation_occurrence_id),
        ).fetchone()
        if row is None:
            raise DecisionSupportCurrentnessUnavailable("evaluation occurrence is unavailable")
        evaluation = self._evaluation_from_row(row)  # type: ignore[attr-defined]
        terminal = _mapping(evaluation.get("terminal_result"))
        if terminal is None:
            raise DecisionSupportCurrentnessUnavailable("evaluation terminal result is unavailable")
        if terminal.get("decision_support_evaluation_id") != evaluation_occurrence_id:
            raise DecisionSupportCurrentnessUnavailable("evaluation terminal identity is invalid")
        if terminal.get("decision_support_evaluation_series_id") != evaluation_series_id:
            raise DecisionSupportCurrentnessUnavailable("evaluation terminal series is invalid")
        if evaluation_digest is not None and str(row["evaluation_digest"]) != evaluation_digest:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation evaluation digest is not the stored digest"
            )
        if terminal.get("content_hash") != str(row["result_hash"]):
            raise DecisionSupportCurrentnessUnavailable("evaluation terminal hash is invalid")
        stored_terminal_binding = {
            "reference": f"decision-support-result:{evaluation_occurrence_id}",
            "content_hash": str(row["result_hash"]),
        }
        if terminal_binding is not None and not _same_ref(
            terminal_binding, stored_terminal_binding
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation terminal result is not the exact stored result"
            )
        permission = _mapping(terminal.get("permission"))
        if permission is None or permission.get("decision_support_evaluation_permitted") is not True:
            raise DecisionSupportCurrentnessUnavailable("evaluation permission is not current")
        return row, evaluation, terminal

    def _validate_bound_operation_locked(
        self,
        *,
        operation: Mapping[str, Any],
        fields: Mapping[str, Any],
        evaluation: Mapping[str, Any],
        terminal_result: Mapping[str, Any],
    ) -> None:
        chain_reasons = _chain_errors(
            operation=operation,
            fields=fields,
            evaluation=evaluation,
            result=terminal_result,
        )
        if chain_reasons:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness operation advice chain is not intrinsically valid"
            )

    def _frozen_currentness_metadata(
        self,
        evaluation: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], object]:
        identity_binding = _mapping(evaluation.get("identity_binding")) or {}
        terminal = _mapping(evaluation.get("terminal_result"))
        metadata_source = deepcopy(dict(evaluation))
        if terminal is not None:
            for key in (
                "advice_currentness_dependency_set",
                "consumed_operational_horizons",
                "advice_valid_through",
                "advice_currentness_metadata_state",
            ):
                if key in terminal:
                    metadata_source[key] = deepcopy(terminal[key])
        metadata_state = _mapping(metadata_source.get("advice_currentness_metadata_state"))
        if metadata_state is None or metadata_state.get("state") != "COMPLETE":
            raise DecisionSupportCurrentnessUnavailable(
                "stored advice currentness metadata is incomplete"
            )
        return _currentness_metadata(metadata_source, identity_binding)

    def _currentness_context(
        self,
        *,
        evaluation: Mapping[str, Any],
        context: Mapping[str, Any] | None,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        object,
    ]:
        dependencies, horizons, advice_valid_through = self._frozen_currentness_metadata(
            evaluation
        )
        supplied = _mapping(context) or {}
        current_dependencies_value = supplied.get("governed_dependency_resolutions")
        if current_dependencies_value is None:
            # A frozen consumed dependency is not a live resolution. Missing
            # authority must therefore fail closed through the dependency
            # predicate instead of silently proving the dependency current.
            current_dependencies = []
        else:
            current_dependencies = _ordered_dependencies(current_dependencies_value)
        current_horizons_value = supplied.get("operational_horizons")
        if current_horizons_value is None:
            current_horizons = horizons
        else:
            current_horizons = _ordered_horizons(current_horizons_value)
            if _canonical_json(current_horizons) != _canonical_json(horizons):
                raise DecisionSupportCurrentnessUnavailable(
                    "current operational horizons do not match the frozen advice inputs"
                )
        current_horizon = advice_valid_through
        supplied_horizon = supplied.get("advice_valid_through")
        if supplied_horizon is not None and _canonical_json(supplied_horizon) != _canonical_json(
            advice_valid_through
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "current advice horizon does not match the frozen advice horizon"
            )
        if _canonical_json(current_horizon) != _canonical_json(_minimum_horizon(current_horizons)):
            raise DecisionSupportCurrentnessUnavailable(
                "current advice horizon does not match its consumed input set"
            )
        return (
            dependencies,
            current_dependencies,
            horizons,
            current_horizons,
            deepcopy(current_horizon),
        )

    def _replace_currentness_authority_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        evaluation_series_id: str,
        dependencies: object,
        updated_at: str,
    ) -> None:
        """Replace one server-owned per-series dependency resolution projection."""

        ensure_currentness_schema(connection, create=False)
        ordered = _ordered_dependencies(dependencies)
        connection.execute(
            """
            DELETE FROM decision_support_currentness_authorities
            WHERE workspace_id = ? AND evaluation_series_id = ?
            """,
            (workspace_id, evaluation_series_id),
        )
        for dependency in ordered:
            connection.execute(
                """
                INSERT INTO decision_support_currentness_authorities (
                    workspace_id, evaluation_series_id, dependency_kind,
                    dependency_id, dependency_version, content_hash,
                    updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    evaluation_series_id,
                    dependency["dependency_kind"],
                    dependency["id"],
                    dependency["version"],
                    dependency["content_hash"],
                    updated_at,
                    _canonical_json(dependency),
                ),
            )
        authority_digest = _sha256(
            {
                "evaluation_series_id": evaluation_series_id,
                "dependencies": ordered,
            }
        )
        authority_occurrence_id = uuid5(
            NAMESPACE_URL,
            "causal-delay-copilot:currentness-authority:"
            f"{workspace_id}:{evaluation_series_id}:{authority_digest}",
        ).hex
        existing_audit = connection.execute(
            """
            SELECT content_hash, occurrence_kind, outcome_code
            FROM audit_events
            WHERE workspace_id = ? AND occurrence_id = ?
            """,
            (workspace_id, authority_occurrence_id),
        ).fetchone()
        if existing_audit is None:
            _audit_locked(
                connection,
                workspace_id=workspace_id,
                occurrence_id=authority_occurrence_id,
                idempotency_key=(
                    "decision-support-currentness-authority:"
                    f"{evaluation_series_id}:{authority_digest}"
                ),
                occurrence_kind=CURRENTNESS_AUTHORITY_AUDIT_KIND,
                outcome_code=CURRENTNESS_AUTHORITY_AUDIT_OUTCOME,
                content_hash=authority_digest,
                created_at=updated_at,
            )
        elif (
            str(existing_audit["content_hash"]) != authority_digest
            or str(existing_audit["occurrence_kind"]) != CURRENTNESS_AUTHORITY_AUDIT_KIND
            or str(existing_audit["outcome_code"]) != CURRENTNESS_AUTHORITY_AUDIT_OUTCOME
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness authority audit binding is inconsistent"
            )

    def publish_decision_support_currentness_authority(
        self,
        workspace_id: str,
        *,
        evaluation_series_id: str,
        dependencies: object,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Publish the server-owned current dependency projection for one series."""

        if not isinstance(evaluation_series_id, str) or not evaluation_series_id:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness authority series is invalid"
            )
        ordered = _ordered_dependencies(dependencies)
        updated_at = _timestamp(now or datetime.now(timezone.utc))
        with self._lock:  # type: ignore[attr-defined]
            connection = self._currentness_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._replace_currentness_authority_locked(
                    connection,
                    workspace_id=workspace_id,
                    evaluation_series_id=evaluation_series_id,
                    dependencies=ordered,
                    updated_at=updated_at,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return deepcopy(ordered)

    def _stored_currentness_authority(
        self,
        connection: sqlite3.Connection,
        evaluation: Mapping[str, Any],
        *,
        workspace_id: str,
        evaluation_series_id: str,
    ) -> dict[str, Any]:
        """Resolve the server-owned live dependency projection for one series."""

        consumed_dependencies, _, _ = self._frozen_currentness_metadata(evaluation)
        rows = connection.execute(
            """
            SELECT * FROM decision_support_currentness_authorities
            WHERE workspace_id = ? AND evaluation_series_id = ?
            ORDER BY dependency_kind, dependency_id, dependency_version
            """,
            (workspace_id, evaluation_series_id),
        ).fetchall()
        current_dependencies: list[dict[str, Any]] = []
        for row in rows:
            dependency = _json_mapping(
                row["payload_json"],
                "stored currentness authority is invalid",
            )
            ordered = _ordered_dependencies([dependency])
            if (
                len(ordered) != 1
                or ordered[0]["dependency_kind"] != str(row["dependency_kind"])
                or ordered[0]["id"] != str(row["dependency_id"])
                or ordered[0]["version"] != str(row["dependency_version"])
                or ordered[0]["content_hash"] != str(row["content_hash"])
            ):
                raise DecisionSupportCurrentnessUnavailable(
                    "stored currentness authority failed integrity"
                )
            current_dependencies.append(ordered[0])
        current_dependencies = _ordered_dependencies(current_dependencies)
        authority_digest = _sha256(
            {
                "evaluation_series_id": evaluation_series_id,
                "dependencies": current_dependencies,
            }
        )
        authority_occurrence_id = uuid5(
            NAMESPACE_URL,
            "causal-delay-copilot:currentness-authority:"
            f"{workspace_id}:{evaluation_series_id}:{authority_digest}",
        ).hex
        authority_audit = connection.execute(
            """
            SELECT content_hash, occurrence_kind, outcome_code
            FROM audit_events
            WHERE workspace_id = ? AND occurrence_id = ?
            """,
            (workspace_id, authority_occurrence_id),
        ).fetchone()
        if (
            authority_audit is None
            or str(authority_audit["content_hash"]) != authority_digest
            or str(authority_audit["occurrence_kind"]) != CURRENTNESS_AUTHORITY_AUDIT_KIND
            or str(authority_audit["outcome_code"]) != CURRENTNESS_AUTHORITY_AUDIT_OUTCOME
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "currentness authority is unavailable or not authoritative"
            )
        if consumed_dependencies and not current_dependencies:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness authority has no live dependency resolutions"
            )
        return {"governed_dependency_resolutions": current_dependencies}

    def _dependency_reasons(
        self,
        *,
        consumed: list[Mapping[str, Any]],
        current: list[Mapping[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        current_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
        duplicate_identities: set[tuple[str, str, str]] = set()
        for item in current:
            identity = (
                str(item.get("dependency_kind")),
                str(item.get("id") or item.get("reference")),
                str(item.get("version")),
            )
            if identity in current_by_identity:
                duplicate_identities.add(identity)
                continue
            current_by_identity[identity] = item
        reasons: list[str] = []
        offending: list[dict[str, Any]] = []
        if duplicate_identities:
            reasons.append("CURRENTNESS_COMPARISON_UNRESOLVED")
            offending.extend(
                deepcopy(
                    [
                        dict(item)
                        for item in current
                        if (
                            str(item.get("dependency_kind")),
                            str(item.get("id") or item.get("reference")),
                            str(item.get("version")),
                        )
                        in duplicate_identities
                    ]
                )
            )
        for dependency in consumed:
            identity = (
                str(dependency.get("dependency_kind")),
                str(dependency.get("id") or dependency.get("reference")),
                str(dependency.get("version")),
            )
            status = _dependency_current(dependency, current_by_identity.get(identity))
            if status is not True:
                reasons.append("GOVERNED_DEPENDENCY_NOT_CURRENT")
                offending.append(deepcopy(dict(dependency)))
        return reasons, offending

    def _horizon_reasons(
        self,
        *,
        currentness_checked_at: object,
        advice_valid_through: object,
        horizons: list[Mapping[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        reasons: list[str] = []
        offending: list[dict[str, Any]] = []
        if advice_valid_through != "NO_EXPIRY":
            comparison = _time_compare(currentness_checked_at, advice_valid_through)
            if comparison is None:
                reasons.append("CURRENTNESS_COMPARISON_UNRESOLVED")
                offending.extend(deepcopy([dict(item) for item in horizons]))
            elif comparison > 0:
                reasons.append("OPERATIONAL_FACT_EXPIRED")
                offending.extend(deepcopy([dict(item) for item in horizons]))
        for horizon in horizons:
            valid_through = horizon.get("valid_through")
            if valid_through == "NO_EXPIRY":
                continue
            comparison = _time_compare(currentness_checked_at, valid_through)
            if comparison is None:
                if "CURRENTNESS_COMPARISON_UNRESOLVED" not in reasons:
                    reasons.append("CURRENTNESS_COMPARISON_UNRESOLVED")
                offending.append(deepcopy(dict(horizon)))
            elif comparison > 0:
                if "OPERATIONAL_FACT_EXPIRED" not in reasons:
                    reasons.append("OPERATIONAL_FACT_EXPIRED")
                offending.append(deepcopy(dict(horizon)))
        return reasons, offending

    def _write_currentness_check_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        operation_key: str,
        check_key: str,
        outcome: str,
        expected_head: Mapping[str, Any],
        observed_head: Mapping[str, Any],
        advice_valid_through: object,
        dependencies: list[Mapping[str, Any]],
        horizons: list[Mapping[str, Any]],
        reasons: list[str],
        created_at: str,
    ) -> dict[str, Any]:
        operation_ref = {
            "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
            "content_hash": operation["content_hash"],
        }
        predecessor = {
            "occurrence_id": expected_head["head_occurrence_id"],
            "digest": expected_head["head_digest"],
            "result_hash": expected_head["head_result_hash"],
        }
        observed = {
            "head_kind": observed_head.get("head_kind"),
            "head_ref_and_hash": _head_ref_and_hash(observed_head),
        }
        ordered_reasons = sorted(
            dict.fromkeys(reasons),
            key=lambda reason: (CURRENTNESS_REASON_PRIORITY.get(reason, 999), reason),
        )
        evidence_payload = {
            "currentness_policy_identifier_and_version": deepcopy(
                operation["currentness_policy_identifier_and_version"]
            ),
            "operation_kind": operation["operation_kind"],
            "currentness_operation_ref_and_hash": operation_ref,
            "evaluation_series_id": operation["evaluation_series_id"],
            "predecessor_head_occurrence_id": predecessor["occurrence_id"],
            "predecessor_head_digest": predecessor["digest"],
            "predecessor_result_hash": predecessor["result_hash"],
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                operation["accepted_selection_claim_ref_and_hash_or_null"]
            ),
            "observed_authoritative_head_kind_and_ref_and_hash": observed,
            "currentness_checked_at": deepcopy(operation["currentness_checked_at"]),
            "advice_valid_through": deepcopy(advice_valid_through),
            "ordered_governed_dependency_resolutions": deepcopy(
                [dict(item) for item in dependencies]
            ),
            "ordered_consumed_operational_horizons": deepcopy(
                [dict(item) for item in horizons]
            ),
            "currentness_outcome": outcome,
            "ordered_currentness_reasons": ordered_reasons,
        }
        evidence_digest = _sha256(evidence_payload)
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:currentness-check:{check_key}",
        ).hex
        record: dict[str, Any] = {
            "schema_identifier": CURRENTNESS_CHECK_SCHEMA_IDENTIFIER,
            "schema_version": CURRENTNESS_SCHEMA_VERSION,
            "currentness_check_occurrence_id": occurrence_id,
            "currentness_check_key": check_key,
            "currentness_operation_key": operation_key,
            "currentness_operation_ref_and_hash": operation_ref,
            "operation_kind": operation["operation_kind"],
            "evaluation_series_id": operation["evaluation_series_id"],
            "evaluation_occurrence_id": operation["evaluation_occurrence_id"],
            "evaluation_head_ref_and_hash": _head_ref_and_hash(expected_head),
            "observed_authoritative_head_ref_and_hash": _head_ref_and_hash(observed_head),
            "observed_authoritative_head_kind": observed_head.get("head_kind"),
            "observed_authoritative_head_digest": observed_head.get("head_digest"),
            "observed_authoritative_head_result_hash": observed_head.get(
                "head_result_hash"
            ),
            "observed_authoritative_head_updated_at": observed_head.get("updated_at"),
            "currentness_checked_at": deepcopy(operation["currentness_checked_at"]),
            "advice_valid_through": deepcopy(advice_valid_through),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                operation["accepted_selection_claim_ref_and_hash_or_null"]
            ),
            "ordered_governed_dependency_resolutions": deepcopy(
                [dict(item) for item in dependencies]
            ),
            "ordered_consumed_operational_horizons": deepcopy(
                [dict(item) for item in horizons]
            ),
            "currentness_outcome": outcome,
            "ordered_currentness_reasons": ordered_reasons,
            "currentness_evidence_digest": evidence_digest,
        }
        record["content_hash"] = _hash_without_content_hash(record)
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            idempotency_key=f"decision-support-currentness-check:{check_key}",
            occurrence_kind="DECISION_SUPPORT_CURRENTNESS_CHECK",
            outcome_code=outcome,
            content_hash=str(record["content_hash"]),
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO decision_support_currentness_checks (
                currentness_check_occurrence_id, workspace_id,
                currentness_check_key, currentness_operation_key, content_hash,
                currentness_outcome, currentness_checked_at,
                currentness_evidence_digest, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                workspace_id,
                check_key,
                operation_key,
                record["content_hash"],
                outcome,
                _canonical_json(operation["currentness_checked_at"]),
                evidence_digest,
                created_at,
                _canonical_json(record),
            ),
        )
        return record

    def _write_render_result_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        check: Mapping[str, Any],
        render_request: Mapping[str, Any],
        evaluation: Mapping[str, Any],
        terminal_result: Mapping[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        request_ref = {
            "reference": f"current-advice-render-request:{render_request['render_request_occurrence_id']}",
            "content_hash": render_request["content_hash"],
        }
        operation_ref = {
            "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
            "content_hash": operation["content_hash"],
        }
        check_ref = {
            "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
            "content_hash": check["content_hash"],
        }
        result_key = current_advice_render_result_key_for(
            request_ref,
            operation_ref,
            check_ref,
        )
        existing = connection.execute(
            """
            SELECT * FROM decision_support_current_advice_render_results
            WHERE workspace_id = ? AND current_advice_render_result_key = ?
            """,
            (workspace_id, result_key),
        ).fetchone()
        if existing is not None:
            return self._render_result_from_row(existing)
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:current-advice-render-result:{result_key}",
        ).hex
        projection = deepcopy(dict(terminal_result))
        projection.pop("content_hash", None)
        record: dict[str, Any] = {
            "schema_identifier": CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER,
            "schema_version": CURRENTNESS_SCHEMA_VERSION,
            "render_result_occurrence_id": occurrence_id,
            "current_advice_render_result_key": result_key,
            "render_request_ref_and_hash": request_ref,
            "evaluation_result_ref_and_hash": deepcopy(
                render_request["terminal_result_ref_and_hash"]
            ),
            "advice_chain_kind": render_request["advice_chain_kind"],
            "recommendation_ref_and_hash_or_null": deepcopy(
                render_request["recommendation_ref_and_hash_or_null"]
            ),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                render_request["accepted_selection_claim_ref_and_hash_or_null"]
            ),
            "advice_chain": projection,
            "current_as_of": deepcopy(operation["currentness_checked_at"]),
            "currentness_operation_ref_and_hash": operation_ref,
            "currentness_check_ref_and_hash": check_ref,
        }
        record["content_hash"] = _hash_without_content_hash(record)
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            idempotency_key=f"decision-support-current-advice-render-result:{result_key}",
            occurrence_kind="DECISION_SUPPORT_CURRENT_ADVICE_RENDER",
            outcome_code="CURRENTNESS_PROVEN_AT_CHECK",
            content_hash=str(record["content_hash"]),
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO decision_support_current_advice_render_results (
                render_result_occurrence_id, workspace_id,
                current_advice_render_result_key, content_hash,
                render_request_ref, render_request_hash,
                currentness_check_ref, currentness_check_hash,
                created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                workspace_id,
                result_key,
                record["content_hash"],
                request_ref["reference"],
                request_ref["content_hash"],
                check_ref["reference"],
                check_ref["content_hash"],
                created_at,
                _canonical_json(record),
            ),
        )
        return record

    def _write_currentness_consuming_result_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        check: Mapping[str, Any],
        terminal_result: Mapping[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        operation_kind = str(operation["operation_kind"])
        result_kind = CURRENTNESS_CONSUMING_RESULT_BY_OPERATION_KIND.get(operation_kind)
        if result_kind is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness consuming result kind is unsupported"
            )
        operation_ref = {
            "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
            "content_hash": operation["content_hash"],
        }
        check_ref = {
            "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
            "content_hash": check["content_hash"],
        }
        payload = _mapping(operation.get("operation_payload"))
        if payload is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness consuming payload is unavailable"
            )
        recommendation = _recommendation_ref(terminal_result)
        claim = operation["accepted_selection_claim_ref_and_hash_or_null"]
        payload_ref = operation["operation_payload_ref_and_hash"]
        if operation_kind == "MANAGER_AUTHORIZATION":
            result_key_fields = {
                "authorization_attempt_ref_and_hash": deepcopy(dict(payload_ref)),
                "recommendation_ref_and_hash": deepcopy(recommendation),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(claim),
                "manager_actor_ref": payload.get("manager_actor_ref"),
                "currentness_operation_ref_and_hash": operation_ref,
                "currentness_check_ref_and_hash": check_ref,
            }
        elif operation_kind == "MONITORING_TRIGGER_MATCH":
            match_outcome = payload.get("match_outcome", "NO_REVIEW_REQUEST")
            if match_outcome != "NO_REVIEW_REQUEST":
                raise DecisionSupportCurrentnessUnavailable(
                    "Core 31 does not publish monitoring review requests"
                )
            result_key_fields = {
                "recommendation_ref_and_hash": deepcopy(recommendation),
                "trigger_id_and_version": deepcopy(
                    payload.get("trigger_id_and_version")
                ),
                "monitoring_observation_key": payload.get(
                    "monitoring_observation_key", payload_ref["reference"]
                ),
                "monitoring_observation_ref_and_hash": deepcopy(dict(payload_ref)),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(claim),
                "currentness_operation_ref_and_hash": operation_ref,
                "currentness_check_ref_and_hash": check_ref,
                "match_outcome": match_outcome,
                "monitoring_review_request_key_or_null": None,
            }
        else:
            result_key_fields = {
                "tradeoff_selection_attempt_ref_and_hash": deepcopy(dict(payload_ref)),
                "currentness_operation_ref_and_hash": operation_ref,
                "currentness_check_ref_and_hash": check_ref,
                "selection_result": "CURRENTNESS_PROVEN_AT_CHECK",
            }
        result_key = _sha256(result_key_fields)
        existing = connection.execute(
            """
            SELECT * FROM decision_support_currentness_consuming_results
            WHERE workspace_id = ? AND consuming_result_key = ?
            """,
            (workspace_id, result_key),
        ).fetchone()
        if existing is not None:
            return self._consuming_result_from_row(existing, connection=connection)
        occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:{result_kind}:{result_key}",
        ).hex
        record: dict[str, Any] = {
            "schema_identifier": result_kind,
            "schema_version": CURRENTNESS_CONSUMING_RESULT_SCHEMA_VERSION,
            "consuming_result_occurrence_id": occurrence_id,
            "consuming_result_key": result_key,
            "currentness_operation_key": operation["currentness_operation_key"],
            "operation_kind": operation_kind,
            "currentness_operation_ref_and_hash": operation_ref,
            "currentness_check_ref_and_hash": check_ref,
            "evaluation_series_id": operation["evaluation_series_id"],
            "evaluation_occurrence_id": operation["evaluation_occurrence_id"],
            "evaluation_digest": operation["evaluation_digest"],
            "terminal_result_ref_and_hash": deepcopy(
                operation["terminal_result_ref_and_hash"]
            ),
            "recommendation_ref_and_hash_or_null": deepcopy(recommendation),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(claim),
            "operation_payload_ref_and_hash": deepcopy(dict(payload_ref)),
            "current_as_of": deepcopy(operation["currentness_checked_at"]),
            "result_key_fields": result_key_fields,
        }
        if operation_kind == "TRADEOFF_SELECTION_ACCEPTANCE":
            record.update(
                {
                    "selection_result": "CURRENTNESS_PROVEN_AT_CHECK",
                    "selection_side_effect": "DEFERRED_TO_TRADEOFF_SELECTION_CONTRACT",
                    "selected_candidate_ref": deepcopy(payload.get("selected_candidate_ref")),
                }
            )
        elif operation_kind == "MANAGER_AUTHORIZATION":
            record.update(
                {
                    "authorization_currentness": "PROVEN",
                    "manager_actor_ref": payload.get("manager_actor_ref"),
                    "manager_decision": "NOT_RECORDED_BY_CORE_31",
                }
            )
        else:
            record.update(
                {
                    "match_outcome": payload.get("match_outcome", "NO_REVIEW_REQUEST"),
                    "monitoring_review_request_ref_and_hash": None,
                }
            )
        record["content_hash"] = _hash_without_content_hash(record)
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            idempotency_key=f"decision-support-currentness-result:{result_key}",
            occurrence_kind="DECISION_SUPPORT_CURRENTNESS_CONSUMING_RESULT",
            outcome_code="CURRENTNESS_PROVEN_AT_CHECK",
            content_hash=str(record["content_hash"]),
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO decision_support_currentness_consuming_results (
                consuming_result_occurrence_id, workspace_id,
                consuming_result_key, consuming_result_kind,
                currentness_operation_key, currentness_check_ref,
                currentness_check_hash, content_hash, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                workspace_id,
                result_key,
                result_kind,
                operation["currentness_operation_key"],
                check_ref["reference"],
                check_ref["content_hash"],
                record["content_hash"],
                created_at,
                _canonical_json(record),
            ),
        )
        return record

    def _write_currentness_invalidation_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        check: Mapping[str, Any],
        predecessor: sqlite3.Row,
        reasons: list[str],
        offending: list[Mapping[str, Any]],
        advice_valid_through: object,
        created_at: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        ordered_reasons = sorted(
            dict.fromkeys(reasons),
            key=lambda reason: (CURRENTNESS_REASON_PRIORITY.get(reason, 999), reason),
        )
        primary_reason = ordered_reasons[0]
        currentness_invalidation_digest = _sha256(
            {
                "evaluation_series_id": operation["evaluation_series_id"],
                "predecessor_head_occurrence_id": str(predecessor["head_occurrence_id"]),
                "predecessor_head_digest": str(predecessor["head_digest"]),
                "predecessor_head_result_hash": str(predecessor["head_result_hash"]),
                "evaluation_ref_and_hash": deepcopy(
                    operation["terminal_result_ref_and_hash"]
                ),
                "recommendation_ref_and_hash_or_null": deepcopy(
                    operation["recommendation_ref_and_hash_or_null"]
                ),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                    operation["accepted_selection_claim_ref_and_hash_or_null"]
                ),
                "operation_kind": operation["operation_kind"],
                "currentness_operation_ref_and_hash": {
                    "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
                    "content_hash": operation["content_hash"],
                },
                "currentness_checked_at": deepcopy(operation["currentness_checked_at"]),
                "prior_advice_valid_through": deepcopy(advice_valid_through),
                "ordered_currentness_reasons": ordered_reasons,
                "offending_dependencies_or_horizons": deepcopy(
                    [dict(item) for item in offending]
                ),
                "currentness_evidence_digest": check["currentness_evidence_digest"],
            }
        )
        invalidation_occurrence_id = uuid5(
            NAMESPACE_URL,
            f"causal-delay-copilot:currentness-invalidation:{operation['currentness_operation_key']}",
        ).hex
        predecessor_ref = {
            "reference": str(predecessor["head_occurrence_id"]),
            "content_hash": str(predecessor["head_record_hash"]),
        }
        invalidation_result: dict[str, Any] = {
            "schema_version": "decision-support-boundary.v1",
            "outcome": "FAILED",
            "state": "unavailable",
            "primary_reason_code": "DECISION_SUPPORT_ADVICE_NOT_CURRENT",
            "reason": (
                "The exact Decision Support advice chain could not be proven current "
                "at the operation's authoritative availability time."
            ),
            "next_step": "Request a fresh permission-true evaluation and retry the exact operation.",
            "permission": {
                "decision_support_evaluation_permitted": True,
                "denial_reason_code": None,
                "reason": "The upstream permission was not changed by this currentness check.",
                "next_step": "Restore current governed evidence before using advice.",
            },
            "decision_support_evaluation_id": operation["evaluation_occurrence_id"],
            "decision_support_evaluation_series_id": operation["evaluation_series_id"],
            "decision_support_invalidation": {
                "schema_identifier": CURRENTNESS_INVALIDATION_SCHEMA_IDENTIFIER,
                "schema_version": CURRENTNESS_SCHEMA_VERSION,
                "invalidation_kind": "ADVICE_CURRENTNESS_INVALIDATION",
                "invalidation_occurrence_id": invalidation_occurrence_id,
                "predecessor_head_occurrence_id": str(predecessor["head_occurrence_id"]),
                "predecessor_head_digest": str(predecessor["head_digest"]),
                "predecessor_head_result_hash": str(predecessor["head_result_hash"]),
                "invalidated_artifact_ref_and_hash": predecessor_ref,
                "evaluation_ref_and_hash": deepcopy(
                    operation["terminal_result_ref_and_hash"]
                ),
                "recommendation_ref_and_hash_or_null": deepcopy(
                    operation["recommendation_ref_and_hash_or_null"]
                ),
                "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                    operation["accepted_selection_claim_ref_and_hash_or_null"]
                ),
                "operation_kind": operation["operation_kind"],
                "authoritative_invalidation_ref_and_hash": {
                    "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
                    "content_hash": check["content_hash"],
                },
                "currentness_operation_ref_and_hash": {
                    "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
                    "content_hash": operation["content_hash"],
                },
                "currentness_check_ref_and_hash": {
                    "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
                    "content_hash": check["content_hash"],
                },
                "currentness_checked_at": deepcopy(operation["currentness_checked_at"]),
                "prior_advice_valid_through": deepcopy(advice_valid_through),
                "ordered_currentness_reasons": ordered_reasons,
                "primary_currentness_reason": primary_reason,
                "offending_dependencies_or_horizons": deepcopy(
                    [dict(item) for item in offending]
                ),
                "currentness_evidence_digest": check["currentness_evidence_digest"],
                "invalidation_digest": currentness_invalidation_digest,
            },
            "options": [],
            "action_recommendation": None,
            "tradeoff": None,
            "monitoring": {"state": "NOT_AVAILABLE"},
            "drafting": {"state": "NOT_PERMITTED"},
            "authorization": {"state": "NOT_PERMITTED"},
            "consumed_inputs": [],
        }
        invalidation_result["content_hash"] = _sha256(invalidation_result)
        record: dict[str, Any] = {
            "schema_identifier": "decision-support-invalidation",
            "schema_version": "1",
            "invalidation_occurrence_id": invalidation_occurrence_id,
            "evaluation_series_id": operation["evaluation_series_id"],
            "invalidation_kind": "ADVICE_CURRENTNESS_INVALIDATION",
            "predecessor_head_occurrence_id": str(predecessor["head_occurrence_id"]),
            "predecessor_head_digest": str(predecessor["head_digest"]),
            "predecessor_head_result_hash": str(predecessor["head_result_hash"]),
            "invalidated_artifact_ref_and_hash": predecessor_ref,
            "evaluation_ref_and_hash": deepcopy(
                operation["terminal_result_ref_and_hash"]
            ),
            "recommendation_ref_and_hash_or_null": deepcopy(
                operation["recommendation_ref_and_hash_or_null"]
            ),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                operation["accepted_selection_claim_ref_and_hash_or_null"]
            ),
            "operation_kind": operation["operation_kind"],
            "authoritative_invalidation_ref_and_hash": {
                "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
                "content_hash": check["content_hash"],
            },
            "registered_invalidation_reason": "OPERATIONAL_FACT_EXPIRED"
            if primary_reason == "OPERATIONAL_FACT_EXPIRED"
            else primary_reason,
            "currentness_operation_ref_and_hash": {
                "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
                "content_hash": operation["content_hash"],
            },
            "currentness_check_ref_and_hash": {
                "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
                "content_hash": check["content_hash"],
            },
            "invalidation_digest": currentness_invalidation_digest,
            "created_at": created_at,
            "result": invalidation_result,
        }
        record["content_hash"] = _hash_without_content_hash(record)
        _audit_locked(
            connection,
            workspace_id=workspace_id,
            occurrence_id=invalidation_occurrence_id,
            idempotency_key=f"decision-support-currentness-invalidation:{operation['currentness_operation_key']}",
            occurrence_kind="DECISION_SUPPORT_CURRENTNESS_INVALIDATION",
            outcome_code="ADVICE_CURRENTNESS_INVALIDATION",
            content_hash=str(record["content_hash"]),
            created_at=created_at,
        )
        connection.execute(
            """
            INSERT INTO decision_support_invalidation_records (
                invalidation_occurrence_id, workspace_id, evaluation_series_id,
                idempotency_key, invalidation_kind,
                predecessor_head_occurrence_id, predecessor_head_digest,
                predecessor_head_result_hash, invalidated_artifact_ref,
                invalidated_artifact_hash, authoritative_invalidation_ref,
                authoritative_invalidation_hash, reason_code, result_hash,
                content_hash, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invalidation_occurrence_id,
                workspace_id,
                operation["evaluation_series_id"],
                f"decision-support-currentness-invalidation:{operation['currentness_operation_key']}",
                "ADVICE_CURRENTNESS_INVALIDATION",
                str(predecessor["head_occurrence_id"]),
                str(predecessor["head_digest"]),
                str(predecessor["head_result_hash"]),
                predecessor_ref["reference"],
                predecessor_ref["content_hash"],
                f"currentness-check:{check['currentness_check_occurrence_id']}",
                check["content_hash"],
                record["registered_invalidation_reason"],
                invalidation_result["content_hash"],
                record["content_hash"],
                created_at,
                _canonical_json(record),
            ),
        )
        cursor = connection.execute(
            """
            UPDATE decision_support_evaluation_heads
            SET head_kind = 'ADVICE_CURRENTNESS_INVALIDATION',
                head_occurrence_id = ?, head_digest = ?,
                head_result_hash = ?, head_record_hash = ?,
                predecessor_occurrence_id = ?, updated_at = ?
            WHERE workspace_id = ? AND evaluation_series_id = ?
              AND head_kind = 'EVALUATION'
              AND head_occurrence_id = ?
              AND head_digest = ?
              AND head_result_hash = ?
            """,
            (
                invalidation_occurrence_id,
                currentness_invalidation_digest,
                invalidation_result["content_hash"],
                record["content_hash"],
                str(predecessor["head_occurrence_id"]),
                created_at,
                workspace_id,
                operation["evaluation_series_id"],
                str(predecessor["head_occurrence_id"]),
                str(predecessor["head_digest"]),
                str(predecessor["head_result_hash"]),
            ),
        )
        if cursor.rowcount != 1:
            raise _CurrentnessFinalHeadRace(
                "currentness invalidation lost the authoritative head race"
            )
        updated = self._currentness_head_locked(  # type: ignore[attr-defined]
            connection,
            workspace_id,
            str(operation["evaluation_series_id"]),
        )
        if updated is None:
            raise DecisionSupportCurrentnessUnavailable("currentness invalidation head is unavailable")
        return invalidation_result, updated[1]

    def _write_terminal_claim_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        operation_key: str,
        check: Mapping[str, Any],
        outcome: str,
        render: Mapping[str, Any] | None,
        consuming_result: Mapping[str, Any] | None,
        invalidation_head: Mapping[str, Any] | None,
        created_at: str,
    ) -> dict[str, Any]:
        terminal_ref = {
            "reference": f"currentness-check:{check['currentness_check_occurrence_id']}",
            "content_hash": check["content_hash"],
        }
        render_ref = None
        if render is not None:
            render_ref = {
                "reference": f"current-advice-render-result:{render['render_result_occurrence_id']}",
                "content_hash": render["content_hash"],
            }
        consuming_ref = render_ref
        consuming_kind = "current-advice-render-result" if render is not None else "NOT_APPLICABLE"
        if consuming_result is not None:
            consuming_ref = {
                "reference": (
                    f"{consuming_result['schema_identifier']}:{consuming_result['consuming_result_occurrence_id']}"
                ),
                "content_hash": consuming_result["content_hash"],
            }
            consuming_kind = str(consuming_result["schema_identifier"])
        invalidation_ref = None
        if invalidation_head is not None:
            invalidation_ref = _head_ref_and_hash(invalidation_head)
        if invalidation_head is not None:
            terminal_head = deepcopy(dict(invalidation_head))
        else:
            terminal_head = _historical_head_from_check(check)
        record: dict[str, Any] = {
            "currentness_operation_key": operation_key,
            "currentness_operation_ref_and_hash": {
                "reference": f"currentness-operation:{operation['operation_occurrence_id']}",
                "content_hash": operation["content_hash"],
            },
            "currentness_check_key": check["currentness_check_key"],
            "terminal_currentness_ref_and_hash": terminal_ref,
            "currentness_outcome": outcome,
            "observed_authoritative_head_ref_and_hash": deepcopy(
                check["observed_authoritative_head_ref_and_hash"]
            ),
            "consuming_result_kind": consuming_kind,
            "consuming_result_ref_and_hash": consuming_ref,
            "refusal_result_ref_and_hash_or_null": None,
            "installed_invalidation_head_ref_and_hash_or_null": invalidation_ref,
            "terminal_head": terminal_head,
        }
        record["content_hash"] = _hash_without_content_hash(record)
        connection.execute(
            """
            INSERT INTO decision_support_currentness_terminal_claims (
                workspace_id, currentness_operation_key, operation_occurrence_id,
                currentness_check_key, terminal_currentness_ref,
                terminal_currentness_hash, currentness_outcome,
                consuming_result_kind, consuming_result_ref,
                consuming_result_hash, refusal_result_ref, refusal_result_hash,
                installed_invalidation_head_ref, installed_invalidation_head_hash,
                content_hash, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                operation_key,
                operation["operation_occurrence_id"],
                check["currentness_check_key"],
                terminal_ref["reference"],
                terminal_ref["content_hash"],
                outcome,
                record["consuming_result_kind"],
                None if consuming_ref is None else consuming_ref["reference"],
                None if consuming_ref is None else consuming_ref["content_hash"],
                None,
                None,
                None if invalidation_ref is None else invalidation_ref["reference"],
                None if invalidation_ref is None else invalidation_ref["content_hash"],
                record["content_hash"],
                created_at,
                _canonical_json(record),
            ),
        )
        return record

    def _consuming_projection_from_claim_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        claim: Mapping[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        consuming = _mapping(claim.get("consuming_result_ref_and_hash"))
        if consuming is None:
            return None, None
        consuming_kind = claim.get("consuming_result_kind")
        occurrence_id = consuming.get("reference", "").split(":")[-1]
        if consuming_kind == CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER:
            render_row = connection.execute(
                """
                SELECT * FROM decision_support_current_advice_render_results
                WHERE workspace_id = ? AND render_result_occurrence_id = ?
                """,
                (workspace_id, occurrence_id),
            ).fetchone()
            if render_row is None:
                raise DecisionSupportCurrentnessUnavailable(
                    "currentness render result is missing"
                )
            return self._render_result_from_row(render_row), None
        if consuming_kind in {
            "tradeoff-selection-result",
            "authorization-currentness-result",
            "monitoring-match-result",
        }:
            consuming_row = connection.execute(
                """
                SELECT * FROM decision_support_currentness_consuming_results
                WHERE workspace_id = ? AND consuming_result_occurrence_id = ?
                """,
                (workspace_id, occurrence_id),
            ).fetchone()
            if consuming_row is None:
                raise DecisionSupportCurrentnessUnavailable(
                    "currentness consuming result is missing"
                )
            return None, self._consuming_result_from_row(
                consuming_row,
                connection=connection,
            )
        raise DecisionSupportCurrentnessUnavailable(
            "currentness consuming result kind is unsupported"
        )

    def _replay_terminal_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation_key: str,
        operation: Mapping[str, Any],
    ) -> StoredCurrentnessResult | None:
        claim_row = connection.execute(
            """
            SELECT * FROM decision_support_currentness_terminal_claims
            WHERE workspace_id = ? AND currentness_operation_key = ?
            """,
            (workspace_id, operation_key),
        ).fetchone()
        if claim_row is None:
            return None
        claim = self._currentness_claim_from_row(claim_row)
        operation_row = connection.execute(
            """
            SELECT * FROM decision_support_currentness_operations
            WHERE workspace_id = ? AND currentness_operation_key = ?
            """,
            (workspace_id, operation_key),
        ).fetchone()
        if operation_row is None:
            raise DecisionSupportCurrentnessUnavailable("currentness operation is missing")
        stored_operation = self._currentness_operation_from_row(operation_row)
        if not _same_ref(
            stored_operation.get("operation_payload_ref_and_hash"),
            operation.get("operation_payload_ref_and_hash"),
        ):
            raise DecisionSupportCurrentnessConflict("currentness operation replay content differs")
        check_row = connection.execute(
            """
            SELECT * FROM decision_support_currentness_checks
            WHERE workspace_id = ? AND currentness_check_key = ?
            """,
            (workspace_id, claim["currentness_check_key"]),
        ).fetchone()
        if check_row is None:
            raise DecisionSupportCurrentnessUnavailable("currentness check is missing")
        check = self._currentness_check_from_row(check_row)
        render, consuming_result = self._consuming_projection_from_claim_locked(
            connection,
            workspace_id=workspace_id,
            claim=claim,
        )
        terminal_head = _mapping(claim.get("terminal_head"))
        if terminal_head is None:
            terminal_head = _historical_head_from_check(check)
        return StoredCurrentnessResult(
            result="IDEMPOTENT_REPLAY",
            operation=stored_operation,
            currentness=check,
            terminal_claim=claim,
            render=render,
            consuming_result=consuming_result,
            head=deepcopy(dict(terminal_head)),
        )

    def _check_currentness_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        operation: Mapping[str, Any],
        currentness_context: Mapping[str, Any] | None,
        now: str,
    ) -> StoredCurrentnessResult:
        fields, payload, operation_key, check_key = self._normalize_operation(operation)
        invocation_kind = operation.get("invocation_operation_kind")
        if invocation_kind is not None and invocation_kind != fields["operation_kind"]:
            raise DecisionSupportCurrentnessOperationMismatch(
                "currentness operation was presented through a different consumer"
            )
        replay = self._replay_terminal_locked(
            connection,
            workspace_id=workspace_id,
            operation_key=operation_key,
            operation=fields,
        )
        if replay is not None:
            return replay
        self._require_authoritative_operation_payload_locked(
            connection,
            workspace_id=workspace_id,
            operation_kind=str(fields["operation_kind"]),
            payload=payload,
            payload_ref=fields["operation_payload_ref_and_hash"],
        )
        evaluation_row, evaluation, terminal_result = self._load_evaluation_locked(
            connection,
            workspace_id=workspace_id,
            evaluation_series_id=str(fields["evaluation_series_id"]),
            evaluation_occurrence_id=str(fields["evaluation_occurrence_id"]),
            evaluation_digest=fields["evaluation_digest"],
            terminal_binding=fields["terminal_result_ref_and_hash"],
        )
        self._validate_bound_operation_locked(
            operation=operation,
            fields=fields,
            evaluation=evaluation,
            terminal_result=terminal_result,
        )
        consumed_dependencies: list[dict[str, Any]] = []
        horizons: list[dict[str, Any]] = []
        advice_valid_through: object = "NO_EXPIRY"
        current_dependencies: list[dict[str, Any]] = []
        current_horizons = horizons
        expected_head = _expected_evaluation_head(evaluation_row, fields)
        current_head = self._currentness_head_locked(
            connection,
            workspace_id,
            str(fields["evaluation_series_id"]),
        )
        if current_head is None:
            raise DecisionSupportCurrentnessUnavailable(
                "currentness evaluation series is unavailable"
            )
        head_row, head = current_head
        expected_head_matches = (
            head["head_kind"] == expected_head["head_kind"]
            and head["head_occurrence_id"] == expected_head["head_occurrence_id"]
            and head["head_digest"] == expected_head["head_digest"]
            and head["head_result_hash"] == expected_head["head_result_hash"]
        )
        if expected_head_matches:
            consumed_dependencies, horizons, advice_valid_through = (
                self._frozen_currentness_metadata(evaluation)
            )
            effective_context = currentness_context
            if effective_context is None:
                effective_context = self._stored_currentness_authority(
                    connection,
                    evaluation,
                    workspace_id=workspace_id,
                    evaluation_series_id=str(fields["evaluation_series_id"]),
                )
            (
                consumed_dependencies,
                current_dependencies,
                horizons,
                current_horizons,
                advice_valid_through,
            ) = self._currentness_context(
                evaluation=evaluation,
                context=effective_context,
            )
        operation_record = self._claim_operation_locked(
            connection,
            workspace_id=workspace_id,
            fields=fields,
            payload=payload,
            operation_key=operation_key,
            check_key=check_key,
            now=now,
        )
        replay = self._replay_terminal_locked(
            connection,
            workspace_id=workspace_id,
            operation_key=operation_key,
            operation=fields,
        )
        if replay is not None:
            return replay
        chain_reasons: list[str] = []
        if not expected_head_matches:
            outcome = "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
            reasons: list[str] = []
            offending: list[dict[str, Any]] = []
            observed_head = head
        else:
            dependency_reasons, offending_dependencies = self._dependency_reasons(
                consumed=consumed_dependencies,
                current=current_dependencies,
            )
            horizon_reasons, offending_horizons = self._horizon_reasons(
                currentness_checked_at=fields["currentness_checked_at"],
                advice_valid_through=advice_valid_through,
                horizons=current_horizons,
            )
            reasons = dependency_reasons + horizon_reasons + chain_reasons
            offending = offending_dependencies + offending_horizons
            if reasons:
                outcome = "ADVICE_CURRENTNESS_INVALIDATION"
            else:
                outcome = "CURRENTNESS_PROVEN_AT_CHECK"
            observed_head = head

        if outcome in {
            "CURRENTNESS_PROVEN_AT_CHECK",
            "ADVICE_CURRENTNESS_INVALIDATION",
        }:
            final_observation = self._currentness_head_locked(
                connection,
                workspace_id,
                str(fields["evaluation_series_id"]),
            )
            if final_observation is None:
                raise DecisionSupportCurrentnessUnavailable(
                    "currentness final head is unavailable"
                )
            final_head_row, final_head = final_observation
            if not (
                final_head["head_kind"] == expected_head["head_kind"]
                and final_head["head_occurrence_id"] == expected_head["head_occurrence_id"]
                and final_head["head_digest"] == expected_head["head_digest"]
                and final_head["head_result_hash"] == expected_head["head_result_hash"]
            ):
                outcome = "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
                reasons = []
                offending = []
                observed_head = final_head

        connection.execute("SAVEPOINT currentness_publish")
        try:
            check = self._write_currentness_check_locked(
                connection,
                workspace_id=workspace_id,
                operation=operation_record,
                operation_key=operation_key,
                check_key=check_key,
                outcome=outcome,
                expected_head=expected_head,
                observed_head=observed_head,
                advice_valid_through=advice_valid_through,
                dependencies=current_dependencies,
                horizons=current_horizons,
                reasons=reasons,
                created_at=now,
            )
            render = None
            consuming_result = None
            invalidation_head = None
            if outcome == "CURRENTNESS_PROVEN_AT_CHECK":
                if fields["operation_kind"] == "CURRENT_ADVICE_RENDER":
                    render_request = self._render_request_by_ref_locked(
                        connection,
                        workspace_id=workspace_id,
                        reference=fields["operation_payload_ref_and_hash"]["reference"],
                    )
                    render = self._write_render_result_locked(
                        connection,
                        workspace_id=workspace_id,
                        operation=operation_record,
                        check=check,
                        render_request=render_request,
                        evaluation=evaluation,
                        terminal_result=terminal_result,
                        created_at=now,
                    )
                else:
                    consuming_result = self._write_currentness_consuming_result_locked(
                        connection,
                        workspace_id=workspace_id,
                        operation=operation_record,
                        check=check,
                        terminal_result=terminal_result,
                        created_at=now,
                    )
            elif outcome == "ADVICE_CURRENTNESS_INVALIDATION":
                _, invalidation_head = self._write_currentness_invalidation_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation=operation_record,
                    check=check,
                    predecessor=head_row,
                    reasons=reasons,
                    offending=offending,
                    advice_valid_through=advice_valid_through,
                    created_at=now,
                )
            claim = self._write_terminal_claim_locked(
                connection,
                workspace_id=workspace_id,
                operation=operation_record,
                operation_key=operation_key,
                check=check,
                outcome=outcome,
                render=render,
                consuming_result=consuming_result,
                invalidation_head=invalidation_head,
                created_at=now,
            )
            connection.execute("RELEASE SAVEPOINT currentness_publish")
        except _CurrentnessFinalHeadRace:
            connection.execute("ROLLBACK TO SAVEPOINT currentness_publish")
            connection.execute("RELEASE SAVEPOINT currentness_publish")
            stale_observation = self._currentness_head_locked(
                connection,
                workspace_id,
                str(fields["evaluation_series_id"]),
            )
            if stale_observation is None:
                raise DecisionSupportCurrentnessUnavailable(
                    "currentness race successor head is unavailable"
                )
            _, observed_head = stale_observation
            outcome = "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
            reasons = []
            offending = []
            check = self._write_currentness_check_locked(
                connection,
                workspace_id=workspace_id,
                operation=operation_record,
                operation_key=operation_key,
                check_key=check_key,
                outcome=outcome,
                expected_head=expected_head,
                observed_head=observed_head,
                advice_valid_through=advice_valid_through,
                dependencies=current_dependencies,
                horizons=current_horizons,
                reasons=reasons,
                created_at=now,
            )
            render = None
            consuming_result = None
            invalidation_head = None
            claim = self._write_terminal_claim_locked(
                connection,
                workspace_id=workspace_id,
                operation=operation_record,
                operation_key=operation_key,
                check=check,
                outcome=outcome,
                render=render,
                consuming_result=consuming_result,
                invalidation_head=invalidation_head,
                created_at=now,
            )
        final_head = self._currentness_head_locked(
            connection,
            workspace_id,
            str(fields["evaluation_series_id"]),
        )
        if final_head is None:
            raise DecisionSupportCurrentnessUnavailable("currentness final head is unavailable")
        return StoredCurrentnessResult(
            result="CREATED",
            operation=operation_record,
            currentness=check,
            terminal_claim=claim,
            render=render,
            consuming_result=consuming_result,
            head=final_head[1],
        )

    def _render_request_by_ref_locked(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        reference: str,
    ) -> dict[str, Any]:
        if reference.startswith("current-advice-render-request:"):
            occurrence_id = reference.split(":", 1)[1]
        else:
            occurrence_id = reference
        row = connection.execute(
            """
            SELECT * FROM decision_support_current_advice_render_requests
            WHERE workspace_id = ? AND render_request_occurrence_id = ?
            """,
            (workspace_id, occurrence_id),
        ).fetchone()
        if row is None:
            raise DecisionSupportCurrentnessUnavailable("render request is unavailable")
        return self._render_request_from_row(row)

    def _render_operation(
        self,
        render_request: Mapping[str, Any],
        *,
        request_ref_and_hash: Mapping[str, Any],
    ) -> dict[str, Any]:
        operation: dict[str, Any] = {
            "schema_identifier": CURRENTNESS_OPERATION_SCHEMA_IDENTIFIER,
            "schema_version": CURRENTNESS_SCHEMA_VERSION,
            "currentness_policy_identifier_and_version": deepcopy(
                CURRENTNESS_POLICY_IDENTIFIER_AND_VERSION
            ),
            "operation_kind": "CURRENT_ADVICE_RENDER",
            "evaluation_series_id": render_request["evaluation_series_id"],
            "evaluation_occurrence_id": render_request["evaluation_occurrence_id"],
            "evaluation_digest": render_request["evaluation_digest"],
            "terminal_result_ref_and_hash": deepcopy(
                render_request["terminal_result_ref_and_hash"]
            ),
            "recommendation_ref_and_hash_or_null": deepcopy(
                render_request["recommendation_ref_and_hash_or_null"]
            ),
            "accepted_selection_claim_ref_and_hash_or_null": deepcopy(
                render_request["accepted_selection_claim_ref_and_hash_or_null"]
            ),
            "operation_payload_ref_and_hash": deepcopy(dict(request_ref_and_hash)),
            "operation_payload": deepcopy(dict(render_request)),
            "currentness_checked_at": deepcopy(render_request["available_at"]),
        }
        fields = _key_fields(operation)
        operation_key = currentness_operation_key_for(fields)
        record = _operation_record_for(fields, render_request, operation_key)
        operation.update(
            {
                "currentness_operation_key": operation_key,
                "operation_occurrence_id": record["operation_occurrence_id"],
                "content_hash": record["content_hash"],
            }
        )
        return operation

    def render_current_advice(
        self,
        workspace_id: str,
        *,
        render_request: Mapping[str, Any],
        currentness_context: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> StoredCurrentnessResult:
        """Claim a render request and prove its exact advice chain at its availability time."""

        if not isinstance(render_request, Mapping):
            raise DecisionSupportCurrentnessUnavailable("render request is invalid")
        current_time = _timestamp(now or datetime.now(timezone.utc))
        with self._lock:  # type: ignore[attr-defined]
            connection = self._currentness_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                request_preview = _render_request_record_for(render_request)
                supplied_occurrence_id = render_request.get("render_request_occurrence_id")
                supplied_content_hash = render_request.get("content_hash")
                if supplied_occurrence_id is not None and supplied_occurrence_id != request_preview[
                    "render_request_occurrence_id"
                ]:
                    raise DecisionSupportCurrentnessUnavailable(
                        "render request occurrence does not match its deterministic key"
                    )
                if supplied_content_hash is not None and supplied_content_hash != request_preview[
                    "content_hash"
                ]:
                    raise DecisionSupportCurrentnessUnavailable(
                        "render request content hash does not match its immutable record"
                    )
                request_ref_preview = {
                    "reference": (
                        f"current-advice-render-request:{request_preview['render_request_occurrence_id']}"
                    ),
                    "content_hash": request_preview["content_hash"],
                }
                preview_operation = self._render_operation(
                    request_preview,
                    request_ref_and_hash=request_ref_preview,
                )
                preview_fields = _key_fields(preview_operation)
                _, preview_evaluation, preview_terminal = self._load_evaluation_locked(
                    connection,
                    workspace_id=workspace_id,
                    evaluation_series_id=str(preview_fields["evaluation_series_id"]),
                    evaluation_occurrence_id=str(preview_fields["evaluation_occurrence_id"]),
                    evaluation_digest=preview_fields["evaluation_digest"],
                    terminal_binding=preview_fields["terminal_result_ref_and_hash"],
                )
                self._validate_bound_operation_locked(
                    operation=preview_operation,
                    fields=preview_fields,
                    evaluation=preview_evaluation,
                    terminal_result=preview_terminal,
                )
                request_record = self._claim_render_request_locked(
                    connection,
                    workspace_id=workspace_id,
                    render_request=render_request,
                    now=current_time,
                )
                request_ref = {
                    "reference": (
                        f"current-advice-render-request:{request_record['render_request_occurrence_id']}"
                    ),
                    "content_hash": request_record["content_hash"],
                }
                connection.commit()
            except (
                DecisionSupportCurrentnessConflict,
                DecisionSupportCurrentnessUnavailable,
            ):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise DecisionSupportCurrentnessConflict from error
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportCurrentnessUnavailable from error
            except Exception:
                connection.rollback()
                raise
        return self.check_decision_support_currentness(
            workspace_id,
            operation=self._render_operation(
                request_record,
                request_ref_and_hash=request_ref,
            ),
            currentness_context=currentness_context,
            now=now,
        )

    def check_decision_support_currentness(
        self,
        workspace_id: str,
        *,
        operation: Mapping[str, Any],
        currentness_context: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> StoredCurrentnessResult:
        """Prove one exact operation-bound currentness claim or persist its refusal."""

        if not isinstance(operation, Mapping):
            raise DecisionSupportCurrentnessUnavailable("currentness operation is invalid")
        current_time = _timestamp(now or datetime.now(timezone.utc))
        with self._lock:  # type: ignore[attr-defined]
            connection = self._currentness_connection()
            try:
                connection.execute("BEGIN IMMEDIATE")
                fields, _, operation_key, _ = self._normalize_operation(operation)
                invocation_kind = operation.get("invocation_operation_kind")
                if invocation_kind is not None and invocation_kind != fields["operation_kind"]:
                    raise DecisionSupportCurrentnessOperationMismatch(
                        "currentness operation was presented through a different consumer"
                    )
                result = self._check_currentness_locked(
                    connection,
                    workspace_id=workspace_id,
                    operation=operation,
                    currentness_context=currentness_context,
                    now=current_time,
                )
                connection.commit()
                return result
            except (
                DecisionSupportCurrentnessConflict,
                DecisionSupportCurrentnessOperationMismatch,
                DecisionSupportCurrentnessUnavailable,
            ):
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise DecisionSupportCurrentnessConflict from error
            except sqlite3.Error as error:
                connection.rollback()
                raise DecisionSupportCurrentnessUnavailable from error
            except Exception:
                connection.rollback()
                raise

    prove_decision_support_currentness = check_decision_support_currentness
    check_advice_currentness = check_decision_support_currentness
    publish_current_advice_render = render_current_advice

    def list_decision_support_currentness(
        self,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """Return the immutable operation/check/claim projections for audit inspection."""

        with self._lock:  # type: ignore[attr-defined]
            connection = self._currentness_connection()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM decision_support_currentness_operations
                    WHERE workspace_id = ? ORDER BY created_at, operation_occurrence_id
                    """,
                    (workspace_id,),
                ).fetchall()
                result: list[dict[str, Any]] = []
                for row in rows:
                    operation = self._currentness_operation_from_row(row)
                    check_row = connection.execute(
                        """
                        SELECT * FROM decision_support_currentness_checks
                        WHERE workspace_id = ? AND currentness_operation_key = ?
                        """,
                        (workspace_id, row["currentness_operation_key"]),
                    ).fetchone()
                    claim_row = connection.execute(
                        """
                        SELECT * FROM decision_support_currentness_terminal_claims
                        WHERE workspace_id = ? AND currentness_operation_key = ?
                        """,
                        (workspace_id, row["currentness_operation_key"]),
                    ).fetchone()
                    claim = (
                        None
                        if claim_row is None
                        else self._currentness_claim_from_row(claim_row)
                    )
                    render = None
                    consuming_result = None
                    if claim is not None:
                        render, consuming_result = self._consuming_projection_from_claim_locked(
                            connection,
                            workspace_id=workspace_id,
                            claim=claim,
                        )
                    result.append(
                        {
                            "operation": operation,
                            "currentness": (
                                None
                                if check_row is None
                                else self._currentness_check_from_row(check_row)
                            ),
                            "terminal_claim": claim,
                            "render": render,
                            "consuming_result": consuming_result,
                        }
                    )
                return result
            except DecisionSupportCurrentnessUnavailable:
                raise
            except sqlite3.Error as error:
                raise DecisionSupportCurrentnessUnavailable from error
