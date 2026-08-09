from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.decision_support_currentness import (
    DecisionSupportCurrentnessOperationMismatch,
    DecisionSupportCurrentnessUnavailable,
    _key_fields,
    _operation_record_for,
    _record_content_hash,
    currentness_operation_key_for,
)
from backend.app.decision_support_heads import DecisionSupportHeadRaceLost
from backend.app.ingestion import LineageStore
from backend.app.main import create_app
from backend.app.settings import Settings


def _identity_binding(
    *,
    valid_through: str = "NO_EXPIRY",
    dependency_status: str = "APPROVED",
) -> dict[str, object]:
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
            "disposition": dependency_status,
            "effective": True,
            "unique_unsuperseded_head": True,
            "superseded_by": None,
        },
    }
    return {
        "evaluation_series_id": "series-1",
        "investigation_request": {
            "record_id": "investigation-1",
            "content_hash": "sha256:" + "1" * 64,
        },
        "subject_identity": "order-line-1",
        "causal_decision_at": "2026-08-09T10:00:00+00:00",
        "trigger_mode": "reactive",
        "subject_driver_state": {
            "kind": "high_load_exposure",
            "value": True,
            "content_hash": "sha256:" + "4" * 64,
        },
        "governed_records": {
            "advice_currentness_dependency_set": [dependency],
        },
        "operational_snapshot": {
            "facts": [
                {
                    "input_path": "case_constraint_snapshot.facts[0]",
                    "reference": "fact-1",
                    "content_hash": "sha256:" + "7" * 64,
                    "valid_through": valid_through,
                }
            ]
        },
        "available_at": "2026-08-09T10:00:00+00:00",
    }


def _evaluation(
    *,
    digest: str = "sha256:" + "a" * 64,
    valid_through: str = "NO_EXPIRY",
) -> dict[str, object]:
    identity = _identity_binding(valid_through=valid_through)
    return {
        "schema_version": "decision-support-boundary.v1",
        "outcome": "RECOMMENDATION_AVAILABLE",
        "state": "recommendation_available",
        "permission": {
            "decision_support_evaluation_permitted": True,
            "denial_reason_code": None,
            "reason": "supported",
            "next_step": "render current advice",
        },
        "decision_support_evaluation_id": "calculated-evaluation-id",
        "decision_support_evaluation_series_id": "series-1",
        "decision_support_input_digest": digest,
        "options": [{"option_code": "PROTECTED_PRODUCTION_SLOT"}],
        "action_recommendation": {
            "occurrence_id": "recommendation-1",
            "content_hash": "sha256:" + "b" * 64,
            "selected_option_code": "PROTECTED_PRODUCTION_SLOT",
            "selection_basis": "UNIVERSAL_PARETO_DOMINANCE",
        },
        "tradeoff": None,
        "advice_currentness_dependency_set": deepcopy(
            identity["governed_records"]["advice_currentness_dependency_set"]  # type: ignore[index]
        ),
        "consumed_operational_horizons": [
            {
                "input_path": "operational_snapshot.facts[0]",
                "reference": "fact-1",
                "content_hash": "sha256:" + "7" * 64,
                "valid_through": valid_through,
            }
        ],
        "advice_valid_through": valid_through,
    }


def _store(tmp_path: Path) -> tuple[TestClient, str, LineageStore]:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    return client, workspace_id, client.app.state.audit_store


def _publish(store: LineageStore, workspace_id: str, *, now: datetime):
    return store.publish_decision_support_evaluation(
        workspace_id,
        idempotency_key=f"evaluation-{now.isoformat()}",
        evaluation=_evaluation(),
        identity_binding=_identity_binding(),
        now=now,
    )


def _render_request(
    published: object,
    *,
    available_at: str,
    requested_at: str | None = None,
) -> dict[str, object]:
    evaluation = published.evaluation  # type: ignore[attr-defined]
    result = published.result_projection  # type: ignore[attr-defined]
    published_at = str(evaluation["evaluation_published_at"])
    request: dict[str, object] = {
        "schema_identifier": "current-advice-render-request",
        "schema_version": "1",
        "render_mode": "CURRENT_ADVICE",
        "evaluation_series_id": "series-1",
        "evaluation_occurrence_id": evaluation["evaluation_occurrence_id"],
        "evaluation_digest": evaluation["evaluation_digest"],
        "terminal_result_ref_and_hash": evaluation["terminal_result_ref_and_hash"],
        "advice_chain_kind": "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "recommendation_ref_and_hash_or_null": {
            "reference": result["action_recommendation"]["occurrence_id"],
            "content_hash": result["action_recommendation"]["content_hash"],
        },
        "accepted_selection_claim_ref_and_hash_or_null": None,
        "advice_chain_published_at": published_at,
        "requested_at": requested_at or published_at,
        "available_at": available_at,
    }
    return request


def test_current_render_proves_exact_advice_and_replays_one_terminal_occurrence(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )

        first = store.render_current_advice(
            workspace_id,
            render_request=request,
        )
        replay = store.render_current_advice(
            workspace_id,
            render_request=request,
        )

        assert first.result == "CREATED"
        assert first.currentness["currentness_outcome"] == "CURRENTNESS_PROVEN_AT_CHECK"
        assert first.render["current_as_of"] == "2026-08-09T10:02:00+00:00"
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.operation["operation_occurrence_id"] == first.operation[
            "operation_occurrence_id"
        ]
        assert replay.currentness["currentness_check_occurrence_id"] == first.currentness[
            "currentness_check_occurrence_id"
        ]
        assert replay.render["render_result_occurrence_id"] == first.render[
            "render_result_occurrence_id"
        ]
        assert replay.head == first.head
        assert currentness_operation_key_for(first.operation) == first.operation[
            "currentness_operation_key"
        ]

        audit = client.get("/api/audit/occurrences")
        assert audit.status_code == 200
        assert {
            item["occurrence_kind"] for item in audit.json()["items"]
        } >= {
            "DECISION_SUPPORT_CURRENTNESS_OPERATION",
            "DECISION_SUPPORT_CURRENTNESS_CHECK",
            "DECISION_SUPPORT_CURRENT_ADVICE_RENDER",
        }
    finally:
        client.__exit__(None, None, None)


def test_currentness_rejects_successor_and_does_not_invalidate_new_head(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        first = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        second = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-successor",
            evaluation=_evaluation(digest="sha256:" + "c" * 64),
            identity_binding=_identity_binding(),
            expected_head_occurrence_id=first.head["head_occurrence_id"],
            expected_head_digest=first.head["head_digest"],
            expected_head_result_hash=first.head["head_result_hash"],
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
        )
        result = store.render_current_advice(
            workspace_id,
            render_request=_render_request(
                first,
                available_at="2026-08-09T10:04:00+00:00",
            ),
        )

        assert result.currentness["currentness_outcome"] == (
            "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
        )
        assert result.currentness["observed_authoritative_head_ref_and_hash"][
            "reference"
        ] == second.head["head_occurrence_id"]
        head = store.get_decision_support_evaluation_head(workspace_id, "series-1")
        assert head is not None
        assert head["head_occurrence_id"] == second.head["head_occurrence_id"]
        assert head["head_kind"] == "EVALUATION"
    finally:
        client.__exit__(None, None, None)


def test_current_render_api_exposes_currentness_and_audit_bound_state(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )
        response = client.post(
            "/api/decision-support/evaluation-series/series-1/current-advice/render",
            json=request,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["result"] == "CREATED"
        assert body["currentness"]["currentness_outcome"] == (
            "CURRENTNESS_PROVEN_AT_CHECK"
        )
        assert body["render"]["current_as_of"] == "2026-08-09T10:02:00+00:00"
        assert client.get("/api/decision-support/currentness").status_code == 200
        replay = client.post(
            "/api/decision-support/current-advice/render",
            json=request,
        )
        assert replay.status_code == 200
        assert replay.json()["result"] == "IDEMPOTENT_REPLAY"
    finally:
        client.__exit__(None, None, None)


def test_expiry_and_dependency_downgrade_install_one_currentness_invalidation(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-expiry",
            evaluation=_evaluation(valid_through="2026-08-09T10:02:00+00:00"),
            identity_binding=_identity_binding(
                valid_through="2026-08-09T10:02:00+00:00"
            ),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:03:00+00:00",
        )
        result = store.render_current_advice(
            workspace_id,
            render_request=request,
        )

        assert result.render is None
        assert result.currentness["currentness_outcome"] == (
            "ADVICE_CURRENTNESS_INVALIDATION"
        )
        assert result.currentness["ordered_currentness_reasons"] == [
            "OPERATIONAL_FACT_EXPIRED"
        ]
        assert result.head["head_kind"] == "ADVICE_CURRENTNESS_INVALIDATION"
        replay = store.render_current_advice(
            workspace_id,
            render_request=request,
        )
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.head["head_kind"] == "ADVICE_CURRENTNESS_INVALIDATION"
        series = store.get_decision_support_evaluation_series(workspace_id, "series-1")
        assert series is not None
        assert series["head"]["advice_state"] == "invalidated"
        assert any(
            item["record_type"] == "invalidation"
            and item["record_state"] == "current"
            for item in series["history"]
        )
    finally:
        client.__exit__(None, None, None)


def test_governed_dependency_downgrade_is_primary_currentness_reason(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )
        dependency = deepcopy(
            _identity_binding()["governed_records"][
                "advice_currentness_dependency_set"
            ][0]  # type: ignore[index]
        )
        dependency["current"]["disposition"] = "REJECTED"  # type: ignore[index]
        store.publish_decision_support_currentness_authority(
            workspace_id,
            evaluation_series_id="series-1",
            dependencies=[dependency],
            now=datetime(2026, 8, 9, 10, 2, tzinfo=timezone.utc),
        )
        result = store.render_current_advice(
            workspace_id,
            render_request=request,
        )
        assert result.currentness["currentness_outcome"] == (
            "ADVICE_CURRENTNESS_INVALIDATION"
        )
        assert result.currentness["ordered_currentness_reasons"] == [
            "GOVERNED_DEPENDENCY_NOT_CURRENT"
        ]
        assert result.head["head_kind"] == "ADVICE_CURRENTNESS_INVALIDATION"
    finally:
        client.__exit__(None, None, None)


def test_currentness_operation_mismatch_does_not_poison_exact_render_operation(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )
        first = store.render_current_advice(workspace_id, render_request=request)
        with pytest.raises(DecisionSupportCurrentnessOperationMismatch):
            store.check_decision_support_currentness(
                workspace_id,
                operation={
                    **first.operation,
                    "invocation_operation_kind": "MANAGER_AUTHORIZATION",
                },
            )
        replay = store.render_current_advice(workspace_id, render_request=request)
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.render["render_result_occurrence_id"] == first.render[
            "render_result_occurrence_id"
        ]
    finally:
        client.__exit__(None, None, None)


def test_invalid_currentness_envelope_creates_no_operation_or_check(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        with pytest.raises(DecisionSupportCurrentnessUnavailable):
            store.check_decision_support_currentness(
                workspace_id,
                operation={"operation_kind": "CURRENT_ADVICE_RENDER"},
            )
        assert store.list_decision_support_currentness(workspace_id) == []
    finally:
        client.__exit__(None, None, None)


def test_backdated_render_request_is_rejected_before_any_currentness_record(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
            requested_at="2026-08-09T09:59:00+00:00",
        )
        with pytest.raises(DecisionSupportCurrentnessUnavailable):
            store.render_current_advice(workspace_id, render_request=request)

        assert store.list_decision_support_currentness(workspace_id) == []
        head = store.get_decision_support_evaluation_head(workspace_id, "series-1")
        assert head is not None
        assert head["head_kind"] == "EVALUATION"
        assert not any(
            item["occurrence_kind"]
            in {
                "DECISION_SUPPORT_CURRENTNESS_OPERATION",
                "DECISION_SUPPORT_CURRENTNESS_CHECK",
                "DECISION_SUPPORT_CURRENT_ADVICE_RENDER_REQUEST",
                "DECISION_SUPPORT_CURRENT_ADVICE_RENDER",
                "DECISION_SUPPORT_CURRENTNESS_INVALIDATION",
                "DECISION_SUPPORT_CURRENTNESS_CONSUMING_RESULT",
            }
            for item in client.get("/api/audit/occurrences").json()["items"]
        )
    finally:
        client.__exit__(None, None, None)


def test_missing_live_dependency_resolution_fails_closed(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        result = store.render_current_advice(
            workspace_id,
            render_request=_render_request(
                published,
                available_at="2026-08-09T10:02:00+00:00",
            ),
            currentness_context={},
        )
        assert result.currentness["currentness_outcome"] == (
            "ADVICE_CURRENTNESS_INVALIDATION"
        )
        assert result.currentness["ordered_currentness_reasons"] == [
            "GOVERNED_DEPENDENCY_NOT_CURRENT"
        ]
    finally:
        client.__exit__(None, None, None)


def test_operation_content_hash_mismatch_is_rejected_without_poisoning_replay(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = _publish(
            store,
            workspace_id,
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        first = store.render_current_advice(
            workspace_id,
            render_request=_render_request(
                published,
                available_at="2026-08-09T10:02:00+00:00",
            ),
        )
        with pytest.raises(DecisionSupportCurrentnessUnavailable):
            store.check_decision_support_currentness(
                workspace_id,
                operation={
                    **first.operation,
                    "content_hash": "sha256:" + "f" * 64,
                },
            )
        replay = store.render_current_advice(
            workspace_id,
            render_request=_render_request(
                published,
                available_at="2026-08-09T10:02:00+00:00",
            ),
        )
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.operation["operation_occurrence_id"] == first.operation[
            "operation_occurrence_id"
        ]
    finally:
        client.__exit__(None, None, None)


def _strict_consuming_operation(
    published: object,
    *,
    operation_kind: str,
    payload: dict[str, object],
    recommendation_ref: dict[str, str] | None,
) -> dict[str, object]:
    evaluation = published.evaluation  # type: ignore[attr-defined]
    payload_hash = _record_content_hash(payload)
    assert payload_hash is not None
    operation: dict[str, object] = {
        "schema_identifier": "advice-currentness-operation",
        "schema_version": "1",
        "currentness_policy_identifier_and_version": {
            "identifier": "decision-support-advice-currentness",
            "version": "1",
        },
        "operation_kind": operation_kind,
        "evaluation_series_id": evaluation["evaluation_series_id"],
        "evaluation_occurrence_id": evaluation["evaluation_occurrence_id"],
        "evaluation_digest": evaluation["evaluation_digest"],
        "terminal_result_ref_and_hash": deepcopy(
            evaluation["terminal_result_ref_and_hash"]
        ),
        "recommendation_ref_and_hash_or_null": deepcopy(recommendation_ref),
        "accepted_selection_claim_ref_and_hash_or_null": None,
        "operation_payload_ref_and_hash": {
            "reference": f"{payload['schema_identifier']}:{payload['occurrence_id']}",
            "content_hash": payload_hash,
        },
        "currentness_checked_at": payload["available_at"],
        "operation_payload": deepcopy(payload),
    }
    fields = _key_fields(operation)
    operation_key = currentness_operation_key_for(fields)
    record = _operation_record_for(fields, payload, operation_key)
    operation.update(
        {
            "currentness_operation_key": operation_key,
            "operation_occurrence_id": record["operation_occurrence_id"],
            "content_hash": record["content_hash"],
        }
    )
    return operation


@pytest.mark.parametrize(
    ("operation_kind", "result_variant"),
    [
        ("TRADEOFF_SELECTION_ACCEPTANCE", "tradeoff"),
        ("MANAGER_AUTHORIZATION", "recommendation"),
        ("MONITORING_TRIGGER_MATCH", "recommendation"),
    ],
)
def test_non_render_consumers_persist_one_typed_currentness_result_and_replay(
    tmp_path: Path,
    operation_kind: str,
    result_variant: str,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        evaluation = _evaluation()
        if result_variant == "tradeoff":
            evaluation.update(
                {
                    "outcome": "TRADEOFF_REQUIRES_MANAGER_CHOICE",
                    "state": "tradeoff_requires_manager_choice",
                    "action_recommendation": None,
                }
            )
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key=f"evaluation-{operation_kind}",
            evaluation=evaluation,
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        stored_evaluation = published.evaluation
        published_at = str(stored_evaluation["evaluation_published_at"])
        available_at = "2026-08-09T10:02:00+00:00"
        recommendation = published.result_projection.get("action_recommendation")
        recommendation_ref = (
            None
            if recommendation is None
            else {
                "reference": recommendation["occurrence_id"],
                "content_hash": recommendation["content_hash"],
            }
        )
        common = {
            "evaluation_series_id": stored_evaluation["evaluation_series_id"],
            "evaluation_occurrence_id": stored_evaluation["evaluation_occurrence_id"],
            "evaluation_digest": stored_evaluation["evaluation_digest"],
            "terminal_result_ref_and_hash": deepcopy(
                stored_evaluation["terminal_result_ref_and_hash"]
            ),
            "recommendation_ref_and_hash_or_null": deepcopy(recommendation_ref),
            "available_at": available_at,
        }
        if operation_kind == "TRADEOFF_SELECTION_ACCEPTANCE":
            payload = {
                **common,
                "schema_identifier": "tradeoff-selection-delivery-attempt",
                "schema_version": "1",
                "occurrence_id": "tradeoff-selection-attempt-1",
                "tradeoff_selection_ref_and_hash": {
                    "reference": "tradeoff-selection:1",
                    "content_hash": "sha256:" + "c" * 64,
                },
                "selected_candidate_ref": "candidate:PROTECTED_PRODUCTION_SLOT",
                "selection_available_at": published_at,
                "delivered_at": published_at,
            }
        elif operation_kind == "MANAGER_AUTHORIZATION":
            payload = {
                **common,
                "schema_identifier": "manager-authorization-attempt",
                "schema_version": "1",
                "occurrence_id": "manager-authorization-attempt-1",
                "recommendation_ref_and_hash": deepcopy(recommendation_ref),
                "requested_disposition": "APPROVE",
                "manager_actor_ref": "manager:1",
                "advice_chain_published_at": published_at,
                "requested_at": published_at,
            }
        else:
            payload = {
                **common,
                "schema_identifier": "monitoring-observation",
                "schema_version": "1",
                "occurrence_id": "monitoring-observation-1",
                "recommendation_ref_and_hash": deepcopy(recommendation_ref),
                "observation_ref": "source-observation:1",
                "trigger_id_and_version": {
                    "id": "trigger-1",
                    "version": "1",
                },
                "monitoring_activated_at": published_at,
                "observed_at": published_at,
                "match_outcome": "NO_REVIEW_REQUEST",
            }
        payload["content_hash"] = _record_content_hash(payload)
        assert isinstance(payload["content_hash"], str)
        operation = _strict_consuming_operation(
            published,
            operation_kind=operation_kind,
            payload=payload,
            recommendation_ref=recommendation_ref,
        )

        with pytest.raises(DecisionSupportCurrentnessUnavailable):
            store.check_decision_support_currentness(
                workspace_id,
                operation=operation,
            )
        assert store.list_decision_support_currentness(workspace_id) == []
        store.register_decision_support_currentness_source(
            workspace_id,
            payload=payload,
            now=datetime(2026, 8, 9, 10, 2, tzinfo=timezone.utc),
        )

        first = store.check_decision_support_currentness(
            workspace_id,
            operation=operation,
        )
        replay = store.check_decision_support_currentness(
            workspace_id,
            operation=operation,
        )

        expected_result_kind = {
            "TRADEOFF_SELECTION_ACCEPTANCE": "tradeoff-selection-result",
            "MANAGER_AUTHORIZATION": "authorization-currentness-result",
            "MONITORING_TRIGGER_MATCH": "monitoring-match-result",
        }[operation_kind]
        assert first.currentness["currentness_outcome"] == (
            "CURRENTNESS_PROVEN_AT_CHECK"
        )
        assert first.render is None
        assert first.consuming_result["schema_identifier"] == expected_result_kind
        assert first.terminal_claim["consuming_result_kind"] == expected_result_kind
        assert first.terminal_claim["consuming_result_ref_and_hash"]["reference"].endswith(
            first.consuming_result["consuming_result_occurrence_id"]
        )
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.consuming_result["consuming_result_occurrence_id"] == first.consuming_result[
            "consuming_result_occurrence_id"
        ]
        if operation_kind == "TRADEOFF_SELECTION_ACCEPTANCE":
            assert first.consuming_result["selection_side_effect"] == (
                "DEFERRED_TO_TRADEOFF_SELECTION_CONTRACT"
            )
        elif operation_kind == "MANAGER_AUTHORIZATION":
            assert first.consuming_result["manager_decision"] == "NOT_RECORDED_BY_CORE_31"
        else:
            assert first.consuming_result["monitoring_review_request_ref_and_hash"] is None

        currentness = store.list_decision_support_currentness(workspace_id)
        assert currentness[0]["consuming_result"]["schema_identifier"] == expected_result_kind
        series = store.get_decision_support_evaluation_series(
            workspace_id,
            stored_evaluation["evaluation_series_id"],
        )
        assert series is not None
        assert series["currentness"]["consuming_results"][0]["schema_identifier"] == (
            expected_result_kind
        )
        assert any(
            item["occurrence_kind"] == "DECISION_SUPPORT_CURRENTNESS_CONSUMING_RESULT"
            for item in client.get("/api/audit/occurrences").json()["items"]
        )
    finally:
        client.__exit__(None, None, None)
