from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import backend.app.governance as governance
from backend.app.diagnostics import evaluate_primary_interval
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.validity import derive_evidence_verdict


IDENTITY = {
    "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000031",
    "bundle_manifest_hash": "sha256:" + "b" * 64,
    "evidence_refs": ["engine_result:primary"],
    "input_refs": ["engine_result:primary"],
}


def _effect() -> dict[str, object]:
    return {
        "estimate": 1.5,
        "standard_error": 0.1,
        "ci_lower": 1.2,
        "ci_upper": 1.8,
        "ci_level": 0.95,
        "unit": "days",
        "duration_basis": "CALENDAR_DAY",
    }


def _population_verdict() -> dict[str, object]:
    effect = _effect()
    verdict = derive_evidence_verdict(
        {
            "status": "estimated",
            "primary_effect": effect,
            "effect_result_ref": "engine_result:primary",
        },
        [evaluate_primary_interval(effect, **IDENTITY)],
        intended_role="semi_synthetic_hero",
        scope="population",
        **IDENTITY,
    )
    assert verdict is not None
    return verdict


def _reference():
    return SimpleNamespace(
        reference_slot_id="ordinary-demo",
        analysis_run_id=IDENTITY["analysis_run_id"],
        bundle_manifest_hash=IDENTITY["bundle_manifest_hash"],
        validation_attestation_id="attestation-ordinary-demo",
        validation_attestation_ref="attestation-ordinary-demo",
        release_candidate_id="local-default",
        intended_role="semi_synthetic_hero",
        engine_result_status="estimated",
        scientific_request_digest="sha256:" + "c" * 64,
        dataset_version_id="sha256:" + "d" * 64,
        runtime_fingerprint_digest="sha256:" + "e" * 64,
        validation_policy_version="release-validation.v1",
        validated_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
        diagnostic_results=(),
        robustness_grade=None,
        evidence_verdict=_population_verdict(),
    )


def test_decision_brief_snapshot_is_immutable_and_replay_does_not_read_current_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3"))) as client:
        imported = client.post(
            "/api/ingestion-runs",
            json={
                "idempotency_key": "governance-hero-import",
                "dataset_key": "semi-synthetic-hero",
                "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
            },
        )
        assert imported.status_code == 201
        dataset_version_id = imported.json()["dataset_version_id"]

        ingress = client.post(
            "/api/investigations/reactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-reactive-risk-v1",
            },
        )
        assert ingress.status_code == 201
        request_id = ingress.json()["attempt"]["investigation_request_id"]
        ingress_event_seq = ingress.json()["attempt"]["audit"]["event_seq"]
        reference = _reference()
        reference.dataset_version_id = dataset_version_id
        client.app.state.reference_store.read_model = lambda *args, **kwargs: reference

        published = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "brief-publication-1",
                "reference_id": "ordinary-demo",
            },
        )
        assert published.status_code == 201
        snapshot = published.json()["snapshot"]
        assert snapshot["schema_version"] == "decision-brief-snapshot.v2"
        assert snapshot["subject_verdict"]["scope"] == "subject"
        assert snapshot["subject_applicability"]["state"] == "abstained"
        assert snapshot["action_lane"]["state"] == "read_only"
        decision_support = snapshot["decision_support"]
        assert decision_support["schema_version"] == "decision-support-boundary.v1"
        assert decision_support["outcome"] == "NOT_PERMITTED"
        assert decision_support["permission"][
            "decision_support_evaluation_permitted"
        ] is False
        assert decision_support["decision_support_evaluation_id"] is None
        assert decision_support["action_recommendation"] is None
        assert decision_support["consumed_inputs"] == ["permission_envelope"]
        assert "constraints_as_of" not in str(decision_support)
        assert "registry_inspection" not in decision_support
        assert snapshot["decision_support_registry"]["inspection_kind"] == (
            "GOVERNED_RECORD_INSPECTION"
        )
        assert snapshot["decision_support_registry"]["release_binding"]["state"] == (
            "BUNDLED_RELEASE_BOUND"
        )
        assert snapshot["ingress_attempt"]["attempt"]["status"] == "accepted"
        assert (
            snapshot["lineage"]["payload"]["dataset_version"]["dataset_version_id"]
            == dataset_version_id
        )
        assert set(snapshot["referenced_records"]) == {
            "investigation_request",
            "ingress_attempt",
            "lineage",
            "validated_reference",
        }

        with sqlite3.connect(tmp_path / "core.sqlite3") as raw:
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    "UPDATE decision_brief_snapshots SET reference_id = ? WHERE snapshot_id = ?",
                    ("mutated-reference", snapshot["snapshot_id"]),
                )
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    "DELETE FROM decision_brief_snapshots WHERE snapshot_id = ?",
                    (snapshot["snapshot_id"],),
                )

        replay_event_seq = snapshot["event_seq"]
        client.app.state.reference_store.read_model = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("replay must not read current reference state")
        )
        monkeypatch.setattr(
            governance,
            "verify_evidence_verdict",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("replay must not verify current evidence policy")
            ),
        )
        monkeypatch.setattr(
            governance,
            "render_evidence_verdict",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("replay must not render current diagnostic policy")
            ),
        )
        monkeypatch.setattr(
            governance,
            "render_subject_evidence_verdict",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("replay must not render current subject policy")
            ),
        )
        idempotent = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "brief-publication-1",
                "reference_id": "ordinary-demo",
            },
        )
        assert idempotent.status_code == 200
        assert idempotent.json()["result"] == "IDEMPOTENT_REPLAY"
        assert idempotent.json()["snapshot"] == snapshot

        unavailable = client.get(
            "/api/audit/replay",
            params={
                "investigation_request_id": request_id,
                "event_seq": ingress_event_seq,
            },
        )
        assert unavailable.status_code == 200
        assert unavailable.json()["status"] == "REPLAY_UNAVAILABLE"
        assert unavailable.json()["snapshot"] is None

        replay = client.get(
            "/api/audit/replay",
            params={
                "investigation_request_id": request_id,
                "event_seq": replay_event_seq,
            },
        )

    assert replay.status_code == 200
    assert replay.json()["status"] == "REPLAYED"
    assert replay.json()["snapshot"] == snapshot
    assert replay.json()["requested_event_seq"] == replay_event_seq
