from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import sqlite3
from typing import Any, Mapping

from .canonical import canonical_json as _canonical_json
from .canonical import normalise_temporal
from .canonical import sha256 as _sha256


TRADEOFF_SELECTION_SCHEMA_IDENTIFIER = "tradeoff-selection"
TRADEOFF_SELECTION_DELIVERY_ATTEMPT_SCHEMA_IDENTIFIER = (
    "tradeoff-selection-delivery-attempt"
)
TRADEOFF_SELECTION_VALIDATION_RESULT_SCHEMA_IDENTIFIER = (
    "tradeoff-selection-validation-result"
)
TRADEOFF_SELECTION_RESULT_SCHEMA_IDENTIFIER = "tradeoff-selection-result"
TRADEOFF_SELECTION_CLAIM_SCHEMA_IDENTIFIER = "tradeoff-selection-claim"
TRADEOFF_SELECTION_SCHEMA_VERSION = "1"
TRADEOFF_SELECTION_STORAGE_SCHEMA_VERSION = "tradeoff-selection-storage.v1"
GOVERNANCE_SELECTION_REFERENCE_FIELD = "governance_tradeoff_selection_ref_and_hash"

TRADEOFF_SELECTION_VALIDATION_CODES = frozenset(
    {
        "TRADEOFF_SELECTION_SCHEMA_INVALID",
        "TRADEOFF_SELECTION_SCHEMA_UNSUPPORTED",
        "TRADEOFF_SELECTION_SERIES_NOT_FOUND",
        "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH",
    }
)
TRADEOFF_SELECTION_RESULT_CODES = frozenset(
    {
        "TRADEOFF_SELECTION_STALE",
        "TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF",
        "TRADEOFF_SELECTION_INVALID_CANDIDATE",
        "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT",
        "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED",
        "TRADEOFF_SELECTION_ACCEPTED",
    }
)


class TradeoffSelectionContractError(ValueError):
    """A trade-off selection or delivery attempt is not intrinsically valid."""


GOVERNANCE_TRADEOFF_SELECTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS governance_tradeoff_selections (
        selection_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        selection_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        evaluation_occurrence_id TEXT NOT NULL,
        evaluation_digest TEXT NOT NULL,
        terminal_result_ref TEXT NOT NULL,
        terminal_result_hash TEXT NOT NULL,
        selected_candidate_ref TEXT NOT NULL,
        manager_actor_ref TEXT NOT NULL,
        selected_at TEXT NOT NULL,
        available_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, selection_key)
    )
"""
GOVERNANCE_TRADEOFF_SELECTIONS_COLUMNS = [
    "selection_occurrence_id",
    "workspace_id",
    "selection_key",
    "content_hash",
    "evaluation_series_id",
    "evaluation_occurrence_id",
    "evaluation_digest",
    "terminal_result_ref",
    "terminal_result_hash",
    "selected_candidate_ref",
    "manager_actor_ref",
    "selected_at",
    "available_at",
    "created_at",
    "payload_json",
]

TRADEOFF_SELECTION_ATTEMPTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_tradeoff_selection_attempts (
        delivery_attempt_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        delivery_attempt_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        selection_ref TEXT NOT NULL,
        selection_hash TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        evaluation_occurrence_id TEXT NOT NULL,
        evaluation_digest TEXT NOT NULL,
        selected_candidate_ref TEXT NOT NULL,
        delivered_at TEXT NOT NULL,
        available_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, delivery_attempt_key)
    )
"""
TRADEOFF_SELECTION_ATTEMPTS_COLUMNS = [
    "delivery_attempt_occurrence_id",
    "workspace_id",
    "delivery_attempt_key",
    "content_hash",
    "selection_ref",
    "selection_hash",
    "evaluation_series_id",
    "evaluation_occurrence_id",
    "evaluation_digest",
    "selected_candidate_ref",
    "delivered_at",
    "available_at",
    "created_at",
    "payload_json",
]

TRADEOFF_SELECTION_VALIDATION_RESULTS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_tradeoff_selection_validation_results (
        validation_result_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        validation_result_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        validation_code TEXT NOT NULL,
        delivery_attempt_ref TEXT NOT NULL,
        delivery_attempt_hash TEXT NOT NULL,
        evaluation_series_id TEXT,
        governance_selection_ref TEXT,
        governance_selection_hash TEXT,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, validation_result_key)
    )
"""
TRADEOFF_SELECTION_VALIDATION_RESULTS_COLUMNS = [
    "validation_result_occurrence_id",
    "workspace_id",
    "validation_result_key",
    "content_hash",
    "validation_code",
    "delivery_attempt_ref",
    "delivery_attempt_hash",
    "evaluation_series_id",
    "governance_selection_ref",
    "governance_selection_hash",
    "created_at",
    "payload_json",
]

TRADEOFF_SELECTION_CLAIMS_TABLE = """
    CREATE TABLE IF NOT EXISTS decision_support_tradeoff_selection_claims (
        selection_claim_occurrence_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        selection_claim_key TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        evaluation_series_id TEXT NOT NULL,
        evaluation_occurrence_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        UNIQUE (workspace_id, selection_claim_key),
        UNIQUE (workspace_id, evaluation_series_id, evaluation_occurrence_id)
    )
"""
TRADEOFF_SELECTION_CLAIMS_COLUMNS = [
    "selection_claim_occurrence_id",
    "workspace_id",
    "selection_claim_key",
    "content_hash",
    "evaluation_series_id",
    "evaluation_occurrence_id",
    "created_at",
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
            f"{table_name} schema is not the locked trade-off selection schema"
        )


def ensure_tradeoff_selection_schema(
    connection: sqlite3.Connection,
    *,
    create: bool,
) -> None:
    for table_name, create_sql, columns in (
        (
            "governance_tradeoff_selections",
            GOVERNANCE_TRADEOFF_SELECTIONS_TABLE,
            GOVERNANCE_TRADEOFF_SELECTIONS_COLUMNS,
        ),
        (
            "decision_support_tradeoff_selection_attempts",
            TRADEOFF_SELECTION_ATTEMPTS_TABLE,
            TRADEOFF_SELECTION_ATTEMPTS_COLUMNS,
        ),
        (
            "decision_support_tradeoff_selection_validation_results",
            TRADEOFF_SELECTION_VALIDATION_RESULTS_TABLE,
            TRADEOFF_SELECTION_VALIDATION_RESULTS_COLUMNS,
        ),
        (
            "decision_support_tradeoff_selection_claims",
            TRADEOFF_SELECTION_CLAIMS_TABLE,
            TRADEOFF_SELECTION_CLAIMS_COLUMNS,
        ),
    ):
        _ensure_table(
            connection,
            table_name,
            create_sql,
            columns,
            create=create,
        )
    if create:
        for table_name in (
            "governance_tradeoff_selections",
            "decision_support_tradeoff_selection_attempts",
            "decision_support_tradeoff_selection_validation_results",
            "decision_support_tradeoff_selection_claims",
        ):
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'trade-off selection records are immutable');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'trade-off selection records are immutable');
                END
                """
            )


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def is_hash(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == len("sha256:") + 64
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def ref_and_hash(value: object) -> dict[str, str] | None:
    candidate = _mapping(value)
    if candidate is None:
        return None
    reference = candidate.get("reference")
    content_hash = candidate.get("content_hash")
    if not isinstance(reference, str) or not reference or not is_hash(content_hash):
        return None
    return {"reference": reference, "content_hash": content_hash}


def record_content_hash(record: Mapping[str, Any]) -> str:
    content = deepcopy(dict(record))
    content.pop("content_hash", None)
    # Governance points back to this record's hash. Validate that external
    # binding separately rather than making the digest self-referential.
    content.pop(GOVERNANCE_SELECTION_REFERENCE_FIELD, None)
    return _sha256(content)


def _parse_time(value: object) -> tuple[date | datetime, str] | None:
    if isinstance(value, Mapping):
        parsed = normalise_temporal(value)
        if parsed.comparable is None or parsed.field.get("state") != "present":
            return None
        return parsed.comparable, _canonical_json(value)
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        if "T" not in candidate:
            return date.fromisoformat(candidate), value
        parsed_datetime = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed_datetime.tzinfo is None:
        return None
    return parsed_datetime.astimezone(timezone.utc), value


def time_compare(left: object, right: object) -> int | None:
    left_parsed = _parse_time(left)
    right_parsed = _parse_time(right)
    if left_parsed is None or right_parsed is None:
        return None
    left_value = left_parsed[0]
    right_value = right_parsed[0]
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


def time_equal(left: object, right: object) -> bool:
    parsed_left = _parse_time(left)
    parsed_right = _parse_time(right)
    return (
        parsed_left is not None
        and parsed_right is not None
        and time_compare(left, right) == 0
        and parsed_left[1] == parsed_right[1]
    )


def candidate_reference(candidate: Mapping[str, Any]) -> str:
    option_code = candidate.get("option_code")
    option_version = candidate.get("option_version")
    candidate_identity = _mapping(candidate.get("candidate_reference"))
    evaluation_occurrence_id = (
        None
        if candidate_identity is None
        else candidate_identity.get("evaluation_occurrence_id")
    )
    if not all(
        isinstance(value, str) and value
        for value in (option_code, option_version)
    ):
        raise TradeoffSelectionContractError("candidate identity is incomplete")
    if not isinstance(evaluation_occurrence_id, str) or not evaluation_occurrence_id:
        raise TradeoffSelectionContractError("candidate evaluation identity is invalid")
    return f"candidate:{evaluation_occurrence_id}:{option_code}:{option_version}"


def candidate_identity(candidate: Mapping[str, Any]) -> dict[str, str]:
    reference = _mapping(candidate.get("candidate_reference")) or {}
    evaluation_occurrence_id = reference.get("evaluation_occurrence_id")
    if not isinstance(evaluation_occurrence_id, str) or not evaluation_occurrence_id:
        raise TradeoffSelectionContractError("candidate evaluation identity is missing")
    option_code = candidate.get("option_code")
    option_version = candidate.get("option_version")
    if not isinstance(option_code, str) or not isinstance(option_version, str):
        raise TradeoffSelectionContractError("candidate identity is incomplete")
    if (
        reference.get("option_code") != option_code
        or reference.get("option_version") != option_version
    ):
        raise TradeoffSelectionContractError("candidate identity disagrees with its projection")
    return {
        "evaluation_occurrence_id": evaluation_occurrence_id,
        "option_code": option_code,
        "option_version": option_version,
    }


def normalize_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(selection, Mapping):
        raise TradeoffSelectionContractError("trade-off selection is invalid")
    if selection.get("schema_identifier") != TRADEOFF_SELECTION_SCHEMA_IDENTIFIER:
        raise TradeoffSelectionContractError("trade-off selection schema is unsupported")
    if selection.get("schema_version") != TRADEOFF_SELECTION_SCHEMA_VERSION:
        raise TradeoffSelectionContractError("trade-off selection schema version is unsupported")
    occurrence_id = selection.get("selection_occurrence_id", selection.get("occurrence_id"))
    required_strings = {
        "selection_occurrence_id": occurrence_id,
        "evaluation_series_id": selection.get("evaluation_series_id"),
        "evaluation_occurrence_id": selection.get("evaluation_occurrence_id"),
        "evaluation_digest": selection.get("evaluation_digest"),
        "selected_candidate_ref": selection.get("selected_candidate_ref"),
        "manager_actor_ref": selection.get("manager_actor_ref"),
    }
    if not all(isinstance(value, str) and value for value in required_strings.values()):
        raise TradeoffSelectionContractError("trade-off selection binding is incomplete")
    terminal_ref = ref_and_hash(selection.get("terminal_result_ref_and_hash"))
    if terminal_ref is None:
        raise TradeoffSelectionContractError("trade-off selection terminal binding is invalid")
    selected_candidate = _mapping(
        selection.get("selected_candidate", selection.get("candidate"))
    )
    if selected_candidate is None:
        raise TradeoffSelectionContractError("trade-off selection candidate content is missing")
    selected_candidate = deepcopy(dict(selected_candidate))
    selected_identity = candidate_identity(selected_candidate)
    if selected_identity["evaluation_occurrence_id"] != selection["evaluation_occurrence_id"]:
        raise TradeoffSelectionContractError(
            "trade-off selection candidate belongs to another evaluation"
        )
    selected_candidate_hash = selected_candidate.get("content_hash")
    if not is_hash(selected_candidate_hash) or record_content_hash(selected_candidate) != selected_candidate_hash:
        raise TradeoffSelectionContractError("trade-off selection candidate content is invalid")
    if candidate_reference(selected_candidate) != selection["selected_candidate_ref"]:
        raise TradeoffSelectionContractError("trade-off selection candidate reference is inconsistent")
    selected_at = selection.get("selected_at")
    available_at = selection.get("available_at")
    if time_compare(selected_at, available_at) is None or time_compare(selected_at, available_at) > 0:
        raise TradeoffSelectionContractError("trade-off selection chronology is invalid")
    record: dict[str, Any] = {
        "schema_identifier": TRADEOFF_SELECTION_SCHEMA_IDENTIFIER,
        "schema_version": TRADEOFF_SELECTION_SCHEMA_VERSION,
        "selection_occurrence_id": occurrence_id,
        "evaluation_series_id": selection["evaluation_series_id"],
        "evaluation_occurrence_id": selection["evaluation_occurrence_id"],
        "evaluation_digest": selection["evaluation_digest"],
        "terminal_result_ref_and_hash": terminal_ref,
        "selected_candidate_ref": selection["selected_candidate_ref"],
        "selected_candidate": selected_candidate,
        "manager_actor_ref": selection["manager_actor_ref"],
        "selected_at": deepcopy(selected_at),
        "available_at": deepcopy(available_at),
    }
    expected_governance_ref = {
        "reference": f"governance-tradeoff-selection:{occurrence_id}",
        "content_hash": record_content_hash(record),
    }
    if GOVERNANCE_SELECTION_REFERENCE_FIELD not in selection:
        raise TradeoffSelectionContractError(
            "trade-off selection Governance reference is missing"
        )
    supplied_governance_ref = ref_and_hash(
        selection.get(GOVERNANCE_SELECTION_REFERENCE_FIELD)
    )
    if (
        GOVERNANCE_SELECTION_REFERENCE_FIELD in selection
        and supplied_governance_ref is None
    ):
        raise TradeoffSelectionContractError(
            "trade-off selection Governance reference is malformed"
        )
    if supplied_governance_ref is not None and supplied_governance_ref != expected_governance_ref:
        raise TradeoffSelectionContractError(
            "trade-off selection Governance reference is inconsistent"
        )
    record[GOVERNANCE_SELECTION_REFERENCE_FIELD] = expected_governance_ref
    expected_hash = record_content_hash(record)
    supplied_hash = selection.get("content_hash")
    if not is_hash(supplied_hash) or supplied_hash != expected_hash:
        raise TradeoffSelectionContractError("trade-off selection content hash is invalid")
    record["content_hash"] = expected_hash
    return record


def selection_ref_and_hash(selection: Mapping[str, Any]) -> dict[str, str]:
    return {
        "reference": str(selection["selection_occurrence_id"]),
        "content_hash": str(selection["content_hash"]),
    }


def governance_selection_ref_and_hash(selection: Mapping[str, Any]) -> dict[str, str]:
    binding = ref_and_hash(selection.get(GOVERNANCE_SELECTION_REFERENCE_FIELD))
    if binding is None:
        raise TradeoffSelectionContractError(
            "Governance trade-off selection reference is unavailable"
        )
    return binding


def selection_key_for(selection: Mapping[str, Any]) -> str:
    return _sha256(
        {
            "schema_identifier_and_version": {
                "identifier": TRADEOFF_SELECTION_SCHEMA_IDENTIFIER,
                "version": TRADEOFF_SELECTION_SCHEMA_VERSION,
            },
            "selection_occurrence_id": selection["selection_occurrence_id"],
            "content_hash": selection["content_hash"],
        }
    )


def normalize_delivery_attempt(attempt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(attempt, Mapping):
        raise TradeoffSelectionContractError("trade-off selection delivery attempt is invalid")
    if attempt.get("schema_identifier") != TRADEOFF_SELECTION_DELIVERY_ATTEMPT_SCHEMA_IDENTIFIER:
        raise TradeoffSelectionContractError("delivery attempt schema is unsupported")
    if attempt.get("schema_version") != TRADEOFF_SELECTION_SCHEMA_VERSION:
        raise TradeoffSelectionContractError("delivery attempt schema version is unsupported")
    occurrence_id = attempt.get("delivery_attempt_occurrence_id", attempt.get("occurrence_id"))
    if not isinstance(occurrence_id, str) or not occurrence_id:
        raise TradeoffSelectionContractError("delivery attempt occurrence is missing")
    selection_ref = ref_and_hash(attempt.get("tradeoff_selection_ref_and_hash"))
    if selection_ref is None:
        raise TradeoffSelectionContractError("delivery attempt selection reference is invalid")
    required = (
        "evaluation_series_id",
        "evaluation_occurrence_id",
        "evaluation_digest",
        "selected_candidate_ref",
    )
    if not all(isinstance(attempt.get(key), str) and attempt.get(key) for key in required):
        raise TradeoffSelectionContractError("delivery attempt binding is incomplete")
    terminal_ref = ref_and_hash(attempt.get("terminal_result_ref_and_hash"))
    if terminal_ref is None:
        raise TradeoffSelectionContractError("delivery attempt terminal binding is invalid")
    selected_candidate = _mapping(
        attempt.get("selected_candidate", attempt.get("candidate"))
    )
    if selected_candidate is None:
        raise TradeoffSelectionContractError("delivery attempt candidate content is missing")
    selected_candidate = deepcopy(dict(selected_candidate))
    selected_identity = candidate_identity(selected_candidate)
    if selected_identity["evaluation_occurrence_id"] != attempt["evaluation_occurrence_id"]:
        raise TradeoffSelectionContractError(
            "delivery attempt candidate belongs to another evaluation"
        )
    candidate_hash = selected_candidate.get("content_hash")
    if not is_hash(candidate_hash) or record_content_hash(selected_candidate) != candidate_hash:
        raise TradeoffSelectionContractError("delivery attempt candidate content is invalid")
    if candidate_reference(selected_candidate) != attempt["selected_candidate_ref"]:
        raise TradeoffSelectionContractError("delivery attempt candidate reference is inconsistent")
    selected_at = attempt.get("selection_available_at")
    delivered_at = attempt.get("delivered_at")
    available_at = attempt.get("available_at")
    if (
        time_compare(selected_at, delivered_at) is None
        or time_compare(delivered_at, available_at) is None
        or time_compare(selected_at, delivered_at) > 0
        or time_compare(delivered_at, available_at) > 0
    ):
        raise TradeoffSelectionContractError("delivery attempt chronology is invalid")
    record: dict[str, Any] = {
        "schema_identifier": TRADEOFF_SELECTION_DELIVERY_ATTEMPT_SCHEMA_IDENTIFIER,
        "schema_version": TRADEOFF_SELECTION_SCHEMA_VERSION,
        "occurrence_id": occurrence_id,
        "tradeoff_selection_ref_and_hash": selection_ref,
        "evaluation_series_id": attempt["evaluation_series_id"],
        "evaluation_occurrence_id": attempt["evaluation_occurrence_id"],
        "evaluation_digest": attempt["evaluation_digest"],
        "terminal_result_ref_and_hash": terminal_ref,
        "selected_candidate_ref": attempt["selected_candidate_ref"],
        "selected_candidate": selected_candidate,
        "selection_available_at": deepcopy(selected_at),
        "delivered_at": deepcopy(delivered_at),
        "available_at": deepcopy(available_at),
    }
    expected_hash = record_content_hash(record)
    supplied_hash = attempt.get("content_hash")
    if not is_hash(supplied_hash) or supplied_hash != expected_hash:
        raise TradeoffSelectionContractError("delivery attempt content hash is invalid")
    record["content_hash"] = expected_hash
    return record


def seal_delivery_attempt(
    attempt: Mapping[str, Any],
    *,
    authoritative_available_at: object,
) -> dict[str, Any]:
    """Create the immutable delivery occurrence at the server-owned receipt time."""

    candidate = deepcopy(dict(attempt))
    candidate["delivered_at"] = deepcopy(authoritative_available_at)
    candidate["available_at"] = deepcopy(authoritative_available_at)
    candidate.pop("content_hash", None)
    candidate["content_hash"] = record_content_hash(candidate)
    return normalize_delivery_attempt(candidate)


def delivery_attempt_identity(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """Return the retry identity while excluding server-owned temporal fields."""

    return {
        key: deepcopy(attempt[key])
        for key in (
            "schema_identifier",
            "schema_version",
            "occurrence_id",
            "tradeoff_selection_ref_and_hash",
            "evaluation_series_id",
            "evaluation_occurrence_id",
            "evaluation_digest",
            "terminal_result_ref_and_hash",
            "selected_candidate_ref",
            "selected_candidate",
            "selection_available_at",
        )
    }


def delivery_attempt_key_for(attempt: Mapping[str, Any]) -> str:
    return _sha256(
        {
            "schema_identifier_and_version": {
                "identifier": TRADEOFF_SELECTION_DELIVERY_ATTEMPT_SCHEMA_IDENTIFIER,
                "version": TRADEOFF_SELECTION_SCHEMA_VERSION,
            },
            "tradeoff_selection_ref_and_hash": deepcopy(
                dict(attempt["tradeoff_selection_ref_and_hash"])
            ),
            "evaluation_series_id": attempt["evaluation_series_id"],
            "evaluation_occurrence_id": attempt["evaluation_occurrence_id"],
            "evaluation_digest": attempt["evaluation_digest"],
            "terminal_result_ref_and_hash": deepcopy(
                dict(attempt["terminal_result_ref_and_hash"])
            ),
            "selected_candidate_ref": attempt["selected_candidate_ref"],
            "delivered_at": deepcopy(attempt["delivered_at"]),
            "available_at": deepcopy(attempt["available_at"]),
        }
    )


def validation_result_key_for(attempt_ref_and_hash: Mapping[str, Any]) -> str:
    return _sha256(
        {
            "schema_identifier_and_version": {
                "identifier": TRADEOFF_SELECTION_VALIDATION_RESULT_SCHEMA_IDENTIFIER,
                "version": TRADEOFF_SELECTION_SCHEMA_VERSION,
            },
            "delivery_attempt_ref_and_hash": deepcopy(dict(attempt_ref_and_hash)),
        }
    )


def selection_claim_key_for(
    evaluation_series_id: str,
    evaluation_occurrence_id: str,
) -> str:
    return _sha256(
        {
            "schema_identifier_and_version": {
                "identifier": TRADEOFF_SELECTION_CLAIM_SCHEMA_IDENTIFIER,
                "version": TRADEOFF_SELECTION_SCHEMA_VERSION,
            },
            "evaluation_series_id": evaluation_series_id,
            "evaluation_occurrence_id": evaluation_occurrence_id,
        }
    )


def candidate_matches(candidate: Mapping[str, Any], selected_ref: str) -> bool:
    try:
        return candidate_reference(candidate) == selected_ref
    except TradeoffSelectionContractError:
        return False
