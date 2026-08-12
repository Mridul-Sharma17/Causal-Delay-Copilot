from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings
from backend.tests.test_analysis_runs import _suite_request


TERMINAL_OPERATION_STATES = frozenset(
    {
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
        "INTERRUPTED",
        "REJECTED",
    }
)
REFERENCE_SLOT_ID = "ordinary-demo"
REFERENCE_ROLE = "semi_synthetic_hero"
BUILD_MANIFEST_ID = "core-issue-64-browser-v1"


@dataclass(frozen=True)
class PreparedCoreJourney:
    profile: DeliveryProfile
    state_root: Path
    dataset_version_id: str
    investigation_request_id: str
    analysis_run_id: str
    reproduction_run_id: str
    reference_slot_id: str


def core_journey_settings(
    state_root: Path,
    profile: DeliveryProfile,
    *,
    public_origin: str | None = None,
    spa_dist_dir: Path | None = None,
    release_candidate_id: str | None = None,
    build_manifest_id: str | None = None,
) -> Settings:
    state_root = state_root.resolve()
    release_candidate_id = release_candidate_id or f"core-issue-64-{profile.value.lower()}"
    build_manifest_id = build_manifest_id or BUILD_MANIFEST_ID
    if profile is DeliveryProfile.HOSTED:
        return Settings(
            profile=profile,
            state_root=state_root,
            railway_volume_path=state_root.parent,
            public_origin=public_origin or "https://core-issue-64.example.test",
            release_candidate_id=release_candidate_id,
            build_manifest_id=build_manifest_id,
            gemini_enabled=False,
            gemini_api_key=None,
            spa_dist_dir=spa_dist_dir,
        )
    return Settings(
        profile=profile,
        state_root=state_root,
        public_origin=public_origin or "http://127.0.0.1:8000",
        release_candidate_id=release_candidate_id,
        build_manifest_id=build_manifest_id,
        gemini_enabled=False,
        gemini_api_key=None,
        spa_dist_dir=spa_dist_dir,
    )


def core_journey_client(settings: Settings) -> TestClient:
    return TestClient(
        create_app(settings),
        base_url=settings.public_origin or "http://127.0.0.1:8000",
    )


def wait_for_terminal_operation(
    client: TestClient,
    operation_id: str,
    *,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/operations/{operation_id}")
        assert response.status_code == 200, response.text
        operation = response.json()
        if operation.get("state") in TERMINAL_OPERATION_STATES:
            return operation
        time.sleep(0.05)
    raise AssertionError(f"operation {operation_id} did not reach a terminal state")


def _assert_status(response: Any, expected: set[int]) -> dict[str, Any]:
    assert response.status_code in expected, response.text
    payload = response.json()
    assert isinstance(payload, dict), payload
    return payload


def _bound_reproduction_suite(dataset_version_id: str) -> dict[str, Any]:
    """Use the canonical deterministic suite with real delivery identities."""

    suite = deepcopy(_suite_request())
    lineage_ref = f"lineage:{dataset_version_id}"
    suite["dataset_version_id"] = dataset_version_id
    suite["evidence_refs"] = [lineage_ref]
    for variant in suite["variant_inputs"]:
        variant["evidence_refs"] = [lineage_ref]
    return suite


def prepare_core_journey(
    state_root: Path,
    profile: DeliveryProfile,
    *,
    public_origin: str | None = None,
    spa_dist_dir: Path | None = None,
    release_candidate_id: str | None = None,
    build_manifest_id: str | None = None,
) -> PreparedCoreJourney:
    """Prepare a real API/SQLite/artifact state for the compiled-browser journey."""

    settings = core_journey_settings(
        state_root,
        profile,
        public_origin=public_origin,
        spa_dist_dir=spa_dist_dir,
        release_candidate_id=release_candidate_id,
        build_manifest_id=build_manifest_id,
    )
    with core_journey_client(settings) as client:
        imported = _assert_status(
            client.post(
                "/api/ingestion-runs",
                json={
                    "idempotency_key": "core-journey-dataset-v1",
                    "dataset_key": "semi-synthetic-hero",
                    "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
                },
            ),
            {200, 201},
        )
        dataset_version_id = str(imported["dataset_version_id"])

        reactive = _assert_status(
            client.post(
                "/api/investigations/reactive/fixtures",
                json={
                    "dataset_version_id": dataset_version_id,
                    "fixture_id": "hero-reactive-risk-predictive-baseline-v1",
                },
            ),
            {200, 201},
        )
        reactive_attempt = reactive["attempt"]
        investigation_request_id = str(
            reactive_attempt["investigation_request_id"]
        )
        assert reactive_attempt["status"] == "accepted"

        proactive = _assert_status(
            client.post(
                "/api/investigations/proactive/fixtures",
                json={
                    "dataset_version_id": dataset_version_id,
                    "fixture_id": "hero-proactive-proposal-v1",
                },
            ),
            {200, 201},
        )
        assert proactive["attempt"]["status"] == "accepted"
        assert proactive["attempt"]["investigation_request"]["trigger_mode"] == (
            "proactive"
        )

        suite = _bound_reproduction_suite(dataset_version_id)
        admitted = _assert_status(
            client.post(
                "/api/operations",
                json={
                    "operation_kind": "FRESH_ANALYSIS",
                    "idempotency_key": "core-journey-fresh-analysis-v1",
                    "memory_required_bytes": 1024,
                    "request": {
                        "investigation_request_id": investigation_request_id,
                        "suite_request": suite,
                    },
                },
            ),
            {202},
        )
        fresh = wait_for_terminal_operation(
            client,
            str(admitted["operation"]["operation_id"]),
        )
        assert fresh["state"] == "SUCCEEDED", fresh
        assert fresh["analysis_run"]["lifecycle"] == "sealed"
        assert fresh["analysis_run"]["verification_state"] == "machine_verified"
        analysis_run_id = str(fresh["analysis_run"]["analysis_run_id"])

        reproduction_admitted = _assert_status(
            client.post(
                "/api/operations",
                json={
                    "operation_kind": "FRESH_REPRODUCTION",
                    "idempotency_key": "core-journey-fresh-reproduction-v1",
                    "memory_required_bytes": 1024,
                    "request": {"target_analysis_run_id": analysis_run_id},
                },
            ),
            {202},
        )
        reproduction = wait_for_terminal_operation(
            client,
            str(reproduction_admitted["operation"]["operation_id"]),
        )
        assert reproduction["state"] == "SUCCEEDED", reproduction
        reproduction_run = reproduction["analysis_run"]
        assert reproduction_run["run_relationship"] == "reproduction"
        assert reproduction_run["reproduction_comparison"]["status"] == "passed"
        reproduction_run_id = str(reproduction_run["analysis_run_id"])

        promoted = client.app.state.reference_store.promote_reference(
            reproduction_run_id,
            REFERENCE_SLOT_ID,
            intended_role=REFERENCE_ROLE,
        )
        assert promoted.created is True
        delivered = _assert_status(client.get("/api/evidence/reference"), {200})
        assert delivered["reference_slot_id"] == REFERENCE_SLOT_ID
        assert delivered["dataset_version_id"] == dataset_version_id
        assert delivered["analysis_run_id"] == reproduction_run_id

    return PreparedCoreJourney(
        profile=profile,
        state_root=settings.state_root,
        dataset_version_id=dataset_version_id,
        investigation_request_id=investigation_request_id,
        analysis_run_id=analysis_run_id,
        reproduction_run_id=reproduction_run_id,
        reference_slot_id=REFERENCE_SLOT_ID,
    )
