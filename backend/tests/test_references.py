from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from backend.app.canonical import canonical_json, sha256
from backend.app.artifacts import (
    ArtifactLifecycleError,
    RunLease,
    build_artifact_pin_set,
    cleanup_artifacts,
)
from backend.app.errors import CoreSafeError
from backend.app.main import create_app
from backend.app.references import (
    ARTIFACT_CONTRACT_VERSION,
    BUNDLE_MANIFEST_SCHEMA_VERSION,
    CACHE_KEY_SCHEMA_VERSION,
    DEFAULT_REFERENCE_SLOT_ID,
    READ_MODEL_SCHEMA_VERSION,
    REFERENCE_REGISTRY_SCHEMA_VERSION,
    REQUIRED_LOGICAL_ROLES,
    VERIFICATION_REPORT_SCHEMA_VERSION,
    VALIDATION_ATTESTATION_SCHEMA_VERSION,
    ArtifactMember,
    ReferencePromotion,
    ReferencePromotionError,
    ReferenceVerificationError,
    ValidatedReferenceStore,
    promote_validated_reference,
    publish_analysis_bundle,
    read_verified_analysis_bundle,
)
from backend.app.settings import DeliveryProfile, Settings
from backend.app.recovery import StateRecovery


RELEASE_ID = "local-test"
BUILD_ID = "build-test"


def _json_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _request(
    dataset_version_id: str = "sha256:" + "a" * 64,
) -> dict[str, str]:
    return {
        "engine_input_schema_version": "causal-engine-input.v2",
        "dataset_version_id": dataset_version_id,
        "intended_role": "semi_synthetic_hero",
    }


def _runtime(release_id: str, build_id: str) -> dict[str, str]:
    return {
        "schema_version": "runtime-fingerprint.v1",
        "profile": "LOCAL_FALLBACK",
        "release_candidate_id": release_id,
        "build_manifest_id": build_id,
    }


def _cache_key(scientific_request_digest: str, runtime_fingerprint_digest: str) -> str:
    return sha256(
        {
            "schema_version": CACHE_KEY_SCHEMA_VERSION,
            "scientific_request_digest": scientific_request_digest,
            "runtime_fingerprint_digest": runtime_fingerprint_digest,
            "engine_output_schema_version": "causal-engine-result.v1",
            "bundle_manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        }
    )


def _manifest(
    release_id: str,
    build_id: str,
    dataset_version_id: str = "sha256:" + "a" * 64,
) -> dict[str, object]:
    request = _request(dataset_version_id)
    runtime = _runtime(release_id, build_id)
    request_digest = sha256(request)
    runtime_digest = sha256(runtime)
    return {
        "manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "scientific_request_digest": request_digest,
        "runtime_fingerprint_digest": runtime_digest,
        "cache_key": _cache_key(request_digest, runtime_digest),
        "engine_result_status": "estimated",
        "started_at": "2026-08-01T00:00:00+00:00",
        "completed_at": "2026-08-01T00:01:00+00:00",
        "producer_application_build_id": build_id,
    }


def _members(
    release_id: str,
    build_id: str,
    *,
    dataset_version_id: str = "sha256:" + "a" * 64,
) -> tuple[ArtifactMember, ...]:
    request = _request(dataset_version_id)
    runtime = _runtime(release_id, build_id)
    result = {
        "schema_version": "causal-engine-result.v1",
        "status": "estimated",
        "evidence": {"state": "available"},
    }
    verification = {
        "schema_version": VERIFICATION_REPORT_SCHEMA_VERSION,
        "validation_policy_version": "release-validation.v1",
        "status": "passed",
        "checks": [
            {
                "check_id": "fixture",
                "status": "passed",
                "evidence_digest": "sha256:" + "c" * 64,
            }
        ],
    }
    members: list[ArtifactMember] = [
        ArtifactMember(
            logical_role="engine_request",
            logical_id="request",
            producer_schema_id="causal-engine-input",
            producer_schema_version="v2",
            media_type="application/json",
            confidentiality_class="public_safe",
            content=_json_bytes(request),
        ),
        ArtifactMember(
            logical_role="runtime_fingerprint",
            logical_id="runtime",
            producer_schema_id="runtime-fingerprint",
            producer_schema_version="v1",
            media_type="application/json",
            confidentiality_class="public_safe",
            content=_json_bytes(runtime),
        ),
        ArtifactMember(
            logical_role="engine_result",
            logical_id="result",
            producer_schema_id="causal-engine-result",
            producer_schema_version="v1",
            media_type="application/json",
            confidentiality_class="public_safe",
            content=_json_bytes(result),
            scientific_content_digest=sha256(result),
        ),
        ArtifactMember(
            logical_role="verification_report",
            logical_id="verification",
            producer_schema_id="analysis-run-verification",
            producer_schema_version="v1",
            media_type="application/json",
            confidentiality_class="public_safe",
            content=_json_bytes(verification),
        ),
    ]
    for role in sorted(REQUIRED_LOGICAL_ROLES - {"engine_request", "runtime_fingerprint", "engine_result", "verification_report"}):
        payload = {"schema_version": f"{role}.v1"}
        members.append(
            ArtifactMember(
                logical_role=role,
                logical_id=role,
                producer_schema_id=role,
                producer_schema_version="v1",
                media_type="application/json",
                confidentiality_class="public_safe",
                content=_json_bytes(payload),
                scientific_content_digest=sha256(payload),
            )
        )
    return tuple(members)


def _members_with_verification_gates(
    release_id: str,
    build_id: str,
    *gate_ids: str,
) -> tuple[ArtifactMember, ...]:
    members = list(_members(release_id, build_id))
    verification_index = next(
        index
        for index, member in enumerate(members)
        if member.logical_role == "verification_report"
    )
    members[verification_index] = replace(
        members[verification_index],
        content=_json_bytes(
            {
                "schema_version": VERIFICATION_REPORT_SCHEMA_VERSION,
                "validation_policy_version": "release-validation.v1",
                "status": "passed",
                "checks": [
                    {
                        "check_id": gate_id,
                        "status": "passed",
                        "evidence_digest": "sha256:" + chr(97 + index) * 64,
                    }
                    for index, gate_id in enumerate(gate_ids)
                ],
            }
        ),
    )
    return tuple(members)


def _install_reference(
    artifact_root: Path,
    *,
    run_id: str,
    slot_id: str,
    validated_at: str,
    release_id: str = RELEASE_ID,
    build_id: str = BUILD_ID,
    dataset_version_id: str = "sha256:" + "a" * 64,
) -> str:
    request = _request(dataset_version_id)
    runtime = _runtime(release_id, build_id)
    published = publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest=_manifest(release_id, build_id, dataset_version_id),
        members=_members(
            release_id,
            build_id,
            dataset_version_id=dataset_version_id,
        ),
    )
    attestation_id = f"attestation-{slot_id}"
    _write_json(
        artifact_root / "attestations" / f"{attestation_id}.json",
        {
            "attestation_schema_version": VALIDATION_ATTESTATION_SCHEMA_VERSION,
            "validation_attestation_id": attestation_id,
            "analysis_run_id": run_id,
            "bundle_manifest_hash": published.bundle_manifest_hash,
            "scientific_request_digest": sha256(request),
            "runtime_fingerprint_digest": sha256(runtime),
            "release_candidate_id": release_id,
            "reference_slot_id": slot_id,
            "validation_policy_version": "release-validation.v1",
            "status": "passed",
            "checks": [
                {
                    "check_id": "fixture",
                    "status": "passed",
                    "evidence_digest": "sha256:" + "c" * 64,
                }
            ],
            "validated_at": validated_at,
        },
    )
    return published.bundle_manifest_hash


def _write_registry(artifact_root: Path, entries: list[dict[str, object]]) -> None:
    _write_json(
        artifact_root / "releases" / RELEASE_ID / "validated-references.json",
        {
            "registry_schema_version": REFERENCE_REGISTRY_SCHEMA_VERSION,
            "release_candidate_id": RELEASE_ID,
            "release_id": RELEASE_ID,
            "entries": entries,
        },
    )


def test_reference_store_selects_the_earliest_verified_current_release_reference(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    old_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000001",
        slot_id="ordinary-demo-old",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    new_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000002",
        slot_id="ordinary-demo-new",
        validated_at="2026-08-02T00:00:00+00:00",
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo-new",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000002",
                "bundle_manifest_hash": new_hash,
                "validation_attestation_id": "attestation-ordinary-demo-new",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            },
            {
                "reference_slot_id": "ordinary-demo-old",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000001",
                "bundle_manifest_hash": old_hash,
                "validation_attestation_id": "attestation-ordinary-demo-old",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            },
        ],
    )

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint={
            "schema_version": "runtime-fingerprint.v1",
            "profile": "LOCAL_FALLBACK",
            "release_candidate_id": RELEASE_ID,
            "build_manifest_id": BUILD_ID,
        },
    )

    selected = store.select_reference()

    assert selected is not None
    assert selected.reference_slot_id == "ordinary-demo-old"
    assert selected.analysis_run_id.endswith("0001")
    assert selected.delivery_mode == "existing_run_reuse"
    assert selected.verification_state == "reference_validated"
    assert store.read_model().reference_slot_id == "ordinary-demo-old"


def test_reference_store_rejects_a_synthetic_conformance_reference(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000003",
        slot_id="ordinary-demo-smuggled-synthetic",
        validated_at="2026-08-01T00:00:00+00:00",
        dataset_version_id="dataset-version-ordinary-demo",
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "synthetic:core-decision-support-v1:reference-slot",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000003",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo-smuggled-synthetic",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint={
            "schema_version": "runtime-fingerprint.v1",
            "profile": "LOCAL_FALLBACK",
            "release_candidate_id": RELEASE_ID,
            "build_manifest_id": BUILD_ID,
        },
    )

    assert store.list_verified_references() == []
    assert store.select_reference() is None
    assert not (artifact_root / "quarantine" / "analysis-run-00000000-0000-4000-8000-000000000003").exists()


def test_bundle_publisher_rejects_synthetic_analysis_identity(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="synthetic conformance fixtures"):
        publish_analysis_bundle(
            tmp_path / "artifacts",
            analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000004",
            manifest={
                "dataset_version_id": (
                    "synthetic:core-decision-support-v1:dataset-approved-reactive"
                )
            },
            members=[],
        )


def test_verified_bundle_rejects_a_synthetic_manifest_identity(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000005"
    publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest=_manifest(RELEASE_ID, BUILD_ID),
        members=_members(RELEASE_ID, BUILD_ID),
    )
    manifest_path = artifact_root / "runs" / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["investigation_request_id"] = (
        "synthetic:core-decision-support-v1:investigation-request"
    )
    manifest["bundle_manifest_hash"] = sha256(
        {key: value for key, value in manifest.items() if key != "bundle_manifest_hash"}
    )
    _write_json(manifest_path, manifest)

    with pytest.raises(ReferenceVerificationError, match="synthetic conformance fixtures"):
        read_verified_analysis_bundle(
            artifact_root,
            analysis_run_id=run_id,
            expected_build_id=BUILD_ID,
            expected_runtime=_runtime(RELEASE_ID, BUILD_ID),
        )


def test_cache_candidate_rejects_a_synthetic_verified_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "runs" / "analysis-run-00000000-0000-4000-8000-000000000006").mkdir(
        parents=True
    )
    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=_runtime(RELEASE_ID, BUILD_ID),
    )
    monkeypatch.setattr(
        store,
        "_verify_run",
        lambda _analysis_run_id: (
            {},
            {
                "dataset_version_id": (
                    "synthetic:core-decision-support-v1:dataset-approved-reactive"
                ),
                "intended_role": "synthetic_conformance",
            },
        ),
    )

    assert store.list_verified_runs() == []
    assert store.select_cache_candidate() is None


def test_reference_store_selects_only_an_exact_request_and_cache_key(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    target_dataset_version_id = "sha256:" + "b" * 64
    old_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000006",
        slot_id="ordinary-demo-old",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    target_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000007",
        slot_id="ordinary-demo-target",
        validated_at="2026-08-02T00:00:00+00:00",
        dataset_version_id=target_dataset_version_id,
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo-old",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000006",
                "bundle_manifest_hash": old_hash,
                "validation_attestation_id": "attestation-ordinary-demo-old",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            },
            {
                "reference_slot_id": "ordinary-demo-target",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000007",
                "bundle_manifest_hash": target_hash,
                "validation_attestation_id": "attestation-ordinary-demo-target",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            },
        ],
    )
    runtime = _runtime(RELEASE_ID, BUILD_ID)
    request = _request(target_dataset_version_id)

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    )

    selected = store.select_reference(
        scientific_request_digest=sha256(request),
        cache_key=_cache_key(sha256(request), sha256(runtime)),
    )

    assert selected is not None
    assert selected.reference_slot_id == "ordinary-demo-target"
    assert selected.scientific_request_digest == sha256(request)


def test_publisher_rejects_an_unregistered_producer_schema(tmp_path: Path) -> None:
    members = list(_members(RELEASE_ID, BUILD_ID))
    index = next(
        index for index, member in enumerate(members) if member.logical_role == "feature_schema"
    )
    members[index] = replace(members[index], producer_schema_id="unregistered-schema")

    with pytest.raises(ValueError, match="producer schema"):
        publish_analysis_bundle(
            tmp_path / "artifacts",
            analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000008",
            manifest=_manifest(RELEASE_ID, BUILD_ID),
            members=members,
        )


def test_publisher_rejects_a_payload_with_the_wrong_role_schema(tmp_path: Path) -> None:
    members = list(_members(RELEASE_ID, BUILD_ID))
    index = next(
        index for index, member in enumerate(members) if member.logical_role == "feature_schema"
    )
    members[index] = replace(
        members[index],
        content=_json_bytes({"schema_version": "wrong-schema.v1"}),
    )

    with pytest.raises(ValueError, match="payload schema"):
        publish_analysis_bundle(
            tmp_path / "artifacts",
            analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000009",
            manifest=_manifest(RELEASE_ID, BUILD_ID),
            members=members,
        )


def test_publisher_rejects_an_unresolved_evidence_reference(tmp_path: Path) -> None:
    members = list(_members(RELEASE_ID, BUILD_ID))
    index = next(
        index for index, member in enumerate(members) if member.logical_role == "feature_schema"
    )
    members[index] = replace(members[index], evidence_refs=("feature_schema:missing",))

    with pytest.raises(ValueError, match="evidence reference"):
        publish_analysis_bundle(
            tmp_path / "artifacts",
            analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000011",
            manifest=_manifest(RELEASE_ID, BUILD_ID),
            members=members,
        )


def test_reference_store_fails_closed_on_corrupt_member_and_does_not_expose_paths(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000003",
        slot_id="ordinary-demo",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000003",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    manifest = json.loads(
        (
            artifact_root
            / "runs"
            / "analysis-run-00000000-0000-4000-8000-000000000003"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    descriptor = next(
        item for item in manifest["artifact_descriptors"] if item["logical_role"] == "engine_result"
    )
    object_path = (
        artifact_root
        / "objects"
        / descriptor["confidentiality_class"]
        / "sha256"
        / descriptor["sha256"][7:9]
        / descriptor["sha256"][9:]
    )
    object_path.write_bytes(b"corrupt")

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint={
            "schema_version": "runtime-fingerprint.v1",
            "profile": "LOCAL_FALLBACK",
            "release_candidate_id": RELEASE_ID,
            "build_manifest_id": BUILD_ID,
        },
    )

    assert store.select_reference() is None
    assert store.list_verified_references() == []


def test_reference_store_rejects_release_or_attestation_mismatch(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000004",
        slot_id="ordinary-demo",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000004",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-missing",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint={
            "schema_version": "runtime-fingerprint.v1",
            "profile": "LOCAL_FALLBACK",
            "release_candidate_id": "different-release",
            "build_manifest_id": BUILD_ID,
        },
    )

    assert store.select_reference() is None


def test_reference_delivery_endpoint_labels_verified_reuse_without_exposing_paths(
    tmp_path: Path,
) -> None:
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=tmp_path / "state",
        public_origin="http://127.0.0.1:8000",
        release_candidate_id=RELEASE_ID,
        build_manifest_id=BUILD_ID,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    bundle_hash = _install_reference(
        settings.artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000005",
        slot_id=DEFAULT_REFERENCE_SLOT_ID,
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        settings.artifact_root,
        [
            {
                "reference_slot_id": DEFAULT_REFERENCE_SLOT_ID,
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000005",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/evidence/reference")

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_mode"] == "existing_run_reuse"
    assert body["delivery_badge"] == "Validated reference"
    assert body["verification_state"] == "reference_validated"
    assert body["reference_slot_id"] == DEFAULT_REFERENCE_SLOT_ID
    assert body["release_candidate_id"] == RELEASE_ID
    assert body["dataset_version_id"] == _request()["dataset_version_id"]
    assert body["analysis_run_id"].startswith("analysis-run-")
    assert len(body["diagnostics"]) == 4
    assert {item["status"] for item in body["diagnostics"]} == {"UNAVAILABLE"}
    assert body["diagnostic_summary"] == {
        "state": "limited",
        "diagnostic_count": 4,
        "status_counts": {"UNAVAILABLE": 4},
    }
    assert all("path" not in key.lower() for key in body)


def test_reference_delivery_endpoint_fails_closed_on_an_unexpected_intended_role(
    tmp_path: Path,
) -> None:
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=tmp_path / "state",
        public_origin="http://127.0.0.1:8000",
        release_candidate_id=RELEASE_ID,
        build_manifest_id=BUILD_ID,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    bundle_hash = _install_reference(
        settings.artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000010",
        slot_id=DEFAULT_REFERENCE_SLOT_ID,
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        settings.artifact_root,
        [
            {
                "reference_slot_id": DEFAULT_REFERENCE_SLOT_ID,
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000010",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "different-role",
            }
        ],
    )

    with pytest.raises(CoreSafeError):
        with TestClient(create_app(settings)):
            pass

    assert not settings.state_root.exists()
    quarantines = list(StateRecovery(settings).quarantine_root.iterdir())
    assert len(quarantines) == 1
    assert (
        quarantines[0]
        / "state"
        / "artifacts"
        / "releases"
        / RELEASE_ID
        / "validated-references.json"
    ).is_file()


def test_reference_delivery_endpoint_falls_back_to_the_earliest_verified_reference(
    tmp_path: Path,
) -> None:
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=tmp_path / "state",
        public_origin="http://127.0.0.1:8000",
        release_candidate_id=RELEASE_ID,
        build_manifest_id=BUILD_ID,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    bundle_hash = _install_reference(
        settings.artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000012",
        slot_id="ordinary-demo-fallback",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        settings.artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo-fallback",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000012",
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo-fallback",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/evidence/reference")

    assert response.status_code == 200
    assert response.json()["reference_slot_id"] == "ordinary-demo-fallback"


def test_promotion_writes_an_immutable_content_addressed_attestation_and_is_idempotent(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000013"
    manifest = _manifest(RELEASE_ID, BUILD_ID)
    manifest["investigation_request_id"] = "investigation-00000000000000000000000000000001"
    publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest=manifest,
        members=_members_with_verification_gates(
            RELEASE_ID,
            BUILD_ID,
            "provenance",
            "reproduction",
        ),
    )
    runtime = _runtime(RELEASE_ID, BUILD_ID)

    promotion = promote_validated_reference(
        artifact_root,
        analysis_run_id=run_id,
        reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    )

    assert isinstance(promotion, ReferencePromotion)
    assert promotion.created is True
    assert promotion.reference.reference_slot_id == DEFAULT_REFERENCE_SLOT_ID
    assert promotion.reference.verification_state == "reference_validated"
    assert promotion.validation_attestation_ref.startswith("sha256:")
    attestation_digest = promotion.validation_attestation_ref.removeprefix("sha256:")
    attestation_path = (
        artifact_root
        / "attestations"
        / "sha256"
        / attestation_digest[:2]
        / attestation_digest[2:]
    )
    assert attestation_path.is_file()
    registry = json.loads(
        (
            artifact_root
            / "releases"
            / RELEASE_ID
            / "validated-references.json"
        ).read_text(encoding="utf-8")
    )
    assert registry["entries"][0]["validation_attestation_ref"] == (
        promotion.validation_attestation_ref
    )

    replay = promote_validated_reference(
        artifact_root,
        analysis_run_id=run_id,
        reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    )

    assert replay.created is False
    assert replay.validation_attestation_ref == promotion.validation_attestation_ref
    assert replay.reference == promotion.reference

    attestation_path.write_bytes(b"tampered")
    assert ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    ).select_reference() is None


def test_cache_selection_prefers_a_reference_then_uses_the_earliest_verified_run(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    early_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000014",
        slot_id="local-early",
        validated_at="2026-08-01T00:00:00+00:00",
    )
    late_hash = _install_reference(
        artifact_root,
        run_id="analysis-run-00000000-0000-4000-8000-000000000015",
        slot_id="ordinary-demo",
        validated_at="2026-08-02T00:00:00+00:00",
    )
    runtime = _runtime(RELEASE_ID, BUILD_ID)
    request_digest = sha256(_request())
    cache_key = _cache_key(request_digest, sha256(runtime))
    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    )

    local_candidate = store.select_cache_candidate(
        scientific_request_digest=request_digest,
        cache_key=cache_key,
    )

    assert local_candidate is not None
    assert local_candidate.analysis_run_id.endswith("0014")
    assert local_candidate.verification_state == "machine_verified"
    assert local_candidate.reference_slot_id is None
    assert local_candidate.validation_attestation_ref is None

    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": "ordinary-demo",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000015",
                "bundle_manifest_hash": late_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    reference_candidate = store.select_cache_candidate(
        scientific_request_digest=request_digest,
        cache_key=cache_key,
    )

    assert reference_candidate is not None
    assert reference_candidate.analysis_run_id.endswith("0015")
    assert reference_candidate.bundle_manifest_hash == late_hash
    assert reference_candidate.verification_state == "reference_validated"
    assert reference_candidate.reference_slot_id == "ordinary-demo"
    assert reference_candidate.validation_attestation_ref == "attestation-ordinary-demo"
    assert early_hash != late_hash


def test_promotion_never_edits_an_existing_release_registry(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    runtime = _runtime(RELEASE_ID, BUILD_ID)
    for suffix in ("18", "19"):
        publish_analysis_bundle(
            artifact_root,
            analysis_run_id=f"analysis-run-00000000-0000-4000-8000-0000000000{suffix}",
            manifest={
                **_manifest(RELEASE_ID, BUILD_ID),
                "investigation_request_id": f"investigation-000000000000000000000000000000{suffix}",
            },
            members=_members_with_verification_gates(
                RELEASE_ID,
                BUILD_ID,
                "provenance",
                "reproduction",
            ),
        )

    first = promote_validated_reference(
        artifact_root,
        analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000018",
        reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=runtime,
    )
    attestation_files_before = sorted(
        (artifact_root / "attestations" / "sha256").rglob("*")
    )

    with pytest.raises(ReferencePromotionError, match="immutable"):
        promote_validated_reference(
            artifact_root,
            analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000019",
            reference_slot_id="ordinary-demo-next",
            release_candidate_id=RELEASE_ID,
            runtime_fingerprint=runtime,
        )

    registry = json.loads(
        (
            artifact_root
            / "releases"
            / RELEASE_ID
            / "validated-references.json"
        ).read_text(encoding="utf-8")
    )
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["validation_attestation_ref"] == (
        first.validation_attestation_ref
    )
    assert sorted((artifact_root / "attestations" / "sha256").rglob("*")) == (
        attestation_files_before
    )


def test_promotion_fails_closed_without_provenance_and_reproduction_gates(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000016"
    publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest=_manifest(RELEASE_ID, BUILD_ID),
        members=_members(RELEASE_ID, BUILD_ID),
    )

    with pytest.raises(ReferencePromotionError, match="provenance"):
        promote_validated_reference(
            artifact_root,
            analysis_run_id=run_id,
            reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
            release_candidate_id=RELEASE_ID,
            runtime_fingerprint=_runtime(RELEASE_ID, BUILD_ID),
        )


def test_promotion_rejects_a_quarantined_source_run_and_a_revoked_reference(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000017"
    publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest={
            **_manifest(RELEASE_ID, BUILD_ID),
            "investigation_request_id": "investigation-00000000000000000000000000000017",
        },
        members=_members_with_verification_gates(
            RELEASE_ID,
            BUILD_ID,
            "provenance",
            "reproduction",
        ),
    )
    (artifact_root / "quarantine" / run_id).mkdir(parents=True)

    with pytest.raises(ReferencePromotionError, match="quarantined"):
        promote_validated_reference(
            artifact_root,
            analysis_run_id=run_id,
            reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
            release_candidate_id=RELEASE_ID,
            runtime_fingerprint=_runtime(RELEASE_ID, BUILD_ID),
        )

    (artifact_root / "quarantine" / run_id).rmdir()
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": DEFAULT_REFERENCE_SLOT_ID,
                "analysis_run_id": run_id,
                "bundle_manifest_hash": json.loads(
                    (
                        artifact_root
                        / "runs"
                        / run_id
                        / "manifest.json"
                    ).read_text(encoding="utf-8")
                )["bundle_manifest_hash"],
                "validation_attestation_id": "attestation-revoked",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
                "status": "revoked",
                "revoked": True,
            }
        ],
    )

    with pytest.raises(ReferencePromotionError, match="revoked"):
        promote_validated_reference(
            artifact_root,
            analysis_run_id=run_id,
            reference_slot_id=DEFAULT_REFERENCE_SLOT_ID,
            release_candidate_id=RELEASE_ID,
            runtime_fingerprint=_runtime(RELEASE_ID, BUILD_ID),
        )


def test_verification_failure_quarantines_material_and_returns_a_safe_status(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000020"
    bundle_hash = _install_reference(
        artifact_root,
        run_id=run_id,
        slot_id=DEFAULT_REFERENCE_SLOT_ID,
        validated_at="2026-08-01T00:00:00+00:00",
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": DEFAULT_REFERENCE_SLOT_ID,
                "analysis_run_id": run_id,
                "bundle_manifest_hash": bundle_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )
    manifest = json.loads(
        (artifact_root / "runs" / run_id / "manifest.json").read_text(encoding="utf-8")
    )
    result_descriptor = next(
        item
        for item in manifest["artifact_descriptors"]
        if item["logical_role"] == "engine_result"
    )
    result_object = (
        artifact_root
        / "objects"
        / result_descriptor["confidentiality_class"]
        / "sha256"
        / result_descriptor["sha256"][7:9]
        / result_descriptor["sha256"][9:]
    )
    result_object.write_bytes(b"tampered")

    store = ValidatedReferenceStore(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        runtime_fingerprint=_runtime(RELEASE_ID, BUILD_ID),
    )

    assert store.select_reference() is None
    status = store.read_artifact_status(run_id)

    assert status.lifecycle == "quarantined"
    assert status.availability_state == "suppressed"
    assert status.reason_code == "RUN_ARTIFACT_INTEGRITY_FAILED"
    assert status.recovery_action == "EXPLICIT_RETRY_AS_NEW_OPERATION"
    assert not (artifact_root / "runs" / run_id).exists()
    assert (artifact_root / "quarantine" / run_id / "quarantine-manifest.json").is_file()
    assert result_object.read_bytes() == b"tampered"
    assert all("path" not in key.lower() for key in status.__dataclass_fields__)


def test_run_leases_reject_conflicting_publication_without_overwriting_the_lease(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000021"
    first = RunLease(artifact_root, run_id, owner_id="first")
    second = RunLease(artifact_root, run_id, owner_id="second")

    first.acquire()
    with pytest.raises(ArtifactLifecycleError, match="RUN_LEASE_CONFLICT"):
        second.acquire()
    first.release()

    second.acquire()
    second.release()
    assert not (artifact_root / "leases" / run_id).exists()


def test_cleanup_honors_transitive_reference_pins_and_records_its_result(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    pinned_run_id = "analysis-run-00000000-0000-4000-8000-000000000022"
    unpinned_run_id = "analysis-run-00000000-0000-4000-8000-000000000023"
    pinned_hash = _install_reference(
        artifact_root,
        run_id=pinned_run_id,
        slot_id=DEFAULT_REFERENCE_SLOT_ID,
        validated_at="2026-08-01T00:00:00+00:00",
    )
    publish_analysis_bundle(
        artifact_root,
        analysis_run_id=unpinned_run_id,
        manifest=_manifest(RELEASE_ID, BUILD_ID, dataset_version_id="sha256:" + "b" * 64),
        members=_members(
            RELEASE_ID,
            BUILD_ID,
            dataset_version_id="sha256:" + "b" * 64,
        ),
    )
    _write_registry(
        artifact_root,
        [
            {
                "reference_slot_id": DEFAULT_REFERENCE_SLOT_ID,
                "analysis_run_id": pinned_run_id,
                "bundle_manifest_hash": pinned_hash,
                "validation_attestation_id": "attestation-ordinary-demo",
                "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
                "intended_role": "semi_synthetic_hero",
            }
        ],
    )

    pins = build_artifact_pin_set(
        artifact_root,
        release_candidate_id=RELEASE_ID,
    )
    receipt = cleanup_artifacts(
        artifact_root,
        release_candidate_id=RELEASE_ID,
        eligible_before=datetime(2026, 8, 10, tzinfo=timezone.utc),
        now=datetime(2026, 8, 11, tzinfo=timezone.utc),
        operation_id="cleanup-test",
    )

    assert pinned_run_id in pins.run_ids
    assert unpinned_run_id not in pins.run_ids
    assert receipt.status == "SUCCEEDED"
    assert receipt.deleted_run_count == 1
    assert receipt.pinned_material_count >= 1
    assert (artifact_root / "runs" / pinned_run_id).is_dir()
    assert not (artifact_root / "runs" / unpinned_run_id).exists()
    assert (artifact_root / "cleanup" / "cleanup-test.intent.json").is_file()
    assert (artifact_root / "cleanup" / "cleanup-test.result.json").is_file()


def test_pin_set_resolves_a_database_bundle_reference_to_its_run(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "analysis-run-00000000-0000-4000-8000-000000000024"
    bundle_hash = publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest=_manifest(RELEASE_ID, BUILD_ID),
        members=_members(RELEASE_ID, BUILD_ID),
    ).bundle_manifest_hash
    database_path = tmp_path / "core.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE workspace_artifacts (artifact_ref TEXT)")
        connection.execute(
            "INSERT INTO workspace_artifacts (artifact_ref) VALUES (?)",
            (bundle_hash,),
        )
        connection.commit()

    pins = build_artifact_pin_set(
        artifact_root,
        database_path=database_path,
    )

    assert run_id in pins.run_ids
    assert bundle_hash in pins.object_digests


def test_cleanup_evaluates_staging_events_independently(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    staging_root = artifact_root / "quarantine" / "staging"
    eligible = staging_root / "eligible-event"
    newer = staging_root / "newer-event"
    for event_root, created_at in (
        (eligible, "2026-08-01T00:00:00+00:00"),
        (newer, "2026-08-20T00:00:00+00:00"),
    ):
        _write_json(
            event_root / "quarantine-manifest.json",
            {
                "schema_version": "analysis-run-quarantine-manifest.v1",
                "analysis_run_id": "analysis-run-00000000-0000-4000-8000-0000000000" + ("25" if event_root == newer else "26"),
                "reason_code": "RUN_ARTIFACT_PUBLICATION_FAILED",
                "recovery_action": "EXPLICIT_RETRY_AS_NEW_OPERATION",
                "cleanup_eligible": True,
                "created_at": created_at,
            },
        )
        (event_root / "partial.json").write_text("partial", encoding="utf-8")

    receipt = cleanup_artifacts(
        artifact_root,
        eligible_before=datetime(2026, 8, 10, tzinfo=timezone.utc),
        now=datetime(2026, 8, 21, tzinfo=timezone.utc),
        operation_id="cleanup-staging-test",
    )

    assert receipt.status == "SUCCEEDED"
    assert receipt.deleted_quarantine_count == 1
    assert not eligible.exists()
    assert newer.is_dir()
