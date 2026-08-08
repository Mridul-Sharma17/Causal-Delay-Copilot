from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.errors import CoreSafeError, SafeErrorCode
from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings


def local_settings(state_root: Path) -> Settings:
    return Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
    )


def hosted_settings(state_root: Path) -> Settings:
    volume_path = state_root.parent / "railway-volume"
    hosted_root = volume_path / state_root.name
    return Settings(
        profile=DeliveryProfile.HOSTED,
        state_root=hosted_root,
        railway_volume_path=volume_path,
        public_origin="https://demo.example.com",
        release_candidate_id="rc-test",
        build_manifest_id="build-test",
    )


def start(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_startup_seals_database_artifacts_release_and_global_reference_state(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    settings = local_settings(state_root)

    with start(settings) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert (state_root / "core.sqlite3").is_file()
    assert (state_root / "artifacts").is_dir()
    assert (state_root / "artifacts" / "validated-references").is_dir()
    for directory in (
        "objects",
        "runs",
        "attestations",
        "releases",
        "temporary",
        "quarantine",
    ):
        assert (state_root / "artifacts" / directory).is_dir()
    assert (state_root / "runtime" / "release_identity.json").is_file()
    assert (state_root / "runtime" / "quota_policy.json").is_file()
    assert (state_root / "runtime" / "runtime_fingerprint.json").is_file()
    assert (state_root / "state_manifest.json").is_file()

    fingerprint = json.loads(
        (state_root / "runtime" / "runtime_fingerprint.json").read_text(
            encoding="utf-8"
        )
    )
    assert fingerprint["profile"] == "LOCAL_FALLBACK"
    assert "database_path" not in fingerprint
    assert "railway_volume_path" not in fingerprint


@pytest.mark.parametrize("profile", list(DeliveryProfile))
def test_startup_uses_the_same_state_contract_for_every_profile(
    tmp_path: Path,
    profile: DeliveryProfile,
) -> None:
    settings = (
        hosted_settings(tmp_path / "hosted")
        if profile is DeliveryProfile.HOSTED
        else local_settings(tmp_path / profile.value.lower())
    )

    with start(settings) as client:
        assert client.get("/api/health").status_code == 200

    assert settings.state_root.joinpath("state_manifest.json").is_file()


def test_startup_rejects_corrupt_sealed_state_without_repairing_it(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    settings = local_settings(state_root)

    with start(settings):
        pass

    quota_path = state_root / "runtime" / "quota_policy.json"
    quota_path.write_text("{}", encoding="utf-8")

    with pytest.raises(CoreSafeError) as failure:
        with start(settings):
            pass

    assert failure.value.code is SafeErrorCode.STATE_CORRUPT
    assert quota_path.read_text(encoding="utf-8") == "{}"


def test_startup_rejects_release_changes_for_an_existing_state_root(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    original = local_settings(state_root)

    with start(original):
        pass

    changed = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        release_candidate_id="different-release",
        build_manifest_id="different-build",
    )

    with pytest.raises(CoreSafeError) as failure:
        with start(changed):
            pass

    assert failure.value.code is SafeErrorCode.STATE_RELEASE_MISMATCH


def test_unsealed_state_is_not_repaired_silently(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    orphan = state_root / "orphan.txt"
    orphan.write_text("interrupted", encoding="utf-8")

    with pytest.raises(CoreSafeError) as failure:
        with start(local_settings(state_root)):
            pass

    assert failure.value.code is SafeErrorCode.STATE_CORRUPT
    assert orphan.read_text(encoding="utf-8") == "interrupted"
