from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from backend.app.canonical import sha256
from backend.app.decision_support import evaluate_synthetic_decision_support_fixture


FIXTURE_ROOT = (
    Path(__file__).parents[2] / "tests" / "fixtures" / "decision_support" / "v1"
)
CUTOFF = "2026-08-01T00:00:00+00:00"
NAMESPACE = "synthetic:core-decision-support-v1:"


def _read_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _fixture(name: str = "approved-reactive") -> tuple[dict[str, Any], dict[str, Any]]:
    records = _read_json("records.json")
    cases = _read_json("cases.json")
    fixture = next(
        item for item in cases["fixtures"] if item["fixture_id"].endswith(f":{name}")
    )
    return records, deepcopy(fixture)


def _rehash(record: dict[str, Any]) -> None:
    record.pop("content_hash", None)
    record["content_hash"] = sha256(record)


def _bind_snapshot(record: dict[str, Any], snapshot: dict[str, Any]) -> None:
    record.update(
        {
            "case_constraint_snapshot_ref": snapshot["snapshot_id"],
            "case_constraint_snapshot_hash": snapshot["content_hash"],
        }
    )
    _rehash(record)


def _approved_record(
    *,
    record_id: str,
    option_code: str | None = None,
    link_reference: str | None = None,
    trigger_mode: str = "REACTIVE",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "record_id": record_id,
        "schema_identifier": "decision-support-value-input",
        "schema_version": "1",
        "state": "APPROVED",
        "review_status": "APPROVED",
        "approval_scope": "SYNTHETIC_CONFORMANCE_ONLY",
        "review_reference": f"{record_id}:review",
        "review_available_at": CUTOFF,
        "review_date": CUTOFF,
        "reviewer_reference": f"{record_id}:reviewer",
        "reviewer_role": "SYNTHETIC_CONFORMANCE_REVIEW",
        "edited": False,
        "rationale": "Synthetic conformance value input.",
        "source_type": "MANAGER_ATTESTATION",
        "source_record_ref": f"{record_id}:source",
        "provenance_ref": f"{record_id}:provenance",
        "known_at": CUTOFF,
        "recorded_at": CUTOFF,
        "valid_through": "NO_EXPIRY",
        "trigger_mode": trigger_mode,
    }
    if option_code is not None:
        record.update(
            {
                "option_code": option_code,
                "option_version": "1",
                "subject_identity": "synthetic:core-decision-support-v1:subjects:approved-reactive",
            }
        )
    if link_reference is not None:
        record["link_reference"] = link_reference
    _rehash(record)
    return record


def _projection_fixture(
    *,
    option_code: str = "PROTECTED_PRODUCTION_SLOT",
    effect: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    records, fixture = _fixture()
    link = next(
        item
        for item in records["driver_action_links"]
        if item["option_code"] == option_code and item["trigger_mode"] == "REACTIVE"
    )
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    inputs: dict[str, Any] = {
        "canonical_slippage_duration_basis": "CALENDAR_DAY",
        "cost_of_critical_path_delay_per_day": _approved_record(
            record_id=f"{NAMESPACE}value-inputs:cost-of-delay:approved-reactive:v1",
        ),
        "direct_action_costs": [],
        "benefit_assumptions": [],
    }
    rate = inputs["cost_of_critical_path_delay_per_day"]
    rate.update(
        {
            "formula_identifier": "COST_OF_CRITICAL_PATH_DELAY_PER_DAY.v1",
            "amount": "decimal:100000",
            "currency": "INR",
            "day_basis": "CANONICAL_SLIPPAGE_DAY",
            "resolved_duration_basis": "CALENDAR_DAY",
        }
    )
    _bind_snapshot(rate, snapshot)
    cost = _approved_record(
        record_id=f"{NAMESPACE}value-inputs:cost:{option_code.lower()}:approved-reactive:v1",
        option_code=option_code,
        link_reference=link["record_id"],
    )
    cost.update(
        {
            "formula_identifier": "DECLARED_TOTAL_COST.v1",
            "total": "decimal:150000",
            "currency": "INR",
        }
    )
    _bind_snapshot(cost, snapshot)
    inputs["direct_action_costs"].append(cost)

    recoverable = _approved_record(
        record_id=f"{NAMESPACE}value-inputs:recoverable:{option_code.lower()}:approved-reactive:v1",
        option_code=option_code,
        link_reference=link["record_id"],
    )
    recoverable.update(
        {
            "assumption_kind": "RECOVERABLE_FRACTION",
            "selected_value": "decimal:0.4",
            "default_value": "decimal:0.4",
            "default_assumption_ref": link["default_assumption_ref"],
            "edited": False,
            "rationale": "Synthetic conformance recoverability assumption.",
        }
    )
    _bind_snapshot(recoverable, snapshot)
    translation = _approved_record(
        record_id=f"{NAMESPACE}value-inputs:translation:{option_code.lower()}:approved-reactive:v1",
        option_code=option_code,
        link_reference=link["record_id"],
    )
    translation.update(
        {
            "assumption_kind": "CRITICAL_PATH_TRANSLATION_FRACTION",
            "selected_value": "decimal:1",
            "default_value": None,
            "edited": False,
            "rationale": "Synthetic conformance critical-path translation assumption.",
            "manager_attestation_reference": (
                f"{NAMESPACE}attestations:translation:approved-reactive:v1"
            ),
        }
    )
    _bind_snapshot(translation, snapshot)
    inputs["benefit_assumptions"].extend([recoverable, translation])

    fixture["operational_inputs"]["decision_support_value_inputs"] = inputs
    if effect:
        fixture["evidence"]["subject_verdict"]["effect"] = {
            "estimate": 10.0,
            "ci_lower": 6.0,
            "ci_upper": 14.0,
            "unit": "days",
            "duration_basis": "CALENDAR_DAY",
        }
    _rehash(fixture)
    return records, fixture, link["record_id"]


def test_exposure_projection_keeps_exact_schedule_and_money_dimensions_separate() -> None:
    records, fixture, _ = _projection_fixture()

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "ACTIVE"
    assert protected["value_status"] == "ROBUSTLY_POSITIVE"
    assert protected["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] == (
        "EXPOSURE_TRANSLATION_ASSUMPTION"
    )
    projection = protected["benefit_projection"]
    assert projection["disclosure"] == "ASSUMPTION_BASED_PROJECTION_RANGE"
    assert projection["recovered_supplier_milestone_days"] == {
        "lower": {"numerator": "12", "denominator": "5"},
        "central": {"numerator": "4", "denominator": "1"},
        "upper": {"numerator": "28", "denominator": "5"},
    }
    assert projection["project_delay_days_protected"] == {
        "lower": {"numerator": "12", "denominator": "5"},
        "central": {"numerator": "4", "denominator": "1"},
        "upper": {"numerator": "28", "denominator": "5"},
    }
    assert projection["gross_avoided_delay_value"] == {
        "lower": {"numerator": "240000", "denominator": "1"},
        "central": {"numerator": "400000", "denominator": "1"},
        "upper": {"numerator": "560000", "denominator": "1"},
    }
    assert projection["net_assumption_value"] == {
        "lower": {"numerator": "90000", "denominator": "1"},
        "central": {"numerator": "250000", "denominator": "1"},
        "upper": {"numerator": "410000", "denominator": "1"},
    }
    assert projection["schedule_protection"] == {
        "basis": "PROJECT_DELAY_DAYS",
        "duration_basis": "CALENDAR_DAY",
        "central": {"numerator": "4", "denominator": "1"},
    }
    assert protected["costs"]["direct_action_cost"]["amount"] == {
        "numerator": "150000",
        "denominator": "1",
    }
    assert protected["action_effect_evidence"] == "INTERVENTION_EFFECT_NOT_ESTIMATED"
    assert "confidence interval" in " ".join(protected["caveats"])


def test_direct_monetary_consequence_does_not_invent_schedule_protection() -> None:
    records, fixture, _ = _projection_fixture(
        option_code="PHASED_DELIVERY",
        effect=False,
    )
    inputs = fixture["operational_inputs"]["decision_support_value_inputs"]
    inputs["cost_of_critical_path_delay_per_day"] = None
    inputs["direct_action_costs"][0]["formula_identifier"] = (
        "DECLARED_TOTAL_COST.v1"
    )
    inputs["benefit_assumptions"] = [
        _approved_record(
            record_id=f"{NAMESPACE}value-inputs:consequence:phased-delivery:approved-reactive:v1",
            option_code="PHASED_DELIVERY",
            link_reference=next(
                item["record_id"]
                for item in records["driver_action_links"]
                if item["option_code"] == "PHASED_DELIVERY"
                and item["trigger_mode"] == "REACTIVE"
            ),
        )
    ]
    inputs["benefit_assumptions"][0].update(
        {
            "assumption_kind": "CONSEQUENCE_BENEFIT",
            "basis": "DIRECT_MONETARY_VALUE",
            "lower": "decimal:200000",
            "central": "decimal:300000",
            "upper": "decimal:450000",
            "currency": "INR",
            "edited": False,
            "rationale": "Synthetic consequence assumption.",
        }
    )
    _bind_snapshot(inputs["benefit_assumptions"][0], fixture["operational_inputs"]["case_constraint_snapshot"])
    inputs["direct_action_costs"][0]["total"] = "decimal:100000"
    _bind_snapshot(inputs["direct_action_costs"][0], fixture["operational_inputs"]["case_constraint_snapshot"])
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    phased = next(
        option
        for option in result["options"]
        if option["option_code"] == "PHASED_DELIVERY"
    )

    assert phased["evaluation_state"] == "ACTIVE"
    assert phased["value_status"] == "ROBUSTLY_POSITIVE"
    assert phased["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] == (
        "OPERATIONAL_ASSUMPTION_ONLY"
    )
    projection = phased["benefit_projection"]
    assert projection["gross_consequence_value"] == {
        "lower": {"numerator": "200000", "denominator": "1"},
        "central": {"numerator": "300000", "denominator": "1"},
        "upper": {"numerator": "450000", "denominator": "1"},
    }
    assert projection["net_assumption_value"] == {
        "lower": {"numerator": "100000", "denominator": "1"},
        "central": {"numerator": "200000", "denominator": "1"},
        "upper": {"numerator": "350000", "denominator": "1"},
    }
    assert projection["schedule_protection"]["basis"] == "NOT_APPLICABLE"
    assert "duration_basis" not in projection["schedule_protection"]
    assert "recovered_supplier_milestone_days" not in projection


def test_missing_translation_and_cost_stays_unavailable_without_fabricating_zero() -> None:
    records, fixture, _ = _projection_fixture()
    inputs = fixture["operational_inputs"]["decision_support_value_inputs"]
    inputs["direct_action_costs"] = []
    inputs["benefit_assumptions"] = [inputs["benefit_assumptions"][0]]
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "SUPPRESSED"
    assert protected["value_status"] == "UNAVAILABLE"
    assert protected["benefit_projection"] is None
    assert protected["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] == "UNAVAILABLE"
    assert [reason["code"] for reason in protected["suppression_reasons"]] == [
        "CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE",
        "ACTION_COST_UNAVAILABLE",
    ]
    assert protected["unavailable_reasons"]
    assert "net_assumption_value" not in json.dumps(protected)


def test_currency_mismatch_is_a_global_fail_closed_result_without_conversion() -> None:
    records, fixture, _ = _projection_fixture()
    inputs = fixture["operational_inputs"]["decision_support_value_inputs"]
    inputs["direct_action_costs"][0]["currency"] = "BRL"
    _rehash(inputs["direct_action_costs"][0])
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == "DECISION_SUPPORT_CURRENCY_MISMATCH"
    assert result["options"] == []


def test_value_sensitive_range_remains_active_for_downstream_tradeoff() -> None:
    records, fixture, _ = _projection_fixture()
    translation = fixture["operational_inputs"]["decision_support_value_inputs"][
        "benefit_assumptions"
    ][1]
    translation["selected_value"] = "decimal:0.5"
    _rehash(translation)
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "ACTIVE"
    assert protected["value_status"] == "VALUE_SENSITIVE"
    assert protected["recommendation_eligible"] is True
    assert protected["suppression_reasons"] == []
    assert protected["benefit_projection"]["net_assumption_value"] == {
        "lower": {"numerator": "-30000", "denominator": "1"},
        "central": {"numerator": "50000", "denominator": "1"},
        "upper": {"numerator": "130000", "denominator": "1"},
    }


def test_non_positive_central_value_suppresses_the_option() -> None:
    records, fixture, _ = _projection_fixture()
    cost = fixture["operational_inputs"]["decision_support_value_inputs"][
        "direct_action_costs"
    ][0]
    cost["total"] = "decimal:400000"
    _rehash(cost)
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "SUPPRESSED"
    assert protected["value_status"] == "NON_POSITIVE_CENTRAL_VALUE"
    assert protected["recommendation_eligible"] is False
    assert protected["suppression_reasons"][-1]["code"] == (
        "NON_POSITIVE_CENTRAL_NET_VALUE"
    )


def test_invalid_fraction_and_rate_inputs_fail_closed_without_arithmetic() -> None:
    records, fixture, _ = _projection_fixture()
    inputs = fixture["operational_inputs"]["decision_support_value_inputs"]
    inputs["benefit_assumptions"][0]["selected_value"] = "decimal:1.1"
    inputs["cost_of_critical_path_delay_per_day"]["resolved_duration_basis"] = (
        "BUSINESS_DAY"
    )
    _rehash(inputs["benefit_assumptions"][0])
    _rehash(inputs["cost_of_critical_path_delay_per_day"])
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "SUPPRESSED"
    assert protected["benefit_projection"] is None
    assert [reason["code"] for reason in protected["suppression_reasons"]] == [
        "RECOVERABLE_FRACTION_INVALID",
        "CRITICAL_PATH_DELAY_RATE_INVALID",
    ]
    assert "net_assumption_value" not in json.dumps(protected)


def test_composite_uses_its_own_single_link_and_declared_total() -> None:
    records, fixture, _ = _projection_fixture(
        option_code="PROTECTED_SLOT_WITH_PHASED_DELIVERY"
    )
    cost = fixture["operational_inputs"]["decision_support_value_inputs"][
        "direct_action_costs"
    ][0]
    cost["formula_identifier"] = "DECLARED_COMPOSITE_TOTAL.v1"
    _rehash(cost)
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    composite = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_SLOT_WITH_PHASED_DELIVERY"
    )

    assert composite["evaluation_state"] == "ACTIVE"
    assert composite["value_status"] == "ROBUSTLY_POSITIVE"
    assert composite["benefit_projection"]["net_assumption_value"] == {
        "lower": {"numerator": "90000", "denominator": "1"},
        "central": {"numerator": "250000", "denominator": "1"},
        "upper": {"numerator": "410000", "denominator": "1"},
    }
    assert composite["benefit_projection"]["provenance"][
        "primary_driver_action_link"
    ]["reference"].endswith(
        ":driver-action-links:protected_slot_with_phased_delivery:reactive:v1"
    )


def test_value_input_edit_creates_a_distinct_immutable_evaluation_identity() -> None:
    records, fixture, _ = _projection_fixture()
    first = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    cost = fixture["operational_inputs"]["decision_support_value_inputs"][
        "direct_action_costs"
    ][0]
    cost["total"] = "decimal:160000"
    _rehash(cost)
    _rehash(fixture)
    second = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert first["decision_support_evaluation_series_id"] == second[
        "decision_support_evaluation_series_id"
    ]
    assert first["decision_support_evaluation_id"] != second[
        "decision_support_evaluation_id"
    ]
    assert first["decision_support_input_digest"] != second[
        "decision_support_input_digest"
    ]


def test_one_robust_option_publishes_a_provenance_bound_recommendation() -> None:
    records, fixture, _ = _projection_fixture()

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "RECOMMENDATION_AVAILABLE"
    assert result["tradeoff"] is None
    recommendation = result["action_recommendation"]
    assert recommendation["selection_basis"] == "SOLE_ELIGIBLE_OPTION"
    assert recommendation["selected_option_code"] == "PROTECTED_PRODUCTION_SLOT"
    assert recommendation["runner_up"] is None
    assert recommendation["content_hash"].startswith("sha256:")
    recommendation_content = dict(recommendation)
    recommendation_content.pop("content_hash")
    assert sha256(recommendation_content) == recommendation["content_hash"]

    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )
    assert protected["comparison_dimensions"]["SCHEDULE_PROTECTION"] == {
        "applicability": "APPLICABLE",
        "basis": "PROJECT_DELAY_DAYS",
        "direction": "HIGHER_IS_MORE_FAVORABLE",
        "duration_basis": "CALENDAR_DAY",
        "source": "VALUE_PROJECTION",
        "unit": "project_delay_days",
        "value": {"numerator": "4", "denominator": "1"},
    }
    assert protected["comparison_dimensions"]["DIRECT_ACTION_COST"] == {
        "applicability": "APPLICABLE",
        "currency": "INR",
        "direction": "LOWER_IS_MORE_FAVORABLE",
        "source": "VALUE_PROJECTION",
        "unit": "INR",
        "value": {"numerator": "150000", "denominator": "1"},
    }
    assert "approval" not in recommendation
    assert "authorization" not in recommendation


def test_canonical_cost_inputs_object_is_consumed_without_reordering_records() -> None:
    records, fixture, _ = _projection_fixture()
    inputs = fixture["operational_inputs"]["decision_support_value_inputs"]
    inputs["cost_inputs"] = {
        "critical_path_delay_rate": inputs.pop("cost_of_critical_path_delay_per_day"),
        "option_costs": inputs.pop("direct_action_costs"),
    }
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )

    assert protected["evaluation_state"] == "ACTIVE"
    assert protected["benefit_projection"]["net_assumption_value"]["central"] == {
        "numerator": "250000",
        "denominator": "1",
    }
