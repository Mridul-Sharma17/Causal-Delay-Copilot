from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


def make_client(database_path: Path) -> TestClient:
    return TestClient(create_app(Settings(database_path=database_path)))


def import_hero(client: TestClient) -> str:
    response = client.post(
        "/api/ingestion-runs",
        json={
            "idempotency_key": "proactive-hero-import",
            "dataset_key": "semi-synthetic-hero",
            "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
        },
    )
    assert response.status_code == 201
    return str(response.json()["dataset_version_id"])


def test_valid_proposal_creates_an_immutable_preview_request_and_replays(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        previews = client.get(
            "/api/proactive-proposals",
            params={"dataset_version_id": dataset_version_id},
        )
        assert previews.status_code == 200
        assert "protected_source_locator" not in json.dumps(previews.json())
        assert "requester_ref" not in json.dumps(previews.json())

        fixture_request = {
            "dataset_version_id": dataset_version_id,
            "fixture_id": "hero-proactive-proposal-v1",
        }
        created = client.post(
            "/api/investigations/proactive/fixtures",
            json=fixture_request,
        )
        replay = client.post(
            "/api/investigations/proactive/fixtures",
            json=fixture_request,
        )

        assert created.status_code == 201
        assert replay.status_code == 200
        assert created.json()["result"] == "CREATED"
        assert replay.json()["result"] == "IDEMPOTENT_REPLAY"

        attempt = created.json()["attempt"]
        request = attempt["investigation_request"]
        assert attempt["scope"] == "proactive_ingress"
        assert attempt["status"] == "accepted"
        assert attempt["primary_code"] == "PROACTIVE_ACCEPTED"
        assert request["trigger_mode"] == "proactive"
        assert request["ingress_ref"]["kind"] == "ProactiveProposal"
        assert request["subject"]["kind"] == "proactive_preview"
        assert "order_line_id" not in json.dumps(request)
        assert request["decision_cutoff_source"] == "proactive_decision"
        assert request["observation_cutoff"]["value"]["normalized_value"] == (
            "2026-01-10T03:30:00+00:00"
        )
        assert request["prediction_metadata"]["state"] == "not_applicable"
        assert "prediction_metadata" not in request["causal_engine_input"]
        assert "score_value" not in json.dumps(request["causal_engine_input"])
        exposure = request["causal_engine_input"]["supplier_load_exposure"]
        assert exposure["trigger_mode"] == "proactive"
        assert exposure["cutoff_source"] == "proactive_decision"
        assert exposure["provisional_load_snapshot"]["state"] == "present"
        assert "load_snapshot" not in exposure
        assert "high_load_exposure" not in json.dumps(exposure)
        assert "order_line_id" not in json.dumps(exposure)
        outcome = request["causal_engine_input"]["supplier_milestone_outcome"]
        assert outcome["state"] == "not_applicable"
        assert outcome["role"] == "SUBJECT_LINE"
        assert outcome["canonical_slippage_duration_basis"] == "CALENDAR_DAY"
        assert outcome["outcome_code"] == "OUTCOME_NOT_REQUIRED_FOR_SUBJECT"
        assert outcome["supplier_milestone_slippage_days"] is None
        assert outcome["actual_target_milestone"] is None
        eligibility = request["causal_engine_input"]["eligibility"]
        assert eligibility["trigger_mode"] == "proactive"
        assert eligibility["state"] == "scientifically_unavailable"
        assert eligibility["estimator_input"] is None
        assert "order_line_id" not in json.dumps(eligibility)
        assert "source_observation_id" not in json.dumps(eligibility)
        assert eligibility["subject"]["state"] in {"unavailable", "ineligible"}

        lineage = client.get(f"/api/datasets/{dataset_version_id}/lineage")
        assert lineage.status_code == 200
        assert lineage.json()["dataset_version"]["record_counts"]["order_lines"] == 3

        audit = client.get("/api/audit/occurrences")
        assert audit.status_code == 200
        assert [item["occurrence_kind"] for item in audit.json()["items"]] == [
            "PROACTIVE_INGRESS",
            "PROACTIVE_INGRESS",
            "LINEAGE_SNAPSHOT_VIEW",
        ]


def test_late_known_proposal_input_is_preserved_in_the_accepted_request(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        response = client.post(
            "/api/investigations/proactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-proactive-proposal-late-field-v1",
            },
        )

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "accepted"
        request = attempt["investigation_request"]
        assert request is not None
        assert request["subject"]["adjustment_inputs"]["quantity"]["state"] == "present"
        assert request["subject"]["adjustment_inputs"]["quantity"]["known_at"][
            "value"
        ] == "2026-01-10T09:05:00+05:30"


def test_proactive_projection_matches_shared_causal_shape_without_subject_removal(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        reactive = client.post(
            "/api/investigations/reactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-reactive-risk-predictive-baseline-v1",
            },
        )
        proactive = client.post(
            "/api/investigations/proactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-proactive-proposal-v1",
            },
        )

        assert reactive.status_code == 201
        assert proactive.status_code == 201
        reactive_input = reactive.json()["attempt"]["investigation_request"][
            "causal_engine_input"
        ]
        proactive_input = proactive.json()["attempt"]["investigation_request"][
            "causal_engine_input"
        ]
        assert set(proactive_input) == set(reactive_input)
        assert set(proactive_input["subject_analytical_values"]) == set(
            reactive_input["subject_analytical_values"]
        )
        assert (
            proactive_input["estimator_window_ref"]["subject_removal"]["removed"]
            is False
        )
        assert (
            reactive_input["estimator_window_ref"]["subject_removal"]["removed"]
            is True
        )
        assert "prediction_metadata" not in proactive_input
        assert "score_value" not in json.dumps(proactive_input)


def test_proactive_schema_failure_is_sanitized_and_audited(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.post(
            "/api/investigations/proactive",
            json={"unexpected": True},
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": "PROACTIVE_SCHEMA_UNSUPPORTED",
            "recovery_action": "USE_SUPPORTED_PROACTIVE_PROPOSAL_SCHEMA",
        }
        audit = client.get("/api/audit/occurrences").json()["items"]
        assert len(audit) == 1
        assert audit[0]["occurrence_kind"] == "PROACTIVE_INGRESS"
        assert audit[0]["outcome_code"] == "PROACTIVE_SCHEMA_UNSUPPORTED"


def test_proactive_refresh_creates_a_new_snapshot_and_refresh_run(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        created = client.post(
            "/api/investigations/proactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-proactive-proposal-v1",
            },
        )
        assert created.status_code == 201
        predecessor = created.json()["attempt"]["investigation_request"]
        proposal = client.app.state.audit_store.get_proactive_proposal_fixture(
            dataset_version_id,
            "hero-proactive-proposal-v1",
        )

        refreshed = client.post(
            f"/api/investigations/{predecessor['investigation_request_id']}/refresh",
            json={
                "idempotency_key": "refresh-proactive-1",
                "trigger_mode": "proactive",
                "request": proposal.model_dump(mode="json"),
                "observation_cutoff": {
                    "value": "2026-01-11T03:35:00+00:00",
                    "kind": "instant",
                    "precision": "minute",
                    "timezone_status": "known",
                    "source_timezone": "UTC",
                },
                "root_seed": 17,
            },
        )

        assert refreshed.status_code == 202
        body = refreshed.json()
        assert body["result"] == "CREATED"
        assert body["attempt"]["investigation_request_id"] != predecessor[
            "investigation_request_id"
        ]
        assert body["snapshot"] is not None, body
        assert body["snapshot"]["predecessor_request_id"] == predecessor[
            "investigation_request_id"
        ]
        assert body["snapshot"]["trigger_mode"] == "proactive"
        assert body["operation"]["analysis_run"]["run_relationship"] == "refresh"
