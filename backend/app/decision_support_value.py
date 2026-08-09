from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
import math
import re
from typing import Any, Mapping, Sequence


_DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_MAX_INTEGER_BITS = 4096
_VALID_DURATION_BASES = {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}
_OPTION_DISPLAY_ORDER = {
    "PROTECTED_PRODUCTION_SLOT": 10,
    "QUALIFIED_SOURCE_SPLIT": 20,
    "PREQUALIFIED_ALTERNATE": 30,
    "RELEASE_TIMING_ADJUSTMENT": 40,
    "CAPACITY_BACKED_ACCELERATION": 50,
    "PHASED_DELIVERY": 60,
    "DEPENDENT_WORK_RESEQUENCING": 70,
    "CONTRACTUAL_ESCALATION": 80,
    "ACCEPT_AND_MONITOR": 90,
    "PROTECTED_SLOT_WITH_PHASED_DELIVERY": 100,
}
_VALUE_REASON_PRIORITIES = {
    "EXPOSURE_EFFECT_UNAVAILABLE": 490,
    "RECOVERABLE_FRACTION_UNAVAILABLE": 500,
    "RECOVERABLE_FRACTION_INVALID": 510,
    "CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE": 520,
    "CRITICAL_PATH_TRANSLATION_FRACTION_INVALID": 530,
    "CRITICAL_PATH_DELAY_RATE_UNAVAILABLE": 540,
    "CRITICAL_PATH_DELAY_RATE_INVALID": 550,
    "CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE": 560,
    "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID": 570,
    "ACTION_COST_UNAVAILABLE": 580,
    "ACTION_COST_INVALID": 590,
    "NON_POSITIVE_CENTRAL_NET_VALUE": 600,
}


@dataclass(frozen=True)
class ValueContext:
    present: bool
    envelope: Mapping[str, Any]
    rate: Mapping[str, Any] | None
    direct_costs: tuple[Mapping[str, Any], ...]
    assumptions: tuple[Mapping[str, Any], ...]
    effect: Mapping[str, Any] | None
    duration_basis: str | None


@dataclass(frozen=True)
class ValuePreparation:
    context: ValueContext
    error: dict[str, str] | None


@dataclass(frozen=True)
class ValueProjection:
    fields: dict[str, Any]
    suppression_reasons: list[dict[str, Any]]


def canonical_value_inputs(value_context: ValueContext) -> dict[str, Any] | None:
    if not value_context.present:
        return None

    envelope = deepcopy(dict(value_context.envelope))
    for key in (
        "cost_of_critical_path_delay_per_day",
        "critical_path_delay_rate",
        "cost_of_delay",
        "rate",
        "direct_action_costs",
        "action_costs",
        "direct_costs",
        "option_costs",
        "benefit_assumptions",
        "assumptions",
        "cost_inputs",
    ):
        envelope.pop(key, None)

    def record_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            _OPTION_DISPLAY_ORDER.get(str(record.get("option_code")), 10**9),
            str(record.get("trigger_mode", "")),
            str(
                _first(record, ("assumption_kind", "kind", "type", "input_kind"))
                or ""
            ),
            str(_record_identifier(record) or ""),
        )

    option_costs = sorted(
        (deepcopy(dict(record)) for record in value_context.direct_costs),
        key=record_key,
    )
    assumptions = sorted(
        (deepcopy(dict(record)) for record in value_context.assumptions),
        key=record_key,
    )
    envelope["cost_inputs"] = {
        "critical_path_delay_rate": (
            deepcopy(dict(value_context.rate)) if value_context.rate is not None else None
        ),
        "option_costs": option_costs,
    }
    envelope["benefit_assumptions"] = assumptions
    return envelope


def _error(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "reason": reason}


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _check_integer_bits(value: int) -> None:
    if abs(value).bit_length() > _MAX_INTEGER_BITS:
        raise ValueError("DECISION_SUPPORT_ARITHMETIC_INVALID")


def _checked(value: Fraction) -> Fraction:
    _check_integer_bits(value.numerator)
    _check_integer_bits(value.denominator)
    return value


def _add(left: Fraction, right: Fraction) -> Fraction:
    return _checked(left + right)


def _subtract(left: Fraction, right: Fraction) -> Fraction:
    return _checked(left - right)


def _multiply(left: Fraction, right: Fraction) -> Fraction:
    return _checked(left * right)


def _fraction_from_decimal(value: object) -> Fraction | None:
    if not isinstance(value, str) or not value.startswith("decimal:"):
        return None
    text = value.split(":", 1)[1]
    if not _DECIMAL_RE.fullmatch(text):
        return None
    negative = text.startswith("-")
    unsigned = text[1:] if negative else text
    integer_part, _, fractional_part = unsigned.partition(".")
    fractional_digits = fractional_part if fractional_part else ""
    if len(integer_part) > 20 or len(fractional_digits) > 18:
        return None
    if len(integer_part) + len(fractional_digits) > 38:
        return None
    if fractional_part and fractional_part.endswith("0"):
        return None
    if len(integer_part) == 20 and int(integer_part) >= 10**20:
        return None
    coefficient = int(integer_part + fractional_digits)
    if negative and coefficient:
        coefficient = -coefficient
    denominator = 10 ** len(fractional_digits)
    try:
        return _checked(Fraction(coefficient, denominator))
    except ValueError:
        return None


def _fraction_from_effect(value: object) -> Fraction | None:
    if isinstance(value, str) and value.startswith("decimal:"):
        return _fraction_from_decimal(value)
    if isinstance(value, str) and value.startswith("f64:"):
        try:
            parsed = float.fromhex(value.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed):
            return None
        try:
            return _checked(Fraction.from_float(parsed))
        except ValueError:
            return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        try:
            return _checked(Fraction(value, 1))
        except ValueError:
            return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        try:
            return _checked(Fraction.from_float(value))
        except ValueError:
            return None
    return None


def _pair(value: Fraction) -> dict[str, str]:
    _checked(value)
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def _pair_range(values: Sequence[Fraction]) -> dict[str, dict[str, str]]:
    return {
        "lower": _pair(values[0]),
        "central": _pair(values[1]),
        "upper": _pair(values[2]),
    }


def _record_identifier(record: Mapping[str, Any]) -> str | None:
    for key in (
        "record_id",
        "assumption_id",
        "cost_id",
        "rate_id",
        "input_id",
    ):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _record_ref(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    reference = _first(
        record,
        (
            "record_id",
            "assumption_id",
            "cost_id",
            "rate_id",
            "input_id",
            "effect_reference",
            "effect_ref",
            "reference",
        ),
    )
    return {
        "reference": reference if isinstance(reference, str) and reference else None,
        "content_hash": _first(record, ("content_hash", "effect_content_hash")),
    }


def _hash_is_valid(record: Mapping[str, Any]) -> bool:
    content_hash = record.get("content_hash")
    if not isinstance(content_hash, str) or not content_hash:
        return False
    try:
        from .canonical import sha256

        content = deepcopy(dict(record))
        content.pop("content_hash", None)
        return sha256(content) == content_hash
    except (TypeError, ValueError):
        return False


def _is_currency(value: object) -> bool:
    return isinstance(value, str) and _ISO_CURRENCY_RE.fullmatch(value) is not None


def _first(value: Mapping[str, Any], keys: Sequence[str]) -> object:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _record_list(value: object, *, key_hint: str | None = None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []
    if any(
        key in value
        for key in (
            "record_id",
            "assumption_id",
            "cost_id",
            "rate_id",
            "option_code",
            "assumption_kind",
            "kind",
            "amount",
            "total",
        )
    ):
        record = dict(value)
        if key_hint is not None and "assumption_kind" not in record:
            record["assumption_kind"] = key_hint
        return [record]
    records: list[dict[str, Any]] = []
    for key, child in value.items():
        if isinstance(child, list):
            for item in child:
                if isinstance(item, Mapping):
                    record = dict(item)
                    if key_hint is not None and "assumption_kind" not in record:
                        record["assumption_kind"] = key_hint
                    records.append(record)
        elif isinstance(child, Mapping):
            record = dict(child)
            if key_hint is not None and "assumption_kind" not in record:
                record["assumption_kind"] = key_hint
            elif key in {
                "recoverable_fraction",
                "recoverable_fraction_assumption",
                "critical_path_translation_fraction",
                "critical_path_translation_fraction_assumption",
                "consequence_benefit",
                "consequence_benefit_assumption",
            } and "assumption_kind" not in record:
                record["assumption_kind"] = key
            records.append(record)
    return records


def _value_envelope(fixture_case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    operational_inputs = _mapping(fixture_case.get("operational_inputs"))
    if operational_inputs is None:
        return None
    for key in (
        "decision_support_value_inputs",
        "value_inputs",
        "projection_inputs",
        "assumption_inputs",
    ):
        candidate = operational_inputs.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _context_value(envelope: Mapping[str, Any], keys: Sequence[str]) -> object:
    for key in keys:
        if key in envelope:
            return envelope[key]
    return None


def _normalize_kind(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _kind_matches(record: Mapping[str, Any], expected: str) -> bool:
    kind = _normalize_kind(
        _first(record, ("assumption_kind", "kind", "type", "input_kind"))
    )
    aliases = {
        "RECOVERABLE_FRACTION": {
            "RECOVERABLE_FRACTION",
            "RECOVERABLE_FRACTION_ASSUMPTION",
        },
        "CRITICAL_PATH_TRANSLATION_FRACTION": {
            "CRITICAL_PATH_TRANSLATION_FRACTION",
            "CRITICAL_PATH_TRANSLATION_FRACTION_ASSUMPTION",
        },
        "CONSEQUENCE_BENEFIT": {
            "CONSEQUENCE_BENEFIT",
            "CONSEQUENCE_BENEFIT_ASSUMPTION",
        },
    }
    return kind in aliases.get(expected, {expected})


def _find_option_record(
    records: Sequence[Mapping[str, Any]],
    *,
    option_code: str,
    trigger_mode: str,
    kind: str | None = None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    candidates: list[Mapping[str, Any]] = []
    for record in records:
        if kind is not None and not _kind_matches(record, kind):
            continue
        record_option = record.get("option_code")
        record_trigger = record.get("trigger_mode")
        if record_option == option_code and record_trigger == trigger_mode:
            candidates.append(record)
    if len(candidates) > 1:
        candidates.sort(key=lambda item: str(_record_identifier(item)))
        return candidates[0], "MULTIPLE"
    return (candidates[0], None) if candidates else (None, None)


def _find_rate(envelope: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str | None]:
    raw = _context_value(
        envelope,
        (
            "cost_of_critical_path_delay_per_day",
            "critical_path_delay_rate",
            "cost_of_delay",
        ),
    )
    if raw is None:
        cost_inputs = _mapping(envelope.get("cost_inputs"))
        if cost_inputs is not None:
            raw = _context_value(
                cost_inputs,
                (
                    "cost_of_critical_path_delay_per_day",
                    "critical_path_delay_rate",
                    "cost_of_delay",
                    "rate",
                ),
            )
    records = _record_list(raw)
    records.sort(key=lambda item: str(_record_identifier(item)))
    if len(records) > 1:
        return records[0], "MULTIPLE"
    return (records[0], None) if records else (None, None)


def _currency_candidates(
    rate: Mapping[str, Any] | None,
    direct_costs: Sequence[Mapping[str, Any]],
    assumptions: Sequence[Mapping[str, Any]],
) -> set[str]:
    values: set[str] = set()
    for record in [rate, *direct_costs, *assumptions]:
        if not isinstance(record, Mapping):
            continue
        currency = record.get("currency")
        if _is_currency(currency):
            values.add(currency)
    return values


def _effect_record(
    fixture_case: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    def with_provenance(effect: Mapping[str, Any]) -> Mapping[str, Any]:
        enriched = dict(effect)
        if subject_verdict is not None:
            subject_reference = subject_verdict.get("record_id")
            if isinstance(subject_reference, str) and subject_reference:
                enriched.setdefault("effect_reference", subject_reference)
            subject_hash = subject_verdict.get("content_hash")
            if isinstance(subject_hash, str) and subject_hash:
                enriched.setdefault("effect_content_hash", subject_hash)
        return enriched

    if isinstance(subject_verdict, Mapping):
        effect = subject_verdict.get("effect")
        if isinstance(effect, Mapping):
            return with_provenance(effect)
    for key in ("effect", "verified_effect", "exposure_effect"):
        effect = fixture_case.get(key)
        if isinstance(effect, Mapping):
            return with_provenance(effect)
    evidence = _mapping(fixture_case.get("evidence"))
    if evidence is not None:
        verdict = _mapping(evidence.get("subject_verdict"))
        effect = _mapping(verdict.get("effect")) if verdict is not None else None
        if effect is not None:
            return with_provenance(effect)
    return None


def prepare_value_inputs(
    *,
    fixture_case: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
) -> ValuePreparation:
    operational_inputs = _mapping(fixture_case.get("operational_inputs"))
    value_keys = (
        "decision_support_value_inputs",
        "value_inputs",
        "projection_inputs",
        "assumption_inputs",
    )
    present_key = next(
        (key for key in value_keys if operational_inputs is not None and key in operational_inputs),
        None,
    )
    envelope = _value_envelope(fixture_case)
    if present_key is not None and envelope is None:
        return ValuePreparation(
            context=ValueContext(
                present=True,
                envelope={},
                rate=None,
                direct_costs=(),
                assumptions=(),
                effect=_effect_record(fixture_case, subject_verdict),
                duration_basis=None,
            ),
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Decision Support value input envelope must be an object.",
            ),
        )
    if envelope is None:
        return ValuePreparation(
            context=ValueContext(
                present=False,
                envelope={},
                rate=None,
                direct_costs=(),
                assumptions=(),
                effect=_effect_record(fixture_case, subject_verdict),
                duration_basis=None,
            ),
            error=None,
        )
    rate, rate_error = _find_rate(envelope)
    direct_costs_raw = _context_value(
        envelope,
        ("direct_action_costs", "action_costs", "direct_costs", "option_costs"),
    )
    if direct_costs_raw is None:
        cost_inputs = _mapping(envelope.get("cost_inputs"))
        direct_costs_raw = (
            _context_value(
                cost_inputs,
                ("direct_action_costs", "action_costs", "direct_costs", "option_costs"),
            )
            if cost_inputs is not None
            else None
        )
    direct_costs = tuple(_record_list(direct_costs_raw))
    assumptions = tuple(
        _record_list(
            _context_value(envelope, ("benefit_assumptions", "assumptions"))
        )
    )
    if rate_error == "MULTIPLE":
        return ValuePreparation(
            context=ValueContext(
                True,
                envelope,
                rate,
                direct_costs,
                assumptions,
                _effect_record(fixture_case, subject_verdict),
                None,
            ),
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "More than one case-scoped critical-path delay rate was supplied.",
            ),
        )
    currencies = _currency_candidates(rate, direct_costs, assumptions)
    if len(currencies) > 1:
        return ValuePreparation(
            context=ValueContext(
                True,
                envelope,
                rate,
                direct_costs,
                assumptions,
                _effect_record(fixture_case, subject_verdict),
                None,
            ),
            error=_error(
                "DECISION_SUPPORT_CURRENCY_MISMATCH",
                "Every present monetized Decision Support input must use one declared currency; conversion is unavailable.",
            ),
        )
    effect = _effect_record(fixture_case, subject_verdict)
    effect_basis = (
        _first(effect, ("duration_basis", "canonical_slippage_duration_basis"))
        if effect is not None
        else None
    )
    declared_basis = _context_value(
        envelope,
        ("canonical_slippage_duration_basis", "resolved_duration_basis"),
    )
    if effect is not None and declared_basis is not None and declared_basis != effect_basis:
        return ValuePreparation(
            context=ValueContext(
                True,
                envelope,
                rate,
                direct_costs,
                assumptions,
                effect,
                declared_basis if isinstance(declared_basis, str) else None,
            ),
            error=_error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The declared Decision Support duration basis disagrees with the verified effect basis.",
            ),
        )
    return ValuePreparation(
        context=ValueContext(
            present=True,
            envelope=envelope,
            rate=rate,
            direct_costs=direct_costs,
            assumptions=assumptions,
            effect=effect,
            duration_basis=(
                effect_basis
                if isinstance(effect_basis, str)
                else declared_basis
                if isinstance(declared_basis, str)
                else None
            ),
        ),
        error=None,
    )


def _common_input_error(
    record: Mapping[str, Any],
    *,
    option_code: str | None,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    constraints_as_of: datetime,
) -> str | None:
    if _record_identifier(record) is None or not _hash_is_valid(record):
        return "MALFORMED"
    statuses = [
        record.get(key)
        for key in ("state", "review_status", "approval_status", "status")
        if key in record
    ]
    if not statuses or any(status != "APPROVED" for status in statuses):
        return "NOT_APPROVED"
    if record.get("approval_scope") not in {None, "SYNTHETIC_CONFORMANCE_ONLY"}:
        return "MALFORMED"
    if option_code is not None:
        if (
            record.get("option_code") != option_code
            or record.get("option_version") != "1"
            or record.get("trigger_mode") != trigger_mode
            or record.get("subject_identity") != subject_identity
        ):
            return "MALFORMED"
        if link is None:
            return "MALFORMED"
        link_reference = _first(record, ("link_reference", "driver_action_link_ref", "link_id"))
        if link_reference != _record_identifier(link):
            return "MALFORMED"
    snapshot_reference = _first(
        record,
        ("case_constraint_snapshot_ref", "snapshot_ref", "constraint_snapshot_ref"),
    )
    snapshot_hash = _first(
        record,
        ("case_constraint_snapshot_hash", "snapshot_hash", "constraint_snapshot_hash"),
    )
    if (
        snapshot_reference != snapshot.get("snapshot_id")
        or snapshot_hash != snapshot.get("content_hash")
    ):
        return "MALFORMED"
    required = ("source_record_ref", "provenance_ref", "known_at", "recorded_at", "valid_through")
    if any(not isinstance(record.get(field), str) or not record.get(field) for field in required):
        return "MALFORMED"
    known_at = _parse_time(record.get("known_at"))
    recorded_at = _parse_time(record.get("recorded_at"))
    if known_at is None or recorded_at is None:
        return "MALFORMED"
    if known_at > constraints_as_of:
        return "LATE"
    valid_through = record.get("valid_through")
    if valid_through != "NO_EXPIRY":
        expiry = _parse_time(valid_through)
        if expiry is None:
            return "MALFORMED"
        if constraints_as_of > expiry:
            return "LATE"
    review_reference = record.get("review_reference")
    if not isinstance(review_reference, str) or not review_reference:
        return "MALFORMED"
    reviewer_reference = _first(record, ("reviewer_reference", "reviewer_ref"))
    if not isinstance(reviewer_reference, str) or not reviewer_reference:
        return "MALFORMED"
    if not isinstance(record.get("reviewer_role"), str) or not record.get(
        "reviewer_role"
    ):
        return "MALFORMED"
    review_available_at = _parse_time(record.get("review_available_at"))
    review_date = _parse_time(record.get("review_date"))
    if review_available_at is None or review_date is None:
        return "MALFORMED"
    if review_available_at > constraints_as_of or review_date > constraints_as_of:
        return "LATE"
    return None


def _check_record(
    record: Mapping[str, Any] | None,
    *,
    unavailable_code: str,
    invalid_code: str,
    option_code: str | None,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    constraints_as_of: datetime,
) -> tuple[Mapping[str, Any] | None, str | None]:
    if record is None:
        return None, unavailable_code
    common_error = _common_input_error(
        record,
        option_code=option_code,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
    )
    if common_error == "LATE":
        return record, unavailable_code
    if common_error is not None:
        return record, invalid_code
    return record, None


def _selected_value(record: Mapping[str, Any]) -> object:
    return _first(record, ("selected_value", "selected", "value", "assumption_value"))


def _record_values(record: Mapping[str, Any], fields: Sequence[str]) -> tuple[object, object, object]:
    return tuple(
        _first(record, (field, f"selected_{field}", f"{field}_value"))
        for field in fields
    )  # type: ignore[return-value]


def _assumption_output(
    record: Mapping[str, Any],
    *,
    kind: str,
    values: Mapping[str, Fraction | str],
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "kind": kind,
        "selected": {
            key: _pair(value) if isinstance(value, Fraction) else value
            for key, value in values.items()
        },
        "edited": record.get("edited", record.get("edited_not_edited", False)),
        "rationale": record.get("rationale"),
        "provenance": _record_ref(record),
        "record": deepcopy(dict(record)),
    }
    default_value = _first(record, ("default_value", "reviewed_default", "registered_default"))
    if default_value is not None:
        parsed_default = _fraction_from_decimal(default_value)
        output["default"] = _pair(parsed_default) if parsed_default is not None else default_value
    for field in ("basis", "currency", "duration_basis", "resolved_duration_basis"):
        if field in record:
            output[field] = record[field]
    return output


def _reason(
    *,
    code: str,
    option_code: str,
    reason: str,
    evidence: Sequence[Mapping[str, Any] | None] = (),
) -> dict[str, Any]:
    refs = [ref for ref in (_record_ref(item) for item in evidence) if ref is not None]
    return {
        "code": code,
        "category": "VALUE",
        "priority": _VALUE_REASON_PRIORITIES[code],
        "option_scope": option_code,
        "reason": reason,
        "explanation_code": code,
        "evidence_refs": refs,
    }


def _empty_fields(*, present: bool) -> dict[str, Any]:
    return {
        "value_status": "NOT_EVALUATED" if not present else "UNAVAILABLE",
        "recommendation_eligible": False,
        "assumptions": {},
        "costs": {},
        "benefit_projection": None,
        "unavailable_reasons": (
            []
            if present
            else [
                {
                    "code": "VALUE_INPUT_ENVELOPE_UNAVAILABLE",
                    "reason": "No exact case-specific Decision Support value input envelope was supplied.",
                }
            ]
        ),
        "caveats": [
            "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "No projection is available until its exact governed inputs and approvals are present.",
        ],
    }


def _parse_effect(
    effect: Mapping[str, Any] | None,
) -> tuple[tuple[Fraction, Fraction, Fraction] | None, str | None]:
    if effect is None:
        return None, "EXPOSURE_EFFECT_UNAVAILABLE"
    lower_raw = _first(effect, ("ci_lower", "lower", "effect_lower"))
    central_raw = _first(effect, ("estimate", "central", "effect_estimate"))
    upper_raw = _first(effect, ("ci_upper", "upper", "effect_upper"))
    values = tuple(
        _fraction_from_effect(raw) for raw in (lower_raw, central_raw, upper_raw)
    )
    if any(value is None for value in values):
        return None, "EXPOSURE_EFFECT_UNAVAILABLE"
    parsed = values  # type: ignore[assignment]
    if not parsed[0] <= parsed[1] <= parsed[2]:
        return None, "EXPOSURE_EFFECT_UNAVAILABLE"
    basis = _first(effect, ("duration_basis", "canonical_slippage_duration_basis"))
    if basis not in _VALID_DURATION_BASES:
        return None, "EXPOSURE_EFFECT_UNAVAILABLE"
    return parsed, None


def _parse_rate(
    record: Mapping[str, Any] | None,
    *,
    duration_basis: str | None,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    record, common_error = _check_record(
        record,
        unavailable_code="CRITICAL_PATH_DELAY_RATE_UNAVAILABLE",
        invalid_code="CRITICAL_PATH_DELAY_RATE_INVALID",
        option_code=None,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=None,
        constraints_as_of=constraints_as_of,
    )
    if common_error is not None:
        return record, common_error
    if record is None:
        return None, "CRITICAL_PATH_DELAY_RATE_UNAVAILABLE"
    if not isinstance(record.get("rationale"), str) or not isinstance(
        record.get("edited"), bool
    ):
        return record, "CRITICAL_PATH_DELAY_RATE_INVALID"
    amount = _fraction_from_decimal(_first(record, ("amount", "selected_amount", "value")))
    currency = record.get("currency")
    day_basis = record.get("day_basis")
    resolved_basis = _first(record, ("resolved_duration_basis", "duration_basis"))
    if (
        amount is None
        or amount < 0
        or not _is_currency(currency)
        or day_basis != "CANONICAL_SLIPPAGE_DAY"
        or resolved_basis not in _VALID_DURATION_BASES
        or duration_basis is None
        or resolved_basis != duration_basis
    ):
        return record, "CRITICAL_PATH_DELAY_RATE_INVALID"
    return {
        "amount": amount,
        "currency": currency,
        "day_basis": day_basis,
        "resolved_duration_basis": resolved_basis,
        "provenance": _record_ref(record),
        "record": deepcopy(dict(record)),
    }, None


def _parse_cost(
    record: Mapping[str, Any] | None,
    *,
    option_code: str,
    currency: str | None,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    constraints_as_of: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    record, common_error = _check_record(
        record,
        unavailable_code="ACTION_COST_UNAVAILABLE",
        invalid_code="ACTION_COST_INVALID",
        option_code=option_code,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
    )
    if common_error is not None:
        return record, common_error
    if record is None:
        return None, "ACTION_COST_UNAVAILABLE"
    if not isinstance(record.get("rationale"), str) or not isinstance(
        record.get("edited"), bool
    ):
        return record, "ACTION_COST_INVALID"
    expected_formula = (
        "DECLARED_MONITORING_TOTAL.v1"
        if option_code == "ACCEPT_AND_MONITOR"
        else "DECLARED_COMPOSITE_TOTAL.v1"
        if option_code == "PROTECTED_SLOT_WITH_PHASED_DELIVERY"
        else "DECLARED_TOTAL_COST.v1"
    )
    total = _fraction_from_decimal(_first(record, ("total", "amount", "selected_total")))
    record_currency = record.get("currency")
    if (
        record.get("formula_identifier", record.get("formula")) != expected_formula
        or total is None
        or total < 0
        or not _is_currency(record_currency)
        or currency is not None and record_currency != currency
    ):
        return record, "ACTION_COST_INVALID"
    breakdown = _first(record, ("breakdown", "component_breakdown"))
    if breakdown is not None:
        if not isinstance(breakdown, list) or len(breakdown) > 100:
            return record, "ACTION_COST_INVALID"
        try:
            parts = [
                _fraction_from_decimal(
                    _first(item, ("amount", "value", "total"))
                )
                for item in breakdown
                if isinstance(item, Mapping)
            ]
            if len(parts) != len(breakdown) or any(part is None or part < 0 for part in parts):
                return record, "ACTION_COST_INVALID"
            summed = Fraction(0, 1)
            for part in parts:
                summed = _add(summed, part)  # type: ignore[arg-type]
            if summed != total:
                return record, "ACTION_COST_INVALID"
        except ValueError:
            return record, "ACTION_COST_INVALID"
    return {
        "amount": total,
        "currency": record_currency,
        "formula_identifier": expected_formula,
        "provenance": _record_ref(record),
        "record": deepcopy(dict(record)),
    }, None


def _parse_fraction(
    record: Mapping[str, Any] | None,
    *,
    kind: str,
    option_code: str,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    constraints_as_of: datetime,
    unavailable_code: str,
    invalid_code: str,
) -> tuple[dict[str, Any] | None, str | None]:
    record, check_code = _check_record(
        record,
        unavailable_code=unavailable_code,
        invalid_code=invalid_code,
        option_code=option_code,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
    )
    if check_code is not None:
        return record, check_code
    if record is None:
        return None, unavailable_code
    if not isinstance(record.get("rationale"), str) or not isinstance(
        record.get("edited"), bool
    ):
        return record, invalid_code
    value = _fraction_from_decimal(_selected_value(record))
    if value is None or value < 0 or value > 1:
        return record, invalid_code
    if kind == "RECOVERABLE_FRACTION":
        default_value = _fraction_from_decimal(
            _first(record, ("default_value", "reviewed_default", "registered_default"))
        )
        if default_value is None or default_value < 0 or default_value > 1:
            return record, invalid_code
        if link is not None:
            expected_default = link.get("default_assumption_ref")
            declared_default = _first(
                record,
                ("default_assumption_ref", "default_recoverable_fraction_ref"),
            )
            if expected_default is not None and declared_default != expected_default:
                return record, invalid_code
    else:
        attestation_reference = _first(
            record,
            (
                "manager_attestation_reference",
                "attestation_reference",
                "review_evidence_ref",
            ),
        )
        if not isinstance(attestation_reference, str) or not attestation_reference:
            return record, invalid_code
    return {
        "value": value,
        "assumption": _assumption_output(
            record,
            kind=kind,
            values={"selected_value": value},
        ),
    }, None


def _parse_consequence_assumption(
    record: Mapping[str, Any] | None,
    *,
    option_code: str,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    constraints_as_of: datetime,
    currency: str | None,
    duration_basis: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    record, check_code = _check_record(
        record,
        unavailable_code="CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE",
        invalid_code="CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID",
        option_code=option_code,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
    )
    if check_code is not None:
        return record, check_code
    if record is None:
        return None, "CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE"
    if not isinstance(record.get("rationale"), str) or not isinstance(
        record.get("edited"), bool
    ):
        return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    basis = record.get("basis")
    if basis not in {"PROJECT_DELAY_DAYS", "DIRECT_MONETARY_VALUE"}:
        return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    lower_raw, central_raw, upper_raw = _record_values(
        record,
        ("lower", "central", "upper"),
    )
    values = tuple(
        _fraction_from_decimal(raw) for raw in (lower_raw, central_raw, upper_raw)
    )
    if any(value is None or value < 0 for value in values):
        return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    parsed = values  # type: ignore[assignment]
    if not parsed[0] <= parsed[1] <= parsed[2]:
        return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    record_currency = record.get("currency")
    if basis == "DIRECT_MONETARY_VALUE":
        if not _is_currency(record_currency) or currency is not None and record_currency != currency:
            return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    else:
        if record.get("duration_basis") != duration_basis or duration_basis not in _VALID_DURATION_BASES:
            return record, "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    selected = {"lower": parsed[0], "central": parsed[1], "upper": parsed[2]}
    return {
        "basis": basis,
        "values": parsed,
        "currency": record_currency,
        "assumption": _assumption_output(
            record,
            kind="CONSEQUENCE_BENEFIT",
            values=selected,
        ),
    }, None


def _sort_reasons(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(reasons, key=lambda item: (int(item["priority"]), str(item["code"])))


def project_option_value(
    *,
    option: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    trigger_mode: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    required_constraints_pass: bool,
    value_context: ValueContext,
) -> ValueProjection:
    option_code = str(option["option_code"])
    fields = _empty_fields(present=value_context.present)
    reasons: list[dict[str, Any]] = []
    if not value_context.present:
        return ValueProjection(fields=fields, suppression_reasons=[])

    effect_values, effect_error = _parse_effect(value_context.effect)
    duration_basis = value_context.duration_basis
    currency_candidates = _currency_candidates(
        value_context.rate,
        value_context.direct_costs,
        value_context.assumptions,
    )
    currency = next(iter(currency_candidates), None)
    cost_record, cost_lookup_error = _find_option_record(
        value_context.direct_costs,
        option_code=option_code,
        trigger_mode=trigger_mode,
    )
    if cost_lookup_error == "MULTIPLE":
        cost_record = cost_record
        cost_error = "ACTION_COST_INVALID"
    else:
        cost_error = None
    cost, parsed_cost_error = _parse_cost(
        cost_record,
        option_code=option_code,
        currency=currency,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
    )
    if cost_error is not None:
        parsed_cost_error = cost_error
    if parsed_cost_error is not None:
        reasons.append(
            _reason(
                code=parsed_cost_error,
                option_code=option_code,
                reason=(
                    "The exact governed direct action cost is unavailable."
                    if parsed_cost_error == "ACTION_COST_UNAVAILABLE"
                    else "The exact governed direct action cost is malformed or does not reconcile."
                ),
                evidence=(cost_record,),
            )
        )
    elif cost is not None:
        fields["costs"]["direct_action_cost"] = {
            key: _pair(value) if isinstance(value, Fraction) else value
            for key, value in cost.items()
            if key != "record"
        }
        fields["costs"]["direct_action_cost"]["record"] = cost["record"]

    if option_code == "ACCEPT_AND_MONITOR":
        fields["evidence_tags"] = {
            "ASSUMPTION_BASED_BENEFIT": "NO_BENEFIT_CLAIM"
        }
        fields["value_status"] = "NOT_APPLICABLE"
        fields["recommendation_eligible"] = not reasons and required_constraints_pass
        fields["caveats"] = [
            "NO_BENEFIT_CLAIM",
            "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "Monitoring is a baseline and does not claim recovered time or money.",
        ]
        fields["unavailable_reasons"] = deepcopy(reasons)
        return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))

    assumptions = value_context.assumptions
    if option.get("response_class") in {"EXPOSURE_REDUCTION", "MILESTONE_ACCELERATION"}:
        if effect_error is not None:
            reasons.append(
                _reason(
                    code=effect_error,
                    option_code=option_code,
                    reason="The verified supported exposure effect and duration basis are unavailable for translation.",
                )
            )
        recoverable_record, recoverable_lookup_error = _find_option_record(
            assumptions,
            option_code=option_code,
            trigger_mode=trigger_mode,
            kind="RECOVERABLE_FRACTION",
        )
        if recoverable_lookup_error == "MULTIPLE":
            recoverable_record = recoverable_record
            recoverable_error = "RECOVERABLE_FRACTION_INVALID"
        else:
            recoverable_error = None
        recoverable, parsed_recoverable_error = _parse_fraction(
            recoverable_record,
            kind="RECOVERABLE_FRACTION",
            option_code=option_code,
            trigger_mode=trigger_mode,
            subject_identity=subject_identity,
            snapshot=snapshot,
            link=link,
            constraints_as_of=constraints_as_of,
            unavailable_code="RECOVERABLE_FRACTION_UNAVAILABLE",
            invalid_code="RECOVERABLE_FRACTION_INVALID",
        )
        if recoverable_error is not None:
            parsed_recoverable_error = recoverable_error
        if parsed_recoverable_error is not None:
            reasons.append(
                _reason(
                    code=parsed_recoverable_error,
                    option_code=option_code,
                    reason=(
                        "The exact reviewed recoverable-fraction assumption is unavailable."
                        if parsed_recoverable_error == "RECOVERABLE_FRACTION_UNAVAILABLE"
                        else "The recoverable-fraction assumption is malformed or outside [0,1]."
                    ),
                    evidence=(recoverable_record,),
                )
            )
        elif recoverable is not None:
            fields["assumptions"]["recoverable_fraction"] = recoverable["assumption"]

        translation_record, translation_lookup_error = _find_option_record(
            assumptions,
            option_code=option_code,
            trigger_mode=trigger_mode,
            kind="CRITICAL_PATH_TRANSLATION_FRACTION",
        )
        if translation_lookup_error == "MULTIPLE":
            translation_record = translation_record
            translation_error = "CRITICAL_PATH_TRANSLATION_FRACTION_INVALID"
        else:
            translation_error = None
        translation, parsed_translation_error = _parse_fraction(
            translation_record,
            kind="CRITICAL_PATH_TRANSLATION_FRACTION",
            option_code=option_code,
            trigger_mode=trigger_mode,
            subject_identity=subject_identity,
            snapshot=snapshot,
            link=link,
            constraints_as_of=constraints_as_of,
            unavailable_code="CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE",
            invalid_code="CRITICAL_PATH_TRANSLATION_FRACTION_INVALID",
        )
        if translation_error is not None:
            parsed_translation_error = translation_error
        if parsed_translation_error is not None:
            reasons.append(
                _reason(
                    code=parsed_translation_error,
                    option_code=option_code,
                    reason=(
                        "The exact reviewed critical-path translation assumption is unavailable."
                        if parsed_translation_error
                        == "CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE"
                        else "The critical-path translation assumption is malformed or outside [0,1]."
                    ),
                    evidence=(translation_record,),
                )
            )
        elif translation is not None:
            fields["assumptions"]["critical_path_translation_fraction"] = translation[
                "assumption"
            ]

        rate, parsed_rate_error = _parse_rate(
            value_context.rate,
            duration_basis=duration_basis,
            trigger_mode=trigger_mode,
            subject_identity=subject_identity,
            snapshot=snapshot,
            constraints_as_of=constraints_as_of,
        )
        if parsed_rate_error is not None:
            reasons.append(
                _reason(
                    code=parsed_rate_error,
                    option_code=option_code,
                    reason=(
                        "The case-scoped critical-path delay rate is unavailable."
                        if parsed_rate_error == "CRITICAL_PATH_DELAY_RATE_UNAVAILABLE"
                        else "The critical-path delay rate has an invalid amount, currency, day basis, or resolved duration basis."
                    ),
                    evidence=(value_context.rate,),
                )
            )
        elif rate is not None:
            fields["costs"]["cost_of_critical_path_delay_per_day"] = {
                key: _pair(value) if isinstance(value, Fraction) else value
                for key, value in rate.items()
                if key != "record"
            }
            fields["costs"]["cost_of_critical_path_delay_per_day"]["record"] = rate[
                "record"
            ]

        fields["unavailable_reasons"] = deepcopy(reasons)
        if reasons or not required_constraints_pass:
            if not required_constraints_pass:
                fields["value_status"] = "NOT_EVALUATED"
            return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
        if effect_values is None or recoverable is None or translation is None or rate is None or cost is None:
            return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
        try:
            recovered = tuple(_multiply(value, recoverable["value"]) for value in effect_values)
            protected = tuple(_multiply(value, translation["value"]) for value in recovered)
            gross = tuple(_multiply(value, rate["amount"]) for value in protected)
            net = tuple(_subtract(value, cost["amount"]) for value in gross)
        except ValueError:
            reasons.append(
                _reason(
                    code="CRITICAL_PATH_DELAY_RATE_INVALID",
                    option_code=option_code,
                    reason="The exact rational projection exceeded the 4,096-bit arithmetic bound.",
                    evidence=(value_context.rate,),
                )
            )
            fields["value_status"] = "UNAVAILABLE"
            fields["unavailable_reasons"] = deepcopy(reasons)
            return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
        value_status = (
            "NON_POSITIVE_CENTRAL_VALUE"
            if net[1] <= 0
            else "VALUE_SENSITIVE"
            if net[0] <= 0
            else "ROBUSTLY_POSITIVE"
        )
        fields["value_status"] = value_status
        fields["recommendation_eligible"] = value_status != "NON_POSITIVE_CENTRAL_VALUE"
        projection = {
            "disclosure": "ASSUMPTION_BASED_PROJECTION_RANGE",
            "recovered_supplier_milestone_days": _pair_range(recovered),
            "project_delay_days_protected": _pair_range(protected),
            "gross_avoided_delay_value": _pair_range(gross),
            "net_assumption_value": _pair_range(net),
            "schedule_protection": {
                "basis": "PROJECT_DELAY_DAYS",
                "duration_basis": duration_basis,
                "central": _pair(protected[1]),
            },
            "currency": rate["currency"],
            "provenance": {
                "verified_effect": _record_ref(value_context.effect),
                "recoverable_fraction": _record_ref(recoverable_record),
                "critical_path_translation_fraction": _record_ref(translation_record),
                "cost_of_critical_path_delay_per_day": rate["provenance"],
                "direct_action_cost": cost["provenance"],
                "primary_driver_action_link": _record_ref(link),
            },
        }
        fields["benefit_projection"] = projection
        fields["caveats"] = [
            "ASSUMPTION_BASED_PROJECTION_RANGE",
            "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "The range is not an intervention-effect confidence interval or a success probability.",
            "Recovered supplier-milestone days and protected project-delay days are separate values.",
            "No currency or duration conversion, tax, NPV, recurring forecast, or inferred quantity is applied.",
        ]
        if value_status == "NON_POSITIVE_CENTRAL_VALUE":
            reasons.append(
                _reason(
                    code="NON_POSITIVE_CENTRAL_NET_VALUE",
                    option_code=option_code,
                    reason="The central net assumption value is not positive; the option is suppressed.",
                    evidence=(cost["record"],),
                )
            )
            fields["recommendation_eligible"] = False
        fields["unavailable_reasons"] = deepcopy(reasons)
        return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))

    consequence_record, consequence_lookup_error = _find_option_record(
        assumptions,
        option_code=option_code,
        trigger_mode=trigger_mode,
        kind="CONSEQUENCE_BENEFIT",
    )
    consequence, consequence_error = _parse_consequence_assumption(
        consequence_record,
        option_code=option_code,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        link=link,
        constraints_as_of=constraints_as_of,
        currency=currency,
        duration_basis=duration_basis,
    )
    if consequence_lookup_error == "MULTIPLE":
        consequence_error = "CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID"
    if consequence_error is not None:
        reasons.append(
            _reason(
                code=consequence_error,
                option_code=option_code,
                reason=(
                    "The exact reviewed consequence benefit assumption is unavailable."
                    if consequence_error == "CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE"
                    else "The consequence benefit assumption is malformed, unapproved, or uses an incompatible basis."
                ),
                evidence=(consequence_record,),
            )
        )
    elif consequence is not None:
        fields["assumptions"]["consequence_benefit"] = consequence["assumption"]
    if consequence is not None and consequence["basis"] == "PROJECT_DELAY_DAYS":
        rate, parsed_rate_error = _parse_rate(
            value_context.rate,
            duration_basis=duration_basis,
            trigger_mode=trigger_mode,
            subject_identity=subject_identity,
            snapshot=snapshot,
            constraints_as_of=constraints_as_of,
        )
        if parsed_rate_error is not None:
            reasons.append(
                _reason(
                    code=parsed_rate_error,
                    option_code=option_code,
                    reason=(
                        "The case-scoped critical-path delay rate is unavailable."
                        if parsed_rate_error == "CRITICAL_PATH_DELAY_RATE_UNAVAILABLE"
                        else "The critical-path delay rate has an invalid amount, currency, day basis, or resolved duration basis."
                    ),
                    evidence=(value_context.rate,),
                )
            )
        elif rate is not None:
            fields["costs"]["cost_of_critical_path_delay_per_day"] = {
                key: _pair(value) if isinstance(value, Fraction) else value
                for key, value in rate.items()
                if key != "record"
            }
            fields["costs"]["cost_of_critical_path_delay_per_day"]["record"] = rate[
                "record"
            ]
    else:
        rate = None
    fields["unavailable_reasons"] = deepcopy(reasons)
    if reasons or not required_constraints_pass or consequence is None or cost is None:
        if not required_constraints_pass:
            fields["value_status"] = "NOT_EVALUATED"
        return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
    try:
        if consequence["basis"] == "PROJECT_DELAY_DAYS":
            if rate is None:
                return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
            gross = tuple(_multiply(value, rate["amount"]) for value in consequence["values"])
            schedule = consequence["values"]
            currency = rate["currency"]
        else:
            gross = consequence["values"]
            schedule = None
            currency = consequence["currency"]
        net = tuple(_subtract(value, cost["amount"]) for value in gross)
    except ValueError:
        reasons.append(
            _reason(
                code="ACTION_COST_INVALID",
                option_code=option_code,
                reason="The exact rational projection exceeded the 4,096-bit arithmetic bound.",
                evidence=(cost["record"],),
            )
        )
        fields["value_status"] = "UNAVAILABLE"
        fields["unavailable_reasons"] = deepcopy(reasons)
        return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
    value_status = (
        "NON_POSITIVE_CENTRAL_VALUE"
        if net[1] <= 0
        else "VALUE_SENSITIVE"
        if net[0] <= 0
        else "ROBUSTLY_POSITIVE"
    )
    fields["value_status"] = value_status
    fields["recommendation_eligible"] = value_status != "NON_POSITIVE_CENTRAL_VALUE"
    projection = {
        "disclosure": "ASSUMPTION_BASED_PROJECTION_RANGE",
        "gross_consequence_value": _pair_range(gross),
        "net_assumption_value": _pair_range(net),
        "schedule_protection": (
            {
                "basis": "PROJECT_DELAY_DAYS",
                "duration_basis": duration_basis,
                "central": _pair(schedule[1]),
            }
            if schedule is not None
            else {"basis": "NOT_APPLICABLE"}
        ),
        "currency": currency,
        "provenance": {
            "consequence_benefit_assumption": _record_ref(consequence_record),
            "cost_of_critical_path_delay_per_day": (
                rate["provenance"] if rate is not None else None
            ),
            "direct_action_cost": cost["provenance"],
            "primary_driver_action_link": _record_ref(link),
        },
    }
    if schedule is not None:
        projection["project_delay_days_protected"] = _pair_range(schedule)
    fields["benefit_projection"] = projection
    fields["caveats"] = [
        "ASSUMPTION_BASED_PROJECTION_RANGE",
        "OPERATIONAL_ASSUMPTION_ONLY",
        "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "The consequence assumption does not claim recovered Supplier Milestone Slippage.",
        "No currency or duration conversion, tax, NPV, recurring forecast, or inferred quantity is applied.",
    ]
    if value_status == "NON_POSITIVE_CENTRAL_VALUE":
        reasons.append(
            _reason(
                code="NON_POSITIVE_CENTRAL_NET_VALUE",
                option_code=option_code,
                reason="The central net assumption value is not positive; the option is suppressed.",
                evidence=(cost["record"],),
            )
        )
        fields["recommendation_eligible"] = False
    fields["unavailable_reasons"] = deepcopy(reasons)
    return ValueProjection(fields=fields, suppression_reasons=_sort_reasons(reasons))
