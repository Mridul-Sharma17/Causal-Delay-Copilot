from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.local_qualification import (
    REQUIRED_LOCAL_CHECK_IDS,
    LocalQualificationError,
    build_local_qualification,
    fresh_run_capability,
    validate_local_qualification,
    verify_local_qualification,
    write_local_qualification,
)
from backend.app.settings import DeliveryProfile, Settings


def _checks(*, blocked: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "status": "BLOCKED" if check_id == blocked else "VERIFIED",
            "code": "CHECK_BLOCKED" if check_id == blocked else "CHECK_PASSED",
            "evidence": {
                "artifact_hashes": ["sha256:" + "a" * 64],
                "result": "verified",
            },
        }
        for check_id in REQUIRED_LOCAL_CHECK_IDS
    ]


def _commands() -> list[dict[str, object]]:
    return [
        {
            "command": "uv run --locked --no-sync pytest backend/tests/test_local_fallback.py",
            "cli": "uv",
            "version": "0.11.8",
            "target": "local-fallback",
            "started_at": "2026-08-12T00:00:00+00:00",
            "finished_at": "2026-08-12T00:00:01+00:00",
            "duration_ms": 1000,
            "exit_status": 0,
            "redacted_output_digest": "sha256:" + "b" * 64,
        }
    ]


def _qualification(
    *, checks: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return build_local_qualification(
        source_commit="a" * 40,
        release_candidate_id="local-fallback",
        build_manifest_id="local-fallback",
        target={
            "profile": "LOCAL_FALLBACK",
            "host": "Windows",
            "origin": "http://127.0.0.1:8000",
        },
        checks=checks or _checks(),
        commands=_commands(),
        platform={
            "os": "Windows",
            "python_version": "3.12.13",
            "node_version": "v24.15.0",
            "playwright_version": "1.58.2",
            "network_state": "EXTERNAL_NETWORK_UNAVAILABLE",
        },
        observed_at="2026-08-12T00:00:00+00:00",
    )


def test_local_qualification_requires_every_gate_for_fresh_control() -> None:
    qualified = _qualification()
    blocked = _qualification(checks=_checks(blocked="fresh_runs_under_five_minutes"))

    assert qualified["qualification_status"] == "QUALIFIED"
    assert qualified["fresh_demo_control"] == "ENABLED"
    assert blocked["qualification_status"] == "BLOCKED"
    assert blocked["fresh_demo_control"] == "DISABLED"


def test_local_qualification_round_trips_as_canonical_immutable_file(
    tmp_path: Path,
) -> None:
    payload = _qualification()
    written = write_local_qualification(tmp_path, payload)

    assert verify_local_qualification(written) == payload
    assert written.name == "local-fallback-qualification.json"
    assert written.read_text(encoding="utf-8") == (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )

    with pytest.raises(LocalQualificationError, match="QUALIFICATION_ALREADY_EXISTS"):
        write_local_qualification(
            tmp_path,
            _qualification(checks=_checks(blocked="online_setup")),
        )

    written.write_text(written.read_text(encoding="utf-8").replace("QUALIFIED", "BLOCKED"), encoding="utf-8")
    with pytest.raises(
        LocalQualificationError,
        match="QUALIFICATION_(?:NOT_CANONICAL|CONTENT_HASH_MISMATCH|STATUS_MISMATCH)",
    ):
        verify_local_qualification(written)


def test_local_qualification_rejects_unredacted_or_incomplete_command_provenance() -> None:
    invalid = _qualification()
    invalid["commands"] = [
        {
            **_commands()[0],
            "raw_output": "a filesystem path and a secret",
        }
    ]

    with pytest.raises(LocalQualificationError, match="UNREDACTED_COMMAND_OUTPUT_FORBIDDEN"):
        validate_local_qualification(invalid)


def test_fresh_run_capability_is_unavailable_until_a_matching_qualification_exists(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime" / "local-fallback-qualification.json"
    missing = fresh_run_capability(
        path,
        required=True,
        expected_release_candidate_id="local-fallback",
        expected_build_manifest_id="local-fallback",
    )
    assert missing["state"] == "unavailable"
    assert missing["control"] == "disabled"

    write_local_qualification(path.parent, _qualification())
    available = fresh_run_capability(
        path,
        required=True,
        expected_release_candidate_id="local-fallback",
        expected_build_manifest_id="local-fallback",
    )
    assert available["state"] == "available"
    assert available["code"] == "FRESH_RUN_QUALIFIED"

    mismatched = fresh_run_capability(
        path,
        required=True,
        expected_release_candidate_id="another-release",
        expected_build_manifest_id="local-fallback",
    )
    assert mismatched["state"] == "unavailable"


def test_fresh_run_capability_rejects_inconsistent_public_state() -> None:
    from backend.app.contracts import FreshRunCapability

    with pytest.raises(ValueError, match="fresh run capability state is inconsistent"):
        FreshRunCapability(
            schema_version="fresh-run-capability.v1",
            state="available",
            code="FRESH_RUN_QUALIFIED",
            control="enabled",
            qualification_hash=None,
        )


def test_required_fresh_run_capability_blocks_operation_admission_without_public_internals(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        release_candidate_id="local-fallback",
        build_manifest_id="local-fallback",
        require_fresh_demo_qualification=True,
    )

    with TestClient(create_app(settings, start_operation_runner=False)) as client:
        health = client.get("/api/health")
        refused = client.post(
            "/api/operations",
            json={
                "idempotency_key": "fresh-gate-test",
                "operation_kind": "FRESH_ANALYSIS",
                "request": {"analysis_request_id": "fresh-gate-test"},
            },
        )

    assert health.status_code == 200
    assert health.json()["fresh_run"] == {
        "schema_version": "fresh-run-capability.v1",
        "state": "unavailable",
        "code": "FRESH_RUN_UNAVAILABLE",
        "control": "disabled",
        "qualification_hash": None,
    }
    assert refused.status_code == 503
    assert refused.json() == {
        "code": "FRESH_RUN_UNAVAILABLE",
        "recovery_action": "RUN_LOCAL_FALLBACK_QUALIFICATION_AND_RETRY",
    }
