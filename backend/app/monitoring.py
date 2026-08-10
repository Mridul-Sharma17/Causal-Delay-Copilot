"""Closed contracts for governed Accept-and-Monitor observations and matches."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .canonical import canonical_json, normalise_temporal, sha256


MONITORING_OBSERVATION_SCHEMA_IDENTIFIER = "monitoring-observation"
MONITORING_SCHEMA_VERSION = "1"
MONITORING_TRIGGER_SCHEMA_IDENTIFIER = "monitoring-escalation-trigger"
MONITORING_REVIEW_REQUEST_SCHEMA_IDENTIFIER = "monitoring-review-request"
MONITORING_MATCH_RESULT_SCHEMA_IDENTIFIER = "monitoring-match-result"
MONITORING_RESPONSE_CODE = "REQUEST_MANAGER_REVIEW"
MONITORING_OPTION_CODE = "ACCEPT_AND_MONITOR"
MONITORING_OPERATORS = frozenset({"LT", "LTE", "EQ", "NEQ", "GTE", "GT", "IN_SET"})
MONITORING_OUTCOMES = frozenset({"NO_REVIEW_REQUEST", MONITORING_RESPONSE_CODE})


class MonitoringContractError(ValueError):
    """A monitoring record cannot satisfy its immutable closed contract."""


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MonitoringContractError(f"{label} is missing")
    return value


def _hash(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != len("sha256:") + 64
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise MonitoringContractError(f"{label} is not a sha256 content hash")
    return value


def _ref_and_hash(value: object, label: str) -> dict[str, str]:
    candidate = _mapping(value)
    if candidate is None:
        raise MonitoringContractError(f"{label} is missing")
    return {
        "reference": _required_string(candidate.get("reference"), f"{label} reference"),
        "content_hash": _hash(candidate.get("content_hash"), f"{label} content hash"),
    }


def _record_id(record: Mapping[str, Any]) -> str:
    for key in (
        "occurrence_id",
        "monitoring_observation_occurrence_id",
        "record_id",
    ):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    raise MonitoringContractError("monitoring observation occurrence_id is missing")


def _record_hash(record: Mapping[str, Any]) -> str:
    supplied = record.get("content_hash")
    supplied_hash = _hash(supplied, "monitoring record content hash")
    content = deepcopy(dict(record))
    content.pop("content_hash", None)
    if sha256(content) != supplied_hash:
        raise MonitoringContractError("monitoring record content hash does not match its content")
    return supplied_hash


def _temporal(value: object, label: str) -> object:
    if isinstance(value, Mapping):
        parsed = normalise_temporal(value)
        if parsed.comparable is None or parsed.field.get("state") != "present":
            raise MonitoringContractError(f"{label} is temporally unresolved")
        return deepcopy(dict(value))
    if not isinstance(value, str) or not value:
        raise MonitoringContractError(f"{label} is missing")
    candidate = value.replace("Z", "+00:00")
    try:
        if "T" in candidate:
            parsed_datetime = datetime.fromisoformat(candidate)
            if parsed_datetime.tzinfo is None:
                raise ValueError
        else:
            date.fromisoformat(candidate)
    except ValueError as error:
        raise MonitoringContractError(f"{label} is invalid") from error
    return value


def _temporal_value(value: object) -> date | datetime | None:
    if isinstance(value, Mapping):
        parsed = normalise_temporal(value)
        return parsed.comparable
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        if "T" not in candidate:
            return date.fromisoformat(candidate)
        parsed_datetime = datetime.fromisoformat(candidate)
        if parsed_datetime.tzinfo is None:
            return None
        return parsed_datetime.astimezone(timezone.utc)
    except ValueError:
        return None


def monitoring_time_equal(left: object, right: object) -> bool:
    left_value = _temporal_value(left)
    right_value = _temporal_value(right)
    if left_value is None or right_value is None:
        return False
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
    return type(left_value) is type(right_value) and left_value == right_value and canonical_json(
        left
    ) == canonical_json(right)


def monitoring_time_compare(left: object, right: object) -> int | None:
    left_value = _temporal_value(left)
    right_value = _temporal_value(right)
    if left_value is None or right_value is None:
        return None
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
    return -1 if left_value < right_value else 1 if left_value > right_value else 0


def _loose_ref(
    record: Mapping[str, Any],
    *,
    nested_key: str,
    reference_key: str,
    hash_key: str,
    label: str,
) -> dict[str, str]:
    nested = record.get(nested_key)
    if nested is not None:
        return _ref_and_hash(nested, label)
    return _ref_and_hash(
        {
            "reference": record.get(reference_key),
            "content_hash": record.get(hash_key),
        },
        label,
    )


def _typed_value(
    value: object,
    *,
    value_type: str,
    unit: str,
    label: str,
) -> object:
    if isinstance(value, Mapping):
        state = value.get("state")
        if state != "present":
            raise MonitoringContractError(f"{label} is unavailable")
        value = value.get("value")
    if value_type == "DECIMAL":
        if not isinstance(value, str) or not value.startswith("decimal:"):
            raise MonitoringContractError(f"{label} is not a canonical decimal")
        try:
            parsed = Decimal(value.split(":", 1)[1])
        except (InvalidOperation, ValueError) as error:
            raise MonitoringContractError(f"{label} is not a canonical decimal") from error
        if not parsed.is_finite():
            raise MonitoringContractError(f"{label} is not a finite decimal")
    elif value_type in {"INTEGER", "INT"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise MonitoringContractError(f"{label} is not an integer")
    elif value_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise MonitoringContractError(f"{label} is not a boolean")
    elif value_type in {"STRING", "TEXT"}:
        if not isinstance(value, str):
            raise MonitoringContractError(f"{label} is not a string")
    elif value_type in {"DATE", "DATETIME", "INSTANT"}:
        _temporal(value, label)
    else:
        raise MonitoringContractError(f"{label} has an unsupported value type")
    if not isinstance(unit, str) or not unit:
        raise MonitoringContractError(f"{label} unit is missing")
    return deepcopy(value)


def _typed_equal(left: object, right: object, *, value_type: str) -> bool:
    if value_type == "DECIMAL":
        try:
            left_decimal = (
                left
                if isinstance(left, Decimal)
                else Decimal(str(left).split(":", 1)[1])
            )
            right_decimal = (
                right
                if isinstance(right, Decimal)
                else Decimal(str(right).split(":", 1)[1])
            )
            return left_decimal == right_decimal
        except (InvalidOperation, IndexError, ValueError):
            return False
    if value_type in {"DATE", "DATETIME", "INSTANT"}:
        return monitoring_time_compare(left, right) == 0
    return canonical_json(left) == canonical_json(right)


def _source_schema(record: Mapping[str, Any], *, label: str) -> dict[str, str]:
    nested = _mapping(record.get("source_schema")) or _mapping(
        record.get("source_schema_id_version_and_hash")
    )
    source = nested or record
    return {
        "identifier": _required_string(
            source.get("identifier", source.get("source_schema_identifier")),
            f"{label} identifier",
        ),
        "version": _required_string(
            source.get("version", source.get("source_schema_version")),
            f"{label} version",
        ),
        "content_hash": _hash(
            source.get("content_hash", source.get("source_schema_content_hash")),
            f"{label} content hash",
        ),
    }


def _observation_definition(record: Mapping[str, Any]) -> dict[str, Any]:
    registry = _mapping(record.get("observation_registry")) or record
    mapping = _mapping(
        registry.get("mapping_manifest_ref_and_hash")
        or registry.get("source_mapping_manifest_ref_and_hash")
    )
    if mapping is None:
        mapping = {
            "reference": registry.get("mapping_manifest_ref"),
            "content_hash": registry.get("mapping_manifest_hash"),
        }
    source_schema = _source_schema(registry, label="observation source schema")
    mapping_ref = _ref_and_hash(mapping, "observation source mapping manifest")
    return {
        "registry_identifier": _required_string(
            registry.get("registry_identifier", record.get("observation_registry_id")),
            "observation registry identifier",
        ),
        "registry_version": _required_string(
            registry.get("registry_version", record.get("observation_registry_version")),
            "observation registry version",
        ),
        "observation_code": _required_string(
            registry.get("observation_code", record.get("observation_code")),
            "observation code",
        ),
        "value_type": _required_string(
            registry.get("value_type", record.get("value_type")),
            "observation value type",
        ),
        "unit": _required_string(
            registry.get("unit", record.get("observed_unit")),
            "observation unit",
        ),
        "source_schema": source_schema,
        "mapping_manifest_ref_and_hash": mapping_ref,
        "mapping_entry_code": _required_string(
            registry.get("mapping_entry_code", record.get("mapping_entry_code")),
            "observation mapping entry code",
        ),
    }


def normalize_monitoring_trigger(
    trigger: Mapping[str, Any],
    *,
    require_fully_specified: bool = True,
) -> dict[str, Any]:
    if not isinstance(trigger, Mapping):
        raise MonitoringContractError("monitoring trigger is invalid")
    record = deepcopy(dict(trigger))
    if record.get("schema_identifier") != MONITORING_TRIGGER_SCHEMA_IDENTIFIER:
        raise MonitoringContractError("monitoring trigger schema is unsupported")
    if record.get("schema_version") != MONITORING_SCHEMA_VERSION:
        raise MonitoringContractError("monitoring trigger schema version is unsupported")
    content_hash = _record_hash(record)
    trigger_id = _required_string(
        record.get("trigger_id", record.get("record_id")), "monitoring trigger id"
    )
    trigger_version = _required_string(
        record.get("trigger_version", record.get("version", "1")),
        "monitoring trigger version",
    )
    trigger_registry_identifier = _required_string(
        record.get("registry_identifier"), "monitoring trigger registry identifier"
    )
    trigger_registry_version = _required_string(
        record.get("registry_version", "1"), "monitoring trigger registry version"
    )
    if record.get("option_code") != MONITORING_OPTION_CODE or record.get("option_version") != "1":
        raise MonitoringContractError("monitoring trigger option identity is invalid")
    raw_modes = record.get("trigger_modes")
    if raw_modes is None:
        raw_modes = [record.get("trigger_mode")]
    if not isinstance(raw_modes, list) or not raw_modes:
        raise MonitoringContractError("monitoring trigger modes are missing")
    modes = [
        _required_string(mode, "monitoring trigger mode").upper() for mode in raw_modes
    ]
    if len(modes) != len(set(modes)) or modes != sorted(modes):
        raise MonitoringContractError("monitoring trigger modes are not sorted and unique")
    if any(mode not in {"REACTIVE", "PROACTIVE"} for mode in modes):
        raise MonitoringContractError("monitoring trigger mode is unsupported")
    singular_mode = record.get("trigger_mode")
    if singular_mode is not None and (
        not isinstance(singular_mode, str) or singular_mode.upper() not in modes
    ):
        raise MonitoringContractError("monitoring trigger mode identity is inconsistent")
    for composite_field in (
        "conditions",
        "composite_predicate",
        "observations",
        "operators",
        "response_codes",
        "subpredicates",
    ):
        if composite_field in record and record[composite_field] not in (None, [], {}):
            raise MonitoringContractError("monitoring trigger predicate is composite")
    definition = _observation_definition(record)
    operator = record.get("operator")
    if not isinstance(operator, str) or operator not in MONITORING_OPERATORS:
        raise MonitoringContractError("monitoring trigger operator is not atomic")
    threshold = record.get("threshold")
    allowed_values: list[object] | None = None
    if operator == "IN_SET":
        raw_allowed = record.get("allowed_values", record.get("allowed_set"))
        if isinstance(raw_allowed, Mapping):
            raw_allowed = raw_allowed.get("values")
        if not isinstance(raw_allowed, list) or not raw_allowed:
            raise MonitoringContractError("monitoring trigger allowed set is missing")
        allowed_values = [
            _typed_value(
                value,
                value_type=definition["value_type"],
                unit=definition["unit"],
                label="monitoring trigger allowed value",
            )
            for value in raw_allowed
        ]
        if len({canonical_json(value) for value in allowed_values}) != len(allowed_values):
            raise MonitoringContractError("monitoring trigger allowed set contains duplicates")
        if allowed_values != sorted(allowed_values, key=canonical_json):
            raise MonitoringContractError("monitoring trigger allowed set is not canonical")
        threshold = None
    else:
        threshold_map = _mapping(threshold)
        if threshold_map is None:
            raise MonitoringContractError("monitoring trigger threshold is missing")
        threshold_value_type = threshold_map.get("value_type", definition["value_type"])
        threshold_unit = threshold_map.get("unit", definition["unit"])
        if threshold_value_type != definition["value_type"] or threshold_unit != definition["unit"]:
            raise MonitoringContractError("monitoring trigger threshold type or unit disagrees with observation")
        threshold = {
            "value_type": definition["value_type"],
            "value": _typed_value(
                threshold_map.get("value"),
                value_type=definition["value_type"],
                unit=definition["unit"],
                label="monitoring trigger threshold",
            ),
            "unit": definition["unit"],
        }
    if record.get("response_code", record.get("response")) != MONITORING_RESPONSE_CODE:
        raise MonitoringContractError("monitoring trigger response is not manager review")
    state = record.get("state", record.get("lifecycle_status"))
    lifecycle_status = record.get("lifecycle_status")
    review_status = record.get("review_status")
    if state not in {"PROVISIONAL", "APPROVED", "REJECTED", "RETIRED"}:
        raise MonitoringContractError("monitoring trigger lifecycle state is unsupported")
    if lifecycle_status is not None and lifecycle_status not in {"ACTIVE", "RETIRED"}:
        raise MonitoringContractError("monitoring trigger lifecycle status is unsupported")
    if record.get("published_at") is not None:
        published_at = _temporal(record.get("published_at"), "monitoring trigger published_at")
    else:
        published_at = None
    review_times = []
    for review_key in ("review_date", "review_available_at", "reviewed_at"):
        if record.get(review_key) is not None:
            review_times.append(
                (review_key, _temporal(record[review_key], f"monitoring trigger {review_key}"))
            )
    source_refs = record.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        raise MonitoringContractError("monitoring trigger source_refs are missing")
    normalized_source_refs = [_ref_and_hash(item, "monitoring trigger source reference") for item in source_refs]
    if (
        record.get("provenance") is None
        or not isinstance(record.get("provenance"), Mapping)
        or not record.get("provenance")
    ):
        raise MonitoringContractError("monitoring trigger provenance is missing")
    for supersession_key in ("predecessor_version_ref", "supersession_ref"):
        if record.get(supersession_key) is not None:
            _ref_and_hash(record[supersession_key], f"monitoring trigger {supersession_key}")
    if require_fully_specified:
        if state != "APPROVED" or review_status != "APPROVED" or lifecycle_status != "ACTIVE":
            raise MonitoringContractError("monitoring trigger is not approved and active")
        for key in ("reviewer_role", "review_date", "review_reference", "review_reason_code"):
            if not record.get(key):
                raise MonitoringContractError(f"monitoring trigger {key} is missing")
        if published_at is None:
            raise MonitoringContractError("monitoring trigger published_at is missing")
        for review_key, review_time in review_times:
            comparison = monitoring_time_compare(review_time, published_at)
            if comparison is None:
                raise MonitoringContractError(
                    f"monitoring trigger {review_key} is not comparable with published_at"
                )
            if comparison > 0:
                raise MonitoringContractError(
                    f"monitoring trigger {review_key} is later than published_at"
                )
    normalized = {
        "record": record,
        "content_hash": content_hash,
        "trigger_id": trigger_id,
        "trigger_version": trigger_version,
        "trigger_id_and_version": {"id": trigger_id, "version": trigger_version},
        "trigger_registry_identifier": trigger_registry_identifier,
        "trigger_registry_version": trigger_registry_version,
        "option_code": MONITORING_OPTION_CODE,
        "option_version": "1",
        "trigger_modes": modes,
        "observation_registry": definition,
        "operator": operator,
        "threshold": deepcopy(threshold),
        "allowed_values": deepcopy(allowed_values),
        "response_code": MONITORING_RESPONSE_CODE,
        "state": state,
        "lifecycle_status": lifecycle_status,
        "review_status": review_status,
        "published_at": published_at,
        "source_refs": normalized_source_refs,
        "provenance": deepcopy(dict(record["provenance"])),
    }
    return normalized


def _observation_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema_identifier") != MONITORING_OBSERVATION_SCHEMA_IDENTIFIER:
        raise MonitoringContractError("monitoring observation schema is unsupported")
    if record.get("schema_version") != MONITORING_SCHEMA_VERSION:
        raise MonitoringContractError("monitoring observation schema version is unsupported")
    definition = _observation_definition(record)
    source_mapping = _loose_ref(
        record,
        nested_key="source_mapping_manifest_ref_and_hash",
        reference_key="mapping_manifest_ref",
        hash_key="mapping_manifest_hash",
        label="monitoring observation source mapping manifest",
    )
    source_schema = _source_schema(record, label="monitoring observation source schema")
    source_record = _loose_ref(
        record,
        nested_key="source_record_ref_and_hash",
        reference_key="source_record_ref",
        hash_key="source_record_content_hash",
        label="monitoring observation source record",
    )
    subject_identity = _required_string(
        record.get("subject_identity", record.get("canonical_subject_identity")),
        "monitoring observation subject identity",
    )
    value_type = _required_string(
        record.get("value_type", definition["value_type"]),
        "monitoring observation value type",
    )
    unit = _required_string(record.get("observed_unit", definition["unit"]), "monitoring observation unit")
    if value_type != definition["value_type"] or unit != definition["unit"]:
        raise MonitoringContractError("monitoring observation type or unit disagrees with its registry")
    value = _typed_value(
        record.get("observed_value", record.get("value")),
        value_type=value_type,
        unit=unit,
        label="monitoring observation value",
    )
    observed_at = _temporal(record.get("observed_at"), "monitoring observation observed_at")
    first_available_at = _temporal(
        record.get("first_available_at"),
        "monitoring observation first_available_at",
    )
    available_at = _temporal(record.get("available_at"), "monitoring observation available_at")
    if not monitoring_time_equal(first_available_at, available_at):
        raise MonitoringContractError("monitoring observation available_at is not source first availability")
    return {
        "schema_identifier_and_version": {
            "identifier": MONITORING_OBSERVATION_SCHEMA_IDENTIFIER,
            "version": MONITORING_SCHEMA_VERSION,
        },
        "observation_registry_id_version_and_code": {
            "registry_identifier": definition["registry_identifier"],
            "registry_version": definition["registry_version"],
            "observation_code": definition["observation_code"],
        },
        "source_mapping_manifest_ref_and_hash": source_mapping,
        "mapping_entry_code": definition["mapping_entry_code"],
        "canonical_subject_identity": subject_identity,
        "typed_value_and_unit": {
            "value_type": value_type,
            "value": value,
            "unit": unit,
        },
        "source_schema_id_version_and_hash": source_schema,
        "source_record_ref_and_hash": source_record,
        "observed_at": observed_at,
        "source_record_first_available_at": first_available_at,
    }


def monitoring_observation_key_for(observation: Mapping[str, Any]) -> str:
    canonical_fields = observation.get("canonical_fields")
    if isinstance(canonical_fields, Mapping):
        return sha256(canonical_fields)
    return sha256(_observation_fields(observation))


def normalize_monitoring_observation(
    observation: Mapping[str, Any],
    *,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise MonitoringContractError("monitoring observation is invalid")
    record = deepcopy(dict(observation))
    if allow_legacy and not any(
        key in record
        for key in (
            "observation_registry_id",
            "observation_registry_version",
            "observation_code",
            "observation_registry",
        )
    ):
        if record.get("schema_identifier") != MONITORING_OBSERVATION_SCHEMA_IDENTIFIER:
            raise MonitoringContractError("monitoring observation schema is unsupported")
        if record.get("schema_version") != MONITORING_SCHEMA_VERSION:
            raise MonitoringContractError("monitoring observation schema version is unsupported")
        content_hash = _record_hash(record)
        occurrence_id = _record_id(record)
        key = record.get("monitoring_observation_key")
        if not isinstance(key, str) or not key:
            key = f"legacy:{record.get('observation_ref', occurrence_id)}"
        return {
            "record": record,
            "content_hash": content_hash,
            "occurrence_id": occurrence_id,
            "monitoring_observation_key": key,
            "legacy": True,
            "canonical_fields": None,
        }
    if record.get("schema_identifier") != MONITORING_OBSERVATION_SCHEMA_IDENTIFIER:
        raise MonitoringContractError("monitoring observation schema is unsupported")
    if record.get("schema_version") != MONITORING_SCHEMA_VERSION:
        raise MonitoringContractError("monitoring observation schema version is unsupported")
    content_hash = _record_hash(record)
    occurrence_id = _record_id(record)
    canonical_fields = _observation_fields(record)
    key = monitoring_observation_key_for(record)
    supplied_key = record.get("monitoring_observation_key")
    if supplied_key is not None and supplied_key != key:
        raise MonitoringContractError("monitoring observation logical key does not match its canonical fields")
    return {
        "record": record,
        "content_hash": content_hash,
        "occurrence_id": occurrence_id,
        "monitoring_observation_key": key,
        "legacy": False,
        "canonical_fields": canonical_fields,
    }


def _canonical_value(value: object, *, value_type: str, unit: str, label: str) -> object:
    return _typed_value(value, value_type=value_type, unit=unit, label=label)


def evaluate_monitoring_predicate(
    trigger: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> bool:
    normalized_trigger = (
        trigger
        if "record" in trigger and "observation_registry" in trigger
        else normalize_monitoring_trigger(trigger)
    )
    normalized_observation = (
        observation
        if "canonical_fields" in observation
        else normalize_monitoring_observation(observation)
    )
    canonical_fields = normalized_observation.get("canonical_fields")
    if not isinstance(canonical_fields, Mapping):
        raise MonitoringContractError("legacy monitoring observation cannot evaluate a predicate")
    definition = normalized_trigger["observation_registry"]
    observation_definition = {
        "registry_identifier": canonical_fields["observation_registry_id_version_and_code"][
            "registry_identifier"
        ],
        "registry_version": canonical_fields["observation_registry_id_version_and_code"][
            "registry_version"
        ],
        "observation_code": canonical_fields["observation_registry_id_version_and_code"][
            "observation_code"
        ],
        "value_type": canonical_fields["typed_value_and_unit"]["value_type"],
        "unit": canonical_fields["typed_value_and_unit"]["unit"],
        "source_schema": canonical_fields["source_schema_id_version_and_hash"],
        "mapping_manifest_ref_and_hash": canonical_fields[
            "source_mapping_manifest_ref_and_hash"
        ],
        "mapping_entry_code": canonical_fields["mapping_entry_code"],
    }
    for key in (
        "registry_identifier",
        "registry_version",
        "observation_code",
        "value_type",
        "unit",
        "mapping_entry_code",
    ):
        if definition[key] != observation_definition[key]:
            if key == "unit":
                raise MonitoringContractError("monitoring observation unit disagrees with trigger definition")
            raise MonitoringContractError("monitoring observation disagrees with trigger definition")
    if definition["source_schema"] != observation_definition["source_schema"]:
        raise MonitoringContractError("monitoring observation source schema disagrees with trigger definition")
    if definition["mapping_manifest_ref_and_hash"] != observation_definition[
        "mapping_manifest_ref_and_hash"
    ]:
        raise MonitoringContractError("monitoring observation mapping disagrees with trigger definition")
    value = canonical_fields["typed_value_and_unit"]["value"]
    value_type = definition["value_type"]
    unit = definition["unit"]
    operator = normalized_trigger["operator"]
    if operator in {"LT", "LTE", "GTE", "GT"} and value_type in {"BOOLEAN", "STRING", "TEXT"}:
        raise MonitoringContractError("monitoring trigger requires an orderable observation type")
    if operator in {"EQ", "NEQ"}:
        _canonical_value(value, value_type=value_type, unit=unit, label="monitoring observation value")
    threshold = normalized_trigger.get("threshold")
    if operator == "IN_SET":
        allowed = normalized_trigger.get("allowed_values")
        if not isinstance(allowed, list):
            raise MonitoringContractError("monitoring trigger allowed set is missing")
        return any(
            _typed_equal(value, item, value_type=value_type)
            for item in allowed
        )
    if not isinstance(threshold, Mapping):
        raise MonitoringContractError("monitoring trigger threshold is missing")
    threshold_value = threshold["value"]
    if value_type == "DECIMAL":
        left: Any = Decimal(str(value).split(":", 1)[1])
        right: Any = Decimal(str(threshold_value).split(":", 1)[1])
    elif value_type in {"INTEGER", "INT"}:
        left, right = value, threshold_value
    elif value_type in {"DATE", "DATETIME", "INSTANT"}:
        comparison = monitoring_time_compare(value, threshold_value)
        if comparison is None:
            raise MonitoringContractError("monitoring predicate temporal comparison is unresolved")
        left, right = comparison, 0
    else:
        left, right = value, threshold_value
    if operator == "LT":
        return left < right
    if operator == "LTE":
        return left <= right
    if operator == "EQ":
        return _typed_equal(left, right, value_type=value_type)
    if operator == "NEQ":
        return not _typed_equal(left, right, value_type=value_type)
    if operator == "GTE":
        return left >= right
    if operator == "GT":
        return left > right
    raise MonitoringContractError("monitoring trigger operator is unsupported")


def monitoring_review_request_key_for(fields: Mapping[str, Any]) -> str:
    expected = {
        key: deepcopy(fields.get(key))
        for key in (
            "evaluation_series_id",
            "recommendation_occurrence_id",
            "trigger_id_and_version",
            "monitoring_observation_key",
            "monitoring_observation_ref_and_hash",
            "accepted_selection_claim_ref_and_hash_or_null",
            "currentness_operation_ref_and_hash",
            "currentness_check_ref_and_hash",
        )
    }
    expected["response_code"] = MONITORING_RESPONSE_CODE
    return sha256(expected)


def monitoring_match_result_key_for(fields: Mapping[str, Any]) -> str:
    expected = {
        key: deepcopy(fields.get(key))
        for key in (
            "recommendation_ref_and_hash",
            "trigger_id_and_version",
            "monitoring_observation_key",
            "monitoring_observation_ref_and_hash",
            "accepted_selection_claim_ref_and_hash_or_null",
            "currentness_operation_ref_and_hash",
            "currentness_check_ref_and_hash",
            "match_outcome",
            "monitoring_review_request_key_or_null",
        )
    }
    return sha256(expected)


def trigger_id_and_version(trigger: Mapping[str, Any]) -> dict[str, str]:
    normalized = (
        trigger
        if "trigger_id_and_version" in trigger
        else normalize_monitoring_trigger(trigger)
    )
    candidate = normalized.get("trigger_id_and_version")
    if not isinstance(candidate, Mapping):
        raise MonitoringContractError("monitoring trigger identity is missing")
    return {
        "id": _required_string(candidate.get("id"), "monitoring trigger id"),
        "version": _required_string(candidate.get("version"), "monitoring trigger version"),
    }
