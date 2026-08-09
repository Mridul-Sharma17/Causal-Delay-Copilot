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
OPTION_CODES = [
    "PROTECTED_PRODUCTION_SLOT",
    "QUALIFIED_SOURCE_SPLIT",
    "PREQUALIFIED_ALTERNATE",
    "RELEASE_TIMING_ADJUSTMENT",
    "CAPACITY_BACKED_ACCELERATION",
    "PHASED_DELIVERY",
    "DEPENDENT_WORK_RESEQUENCING",
    "CONTRACTUAL_ESCALATION",
    "ACCEPT_AND_MONITOR",
    "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
]


def _read_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _pack() -> tuple[dict[str, Any], dict[str, Any]]:
    return _read_json("records.json"), _read_json("cases.json")


def _fixture(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    records, cases = _pack()
    fixture = next(
        item for item in cases["fixtures"] if item["fixture_id"].endswith(f":{name}")
    )
    return records, fixture


def _rehash(record: dict[str, Any]) -> None:
    record.pop("content_hash", None)
    record["content_hash"] = sha256(record)


def test_active_fixture_evaluates_every_closed_option_and_retains_provenance() -> None:
    records, fixture = _fixture("approved-reactive")

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "NO_ELIGIBLE_OPTION"
    assert result["state"] == "constraints_evaluated"
    assert result["primary_reason_code"] == "CONSTRAINT_EVALUATION_COMPLETE"
    assert result["case_constraint_snapshot"]["snapshot_id"].endswith(
        ":constraints:approved-reactive:v1"
    )
    assert result["case_constraint_snapshot"]["idempotency_key"]
    assert result["case_constraint_snapshot"]["source"]["source_type"] == (
        "SYNTHETIC_CONFORMANCE_FIXTURE"
    )

    options = result["options"]
    assert [option["option_code"] for option in options] == OPTION_CODES
    assert all(
        option["evaluation_state"] == "ACTIVE"
        for option in options
        if option["option_code"] != "RELEASE_TIMING_ADJUSTMENT"
    )
    release = next(
        option
        for option in options
        if option["option_code"] == "RELEASE_TIMING_ADJUSTMENT"
    )
    assert release["suppression_reasons"][0]["code"] == "TRIGGER_MODE_INCOMPATIBLE"
    assert release["advisory_results"] == []
    assert release["comparison_state"] == "NOT_EVALUATED"
    assert all(
        dimension["applicability"] == "NOT_EVALUATED"
        for dimension in release["comparison_dimensions"].values()
    )
    assert all(
        option["action_effect_evidence"] == "INTERVENTION_EFFECT_NOT_ESTIMATED"
        for option in options
    )

    protected = options[0]
    assert [item["rule_code"] for item in protected["constraint_results"]] == [
        "PROTECTED_SLOT_MECHANISM_VERIFIED",
        "PROTECTED_SLOT_SUPPLIER_ACCEPTED",
        "PROTECTED_SLOT_WITHIN_FLOAT",
    ]
    assert [item["status"] for item in protected["constraint_results"]] == [
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
    ]
    assert all(
        item["rule_version"] == "1"
        and item["option_scope"] == "PROTECTED_PRODUCTION_SLOT"
        and item["observed_facts"]
        and item["evidence_refs"]
        and item["explanation_code"]
        for item in protected["constraint_results"]
    )
    assert protected["evidence_tags"] == {
        "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
        "MECHANISTIC_LINK": "REVIEWED_PLAUSIBLE",
        "RULE_BASED_ELIGIBILITY": "SATISFIED",
        "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
    }
    assert protected["provenance"]["case_constraint_snapshot"][
        "content_hash"
    ].startswith("sha256:")
    assert protected["provenance"]["driver_action_link"]["reference"].endswith(
        ":driver-action-links:protected_production_slot:reactive:v1"
    )

    monitor = next(
        option for option in options if option["option_code"] == "ACCEPT_AND_MONITOR"
    )
    assert monitor["evidence_tags"]["MECHANISTIC_LINK"] == "REVIEWED_BASELINE"
    assert monitor["constraint_results"][-1]["status"] == "SATISFIED"
    assert result["action_recommendation"] is None
    assert "net_central" not in json.dumps(result)
    assert "net_assumption_value" not in json.dumps(result)


def test_active_fixture_publishes_advisories_and_explicit_comparison_applicability() -> None:
    records, fixture = _fixture("approved-reactive")

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )
    advisories = {
        advisory["dimension"]: advisory
        for advisory in protected["advisory_results"]
    }

    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["status"] == "KNOWN"
    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["value"] == "LOW"
    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["matched_rule"]["priority"] == 10
    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["rubric"]["rubric_version"] == "1"
    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["input_values"] == [
        {
            "fact_code": "PROTECTED_SLOT_SUPPLIER_ACCEPTED",
            "value": True,
        }
    ]
    assert advisories["CONTRACTUAL_RELATIONSHIP_RISK"]["provenance"][
        "case_constraint_snapshot"
    ]["reference"].endswith(":constraints:approved-reactive:v1")

    for dimension in ("OPERATIONAL_DISRUPTION", "REVERSIBILITY"):
        advisory = advisories[dimension]
        assert advisory["status"] == "UNKNOWN"
        assert advisory["value"] == "UNKNOWN"
        assert [reason["code"] for reason in advisory["reasons"]] == [
            "RUBRIC_INPUT_MISSING"
        ]

    comparison_dimensions = protected["comparison_dimensions"]
    assert comparison_dimensions["CONTRACTUAL_RELATIONSHIP_RISK"] == {
        "applicability": "APPLICABLE",
        "value": "LOW",
        "direction": "LOWER_IS_MORE_FAVORABLE",
        "source": "ADVISORY_RESULT",
    }
    assert comparison_dimensions["OPERATIONAL_DISRUPTION"]["applicability"] == (
        "INCOMPARABLE"
    )
    assert comparison_dimensions["OPERATIONAL_DISRUPTION"]["value"] == "UNKNOWN"
    assert comparison_dimensions["OPERATIONAL_DISRUPTION"]["reason_codes"] == [
        "RUBRIC_INPUT_MISSING"
    ]
    assert protected["comparison_state"] == "INCOMPARABLE_EVIDENCE"


def test_unapproved_advisory_is_unknown_without_suppressing_eligible_option() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)

    rubric = next(
        rubric
        for rubric in records["advisory_rubrics"]
        if rubric["option_code"] == "PROTECTED_PRODUCTION_SLOT"
        and rubric["dimension"] == "CONTRACTUAL_RELATIONSHIP_RISK"
        and rubric["trigger_mode"] == "REACTIVE"
    )
    rubric["state"] = "PROVISIONAL"
    _rehash(rubric)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )
    advisory = next(
        advisory
        for advisory in protected["advisory_results"]
        if advisory["dimension"] == "CONTRACTUAL_RELATIONSHIP_RISK"
    )

    assert protected["evaluation_state"] == "ACTIVE"
    assert advisory["status"] == "UNKNOWN"
    assert [reason["code"] for reason in advisory["reasons"]] == [
        "RUBRIC_NOT_APPROVED"
    ]
    assert protected["comparison_dimensions"][
        "CONTRACTUAL_RELATIONSHIP_RISK"
    ]["applicability"] == "INCOMPARABLE"


def test_pending_advisory_declaration_is_explicitly_unavailable() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)

    library = records["intervention_libraries"][0]
    option = next(
        option
        for option in library["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )
    declaration = next(
        declaration
        for declaration in option["advisory_rubric_declarations"]
        if declaration["dimension"] == "CONTRACTUAL_RELATIONSHIP_RISK"
        and declaration["trigger_mode"] == "REACTIVE"
    )
    declaration["rubric_reference"] = "UNAVAILABLE_PENDING_REVIEW"
    _rehash(library)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )
    protected = next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )
    advisory = next(
        advisory
        for advisory in protected["advisory_results"]
        if advisory["dimension"] == "CONTRACTUAL_RELATIONSHIP_RISK"
    )

    assert protected["evaluation_state"] == "ACTIVE"
    assert advisory["status"] == "UNKNOWN"
    assert [reason["code"] for reason in advisory["reasons"]] == [
        "RUBRIC_UNAVAILABLE"
    ]


def test_malformed_advisory_rubric_fails_before_option_evaluation() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)

    rubric = next(
        rubric
        for rubric in records["advisory_rubrics"]
        if rubric["option_code"] == "PROTECTED_PRODUCTION_SLOT"
        and rubric["dimension"] == "CONTRACTUAL_RELATIONSHIP_RISK"
        and rubric["trigger_mode"] == "REACTIVE"
    )
    rubric["result_contract"]["allowed_values"] = ["LOW", "UNSUPPORTED"]
    _rehash(rubric)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == (
        "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH"
    )
    assert result["options"] == []


def test_composite_advisories_retain_component_results_and_derivation() -> None:
    records, fixture = _fixture("approved-reactive")

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
    for advisory in composite["advisory_results"]:
        assert advisory["derivation"] == {
            "kind": "LEAST_FAVORABLE_COMPONENT_RESULTS.v1",
            "version": "1",
        }
        assert [
            component["option_code"]
            for component in advisory["component_results"]
        ] == ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"]
        assert advisory["status"] == "UNKNOWN"
        assert "RUBRIC_COMPONENT_RESULT_UNKNOWN" in [
            reason["code"] for reason in advisory["reasons"]
        ]
    assert composite["comparison_dimensions"]["TIME_TO_INITIATE"]["reason_codes"] == [
        "TIME_COMPOSITION_RULE_UNAVAILABLE"
    ]


def test_composite_review_after_cutoff_suppresses_only_composite_with_explicit_reason() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)
    fixture = deepcopy(fixture)

    review = records["composite_reviews"][0]
    review["published_at"] = "2026-08-02T00:00:00+00:00"
    review["review_available_at"] = "2026-08-02T00:00:00+00:00"
    _rehash(review)
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    review_fact = next(
        fact
        for fact in snapshot["facts"]
        if fact["fact_code"] == "COMPOSITE_COMPATIBILITY_REVIEW_REF"
    )
    review_fact["value"]["content_hash"] = review["content_hash"]
    _rehash(snapshot)
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
    compatibility = next(
        rule
        for rule in composite["constraint_results"]
        if rule["rule_code"] == "COMPOSITE_COMPONENTS_COMPATIBLE"
    )

    assert composite["evaluation_state"] == "SUPPRESSED"
    assert compatibility["status"] == "UNKNOWN"
    assert compatibility["explanation_code"] == "COMPOSITE_REVIEW_NOT_AVAILABLE_AT_CUTOFF"
    assert composite["suppression_reasons"][-1]["code"] == (
        "REQUIRED_CONSTRAINT_UNKNOWN"
    )
    assert next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )["evaluation_state"] == "ACTIVE"


def test_approved_incompatible_composite_review_suppresses_composite_only() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)
    fixture = deepcopy(fixture)

    review = records["composite_reviews"][0]
    review["attestations"][2]["outcome"] = "ATTESTED_INCOMPATIBLE"
    review["outcome"] = "INCOMPATIBLE"
    review["compatibility_status"] = "UNSATISFIED"
    _rehash(review)
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    review_fact = next(
        fact
        for fact in snapshot["facts"]
        if fact["fact_code"] == "COMPOSITE_COMPATIBILITY_REVIEW_REF"
    )
    review_fact["value"]["content_hash"] = review["content_hash"]
    _rehash(snapshot)
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
    compatibility = next(
        rule
        for rule in composite["constraint_results"]
        if rule["rule_code"] == "COMPOSITE_COMPONENTS_COMPATIBLE"
    )

    assert composite["evaluation_state"] == "SUPPRESSED"
    assert compatibility["status"] == "UNSATISFIED"
    assert compatibility["explanation_code"] == "COMPOSITE_REVIEW_INCOMPATIBLE"
    assert composite["suppression_reasons"][-1]["code"] == (
        "REQUIRED_CONSTRAINT_UNSATISFIED"
    )
    assert next(
        option
        for option in result["options"]
        if option["option_code"] == "PROTECTED_PRODUCTION_SLOT"
    )["evaluation_state"] == "ACTIVE"


def test_composite_review_with_reordered_attestations_is_global_schema_failure() -> None:
    records, fixture = _fixture("approved-reactive")
    records = deepcopy(records)
    fixture = deepcopy(fixture)

    review = records["composite_reviews"][0]
    review["attestations"][1]["attestation_code"] = (
        "COMPONENT_IDENTITIES_ALIGNED"
    )
    _rehash(review)
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    review_fact = next(
        fact
        for fact in snapshot["facts"]
        if fact["fact_code"] == "COMPOSITE_COMPATIBILITY_REVIEW_REF"
    )
    review_fact["value"]["content_hash"] = review["content_hash"]
    _rehash(snapshot)
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == "DECISION_SUPPORT_INPUT_SCHEMA_INVALID"
    assert result["options"] == []


def test_missing_and_false_facts_are_both_retained_in_locked_suppression_order() -> (
    None
):
    records, fixture = _fixture("approved-reactive")
    fixture = deepcopy(fixture)
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    assert isinstance(snapshot, dict)
    mechanism = next(
        fact
        for fact in snapshot["facts"]
        if fact["fact_code"] == "PROTECTED_SLOT_MECHANISM_KIND"
    )
    mechanism["state"] = "missing"
    supplier_acceptance = next(
        fact
        for fact in snapshot["facts"]
        if fact["fact_code"] == "PROTECTED_SLOT_SUPPLIER_ACCEPTED"
    )
    supplier_acceptance["value"] = False
    _rehash(snapshot)
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
    assert [item["status"] for item in protected["constraint_results"]] == [
        "UNKNOWN",
        "UNSATISFIED",
        "SATISFIED",
    ]
    assert [
        (reason["code"], reason["constraint_rule_priority"])
        for reason in protected["suppression_reasons"]
    ] == [
        ("REQUIRED_CONSTRAINT_UNSATISFIED", 110),
        ("REQUIRED_CONSTRAINT_UNKNOWN", 100),
    ]
    assert result["primary_reason_code"] == "CONSTRAINT_EVALUATION_COMPLETE"


def test_permission_and_inactive_fixture_branches_do_not_consume_constraints() -> None:
    records, inactive_fixture = _fixture("inactive-driver")
    inactive = evaluate_synthetic_decision_support_fixture(
        fixture_case=inactive_fixture,
        governed_records=records,
    )
    assert inactive["state"] == "inactive_driver"
    assert inactive["outcome"] == "NO_ELIGIBLE_OPTION"
    assert inactive["options"]
    assert all(
        option["evaluation_state"] == "NOT_EVALUATED" for option in inactive["options"]
    )
    assert "case_constraint_snapshot" not in json.dumps(inactive)

    records, permission_fixture = _fixture("permission-denied")
    denied = evaluate_synthetic_decision_support_fixture(
        fixture_case=permission_fixture,
        governed_records=records,
    )
    assert denied["state"] == "not_permitted"
    assert denied["outcome"] == "NOT_PERMITTED"
    assert denied["options"] == []
    assert denied["consumed_inputs"] == ["permission_envelope"]
    assert "case_constraint_snapshot" not in json.dumps(denied)


def test_unknown_snapshot_fact_fails_closed_before_evaluating_options() -> None:
    records, fixture = _fixture("approved-reactive")
    fixture = deepcopy(fixture)
    snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["facts"].append(
        {
            "fact_code": "RUNTIME_INVENTED_RULE_INPUT",
            "known_at": snapshot["constraints_as_of"],
            "provenance_ref": "synthetic:core-decision-support-v1:invented",
            "recorded_at": snapshot["constraints_as_of"],
            "source_available_at": snapshot["constraints_as_of"],
            "source_record_ref": "synthetic:core-decision-support-v1:invented",
            "source_type": "VERIFIED_UPSTREAM_RECORD",
            "state": "present",
            "valid_through": "NO_EXPIRY",
            "value": True,
        }
    )
    _rehash(snapshot)
    _rehash(fixture)

    result = evaluate_synthetic_decision_support_fixture(
        fixture_case=fixture,
        governed_records=records,
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == "DECISION_SUPPORT_INPUT_SCHEMA_INVALID"
    assert result["options"] == []
