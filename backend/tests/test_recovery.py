from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.recovery import StateRecovery, StateRecoveryError
from backend.app.settings import DeliveryProfile, Settings


def local_settings(state_root: Path) -> Settings:
    return Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
    )


def start(settings: Settings) -> TestClient:
    return TestClient(create_app(settings, start_operation_runner=False))


def audit_request(key: str, outcome_code: str = "CORE_READY_GEMINI_DEGRADED") -> dict[str, str]:
    return {
        "idempotency_key": key,
        "occurrence_kind": "BOOT_HEALTH_CHECK",
        "outcome_code": outcome_code,
    }


def test_reset_archives_complete_state_and_restores_sealed_baseline(tmp_path: Path) -> None:
    settings = local_settings(tmp_path / "state")

    with start(settings) as client:
        created = client.post("/api/audit/occurrences", json=audit_request("before-reset"))
        capability = client.cookies.get("core_demo_workspace")

    assert created.status_code == 201
    assert capability is not None

    recovery = StateRecovery(settings)
    receipt = recovery.reset()

    assert receipt.status == "RESET"
    assert receipt.archive_id is not None
    assert (recovery.archive_root / receipt.archive_id / "state" / "core.sqlite3").is_file()
    assert (
        recovery.archive_root / receipt.archive_id / "state" / "state_manifest.json"
    ).is_file()
    assert receipt.preflight_state == "VERIFIED"

    with start(settings) as restored:
        workspace = restored.get("/api/workspace")
        history = restored.get("/api/audit/occurrences")
        health = restored.get("/api/health")

    assert health.status_code == 200
    assert workspace.status_code == 200
    assert history.status_code == 200
    assert history.json()["items"] == []


def test_restore_replaces_the_whole_state_without_merging_audit_history(
    tmp_path: Path,
) -> None:
    settings = local_settings(tmp_path / "state")

    with start(settings) as client:
        first = client.post("/api/audit/occurrences", json=audit_request("archived"))
        capability = client.cookies.get("core_demo_workspace")

    recovery = StateRecovery(settings)
    archive = recovery.archive()

    with start(settings) as client:
        client.cookies.set("core_demo_workspace", capability)
        second = client.post("/api/audit/occurrences", json=audit_request("divergent"))

    restored = recovery.restore(archive.archive_id)

    assert first.status_code == 201
    assert second.status_code == 201
    assert restored.status == "RESTORED"
    assert restored.archive_id is not None
    assert restored.archive_id != archive.archive_id

    with start(settings) as client:
        client.cookies.set("core_demo_workspace", capability)
        history = client.get("/api/audit/occurrences")

    assert history.status_code == 200
    assert [item["occurrence_id"] for item in history.json()["items"]] == [
        first.json()["occurrence_id"]
    ]


def test_restore_quarantines_a_corrupt_archive_before_replacing_current_state(
    tmp_path: Path,
) -> None:
    settings = local_settings(tmp_path / "state")
    with start(settings):
        pass

    recovery = StateRecovery(settings)
    archive = recovery.archive()
    manifest_path = recovery.archive_root / archive.archive_id / "archive-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(StateRecoveryError) as failure:
        recovery.restore(archive.archive_id)

    assert failure.value.code == "CORE_STATE_BACKUP_INVALID"
    assert failure.value.quarantine_id is not None
    assert settings.state_root.is_dir()
    assert not (recovery.archive_root / archive.archive_id).exists()
    assert (
        recovery.quarantine_root
        / str(failure.value.quarantine_id)
        / "quarantine-manifest.json"
    ).is_file()


def test_reset_refuses_active_operation_without_mutating_state(tmp_path: Path) -> None:
    settings = local_settings(tmp_path / "state")

    with start(settings) as client:
        admitted = client.post(
            "/api/operations",
            json={
                "idempotency_key": "active-reset",
                "operation_kind": "BOUNDED_WORK",
                "memory_required_bytes": 1024,
                "request": {"analysis_request_id": "active-reset"},
            },
        )

    assert admitted.status_code == 202
    with pytest.raises(StateRecoveryError) as failure:
        StateRecovery(settings).reset()

    assert failure.value.code == "CORE_STATE_ACTIVE"
    assert settings.state_root.joinpath("core.sqlite3").is_file()


def test_reset_refuses_recovery_pending_state_without_mutating_state(tmp_path: Path) -> None:
    settings = local_settings(tmp_path / "state")
    with start(settings):
        pass

    recovery = StateRecovery(settings)
    recovery.pending_path.parent.mkdir(parents=True, exist_ok=True)
    recovery.pending_path.write_text('{"operation":"RESET"}', encoding="utf-8")

    with pytest.raises(StateRecoveryError) as failure:
        recovery.reset()

    assert failure.value.code == "CORE_STATE_RECOVERY_PENDING"
    assert settings.state_root.joinpath("core.sqlite3").is_file()
    assert recovery.pending_path.is_file()


def test_corruption_is_quarantined_and_stops_the_recovery_write_path(tmp_path: Path) -> None:
    settings = local_settings(tmp_path / "state")
    with start(settings):
        pass

    quota_path = settings.state_root / "runtime" / "quota_policy.json"
    quota_path.write_text("{}", encoding="utf-8")

    recovery = StateRecovery(settings)
    with pytest.raises(StateRecoveryError) as failure:
        recovery.verify_current_state()

    assert failure.value.code == "CORE_STATE_CORRUPT"
    assert not settings.state_root.exists()
    quarantines = list(recovery.quarantine_root.iterdir())
    assert len(quarantines) == 1
    quarantined_state = quarantines[0] / "state"
    assert (quarantined_state / "runtime" / "quota_policy.json").read_text(
        encoding="utf-8"
    ) == "{}"
    assert (quarantines[0] / "quarantine-manifest.json").is_file()


@pytest.mark.parametrize("corrupt_relative_path", ("core.sqlite3", "artifacts/runs/analysis-run-corrupt/manifest.json"))
def test_database_or_referenced_artifact_corruption_is_quarantined(
    tmp_path: Path,
    corrupt_relative_path: str,
) -> None:
    settings = local_settings(tmp_path / "state")
    with start(settings):
        pass

    corrupt_path = settings.state_root / corrupt_relative_path
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    if corrupt_relative_path == "core.sqlite3":
        corrupt_path.write_bytes(b"not a sqlite database")
    else:
        corrupt_path.write_text("{}", encoding="utf-8")

    recovery = StateRecovery(settings)
    with pytest.raises(StateRecoveryError) as failure:
        recovery.verify_current_state()

    assert failure.value.code == "CORE_STATE_CORRUPT"
    assert failure.value.quarantine_id is not None
    assert not settings.state_root.exists()
    quarantined_state = (
        recovery.quarantine_root / str(failure.value.quarantine_id) / "state"
    )
    assert (quarantined_state / corrupt_relative_path).exists()


def test_live_app_does_not_expose_the_static_fallback_route(tmp_path: Path) -> None:
    settings = local_settings(tmp_path / "state")
    with start(settings) as client:
        response = client.get("/api/reference-fallback")

    assert response.status_code == 404
