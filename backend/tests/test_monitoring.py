from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.canonical import sha256
from backend.app.monitoring import (
    MonitoringContractError,
    evaluate_monitoring_predicate,
    monitoring_match_result_key_for,
    monitoring_observation_key_for,
    monitoring_review_request_key_for,
    normalize_monitoring_observation,
    normalize_monitoring_trigger,
)
from backend.tests.test_decision_support_currentness import (
    _identity_binding,
    _evaluation,
)
from backend.app.ingestion import LineageStore
from backend.app.decision_support_currentness import DecisionSupportCurrentnessConflict
from backend.app.main import create_app
from backend.app.settings import Settings


FIXTURE_ROOT = Path(__file__).parents[2] / "tests" / "fixtures" / "decision_support" / "v1"


def _trigger() -> dict[str, object]:
    record: dict[str, object] = {
        "schema_identifier": "monitoring-escalation-trigger",
        "schema_version": "1",
        "trigger_id": "trigger:load:v1",
        "trigger_version": "1",
        "registry_identifier": "decision-support-monitoring-escalation-triggers",
        "registry_version": "1",
        "option_code": "ACCEPT_AND_MONITOR",
        "option_version": "1",
        "trigger_modes": ["REACTIVE"],
        "observation_registry": {
            "registry_identifier": "decision-support-monitoring-observations",
            "registry_version": "1",
            "observation_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
            "value_type": "DECIMAL",
            "unit": "RATIO",
            "source_schema": {
                "identifier": "subject-driver-state",
                "version": "1",
                "content_hash": "sha256:" + "1" * 64,
            },
            "mapping_manifest_ref_and_hash": {
                "reference": "mapping:monitoring:v1",
                "content_hash": "sha256:" + "2" * 64,
            },
            "mapping_entry_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
        },
        "operator": "GTE",
        "threshold": {
            "state": "present",
            "value_type": "DECIMAL",
            "value": "decimal:0.80",
            "unit": "RATIO",
        },
        "response_code": "REQUEST_MANAGER_REVIEW",
        "source_refs": [
            {
                "reference": "review-source:trigger",
                "content_hash": "sha256:" + "3" * 64,
            }
        ],
        "provenance": {"source_kind": "test"},
        "published_at": "2026-08-01T00:00:00+00:00",
        "state": "APPROVED",
        "lifecycle_status": "ACTIVE",
        "review_status": "APPROVED",
        "reviewer_role": "TEST_REVIEW",
        "review_date": "2026-08-01T00:00:00+00:00",
        "review_reference": "review:trigger:v1",
        "review_reason_code": "test",
    }
    record["content_hash"] = sha256(record)
    return record


def _observation(*, value: str = "decimal:0.90") -> dict[str, object]:
    record: dict[str, object] = {
        "schema_identifier": "monitoring-observation",
        "schema_version": "1",
        "occurrence_id": "observation:1",
        "observation_registry_id": "decision-support-monitoring-observations",
        "observation_registry_version": "1",
        "observation_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
        "source_mapping_manifest_ref_and_hash": {
            "reference": "mapping:monitoring:v1",
            "content_hash": "sha256:" + "2" * 64,
        },
        "mapping_entry_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
        "subject_identity": "subject:1",
        "value_type": "DECIMAL",
        "observed_value": value,
        "observed_unit": "RATIO",
        "source_schema_id_version_and_hash": {
            "identifier": "subject-driver-state",
            "version": "1",
            "content_hash": "sha256:" + "1" * 64,
        },
        "source_record_ref_and_hash": {
            "reference": "source-record:1",
            "content_hash": "sha256:" + "4" * 64,
        },
        "observed_at": "2026-08-01T12:00:00+00:00",
        "first_available_at": "2026-08-01T12:00:00+00:00",
        "available_at": "2026-08-01T12:00:00+00:00",
    }
    record["monitoring_observation_key"] = monitoring_observation_key_for(record)
    record["content_hash"] = sha256(record)
    return record


def test_monitoring_predicate_is_typed_and_keys_are_deterministic() -> None:
    trigger = normalize_monitoring_trigger(_trigger())
    observation = normalize_monitoring_observation(_observation())

    assert evaluate_monitoring_predicate(trigger, observation) is True
    assert observation["monitoring_observation_key"].startswith("sha256:")

    replay = deepcopy(observation)
    replay["occurrence_id"] = "observation:wrapped-again"
    replay["content_hash"] = sha256(replay)
    assert monitoring_observation_key_for(replay) == observation["monitoring_observation_key"]

    request_key = monitoring_review_request_key_for(
        {
            "evaluation_series_id": "series:1",
            "recommendation_occurrence_id": "recommendation:1",
            "trigger_id_and_version": {"id": "trigger:load:v1", "version": "1"},
            "monitoring_observation_key": observation["monitoring_observation_key"],
            "monitoring_observation_ref_and_hash": {
                "reference": "monitoring-observation:observation:1",
                "content_hash": observation["content_hash"],
            },
            "accepted_selection_claim_ref_and_hash_or_null": None,
            "currentness_operation_ref_and_hash": {
                "reference": "currentness-operation:1",
                "content_hash": "sha256:" + "5" * 64,
            },
            "currentness_check_ref_and_hash": {
                "reference": "currentness-check:1",
                "content_hash": "sha256:" + "6" * 64,
            },
            "response_code": "REQUEST_MANAGER_REVIEW",
        }
    )
    result_key = monitoring_match_result_key_for(
        {
            "recommendation_ref_and_hash": {
                "reference": "recommendation:1",
                "content_hash": "sha256:" + "7" * 64,
            },
            "trigger_id_and_version": {"id": "trigger:load:v1", "version": "1"},
            "monitoring_observation_key": observation["monitoring_observation_key"],
            "monitoring_observation_ref_and_hash": {
                "reference": "monitoring-observation:observation:1",
                "content_hash": observation["content_hash"],
            },
            "accepted_selection_claim_ref_and_hash_or_null": None,
            "currentness_operation_ref_and_hash": {
                "reference": "currentness-operation:1",
                "content_hash": "sha256:" + "5" * 64,
            },
            "currentness_check_ref_and_hash": {
                "reference": "currentness-check:1",
                "content_hash": "sha256:" + "6" * 64,
            },
            "match_outcome": "REQUEST_MANAGER_REVIEW",
            "monitoring_review_request_key_or_null": request_key,
        }
    )
    assert result_key.startswith("sha256:")


def test_monitoring_predicate_rejects_unit_and_type_coercion() -> None:
    trigger = normalize_monitoring_trigger(_trigger())

    wrong_unit = _observation()
    wrong_unit["observed_unit"] = "PERCENT"
    wrong_unit.pop("content_hash")
    wrong_unit["monitoring_observation_key"] = monitoring_observation_key_for(wrong_unit)
    wrong_unit["content_hash"] = sha256(wrong_unit)
    with pytest.raises(MonitoringContractError, match="unit"):
        evaluate_monitoring_predicate(trigger, normalize_monitoring_observation(wrong_unit))

    wrong_type = _observation()
    wrong_type["observed_value"] = "0.90"
    wrong_type.pop("monitoring_observation_key")
    wrong_type.pop("content_hash")
    wrong_type["content_hash"] = sha256(wrong_type)
    with pytest.raises(MonitoringContractError, match="decimal"):
        normalize_monitoring_observation(wrong_type)

    equality_trigger = deepcopy(_trigger())
    equality_trigger["operator"] = "EQ"
    equality_trigger["threshold"] = {
        "state": "present",
        "value_type": "DECIMAL",
        "value": "decimal:0.80",
        "unit": "RATIO",
    }
    equality_trigger.pop("content_hash")
    equality_trigger["content_hash"] = sha256(equality_trigger)
    equality_observation = _observation(value="decimal:0.8")
    assert evaluate_monitoring_predicate(
        normalize_monitoring_trigger(equality_trigger),
        normalize_monitoring_observation(equality_observation),
    ) is True


def test_monitoring_trigger_rejects_compound_or_non_review_response() -> None:
    compound = _trigger()
    compound["operator"] = ["GTE", "LT"]
    compound.pop("content_hash")
    compound["content_hash"] = sha256(compound)
    with pytest.raises(MonitoringContractError, match="operator"):
        normalize_monitoring_trigger(compound)

    response = _trigger()
    response["response_code"] = "EXECUTE_ACTION"
    response.pop("content_hash")
    response["content_hash"] = sha256(response)
    with pytest.raises(MonitoringContractError, match="response"):
        normalize_monitoring_trigger(response)


def _fixture_trigger() -> dict[str, object]:
    records = json.loads((FIXTURE_ROOT / "records.json").read_text(encoding="utf-8"))
    return next(
        record
        for record in records["monitoring_triggers"]
        if record["record_id"].endswith(":reactive:v1")
    )


def _monitor_published(store: LineageStore, workspace_id: str):
    identity = _identity_binding()
    trigger = _fixture_trigger()
    evaluation = _evaluation()
    recommendation = deepcopy(evaluation["action_recommendation"])
    recommendation.update(
        {
            "selected_option_code": "ACCEPT_AND_MONITOR",
            "selected_option_version": "1",
            "monitoring_escalation_trigger_ref_and_hash": {
                "reference": trigger["trigger_id"],
                "content_hash": trigger["content_hash"],
            },
            "monitoring_trigger_ref_and_hash": {
                "reference": trigger["trigger_id"],
                "content_hash": trigger["content_hash"],
            },
        },
    )
    evaluation["action_recommendation"] = recommendation
    evaluation["identity_binding"] = deepcopy(identity)
    evaluation["registry_inspection"] = {"monitoring_triggers": [trigger]}
    return store.publish_decision_support_evaluation(
        workspace_id,
        idempotency_key="monitoring-evaluation",
        evaluation=evaluation,
        identity_binding=identity,
        now=datetime(2026, 8, 9, 10, 1, tzinfo=timezone.utc),
    )


def _fixture_observation(trigger: dict[str, object]) -> dict[str, object]:
    definition = trigger["observation_registry"]
    source_schema = definition["source_schema"]
    mapping_ref = {
        "reference": definition["mapping_manifest_ref"],
        "content_hash": definition["mapping_manifest_hash"],
    }
    observation: dict[str, object] = {
        "schema_identifier": "monitoring-observation",
        "schema_version": "1",
        "occurrence_id": "monitoring-observation:fixture-1",
        "observation_registry_id": definition["registry_identifier"],
        "observation_registry_version": definition["registry_version"],
        "observation_code": definition["observation_code"],
        "source_mapping_manifest_ref_and_hash": mapping_ref,
        "mapping_entry_code": definition["mapping_entry_code"],
        "subject_identity": "order-line-1",
        "value_type": definition["value_type"],
        "observed_value": "decimal:0.90",
        "observed_unit": definition["unit"],
        "source_schema_id_version_and_hash": source_schema,
        "source_record_ref_and_hash": {
            "reference": "source-record:fixture-1",
            "content_hash": "sha256:" + "8" * 64,
        },
        "observed_at": "2026-08-09T10:02:00+00:00",
        "first_available_at": "2026-08-09T10:02:00+00:00",
        "available_at": "2026-08-09T10:02:00+00:00",
    }
    observation["monitoring_observation_key"] = monitoring_observation_key_for(observation)
    observation["content_hash"] = sha256(observation)
    return observation


def test_true_monitoring_match_publishes_one_review_request_and_replays(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    store: LineageStore = client.app.state.audit_store
    try:
        published = _monitor_published(store, workspace_id)
        observation = _fixture_observation(_fixture_trigger())

        first = store.match_monitoring_observation(
            workspace_id,
            observation=observation,
            evaluation_series_id=published.evaluation["evaluation_series_id"],
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
        )
        replay = store.match_monitoring_observation(
            workspace_id,
            observation=observation,
            evaluation_series_id=published.evaluation["evaluation_series_id"],
            now=datetime(2026, 8, 9, 10, 4, tzinfo=timezone.utc),
        )

        assert first.currentness["currentness_outcome"] == "CURRENTNESS_PROVEN_AT_CHECK"
        assert first.consuming_result["match_outcome"] == "REQUEST_MANAGER_REVIEW"
        request_ref = first.consuming_result["monitoring_review_request_ref_and_hash"]
        assert request_ref["reference"].startswith("monitoring-review-request:")
        assert len(store.list_decision_support_monitoring_review_requests(workspace_id)) == 1
        assert replay.result == "IDEMPOTENT_REPLAY"
        assert replay.consuming_result["consuming_result_occurrence_id"] == first.consuming_result[
            "consuming_result_occurrence_id"
        ]
        audit_items = client.get("/api/audit/occurrences").json()["items"]
        assert any(
            item["occurrence_kind"] == "DECISION_SUPPORT_MONITORING_REVIEW_REQUEST"
            and item["outcome_code"] == "REQUEST_MANAGER_REVIEW"
            for item in audit_items
        )
    finally:
        client.__exit__(None, None, None)


def test_false_monitoring_match_is_terminal_without_a_review_request(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    store: LineageStore = client.app.state.audit_store
    try:
        published = _monitor_published(store, workspace_id)
        observation = _fixture_observation(_fixture_trigger())
        observation["occurrence_id"] = "monitoring-observation:false"
        observation["source_record_ref_and_hash"] = {
            "reference": "source-record:false",
            "content_hash": "sha256:" + "9" * 64,
        }
        observation["observed_value"] = "decimal:0.70"
        observation.pop("monitoring_observation_key")
        observation.pop("content_hash")
        observation["monitoring_observation_key"] = monitoring_observation_key_for(observation)
        observation["content_hash"] = sha256(observation)

        first = store.match_monitoring_observation(
            workspace_id,
            observation=observation,
            evaluation_series_id=published.evaluation["evaluation_series_id"],
            now=datetime(2026, 8, 9, 10, 3, tzinfo=timezone.utc),
        )

        assert first.currentness["currentness_outcome"] == "CURRENTNESS_PROVEN_AT_CHECK"
        assert first.consuming_result["match_outcome"] == "NO_REVIEW_REQUEST"
        assert first.consuming_result["monitoring_review_request_ref_and_hash"] is None
        assert store.list_decision_support_monitoring_review_requests(workspace_id) == []
    finally:
        client.__exit__(None, None, None)


def test_rewrapped_monitoring_observation_is_a_cardinality_conflict(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    store: LineageStore = client.app.state.audit_store
    try:
        observation = _fixture_observation(_fixture_trigger())
        store.register_monitoring_observation(workspace_id, observation=observation)
        duplicate = deepcopy(observation)
        duplicate["occurrence_id"] = "monitoring-observation:rewrapped"
        duplicate.pop("content_hash")
        duplicate["content_hash"] = sha256(duplicate)

        with pytest.raises(DecisionSupportCurrentnessConflict, match="logical key"):
            store.register_monitoring_observation(workspace_id, observation=duplicate)
    finally:
        client.__exit__(None, None, None)


def test_monitoring_http_delivery_exposes_typed_observation_and_match_state(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3")))
    client.__enter__()
    workspace_id = client.get("/api/workspace").json()["workspace_id"]
    store: LineageStore = client.app.state.audit_store
    try:
        published = _monitor_published(store, workspace_id)
        observation = _fixture_observation(_fixture_trigger())
        registration = client.post(
            "/api/decision-support/monitoring-observations",
            json={"observation": observation},
        )
        assert registration.status_code == 201
        assert registration.json()["observation"]["monitoring_observation_key"] == observation[
            "monitoring_observation_key"
        ]
        registration_replay = client.post(
            "/api/decision-support/monitoring-observations",
            json={"observation": observation},
        )
        assert registration_replay.status_code == 200
        assert registration_replay.json()["result"] == "IDEMPOTENT_REPLAY"
        match_payload = {
            "observation": observation,
            "evaluation_series_id": published.evaluation["evaluation_series_id"],
        }
        first = client.post(
            "/api/decision-support/evaluation-series/"
            f"{published.evaluation['evaluation_series_id']}/monitoring/match",
            json=match_payload,
        )
        assert first.status_code == 201
        assert first.json()["consuming_result"]["match_outcome"] == (
            "REQUEST_MANAGER_REVIEW"
        )
        replay = client.post(
            "/api/decision-support/monitoring/match",
            json=match_payload,
        )
        assert replay.status_code == 200
        assert replay.json()["result"] == "IDEMPOTENT_REPLAY"
        assert client.get("/api/decision-support/monitoring-review-requests").json()[0][
            "response_code"
        ] == "REQUEST_MANAGER_REVIEW"
    finally:
        client.__exit__(None, None, None)
