from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.canonical import sha256
from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings
from backend.tests.core_journey_support import (
    REFERENCE_SLOT_ID,
    core_journey_client,
    core_journey_settings,
    prepare_core_journey,
)
from backend.tests.test_analysis_runs import _suite_request


def _wait_for_terminal(client: TestClient, operation_id: str) -> dict[str, object]:
    for _ in range(240):
        response = client.get(f"/api/operations/{operation_id}")
        assert response.status_code == 200
        operation = response.json()
        if operation["state"] in {
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
            "TIMED_OUT",
            "INTERRUPTED",
            "REJECTED",
        }:
            return operation
        time.sleep(0.05)
    raise AssertionError(f"operation {operation_id} did not reach a terminal state")


def test_fresh_bundle_survives_a_local_restart_with_its_full_runtime_identity(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        gemini_enabled=False,
        gemini_api_key=None,
    )
    request = _suite_request()

    with TestClient(create_app(settings)) as client:
        admitted = client.post(
            "/api/operations",
            json={
                "operation_kind": "FRESH_ANALYSIS",
                "idempotency_key": "core-journey-runtime-restart",
                "memory_required_bytes": 1024,
                "request": {"suite_request": request},
            },
        )
        assert admitted.status_code == 202, admitted.text
        terminal = _wait_for_terminal(
            client,
            admitted.json()["operation"]["operation_id"],
        )
        assert terminal["state"] == "SUCCEEDED"
        assert terminal["analysis_run"]["lifecycle"] == "sealed"
        assert terminal["analysis_run"]["verification_state"] == "machine_verified"

    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json()["state"] == "degraded"


@pytest.mark.parametrize(
    "profile",
    [DeliveryProfile.LOCAL_FALLBACK, DeliveryProfile.HOSTED],
)
def test_real_delivery_profiles_share_the_api_sqlite_artifact_and_replay_contract(
    tmp_path: Path,
    profile: DeliveryProfile,
) -> None:
    state_root = tmp_path / profile.value.lower()
    prepared = prepare_core_journey(state_root, profile)
    settings = core_journey_settings(state_root, profile)

    with core_journey_client(settings) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json()["state"] == "degraded"

        reference_response = client.get("/api/evidence/reference")
        assert reference_response.status_code == 200, reference_response.text
        reference = reference_response.json()
        assert reference["reference_slot_id"] == REFERENCE_SLOT_ID
        assert reference["analysis_run_id"] == prepared.reproduction_run_id
        assert reference["dataset_version_id"] == prepared.dataset_version_id
        assert reference["release_candidate_id"] == (
            f"core-issue-64-{profile.value.lower()}"
        )
        assert reference["runtime_fingerprint_digest"].startswith("sha256:")
        assert "filesystem" not in json.dumps(reference).lower()

        lineage_response = client.get(
            f"/api/datasets/{prepared.dataset_version_id}/lineage"
        )
        assert lineage_response.status_code == 200, lineage_response.text
        lineage = lineage_response.json()
        assert lineage["dataset_version"]["dataset_version_id"] == (
            prepared.dataset_version_id
        )
        assert lineage["dataset_version"]["mapping_manifest_id"] == (
            "semi-synthetic-hero.mapping.v1"
        )

        signals_response = client.get(
            "/api/risk-signals",
            params={"dataset_version_id": prepared.dataset_version_id},
        )
        assert signals_response.status_code == 200, signals_response.text
        signals = signals_response.json()
        assert signals["predictive_status"]["state"] == "verified"
        assert any(
            item["fixture_id"] == "hero-reactive-risk-predictive-baseline-v1"
            for item in signals["items"]
        )

        proactive_response = client.post(
            "/api/investigations/proactive/fixtures",
            json={
                "dataset_version_id": prepared.dataset_version_id,
                "fixture_id": "hero-proactive-proposal-v1",
            },
        )
        assert proactive_response.status_code == 201, proactive_response.text
        proactive_attempt = proactive_response.json()["attempt"]
        assert proactive_attempt["status"] == "accepted"
        assert proactive_attempt["investigation_request"]["trigger_mode"] == (
            "proactive"
        )

        reactive_response = client.post(
            "/api/investigations/reactive/fixtures",
            json={
                "dataset_version_id": prepared.dataset_version_id,
                "fixture_id": "hero-reactive-risk-predictive-baseline-v1",
            },
        )
        assert reactive_response.status_code == 201, reactive_response.text
        reactive_attempt = reactive_response.json()["attempt"]
        assert reactive_attempt["status"] == "accepted"
        request_id = reactive_attempt["investigation_request_id"]

        brief_response = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "core-journey-decision-brief-v1",
                "reference_id": REFERENCE_SLOT_ID,
            },
        )
        assert brief_response.status_code == 201, brief_response.text
        snapshot = brief_response.json()["snapshot"]
        assert snapshot["subject_applicability"]["state"] == "abstained"
        assert snapshot["action_lane"]["state"] == "read_only"
        assert snapshot["decision_support"]["action_recommendation"] is None

        replay_response = client.get(
            "/api/audit/replay",
            params={
                "investigation_request_id": request_id,
                "event_seq": snapshot["event_seq"],
            },
        )
        assert replay_response.status_code == 200, replay_response.text
        replay = replay_response.json()
        assert replay["status"] == "REPLAYED"
        assert replay["snapshot"] == snapshot
        assert replay["historical_state"]["read_only"] is True
        assert replay["historical_state"]["recommendation"]["state"] == (
            "NOT_PUBLISHED"
        )
        assert replay["historical_state"]["decision"]["state"] == (
            "NOT_RECORDED"
        )

        idempotent_brief = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "core-journey-decision-brief-v1",
                "reference_id": REFERENCE_SLOT_ID,
            },
        )
        assert idempotent_brief.status_code == 200, idempotent_brief.text
        assert idempotent_brief.json()["result"] == "IDEMPOTENT_REPLAY"
        assert idempotent_brief.json()["snapshot"] == snapshot

        with sqlite3.connect(settings.database_path) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            assert {"audit_events", "decision_brief_snapshots", "durable_operations"} <= (
                table_names
            )
            assert connection.execute(
                "SELECT COUNT(*) FROM decision_brief_snapshots"
            ).fetchone()[0] >= 1

        manifest_path = (
            settings.artifact_root
            / "runs"
            / prepared.reproduction_run_id
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_core = dict(manifest)
        manifest_core.pop("bundle_manifest_hash")
        assert sha256(manifest_core) == manifest["bundle_manifest_hash"]
        assert manifest["investigation_request_id"] == prepared.investigation_request_id
        assert manifest["reproduces_run_id"] == prepared.analysis_run_id
        assert manifest["artifact_descriptors"]
        for descriptor in manifest["artifact_descriptors"]:
            digest = descriptor["sha256"]
            object_path = (
                settings.artifact_root
                / "objects"
                / descriptor["confidentiality_class"]
                / "sha256"
                / digest[7:9]
                / digest[9:]
            )
            assert object_path.is_file()
            assert (
                "sha256:" + hashlib.sha256(object_path.read_bytes()).hexdigest()
            ) == digest


def test_real_fresh_reproduction_is_reusable_after_a_process_restart(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "restartable"
    prepared = prepare_core_journey(state_root, DeliveryProfile.LOCAL_FALLBACK)
    settings = core_journey_settings(state_root, DeliveryProfile.LOCAL_FALLBACK)

    with core_journey_client(settings) as client:
        reference = client.get("/api/evidence/reference")
        assert reference.status_code == 200, reference.text
        assert reference.json()["analysis_run_id"] == prepared.reproduction_run_id
        assert client.get("/api/health").status_code == 200
