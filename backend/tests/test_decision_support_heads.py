from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from backend.app.decision_support_heads import (
    DecisionSupportEvaluationConflict,
    DecisionSupportEvaluationUnavailable,
    DecisionSupportHeadRaceLost,
)
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.ingestion import LineageStore


def _identity_binding() -> dict[str, object]:
    return {
        "investigation_request": {
            "record_id": "investigation-1",
            "content_hash": "sha256:" + "1" * 64,
        },
        "subject_verdict": {
            "record_id": "subject-verdict-1",
            "content_hash": "sha256:" + "2" * 64,
        },
        "population_verdict": {
            "record_id": "population-verdict-1",
            "content_hash": "sha256:" + "3" * 64,
        },
        "subject_driver_state": {
            "kind": "high_load_exposure",
            "value": True,
            "content_hash": "sha256:" + "4" * 64,
        },
        "operational_snapshot": {
            "snapshot_id": "constraints-1",
            "content_hash": "sha256:" + "5" * 64,
        },
        "governed_records": {
            "intervention_library": {
                "identifier": "core-intervention-library",
                "version": "1",
                "content_hash": "sha256:" + "6" * 64,
            }
        },
        "assumptions": {"critical_path_delay_rate": "decimal:10"},
        "policy_versions": {
            "decision_support_policy": "decision-support-policy:1",
        },
        "available_at": "2026-08-09T10:00:00+00:00",
    }


def _evaluation(*, digest: str = "sha256:" + "a" * 64) -> dict[str, object]:
    return {
        "schema_version": "decision-support-boundary.v1",
        "outcome": "RECOMMENDATION_AVAILABLE",
        "state": "recommendation_available",
        "decision_support_evaluation_id": "calculated-evaluation-id",
        "decision_support_evaluation_series_id": "series-1",
        "decision_support_input_digest": digest,
        "options": [{"option_code": "PROTECTED_PRODUCTION_SLOT"}],
        "action_recommendation": {
            "occurrence_id": "recommendation-1",
            "content_hash": "sha256:" + "b" * 64,
        },
        "action_recommendation_ref_and_hash": {
            "reference": "recommendation-1",
            "content_hash": "sha256:" + "b" * 64,
        },
        "tradeoff": None,
    }


def _store(tmp_path: Path) -> tuple[TestClient, str, LineageStore]:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    return client, workspace_id, client.app.state.audit_store


def test_evaluation_series_publishes_immutable_successors_and_read_states(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        first = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-1",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        replay = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-1",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 2, tzinfo=timezone.utc),
        )
        with pytest.raises(DecisionSupportEvaluationUnavailable):
            store.publish_decision_support_evaluation(
                workspace_id,
                idempotency_key="evaluation-backdated",
                evaluation=_evaluation(),
                identity_binding=_identity_binding(),
                expected_head_occurrence_id=first.head["head_occurrence_id"],
                expected_head_digest=first.head["head_digest"],
                expected_head_result_hash=first.head["head_result_hash"],
                now=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
            )
        second = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-2",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
            expected_head_occurrence_id=first.head["head_occurrence_id"],
            expected_head_digest=first.head["head_digest"],
            expected_head_result_hash=first.head["head_result_hash"],
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
        )

        assert first.result == "CREATED"
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.evaluation["evaluation_occurrence_id"] == first.evaluation[
            "evaluation_occurrence_id"
        ]
        assert replay.evaluation["evaluation_published_at"] == first.evaluation[
            "evaluation_published_at"
        ]
        changed_identity = _identity_binding()
        changed_identity["assumptions"] = {"critical_path_delay_rate": "decimal:11"}
        with pytest.raises(DecisionSupportEvaluationConflict):
            store.publish_decision_support_evaluation(
                workspace_id,
                idempotency_key="evaluation-1",
                evaluation=_evaluation(),
                identity_binding=changed_identity,
            )
        assert second.evaluation["evaluation_occurrence_id"] != first.evaluation[
            "evaluation_occurrence_id"
        ]
        assert second.evaluation["predecessor_occurrence_id"] == first.head[
            "head_occurrence_id"
        ]
        assert second.head["head_kind"] == "EVALUATION"
        with pytest.raises(DecisionSupportHeadRaceLost):
            store.publish_decision_support_evaluation(
                workspace_id,
                idempotency_key="evaluation-3",
                evaluation=_evaluation(),
                identity_binding=_identity_binding(),
                expected_head_occurrence_id=second.head["head_occurrence_id"],
                expected_head_digest="sha256:" + "z" * 64,
                expected_head_result_hash=second.head["head_result_hash"],
            )

        series = store.get_decision_support_evaluation_series(
            workspace_id,
            "series-1",
        )
        assert series is not None
        assert series["head"]["head_occurrence_id"] == second.head["head_occurrence_id"]
        states = {
            item["evaluation_occurrence_id"]: item["record_state"]
            for item in series["history"]
            if item["record_type"] == "evaluation"
        }
        assert states[first.evaluation["evaluation_occurrence_id"]] == "superseded"
        assert states[second.evaluation["evaluation_occurrence_id"]] == "current"

        with sqlite3.connect(tmp_path / "core.sqlite3") as connection:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE decision_support_evaluations SET result_hash = ? WHERE evaluation_occurrence_id = ?",
                    ("tampered", first.evaluation["evaluation_occurrence_id"]),
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM decision_support_evaluations WHERE evaluation_occurrence_id = ?",
                    (first.evaluation["evaluation_occurrence_id"],),
                )
        with sqlite3.connect(tmp_path / "core.sqlite3") as connection:
            connection.execute(
                "UPDATE decision_support_evaluation_heads SET head_result_hash = ? WHERE evaluation_series_id = ?",
                ("tampered", "series-1"),
            )
            connection.commit()
        with pytest.raises(DecisionSupportEvaluationUnavailable):
            store.get_decision_support_evaluation_series(workspace_id, "series-1")
    finally:
        client.__exit__(None, None, None)


def test_invalidation_advances_head_without_rewriting_predecessor(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        first = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-1",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
            now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(DecisionSupportEvaluationUnavailable):
            store.invalidate_decision_support_evaluation(
                workspace_id,
                idempotency_key="invalidation-unregistered",
                evaluation_series_id="series-1",
                expected_head_occurrence_id=first.head["head_occurrence_id"],
                expected_head_digest=first.head["head_digest"],
                expected_head_result_hash=first.head["head_result_hash"],
                invalidation_kind="EVIDENCE_INTEGRITY_INVALIDATION",
                invalidated_artifact_ref_and_hash={
                    "reference": "bundle-1",
                    "content_hash": "sha256:" + "c" * 64,
                },
                authoritative_invalidation_ref_and_hash={
                    "reference": "quarantine-1",
                    "content_hash": "sha256:" + "d" * 64,
                },
                reason_code="UNREGISTERED_REASON",
            )
        invalidated = store.invalidate_decision_support_evaluation(
            workspace_id,
            idempotency_key="invalidation-1",
            evaluation_series_id="series-1",
            expected_head_occurrence_id=first.head["head_occurrence_id"],
            expected_head_digest=first.head["head_digest"],
            expected_head_result_hash=first.head["head_result_hash"],
            invalidation_kind="EVIDENCE_INTEGRITY_INVALIDATION",
            invalidated_artifact_ref_and_hash={
                "reference": "bundle-1",
                "content_hash": "sha256:" + "c" * 64,
            },
            authoritative_invalidation_ref_and_hash={
                "reference": "quarantine-1",
                "content_hash": "sha256:" + "d" * 64,
            },
            reason_code="ARTIFACT_QUARANTINED",
            now=datetime(2026, 8, 9, 10, 4, tzinfo=timezone.utc),
        )

        assert invalidated.head["head_kind"] == "EVIDENCE_INTEGRITY_INVALIDATION"
        assert invalidated.invalidation["outcome"] == "FAILED"
        assert invalidated.invalidation["primary_reason_code"] == (
            "DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED"
        )
        assert invalidated.invalidation["options"] == []
        assert invalidated.invalidation["action_recommendation"] is None
        series = store.get_decision_support_evaluation_series(workspace_id, "series-1")
        assert series is not None
        evaluation_state = next(
            item["record_state"]
            for item in series["history"]
            if item["record_type"] == "evaluation"
        )
        assert evaluation_state == "invalidated"
        assert series["head"]["advice_state"] == "invalidated"

        with pytest.raises(DecisionSupportHeadRaceLost):
            store.invalidate_decision_support_evaluation(
                workspace_id,
                idempotency_key="invalidation-2",
                evaluation_series_id="series-1",
                expected_head_occurrence_id=first.head["head_occurrence_id"],
                expected_head_digest=first.head["head_digest"],
                expected_head_result_hash=first.head["head_result_hash"],
                invalidation_kind="ADVICE_CURRENTNESS_INVALIDATION",
                invalidated_artifact_ref_and_hash={
                    "reference": "fact-1",
                    "content_hash": "sha256:" + "e" * 64,
                },
                authoritative_invalidation_ref_and_hash={
                    "reference": "expiry-1",
                    "content_hash": "sha256:" + "f" * 64,
                },
                reason_code="OPERATIONAL_FACT_EXPIRED",
            )
    finally:
        client.__exit__(None, None, None)


def test_concurrent_publications_with_one_expected_head_have_one_winner(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    contender = LineageStore(
        tmp_path / "core.sqlite3",
        release_candidate_id="local-default",
    )
    contender.initialize()
    try:
        first = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-1",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
        )
        expected = first.head["head_occurrence_id"]

        def publish(candidate: LineageStore, key: str):
            return candidate.publish_decision_support_evaluation(
                workspace_id,
                idempotency_key=key,
                evaluation=_evaluation(),
                identity_binding=_identity_binding(),
                expected_head_occurrence_id=expected,
                expected_head_digest=first.head["head_digest"],
                expected_head_result_hash=first.head["head_result_hash"],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(publish, store, "evaluation-2"),
                pool.submit(publish, contender, "evaluation-3"),
            ]

        successes = 0
        races = 0
        for future in futures:
            try:
                future.result()
                successes += 1
            except DecisionSupportHeadRaceLost:
                races += 1
        assert successes == 1
        assert races == 1
        series = store.get_decision_support_evaluation_series(workspace_id, "series-1")
        assert series is not None
        assert series["head"]["head_kind"] == "EVALUATION"
        assert len([item for item in series["history"] if item["record_type"] == "evaluation"]) == 2
    finally:
        contender.close()
        client.__exit__(None, None, None)


def test_typed_series_read_model_and_invalidation_api(
    tmp_path: Path,
) -> None:
    client, workspace_id, store = _store(tmp_path)
    try:
        first = store.publish_decision_support_evaluation(
            workspace_id,
            idempotency_key="evaluation-api-1",
            evaluation=_evaluation(),
            identity_binding=_identity_binding(),
        )
        series_response = client.get(
            "/api/decision-support/evaluation-series/series-1"
        )
        assert series_response.status_code == 200
        series_body = series_response.json()
        assert series_body["schema_version"] == (
            "decision-support-evaluation-read-model.v1"
        )
        assert series_body["head"]["head_kind"] == "EVALUATION"
        assert series_body["history"][0]["record_state"] == "current"

        invalidation_body = {
            "idempotency_key": "invalidation-api-1",
            "expected_head_occurrence_id": first.head["head_occurrence_id"],
            "expected_head_digest": first.head["head_digest"],
            "expected_head_result_hash": first.head["head_result_hash"],
            "invalidation_kind": "ADVICE_CURRENTNESS_INVALIDATION",
            "invalidated_artifact_ref_and_hash": {
                "reference": "operational-fact-1",
                "content_hash": "sha256:" + "c" * 64,
            },
            "authoritative_invalidation_ref_and_hash": {
                "reference": "expiry-1",
                "content_hash": "sha256:" + "d" * 64,
            },
            "reason_code": "OPERATIONAL_FACT_EXPIRED",
        }
        invalidation_response = client.post(
            "/api/decision-support/evaluation-series/series-1/invalidations",
            json=invalidation_body,
        )
        assert invalidation_response.status_code == 201
        assert invalidation_response.json()["head"]["head_kind"] == (
            "ADVICE_CURRENTNESS_INVALIDATION"
        )

        replay_response = client.post(
            "/api/decision-support/evaluation-series/series-1/invalidations",
            json=invalidation_body,
        )
        assert replay_response.status_code == 200
        assert replay_response.json()["result"] == "IDEMPOTENT_REPLAY"
        audit_response = client.get("/api/audit/occurrences")
        assert audit_response.status_code == 200
        assert {
            item["occurrence_kind"] for item in audit_response.json()["items"]
        } >= {"DECISION_SUPPORT_EVALUATION", "DECISION_SUPPORT_INVALIDATION"}
    finally:
        client.__exit__(None, None, None)
