from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Mapping, Sequence

from .canonical import sha256


COMPARISON_DIMENSION_ORDER = (
    "SCHEDULE_PROTECTION",
    "DIRECT_ACTION_COST",
    "TIME_TO_INITIATE",
    "CONTRACTUAL_RELATIONSHIP_RISK",
    "OPERATIONAL_DISRUPTION",
    "REVERSIBILITY",
)

_DIRECTIONS = {
    "SCHEDULE_PROTECTION": "HIGHER_IS_MORE_FAVORABLE",
    "DIRECT_ACTION_COST": "LOWER_IS_MORE_FAVORABLE",
    "TIME_TO_INITIATE": "LOWER_IS_MORE_FAVORABLE",
    "CONTRACTUAL_RELATIONSHIP_RISK": "LOWER_IS_MORE_FAVORABLE",
    "OPERATIONAL_DISRUPTION": "LOWER_IS_MORE_FAVORABLE",
    "REVERSIBILITY": "MORE_REVERSIBLE_IS_MORE_FAVORABLE",
}
_ENUM_RANKS = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "DIFFICULT_TO_REVERSE": 0,
    "PARTIALLY_REVERSIBLE": 1,
    "EASILY_REVERSIBLE": 2,
}
_COMPARABLE_APPLICABILITY = "APPLICABLE"
_NOT_APPLICABLE = "NOT_APPLICABLE"
_INCOMPARABLE = "INCOMPARABLE"
_MAX_INTEGER_BITS = 4096


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _pair(value: object) -> tuple[Fraction, dict[str, str]] | None:
    candidate = _mapping(value)
    if candidate is not None:
        numerator = candidate.get("numerator")
        denominator = candidate.get("denominator")
        try:
            if isinstance(numerator, str) and isinstance(denominator, str):
                fraction = Fraction(int(numerator), int(denominator))
            elif (
                isinstance(numerator, int)
                and not isinstance(numerator, bool)
                and isinstance(denominator, int)
                and not isinstance(denominator, bool)
            ):
                fraction = Fraction(numerator, denominator)
            else:
                return None
        except (ValueError, ZeroDivisionError, TypeError):
            return None
    elif isinstance(value, str) and value.startswith("decimal:"):
        try:
            decimal = Decimal(value.split(":", 1)[1])
            if not decimal.is_finite():
                return None
            fraction = Fraction(decimal)
        except (InvalidOperation, ValueError, ZeroDivisionError):
            return None
    else:
        return None
    if (
        abs(fraction.numerator).bit_length() > _MAX_INTEGER_BITS
        or abs(fraction.denominator).bit_length() > _MAX_INTEGER_BITS
    ):
        return None
    return fraction, {
        "numerator": str(fraction.numerator),
        "denominator": str(fraction.denominator),
    }


def _central_net(option: Mapping[str, Any]) -> tuple[Fraction, dict[str, str]] | None:
    projection = _mapping(option.get("benefit_projection"))
    if projection is None:
        return None
    net = _mapping(projection.get("net_assumption_value"))
    return None if net is None else _pair(net.get("central"))


def _unknown_dimension(
    *,
    dimension: str,
    reason_codes: Sequence[str] = (),
    source: str = "VALUE_PROJECTION",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "applicability": _INCOMPARABLE,
        "direction": _DIRECTIONS[dimension],
        "source": source,
        "value": "UNKNOWN",
    }
    if reason_codes:
        result["reason_codes"] = list(dict.fromkeys(str(code) for code in reason_codes))
    return result


def _value_reason_codes(option: Mapping[str, Any], prefix: str) -> list[str]:
    reasons = option.get("unavailable_reasons")
    codes = [
        str(reason.get("code"))
        for reason in reasons
        if isinstance(reason, Mapping) and isinstance(reason.get("code"), str)
    ] if isinstance(reasons, list) else []
    return codes or [f"{prefix}_UNAVAILABLE"]


def _schedule_dimension(option: Mapping[str, Any]) -> dict[str, Any]:
    if option.get("option_code") == "ACCEPT_AND_MONITOR":
        return {
            "applicability": _NOT_APPLICABLE,
            "basis": _NOT_APPLICABLE,
            "direction": _DIRECTIONS["SCHEDULE_PROTECTION"],
            "source": "MONITOR_ONLY",
            "unit": "project_delay_days",
            "value": _NOT_APPLICABLE,
        }
    projection = _mapping(option.get("benefit_projection"))
    schedule = _mapping(projection.get("schedule_protection")) if projection else None
    if schedule is None:
        return _unknown_dimension(
            dimension="SCHEDULE_PROTECTION",
            reason_codes=_value_reason_codes(option, "SCHEDULE_PROTECTION"),
        )
    basis = schedule.get("basis")
    if basis == _NOT_APPLICABLE:
        return {
            "applicability": _NOT_APPLICABLE,
            "basis": _NOT_APPLICABLE,
            "direction": _DIRECTIONS["SCHEDULE_PROTECTION"],
            "source": "VALUE_PROJECTION",
            "unit": "project_delay_days",
            "value": _NOT_APPLICABLE,
        }
    if basis != "PROJECT_DELAY_DAYS":
        return _unknown_dimension(
            dimension="SCHEDULE_PROTECTION",
            reason_codes=["SCHEDULE_PROTECTION_BASIS_UNSUPPORTED"],
        )
    parsed = _pair(schedule.get("central"))
    if parsed is None:
        return _unknown_dimension(
            dimension="SCHEDULE_PROTECTION",
            reason_codes=["SCHEDULE_PROTECTION_UNAVAILABLE"],
        )
    _, value = parsed
    result: dict[str, Any] = {
        "applicability": _COMPARABLE_APPLICABILITY,
        "basis": basis,
        "direction": _DIRECTIONS["SCHEDULE_PROTECTION"],
        "duration_basis": schedule.get("duration_basis"),
        "source": "VALUE_PROJECTION",
        "unit": "project_delay_days",
        "value": value,
    }
    if not isinstance(result["duration_basis"], str) or not result["duration_basis"]:
        return _unknown_dimension(
            dimension="SCHEDULE_PROTECTION",
            reason_codes=["SCHEDULE_PROTECTION_DURATION_BASIS_UNAVAILABLE"],
        )
    return result


def _direct_cost_dimension(option: Mapping[str, Any]) -> dict[str, Any]:
    costs = _mapping(option.get("costs"))
    direct_cost = _mapping(costs.get("direct_action_cost")) if costs else None
    if direct_cost is None:
        return _unknown_dimension(
            dimension="DIRECT_ACTION_COST",
            reason_codes=_value_reason_codes(option, "DIRECT_ACTION_COST"),
        )
    parsed = _pair(direct_cost.get("amount"))
    currency = direct_cost.get("currency")
    if parsed is None or not isinstance(currency, str) or not currency:
        return _unknown_dimension(
            dimension="DIRECT_ACTION_COST",
            reason_codes=["DIRECT_ACTION_COST_UNAVAILABLE"],
        )
    _, value = parsed
    return {
        "applicability": _COMPARABLE_APPLICABILITY,
        "currency": currency,
        "direction": _DIRECTIONS["DIRECT_ACTION_COST"],
        "source": "VALUE_PROJECTION",
        "unit": currency,
        "value": value,
    }


def comparison_dimensions_for_option(option: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the complete closed comparison profile for one evaluated option."""

    existing = _mapping(option.get("comparison_dimensions")) or {}
    dimensions: dict[str, dict[str, Any]] = {
        "SCHEDULE_PROTECTION": _schedule_dimension(option),
        "DIRECT_ACTION_COST": _direct_cost_dimension(option),
    }
    for dimension in COMPARISON_DIMENSION_ORDER[2:]:
        value = existing.get(dimension)
        if isinstance(value, Mapping):
            dimensions[dimension] = deepcopy(dict(value))
        else:
            dimensions[dimension] = _unknown_dimension(dimension=dimension)
    return dimensions


def _dimension_rank(value: object) -> int | None:
    return _ENUM_RANKS.get(value) if isinstance(value, str) else None


def _pair_dimension_result(
    dimension: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    left_applicability = left.get("applicability")
    right_applicability = right.get("applicability")
    result: dict[str, Any] = {
        "dimension": dimension,
        "left": deepcopy(dict(left)),
        "right": deepcopy(dict(right)),
    }
    if left_applicability == _NOT_APPLICABLE and right_applicability == _NOT_APPLICABLE:
        result.update({"state": "NOT_APPLICABLE", "relation": "NOT_APPLICABLE"})
        return result
    if left_applicability == _NOT_APPLICABLE or right_applicability == _NOT_APPLICABLE:
        result.update(
            {
                "state": "INCOMPARABLE",
                "relation": "INCOMPARABLE",
                "blocking_reason_code": "ONE_SIDED_NOT_APPLICABLE",
            }
        )
        return result
    if left_applicability != _COMPARABLE_APPLICABILITY or right_applicability != _COMPARABLE_APPLICABILITY:
        result.update(
            {
                "state": "INCOMPARABLE",
                "relation": "INCOMPARABLE",
                "blocking_reason_code": "UNKNOWN",
            }
        )
        return result
    if (
        left.get("direction") != _DIRECTIONS[dimension]
        or right.get("direction") != _DIRECTIONS[dimension]
    ):
        result.update(
            {
                "state": "INCOMPARABLE",
                "relation": "INCOMPARABLE",
                "blocking_reason_code": "UNKNOWN",
            }
        )
        return result
    if dimension == "SCHEDULE_PROTECTION" and (
        left.get("basis") != "PROJECT_DELAY_DAYS"
        or right.get("basis") != "PROJECT_DELAY_DAYS"
        or left.get("unit") != "project_delay_days"
        or right.get("unit") != "project_delay_days"
    ):
        result.update(
            {
                "state": "INCOMPARABLE",
                "relation": "INCOMPARABLE",
                "blocking_reason_code": "UNKNOWN",
            }
        )
        return result
    if dimension in {"SCHEDULE_PROTECTION", "TIME_TO_INITIATE"}:
        left_basis = left.get("duration_basis")
        right_basis = right.get("duration_basis")
        if left_basis != right_basis:
            result.update(
                {
                    "state": "INCOMPARABLE",
                    "relation": "INCOMPARABLE",
                    "blocking_reason_code": (
                        "INCOMPATIBLE_INITIATION_DURATION_BASIS"
                        if dimension == "TIME_TO_INITIATE"
                        else "UNKNOWN"
                    ),
                }
            )
            return result
    if dimension == "DIRECT_ACTION_COST":
        if (
            left.get("currency") != right.get("currency")
            or left.get("unit") != left.get("currency")
            or right.get("unit") != right.get("currency")
        ):
            result.update(
                {
                    "state": "INCOMPARABLE",
                    "relation": "INCOMPARABLE",
                    "blocking_reason_code": "UNKNOWN",
                }
            )
            return result
    left_rank = _dimension_rank(left.get("value"))
    right_rank = _dimension_rank(right.get("value"))
    if left_rank is not None and right_rank is not None:
        left_value, right_value = left_rank, right_rank
    else:
        left_pair = _pair(left.get("value"))
        right_pair = _pair(right.get("value"))
        if left_pair is None or right_pair is None:
            result.update(
                {
                    "state": "INCOMPARABLE",
                    "relation": "INCOMPARABLE",
                    "blocking_reason_code": "UNKNOWN",
                }
            )
            return result
        left_value, right_value = left_pair[0], right_pair[0]
    if left_value == right_value:
        relation = "EQUAL"
    else:
        higher_is_better = _DIRECTIONS[dimension] in {
            "HIGHER_IS_MORE_FAVORABLE",
            "MORE_REVERSIBLE_IS_MORE_FAVORABLE",
        }
        left_better = left_value > right_value if higher_is_better else left_value < right_value
        relation = "LEFT_BETTER" if left_better else "RIGHT_BETTER"
    result.update({"state": "COMPARABLE", "relation": relation})
    return result


def _pair_result(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, dict[str, Any]] = {}
    blockers: list[dict[str, str]] = []
    left_better = False
    right_better = False
    pair_applicable = False
    left_profile = _mapping(left.get("comparison_dimensions")) or {}
    right_profile = _mapping(right.get("comparison_dimensions")) or {}
    for dimension in COMPARISON_DIMENSION_ORDER:
        result = _pair_dimension_result(
            dimension,
            _mapping(left_profile.get(dimension)) or _unknown_dimension(dimension=dimension),
            _mapping(right_profile.get(dimension)) or _unknown_dimension(dimension=dimension),
        )
        dimensions[dimension] = result
        if result["state"] == "INCOMPARABLE":
            blockers.append(
                {
                    "dimension": dimension,
                    "reason_code": str(result["blocking_reason_code"]),
                }
            )
        elif result["state"] == "COMPARABLE":
            pair_applicable = True
            if result["relation"] == "LEFT_BETTER":
                left_better = True
            elif result["relation"] == "RIGHT_BETTER":
                right_better = True
    blockers = list({(item["dimension"], item["reason_code"]): item for item in blockers}.values())
    state = "INCOMPARABLE_EVIDENCE" if blockers else "COMPARABLE"
    return {
        "left_option_code": left.get("option_code"),
        "left_option_version": left.get("option_version"),
        "right_option_code": right.get("option_code"),
        "right_option_version": right.get("option_version"),
        "state": state,
        "pair_applicable": pair_applicable,
        "blocking_dimensions": blockers,
        "dimensions": dimensions,
        "left_dominates": bool(not blockers and pair_applicable and left_better and not right_better),
        "right_dominates": bool(not blockers and pair_applicable and right_better and not left_better),
    }


def _ordered_by_central_net(options: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    def key(option: Mapping[str, Any]) -> tuple[Fraction, int]:
        central = _central_net(option)
        return (
            -(central[0] if central is not None else Fraction(0)),
            int(option.get("display_order", 10**9)),
        )

    return sorted(options, key=key)


def _dimension_value(option: Mapping[str, Any], dimension: str) -> Fraction | None:
    profile = _mapping(option.get("comparison_dimensions")) or {}
    dimension_value = _mapping(profile.get(dimension))
    if (
        dimension_value is None
        or dimension_value.get("applicability") != _COMPARABLE_APPLICABILITY
    ):
        return None
    rank = _dimension_rank(dimension_value.get("value"))
    if rank is not None:
        return Fraction(rank)
    parsed = _pair(dimension_value.get("value"))
    return None if parsed is None else parsed[0]


def _ordered_by_dimension(
    options: Sequence[Mapping[str, Any]], dimension: str
) -> list[Mapping[str, Any]]:
    higher_is_better = _DIRECTIONS[dimension] in {
        "HIGHER_IS_MORE_FAVORABLE",
        "MORE_REVERSIBLE_IS_MORE_FAVORABLE",
    }

    def key(option: Mapping[str, Any]) -> tuple[int, Fraction, Fraction, int]:
        value = _dimension_value(option, dimension)
        central = _central_net(option)
        central_value = central[0] if central is not None else Fraction(0)
        display_order = int(option.get("display_order", 10**9))
        if value is None:
            return (1, Fraction(0), -central_value, display_order)
        return (
            0,
            -value if higher_is_better else value,
            -central_value,
            display_order,
        )

    return sorted(options, key=key)


def _ordering_evidence(options: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    central_values = [_central_net(option) for option in options]
    tied = len(central_values) > 1 and all(
        value is not None and value[0] == central_values[0][0]
        for value in central_values
    )
    return {
        "primary_key": "CENTRAL_NET_ASSUMPTION_VALUE",
        "direction": "DESCENDING",
        "tie_break": "INTERVENTION_LIBRARY_DISPLAY_ORDER",
        "annotation": "TIED_UNDER_POLICY" if tied else None,
    }


def _candidate(
    option: Mapping[str, Any],
    *,
    evaluation_occurrence_id: str,
    label: str,
    basis: str,
    ordering_evidence: Mapping[str, Any] | None = None,
    explanation: str | None = None,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "candidate_label": label,
        "candidate_basis": basis,
        "candidate_reference": {
            "evaluation_occurrence_id": evaluation_occurrence_id,
            "option_code": option.get("option_code"),
            "option_version": option.get("option_version"),
        },
        "option_code": option.get("option_code"),
        "option_version": option.get("option_version"),
        "label": option.get("label"),
        "value_status": option.get("value_status"),
        "central_net_assumption_value": (
            _central_net(option)[1] if _central_net(option) is not None else None
        ),
        "comparison_profile": deepcopy(option.get("comparison_dimensions", {})),
        "option_evaluation": deepcopy(dict(option)),
        "provenance": deepcopy(option.get("provenance", {})),
        "action_effect_evidence": option.get(
            "action_effect_evidence", "INTERVENTION_EFFECT_NOT_ESTIMATED"
        ),
        "ordering_evidence": deepcopy(dict(ordering_evidence or {})),
    }
    if explanation is not None:
        candidate["explanation"] = explanation
    candidate["content_hash"] = sha256(candidate)
    return candidate


def _runner_up(
    option: Mapping[str, Any],
    *,
    evaluation_occurrence_id: str,
    reason: str,
    ordering_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_reference": {
            "evaluation_occurrence_id": evaluation_occurrence_id,
            "option_code": option.get("option_code"),
            "option_version": option.get("option_version"),
        },
        "option_code": option.get("option_code"),
        "option_version": option.get("option_version"),
        "label": option.get("label"),
        "value_status": option.get("value_status"),
        "central_net_assumption_value": (
            _central_net(option)[1] if _central_net(option) is not None else None
        ),
        "comparison_profile": deepcopy(option.get("comparison_dimensions", {})),
        "provenance": deepcopy(option.get("provenance", {})),
        "action_effect_evidence": option.get(
            "action_effect_evidence", "INTERVENTION_EFFECT_NOT_ESTIMATED"
        ),
        "ordering_evidence": deepcopy(dict(ordering_evidence)),
        "ordering_reason": reason,
    }


def _recommendation(
    option: Mapping[str, Any],
    *,
    evaluation_occurrence_id: str,
    evaluation_series_id: str,
    input_digest: str,
    selection_basis: str,
    runner_up: Mapping[str, Any] | None,
    comparison: Mapping[str, Any],
    provenance: Mapping[str, Any],
    monitoring_fallback_reason: str | None = None,
) -> dict[str, Any]:
    key = sha256(
        {
            "evaluation_series_id": evaluation_series_id,
            "evaluation_occurrence_id": evaluation_occurrence_id,
            "decision_support_input_digest": input_digest,
            "selected_option_code_and_version": {
                "option_code": option.get("option_code"),
                "option_version": option.get("option_version"),
            },
            "selection_basis": selection_basis,
            "governance_tradeoff_selection_ref_and_hash_or_null": None,
        }
    )
    recommendation: dict[str, Any] = {
        "schema_identifier": "action-recommendation",
        "schema_version": "1",
        "action_recommendation_key": key,
        "occurrence_id": f"action-recommendation:{key}",
        "evaluation_series_id": evaluation_series_id,
        "evaluation_occurrence_id": evaluation_occurrence_id,
        "decision_support_input_digest": input_digest,
        "selected_option_code": option.get("option_code"),
        "selected_option_version": option.get("option_version"),
        "selected_option": deepcopy(dict(option)),
        "selection_basis": selection_basis,
        "runner_up": deepcopy(dict(runner_up)) if runner_up is not None else None,
        "presented_alternative": None,
        "comparison": deepcopy(dict(comparison)),
        "monitoring_fallback_reason": monitoring_fallback_reason,
        "action_effect_evidence": option.get(
            "action_effect_evidence", "INTERVENTION_EFFECT_NOT_ESTIMATED"
        ),
        "provenance": {
            "evaluation_provenance": deepcopy(dict(provenance)),
            "selected_option": deepcopy(option.get("provenance", {})),
            "comparison_policy": {
                "identifier": "pareto-tradeoff-comparison-policy",
                "version": "1",
            },
        },
    }
    recommendation["content_hash"] = sha256(recommendation)
    return recommendation


def _evaluation_record(
    *,
    evaluation_occurrence_id: str,
    evaluation_series_id: str,
    input_digest: str,
    outcome: str,
    options: Sequence[Mapping[str, Any]],
    comparison: Mapping[str, Any],
    tradeoff: Mapping[str, Any] | None,
    recommendation: Mapping[str, Any] | None,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_identifier": "decision-support-evaluation",
        "schema_version": "1",
        "evaluation_occurrence_id": evaluation_occurrence_id,
        "evaluation_series_id": evaluation_series_id,
        "decision_support_input_digest": input_digest,
        "outcome": outcome,
        "options": deepcopy([dict(option) for option in options]),
        "comparison": deepcopy(dict(comparison)),
        "tradeoff": deepcopy(dict(tradeoff)) if tradeoff is not None else None,
        "action_recommendation_ref_and_hash": (
            None
            if recommendation is None
            else {
                "reference": recommendation["occurrence_id"],
                "content_hash": recommendation["content_hash"],
            }
        ),
        "provenance": deepcopy(dict(provenance)),
    }
    record["content_hash"] = sha256(record)
    return record


def compare_and_publish(
    *,
    options: Sequence[Mapping[str, Any]],
    evaluation_occurrence_id: str,
    evaluation_series_id: str,
    input_digest: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the closed Pareto policy and publish immutable logical projections."""

    eligible = [
        option
        for option in options
        if option.get("evaluation_state") == "ACTIVE"
        and option.get("recommendation_eligible") is True
        and option.get("option_code") != "ACCEPT_AND_MONITOR"
    ]
    monitor = next(
        (
            option
            for option in options
            if option.get("option_code") == "ACCEPT_AND_MONITOR"
            and option.get("evaluation_state") == "ACTIVE"
            and option.get("recommendation_eligible") is True
        ),
        None,
    )
    dominance_matrix: dict[str, dict[str, dict[str, Any]]] = {}
    pair_records: list[dict[str, Any]] = []
    for left in eligible:
        left_code = str(left.get("option_code"))
        dominance_matrix[left_code] = {}
        for right in eligible:
            right_code = str(right.get("option_code"))
            if left is right:
                continue
            pair = _pair_result(left, right)
            dominance_matrix[left_code][right_code] = pair
            pair_records.append(pair)
    dominated_codes = {
        str(pair["right_option_code"])
        for pair in pair_records
        if pair["left_dominates"]
    }
    frontier = [
        option for option in eligible if str(option.get("option_code")) not in dominated_codes
    ]
    comparison_state = (
        "INCOMPARABLE_EVIDENCE_GAP"
        if any(pair["state"] == "INCOMPARABLE_EVIDENCE" for pair in pair_records)
        else "COMPARABLE"
    )
    comparison: dict[str, Any] = {
        "schema_identifier": "pareto-tradeoff-comparison-policy",
        "schema_version": "1",
        "dimension_order": list(COMPARISON_DIMENSION_ORDER),
        "directions": deepcopy(_DIRECTIONS),
        "state": comparison_state,
        "active_option_codes": [str(option.get("option_code")) for option in eligible],
        "pareto_frontier_option_codes": [str(option.get("option_code")) for option in frontier],
        "dominance_matrix": dominance_matrix,
        "pair_records": pair_records,
        "policy_disclosures": [
            "STRICT_PARETO_DOMINANCE_ONLY",
            "NO_HIDDEN_WEIGHTS",
            "NO_UNIT_COERCION",
            "NO_VALUE_SCORE_SUBSTITUTION",
            "MISSING_DATA_IS_NOT_FAVORABLE",
            "MONITORING_BASELINE_OUTSIDE_DOMINANCE_WHEN_POSITIVE_OPTIONS_EXIST",
        ],
        "provenance": {
            "comparison_policy": {
                "identifier": "pareto-tradeoff-comparison-policy",
                "version": "1",
            },
            "option_provenance": {
                str(option.get("option_code")): deepcopy(option.get("provenance", {}))
                for option in options
            },
        },
    }
    comparison["content_hash"] = sha256(comparison)

    monitoring = {
        "state": (
            "BASELINE_OUTSIDE_DOMINANCE"
            if monitor is not None and eligible
            else "ELIGIBLE_FALLBACK"
            if monitor is not None
            else "INELIGIBLE_OR_UNAVAILABLE"
        ),
        "option_code": "ACCEPT_AND_MONITOR",
        "recommendation_eligible": monitor is not None,
        "suppression_reasons": deepcopy(
            monitor.get("suppression_reasons", [])
            if monitor is not None
            else next(
                (
                    option.get("suppression_reasons", [])
                    for option in options
                    if option.get("option_code") == "ACCEPT_AND_MONITOR"
                ),
                [],
            )
        ),
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
    }

    recommendation: dict[str, Any] | None = None
    tradeoff: dict[str, Any] | None = None
    primary_reason_code = "CONSTRAINT_EVALUATION_COMPLETE"
    state = "constraints_evaluated"
    outcome = "NO_ELIGIBLE_OPTION"
    reason = (
        "Every active governed option was evaluated under the closed comparison policy; "
        "no option is recommendation-eligible under the value and monitoring rules."
    )
    next_step = "Inspect the exact option values, comparison profile, and suppression reasons."

    robust = [option for option in eligible if option.get("value_status") == "ROBUSTLY_POSITIVE"]
    sensitive = [option for option in eligible if option.get("value_status") == "VALUE_SENSITIVE"]

    if not eligible:
        if monitor is not None:
            recommendation = _recommendation(
                monitor,
                evaluation_occurrence_id=evaluation_occurrence_id,
                evaluation_series_id=evaluation_series_id,
                input_digest=input_digest,
                selection_basis="MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION",
                runner_up=None,
                comparison=comparison,
                provenance=provenance,
                monitoring_fallback_reason=(
                    "No active option has positive central net assumption value."
                ),
            )
            outcome = "RECOMMENDATION_AVAILABLE"
            state = "recommendation_available"
            reason = (
                "No active option has positive central net assumption value; the eligible "
                "monitoring baseline is presented as the transparent fallback."
            )
            next_step = "Manager review is required; the monitoring baseline does not authorize or execute an action."
        else:
            monitoring_reasons = monitoring["suppression_reasons"]
            if sensitive:
                primary_reason_code = "VALUE_SENSITIVE_BASELINE_UNAVAILABLE"
                reason = (
                    "Only value-sensitive options are active and the monitoring baseline "
                    "is unavailable or not eligible; no forced choice was published."
                )
                next_step = "Resolve the monitoring baseline constraints before comparing a value-sensitive option."
            elif monitoring_reasons:
                primary_reason_code = str(monitoring_reasons[0].get("code", primary_reason_code))
                reason = (
                    "No recommendation-eligible option remains after the governed value and "
                    "monitoring checks."
                )
    elif len(eligible) == 1 and robust:
        recommendation = _recommendation(
            eligible[0],
            evaluation_occurrence_id=evaluation_occurrence_id,
            evaluation_series_id=evaluation_series_id,
            input_digest=input_digest,
            selection_basis="SOLE_ELIGIBLE_OPTION",
            runner_up=None,
            comparison=comparison,
            provenance=provenance,
        )
        outcome = "RECOMMENDATION_AVAILABLE"
        state = "recommendation_available"
        reason = "Exactly one robustly positive governed option remains eligible after comparison."
        next_step = "Manager review is required; this recommendation is not approval or authorization."
    else:
        universal = [
            option
            for option in robust
            if all(
                dominance_matrix[str(option.get("option_code"))][str(other.get("option_code"))][
                    "left_dominates"
                ]
                for other in eligible
                if other is not option
            )
        ]
        if universal:
            selected = universal[0]
            remaining = [option for option in eligible if option is not selected]
            ordered_remaining = _ordered_by_central_net(remaining)
            runner = (
                _runner_up(
                    ordered_remaining[0],
                    evaluation_occurrence_id=evaluation_occurrence_id,
                    reason=(
                        "Highest central net assumption value among remaining active eligible options; "
                        "this is not a recommendation."
                    ),
                    ordering_evidence=_ordering_evidence(ordered_remaining),
                )
                if ordered_remaining
                else None
            )
            recommendation = _recommendation(
                selected,
                evaluation_occurrence_id=evaluation_occurrence_id,
                evaluation_series_id=evaluation_series_id,
                input_digest=input_digest,
                selection_basis="UNIVERSAL_PARETO_DOMINANCE",
                runner_up=runner,
                comparison=comparison,
                provenance=provenance,
            )
            outcome = "RECOMMENDATION_AVAILABLE"
            state = "recommendation_available"
            reason = "One robustly positive governed option strictly Pareto-dominates every other active eligible option."
            next_step = "Manager review is required; Pareto dominance is not approval or authorization."
        elif robust and not any(option in robust for option in frontier):
            ordered_frontier = _ordered_by_central_net(frontier)
            ordered_robust = _ordered_by_central_net(robust)
            candidate_a = _candidate(
                ordered_frontier[0],
                evaluation_occurrence_id=evaluation_occurrence_id,
                label="A",
                basis="PARETO_FRONTIER_OPTION",
                ordering_evidence=_ordering_evidence(ordered_frontier),
            )
            candidate_b = _candidate(
                ordered_robust[0],
                evaluation_occurrence_id=evaluation_occurrence_id,
                label="B",
                basis="ROBUST_SAFETY_ALTERNATIVE",
                ordering_evidence=_ordering_evidence(ordered_robust),
                explanation=(
                    "A governed robust safety alternative; this candidate is not claimed to be "
                    "on the Pareto frontier or superior."
                ),
            )
            tradeoff = {
                "schema_identifier": "decision-support-tradeoff",
                "schema_version": "1",
                "state": "REQUIRES_MANAGER_CHOICE",
                "pivot": "VALUE_UNCERTAINTY",
                "candidates": [candidate_a, candidate_b],
                "dominance_matrix": deepcopy(dominance_matrix),
                "selection": {"state": "NOT_SELECTED"},
                "reason": "Value-sensitive frontier options are presented with a governed robust safety alternative.",
                "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
            }
            tradeoff["content_hash"] = sha256(tradeoff)
            outcome = "TRADEOFF_REQUIRES_MANAGER_CHOICE"
            state = "tradeoff_requires_choice"
            reason = "A value-sensitive frontier and a robust safety alternative are incomparable under the closed policy."
            next_step = "A manager may later choose one exact candidate; selection is not approval or authorization."
        elif not robust and sensitive and monitor is None:
            primary_reason_code = "VALUE_SENSITIVE_BASELINE_UNAVAILABLE"
            reason = (
                "Only value-sensitive options are active and the monitoring baseline is "
                "unavailable or not eligible; no forced choice was published."
            )
            next_step = (
                "Resolve the monitoring baseline constraints before comparing a value-sensitive option."
            )
        elif not robust and sensitive and monitor is not None:
            ordered_sensitive = _ordered_by_central_net(sensitive)
            candidate_a = _candidate(
                ordered_sensitive[0],
                evaluation_occurrence_id=evaluation_occurrence_id,
                label="A",
                basis="VALUE_SENSITIVE_OPTION",
                ordering_evidence=_ordering_evidence(ordered_sensitive),
            )
            candidate_b = _candidate(
                monitor,
                evaluation_occurrence_id=evaluation_occurrence_id,
                label="B",
                basis="MONITORING_BASELINE",
                explanation=(
                    "A reviewed monitoring baseline with no intervention benefit claim."
                ),
            )
            tradeoff = {
                "schema_identifier": "decision-support-tradeoff",
                "schema_version": "1",
                "state": "REQUIRES_MANAGER_CHOICE",
                "pivot": "VALUE_UNCERTAINTY",
                "candidates": [candidate_a, candidate_b],
                "dominance_matrix": deepcopy(dominance_matrix),
                "selection": {"state": "NOT_SELECTED"},
                "reason": "Only value-sensitive options are active; the monitoring baseline remains an explicit alternative.",
                "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
            }
            tradeoff["content_hash"] = sha256(tradeoff)
            outcome = "TRADEOFF_REQUIRES_MANAGER_CHOICE"
            state = "tradeoff_requires_choice"
            reason = "Only value-sensitive options are active, so the value uncertainty remains visible beside monitoring."
            next_step = "A manager may later choose one exact candidate; selection is not approval or authorization."
        else:
            ordered_frontier = _ordered_by_central_net(frontier)
            selected = ordered_frontier[0]
            other_frontier = ordered_frontier[1:]
            selected_code = str(selected.get("option_code"))
            selected_to_other = {
                str(option.get("option_code")): dominance_matrix[selected_code][
                    str(option.get("option_code"))
                ]
                for option in other_frontier
            }
            equal_profile = [
                option
                for option in other_frontier
                if selected_to_other[str(option.get("option_code"))]["state"] == "COMPARABLE"
                and all(
                    item["relation"] in {"EQUAL", "NOT_APPLICABLE"}
                    for item in selected_to_other[str(option.get("option_code"))]["dimensions"].values()
                )
                and selected_to_other[str(option.get("option_code"))]["pair_applicable"]
                and _central_net(option) is not None
                and _central_net(selected) is not None
                and _central_net(option)[0] != _central_net(selected)[0]
            ]
            tied_profile = [
                option
                for option in other_frontier
                if selected_to_other[str(option.get("option_code"))]["state"] == "COMPARABLE"
                and all(
                    item["relation"] in {"EQUAL", "NOT_APPLICABLE"}
                    for item in selected_to_other[str(option.get("option_code"))]["dimensions"].values()
                )
                and selected_to_other[str(option.get("option_code"))]["pair_applicable"]
                and _central_net(option) is not None
                and _central_net(selected) is not None
                and _central_net(option)[0] == _central_net(selected)[0]
            ]
            pivot = None
            candidate_b_option: Mapping[str, Any] | None = None
            if tied_profile:
                pivot = "TIED_UNDER_POLICY"
                candidate_b_option = sorted(
                    tied_profile, key=lambda option: int(option.get("display_order", 10**9))
                )[0]
            else:
                for dimension in COMPARISON_DIMENSION_ORDER:
                    better = [
                        option
                        for option in other_frontier
                        if selected_to_other[str(option.get("option_code"))]["dimensions"][dimension][
                            "relation"
                        ]
                        == "RIGHT_BETTER"
                    ]
                    if better:
                        pivot = dimension
                        candidate_b_option = _ordered_by_dimension(better, dimension)[0]
                        break
            if pivot is None and equal_profile:
                pivot = "EQUAL_COMPARISON_PROFILE"
                candidate_b_option = _ordered_by_central_net(equal_profile)[0]
            if pivot is None and other_frontier:
                pivot = "INCOMPARABLE_EVIDENCE_GAP"
                candidate_b_option = _ordered_by_central_net(other_frontier)[0]
            if candidate_b_option is None:
                recommendation = _recommendation(
                    selected,
                    evaluation_occurrence_id=evaluation_occurrence_id,
                    evaluation_series_id=evaluation_series_id,
                    input_digest=input_digest,
                    selection_basis="SOLE_ELIGIBLE_OPTION",
                    runner_up=None,
                    comparison=comparison,
                    provenance=provenance,
                )
                outcome = "RECOMMENDATION_AVAILABLE"
                state = "recommendation_available"
                reason = "Exactly one active eligible option remains after the closed comparison policy."
                next_step = "Manager review is required; this recommendation is not approval or authorization."
            else:
                pair = selected_to_other[str(candidate_b_option.get("option_code"))]
                candidate_a = _candidate(
                    selected,
                    evaluation_occurrence_id=evaluation_occurrence_id,
                    label="A",
                    basis="PARETO_FRONTIER_OPTION",
                    ordering_evidence=_ordering_evidence(ordered_frontier),
                )
                candidate_b = _candidate(
                    candidate_b_option,
                    evaluation_occurrence_id=evaluation_occurrence_id,
                    label="B",
                    basis="PARETO_FRONTIER_OPTION",
                    ordering_evidence={
                        "pivot": pivot,
                        "pair_evidence": deepcopy(pair),
                    },
                )
                blocking = pair.get("blocking_dimensions", [])
                tradeoff = {
                    "schema_identifier": "decision-support-tradeoff",
                    "schema_version": "1",
                    "state": "REQUIRES_MANAGER_CHOICE",
                    "pivot": pivot,
                    "candidates": [candidate_a, candidate_b],
                    "dominance_matrix": deepcopy(dominance_matrix),
                    "blocking_dimensions": deepcopy(blocking),
                    "selection": {"state": "NOT_SELECTED"},
                    "reason": (
                        "No singular recommendation is published because the exact candidates "
                        "remain a Pareto trade-off under the declared dimensions."
                    ),
                    "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
                }
                tradeoff["content_hash"] = sha256(tradeoff)
                outcome = "TRADEOFF_REQUIRES_MANAGER_CHOICE"
                state = "tradeoff_requires_choice"
                reason = "Two exact governed candidates remain on the active Pareto frontier."
                next_step = "A manager may later choose one exact candidate; selection is not approval or authorization."

    recommendation_ref = (
        None
        if recommendation is None
        else {
            "reference": recommendation["occurrence_id"],
            "content_hash": recommendation["content_hash"],
        }
    )
    evaluation = _evaluation_record(
        evaluation_occurrence_id=evaluation_occurrence_id,
        evaluation_series_id=evaluation_series_id,
        input_digest=input_digest,
        outcome=outcome,
        options=options,
        comparison=comparison,
        tradeoff=tradeoff,
        recommendation=recommendation,
        provenance=provenance,
    )
    return {
        "outcome": outcome,
        "state": state,
        "primary_reason_code": primary_reason_code,
        "reason": reason,
        "next_step": next_step,
        "options": deepcopy([dict(option) for option in options]),
        "comparison": comparison,
        "dominance_matrix": deepcopy(dominance_matrix),
        "pareto_frontier_option_codes": [
            str(option.get("option_code")) for option in frontier
        ],
        "monitoring": monitoring,
        "tradeoff": tradeoff,
        "action_recommendation": recommendation,
        "action_recommendation_ref_and_hash": recommendation_ref,
        "decision_support_evaluation": evaluation,
        "decision_support_evaluation_content_hash": evaluation["content_hash"],
    }
