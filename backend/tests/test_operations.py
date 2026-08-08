from __future__ import annotations

import sys
import time
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.operations import OperationRunner
from backend.app.settings import DeliveryProfile, QuotaPolicy, Settings


def local_settings(
    state_root: Path,
    *,
    quotas: QuotaPolicy | None = None,
) -> Settings:
    return Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        quotas=quotas or QuotaPolicy(),
    )


def make_client(
    state_root: Path,
    *,
    quotas: QuotaPolicy | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            local_settings(state_root, quotas=quotas),
            start_operation_runner=False,
        )
    )


def admit(client: TestClient, key: str, *, operation_kind: str = "FRESH_ANALYSIS"):
    return client.post(
        "/api/operations",
        json={
            "idempotency_key": key,
            "operation_kind": operation_kind,
            "memory_required_bytes": 1024,
            "request": {"analysis_request_id": key},
        },
    )


def test_admission_is_durable_and_bounded_across_workspaces(tmp_path: Path) -> None:
    quotas = QuotaPolicy(
        max_running_operations=1,
        max_waiting_operations=2,
        max_outstanding_operations_per_workspace=1,
    )
    state_root = tmp_path / "state"
    client_a = make_client(state_root, quotas=quotas)
    client_b = make_client(state_root, quotas=quotas)
    client_c = make_client(state_root, quotas=quotas)
    client_d = make_client(state_root, quotas=quotas)
    with client_a, client_b, client_c, client_d:
        workspace_a = client_a.get("/api/workspace").json()["workspace_id"]
        workspace_b = client_b.get("/api/workspace").json()["workspace_id"]
        workspace_c = client_c.get("/api/workspace").json()["workspace_id"]
        workspace_d = client_d.get("/api/workspace").json()["workspace_id"]

        first = admit(client_a, "operation-key-a")
        same_request = admit(client_a, "operation-key-a")
        workspace_limit = admit(client_a, "operation-key-a-2")
        second = admit(client_b, "operation-key-b")
        third = admit(client_c, "operation-key-c")
        queue_limit = admit(client_d, "operation-key-d")

    assert first.status_code == 202
    assert first.json()["result"] == "CREATED"
    assert first.json()["operation"]["state"] == "QUEUED"
    assert first.json()["operation"]["operation_id"].startswith("operation-")
    assert same_request.status_code == 200
    assert same_request.json()["result"] == "IDEMPOTENT_REPLAY"
    assert same_request.json()["operation"]["operation_id"] == first.json()["operation"]["operation_id"]
    assert workspace_limit.status_code == 429
    assert workspace_limit.json()["code"] == "DEMO_WORKSPACE_OPERATION_LIMIT_REACHED"
    assert second.status_code == 202
    assert third.status_code == 202
    assert queue_limit.status_code == 429
    assert queue_limit.json()["code"] == "OPERATION_QUEUE_CAPACITY_REACHED"
    assert len({workspace_a, workspace_b, workspace_c, workspace_d}) == 4


def test_resource_admission_warns_on_disk_and_blocks_low_disk_or_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.app.operations.disk_free_bytes",
        lambda _: 700 * 1024 * 1024,
    )
    monkeypatch.setattr(
        "backend.app.operations.available_memory_bytes",
        lambda: 2 * 1024 * 1024 * 1024,
    )
    state_root = tmp_path / "warning-state"
    with make_client(state_root) as warning_client:
        warning_client.get("/api/workspace")
        warning = admit(warning_client, "warning-key")

    assert warning.status_code == 202
    assert warning.json()["operation"]["resource_warnings"] == ["DISK_SPACE_LOW"]

    monkeypatch.setattr(
        "backend.app.operations.disk_free_bytes",
        lambda _: 511 * 1024 * 1024,
    )
    with make_client(tmp_path / "blocked-disk-state") as blocked_disk_client:
        blocked_disk_client.get("/api/workspace")
        blocked_disk = admit(blocked_disk_client, "blocked-disk-key")
        read_only = blocked_disk_client.get("/api/workspace")

    assert blocked_disk.status_code == 507
    assert blocked_disk.json() == {
        "code": "OPERATION_DISK_SPACE_BLOCKED",
        "recovery_action": "RESTORE_CORE_STATE_AND_RETRY",
    }
    assert read_only.status_code == 200

    monkeypatch.setattr(
        "backend.app.operations.disk_free_bytes",
        lambda _: 2 * 1024 * 1024 * 1024,
    )
    monkeypatch.setattr(
        "backend.app.operations.available_memory_bytes",
        lambda: 1249,
    )
    with make_client(tmp_path / "blocked-memory-state") as blocked_memory_client:
        blocked_memory_client.get("/api/workspace")
        blocked_memory = admit(blocked_memory_client, "blocked-memory-key")

    assert blocked_memory.status_code == 503
    assert blocked_memory.json() == {
        "code": "OPERATION_MEMORY_HEADROOM_INSUFFICIENT",
        "recovery_action": "WAIT_FOR_MEMORY_AND_RETRY",
    }


def test_claim_is_transactional_and_preserves_global_queue_order(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client_a = make_client(state_root)
    client_b = make_client(state_root)
    with client_a, client_b:
        client_a.get("/api/workspace")
        client_b.get("/api/workspace")
        first = admit(client_a, "claim-key-a")
        second = admit(client_b, "claim-key-b")
        store = client_a.app.state.audit_store

        claimed = store.claim_next_operation()
        claimed_again = store.claim_next_operation()
        first_status = client_a.get(
            f"/api/operations/{first.json()['operation']['operation_id']}"
        )
        second_status = client_b.get(
            f"/api/operations/{second.json()['operation']['operation_id']}"
        )

    assert claimed is not None
    assert claimed.operation_id == first.json()["operation"]["operation_id"]
    assert claimed.state == "RUNNING"
    assert claimed_again is None
    assert first_status.json()["state"] == "RUNNING"
    assert second_status.json()["state"] == "QUEUED"
    assert second_status.json()["queue_position"] == 1


def test_cancel_quarantines_partial_work_and_retry_creates_new_operation(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"

    def slow_worker(record, temporary_root: Path) -> list[str]:
        script = (
            "from pathlib import Path; import sys, time; "
            "Path(sys.argv[1], 'partial.json').write_text('partial', encoding='utf-8'); "
            "time.sleep(30)"
        )
        return [sys.executable, "-c", script, str(temporary_root)]

    with make_client(state_root) as client:
        client.get("/api/workspace")
        created = admit(client, "cancel-key", operation_kind="BOUNDED_WORK")
        operation_id = created.json()["operation"]["operation_id"]
        runner = OperationRunner(
            client.app.state.audit_store,
            client.app.state.state_layout,
            worker_command_factory=slow_worker,
            poll_interval_seconds=0.01,
        )
        runner.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                state = client.get(f"/api/operations/{operation_id}").json()["state"]
                if state == "RUNNING":
                    break
                time.sleep(0.01)
            assert state == "RUNNING"

            cancelled = client.post(
                f"/api/operations/{operation_id}/cancel",
                json={"idempotency_key": "cancel-action-key"},
            )
            assert cancelled.status_code == 202

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                final = client.get(f"/api/operations/{operation_id}").json()
                if final["state"] == "CANCELLED":
                    break
                time.sleep(0.01)
            assert final["state"] == "CANCELLED"
        finally:
            runner.stop()

        quarantine_manifest = (
            state_root
            / "artifacts"
            / "quarantine"
            / operation_id
            / "quarantine-manifest.json"
        )
        assert quarantine_manifest.is_file()
        assert not (
            state_root / "artifacts" / "runs" / operation_id
        ).exists()

        retried = client.post(
            f"/api/operations/{operation_id}/retry",
            json={"idempotency_key": "retry-action-key"},
        )

    assert retried.status_code == 202
    assert retried.json()["result"] == "CREATED"
    retry_operation = retried.json()["operation"]
    assert retry_operation["operation_id"] != operation_id
    assert retry_operation["retry_of_operation_id"] == operation_id
    assert retry_operation["state"] == "QUEUED"


def test_restart_marks_running_work_interrupted_and_quarantines_partial_material(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    with make_client(state_root) as first_client:
        first_workspace = first_client.get("/api/workspace")
        capability = first_workspace.cookies.get("core_demo_workspace")
        created = admit(first_client, "restart-key", operation_kind="BOUNDED_WORK")
        operation_id = created.json()["operation"]["operation_id"]
        store = first_client.app.state.audit_store
        claimed = store.claim_next_operation()
        temporary_root = (
            first_client.app.state.state_layout.temporary_root / operation_id
        )
        temporary_root.mkdir(parents=True)
        (temporary_root / "partial.json").write_text("partial", encoding="utf-8")
        published_root = first_client.app.state.state_layout.run_root / operation_id
        published_root.mkdir(parents=True)
        (published_root / "published.json").write_text("partial", encoding="utf-8")
        assert claimed is not None and claimed.state == "RUNNING"

    with make_client(state_root) as restarted_client:
        assert capability is not None
        restarted_client.cookies.set("core_demo_workspace", capability)
        recovered = restarted_client.get(f"/api/operations/{operation_id}")

    assert recovered.status_code == 200
    assert recovered.json()["state"] == "INTERRUPTED"
    assert recovered.json()["failure_code"] == "RUN_EXECUTION_INTERRUPTED"
    assert recovered.json()["recovery_action"] == "EXPLICIT_RETRY_AS_NEW_OPERATION"
    quarantine_root = state_root / "artifacts" / "quarantine" / operation_id
    assert (quarantine_root / "quarantine-manifest.json").is_file()
    assert not (state_root / "artifacts" / "temporary" / operation_id).exists()
    assert not (state_root / "artifacts" / "runs" / operation_id).exists()
    assert (quarantine_root / "temporary" / "partial.json").is_file()
    assert (quarantine_root / "published" / "published.json").is_file()


def test_default_lifespan_starts_the_durable_runner(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with TestClient(create_app(local_settings(state_root))) as client:
        client.get("/api/workspace")
        created = admit(client, "default-runner-key", operation_kind="BOUNDED_WORK")
        operation_id = created.json()["operation"]["operation_id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            final = client.get(f"/api/operations/{operation_id}").json()
            if final["state"] == "SUCCEEDED":
                break
            time.sleep(0.01)

    assert final["state"] == "SUCCEEDED"


def test_runner_serializes_compute_and_sets_deterministic_thread_caps(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"

    def worker(record, temporary_root: Path) -> list[str]:
        script = (
            "from pathlib import Path; import json, os, sys, time; "
            "Path(sys.argv[1], 'thread-env.json').write_text(json.dumps({"
            "k: os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',"
            "'MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS',"
            "'BLIS_NUM_THREADS','PYTHONHASHSEED')}), encoding='utf-8'); "
            "time.sleep(0.05)"
        )
        return [sys.executable, "-c", script, str(temporary_root)]

    with make_client(state_root) as client_a, make_client(state_root) as client_b:
        client_a.get("/api/workspace")
        client_b.get("/api/workspace")
        first = admit(client_a, "runner-key-a", operation_kind="BOUNDED_WORK")
        second = admit(client_b, "runner-key-b", operation_kind="BOUNDED_WORK")
        first_id = first.json()["operation"]["operation_id"]
        second_id = second.json()["operation"]["operation_id"]
        runner = OperationRunner(
            client_a.app.state.audit_store,
            client_a.app.state.state_layout,
            worker_command_factory=worker,
            poll_interval_seconds=0.01,
        )
        runner.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                first_state = client_a.get(f"/api/operations/{first_id}").json()["state"]
                second_state = client_b.get(f"/api/operations/{second_id}").json()["state"]
                if first_state == "SUCCEEDED" and second_state == "SUCCEEDED":
                    break
                time.sleep(0.01)
        finally:
            runner.stop()

        first_response = client_a.get(f"/api/operations/{first_id}").json()
        second_response = client_b.get(f"/api/operations/{second_id}").json()

    assert first_response["state"] == "SUCCEEDED"
    assert second_response["state"] == "SUCCEEDED"
    assert first_response["thread_cap"] == 1
    assert second_response["thread_cap"] == 1
    assert first_response["timeout_seconds"] == 300
    for operation_id in (first_id, second_id):
        env = json.loads(
            (
                state_root
                / "artifacts"
                / "runs"
                / operation_id
                / "thread-env.json"
            ).read_text(encoding="utf-8")
        )
        assert set(env.values()) == {"1", "0"}
        assert env["PYTHONHASHSEED"] == "0"


def test_runner_hard_timeout_quarantines_without_publishing_partial_work(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    quotas = QuotaPolicy(compute_timeout_seconds=0.05)

    def timed_worker(record, temporary_root: Path) -> list[str]:
        script = (
            "from pathlib import Path; import sys, time; "
            "Path(sys.argv[1], 'partial.json').write_text('partial', encoding='utf-8'); "
            "time.sleep(2)"
        )
        return [sys.executable, "-c", script, str(temporary_root)]

    with make_client(state_root, quotas=quotas) as client:
        client.get("/api/workspace")
        created = admit(client, "timeout-key", operation_kind="BOUNDED_WORK")
        operation_id = created.json()["operation"]["operation_id"]
        runner = OperationRunner(
            client.app.state.audit_store,
            client.app.state.state_layout,
            worker_command_factory=timed_worker,
            poll_interval_seconds=0.01,
        )
        runner.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                response = client.get(f"/api/operations/{operation_id}").json()
                if response["state"] == "TIMED_OUT":
                    break
                time.sleep(0.01)
        finally:
            runner.stop()

    assert response["state"] == "TIMED_OUT"
    assert response["failure_code"] == "OPERATION_TIMEOUT"
    assert not (state_root / "artifacts" / "runs" / operation_id).exists()
    assert (
        state_root
        / "artifacts"
        / "quarantine"
        / operation_id
        / "quarantine-manifest.json"
    ).is_file()
