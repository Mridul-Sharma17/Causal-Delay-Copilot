from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings


def test_release_identity_endpoint_exposes_only_the_public_release_binding(tmp_path) -> None:
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=tmp_path / "state",
        public_origin="http://127.0.0.1:8000",
        release_candidate_id="rc-test",
        build_manifest_id="build-test",
    )

    with TestClient(create_app(settings, start_operation_runner=False)) as client:
        response = client.get("/api/release")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "release-identity.v1",
        "profile": "LOCAL_FALLBACK",
        "release_candidate_id": "rc-test",
        "build_manifest_id": "build-test",
    }
    assert "gemini" not in response.text.lower()
