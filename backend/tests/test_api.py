from __future__ import annotations

from copy import deepcopy
import json
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


def test_hero_import_publishes_immutable_lineage_and_audit_bound_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "core.sqlite3"
    request = {
        "idempotency_key": "hero-import-v1",
        "dataset_key": "semi-synthetic-hero",
        "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
    }

    with make_client(database_path) as client:
        first = client.post("/api/ingestion-runs", json=request)
        retry = client.post("/api/ingestion-runs", json=request)
        dataset_version_id = first.json()["dataset_version_id"]
        versions = client.get("/api/datasets")
        lineage = client.get(f"/api/datasets/{dataset_version_id}/lineage")

    assert first.status_code == 201
    assert first.json()["result"] == "CREATED"
    assert first.json()["status"] == "SUCCEEDED"
    assert dataset_version_id.startswith("sha256:")
    assert retry.status_code == 200
    assert retry.json()["result"] == "IDEMPOTENT_REPLAY"
    assert retry.json()["ingestion_run_id"] == first.json()["ingestion_run_id"]
    assert retry.json()["dataset_version_id"] == dataset_version_id

    assert versions.status_code == 200
    assert [item["dataset_version_id"] for item in versions.json()["items"]] == [
        dataset_version_id
    ]

    assert lineage.status_code == 200
    body = lineage.json()
    assert body["ingestion_run"]["status"] == "SUCCEEDED"
    assert body["dataset_version"]["source_kind"] == "semi_synthetic"
    assert body["dataset_version"]["intended_role"] == "semi_synthetic_hero"
    assert body["dataset_version"]["mapping_manifest_id"] == (
        "semi-synthetic-hero.mapping.v1"
    )
    assert body["audit_binding"]["dataset_version_id"] == dataset_version_id
    assert body["audit_binding"]["event_seq"] > 0
    assert body["audit_binding"]["snapshot_id"].startswith("sha256:")
    assert len(body["order_lines"]) == 3
    assert len(body["order_line_events"]) >= len(body["order_lines"])
    assert len(body["source_observations"]) >= len(body["order_lines"])
    assert body["mapping_manifest"]["field_mappings"]["quantity"]["source_path"] == (
        "fields.quantity"
    )

    states = {
        field["state"]
        for order_line in body["order_lines"]
        for field in order_line["fields"].values()
    }
    assert {"present", "missing", "not_applicable", "invalid", "unresolved"} <= states

    event = next(
        event for event in body["order_line_events"] if event["kind"] == "committed"
    )
    assert {"occurred_at", "known_at", "available_at"} <= set(event["clocks"])
    assert event["clocks"]["occurred_at"]["state"] == "present"
    assert event["clocks"]["occurred_at"]["value"]["source_value"] == (
        "2026-01-08T11:00:00+05:30"
    )
    assert event["clocks"]["occurred_at"]["value"]["normalized_value"] == (
        "2026-01-08T05:30:00+00:00"
    )
    assert event["clocks"]["known_at"]["state"] in {"present", "unresolved"}
    assert event["clocks"]["available_at"]["state"] in {"present", "unresolved"}

    observations_by_target = {
        observation["target_record_id"]
        for observation in body["source_observations"]
    }
    assert observations_by_target >= {
        order_line["order_line_id"] for order_line in body["order_lines"]
    }
    assert {finding["code"] for finding in body["validation_findings"]} >= {
        "SOURCE_DUPLICATE_DEDUPED",
        "TIMEZONE_UNKNOWN",
        "VALUE_OUT_OF_RANGE",
    }
    invalid_quantity = next(
        order_line["fields"]["quantity"]
        for order_line in body["order_lines"]
        if order_line["fields"]["quantity"]["state"] == "invalid"
    )
    assert invalid_quantity["source_value"] == "-3"
    assert all("source-value" not in str(observation) for observation in body["source_observations"])


def test_conflicting_identity_content_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app import ingestion

    source = json.loads(ingestion.HERO_SOURCE_FILE.read_text(encoding="utf-8"))
    mapping = json.loads(ingestion.HERO_MAPPING_FILE.read_text(encoding="utf-8"))
    first = deepcopy(source["rows"][0])
    conflicting = deepcopy(first)
    conflicting["fields"]["material_class"] = {
        "state": "present",
        "value": "conflicting-material",
    }
    source["rows"] = [first, conflicting]
    monkeypatch.setattr(
        ingestion,
        "_read_bundle",
        lambda: (source, mapping, "sha256:test-source", "sha256:test-mapping"),
    )

    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.post(
            "/api/ingestion-runs",
            json={
                "idempotency_key": "hero-conflict-v1",
                "dataset_key": "semi-synthetic-hero",
                "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "INGESTION_REJECTED",
        "recovery_action": "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
    }


def test_identical_hero_inputs_reuse_the_first_dataset_publication(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "core.sqlite3"
    base_request = {
        "dataset_key": "semi-synthetic-hero",
        "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
    }

    with make_client(database_path) as client:
        first = client.post(
            "/api/ingestion-runs",
            json={**base_request, "idempotency_key": "hero-reingest-1"},
        )
        second = client.post(
            "/api/ingestion-runs",
            json={**base_request, "idempotency_key": "hero-reingest-2"},
        )
        versions = client.get("/api/datasets")
        lineage = client.get(
            f"/api/datasets/{first.json()['dataset_version_id']}/lineage"
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["ingestion_run_id"] != first.json()["ingestion_run_id"]
    assert second.json()["dataset_version_id"] == first.json()["dataset_version_id"]
    assert len(versions.json()["items"]) == 1
    assert lineage.json()["dataset_version"]["first_published_by_run_id"] == (
        first.json()["ingestion_run_id"]
    )
