from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256(value: object) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def safe_sha256(value: object) -> str:
    """Hash untrusted JSON-shaped input without accepting it as canonical data."""
    try:
        return sha256(value)
    except (TypeError, ValueError, OverflowError):
        return sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=True,
            )
        )


def field(state: str, value: object | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"state": state}
    if state == "present":
        result["value"] = value
    return result


def timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class Temporal:
    field: dict[str, Any]
    comparable: date | datetime | None


def normalise_temporal(value: Any) -> Temporal:
    if not isinstance(value, Mapping):
        return Temporal(field("invalid"), None)
    raw_value = value.get("value")
    canonical_normalised_value = value.get("normalized_value")
    kind = value.get("kind")
    precision = value.get("precision")
    timezone_status = value.get("timezone_status")
    source_timezone = value.get("source_timezone")
    if isinstance(source_timezone, Mapping):
        source_timezone = source_timezone.get("value")
    if raw_value is None and isinstance(canonical_normalised_value, str):
        raw_value = value.get("source_value")
    if not all(
        isinstance(item, str) and item
        for item in (raw_value, kind, precision, timezone_status)
    ):
        return Temporal(field("invalid"), None)
    if kind not in {"date", "local_datetime", "instant"}:
        return Temporal(field("invalid"), None)
    if timezone_status not in {"known", "assumed", "unknown", "not_applicable"}:
        return Temporal(field("invalid"), None)
    if timezone_status in {"known", "assumed"} and not isinstance(
        source_timezone, str
    ):
        return Temporal(field("unresolved"), None)
    if timezone_status == "not_applicable" and source_timezone is not None:
        return Temporal(field("invalid"), None)

    normalised = (
        canonical_normalised_value
        if isinstance(canonical_normalised_value, str)
        else raw_value
    )
    comparable: date | datetime | None = None
    try:
        if kind == "date":
            comparable = date.fromisoformat(raw_value)
        elif kind == "instant":
            parsed = datetime.fromisoformat(normalised)
            if parsed.tzinfo is None or timezone_status not in {"known", "assumed"}:
                return Temporal(field("unresolved"), None)
            comparable = parsed.astimezone(timezone.utc)
            normalised = comparable.isoformat()
        else:
            datetime.fromisoformat(str(normalised))
            if timezone_status in {"known", "assumed"}:
                return Temporal(field("unresolved"), None)
    except ValueError:
        return Temporal(field("invalid"), None)

    timezone_field = (
        field("present", source_timezone)
        if timezone_status in {"known", "assumed"}
        else field("not_applicable")
        if timezone_status == "not_applicable"
        else field("unresolved")
    )
    return Temporal(
        field(
            "present",
            {
                "kind": kind,
                "source_value": raw_value,
                "normalized_value": normalised,
                "precision": precision,
                "timezone_status": timezone_status,
                "source_timezone": timezone_field,
            },
        ),
        comparable,
    )


def compare_temporal(left: Temporal, right: Temporal) -> int | None:
    if left.field.get("state") != "present" or right.field.get("state") != "present":
        return None
    left_value = left.field.get("value")
    right_value = right.field.get("value")
    if not isinstance(left_value, Mapping) or not isinstance(right_value, Mapping):
        return None
    if left.comparable is None or right.comparable is None:
        return None
    left_kind = left_value.get("kind")
    right_kind = right_value.get("kind")
    left_comparable: date | datetime = left.comparable
    right_comparable: date | datetime = right.comparable
    if left_kind != right_kind:
        if left_kind not in {"date", "local_datetime", "instant"} or right_kind not in {
            "date",
            "local_datetime",
            "instant",
        }:
            return None
        left_comparable = (
            left.comparable
            if left_kind == "date"
            else left.comparable.date()
        )
        right_comparable = (
            right.comparable
            if right_kind == "date"
            else right.comparable.date()
        )
        if left_comparable == right_comparable:
            return None
    if left_comparable < right_comparable:
        return -1
    if left_comparable > right_comparable:
        return 1
    return 0


def equal_temporal(left: Temporal, right: Temporal) -> bool | None:
    comparison = compare_temporal(left, right)
    if comparison is None:
        return None
    left_value = left.field["value"]
    right_value = right.field["value"]
    return (
        comparison == 0
        and left_value.get("precision") == right_value.get("precision")
        and left_value.get("timezone_status") == right_value.get("timezone_status")
    )
