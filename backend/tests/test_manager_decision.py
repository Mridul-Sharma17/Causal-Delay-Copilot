from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.ingestion import LineageStore
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.tests.test_decision_support_currentness import (
    _evaluation,
    _identity_binding,
    _render_request,
)
from backend.tests.test_draft_context import (
    _create_persisted_draft,
    _current_advice,
    _draft_test_app,
)


def _store(tmp_path: Path) -> tuple[TestClient, str, LineageStore]:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    return client, workspace_id, client.app.state.audit_store


def _rich_evaluation(digest: str = "sha256:" + "a" * 64) -> dict[str, object]:
    evaluation = _evaluation()
    evaluation["decision_support_input_digest"] = digest
    evaluation["action_recommendation"] = deepcopy(
        _current_advice()["render"]["advice_chain"]["action_recommendation"]
    )
    return evaluation


def test_manager_decision_authorizes_exact_draft_chain_and_replays(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        evaluation = _rich_evaluation()
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="manager-decision-evaluation-1",
            evaluation=evaluation,
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        render_request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )
        created = client.post(
            "/api/decision-support/draft-context",
            json={
                "idempotency_key": "manager-decision-draft-1",
                "manager_actor_ref": "anonymous-demo-manager",
                "current_advice": render_request,
            },
        )
        assert created.status_code == 200
        draft = created.json()["draft"]
        edited_body = draft["body"] + "\n\nPlease review this governed request."
        edited = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/edits",
            json={
                "idempotency_key": "manager-decision-edit-1",
                "expected_head_ref_and_hash": {
                    "reference": draft["occurrence_id"],
                    "content_hash": draft["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "subject": draft["subject"],
                "body": edited_body,
            },
        )
        assert edited.status_code == 201
        edited_head = edited.json()["draft"]
        intent = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/dispositions",
            json={
                "idempotency_key": "manager-decision-intent-1",
                "expected_head_ref_and_hash": {
                    "reference": edited_head["occurrence_id"],
                    "content_hash": edited_head["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "APPROVE",
            },
        )
        assert intent.status_code == 201
        intent_head = intent.json()["draft"]

        request = {
            "idempotency_key": "manager-decision-1",
            "expected_head_ref_and_hash": {
                "reference": intent_head["occurrence_id"],
                "content_hash": intent_head["content_hash"],
            },
            "manager_actor_ref": "anonymous-demo-manager",
            "disposition": "APPROVE",
        }
        first = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions",
            json=request,
        )
        replay = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions",
            json=request,
        )
        listed = client.get(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions"
        )

        assert first.status_code == 201
        assert replay.status_code == 200
        assert listed.status_code == 200
        body = first.json()
        replay_body = replay.json()
        assert replay_body == {**body, "result": "IDEMPOTENT_REPLAY"}
        conflict = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions",
            json={**request, "disposition": "REJECT"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "MANAGER_DECISION_IDEMPOTENCY_CONFLICT"
        decision = body["decision"]
        assert decision["disposition"] == "APPROVE"
        assert decision["authorization_state"] == "AUTHORIZED"
        assert decision["execution_state"] == "NOT_EXECUTED"
        assert decision["no_send"] is True
        assert decision["draft_version_ref_and_hash"] == {
            "reference": intent_head["occurrence_id"],
            "content_hash": intent_head["content_hash"],
        }
        assert decision["recommendation_ref_and_hash"] == intent_head[
            "recommendation_ref_and_hash"
        ]
        assert decision["evidence_ref_and_hash"] == intent_head["evidence_ref_and_hash"]
        assert decision["draft_history_ref_and_hashes"] == [
            {"reference": draft["occurrence_id"], "content_hash": draft["content_hash"]},
            {
                "reference": edited_head["occurrence_id"],
                "content_hash": edited_head["content_hash"],
            },
            {
                "reference": intent_head["occurrence_id"],
                "content_hash": intent_head["content_hash"],
            },
        ]
        assert body["authorization_attempt"]["requested_disposition"] == "APPROVE"
        assert body["authorization_currentness"]["authorization_currentness"] == "PROVEN"
        assert body["currentness"]["currentness_outcome"] == "CURRENTNESS_PROVEN_AT_CHECK"
        assert body["snapshot"]["no_send"] is True
        assert body["snapshot"]["draft_version_ref_and_hash"] == decision[
            "draft_version_ref_and_hash"
        ]
        assert body["snapshot"]["recommendation_ref_and_hash"] == decision[
            "recommendation_ref_and_hash"
        ]
        assert body["snapshot"]["evidence_ref_and_hash"] == decision[
            "evidence_ref_and_hash"
        ]
        assert body["snapshot"]["draft_version"]["body"] == intent_head["body"]
        assert body["snapshot"]["draft_context"]["content_hash"] == draft[
            "draft_context_ref_and_hash"
        ]["content_hash"]
        assert body["snapshot"]["drafted_artifact"]["content_hash"] == draft[
            "source_artifact_ref_and_hash"
        ]["content_hash"]
        assert body["snapshot"]["action_recommendation"]["content_hash"] == decision[
            "recommendation_ref_and_hash"
        ]["content_hash"]
        assert body["snapshot"]["evidence"]["content_hash"] == decision[
            "evidence_ref_and_hash"
        ]["content_hash"]
        assert listed.json()["items"][0]["decision"] == decision
        assert {
            item["occurrence_kind"]
            for item in client.get("/api/audit/occurrences").json()["items"]
        } >= {
            "GOVERNANCE_MANAGER_DECISION",
            "MANAGER_DECISION_BRIEF_SNAPSHOT",
            "DECISION_SUPPORT_CURRENTNESS_SOURCE_OCCURRENCE",
        }
        connection = store._connection_or_raise()
        for table in (
            "governance_manager_decisions",
            "governance_manager_decision_snapshots",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"UPDATE {table} SET content_hash = content_hash")
            connection.rollback()
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"DELETE FROM {table}")
            connection.rollback()
    finally:
        client.__exit__(None, None, None)


def test_reject_and_investigate_persist_without_authorization_or_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _draft_test_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        client.get("/api/workspace")
        created = _create_persisted_draft(client)
        draft = created["draft"]
        rejected = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/dispositions",
            json={
                "idempotency_key": "manager-reject-intent-1",
                "expected_head_ref_and_hash": {
                    "reference": draft["occurrence_id"],
                    "content_hash": draft["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "REJECT",
                "rejection_reason": {
                    "code": "DRAFT_CONTENT_INACCURATE",
                    "detail": "The manager needs a different governed explanation.",
                },
            },
        )
        assert rejected.status_code == 201
        rejected_head = rejected.json()["draft"]
        rejected_decision = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions",
            json={
                "idempotency_key": "manager-reject-decision-1",
                "expected_head_ref_and_hash": {
                    "reference": rejected_head["occurrence_id"],
                    "content_hash": rejected_head["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "REJECT",
            },
        )

        second = client.post(
            "/api/decision-support/draft-context",
            json={
                "idempotency_key": "manager-investigate-draft-1",
                "manager_actor_ref": "anonymous-demo-manager",
                "current_advice": _current_advice_render_request_for_test(),
            },
        )
        assert second.status_code == 200
        second_draft = second.json()["draft"]
        investigated = client.post(
            f"/api/decision-support/drafts/{second_draft['draft_id']}/dispositions",
            json={
                "idempotency_key": "manager-investigate-intent-1",
                "expected_head_ref_and_hash": {
                    "reference": second_draft["occurrence_id"],
                    "content_hash": second_draft["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "INVESTIGATE_FURTHER",
            },
        )
        assert investigated.status_code == 201
        investigated_head = investigated.json()["draft"]
        investigated_decision = client.post(
            f"/api/decision-support/drafts/{second_draft['draft_id']}/decisions",
            json={
                "idempotency_key": "manager-investigate-decision-1",
                "expected_head_ref_and_hash": {
                    "reference": investigated_head["occurrence_id"],
                    "content_hash": investigated_head["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "INVESTIGATE_FURTHER",
            },
        )

    for response in (rejected_decision, investigated_decision):
        assert response.status_code == 201
        body = response.json()
        assert body["decision"]["authorization_state"] == "NOT_AUTHORIZED"
        assert body["decision"]["execution_state"] == "NOT_EXECUTED"
        assert body["decision"]["no_send"] is True
        assert body["authorization_attempt"] is None
        assert body["authorization_currentness"] is None
        assert body["currentness"] is None
        assert body["snapshot"]["no_send"] is True


def test_approval_refuses_a_racing_successor_without_publishing_a_decision(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        published = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="manager-race-evaluation-1",
            evaluation=_rich_evaluation(),
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        render_request = _render_request(
            published,
            available_at="2026-08-09T10:02:00+00:00",
        )
        created = client.post(
            "/api/decision-support/draft-context",
            json={
                "idempotency_key": "manager-race-draft-1",
                "manager_actor_ref": "anonymous-demo-manager",
                "current_advice": render_request,
            },
        )
        draft = created.json()["draft"]
        intent = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/dispositions",
            json={
                "idempotency_key": "manager-race-intent-1",
                "expected_head_ref_and_hash": {
                    "reference": draft["occurrence_id"],
                    "content_hash": draft["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "APPROVE",
            },
        )
        intent_head = intent.json()["draft"]
        successor = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="manager-race-evaluation-2",
            evaluation=_rich_evaluation("sha256:" + "c" * 64),
            identity_binding=_identity_binding(),
            expected_head_occurrence_id=published.head["head_occurrence_id"],
            expected_head_digest=published.head["head_digest"],
            expected_head_result_hash=published.head["head_result_hash"],
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
        )
        response = client.post(
            f"/api/decision-support/drafts/{draft['draft_id']}/decisions",
            json={
                "idempotency_key": "manager-race-decision-1",
                "expected_head_ref_and_hash": {
                    "reference": intent_head["occurrence_id"],
                    "content_hash": intent_head["content_hash"],
                },
                "manager_actor_ref": "anonymous-demo-manager",
                "disposition": "APPROVE",
            },
        )

        assert response.status_code == 409
        body = response.json()
        assert body["result"] == "CURRENTNESS_REFUSED"
        assert body["decision"] is None
        assert body["currentness"]["currentness_outcome"] == (
            "CURRENTNESS_NOT_AUTHORITATIVE_HEAD"
        )
        assert body["currentness"]["observed_authoritative_head_ref_and_hash"][
            "reference"
        ] == successor.head["head_occurrence_id"]
        assert not any(
            item["occurrence_kind"]
            in {"GOVERNANCE_MANAGER_DECISION", "MANAGER_DECISION_BRIEF_SNAPSHOT"}
            for item in client.get("/api/audit/occurrences").json()["items"]
        )
    finally:
        client.__exit__(None, None, None)


def _current_advice_render_request_for_test() -> dict[str, object]:
    current_advice = _current_advice()
    render = current_advice["render"]
    assert isinstance(render, dict)
    recommendation = render["recommendation_ref_and_hash_or_null"]
    assert isinstance(recommendation, dict)
    return {
        "schema_identifier": "current-advice-render-request",
        "schema_version": "1",
        "render_mode": "CURRENT_ADVICE",
        "evaluation_series_id": "series-1",
        "evaluation_occurrence_id": "evaluation-1",
        "evaluation_digest": "sha256:" + "1" * 64,
        "terminal_result_ref_and_hash": render["evaluation_result_ref_and_hash"],
        "advice_chain_kind": "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "recommendation_ref_and_hash_or_null": recommendation,
        "accepted_selection_claim_ref_and_hash_or_null": None,
        "advice_chain_published_at": "2026-08-09T10:02:00+00:00",
        "requested_at": "2026-08-09T10:03:00+00:00",
        "available_at": "2026-08-09T10:03:00+00:00",
    }
