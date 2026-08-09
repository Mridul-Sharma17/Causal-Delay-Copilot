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
    assert (
        next(
            option
            for option in options
            if option["option_code"] == "RELEASE_TIMING_ADJUSTMENT"
        )["suppression_reasons"][0]["code"]
        == "TRIGGER_MODE_INCOMPATIBLE"
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
    assert "benefit_projection" not in json.dumps(result)


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
