from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.errors import CoreSafeError, SafeErrorCode
from backend.app.settings import DeliveryProfile, Settings


def hosted_settings(tmp_path: Path) -> Settings:
    volume_path = tmp_path / "railway-volume"
    return Settings(
        profile=DeliveryProfile.HOSTED,
        state_root=volume_path / "core",
        railway_volume_path=volume_path,
        public_origin="https://demo.example.com",
        release_candidate_id="rc-2026-08-05",
        build_manifest_id="build-2026-08-05",
    )


@pytest.mark.parametrize("profile", list(DeliveryProfile))
def test_delivery_profiles_share_one_typed_configuration_contract(
    tmp_path: Path,
    profile: DeliveryProfile,
) -> None:
    if profile is DeliveryProfile.HOSTED:
        settings = hosted_settings(tmp_path)
    else:
        settings = Settings(
            profile=profile,
            state_root=tmp_path / profile.value.lower(),
            public_origin="http://127.0.0.1:8000",
        )

    assert settings.profile is profile
    assert settings.delivery_profile is profile
    assert settings.web_worker_count == 1
    assert settings.sqlite_writer_count == 1
    assert settings.compute_subprocess_count == 1
    assert settings.database_path == settings.state_root / "core.sqlite3"
    assert settings.artifact_root == settings.state_root / "artifacts"
    assert settings.validated_reference_root == (
        settings.artifact_root / "validated-references"
    )


def test_unknown_or_contradictory_delivery_configuration_fails_safely(
    tmp_path: Path,
) -> None:
    with pytest.raises(CoreSafeError) as unknown:
        Settings(profile="UNSUPPORTED")
    assert unknown.value.code is SafeErrorCode.CONFIGURATION_INVALID

    with pytest.raises(CoreSafeError) as contradictory:
        Settings(
            profile=DeliveryProfile.HOSTED,
            delivery_profile=DeliveryProfile.LOCAL_FALLBACK,
            state_root=tmp_path / "state",
            railway_volume_path=tmp_path,
            public_origin="https://demo.example.com",
            release_candidate_id="rc-test",
            build_manifest_id="build-test",
        )
    assert contradictory.value.code is SafeErrorCode.CONFIGURATION_INVALID

    with pytest.raises(CoreSafeError) as local_origin:
        Settings(
            profile=DeliveryProfile.LOCAL_FALLBACK,
            state_root=tmp_path / "local",
            public_origin="https://demo.example.com",
        )
    assert local_origin.value.code is SafeErrorCode.CONFIGURATION_INVALID


def test_hosted_configuration_requires_the_railway_volume_and_release_contract(
    tmp_path: Path,
) -> None:
    with pytest.raises(CoreSafeError) as invalid_hosted:
        Settings(
            profile=DeliveryProfile.HOSTED,
            state_root=tmp_path / "state",
            public_origin="https://demo.example.com",
        )

    assert invalid_hosted.value.code is SafeErrorCode.CONFIGURATION_INVALID


def test_runtime_fingerprint_records_release_identity_without_infrastructure(
    tmp_path: Path,
) -> None:
    settings = hosted_settings(tmp_path)

    assert settings.runtime_fingerprint.model_dump(mode="json") == {
        "schema_version": "runtime-fingerprint.v1",
        "profile": "HOSTED",
        "release_candidate_id": "rc-2026-08-05",
        "build_manifest_id": "build-2026-08-05",
    }
