from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.canonical import sha256
from backend.app.decision_support_comparison import compare_and_publish


EVALUATION_ID = "dse:comparison-test"
SERIES_ID = "dses:comparison-test"
INPUT_DIGEST = "sha256:comparison-input"


def _pair(value: int) -> dict[str, str]:
    return {"numerator": str(value), "denominator": "1"}


def _option(
    code: str,
    order: int,
    *,
    value_status: str = "ROBUSTLY_POSITIVE",
    schedule: int | None = 5,
    cost: int | None = 100,
    time: int | None = 2,
    risk: str = "LOW",
    disruption: str = "LOW",
    reversibility: str = "EASILY_REVERSIBLE",
) -> dict[str, Any]:
    dimensions: dict[str, Any] = {
        "SCHEDULE_PROTECTION": {
            "applicability": "APPLICABLE" if schedule is not None else "NOT_APPLICABLE",
            "basis": "PROJECT_DELAY_DAYS" if schedule is not None else "NOT_APPLICABLE",
            "direction": "HIGHER_IS_MORE_FAVORABLE",
            "duration_basis": "CALENDAR_DAY" if schedule is not None else None,
            "source": "VALUE_PROJECTION",
            "unit": "project_delay_days",
            "value": _pair(schedule) if schedule is not None else "NOT_APPLICABLE",
        },
        "DIRECT_ACTION_COST": {
            "applicability": "APPLICABLE" if cost is not None else "INCOMPARABLE",
            "currency": "INR" if cost is not None else None,
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "source": "VALUE_PROJECTION",
            "unit": "INR",
            "value": _pair(cost) if cost is not None else "UNKNOWN",
        },
        "TIME_TO_INITIATE": {
            "applicability": "APPLICABLE" if time is not None else "INCOMPARABLE",
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "duration_basis": "CALENDAR_DAY" if time is not None else None,
            "source": "CONSTRAINT_FACT",
            "value": f"decimal:{time}" if time is not None else "UNKNOWN",
        },
        "CONTRACTUAL_RELATIONSHIP_RISK": {
            "applicability": "APPLICABLE" if risk != "UNKNOWN" else "INCOMPARABLE",
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "source": "ADVISORY_RESULT",
            "value": risk,
        },
        "OPERATIONAL_DISRUPTION": {
            "applicability": "APPLICABLE" if disruption != "UNKNOWN" else "INCOMPARABLE",
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "source": "ADVISORY_RESULT",
            "value": disruption,
        },
        "REVERSIBILITY": {
            "applicability": "APPLICABLE" if reversibility != "UNKNOWN" else "INCOMPARABLE",
            "direction": "MORE_REVERSIBLE_IS_MORE_FAVORABLE",
            "source": "ADVISORY_RESULT",
            "value": reversibility,
        },
    }
    option: dict[str, Any] = {
        "display_order": order,
        "option_code": code,
        "option_version": "1",
        "label": code,
        "evaluation_state": "ACTIVE",
        "recommendation_eligible": True,
        "value_status": value_status,
        "comparison_dimensions": dimensions,
        "provenance": {"option": {"reference": f"option:{code}", "content_hash": f"sha256:{code}"}},
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "suppression_reasons": [],
    }
    if value_status != "NOT_APPLICABLE":
        option["benefit_projection"] = {
            "net_assumption_value": {
                "lower": _pair(1),
                "central": _pair(50 if value_status == "VALUE_SENSITIVE" else 200),
                "upper": _pair(300),
            },
            "schedule_protection": {
                "basis": "PROJECT_DELAY_DAYS" if schedule is not None else "NOT_APPLICABLE",
                **({"duration_basis": "CALENDAR_DAY", "central": _pair(schedule)} if schedule is not None else {}),
            },
        }
        option["costs"] = {
            "direct_action_cost": {
                "amount": _pair(cost) if cost is not None else _pair(0),
                "currency": "INR",
            }
        }
    return option


def _evaluate(options: list[dict[str, Any]]) -> dict[str, Any]:
    return compare_and_publish(
        options=options,
        evaluation_occurrence_id=EVALUATION_ID,
        evaluation_series_id=SERIES_ID,
        input_digest=INPUT_DIGEST,
        provenance={"source": "synthetic-comparison-test"},
    )


def test_robust_option_can_universally_dominate_without_a_score() -> None:
    result = _evaluate(
        [
            _option("A", 1, schedule=8, cost=50, time=1),
            _option("B", 2, schedule=5, cost=100, time=2, risk="MEDIUM"),
        ]
    )

    assert result["outcome"] == "RECOMMENDATION_AVAILABLE"
    assert result["action_recommendation"]["selection_basis"] == (
        "UNIVERSAL_PARETO_DOMINANCE"
    )
    assert result["action_recommendation"]["selected_option_code"] == "A"
    assert result["action_recommendation"]["runner_up"]["option_code"] == "B"
    assert result["dominance_matrix"]["A"]["B"]["left_dominates"] is True
    assert all("weight" not in key.lower() for key in result["comparison"])
    assert "NO_HIDDEN_WEIGHTS" in result["comparison"]["policy_disclosures"]
    assert result["action_recommendation"]["provenance"]["evaluation_provenance"] == {
        "source": "synthetic-comparison-test"
    }


def test_runner_up_ties_use_display_order_and_are_annotated() -> None:
    result = _evaluate(
        [
            _option("A", 1, schedule=8, cost=50, time=1),
            _option("B", 2, schedule=5, cost=100, time=2, risk="MEDIUM"),
            _option("C", 3, schedule=4, cost=110, time=3, risk="HIGH"),
        ]
    )

    assert result["action_recommendation"]["runner_up"]["option_code"] == "B"
    assert result["action_recommendation"]["runner_up"]["ordering_evidence"]["annotation"] == (
        "TIED_UNDER_POLICY"
    )


def test_unknown_dimension_yields_two_candidates_and_an_evidence_gap_pivot() -> None:
    result = _evaluate(
        [
            _option("A", 1, schedule=8, cost=50, time=1, disruption="UNKNOWN"),
            _option("B", 2, schedule=5, cost=100, time=2, disruption="UNKNOWN"),
        ]
    )

    assert result["outcome"] == "TRADEOFF_REQUIRES_MANAGER_CHOICE"
    assert result["action_recommendation"] is None
    assert result["tradeoff"]["pivot"] == "INCOMPARABLE_EVIDENCE_GAP"
    assert [candidate["candidate_label"] for candidate in result["tradeoff"]["candidates"]] == [
        "A",
        "B",
    ]
    assert result["tradeoff"]["blocking_dimensions"] == [
        {"dimension": "OPERATIONAL_DISRUPTION", "reason_code": "UNKNOWN"}
    ]
    assert all(
        candidate["action_effect_evidence"] == "INTERVENTION_EFFECT_NOT_ESTIMATED"
        for candidate in result["tradeoff"]["candidates"]
    )
    for candidate in result["tradeoff"]["candidates"]:
        candidate_content = deepcopy(candidate)
        candidate_hash = candidate_content.pop("content_hash")
        assert sha256(candidate_content) == candidate_hash
    tradeoff_content = deepcopy(result["tradeoff"])
    tradeoff_hash = tradeoff_content.pop("content_hash")
    assert sha256(tradeoff_content) == tradeoff_hash
    evaluation_content = deepcopy(result["decision_support_evaluation"])
    evaluation_hash = evaluation_content.pop("content_hash")
    assert sha256(evaluation_content) == evaluation_hash


def test_value_sensitive_frontier_keeps_a_robust_safety_alternative() -> None:
    result = _evaluate(
        [
            _option(
                "SENSITIVE",
                1,
                value_status="VALUE_SENSITIVE",
                schedule=10,
                cost=20,
                time=1,
            ),
            _option("ROBUST", 2, schedule=5, cost=100, time=2, risk="MEDIUM"),
        ]
    )

    assert result["outcome"] == "TRADEOFF_REQUIRES_MANAGER_CHOICE"
    assert result["tradeoff"]["pivot"] == "VALUE_UNCERTAINTY"
    assert result["tradeoff"]["candidates"][0]["candidate_basis"] == (
        "PARETO_FRONTIER_OPTION"
    )
    assert result["tradeoff"]["candidates"][1]["candidate_basis"] == (
        "ROBUST_SAFETY_ALTERNATIVE"
    )
    assert result["tradeoff"]["candidates"][1]["option_code"] == "ROBUST"
    assert result["dominance_matrix"]["SENSITIVE"]["ROBUST"]["left_dominates"] is True


def test_only_value_sensitive_options_without_monitoring_fail_closed() -> None:
    sensitive = _option("SENSITIVE", 1, value_status="VALUE_SENSITIVE")
    result = _evaluate([sensitive])

    assert result["outcome"] == "NO_ELIGIBLE_OPTION"
    assert result["primary_reason_code"] == "VALUE_SENSITIVE_BASELINE_UNAVAILABLE"
    assert result["tradeoff"] is None
    assert result["action_recommendation"] is None


def test_normal_pivot_selects_the_frontier_option_best_on_that_dimension() -> None:
    result = _evaluate(
        [
            _option("A", 1, schedule=10, cost=100),
            _option("B", 2, schedule=8, cost=80),
            _option("C", 3, schedule=1, cost=50),
        ]
    )

    assert result["tradeoff"]["pivot"] == "DIRECT_ACTION_COST"
    assert result["tradeoff"]["candidates"][0]["option_code"] == "A"
    assert result["tradeoff"]["candidates"][1]["option_code"] == "C"


def test_equal_comparison_profile_and_true_tie_have_distinct_pivots() -> None:
    tied = _evaluate([_option("A", 1), _option("B", 2)])
    assert tied["tradeoff"]["pivot"] == "TIED_UNDER_POLICY"

    higher_net = _option("A", 1)
    lower_net = _option("B", 2)
    lower_net["benefit_projection"]["net_assumption_value"]["central"] = _pair(100)
    equal_profile = _evaluate([higher_net, lower_net])
    assert equal_profile["tradeoff"]["pivot"] == "EQUAL_COMPARISON_PROFILE"


def test_incompatible_duration_basis_is_an_evidence_gap() -> None:
    left = _option("A", 1)
    right = _option("B", 2)
    right["comparison_dimensions"]["TIME_TO_INITIATE"]["duration_basis"] = "BUSINESS_DAY"

    result = _evaluate([left, right])

    assert result["tradeoff"]["pivot"] == "INCOMPARABLE_EVIDENCE_GAP"
    assert result["tradeoff"]["blocking_dimensions"] == [
        {
            "dimension": "TIME_TO_INITIATE",
            "reason_code": "INCOMPATIBLE_INITIATION_DURATION_BASIS",
        }
    ]


def test_monitoring_is_a_transparent_fallback_and_not_a_pareto_candidate() -> None:
    monitor = _option("ACCEPT_AND_MONITOR", 9, value_status="NOT_APPLICABLE")
    monitor["recommendation_eligible"] = True
    non_positive = _option("A", 1, value_status="NON_POSITIVE_CENTRAL_VALUE")
    non_positive["recommendation_eligible"] = False
    result = _evaluate([non_positive, monitor])

    assert result["outcome"] == "RECOMMENDATION_AVAILABLE"
    recommendation = result["action_recommendation"]
    assert recommendation["selection_basis"] == (
        "MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION"
    )
    assert recommendation["selected_option_code"] == "ACCEPT_AND_MONITOR"
    assert recommendation["runner_up"] is None
    assert result["comparison"]["active_option_codes"] == []
    assert result["monitoring"]["state"] == "ELIGIBLE_FALLBACK"


def test_one_sided_not_applicable_blocks_a_cross_basis_pair() -> None:
    result = _evaluate(
        [
            _option("SCHEDULED", 1, schedule=5, cost=50),
            _option("DIRECT", 2, schedule=None, cost=50),
        ]
    )

    assert result["outcome"] == "TRADEOFF_REQUIRES_MANAGER_CHOICE"
    assert result["tradeoff"]["pivot"] == "INCOMPARABLE_EVIDENCE_GAP"
    assert {item["reason_code"] for item in result["tradeoff"]["blocking_dimensions"]} == {
        "ONE_SIDED_NOT_APPLICABLE"
    }
