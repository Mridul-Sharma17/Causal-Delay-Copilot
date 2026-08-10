from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.canonical import sha256
from backend.app.decision_support_currentness import (
    DecisionSupportCurrentnessConflict,
    DecisionSupportCurrentnessUnavailable,
)
from backend.app.ingestion import LineageStore
from backend.app.main import create_app
from backend.app.settings import Settings


def _identity_binding() -> dict[str, object]:
    library_dependency = {
        "dependency_kind": "INTERVENTION_LIBRARY_VERSION",
        "reference": "library-1",
        "id": "library-1",
        "version": "1",
        "content_hash": "sha256:" + "8" * 64,
        "consumed_disposition": "APPROVED",
        "unique_unsuperseded_head": True,
        "supported": True,
        "current": {
            "reference": "library-1",
            "id": "library-1",
            "version": "1",
            "content_hash": "sha256:" + "8" * 64,
            "disposition": "APPROVED",
            "unique_unsuperseded_head": True,
            "supported": True,
        },
    }
    dependency = {
        "dependency_kind": "DRIVER_ACTION_LINK_VERSION",
        "reference": "link-1",
        "id": "link-1",
        "version": "1",
        "content_hash": "sha256:" + "6" * 64,
        "consumed_disposition": "APPROVED",
        "effective": True,
        "unique_unsuperseded_head": True,
        "current": {
            "reference": "link-1",
            "id": "link-1",
            "version": "1",
            "content_hash": "sha256:" + "6" * 64,
            "disposition": "APPROVED",
            "option_code": "A",
            "option_version": "1",
            "trigger_mode": "REACTIVE",
            "effective": True,
            "unique_unsuperseded_head": True,
            "superseded_by": None,
        },
    }
    return {
        "evaluation_series_id": "series-tradeoff-1",
        "investigation_request": {
            "record_id": "investigation-1",
            "content_hash": "sha256:" + "1" * 64,
        },
        "subject_identity": "order-line-1",
        "causal_decision_at": "2026-08-09T10:00:00+00:00",
        "trigger_mode": "reactive",
        "trigger_mode_mapping": "REACTIVE",
        "constraints_as_of": "2026-08-09T10:00:00+00:00",
        "requested_claim_scope": "population_and_subject",
        "analysis_run_bundle_ref_and_hash": {
            "reference": "analysis-run-1",
            "content_hash": "sha256:" + "3" * 64,
        },
        "verified_analysis_run_bundle_binding": {
            "analysis_run_id": "analysis-run-1",
            "bundle_manifest_hash": "sha256:" + "3" * 64,
            "scientific_request_digest": "sha256:" + "c" * 64,
            "engine_request_descriptor_hash": "sha256:" + "d" * 64,
            "producer_schema_identifier": "causal-engine-suite-result",
            "producer_schema_version": "v2",
        },
        "case_constraint_snapshot_ref_and_hash": {
            "reference": "constraint-snapshot-1",
            "content_hash": "sha256:" + "5" * 64,
        },
        "intervention_library_ref_and_hash": {
            "reference": "library-1",
            "content_hash": "sha256:" + "8" * 64,
        },
        "driver_action_link_ref_and_hash": {
            "reference": "link-1",
            "content_hash": "sha256:" + "6" * 64,
        },
        "subject_verdict": {
            "record_id": "subject-verdict-1",
            "content_hash": "sha256:" + "9" * 64,
        },
        "population_verdict": {
            "record_id": "population-verdict-1",
            "content_hash": "sha256:" + "b" * 64,
        },
        "subject_driver_state": {
            "kind": "high_load_exposure",
            "value": True,
            "content_hash": "sha256:" + "4" * 64,
        },
        "governed_records": {
            "advice_currentness_dependency_set": [library_dependency, dependency],
        },
        "operational_snapshot": {
            "snapshot_id": "constraint-snapshot-1",
            "content_hash": "sha256:" + "5" * 64,
            "facts": [
                {
                    "input_path": "case_constraint_snapshot.facts[0]",
                    "source_record_ref": "fact-1",
                    "content_hash": "sha256:" + "7" * 64,
                    "valid_through": "NO_EXPIRY",
                }
            ]
        },
        "available_at": "2026-08-09T10:00:00+00:00",
    }


def _candidate(
    evaluation_occurrence_id: str,
    option_code: str,
    label: str,
) -> dict[str, object]:
    candidate: dict[str, object] = {
        "candidate_label": label,
        "candidate_basis": "PARETO_FRONTIER_OPTION",
        "candidate_reference": {
            "evaluation_occurrence_id": evaluation_occurrence_id,
            "option_code": option_code,
            "option_version": "1",
        },
        "option_code": option_code,
        "option_version": "1",
        "label": label,
        "value_status": "ROBUSTLY_POSITIVE",
        "comparison_profile": {
            "DIRECT_ACTION_COST": {"value": option_code},
        },
        "option_evaluation": {
            "option_code": option_code,
            "option_version": "1",
            "label": label,
            "evaluation_state": "ACTIVE",
            "recommendation_eligible": True,
        },
        "provenance": {"option": {"reference": f"option:{option_code}"}},
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "ordering_evidence": {"display_order": 10 if option_code == "A" else 20},
    }
    candidate["content_hash"] = sha256(candidate)
    return candidate


def _tradeoff_evaluation() -> tuple[dict[str, object], dict[str, object]]:
    evaluation_occurrence_id = "evaluation-tradeoff-1"
    candidates = [
        _candidate(evaluation_occurrence_id, "A", "Candidate A"),
        _candidate(evaluation_occurrence_id, "B", "Candidate B"),
    ]
    tradeoff: dict[str, object] = {
        "candidate_count": 2,
        "pivot": "DIRECT_ACTION_COST",
        "candidates": candidates,
        "blocking_dimensions": [],
    }
    tradeoff["content_hash"] = sha256(tradeoff)
    evaluation: dict[str, object] = {
        "schema_version": "decision-support-boundary.v1",
        "outcome": "TRADEOFF_REQUIRES_MANAGER_CHOICE",
        "state": "tradeoff_requires_choice",
        "primary_reason_code": None,
        "reason": "Two exact candidates remain.",
        "next_step": "Choose one candidate.",
        "permission": {
            "decision_support_evaluation_permitted": True,
            "denial_reason_code": None,
            "reason": "supported",
            "next_step": "select",
        },
        "decision_support_evaluation_id": evaluation_occurrence_id,
        "decision_support_evaluation_series_id": "series-tradeoff-1",
        "decision_support_input_digest": "sha256:" + "a" * 64,
        "options": [],
        "evidence_tags": {
            "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
            "MECHANISTIC_LINK": "APPROVED",
            "RULE_BASED_ELIGIBILITY": "SUPPORTED",
            "ASSUMPTION_BASED_BENEFIT": "ASSUMPTION_BASED",
        },
        "suppression_reasons": [],
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "action_recommendation": None,
        "explanation_template_identifiers": [
            {
                "identifier": "decision-support.tradeoff-selection",
                "version": "1",
            },
            {
                "identifier": "decision-support.action-recommendation",
                "version": "1",
            },
        ],
        "tradeoff": tradeoff,
        "monitoring": {"state": "NOT_AVAILABLE"},
        "drafting": {"state": "NOT_PERMITTED"},
        "authorization": {"state": "NOT_PERMITTED"},
        "consumed_inputs": [],
    }
    return evaluation, {"evaluation_occurrence_id": evaluation_occurrence_id, "candidates": candidates}


def _store(tmp_path: Path) -> tuple[TestClient, str, LineageStore]:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    return client, workspace_id, client.app.state.audit_store


def _publish(store: LineageStore, workspace_id: str):
    evaluation, metadata = _tradeoff_evaluation()
    return store.publish_decision_support_evaluation(
        workspace_id,
        idempotency_key="evaluation-tradeoff-1",
        evaluation=evaluation,
        identity_binding=_identity_binding(),
        now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        evaluation_occurrence_id=metadata["evaluation_occurrence_id"],
    ), metadata


def _selection(published: object, metadata: dict[str, object], *, code: str, selection_id: str):
    evaluation = published.evaluation  # type: ignore[attr-defined]
    candidate = next(
        item for item in metadata["candidates"] if item["option_code"] == code  # type: ignore[index]
    )
    record: dict[str, object] = {
        "schema_identifier": "tradeoff-selection",
        "schema_version": "1",
        "selection_occurrence_id": selection_id,
        "evaluation_series_id": evaluation["evaluation_series_id"],
        "evaluation_occurrence_id": evaluation["evaluation_occurrence_id"],
        "evaluation_digest": evaluation["evaluation_digest"],
        "terminal_result_ref_and_hash": deepcopy(
            evaluation["terminal_result_ref_and_hash"]
        ),
        "selected_candidate_ref": f"candidate:{metadata['evaluation_occurrence_id']}:{code}:1",
        "selected_candidate": deepcopy(candidate),
        "manager_actor_ref": "anonymous-demo-manager",
        "selected_at": evaluation["evaluation_published_at"],
        "available_at": evaluation["evaluation_published_at"],
    }
    record["content_hash"] = sha256(record)
    record["governance_tradeoff_selection_ref_and_hash"] = {
        "reference": f"governance-tradeoff-selection:{selection_id}",
        "content_hash": record["content_hash"],
    }
    return record


def _attempt(selection: dict[str, object], *, attempt_id: str, delivered_at: str | None = None):
    attempt: dict[str, object] = {
        "schema_identifier": "tradeoff-selection-delivery-attempt",
        "schema_version": "1",
        "occurrence_id": attempt_id,
        "tradeoff_selection_ref_and_hash": {
            "reference": selection["selection_occurrence_id"],
            "content_hash": selection["content_hash"],
        },
        "evaluation_series_id": selection["evaluation_series_id"],
        "evaluation_occurrence_id": selection["evaluation_occurrence_id"],
        "evaluation_digest": selection["evaluation_digest"],
        "terminal_result_ref_and_hash": deepcopy(
            selection["terminal_result_ref_and_hash"]
        ),
        "selected_candidate_ref": selection["selected_candidate_ref"],
        "selected_candidate": deepcopy(selection["selected_candidate"]),
        "selection_available_at": selection["available_at"],
        "delivered_at": delivered_at or selection["available_at"],
        "available_at": delivered_at or selection["available_at"],
    }
    attempt["content_hash"] = sha256(attempt)
    return attempt


def test_accept_tradeoff_selection_publishes_one_proof_bound_recommendation(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        attempt = _attempt(selection, attempt_id="attempt-a")

        accepted = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=attempt,
            currentness_context={"governed_dependency_resolutions": []},
            now=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
        )

        assert accepted.selection_result["selection_result"] == "TRADEOFF_SELECTION_ACCEPTED"
        assert accepted.currentness["currentness_outcome"] == "CURRENTNESS_PROVEN_AT_CHECK"
        assert accepted.operation["currentness_checked_at"] == accepted.delivery_attempt[
            "available_at"
        ]
        assert accepted.delivery_attempt["available_at"] != attempt["available_at"]
        assert accepted.operation["currentness_checked_at"] != (
            "2026-08-09T10:00:00+00:00"
        )
        assert accepted.action_recommendation["selection_basis"] == "MANAGER_TRADEOFF_SELECTION"
        assert accepted.action_recommendation["selected_option_code"] == "A"
        assert accepted.action_recommendation["decision_support_input_digest"] == (
            "sha256:" + "a" * 64
        )
        assert accepted.action_recommendation["selected_candidate_ref"] == (
            "candidate:evaluation-tradeoff-1:A:1"
        )
        assert accepted.action_recommendation["presented_alternative"]["option_code"] == "B"
        assert accepted.action_recommendation["authorization"]["state"] == "NOT_RECORDED"
        assert accepted.action_recommendation["investigation_request_ref_and_hash"] == {
            "reference": "investigation-1",
            "content_hash": "sha256:" + "1" * 64,
        }
        assert accepted.action_recommendation["analysis_run_bundle_ref_and_hash"] == {
            "reference": "analysis-run-1",
            "content_hash": "sha256:" + "3" * 64,
        }
        assert accepted.action_recommendation[
            "verified_analysis_run_bundle_binding"
        ]["engine_request_descriptor_hash"] == "sha256:" + "d" * 64
        assert accepted.action_recommendation[
            "verified_analysis_run_bundle_binding"
        ]["producer_schema_version"] == "v2"
        assert accepted.action_recommendation[
            "explanation_template_identifiers"
        ] == [
            {
                "identifier": "decision-support.tradeoff-selection",
                "version": "1",
            },
            {
                "identifier": "decision-support.action-recommendation",
                "version": "1",
            },
        ]
        assert accepted.action_recommendation["intervention_library_ref_and_hash"] == {
            "reference": "library-1",
            "content_hash": "sha256:" + "8" * 64,
        }
        assert accepted.action_recommendation["driver_action_link_ref_and_hash"] == {
            "reference": "link-1",
            "content_hash": "sha256:" + "6" * 64,
        }
        assert accepted.action_recommendation["monitoring_activated_at"] == "NOT_APPLICABLE"
        assert accepted.action_recommendation["selection_is_not_authorization"] is True
        assert accepted.action_recommendation[
            "governance_tradeoff_selection_ref_and_hash"
        ] == {
            "reference": "governance-tradeoff-selection:selection-a",
            "content_hash": selection["content_hash"],
        }
        assert accepted.action_recommendation[
            "creation_currentness_operation_ref_and_hash"
        ]["reference"].startswith("currentness-operation:")
        assert accepted.action_recommendation["exact_evaluation_terminal_result"][
            "outcome"
        ] == "TRADEOFF_REQUIRES_MANAGER_CHOICE"
        assert accepted.selection_claim["creation_currentness_check_ref_and_hash"] == {
            "reference": f"currentness-check:{accepted.currentness['currentness_check_occurrence_id']}",
            "content_hash": accepted.currentness["content_hash"],
        }
        render_request = {
            "schema_identifier": "current-advice-render-request",
            "schema_version": "1",
            "render_mode": "CURRENT_ADVICE",
            "evaluation_series_id": published.evaluation["evaluation_series_id"],  # type: ignore[attr-defined]
            "evaluation_occurrence_id": published.evaluation["evaluation_occurrence_id"],  # type: ignore[attr-defined]
            "evaluation_digest": published.evaluation["evaluation_digest"],  # type: ignore[attr-defined]
            "terminal_result_ref_and_hash": published.evaluation["terminal_result_ref_and_hash"],  # type: ignore[attr-defined]
            "advice_chain_kind": "ACCEPTED_TRADEOFF_SELECTION",
            "recommendation_ref_and_hash_or_null": {
                "reference": accepted.action_recommendation["occurrence_id"],
                "content_hash": accepted.action_recommendation["content_hash"],
            },
            "accepted_selection_claim_ref_and_hash_or_null": {
                "reference": f"tradeoff-selection-claim:{accepted.selection_claim['selection_claim_occurrence_id']}",
                "content_hash": accepted.selection_claim["content_hash"],
            },
            "advice_chain_published_at": accepted.selection_claim["published_at"],
            "requested_at": accepted.selection_claim["published_at"],
            "available_at": accepted.selection_claim["published_at"],
        }
        rendered = store.render_current_advice(
            workspace_id,
            render_request=render_request,
        )
        assert rendered.render["advice_chain"]["action_recommendation"][
            "selection_basis"
        ] == "MANAGER_TRADEOFF_SELECTION"

        series = store.get_decision_support_evaluation_series(
            workspace_id,
            published.evaluation["evaluation_series_id"],  # type: ignore[attr-defined]
        )
        assert series is not None
        assert series["head"]["head_kind"] == "EVALUATION"
        assert series["history"][0]["action_recommendation"] is None
        assert any(
            item["occurrence_kind"] == "GOVERNANCE_TRADEOFF_SELECTION"
            for item in client.get("/api/audit/occurrences").json()["items"]
        )
    finally:
        client.__exit__(None, None, None)


def test_missing_analysis_provenance_fails_closed_without_recommendation(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        evaluation, metadata = _tradeoff_evaluation()
        identity = _identity_binding()
        verified_binding = identity["verified_analysis_run_bundle_binding"]
        assert isinstance(verified_binding, dict)
        verified_binding.pop("engine_request_descriptor_hash")
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-tradeoff-missing-provenance",
            evaluation=evaluation,
            identity_binding=identity,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
            evaluation_occurrence_id=str(metadata["evaluation_occurrence_id"]),
        )
        selection = _selection(
            published,
            metadata,
            code="A",
            selection_id="selection-missing-provenance",
        )
        store.publish_tradeoff_selection(workspace_id, selection=selection)

        accepted = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection, attempt_id="attempt-missing-provenance"),
        )

        assert accepted.selection_result["selection_result"] == (
            "TRADEOFF_SELECTION_INVALID_CANDIDATE"
        )
        assert accepted.action_recommendation is None
        assert accepted.selection_claim is None
    finally:
        client.__exit__(None, None, None)


def test_explicit_option_provenance_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        evaluation, metadata = _tradeoff_evaluation()
        identity = _identity_binding()
        identity["driver_action_link_ref_and_hash"] = {
            "reference": "link-not-authoritative",
            "content_hash": "sha256:" + "e" * 64,
        }
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-tradeoff-mismatched-provenance",
            evaluation=evaluation,
            identity_binding=identity,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
            evaluation_occurrence_id=str(metadata["evaluation_occurrence_id"]),
        )
        selection = _selection(
            published,
            metadata,
            code="A",
            selection_id="selection-mismatched-provenance",
        )
        store.publish_tradeoff_selection(workspace_id, selection=selection)

        accepted = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection, attempt_id="attempt-mismatched-provenance"),
        )

        assert accepted.selection_result["selection_result"] == (
            "TRADEOFF_SELECTION_INVALID_CANDIDATE"
        )
        assert accepted.action_recommendation is None
        assert accepted.selection_claim is None
    finally:
        client.__exit__(None, None, None)


def test_selection_replay_is_idempotent_and_conflicting_reuse_fails_closed(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection_a = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection_a)
        first = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection_a, attempt_id="attempt-a"),
        )
        replay = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection_a, attempt_id="attempt-a"),
        )
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.action_recommendation == first.action_recommendation

        selection_b = _selection(published, metadata, code="B", selection_id="selection-b")
        store.publish_tradeoff_selection(workspace_id, selection=selection_b)
        conflict = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection_b, attempt_id="attempt-b"),
        )
        assert conflict.selection_result["selection_result"] == (
            "TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED"
        )
        assert conflict.action_recommendation is None
    finally:
        client.__exit__(None, None, None)


def test_later_delivery_is_idempotent_and_same_key_conflict_fails_closed(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        first = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(selection, attempt_id="attempt-a"),
        )
        later = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(
                selection,
                attempt_id="attempt-a-later",
                delivered_at="2026-08-09T10:02:00+00:00",
            ),
        )
        assert later.selection_result["selection_result"] == (
            "TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT"
        )
        assert later.action_recommendation == first.action_recommendation

        conflicting = _attempt(selection, attempt_id="attempt-a")
        conflicting_candidate = deepcopy(conflicting["selected_candidate"])
        conflicting_candidate["label"] = "Changed candidate content"
        conflicting_candidate.pop("content_hash", None)
        conflicting_candidate["content_hash"] = sha256(conflicting_candidate)
        conflicting["selected_candidate"] = conflicting_candidate
        conflicting.pop("content_hash", None)
        conflicting["content_hash"] = sha256(conflicting)
        with pytest.raises(DecisionSupportCurrentnessConflict):
            store.accept_tradeoff_selection(
                workspace_id,
                delivery_attempt=conflicting,
            )
    finally:
        client.__exit__(None, None, None)


def test_wrong_type_governance_reference_is_retained_and_replayed(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        attempt = _attempt(selection, attempt_id="attempt-wrong-type")
        attempt["tradeoff_selection_ref_and_hash"] = {
            "reference": f"governance-tradeoff-selection:{selection['selection_occurrence_id']}",
            "content_hash": selection["content_hash"],
        }
        attempt.pop("content_hash", None)
        attempt["content_hash"] = sha256(attempt)

        first = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=attempt,
        )
        assert first.validation_result["validation_code"] == (
            "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH"
        )
        replay = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=attempt,
        )
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.validation_result == first.validation_result
    finally:
        client.__exit__(None, None, None)


def test_selection_argument_must_match_delivery_attempt_before_publication(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection_a = _selection(published, metadata, code="A", selection_id="selection-a")
        selection_b = _selection(published, metadata, code="B", selection_id="selection-b")
        store.publish_tradeoff_selection(workspace_id, selection=selection_a)
        attempt = _attempt(selection_a, attempt_id="attempt-selection-mismatch")
        result = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=attempt,
            selection=selection_b,
        )
        assert result.validation_result["validation_code"] == (
            "TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH"
        )
        assert store.get_tradeoff_selection(
            workspace_id, "selection-b"
        ) is None
    finally:
        client.__exit__(None, None, None)


def test_tradeoff_selection_http_seam_returns_typed_acceptance(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-http")
        published_response = client.post(
            "/api/decision-support/tradeoff-selections",
            json={"selection": selection},
        )
        assert published_response.status_code == 201, published_response.text
        stored_selection = published_response.json()["selection"]
        attempt = _attempt(selection, attempt_id="attempt-http")
        series_id = str(published.evaluation["evaluation_series_id"])  # type: ignore[attr-defined]
        accepted_response = client.post(
            f"/api/decision-support/evaluation-series/{series_id}/tradeoff-selection/accept",
            json={"delivery_attempt": attempt, "selection": stored_selection},
        )
        assert accepted_response.status_code == 201, accepted_response.text
        assert accepted_response.json()["selection_result"]["selection_result"] == (
            "TRADEOFF_SELECTION_ACCEPTED"
        )
    finally:
        client.__exit__(None, None, None)


def test_stale_selection_does_not_publish_a_recommendation(tmp_path: Path) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        successor_evaluation, _ = _tradeoff_evaluation()
        successor_evaluation["decision_support_input_digest"] = "sha256:" + "b" * 64
        successor = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-tradeoff-successor",
            evaluation=successor_evaluation,
            identity_binding=_identity_binding(),
            expected_head_occurrence_id=published.head["head_occurrence_id"],  # type: ignore[attr-defined]
            expected_head_digest=published.head["head_digest"],  # type: ignore[attr-defined]
            expected_head_result_hash=published.head["head_result_hash"],  # type: ignore[attr-defined]
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
            evaluation_occurrence_id="evaluation-tradeoff-successor",
        )

        stale = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=_attempt(
                selection,
                attempt_id="attempt-stale",
                delivered_at="2026-08-09T10:04:00+00:00",
            ),
        )

        assert stale.selection_result["selection_result"] == "TRADEOFF_SELECTION_STALE"
        assert stale.action_recommendation is None
        assert stale.currentness["currentness_outcome"] == "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
        assert stale.head["head_occurrence_id"] == successor.head["head_occurrence_id"]
    finally:
        client.__exit__(None, None, None)


def test_selection_race_loss_publishes_only_stale_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-race")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        attempt = _attempt(selection, attempt_id="attempt-race")
        original_head_read = store._currentness_head_locked
        reads = 0

        def racing_head_read(connection, current_workspace_id, series_id):
            nonlocal reads
            reads += 1
            observed = original_head_read(connection, current_workspace_id, series_id)
            if reads == 2:
                assert observed is not None
                successor_evaluation, _ = _tradeoff_evaluation()
                successor_evaluation["decision_support_input_digest"] = (
                    "sha256:" + "b" * 64
                )
                store._publish_decision_support_evaluation_locked(
                    connection,
                    workspace_id,
                    idempotency_key="evaluation-tradeoff-race-successor",
                    evaluation=successor_evaluation,
                    identity_binding=_identity_binding(),
                    expected_head_occurrence_id=published.head["head_occurrence_id"],  # type: ignore[attr-defined]
                    expected_head_digest=published.head["head_digest"],  # type: ignore[attr-defined]
                    expected_head_result_hash=published.head["head_result_hash"],  # type: ignore[attr-defined]
                    now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
                    evaluation_occurrence_id="evaluation-tradeoff-race-successor",
                )
                return original_head_read(connection, current_workspace_id, series_id)
            return observed

        monkeypatch.setattr(store, "_currentness_head_locked", racing_head_read)
        raced = store.accept_tradeoff_selection(
            workspace_id,
            delivery_attempt=attempt,
        )
        assert raced.selection_result["selection_result"] == "TRADEOFF_SELECTION_STALE"
        assert raced.action_recommendation is None
        assert raced.currentness["currentness_outcome"] == (
            "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
        )
        assert raced.head["head_occurrence_id"] == "evaluation-tradeoff-race-successor"
    finally:
        client.__exit__(None, None, None)


def test_selection_validation_fails_before_currentness_for_malformed_candidate(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published, metadata = _publish(store, workspace_id)
        selection = _selection(published, metadata, code="A", selection_id="selection-a")
        store.publish_tradeoff_selection(workspace_id, selection=selection)
        attempt = _attempt(selection, attempt_id="attempt-invalid")
        attempt["selected_candidate_ref"] = (
            "candidate:evaluation-tradeoff-1:not-in-pair:1"
        )
        attempt["content_hash"] = sha256(attempt)

        with pytest.raises(DecisionSupportCurrentnessUnavailable):
            store.accept_tradeoff_selection(workspace_id, delivery_attempt=attempt)
    finally:
        client.__exit__(None, None, None)
