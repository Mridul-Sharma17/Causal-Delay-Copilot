from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

from backend.app.local_fallback import (
    LocalFallbackPreflightError,
    preflight_local_fallback,
    record_setup_success,
)
from backend.app.settings import DeliveryProfile, Settings
from backend.app.state import StateRoot


ROOT = Path(__file__).parents[2]


def _settings(project_root: Path, state_root: Path) -> Settings:
    return Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
        release_candidate_id="local-fallback",
        build_manifest_id="local-fallback",
        spa_dist_dir=project_root / "frontend" / "dist",
    )


def _prepared_project(tmp_path: Path) -> tuple[Path, Settings]:
    project_root = tmp_path / "project"
    project_root.mkdir()
    for relative in (
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
    ):
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)

    dist = project_root / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")

    package_root = project_root / "node_modules" / "playwright-core"
    package_root.mkdir(parents=True)
    (package_root / "browsers.json").write_text(
        json.dumps({"browsers": [{"name": "chromium", "revision": "1"}]}),
        encoding="utf-8",
    )
    browser = package_root / ".local-browsers" / "chromium-1" / "chrome-win64"
    browser.mkdir(parents=True)
    (browser / "chrome.exe").write_bytes(b"prepared")

    state_root = project_root / "state"
    settings = _settings(project_root, state_root)
    StateRoot(settings).initialize()
    return project_root, settings


def test_preflight_requires_a_completed_setup_record(tmp_path: Path) -> None:
    project_root, settings = _prepared_project(tmp_path)

    with pytest.raises(LocalFallbackPreflightError) as failure:
        preflight_local_fallback(
            project_root,
            settings,
            interpreter_path=Path(sys.executable),
        )

    assert failure.value.code == "SETUP_NOT_COMPLETED"


def test_recorded_setup_preflight_keeps_missing_reference_explicitly_unavailable(
    tmp_path: Path,
) -> None:
    project_root, settings = _prepared_project(tmp_path)
    record_setup_success(
        project_root,
        settings,
        interpreter_path=Path(sys.executable),
        node_version="v22.12.0",
    )

    report = preflight_local_fallback(
        project_root,
        settings,
        interpreter_path=Path(sys.executable),
    )

    assert report.reference_manifest_state == "UNAVAILABLE"
    assert report.readiness_state == "DEGRADED_GEMINI_ONLY"


def test_preflight_rejects_a_present_but_invalid_current_release_manifest(
    tmp_path: Path,
) -> None:
    project_root, settings = _prepared_project(tmp_path)
    record_setup_success(
        project_root,
        settings,
        interpreter_path=Path(sys.executable),
        node_version="v22.12.0",
    )
    registry = settings.artifact_root / "releases" / "local-fallback" / "validated-references.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"registry_schema_version": "wrong"}), encoding="utf-8")

    with pytest.raises(LocalFallbackPreflightError) as failure:
        preflight_local_fallback(
            project_root,
            settings,
            interpreter_path=Path(sys.executable),
        )

    assert failure.value.code == "REFERENCE_MANIFEST_INVALID"


def test_preflight_rejects_source_changes_after_setup(tmp_path: Path) -> None:
    project_root, settings = _prepared_project(tmp_path)
    record_setup_success(
        project_root,
        settings,
        interpreter_path=Path(sys.executable),
        node_version="v22.12.0",
    )
    (project_root / "package.json").write_text(
        (project_root / "package.json").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LocalFallbackPreflightError) as failure:
        preflight_local_fallback(
            project_root,
            settings,
            interpreter_path=Path(sys.executable),
        )

    assert failure.value.code == "SETUP_NOT_COMPLETED"


def test_launcher_contracts_are_explicit_and_startup_is_install_free() -> None:
    setup = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8")
    start = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    common = (ROOT / "scripts" / "local-fallback-common.ps1").read_text(encoding="utf-8")

    assert "npm.cmd ci" in setup
    assert "uv.exe sync --locked" in setup
    assert "PLAYWRIGHT_BROWSERS_PATH" in setup
    assert "node_modules\\.bin\\playwright.cmd" in setup
    assert "playwrightCommand install chromium" in setup
    assert "npm.cmd exec" not in setup
    assert "npm.cmd run build" in setup
    assert "record-setup-success" in setup

    launcher = start + common
    assert ".venv\\Scripts\\python.exe" in start
    assert "--workers 1" in launcher
    assert "127.0.0.1" in launcher
    assert "/api/health/live" in launcher
    assert "/api/health/ready" in launcher
    assert "preflight" in start
    assert "npm.cmd" not in start
    assert "uv.exe sync" not in start
    assert "playwright install" not in start
    assert "npm.cmd" not in common
    assert "uv.exe sync" not in common
    assert "playwright install" not in common
