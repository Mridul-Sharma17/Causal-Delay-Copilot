from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "release_candidate.py"


def run_release(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_manifest_binds_release_inputs_and_emits_an_immutable_id(tmp_path) -> None:
    spa_root = tmp_path / "spa"
    spa_root.mkdir()
    (spa_root / "index.html").write_text("<main>release</main>", encoding="utf-8")
    (spa_root / "assets").mkdir()
    (spa_root / "assets" / "app.js").write_bytes(b"compiled")
    output = tmp_path / "build-manifest.json"

    run_release(
        "build-manifest",
        "--source-root",
        str(ROOT),
        "--source-commit",
        "a" * 40,
        "--release-candidate-id",
        "rc-aaaaaaaaaaaa",
        "--image-digest",
        "sha256:" + "b" * 64,
        "--spa-root",
        str(spa_root),
        "--output",
        str(output),
    )

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "release-build-manifest.v1"
    assert manifest["release_candidate_id"] == "rc-aaaaaaaaaaaa"
    assert manifest["build_manifest_id"].startswith("build-")
    assert manifest["image"]["digest"] == "sha256:" + "b" * 64
    assert manifest["spa"]["digest"].startswith("sha256:")
    assert manifest["lockfiles"]
    assert manifest["bindings"]["migrations"]
    assert manifest["bindings"]["schemas"]
    assert manifest["bindings"]["policies"]
    assert manifest["bindings"]["model_identity"]
    assert manifest["bindings"]["reference_manifests"]


def test_render_release_assets_binds_the_vercel_guard_to_the_same_identity(tmp_path) -> None:
    spa_root = tmp_path / "spa"
    spa_root.mkdir()
    (spa_root / "index.html").write_text("<main>release</main>", encoding="utf-8")
    output = tmp_path / "vercel"

    run_release(
        "render-release-assets",
        "--source-root",
        str(ROOT),
        "--spa-root",
        str(spa_root),
        "--output",
        str(output),
        "--railway-origin",
        "https://railway.example.com",
        "--release-candidate-id",
        "rc-test",
        "--build-manifest-id",
        "build-test",
    )

    release = json.loads((output / "release.json").read_text(encoding="utf-8"))
    assert release["release_candidate_id"] == "rc-test"
    assert release["build_manifest_id"] == "build-test"
    config = json.loads((output / "vercel.json").read_text(encoding="utf-8"))
    assert not any(item["source"] == "/api/:path*" for item in config["rewrites"])
    guard = (output / "api" / "release.ts").read_text(encoding="utf-8")
    assert "rc-test" in guard
    assert "build-test" in guard
    assert "railway.example.com" in guard
    proxy = (output / "api" / "[...path].ts").read_text(encoding="utf-8")
    assert "RELEASE_IDENTITY_MISMATCH" in proxy
    assert "rc-test" in proxy
    assert "build-test" in proxy


def test_manifest_integrity_is_checked_before_remote_preflight(tmp_path) -> None:
    spa_root = tmp_path / "spa"
    spa_root.mkdir()
    (spa_root / "index.html").write_text("<main>release</main>", encoding="utf-8")
    output = tmp_path / "build-manifest.json"
    run_release(
        "build-manifest",
        "--source-root",
        str(ROOT),
        "--source-commit",
        "a" * 40,
        "--release-candidate-id",
        "rc-aaaaaaaaaaaa",
        "--image-digest",
        "sha256:" + "b" * 64,
        "--spa-root",
        str(spa_root),
        "--output",
        str(output),
    )
    manifest = json.loads(output.read_text(encoding="utf-8"))
    manifest["spa"]["file_count"] = 99
    output.write_text(json.dumps(manifest), encoding="utf-8")

    failed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "verify-railway",
            "--manifest",
            str(output),
            "--railway-origin",
            "https://railway.example.com",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert failed.returncode == 2
    assert "RELEASE_MANIFEST_INTEGRITY_INVALID" in failed.stderr


def test_rollback_occurrence_is_append_only_and_does_not_overwrite_history(tmp_path) -> None:
    output = tmp_path / "rollback.json"
    run_release(
        "record-rollback",
        "--output",
        str(output),
        "--from-release-candidate-id",
        "rc-new",
        "--from-build-manifest-id",
        "build-new",
        "--to-release-candidate-id",
        "rc-old",
        "--to-build-manifest-id",
        "build-old",
        "--target-deployment-id",
        "deployment-old",
        "--target-image-ref",
        "ghcr.io/example/core:rc-old",
        "--target-image-digest",
        "sha256:" + "d" * 64,
        "--source-commit",
        "c" * 40,
        "--reason",
        "preflight failure",
    )
    original = output.read_text(encoding="utf-8")
    failed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "record-rollback",
            "--output",
            str(output),
            "--from-release-candidate-id",
            "rc-different",
            "--from-build-manifest-id",
            "build-new",
            "--to-release-candidate-id",
            "rc-old",
            "--to-build-manifest-id",
            "build-old",
            "--target-deployment-id",
            "deployment-old",
            "--target-image-ref",
            "ghcr.io/example/core:rc-old",
            "--target-image-digest",
            "sha256:" + "d" * 64,
            "--source-commit",
            "c" * 40,
            "--reason",
            "preflight failure",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert output.read_text(encoding="utf-8") == original
    occurrence = json.loads(original)
    assert occurrence["kind"] == "RELEASE_ROLLBACK"
    assert occurrence["mutation"] == "NEW_IMMUTABLE_DEPLOYMENT"
    assert occurrence["target_image"]["digest"] == "sha256:" + "d" * 64
