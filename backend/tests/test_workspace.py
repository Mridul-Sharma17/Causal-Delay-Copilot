from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, QuotaPolicy, Settings
from backend.app.errors import WorkspaceRequestError
from backend.app.audit import AuditStore
from backend.app.workspace import DEMO_WORKSPACE_COOKIE_NAME


def local_settings(
    state_root: Path,
    *,
    quotas: QuotaPolicy | None = None,
    release_candidate_id: str = "local-local_fallback",
) -> Settings:
    return Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        release_candidate_id=release_candidate_id,
        build_manifest_id="build-test",
        quotas=quotas or QuotaPolicy(),
    )


def hosted_settings(state_root: Path) -> Settings:
    volume_path = state_root.parent / "railway-volume"
    return Settings(
        profile=DeliveryProfile.HOSTED,
        state_root=volume_path / state_root.name,
        railway_volume_path=volume_path,
        public_origin="https://demo.example.com",
        release_candidate_id="rc-test",
        build_manifest_id="build-test",
    )


def audit_request(key: str) -> dict[str, str]:
    return {
        "idempotency_key": key,
        "occurrence_kind": "BOOT_HEALTH_CHECK",
        "outcome_code": "CORE_READY_GEMINI_DEGRADED",
    }


def test_bootstrap_issues_a_secure_opaque_256_bit_capability_without_echoing_it(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(hosted_settings(state_root))) as client:
        response = client.get("/api/workspace")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert "capability" not in response.json()
    cookie_header = response.headers["set-cookie"]
    assert f"{DEMO_WORKSPACE_COOKIE_NAME}=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Secure" in cookie_header
    assert "SameSite=lax" in cookie_header

    token = response.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
    assert token is not None
    padded = token + "=" * (-len(token) % 4)
    assert len(base64.urlsafe_b64decode(padded)) == 32

    database_path = state_root.parent / "railway-volume" / state_root.name / "core.sqlite3"
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT capability_digest FROM demo_workspaces"
        ).fetchall()
    assert rows == [(hashlib.sha256(token.encode("ascii")).hexdigest(),)]
    assert token.encode("ascii") not in database_path.read_bytes()


def test_workspace_owned_audit_rows_are_isolated_and_unknown_ids_do_not_reveal_existence(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "state" / "core.sqlite3"
    client_a = TestClient(create_app(local_settings(database_path.parent)))
    client_b = TestClient(create_app(local_settings(database_path.parent)))

    with client_a, client_b:
        assert client_a.get("/api/workspace").status_code == 200
        created_a = client_a.post("/api/audit/occurrences", json=audit_request("a-1"))
        assert client_b.get("/api/workspace").status_code == 200
        created_b = client_b.post("/api/audit/occurrences", json=audit_request("b-1"))

        assert created_a.status_code == 201
        assert created_b.status_code == 201
        occurrence_a = created_a.json()["occurrence_id"]
        occurrence_b = created_b.json()["occurrence_id"]

        listed_a = client_a.get("/api/audit/occurrences")
        listed_b = client_b.get("/api/audit/occurrences")
        cross_workspace = client_a.get(f"/api/audit/occurrences/{occurrence_b}")
        unknown = client_a.get("/api/audit/occurrences/not-a-real-occurrence")

    assert [item["occurrence_id"] for item in listed_a.json()["items"]] == [occurrence_a]
    assert [item["occurrence_id"] for item in listed_b.json()["items"]] == [occurrence_b]
    assert cross_workspace.status_code == unknown.status_code == 404
    assert cross_workspace.json() == unknown.json() == {
        "code": "DEMO_WORKSPACE_RESOURCE_UNAVAILABLE",
        "recovery_action": "CHECK_WORKSPACE_AND_RETRY",
    }


def test_workspace_lifetime_and_rate_quotas_are_enforced_without_counting_idempotent_replay(
    tmp_path: Path,
) -> None:
    quotas = QuotaPolicy(
        max_workspace_mutations=1,
        max_workspace_mutations_per_minute=10,
        max_global_mutations_per_minute=10,
    )
    with TestClient(create_app(local_settings(tmp_path / "state", quotas=quotas))) as client:
        first = client.post("/api/audit/occurrences", json=audit_request("one"))
        replay = client.post("/api/audit/occurrences", json=audit_request("one"))
        exhausted = client.post("/api/audit/occurrences", json=audit_request("two"))

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["result"] == "IDEMPOTENT_REPLAY"
    assert exhausted.status_code == 429
    assert exhausted.json() == {
        "code": "DEMO_WORKSPACE_MUTATION_LIMIT_REACHED",
        "recovery_action": "START_A_NEW_DEMO_WORKSPACE",
    }


def test_workspace_rate_limit_is_enforced_per_workspace(tmp_path: Path) -> None:
    quotas = QuotaPolicy(
        max_workspace_mutations_per_minute=1,
        max_global_mutations_per_minute=10,
    )
    with TestClient(create_app(local_settings(tmp_path / "state", quotas=quotas))) as client:
        first = client.post("/api/audit/occurrences", json=audit_request("one"))
        limited = client.post("/api/audit/occurrences", json=audit_request("two"))

    assert first.status_code == 201
    assert limited.status_code == 429
    assert limited.json() == {
        "code": "DEMO_WORKSPACE_RATE_LIMITED",
        "recovery_action": "WAIT_AND_RETRY",
    }


def test_global_rate_limit_covers_mutations_from_all_workspaces(tmp_path: Path) -> None:
    quotas = QuotaPolicy(
        max_workspace_mutations_per_minute=10,
        max_global_mutations_per_minute=1,
    )
    root = tmp_path / "state"
    client_a = TestClient(create_app(local_settings(root, quotas=quotas)))
    client_b = TestClient(create_app(local_settings(root, quotas=quotas)))

    with client_a, client_b:
        first = client_a.post("/api/audit/occurrences", json=audit_request("one"))
        second = client_b.post("/api/audit/occurrences", json=audit_request("two"))

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json() == {
        "code": "DEMO_WORKSPACE_RATE_LIMITED",
        "recovery_action": "WAIT_AND_RETRY",
    }


def test_workspace_capacity_counts_only_non_retired_workspaces(tmp_path: Path) -> None:
    quotas = QuotaPolicy(max_workspaces=1)
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root, quotas=quotas))) as first:
        assert first.get("/api/workspace").status_code == 200

    second = TestClient(create_app(local_settings(state_root, quotas=quotas)))
    with second:
        response = second.get("/api/workspace")

    assert response.status_code == 429
    assert response.json() == {
        "code": "DEMO_WORKSPACE_CAPACITY_EXCEEDED",
        "recovery_action": "TRY_AGAIN_LATER",
    }


def test_new_workspace_bootstrap_retires_stale_workspaces_before_capacity_check(
    tmp_path: Path,
) -> None:
    quotas = QuotaPolicy(max_workspaces=1)
    state_root = tmp_path / "state"
    first = TestClient(create_app(local_settings(state_root, quotas=quotas)))
    with first:
        created = first.get("/api/workspace")
        workspace_id = created.json()["workspace_id"]
        first.app.state.audit_store.touch_workspace(
            workspace_id,
            now=datetime.now(timezone.utc) - timedelta(days=8),
        )

    second = TestClient(create_app(local_settings(state_root, quotas=quotas)))
    with second:
        response = second.get("/api/workspace")

    assert response.status_code == 200
    assert response.json()["workspace_id"] != workspace_id


def test_inactive_workspace_is_retired_and_cannot_be_recovered(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root))) as client:
        created = client.get("/api/workspace")
        token = created.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
        assert token is not None
        store = client.app.state.audit_store
        workspace_id = created.json()["workspace_id"]
        old = datetime.now(timezone.utc) - timedelta(days=8)
        store.touch_workspace(workspace_id, now=old)

        client.cookies.set(DEMO_WORKSPACE_COOKIE_NAME, token)
        retired = client.get("/api/workspace")

    assert retired.status_code == 403
    assert retired.json() == {
        "code": "DEMO_WORKSPACE_UNAVAILABLE",
        "recovery_action": "START_A_NEW_DEMO_WORKSPACE",
    }


def test_terminal_fresh_bundle_quota_is_idempotent_and_workspace_owned(
    tmp_path: Path,
) -> None:
    quotas = QuotaPolicy(
        max_workspace_terminal_fresh_bundles=1,
        max_workspace_mutations=10,
        max_workspace_mutations_per_minute=10,
        max_global_mutations_per_minute=10,
    )
    with TestClient(create_app(local_settings(tmp_path / "state", quotas=quotas))) as client:
        workspace = client.get("/api/workspace").json()
        store = client.app.state.audit_store
        operation = store.create_workspace_operation(
            workspace["workspace_id"],
            operation_id="fresh-operation-1",
            operation_kind="FRESH_RUN",
            status="TERMINAL",
            idempotency_key="fresh-operation-key-1",
        )
        first = store.record_terminal_fresh_bundle(
            workspace["workspace_id"],
            result_id="fresh-result-1",
            operation_id="fresh-operation-1",
            result_ref="bundle-1",
            idempotency_key="fresh-1",
        )
        replay = store.record_terminal_fresh_bundle(
            workspace["workspace_id"],
            result_id="fresh-result-1",
            operation_id="fresh-operation-1",
            result_ref="bundle-1",
            idempotency_key="fresh-1",
        )
        with pytest.raises(WorkspaceRequestError) as failure:
            store.record_terminal_fresh_bundle(
                workspace["workspace_id"],
                result_id="fresh-result-2",
                operation_id="fresh-operation-1",
                result_ref="bundle-2",
                idempotency_key="fresh-2",
            )

    assert first.replayed is False
    assert operation.replayed is False
    assert replay.replayed is True
    assert failure.value.code.value == "DEMO_WORKSPACE_FRESH_BUNDLE_LIMIT_REACHED"


def test_workspace_capability_is_release_bound_without_recovery(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root))) as client:
        response = client.get("/api/workspace")
        token = response.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
        database_path = state_root / "core.sqlite3"
    assert token is not None

    mismatched = AuditStore(
        database_path,
        release_candidate_id="different-release",
        quotas=QuotaPolicy(),
    )
    mismatched.initialize()
    try:
        with pytest.raises(WorkspaceRequestError) as failure:
            mismatched.resolve_workspace(token)
    finally:
        mismatched.close()

    assert failure.value.code.value == "DEMO_WORKSPACE_UNAVAILABLE"


def test_validated_references_are_global_read_only_state(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root))) as client:
        client.get("/api/workspace")

    with sqlite3.connect(state_root / "core.sqlite3") as connection:
        connection.execute(
            """
            INSERT INTO validated_references (
                reference_id,
                bundle_ref,
                validation_attestation_ref,
                release_candidate_id
            ) VALUES (?, ?, ?, ?)
            """,
            ("reference-1", "bundle-1", "attestation-1", "local-local_fallback"),
        )

    client_a = TestClient(create_app(local_settings(state_root)))
    client_b = TestClient(create_app(local_settings(state_root)))
    with client_a, client_b:
        listed_a = client_a.get("/api/validated-references")
        listed_b = client_b.get("/api/validated-references")
        detail = client_a.get("/api/validated-references/reference-1")

    expected = {
        "reference_id": "reference-1",
        "bundle_ref": "bundle-1",
        "validation_attestation_ref": "attestation-1",
        "release_candidate_id": "local-local_fallback",
    }
    assert listed_a.json() == {"items": [expected]}
    assert listed_b.json() == {"items": [expected]}
    assert detail.json() == expected


def test_copied_selection_is_workspace_owned_and_idempotent(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root))) as bootstrap:
        bootstrap.get("/api/workspace")
    with sqlite3.connect(state_root / "core.sqlite3") as connection:
        connection.execute(
            """
            INSERT INTO validated_references (
                reference_id,
                bundle_ref,
                validation_attestation_ref,
                release_candidate_id
            ) VALUES (?, ?, ?, ?)
            """,
            ("reference-1", "bundle-1", "attestation-1", "local-local_fallback"),
        )

    client_a = TestClient(create_app(local_settings(state_root)))
    client_b = TestClient(create_app(local_settings(state_root)))
    request = {
        "selection_id": "selection-1",
        "reference_id": "reference-1",
        "idempotency_key": "selection-key-1",
    }
    with client_a, client_b:
        created = client_a.post("/api/workspace/selections", json=request)
        replay = client_a.post("/api/workspace/selections", json=request)
        cross_workspace = client_b.get("/api/workspace/selections/selection-1")
        own = client_a.get("/api/workspace/selections/selection-1")

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["result"] == "IDEMPOTENT_REPLAY"
    assert cross_workspace.status_code == 404
    assert cross_workspace.json() == {
        "code": "DEMO_WORKSPACE_RESOURCE_UNAVAILABLE",
        "recovery_action": "CHECK_WORKSPACE_AND_RETRY",
    }
    assert own.status_code == 200
    assert own.json()["reference_id"] == "reference-1"


def test_workspace_operation_and_fresh_result_are_partitioned_and_quota_counted(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    client_a = TestClient(create_app(local_settings(root)))
    client_b = TestClient(create_app(local_settings(root)))
    with client_a, client_b:
        workspace = client_a.get("/api/workspace").json()
        store = client_a.app.state.audit_store
        operation = store.create_workspace_operation(
            workspace["workspace_id"],
            operation_id="operation-1",
            operation_kind="FRESH_RUN",
            status="TERMINAL",
            idempotency_key="operation-key-1",
        )
        result = store.create_workspace_result(
            workspace["workspace_id"],
            result_id="result-1",
            operation_id="operation-1",
            result_ref="bundle-1",
            idempotency_key="result-key-1",
        )
        own = client_a.get("/api/workspace/results/result-1")
        cross_workspace = client_b.get("/api/workspace/results/result-1")

    assert operation.replayed is False
    assert result.replayed is False
    assert own.status_code == 200
    assert own.json()["operation_id"] == "operation-1"
    assert cross_workspace.status_code == 404
    assert cross_workspace.json() == {
        "code": "DEMO_WORKSPACE_RESOURCE_UNAVAILABLE",
        "recovery_action": "CHECK_WORKSPACE_AND_RETRY",
    }
