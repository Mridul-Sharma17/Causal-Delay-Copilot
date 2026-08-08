from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.canonical import canonical_json, sha256
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
    ValidatedReferenceStore,
    publish_analysis_bundle,
)
from backend.app.settings import DeliveryProfile, Settings


RELEASE_ID = "local-test"
BUILD_ID = "build-test"


def _json_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _members(release_id: str, build_id: str) -> tuple[ArtifactMember, ...]:
    request = {
        "engine_input_schema_version": "causal-engine-input.v2",
        "dataset_version_id": "sha256:" + "a" * 64,
        "intended_role": "semi_synthetic_hero",
    }
    runtime = {
        "schema_version": "runtime-fingerprint.v1",
        "profile": "LOCAL_FALLBACK",
        "release_candidate_id": release_id,
        "build_manifest_id": build_id,
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
            content=_json_bytes(
                {
                    "schema_version": "causal-engine-result.v1",
                    "status": "estimated",
                    "evidence": {"state": "available"},
                }
            ),
        ),
        ArtifactMember(
            logical_role="verification_report",
            logical_id="verification",
            producer_schema_id="analysis-run-verification",
            producer_schema_version="v1",
            media_type="application/json",
            confidentiality_class="public_safe",
            content=_json_bytes(
                {
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
            ),
        ),
    ]
    for role in sorted(REQUIRED_LOGICAL_ROLES - {"engine_request", "runtime_fingerprint", "engine_result", "verification_report"}):
        members.append(
            ArtifactMember(
                logical_role=role,
                logical_id=role,
                producer_schema_id=role,
                producer_schema_version="v1",
                media_type="application/json",
                confidentiality_class="public_safe",
                content=_json_bytes({"schema_version": f"{role}.v1"}),
            )
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
) -> str:
    request = {
        "engine_input_schema_version": "causal-engine-input.v2",
        "dataset_version_id": "sha256:" + "a" * 64,
        "intended_role": "semi_synthetic_hero",
    }
    runtime = {
        "schema_version": "runtime-fingerprint.v1",
        "profile": "LOCAL_FALLBACK",
        "release_candidate_id": release_id,
        "build_manifest_id": build_id,
    }
    published = publish_analysis_bundle(
        artifact_root,
        analysis_run_id=run_id,
        manifest={
            "manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
            "scientific_request_digest": sha256(request),
            "runtime_fingerprint_digest": sha256(runtime),
            "cache_key": sha256(
                {
                    "schema_version": CACHE_KEY_SCHEMA_VERSION,
                    "scientific_request_digest": sha256(request),
                    "runtime_fingerprint_digest": sha256(runtime),
                    "engine_output_schema_version": "causal-engine-result.v1",
                    "bundle_manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
                    "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
                }
            ),
            "engine_result_status": "estimated",
            "started_at": "2026-08-01T00:00:00+00:00",
            "completed_at": "2026-08-01T00:01:00+00:00",
            "producer_application_build_id": build_id,
        },
        members=_members(release_id, build_id),
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
    assert body["analysis_run_id"].startswith("analysis-run-")
    assert all("path" not in key.lower() for key in body)
