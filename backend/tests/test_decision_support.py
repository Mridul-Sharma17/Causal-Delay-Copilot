from __future__ import annotations

import json

from backend.app.decision_support import evaluate_decision_support


def _request(*, trigger_mode: str = "reactive", exposure: bool = True) -> dict:
    primary = {
        "state": "present",
        "high_load_exposure": exposure,
        "provisional_high_load_preview": exposure,
    }
    return {
        "investigation_request_id": "investigation-1",
        "trigger_mode": trigger_mode,
        "subject": (
            {"order_line_id": "line-1"}
            if trigger_mode == "reactive"
            else {"preview_subject_digest": "preview-1"}
        ),
        "causal_engine_input": {
            "supplier_load_exposure": {"primary": primary},
        },
    }


def test_permission_false_exposes_exact_denial_without_evaluating_actions() -> None:
    next_step = "Supply the frozen subject support before applying population evidence."
    result = evaluate_decision_support(
        investigation_request=_request(),
        subject_applicability={
            "state": "abstained",
            "subject_identity": "line-1",
            "reason_code": "SUBJECT_OVERLAP_INSUFFICIENT",
            "reason": "Subject support is insufficient for this reference journey.",
            "next_step": next_step,
        },
        subject_verdict={
            "scope": "subject",
            "verdict_code": "INSUFFICIENT",
            "decision_support_role_permitted": False,
            "decision_support_evaluation_permitted": False,
            "primary_trigger_code": "SUBJECT_OVERLAP_INSUFFICIENT",
        },
        population_verdict={
            "scope": "population",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        intended_role="semi_synthetic_hero",
    )

    assert result["schema_version"] == "decision-support-boundary.v1"
    assert result["outcome"] == "NOT_PERMITTED"
    assert result["permission"] == {
        "decision_support_evaluation_permitted": False,
        "denial_reason_code": "SUBJECT_OVERLAP_INSUFFICIENT",
        "reason": "Subject support is insufficient for this reference journey.",
        "next_step": next_step,
    }
    assert result["decision_support_evaluation_id"] is None
    assert result["decision_support_permission_digest"].startswith("sha256:")
    assert result["permission_provenance"]["requested_use"] == "DECISION_SUPPORT"
    assert result["action_recommendation"] is None
    assert result["consumed_inputs"] == ["permission_envelope"]
    assert "constraints_as_of" not in json.dumps(result)
    assert result["suppression_reasons"] == [
        {
            "code": "SUBJECT_OVERLAP_INSUFFICIENT",
            "category": "PERMISSION",
            "priority": 100,
            "reason": "Subject support is insufficient for this reference journey.",
        }
    ]

    catalog = result["registry_inspection"]
    assert catalog["intervention_library"]["identifier"] == "core-intervention-library"
    assert [
        option["option_code"] for option in catalog["intervention_library"]["options"]
    ] == [
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
    assert catalog["driver_action_links"]
    assert all(
        link["review_status"] == "PROVISIONAL"
        for link in catalog["driver_action_links"]
    )
    assert catalog["advisory_rubrics"]
    assert all(
        rubric["state"] == "UNAVAILABLE_PENDING_REVIEW"
        for rubric in catalog["advisory_rubrics"]
    )
    assert catalog["monitoring_triggers"]
    assert all(
        trigger["state"] == "UNAVAILABLE_PENDING_REVIEW"
        for trigger in catalog["monitoring_triggers"]
    )
    composite = catalog["composite_reviews"][0]
    assert composite["option_code"] == "PROTECTED_SLOT_WITH_PHASED_DELIVERY"
    assert composite["option_version"] == "1"
    assert composite["state"] == "UNAVAILABLE_PENDING_REVIEW"
    assert composite["review_status"] == "PROVISIONAL"
    assert composite["content_hash"].startswith("sha256:")


def test_false_reactive_driver_is_inactive_without_consuming_constraints() -> None:
    result = evaluate_decision_support(
        investigation_request=_request(exposure=False),
        subject_applicability={
            "state": "applicable",
            "subject_identity": "line-1",
            "reason": "Subject support is sufficient.",
            "next_step": "Inspect the separately governed action boundary.",
        },
        subject_verdict={
            "scope": "subject",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        population_verdict={
            "scope": "population",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        intended_role="semi_synthetic_hero",
    )

    assert result["outcome"] == "NO_ELIGIBLE_OPTION"
    assert result["state"] == "inactive_driver"
    assert result["primary_reason_code"] == "SUBJECT_DRIVER_NOT_ACTIVE"
    assert result["reason"] == (
        "The verified subject was not in High-Load Exposure at the causal decision "
        "cutoff. No driver-linked option was evaluated. This does not state what "
        "caused any observed or future delay."
    )
    assert result["subject_driver_state"]["kind"] == "high_load_exposure"
    assert result["subject_driver_state"]["value"] is False
    assert result["consumed_inputs"] == [
        "permission_envelope",
        "subject_driver_state",
    ]
    assert "constraints_as_of" not in json.dumps(result)
    assert len(result["options"]) == 10
    assert all(option["evaluation_state"] == "NOT_EVALUATED" for option in result["options"])
    assert all(
        option["suppression_reasons"] == [
            {
                "code": "SUBJECT_DRIVER_NOT_ACTIVE",
                "category": "DRIVER_STATE",
                "priority": 0,
                "reason": result["reason"],
            }
        ]
        for option in result["options"]
    )
    assert all(
        option["evidence_tags"] == {
            "DRIVER_EVIDENCE": "NOT_EVALUATED",
            "MECHANISTIC_LINK": "NOT_EVALUATED",
            "RULE_BASED_ELIGIBILITY": "NOT_EVALUATED",
            "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
        }
        for option in result["options"]
    )


def test_mismatched_verified_verdict_binding_fails_closed() -> None:
    result = evaluate_decision_support(
        investigation_request=_request(),
        subject_applicability={"state": "abstained", "subject_identity": "line-1"},
        subject_verdict={
            "scope": "subject",
            "decision_support_role_permitted": False,
            "decision_support_evaluation_permitted": False,
            "content_hash": "sha256:" + "0" * 64,
        },
        population_verdict=None,
        intended_role="semi_synthetic_hero",
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH"
    assert result["decision_support_evaluation_id"] is None


def test_non_mapping_verdict_fails_closed_without_an_exception() -> None:
    result = evaluate_decision_support(
        investigation_request=_request(),
        subject_applicability={"state": "abstained", "subject_identity": "line-1"},
        subject_verdict=[],  # type: ignore[arg-type]
        population_verdict=None,
        intended_role="semi_synthetic_hero",
    )

    assert result["outcome"] == "FAILED"
    assert result["primary_reason_code"] == "DECISION_SUPPORT_INPUT_SCHEMA_INVALID"
    assert result["decision_support_evaluation_id"] is None


def test_false_proactive_preview_uses_preview_wording_and_state_kind() -> None:
    result = evaluate_decision_support(
        investigation_request=_request(trigger_mode="proactive", exposure=False),
        subject_applicability={
            "state": "applicable",
            "subject_identity": "preview-1",
        },
        subject_verdict={
            "scope": "subject",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        population_verdict={
            "scope": "population",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        intended_role="semi_synthetic_hero",
    )

    assert result["outcome"] == "NO_ELIGIBLE_OPTION"
    assert result["subject_driver_state"]["kind"] == "provisional_high_load_preview"
    assert result["subject_driver_state"]["value"] is False
    assert result["reason"] == (
        "The verified proposal's provisional preview did not meet the High-Load "
        "Exposure threshold at the causal decision cutoff. No driver-linked option "
        "was evaluated. This preview is not a canonical exposure fact and does not "
        "state what caused any delay."
    )


def test_shipped_active_driver_stops_at_provisional_records_without_recommendation() -> None:
    result = evaluate_decision_support(
        investigation_request=_request(),
        subject_applicability={
            "state": "applicable",
            "subject_identity": "line-1",
        },
        subject_verdict={
            "scope": "subject",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        population_verdict={
            "scope": "population",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        intended_role="semi_synthetic_hero",
        release_candidate_id="test-release",
        runtime_fingerprint_digest="sha256:test-runtime",
    )

    assert result["outcome"] == "NO_ELIGIBLE_OPTION"
    assert result["state"] == "approval_dependent_suppressed"
    assert result["primary_reason_code"] == "PRACTITIONER_REVIEW_UNAVAILABLE"
    assert result["action_recommendation"] is None
    assert result["tradeoff"] is None
    assert result["monitoring"] == {
        "state": "SUPPRESSED",
        "reason_code": "MONITORING_TRIGGER_UNDER_SPECIFIED",
    }
    assert result["drafting"] == {"state": "NOT_PERMITTED"}
    assert result["authorization"] == {"state": "NOT_PERMITTED"}
    assert result["consumed_inputs"] == [
        "permission_envelope",
        "subject_driver_state",
        "intervention_library",
        "driver_action_links",
        "release_binding",
    ]
    assert "constraints_as_of" not in json.dumps(result)
    assert "case_constraint_snapshot" not in json.dumps(result)
    assert "net_central" not in json.dumps(result)

    by_code = {option["option_code"]: option for option in result["options"]}
    assert len(by_code) == 10
    assert by_code["RELEASE_TIMING_ADJUSTMENT"]["suppression_reasons"] == [
        {
            "code": "TRIGGER_MODE_INCOMPATIBLE",
            "category": "OPTION",
            "priority": 100,
            "reason": "This option is not registered for the reactive trigger mode.",
        }
    ]
    assert by_code["RELEASE_TIMING_ADJUSTMENT"]["evidence_tags"] == {
        "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
        "MECHANISTIC_LINK": "NOT_EVALUATED",
        "RULE_BASED_ELIGIBILITY": "NOT_EVALUATED",
        "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
    }
    for option_code, option in by_code.items():
        if option_code == "RELEASE_TIMING_ADJUSTMENT":
            continue
        assert option["evaluation_state"] == "SUPPRESSED"
        assert option["suppression_reasons"] == [
            {
                "code": "DRIVER_ACTION_LINK_PROVISIONAL",
                "category": "OPTION",
                "priority": 210,
                "reason": "The exact Driver-Action Link is provisional because practitioner review is unavailable.",
            }
        ]
        assert option["evidence_tags"]["DRIVER_EVIDENCE"] == (
            "SUPPORTED_UNDER_ASSUMPTIONS"
        )
        assert option["evidence_tags"]["MECHANISTIC_LINK"] == "PROVISIONAL"
        assert option["evidence_tags"]["RULE_BASED_ELIGIBILITY"] == "NOT_EVALUATED"
        assert option["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] == "NOT_EVALUATED"
        assert option["action_effect_evidence"] == "INTERVENTION_EFFECT_NOT_ESTIMATED"
        assert option["speculative_disclosure"] == "PRESENT"
