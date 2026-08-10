from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.canonical import sha256
from backend.app.draft_context import (
    DraftContextUnavailable,
    check_deterministic_draft,
    prepare_draft_from_current_advice,
)
from backend.app.main import create_app
from backend.app.settings import Settings


def _hash_record(record: dict[str, object]) -> str:
    content = deepcopy(record)
    content.pop("content_hash", None)
    return sha256(content)


def _current_advice() -> dict[str, object]:
    recommendation: dict[str, object] = {
        "schema_identifier": "action-recommendation",
        "schema_version": "1",
        "action_recommendation_key": "recommendation-key-1",
        "occurrence_id": "action-recommendation:recommendation-key-1",
        "evaluation_series_id": "series-1",
        "evaluation_occurrence_id": "evaluation-1",
        "decision_support_input_digest": "sha256:" + "1" * 64,
        "selected_option_code": "PROTECTED_PRODUCTION_SLOT",
        "selected_option_version": "1",
        "selection_basis": "SOLE_ELIGIBLE_OPTION",
        "selected_option": {
            "option_code": "PROTECTED_PRODUCTION_SLOT",
            "option_version": "1",
            "label": "Protected production slot",
            "evaluation_state": "ACTIVE",
            "recommendation_eligible": True,
            "benefit_projection": {
                "schedule_protection": {
                    "basis": "PROJECT_DELAY_DAYS",
                    "duration_basis": "CALENDAR_DAY",
                    "central": {"numerator": "4", "denominator": "1"},
                },
                "net_assumption_value": {
                    "lower": {"numerator": "90000", "denominator": "1"},
                    "central": {"numerator": "250000", "denominator": "1"},
                    "upper": {"numerator": "410000", "denominator": "1"},
                },
                "caveats": ["ASSUMPTION_BASED_PROJECTION_RANGE"],
            },
            "costs": {
                "direct_action_cost": {
                    "amount": {"numerator": "150000", "denominator": "1"},
                    "currency": "INR",
                }
            },
            "provenance": {
                "primary_driver_action_link": {
                    "reference": "driver-action-link:protected-production-slot",
                    "content_hash": "sha256:" + "2" * 64,
                }
            },
        },
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "evidence_tags": {
            "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
            "MECHANISTIC_LINK": "APPROVED",
            "RULE_BASED_ELIGIBILITY": "SUPPORTED",
            "ASSUMPTION_BASED_BENEFIT": "ASSUMPTION_BASED",
        },
        "subject_identity": "unsafe-internal-order-line-001",
        "subject_driver_state": {
            "kind": "high_load_exposure",
            "value": True,
        },
        "subject_verdict": {
            "scope": "subject",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "permitted_claim_scope": "population_and_subject",
            "decision_support_evaluation_permitted": True,
            "effect": {"estimate": 1.5, "ci_lower": 0.2, "ci_upper": 2.8},
        },
        "population_verdict": {
            "scope": "population",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "permitted_claim_scope": "population_and_subject",
        },
        "causal_decision_at": "2026-08-09T10:00:00+00:00",
        "constraints_as_of": "2026-08-09T10:01:00+00:00",
        "evaluation_published_at": "2026-08-09T10:02:00+00:00",
        "investigation_request_ref_and_hash": {
            "reference": "investigation-request:1",
            "content_hash": "sha256:" + "3" * 64,
        },
        "analysis_run_bundle_ref_and_hash": {
            "reference": "analysis-run:1",
            "content_hash": "sha256:" + "4" * 64,
        },
        "subject_verdict_ref_and_hash": {
            "reference": "subject-verdict:1",
            "content_hash": "sha256:" + "5" * 64,
        },
        "population_verdict_ref_and_hash": {
            "reference": "population-verdict:1",
            "content_hash": "sha256:" + "6" * 64,
        },
        "case_constraint_snapshot_ref_and_hash": {
            "reference": "constraint-snapshot:1",
            "content_hash": "sha256:" + "7" * 64,
        },
        "intervention_library_ref_and_hash": {
            "reference": "intervention-library:1",
            "content_hash": "sha256:" + "8" * 64,
        },
        "driver_action_link_ref_and_hash": {
            "reference": "driver-action-link:1",
            "content_hash": "sha256:" + "9" * 64,
        },
        "explanation_template_identifiers": [
            {"identifier": "decision-support.action-recommendation", "version": "1"}
        ],
        "selection_is_not_authorization": True,
        "authorization": {"state": "NOT_RECORDED"},
        "provenance": {
            "evaluation_provenance": {
                "reference": "decision-support-evaluation:1",
                "content_hash": "sha256:" + "a" * 64,
            }
        },
    }
    recommendation["content_hash"] = _hash_record(recommendation)

    operation_ref = {
        "reference": "currentness-operation:1",
        "content_hash": "sha256:" + "b" * 64,
    }
    check_ref = {
        "reference": "currentness-check:1",
        "content_hash": "sha256:" + "c" * 64,
    }
    render: dict[str, object] = {
        "schema_identifier": "current-advice-render-result",
        "schema_version": "1",
        "render_result_occurrence_id": "render-result-1",
        "current_advice_render_result_key": "render-key-1",
        "advice_chain_kind": "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "recommendation_ref_and_hash_or_null": {
            "reference": recommendation["occurrence_id"],
            "content_hash": recommendation["content_hash"],
        },
        "accepted_selection_claim_ref_and_hash_or_null": None,
        "evaluation_result_ref_and_hash": {
            "reference": "decision-support-result:evaluation-1",
            "content_hash": "sha256:" + "d" * 64,
        },
        "current_as_of": "2026-08-09T10:03:00+00:00",
        "currentness_operation_ref_and_hash": operation_ref,
        "currentness_check_ref_and_hash": check_ref,
        "advice_chain": {
            "outcome": "RECOMMENDATION_AVAILABLE",
            "action_recommendation": recommendation,
            "evidence_tags": recommendation["evidence_tags"],
        },
    }
    render["content_hash"] = _hash_record(render)
    head = {
        "head_kind": "EVALUATION",
        "head_occurrence_id": "evaluation-1",
        "head_record_ref_and_hash": {
            "reference": "evaluation-1",
            "content_hash": "sha256:" + "f" * 64,
        },
    }
    return {
        "result": "CREATED",
        "operation": {
            "currentness_operation_ref_and_hash": operation_ref,
            "terminal_result_ref_and_hash": render["evaluation_result_ref_and_hash"],
            "recommendation_ref_and_hash_or_null": render[
                "recommendation_ref_and_hash_or_null"
            ],
            "accepted_selection_claim_ref_and_hash_or_null": None,
        },
        "currentness": {
            "currentness_check_occurrence_id": "1",
            "content_hash": check_ref["content_hash"],
            "currentness_outcome": "CURRENTNESS_PROVEN_AT_CHECK",
            "currentness_evidence_digest": "sha256:" + "e" * 64,
            "currentness_checked_at": "2026-08-09T10:03:00+00:00",
            "currentness_operation_ref_and_hash": operation_ref,
            "evaluation_head_ref_and_hash": head["head_record_ref_and_hash"],
            "observed_authoritative_head_ref_and_hash": head[
                "head_record_ref_and_hash"
            ],
            "observed_authoritative_head_kind": "EVALUATION",
            "evaluation_occurrence_id": "evaluation-1",
        },
        "terminal_claim": {
            "currentness_outcome": "CURRENTNESS_PROVEN_AT_CHECK",
            "terminal_currentness_ref_and_hash": check_ref,
            "consuming_result_kind": "current-advice-render-result",
            "terminal_head": head,
        },
        "head": head,
        "render": render,
    }


def test_valid_current_advice_produces_a_deterministic_unsent_preview() -> None:
    current_advice = _current_advice()

    first = prepare_draft_from_current_advice(current_advice)
    second = prepare_draft_from_current_advice(current_advice)

    assert first == second
    context = first["draft_context"]
    artifact = first["artifact"]
    assert context["schema_identifier"] == "draft-context"
    assert context["schema_version"] == "1"
    assert artifact["state"] == "UNSENT_PREVIEW"
    assert artifact["source"] == "DETERMINISTIC_ZERO_LLM"
    assert first["checker"]["state"] == "PASS"
    assert "unsafe-internal-order-line-001" not in str(first)
    assert "raw_rows" not in str(first)
    assert "Protected production slot" in artifact["body"]
    assert "2026-08-09T10:00:00+00:00" in artifact["body"]
    assert "250000" in artifact["body"]
    assert "[APPROVED_RECIPIENT]" in artifact["body"]
    assert "does not establish an individual delay cause" in artifact["body"]
    assert "does not approve, authorize, send, or execute anything" in artifact["body"]
    assert context["provenance"]["action_recommendation"]["reference"].startswith(
        "action-recommendation:"
    )
    assert {
        authorization["field"] for authorization in context["fact_authorization"]
    } == {fact["field"] for fact in context["facts"]}
    assert all(
        authorization["source"] == "action_recommendation.selected_option"
        and authorization["recommendation_ref_and_hash"]
        == context["provenance"]["action_recommendation"]
        and authorization["evidence_tags"] == context["evidence_tags"]
        for authorization in context["fact_authorization"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["currentness"].update(
            {"currentness_outcome": "ADVICE_CURRENTNESS_INVALIDATION"}
        ),
        lambda value: value["render"]["advice_chain"].update(
            {"action_recommendation": None}
        ),
        lambda value: value["render"]["advice_chain"]["action_recommendation"].update(
            {"content_hash": "sha256:" + "0" * 64}
        ),
        lambda value: value["render"]["advice_chain"]["action_recommendation"].update(
            {"authorization": {"state": "AUTHORIZED"}}
        ),
        lambda value: value["render"]["advice_chain"]["action_recommendation"][
            "selected_option"
        ].update({"label": "SUPPLIER-PRIVATE contract reroute"}),
    ],
)
def test_invalid_or_unsafe_advice_produces_no_draft(mutation) -> None:
    current_advice = _current_advice()
    mutation(current_advice)

    with pytest.raises(DraftContextUnavailable):
        prepare_draft_from_current_advice(current_advice)


def test_currentness_bindings_must_match_the_rendered_advice() -> None:
    mutations = (
        lambda value: value["operation"]["currentness_operation_ref_and_hash"].update(
            {"content_hash": "sha256:" + "0" * 64}
        ),
        lambda value: value["operation"]["terminal_result_ref_and_hash"].update(
            {"content_hash": "sha256:" + "0" * 64}
        ),
        lambda value: value["currentness"].update(
            {"content_hash": "sha256:" + "0" * 64}
        ),
    )
    for mutation in mutations:
        current_advice = _current_advice()
        mutation(current_advice)
        with pytest.raises(DraftContextUnavailable):
            prepare_draft_from_current_advice(current_advice)

    current_advice = _current_advice()
    current_advice["terminal_claim"]["terminal_head"] = deepcopy(
        current_advice["terminal_claim"]["terminal_head"]
    )
    current_advice["terminal_claim"]["terminal_head"][
        "head_record_ref_and_hash"
    ].update({"content_hash": "sha256:" + "0" * 64})
    with pytest.raises(DraftContextUnavailable):
        prepare_draft_from_current_advice(current_advice)


def test_missing_explanation_template_provenance_is_not_draftable() -> None:
    current_advice = _current_advice()
    recommendation = current_advice["render"]["advice_chain"]["action_recommendation"]
    recommendation.pop("explanation_template_identifiers")
    recommendation["content_hash"] = _hash_record(recommendation)
    current_advice["render"]["recommendation_ref_and_hash_or_null"]["content_hash"] = (
        recommendation["content_hash"]
    )
    current_advice["operation"]["recommendation_ref_and_hash_or_null"][
        "content_hash"
    ] = recommendation["content_hash"]
    current_advice["render"]["content_hash"] = _hash_record(current_advice["render"])

    with pytest.raises(DraftContextUnavailable):
        prepare_draft_from_current_advice(current_advice)


def test_checker_rejects_tampered_numbers_entities_actions_and_template() -> None:
    prepared = prepare_draft_from_current_advice(_current_advice())

    tampered = deepcopy(prepared["artifact"])
    tampered["body"] = tampered["body"].replace("250000", "999999")
    result = check_deterministic_draft(prepared["draft_context"], tampered)
    assert result["state"] == "FAIL"
    assert "UNAUTHORIZED_NUMERIC_TOKEN" in result["failure_codes"]
    assert "TEMPLATE_INTEGRITY_FAILED" in result["failure_codes"]

    tampered = deepcopy(prepared["artifact"])
    tampered["body"] = tampered["body"] + " Please send this automatically."
    result = check_deterministic_draft(prepared["draft_context"], tampered)
    assert result["state"] == "FAIL"
    assert "BLOCKED_ACTION" in result["failure_codes"]

    tampered = deepcopy(prepared["artifact"])
    tampered["body"] = tampered["body"] + " Unapproved destination entity."
    result = check_deterministic_draft(prepared["draft_context"], tampered)
    assert result["state"] == "FAIL"
    assert "UNAUTHORIZED_ENTITY" in result["failure_codes"]

    tampered = deepcopy(prepared["artifact"])
    tampered["body"] = tampered["body"].replace(
        "supported under stated assumptions",
        "proves the cause of the delay",
    )
    result = check_deterministic_draft(prepared["draft_context"], tampered)
    assert result["state"] == "FAIL"
    assert "CAUSAL_LANGUAGE_TOO_STRONG" in result["failure_codes"]


def test_api_reproves_current_advice_before_returning_a_sanitized_preview(
    tmp_path,
    monkeypatch,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "core.sqlite3"))
    stored_payload = _current_advice()
    stored_payload["consuming_result"] = None

    def fake_render_current_advice(_workspace_id, *, render_request):
        assert render_request["render_mode"] == "CURRENT_ADVICE"
        return SimpleNamespace(**stored_payload)

    monkeypatch.setattr(
        app.state.audit_store,
        "render_current_advice",
        fake_render_current_advice,
    )
    render_request = {
        "schema_identifier": "current-advice-render-request",
        "schema_version": "1",
        "render_mode": "CURRENT_ADVICE",
        "evaluation_series_id": "series-1",
        "evaluation_occurrence_id": "evaluation-1",
        "evaluation_digest": "sha256:" + "1" * 64,
        "terminal_result_ref_and_hash": {
            "reference": "decision-support-result:evaluation-1",
            "content_hash": "sha256:" + "d" * 64,
        },
        "advice_chain_kind": "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "recommendation_ref_and_hash_or_null": {
            "reference": "action-recommendation:recommendation-key-1",
            "content_hash": stored_payload["render"]["advice_chain"][
                "action_recommendation"
            ]["content_hash"],
        },
        "accepted_selection_claim_ref_and_hash_or_null": None,
        "advice_chain_published_at": "2026-08-09T10:02:00+00:00",
        "requested_at": "2026-08-09T10:03:00+00:00",
        "available_at": "2026-08-09T10:03:00+00:00",
    }

    with TestClient(app) as client:
        client.get("/api/workspace")
        response = client.post(
            "/api/decision-support/draft-context",
            json={"current_advice": render_request},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_identifier"] == "deterministic-draft-preview"
    assert body["state"] == "UNSENT_PREVIEW"
    assert body["checker"]["state"] == "PASS"
    assert "unsafe-internal-order-line-001" not in response.text
