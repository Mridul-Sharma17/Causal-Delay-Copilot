from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from backend.app.reference_fallback import (
    ReferenceFallbackError,
    ReferenceFallbackIdentity,
    build_reference_fallback,
    launch_reference_fallback,
    verify_reference_fallback,
)


def test_reference_fallback_requires_a_declared_interactive_failure_and_renders_identity(
    tmp_path: Path,
) -> None:
    identity = ReferenceFallbackIdentity(
        capture_id="capture-20260811-01",
        run_id="analysis-run-12345678-1234-4234-8234-123456789abc",
        release_candidate_id="release-20260811",
    )

    with pytest.raises(ReferenceFallbackError):
        build_reference_fallback(
            tmp_path / "fallback",
            identity=identity,
            interactive_failure_code="",
        )

    root = tmp_path / "fallback"
    build_reference_fallback(
        root,
        identity=identity,
        interactive_failure_code="INTERACTIVE_PATH_FAILED",
    )
    manifest = verify_reference_fallback(root)
    html = (root / "index.html").read_text(encoding="utf-8")

    assert manifest.capture_id == identity.capture_id
    assert manifest.run_id == identity.run_id
    assert manifest.release_candidate_id == identity.release_candidate_id
    assert "reference fallback" in html
    assert identity.capture_id in html
    assert identity.run_id in html
    assert identity.release_candidate_id in html
    assert "fresh computation" in html
    assert "/api/" not in html


def test_reference_fallback_launch_is_a_separate_read_only_static_server(
    tmp_path: Path,
) -> None:
    root = tmp_path / "fallback"
    build_reference_fallback(
        root,
        identity=ReferenceFallbackIdentity(
            capture_id="capture-1",
            run_id="analysis-run-12345678-1234-4234-8234-123456789abc",
            release_candidate_id="release-1",
        ),
        interactive_failure_code="INTERACTIVE_PATH_FAILED",
    )

    server = launch_reference_fallback(
        root,
        interactive_failure_code="INTERACTIVE_PATH_FAILED",
        port=0,
    )
    try:
        origin = f"http://127.0.0.1:{server.port}"
        with urlopen(origin + "/", timeout=2) as response:
            body = response.read().decode("utf-8")
        assert response.status == 200
        assert "reference fallback" in body

        with pytest.raises(HTTPError) as failure:
            urlopen(
                Request(origin + "/", method="POST"),
                timeout=2,
            )
        assert failure.value.code == 405
    finally:
        server.close()
