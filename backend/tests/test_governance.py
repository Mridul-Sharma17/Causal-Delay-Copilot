from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import backend.app.governance as governance
from backend.app.canonical import sha256 as _sha256
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


def test_decision_brief_publishes_successors_and_permission_invalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app(Settings(database_path=tmp_path / "core.sqlite3"))) as client:
        imported = client.post(
            "/api/ingestion-runs",
            json={
                "idempotency_key": "governance-heads-import",
                "dataset_key": "semi-synthetic-hero",
                "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
            },
        )
        dataset_version_id = imported.json()["dataset_version_id"]
        ingress = client.post(
            "/api/investigations/reactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-reactive-risk-v1",
            },
        )
        request_id = ingress.json()["attempt"]["investigation_request_id"]
        workspace_id = client.get("/api/workspace").json()["workspace_id"]
        stored_request = client.app.state.audit_store.get_investigation_request(
            workspace_id, request_id
        )
        assert stored_request is not None
        subject_identity = stored_request["subject"]["order_line_id"]
        reference = _reference()
        reference.dataset_version_id = dataset_version_id
        client.app.state.reference_store.read_model = lambda *args, **kwargs: reference

        original_evaluator = governance.evaluate_decision_support
        seed_subject_verdict = {
            "scope": "subject",
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        }
        seed_subject_verdict["content_hash"] = _sha256(seed_subject_verdict)
        seed_population_verdict = {
            "scope": "population",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        }
        seed_population_verdict["content_hash"] = _sha256(seed_population_verdict)
        denied_subject_verdict = {
            "scope": "subject",
            "verdict_code": "INSUFFICIENT",
            "decision_support_role_permitted": False,
            "decision_support_evaluation_permitted": False,
            "primary_trigger_code": "SUBJECT_OVERLAP_INSUFFICIENT",
        }
        denied_subject_verdict["content_hash"] = _sha256(denied_subject_verdict)
        denied_population_verdict = {
            "scope": "population",
            "decision_support_role_permitted": False,
            "decision_support_evaluation_permitted": False,
            "primary_trigger_code": "POPULATION_EVIDENCE_UNAVAILABLE",
        }
        denied_population_verdict["content_hash"] = _sha256(denied_population_verdict)
        seed_result = original_evaluator(
            investigation_request={
                "investigation_request_id": "seed-investigation",
                "trigger_mode": "reactive",
                "subject": {"order_line_id": "seed-line"},
                "causal_engine_input": {
                    "supplier_load_exposure": {
                        "primary": {"high_load_exposure": True}
                    }
                },
            },
            subject_applicability={
                "state": "applicable",
                "subject_identity": "seed-line",
                "reason": "Subject support is sufficient.",
                "next_step": "Inspect the separately governed action boundary.",
            },
            subject_verdict=seed_subject_verdict,
            population_verdict=seed_population_verdict,
            intended_role="semi_synthetic_hero",
            release_candidate_id="local-default",
            runtime_fingerprint_digest="sha256:" + "e" * 64,
        )
        assert seed_result["decision_support_evaluation_id"] is not None

        def permitted_decision_support(**kwargs: object) -> dict[str, object]:
            result = deepcopy(seed_result)
            result["decision_support_evaluation_id"] = "calculated-evaluation-id"
            result["decision_support_evaluation_series_id"] = kwargs[
                "evaluation_series_id"
            ]
            driver_state = result["subject_driver_state"]
            assert isinstance(driver_state, dict)
            driver_state["subject_identity"] = subject_identity
            driver_state["dataset_version_id"] = dataset_version_id
            driver_state["causal_decision_at"] = stored_request["decision_cutoff"]
            return result

        def denied_decision_support(**kwargs: object) -> dict[str, object]:
            result = permitted_decision_support(**kwargs)
            permission_provenance = result["permission_provenance"]
            assert isinstance(permission_provenance, dict)
            permission_provenance = deepcopy(permission_provenance)
            permission_provenance["subject_verdict_ref_and_hash"] = {
                "scope": "subject",
                "reference": denied_subject_verdict["content_hash"],
                "content_hash": denied_subject_verdict["content_hash"],
            }
            permission_provenance["population_verdict_ref_and_hash"] = {
                "scope": "population",
                "reference": denied_population_verdict["content_hash"],
                "content_hash": denied_population_verdict["content_hash"],
            }
            result.update(
                {
                    "outcome": "NOT_PERMITTED",
                    "state": "not_permitted",
                    "primary_reason_code": "SUBJECT_OVERLAP_INSUFFICIENT",
                    "reason": "Subject support is insufficient.",
                    "next_step": "Supply the frozen subject support.",
                    "permission": {
                        "decision_support_evaluation_permitted": False,
                        "denial_reason_code": "SUBJECT_OVERLAP_INSUFFICIENT",
                        "reason": "Subject support is insufficient.",
                        "next_step": "Supply the frozen subject support.",
                    },
                    "decision_support_evaluation_id": None,
                    "decision_support_evaluation_series_id": None,
                    "permission_provenance": permission_provenance,
                    "decision_support_permission_digest": _sha256(
                        permission_provenance
                    ),
                    "options": [],
                    "suppression_reasons": [
                        {
                            "code": "SUBJECT_OVERLAP_INSUFFICIENT",
                            "category": "PERMISSION",
                            "priority": 100,
                            "reason": "Subject support is insufficient.",
                        }
                    ],
                    "action_recommendation": None,
                    "tradeoff": None,
                    "consumed_inputs": ["permission_envelope"],
                }
            )
            return result

        def applicable_subject(**_: object):
            return (
                {
                    "state": "applicable",
                    "subject_identity": subject_identity,
                    "reason": "Subject support is sufficient.",
                    "next_step": "Inspect the separately governed action boundary.",
                },
                {
                    "scope": "subject",
                    "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
                    "decision_support_role_permitted": True,
                    "decision_support_evaluation_permitted": True,
                },
                {
                    "language": "Subject support is sufficient.",
                    "next_step": "Inspect the separately governed action boundary.",
                },
            )

        monkeypatch.setattr(governance, "_subject_applicability", applicable_subject)
        monkeypatch.setattr(
            governance, "evaluate_decision_support", permitted_decision_support
        )
        first_response = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "brief-heads-1",
                "reference_id": "ordinary-demo",
            },
        )
        assert first_response.status_code == 201, first_response.text
        first_snapshot = first_response.json()["snapshot"]
        first_lifecycle = first_snapshot["decision_support"]["evaluation_lifecycle"]
        assert first_lifecycle["head"]["head_kind"] == "EVALUATION"
        assert first_lifecycle["head"]["advice_state"] == "current"

        second_response = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "brief-heads-2",
                "reference_id": "ordinary-demo",
            },
        )
        assert second_response.status_code == 201
        second_lifecycle = second_response.json()["snapshot"]["decision_support"][
            "evaluation_lifecycle"
        ]
        assert second_lifecycle["head"]["head_kind"] == "EVALUATION"
        assert sorted(
            item["record_state"]
            for item in second_lifecycle["history"]
            if item["record_type"] == "evaluation"
        ) == ["current", "superseded"]

        def denied_subject(**_: object):
            return (
                {
                    "state": "abstained",
                    "subject_identity": subject_identity,
                    "reason_code": "SUBJECT_OVERLAP_INSUFFICIENT",
                    "reason": "Subject support is insufficient.",
                    "next_step": "Supply the frozen subject support.",
                },
                {
                    "scope": "subject",
                    "verdict_code": "INSUFFICIENT",
                    "decision_support_role_permitted": False,
                    "decision_support_evaluation_permitted": False,
                    "primary_trigger_code": "SUBJECT_OVERLAP_INSUFFICIENT",
                },
                None,
            )

        monkeypatch.setattr(governance, "_subject_applicability", denied_subject)
        monkeypatch.setattr(
            governance, "evaluate_decision_support", denied_decision_support
        )
        invalidated_response = client.post(
            f"/api/investigations/{request_id}/decision-brief",
            json={
                "idempotency_key": "brief-heads-3",
                "reference_id": "ordinary-demo",
            },
        )
        assert invalidated_response.status_code == 201
        invalidated_lifecycle = invalidated_response.json()["snapshot"][
            "decision_support"
        ]["evaluation_lifecycle"]
        assert invalidated_lifecycle["head"]["head_kind"] == "PERMISSION_INVALIDATION"
        assert invalidated_lifecycle["head"]["advice_state"] == "invalidated"
        invalidation_details = invalidated_response.json()["snapshot"][
            "decision_support"
        ]["decision_support_invalidation"]
        assert invalidation_details["invalidated_artifact_ref_and_hash"] == (
            second_lifecycle["head"]["head_record_ref_and_hash"]
        )
        assert invalidation_details["superseding_verdict_ref_and_hash"][
            "subject_verdict_ref_and_hash"
        ]["content_hash"] == denied_subject_verdict["content_hash"]
        assert all(
            item["record_state"] != "current"
            for item in invalidated_lifecycle["history"]
            if item["record_type"] == "evaluation"
        )
