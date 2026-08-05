from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings


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


def test_public_surface_applies_security_and_cache_headers(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok');", encoding="utf-8")
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=tmp_path / "state",
        public_origin="http://127.0.0.1:8000",
        spa_dist_dir=dist,
    )

    with TestClient(create_app(settings)) as client:
        api = client.get("/api/health")
        html = client.get("/")
        asset = client.get("/assets/app.js")

    expected_security_headers = {
        "content-security-policy": (
            "default-src 'self'; base-uri 'none'; connect-src 'self'; "
            "font-src 'self'; form-action 'none'; frame-ancestors 'none'; "
            "img-src 'self' data:; manifest-src 'none'; object-src 'none'; "
            "script-src 'self'; style-src 'self'; worker-src 'none'"
        ),
        "referrer-policy": "no-referrer",
        "permissions-policy": (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        ),
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "cross-origin-opener-policy": "same-origin",
        "cross-origin-resource-policy": "same-origin",
        "x-permitted-cross-domain-policies": "none",
    }
    for name, value in expected_security_headers.items():
        assert api.headers[name] == value
        assert html.headers[name] == value
        assert asset.headers[name] == value

    assert api.headers["cache-control"] == "no-store"
    assert html.headers["cache-control"] == "no-store"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_hosted_surface_adds_transport_security_header(tmp_path: Path) -> None:
    volume = tmp_path / "railway-volume"
    settings = Settings(
        profile=DeliveryProfile.HOSTED,
        state_root=volume / "core",
        railway_volume_path=volume,
        public_origin="https://demo.example.com",
        release_candidate_id="rc-test",
        build_manifest_id="build-test",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
