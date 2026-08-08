from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.canonical import normalise_temporal
from backend.app.contracts import RiskSignalRequest
from backend.app.main import create_app
from backend.app.risk import (
    resolve_commitment_cutoff,
    resolve_duration_basis,
    resolve_field_as_of,
    resolve_frozen_promise,
)
from backend.app.settings import Settings


def make_client(database_path: Path) -> TestClient:
    return TestClient(create_app(Settings(database_path=database_path)))


def import_hero(client: TestClient) -> str:
    response = client.post(
        "/api/ingestion-runs",
        json={
            "idempotency_key": "risk-signal-hero-import",
            "dataset_key": "semi-synthetic-hero",
            "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
        },
    )
    assert response.status_code == 201
    return str(response.json()["dataset_version_id"])


def get_signal(
    client: TestClient,
    dataset_version_id: str,
    index: int = 0,
    fixture_id: str | None = None,
) -> dict:
    response = client.get(
        "/api/risk-signals",
        params={"dataset_version_id": dataset_version_id},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    if fixture_id is None:
        fixture_id = (
            "hero-reactive-risk-v1"
            if index == 0
            else "hero-reactive-risk-target-mismatch-v1"
            if index == 1
            else None
        )
    selected_fixture_id = fixture_id or items[index]["fixture_id"]
    fixture_file = Path("backend/app/data/risk_signal_fixtures.json")
    fixtures = json.loads(fixture_file.read_text(encoding="utf-8"))["items"]
    signal = next(
        item["signal"]
        for item in fixtures
        if item["fixture_id"] == selected_fixture_id
    )
    assert signal["scored_dataset_version_ref"] == dataset_version_id
    return RiskSignalRequest.model_validate(signal).model_dump(mode="json")


def self_attest_untrusted_hash(signal: dict) -> None:
    payload = json.loads(json.dumps(signal))
    payload.pop("trigger_mode", None)
    payload["source"].pop("source_payload_sha256", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    signal["source"]["source_payload_sha256"] = (
        f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    )


def test_reactive_signal_creates_one_immutable_request_and_replays_exactly(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        public_fixtures = client.get(
            "/api/risk-signals",
            params={"dataset_version_id": dataset_version_id},
        ).json()["items"]
        assert "protected_source_locator" not in json.dumps(public_fixtures)
        signal = get_signal(client, dataset_version_id)

        created = client.post("/api/investigations/reactive", json=signal)
        replay = client.post("/api/investigations/reactive", json=signal)

        assert created.status_code == 201
        assert replay.status_code == 200
        assert created.json()["result"] == "CREATED"
        assert replay.json()["result"] == "IDEMPOTENT_REPLAY"

        attempt = created.json()["attempt"]
        request = attempt["investigation_request"]
        projection = request["causal_engine_input"]
        assert attempt["status"] == "accepted"
        assert attempt["primary_code"] == "RISK_SIGNAL_ACCEPTED"
        assert request["trigger_mode"] == "reactive"
        assert request["subject"]["order_line_id"] != signal["source_order_line_ref"]["key"]
        assert request["decision_cutoff_source"] == "canonical_commitment"
        assert request["observation_cutoff"]["value"]["normalized_value"] == (
            "2026-01-10T03:35:00+00:00"
        )
        assert projection["observation_cutoff"]["value"]["normalized_value"] == (
            "2026-01-10T03:35:00+00:00"
        )
        assert "prediction_metadata" not in projection
        assert "score_value" not in projection
        assert "alert_threshold" not in projection
        assert "flagged" not in projection
        assert request["prediction_metadata"]["value"]["score_value"] == 0.78
        assert replay.json()["attempt"]["investigation_request"][
            "investigation_request_id"
        ] == request["investigation_request_id"]
        assert projection["canonical_slippage_duration_basis"] == "CALENDAR_DAY"
        assert projection["estimator_window_ref"]["selector_version"] == (
            "estimator-window.v1"
        )
        assert projection["history_lookback_ref"]["selector_version"] == (
            "history-lookback.v1"
        )
        assert projection["historical_population_digest"].startswith("sha256:")
        exposure = projection["supplier_load_exposure"]
        assert exposure["trigger_mode"] == "reactive"
        assert exposure["cutoff_source"] == "canonical_commitment"
        assert exposure["load_snapshot"]["state"] == "present"
        assert exposure["primary"]["state"] == "ineligible"
        assert exposure["primary"]["eligibility_codes"] == [
            "SUPPLIER_HISTORY_INSUFFICIENT"
        ]

        lineage_response = client.get(f"/api/datasets/{dataset_version_id}/lineage")
        assert lineage_response.status_code == 200
        lineage = lineage_response.json()
        future_event_ids = {
            str(event["event_id"])
            for event in lineage["order_line_events"]
            if event["kind"] in {"promise_revised", "milestone_reached"}
        }
        future_observation_ids = {
            str(observation["source_observation_id"])
            for observation in lineage["source_observations"]
            if observation["target_record_id"] in future_event_ids
        }
        assert not future_observation_ids.intersection(
            projection["analytical_fact_lineage_refs"]
        )

        audit = client.get("/api/audit/occurrences")
        assert audit.status_code == 200
        assert [item["occurrence_kind"] for item in audit.json()["items"]] == [
            "REACTIVE_INGRESS",
            "REACTIVE_INGRESS",
            "LINEAGE_SNAPSHOT_VIEW",
        ]
        assert audit.json()["items"][1]["outcome_code"] == "RISK_SIGNAL_ACCEPTED"


def test_replay_key_does_not_bypass_mode_validation(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(client, dataset_version_id)
        assert client.post("/api/investigations/reactive", json=signal).status_code == 201

        signal["trigger_mode"] = "proactive"
        response = client.post("/api/investigations/reactive", json=signal)

        assert response.status_code == 201
        assert response.json()["result"] == "CREATED"
        assert response.json()["attempt"]["primary_code"] == "RISK_SIGNAL_MODE_MISMATCH"


def test_prediction_metadata_mutation_keeps_causal_projection_identical(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        baseline = get_signal(client, dataset_version_id)
        mutated = get_signal(
            client,
            dataset_version_id,
            fixture_id="hero-reactive-risk-firewall-variant-v1",
        )

        baseline_response = client.post(
            "/api/investigations/reactive",
            json=baseline,
        )
        mutated_response = client.post(
            "/api/investigations/reactive",
            json=mutated,
        )

        assert baseline_response.status_code == 201
        assert mutated_response.status_code == 201
        baseline_request = baseline_response.json()["attempt"][
            "investigation_request"
        ]
        mutated_request = mutated_response.json()["attempt"][
            "investigation_request"
        ]
        assert baseline_request is not None
        assert mutated_request is not None
        assert baseline_request["causal_engine_input"] == mutated_request[
            "causal_engine_input"
        ]
        assert baseline_request["causal_input_digest"] == mutated_request[
            "causal_input_digest"
        ]
        assert baseline_request["prediction_metadata"] != mutated_request[
            "prediction_metadata"
        ]
        metadata = mutated_request["prediction_metadata"]["value"]
        assert metadata["score_value"] == 0.61
        assert metadata["prediction_explanation_ref"]["state"] == "present"
        assert metadata["prediction_calibration_ref"]["state"] == "present"
        assert metadata["prediction_ranking_ref"]["state"] == "present"
        assert metadata["prediction_delivery_metadata"]["state"] == "present"


def test_non_finite_score_is_a_typed_failure_not_a_server_error(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(client, dataset_version_id)
        signal["score_value"] = float("nan")

        response = client.post(
            "/api/investigations/reactive",
            content=json.dumps(signal, allow_nan=True).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 201
        assert response.json()["attempt"]["status"] == "rejected"
        assert response.json()["attempt"]["primary_code"] in {
            "RISK_SIGNAL_INTEGRITY_FAILED",
            "RISK_SIGNAL_SCORE_UNUSABLE",
        }


def test_target_mismatch_is_rejected_and_audited_without_a_request(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(client, dataset_version_id, index=1)

        response = client.post("/api/investigations/reactive", json=signal)

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "rejected"
        assert attempt["primary_code"] == "RISK_SIGNAL_TARGET_MISMATCH"
        assert attempt["investigation_request"] is None
        assert attempt["recovery_action"] == "USE_CONFIGURED_SUPPLIER_MILESTONE_TARGET"
        audit = client.get("/api/audit/occurrences").json()["items"]
        assert len(audit) == 1
        assert audit[0]["outcome_code"] == "RISK_SIGNAL_TARGET_MISMATCH"


def test_malformed_reactive_body_is_sanitized_and_audited(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.post(
            "/api/investigations/reactive",
            json={"unexpected": True},
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
            "recovery_action": "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
        }
        audit = client.get("/api/audit/occurrences").json()["items"]
        assert len(audit) == 1
        assert audit[0]["outcome_code"] == "RISK_SIGNAL_SCHEMA_UNSUPPORTED"


def test_oversized_reactive_body_is_bounded_and_audited_once(tmp_path: Path) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        response = client.post(
            "/api/investigations/reactive",
            content=b"x" * (64 * 1024 + 1),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 413
        assert response.json() == {
            "code": "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
            "recovery_action": "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
        }
        audit = client.get("/api/audit/occurrences").json()["items"]
        assert len(audit) == 1
        assert audit[0]["outcome_code"] == "RISK_SIGNAL_SCHEMA_UNSUPPORTED"


def test_chunked_oversized_reactive_body_is_bounded_and_audited_once(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        def body_chunks():
            yield b"x" * (64 * 1024)
            yield b"y"

        response = client.post(
            "/api/investigations/reactive",
            content=body_chunks(),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 413
        assert response.json() == {
            "code": "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
            "recovery_action": "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
        }
        audit = client.get("/api/audit/occurrences").json()["items"]
        assert len(audit) == 1
        assert audit[0]["outcome_code"] == "RISK_SIGNAL_SCHEMA_UNSUPPORTED"


def test_temporal_cutoff_helpers_fail_closed_on_invalid_chronology() -> None:
    commitment = {
        "kind": "committed",
        "event_id": "commitment-1",
        "clocks": {
            "occurred_at": {
                "state": "present",
                "value": {
                    "value": "2026-01-05T09:30:00+05:30",
                    "kind": "instant",
                    "precision": "minute",
                    "timezone_status": "known",
                    "source_timezone": "Asia/Kolkata",
                },
            },
            "known_at": {
                "state": "present",
                "value": {
                    "value": "2026-01-05T09:31:00+05:30",
                    "kind": "instant",
                    "precision": "minute",
                    "timezone_status": "known",
                    "source_timezone": "Asia/Kolkata",
                },
            },
        },
    }
    assert resolve_commitment_cutoff([commitment]) == (
        None,
        "COMMITMENT_CUTOFF_UNUSABLE",
    )

    cutoff = normalise_temporal(
        {
            "value": "2026-01-05T09:30:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        }
    )
    promise = {
        "kind": "promise_recorded",
        "event_id": "promise-1",
        "milestone_kind": {"state": "present", "value": "supplier_handoff"},
        "clocks": {
            "occurred_at": cutoff.field,
            "known_at": cutoff.field,
        },
        "promised_for": {
            "state": "present",
            "value": {
                "value": "2026-01-04",
                "kind": "date",
                "precision": "date",
                "timezone_status": "not_applicable",
                "source_timezone": None,
            },
        },
        "revises_promise_event_id": {"state": "not_applicable"},
    }
    assert resolve_frozen_promise(
        [promise],
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff,
    ).code == "FROZEN_PROMISE_TEMPORALLY_INVALID"

    later_correction = deepcopy(promise)
    later_correction["event_id"] = "promise-2"
    later_correction["clocks"]["occurred_at"]["value"][
        "value"
    ] = "2026-01-06T09:00:00+05:30"
    later_correction["clocks"]["known_at"]["value"][
        "value"
    ] = "2026-01-06T09:01:00+05:30"
    later_correction["promised_for"]["value"]["value"] = "2026-02-16"
    later_correction["supersedes_event_id"] = {
        "state": "present",
        "value": "promise-1",
    }
    assert resolve_frozen_promise(
        [promise, later_correction],
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff,
    ).code == "FROZEN_PROMISE_CONFLICT"


def test_commitment_correction_resolves_one_head_and_rejects_invalid_graphs() -> None:
    commitment_clock = {
        "state": "present",
        "value": {
            "value": "2026-01-05T09:30:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        },
    }
    commitment = {
        "kind": "committed",
        "event_id": "commitment-1",
        "order_line_id": "line-1",
        "clocks": {
            "occurred_at": commitment_clock,
            "known_at": deepcopy(commitment_clock),
        },
    }
    commitment["clocks"]["known_at"]["value"][
        "value"
    ] = "2026-01-05T09:29:00+05:30"
    corrected = deepcopy(commitment)
    corrected["event_id"] = "commitment-2"
    corrected["clocks"]["occurred_at"]["value"][
        "value"
    ] = "2026-01-05T09:35:00+05:30"
    corrected["clocks"]["known_at"]["value"][
        "value"
    ] = "2026-01-05T09:34:00+05:30"
    corrected["supersedes_event_id"] = {
        "state": "present",
        "value": "commitment-1",
    }
    resolved, error = resolve_commitment_cutoff([commitment, corrected])
    assert error is None
    assert resolved is corrected

    conflicting = deepcopy(commitment)
    conflicting["event_id"] = "commitment-3"
    assert resolve_commitment_cutoff([commitment, conflicting]) == (
        None,
        "COMMITMENT_CUTOFF_UNUSABLE",
    )

    cyclic = deepcopy(corrected)
    cyclic["supersedes_event_id"] = {
        "state": "present",
        "value": "commitment-2",
    }
    assert resolve_commitment_cutoff([commitment, cyclic]) == (
        None,
        "COMMITMENT_CUTOFF_UNUSABLE",
    )


def test_duration_basis_requires_releasable_union_with_one_basis() -> None:
    configuration = {
        "temporal_eligibility_release_ref": "release.v1",
        "released_s8_rows": [
            {
                "release_ref": "release.v1",
                "release_state": "releasable",
                "row_identity": "row-1",
                "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
            },
            {
                "release_ref": "release.v1",
                "release_state": "releasable",
                "row_identity": "row-2",
                "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
            },
        ],
    }
    assert resolve_duration_basis(configuration)["basis"] == "CALENDAR_DAY"

    mixed = deepcopy(configuration)
    mixed["released_s8_rows"].append(
        {
            "release_ref": "release.v1",
            "release_state": "releasable",
            "row_identity": "row-3",
            "supplier_milestone_slippage_duration_basis": "ELAPSED_86400_SECOND_DAY",
        }
    )
    assert resolve_duration_basis(mixed)["basis"] is None
    assert resolve_duration_basis(
        {
            "temporal_eligibility_release_ref": "release.v1",
            "released_s8_rows": [],
        }
    )["basis"] is None


def test_as_of_field_resolution_abstains_when_final_value_has_late_lineage() -> None:
    cutoff = normalise_temporal(
        {
            "value": "2026-01-05T09:30:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        }
    )
    before = {
        "target_record_id": "line-1",
        "target_field_path": "fields.material_class",
        "known_at": {
            "state": "present",
            "value": {
                "value": "2026-01-05T09:29:00+05:30",
                "kind": "instant",
                "precision": "minute",
                "timezone_status": "known",
                "source_timezone": "Asia/Kolkata",
            },
        },
        "source_value_fingerprint": {"state": "present", "value": "old"},
    }
    after = deepcopy(before)
    after["known_at"]["value"]["value"] = "2026-01-05T09:31:00+05:30"
    after["source_value_fingerprint"] = {"state": "present", "value": "new"}
    assert resolve_field_as_of(
        {"source_observations": [before, after]},
        order_line_id="line-1",
        field_path="fields.material_class",
        canonical_value={"state": "present", "value": "new"},
        cutoff=cutoff,
    ) == {"state": "unresolved"}


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ("hash", "RISK_SIGNAL_INTEGRITY_FAILED"),
        ("clock", "RISK_SIGNAL_CLOCK_UNUSABLE"),
        ("mode", "RISK_SIGNAL_MODE_MISMATCH"),
        ("dataset", "RISK_SIGNAL_INTEGRITY_FAILED"),
        ("context", "RISK_SIGNAL_CONTEXT_CONFLICT"),
    ],
)
def test_reactive_failure_codes_are_registered_and_sanitized(
    tmp_path: Path,
    change: str,
    expected_code: str,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(client, dataset_version_id)
        if change == "hash":
            signal["score_value"] = 0.79
            self_attest_untrusted_hash(signal)
        elif change == "clock":
            signal = get_signal(
                client,
                dataset_version_id,
                fixture_id="hero-reactive-risk-clock-invalid-v1",
            )
        elif change == "mode":
            signal["trigger_mode"] = "proactive"
        elif change == "dataset":
            signal["scored_dataset_version_ref"] = "sha256:missing"
        elif change == "context":
            signal = get_signal(
                client,
                dataset_version_id,
                fixture_id="hero-reactive-risk-context-conflict-v1",
            )

        response = client.post("/api/investigations/reactive", json=signal)

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "rejected"
        assert attempt["primary_code"] == expected_code
        assert attempt["investigation_request"] is None
        assert "raw" not in json.dumps(attempt).lower()
        assert "score_value" not in json.dumps(attempt["findings"])


def test_conflicting_source_revision_has_revision_precedence_over_subject_checks(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        first = get_signal(client, dataset_version_id)
        assert client.post("/api/investigations/reactive", json=first).status_code == 201

        conflicting = get_signal(
            client,
            dataset_version_id,
            fixture_id="hero-reactive-risk-revision-conflict-v1",
        )
        response = client.post("/api/investigations/reactive", json=conflicting)

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "rejected"
        assert attempt["primary_code"] == "RISK_SIGNAL_REVISION_CONFLICT"
        assert attempt["investigation_request"] is None


def test_unverifiable_advisory_context_is_a_warning_and_cannot_change_projection(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(
            client,
            dataset_version_id,
            fixture_id="hero-reactive-risk-context-unverifiable-v1",
        )

        response = client.post("/api/investigations/reactive", json=signal)

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "accepted_with_warning"
        assert attempt["primary_code"] == "RISK_SIGNAL_ACCEPTED"
        assert [finding["code"] for finding in attempt["findings"]] == [
            "RISK_SIGNAL_CONTEXT_UNVERIFIABLE"
        ]
        request = attempt["investigation_request"]
        assert request is not None
        assert request["prediction_metadata"]["value"]["advisory_context"]["state"] == (
            "missing"
        )
        assert "advisory_context" not in request["causal_engine_input"]


def test_identical_signals_are_isolated_between_demo_workspaces(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "core.sqlite3"
    with make_client(database_path) as client_a, make_client(database_path) as client_b:
        dataset_version_id = import_hero(client_a)
        signal = get_signal(client_a, dataset_version_id)

        accepted_a = client_a.post("/api/investigations/reactive", json=signal)
        accepted_b = client_b.post("/api/investigations/reactive", json=signal)

        assert accepted_a.status_code == 201
        assert accepted_b.status_code == 201
        request_a = accepted_a.json()["attempt"]["investigation_request_id"]
        request_b = accepted_b.json()["attempt"]["investigation_request_id"]
        assert request_a != request_b
        assert len(client_a.get("/api/audit/occurrences").json()["items"]) == 1
        assert len(client_b.get("/api/audit/occurrences").json()["items"]) == 1


def test_missing_predictive_artifacts_are_warnings_not_causal_failures(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        dataset_version_id = import_hero(client)
        signal = get_signal(
            client,
            dataset_version_id,
            fixture_id="hero-reactive-risk-metadata-unavailable-v1",
        )

        response = client.post("/api/investigations/reactive", json=signal)

        assert response.status_code == 201
        attempt = response.json()["attempt"]
        assert attempt["status"] == "accepted_with_warning"
        assert [finding["code"] for finding in attempt["findings"]] == [
            "PREDICTOR_ARTIFACT_UNAVAILABLE",
            "PREDICTIVE_ATTRIBUTION_UNAVAILABLE",
        ]
        assert attempt["investigation_request"] is not None
