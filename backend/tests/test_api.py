from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


def make_client(database_path: Path, *, gemini_enabled: bool = False) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                database_path=database_path,
                gemini_enabled=gemini_enabled,
            )
        )
    )


def test_health_distinguishes_liveness_readiness_and_gemini_degradation(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "causal-delay-copilot"
    assert body["liveness"] == {"state": "live", "code": "CORE_LIVE"}
    assert body["readiness"] == {
        "state": "degraded",
        "code": "CORE_READY_GEMINI_DEGRADED",
    }
    assert body["degraded_capabilities"] == ["GEMINI_DRAFTING"]
    assert "database_path" not in body
    assert "stack" not in body


def test_audit_occurrence_assigns_global_sequence_and_replays_exact_retry(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "core.sqlite3"
    request = {
        "idempotency_key": "core-boot-test-1",
        "occurrence_kind": "BOOT_HEALTH_CHECK",
        "outcome_code": "CORE_READY_GEMINI_DEGRADED",
    }

    with make_client(database_path) as client:
        first = client.post("/api/audit/occurrences", json=request)
        retry = client.post("/api/audit/occurrences", json=request)
        second = client.post(
            "/api/audit/occurrences",
            json={**request, "idempotency_key": "core-boot-test-2"},
        )

    assert first.status_code == 201
    assert first.json()["result"] == "CREATED"
    assert first.json()["event_seq"] == 1
    assert retry.status_code == 200
    assert retry.json()["result"] == "IDEMPOTENT_REPLAY"
    assert retry.json()["occurrence_id"] == first.json()["occurrence_id"]
    assert retry.json()["event_seq"] == first.json()["event_seq"]
    assert second.status_code == 201
    assert second.json()["event_seq"] == 2


def test_audit_sequence_continues_after_reopening_the_store(tmp_path: Path) -> None:
    database_path = tmp_path / "core.sqlite3"
    base_request = {
        "occurrence_kind": "BOOT_HEALTH_CHECK",
        "outcome_code": "CORE_READY_GEMINI_DEGRADED",
    }

    with make_client(database_path) as client:
        first = client.post(
            "/api/audit/occurrences",
            json={**base_request, "idempotency_key": "first-process"},
        )

    with make_client(database_path) as client:
        second = client.post(
            "/api/audit/occurrences",
            json={**base_request, "idempotency_key": "second-process"},
        )

    assert first.json()["event_seq"] == 1
    assert second.json()["event_seq"] == 2


def test_conflicting_content_under_one_idempotency_key_is_safe_integrity_error(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "core.sqlite3"
    request = {
        "idempotency_key": "conflicting-key",
        "occurrence_kind": "BOOT_HEALTH_CHECK",
        "outcome_code": "CORE_READY_GEMINI_DEGRADED",
    }

    with make_client(database_path) as client:
        created = client.post("/api/audit/occurrences", json=request)
        conflict = client.post(
            "/api/audit/occurrences",
            json={**request, "outcome_code": "CORE_READY"},
        )

    assert created.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {
        "code": "AUDIT_IDEMPOTENCY_CONFLICT",
        "recovery_action": "USE_NEW_IDEMPOTENCY_KEY",
    }


def test_invalid_request_returns_registered_redacted_error(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.post(
            "/api/audit/occurrences",
            json={"idempotency_key": "bad", "outcome_code": "unsafe raw value"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "REQUEST_SCHEMA_INVALID",
        "recovery_action": "CORRECT_REQUEST_AND_RETRY",
    }
