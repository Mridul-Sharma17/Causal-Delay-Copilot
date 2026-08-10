from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile
from typing import Any
from uuid import uuid4

from .errors import CoreSafeError
from .references import ReferenceVerificationError, ValidatedReferenceStore
from .recovery import StateRecovery
from .settings import DeliveryProfile, Settings
from .state import StateRoot


LOCAL_FALLBACK_PORT = 8000
LOCAL_FALLBACK_HOST = "127.0.0.1"
LOCAL_FALLBACK_ORIGIN = f"http://{LOCAL_FALLBACK_HOST}:{LOCAL_FALLBACK_PORT}"
SETUP_SUCCESS_SCHEMA_VERSION = "local-fallback-setup.v1"
SETUP_SUCCESS_FILENAME = "setup_success.json"
_SETUP_SOURCE_FILES = (
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)


class LocalFallbackPreflightError(RuntimeError):
    """A redacted, actionable local startup failure."""

    def __init__(self, code: str, recovery_action: str) -> None:
        self.code = code
        self.recovery_action = recovery_action
        super().__init__(f"{code}: {recovery_action}")


@dataclass(frozen=True, slots=True)
class LocalFallbackPreflightReport:
    interpreter_state: str
    build_state: str
    state_state: str
    reference_manifest_state: str
    writable_state: str
    port_state: str
    setup_state: str
    readiness_state: str

    def as_dict(self) -> dict[str, str]:
        return {
            "status": "READY",
            "interpreter": self.interpreter_state,
            "build": self.build_state,
            "state": self.state_state,
            "reference_manifest": self.reference_manifest_state,
            "writable_locations": self.writable_state,
            "port": self.port_state,
            "setup": self.setup_state,
            "readiness": self.readiness_state,
        }


def _fail(code: str, recovery_action: str) -> None:
    raise LocalFallbackPreflightError(code, recovery_action)


def _regular_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False


def _regular_directory(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, ValueError) as error:
        raise LocalFallbackPreflightError(
            "SETUP_NOT_COMPLETED",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    return digest.hexdigest()


def _directory_digest(path: Path) -> str:
    if not _regular_directory(path):
        _fail("SPA_BUILD_UNAVAILABLE", "RUN_SETUP_PS1_WHILE_ONLINE")
    digest = hashlib.sha256()
    files: list[Path] = []
    try:
        for candidate in path.rglob("*"):
            if candidate.is_symlink():
                _fail("SPA_BUILD_UNAVAILABLE", "RUN_SETUP_PS1_WHILE_ONLINE")
            if candidate.is_file():
                files.append(candidate)
    except OSError as error:
        raise LocalFallbackPreflightError(
            "SPA_BUILD_UNAVAILABLE",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    if not files or not _regular_file(path / "index.html"):
        _fail("SPA_BUILD_UNAVAILABLE", "RUN_SETUP_PS1_WHILE_ONLINE")
    try:
        for candidate in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
            relative = candidate.relative_to(path).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(candidate.read_bytes())
            digest.update(b"\0")
    except OSError as error:
        raise LocalFallbackPreflightError(
            "SPA_BUILD_UNAVAILABLE",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    return digest.hexdigest()


def _source_digests(project_root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for relative in _SETUP_SOURCE_FILES:
        path = project_root / relative
        if not _regular_file(path):
            _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")
        digests[relative] = _sha256_file(path)
    return digests


def _playwright_chromium_ready(project_root: Path) -> bool:
    package_root = project_root / "node_modules" / "playwright-core"
    browser_root = package_root / ".local-browsers"
    metadata_path = package_root / "browsers.json"
    if not _regular_directory(browser_root) or not _regular_file(metadata_path):
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        browsers = metadata.get("browsers")
        chromium = next(
            browser
            for browser in browsers
            if browser.get("name") == "chromium"
        )
        revision = chromium["revision"]
        if not isinstance(revision, str) or not revision.isdigit():
            return False
        installation = browser_root / f"chromium-{revision}"
        if not _regular_directory(installation):
            return False
        executable_candidates = {
            "Windows": (
                installation / "chrome-win64" / "chrome.exe",
                installation / "chrome-win" / "chrome.exe",
            ),
            "Darwin": (
                installation / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            ),
        }.get(
            platform.system(),
            (installation / "chrome-linux" / "chrome",),
        )
        return any(
            _regular_file(candidate) and candidate.stat().st_size > 0
            for candidate in executable_candidates
        )
    except (
        OSError,
        AttributeError,
        TypeError,
        KeyError,
        StopIteration,
        UnicodeError,
        json.JSONDecodeError,
    ):
        return False


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as error:
        raise LocalFallbackPreflightError(
            "SETUP_RECORD_FAILED",
            "RUN_SETUP_PS1_AGAIN",
        ) from error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LocalFallbackPreflightError(
            "SETUP_NOT_COMPLETED",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    if not isinstance(value, dict):
        _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")
    return value


def _check_writable(path: Path) -> None:
    if not _regular_directory(path):
        _fail("WRITABLE_LOCATION_UNAVAILABLE", "RUN_SETUP_PS1_WHILE_ONLINE")
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=".local-fallback-preflight-",
            dir=str(path),
        )
        temporary = Path(name)
        os.write(descriptor, b"preflight")
        os.fsync(descriptor)
    except (OSError, ValueError) as error:
        raise LocalFallbackPreflightError(
            "WRITABLE_LOCATION_UNAVAILABLE",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _port_available(host: str, port: int) -> bool:
    if host != LOCAL_FALLBACK_HOST or port != LOCAL_FALLBACK_PORT:
        return False
    socket_address = (host, port)
    socket_instance = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        socket_instance.bind(socket_address)
        return True
    except OSError:
        return False
    finally:
        socket_instance.close()


def _validate_setup_record(
    record: dict[str, Any],
    *,
    project_root: Path,
    settings: Settings,
    interpreter_path: Path,
    spa_dist_digest: str,
) -> None:
    expected = {
        "schema_version": SETUP_SUCCESS_SCHEMA_VERSION,
        "status": "SUCCEEDED",
        "profile": DeliveryProfile.LOCAL_FALLBACK.value,
        "python_version": platform.python_version(),
        "release_candidate_id": settings.release_candidate_id,
        "build_manifest_id": settings.build_manifest_id,
        "playwright_browsers_path": "0",
        "playwright_chromium_ready": True,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")
    if not interpreter_path.is_file() or Path(sys.executable).resolve() != interpreter_path.resolve():
        _fail("PYTHON_RUNTIME_UNSUPPORTED", "RUN_SETUP_PS1_WHILE_ONLINE")
    if record.get("source_digests") != _source_digests(project_root):
        _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")
    if record.get("spa_dist_digest") != spa_dist_digest:
        _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")


def preflight_local_fallback(
    project_root: Path,
    settings: Settings,
    *,
    interpreter_path: Path | None = None,
    port: int = LOCAL_FALLBACK_PORT,
    require_setup_success: bool = True,
) -> LocalFallbackPreflightReport:
    """Validate the prepared local profile without mutating application state."""

    project_root = project_root.resolve()
    interpreter = (interpreter_path or Path(sys.executable)).resolve()
    if settings.profile is not DeliveryProfile.LOCAL_FALLBACK:
        _fail("DELIVERY_PROFILE_INVALID", "USE_LOCAL_FALLBACK_CONFIGURATION")
    if (
        settings.bind_host != LOCAL_FALLBACK_HOST
        or settings.public_origin != LOCAL_FALLBACK_ORIGIN
        or not settings.offline_startup
        or settings.web_worker_count != 1
        or settings.sqlite_writer_count != 1
        or settings.compute_subprocess_count != 1
    ):
        _fail("DELIVERY_PROFILE_INVALID", "USE_LOCAL_FALLBACK_CONFIGURATION")
    expected_python = project_root / ".python-version"
    try:
        expected_python_version = expected_python.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise LocalFallbackPreflightError(
            "PYTHON_RUNTIME_UNSUPPORTED",
            "RUN_SETUP_PS1_WHILE_ONLINE",
        ) from error
    if not _regular_file(expected_python) or platform.python_version() != expected_python_version:
        _fail("PYTHON_RUNTIME_UNSUPPORTED", "RUN_SETUP_PS1_WHILE_ONLINE")
    if not interpreter.is_file() or Path(sys.executable).resolve() != interpreter:
        _fail("PYTHON_RUNTIME_UNSUPPORTED", "RUN_SETUP_PS1_WHILE_ONLINE")

    dist = settings.spa_dist_dir or project_root / "frontend" / "dist"
    spa_dist_digest = _directory_digest(dist)
    if not _playwright_chromium_ready(project_root):
        _fail("PLAYWRIGHT_CHROMIUM_UNAVAILABLE", "RUN_SETUP_PS1_WHILE_ONLINE")

    try:
        layout = StateRoot(settings).validate_sealed()
    except CoreSafeError as error:
        code = getattr(error.code, "value", str(error.code))
        raise LocalFallbackPreflightError(code, "RESTORE_CORE_STATE_AND_RETRY") from error

    for writable in (layout.runtime_root, layout.artifact_root, layout.temporary_root):
        _check_writable(writable)

    setup_path = layout.runtime_root / SETUP_SUCCESS_FILENAME
    if require_setup_success:
        if not _regular_file(setup_path):
            _fail("SETUP_NOT_COMPLETED", "RUN_SETUP_PS1_WHILE_ONLINE")
        _validate_setup_record(
            _read_json(setup_path),
            project_root=project_root,
            settings=settings,
            interpreter_path=interpreter,
            spa_dist_digest=spa_dist_digest,
        )

    reference_store = ValidatedReferenceStore(
        settings.artifact_root,
        release_candidate_id=settings.release_candidate_id,
        runtime_fingerprint=settings.runtime_fingerprint.model_dump(mode="json"),
    )
    registry_path = reference_store.registry_path
    if registry_path.exists() and not reference_store.registry_present:
        _fail("REFERENCE_MANIFEST_INVALID", "RESTORE_OR_REINSTALL_CURRENT_RELEASE")
    reference_manifest_state = "UNAVAILABLE"
    if reference_store.registry_present:
        try:
            reference_store.validate_current_release_manifest()
        except ReferenceVerificationError as error:
            raise LocalFallbackPreflightError(
                "REFERENCE_MANIFEST_INVALID",
                "RESTORE_OR_REINSTALL_CURRENT_RELEASE",
            ) from error
        reference_manifest_state = "VERIFIED"

    if not _port_available(settings.bind_host, port):
        _fail("LOCAL_PORT_UNAVAILABLE", "STOP_THE_EXISTING_LOCAL_CORE_AND_RETRY")

    return LocalFallbackPreflightReport(
        interpreter_state="VERIFIED",
        build_state="VERIFIED",
        state_state="VERIFIED",
        reference_manifest_state=reference_manifest_state,
        writable_state="VERIFIED",
        port_state="AVAILABLE",
        setup_state="VERIFIED" if require_setup_success else "PENDING_RECORD",
        readiness_state=(
            "READY" if settings.gemini_configured else "DEGRADED_GEMINI_ONLY"
        ),
    )


def record_setup_success(
    project_root: Path,
    settings: Settings,
    *,
    interpreter_path: Path,
    node_version: str,
) -> dict[str, Any]:
    """Record setup only after the non-mutating preparation checks pass."""

    report = preflight_local_fallback(
        project_root,
        settings,
        interpreter_path=interpreter_path,
        require_setup_success=False,
    )
    if not node_version.strip():
        _fail("SETUP_RECORD_FAILED", "RUN_SETUP_PS1_AGAIN")
    layout = StateRoot(settings).validate_sealed()
    dist = settings.spa_dist_dir or project_root / "frontend" / "dist"
    payload: dict[str, Any] = {
        "schema_version": SETUP_SUCCESS_SCHEMA_VERSION,
        "status": "SUCCEEDED",
        "profile": DeliveryProfile.LOCAL_FALLBACK.value,
        "python_version": platform.python_version(),
        "node_version": node_version.strip(),
        "playwright_browsers_path": "0",
        "playwright_chromium_ready": True,
        "release_candidate_id": settings.release_candidate_id,
        "build_manifest_id": settings.build_manifest_id,
        "source_digests": _source_digests(project_root),
        "spa_dist_digest": _directory_digest(dist),
        "readiness_state": report.readiness_state,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_atomic_json(layout.runtime_root / SETUP_SUCCESS_FILENAME, payload)
    StateRecovery(settings).finalize_baseline_after_setup()
    return payload


def initialize_local_fallback(settings: Settings) -> None:
    """Create the sealed local state once; never repair an existing root."""

    if settings.profile is not DeliveryProfile.LOCAL_FALLBACK:
        _fail("DELIVERY_PROFILE_INVALID", "USE_LOCAL_FALLBACK_CONFIGURATION")
    StateRoot(settings).initialize()
    StateRecovery(settings).ensure_baseline()


def _settings_from_environment() -> Settings:
    try:
        return Settings()
    except CoreSafeError as error:
        code = getattr(error.code, "value", str(error.code))
        raise LocalFallbackPreflightError(code, "CORRECT_CONFIGURATION_AND_RETRY") from error


def _command_result(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepared local fallback lifecycle contract")
    parser.add_argument(
        "command",
        choices=("initialize", "preflight", "record-setup-success"),
    )
    parser.add_argument("--allow-unrecorded-setup", action="store_true")
    parser.add_argument("--node-version", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parse_args(argv)
        settings = _settings_from_environment()
        project_root = Path.cwd()
        if arguments.command == "initialize":
            initialize_local_fallback(settings)
            return _command_result({"status": "INITIALIZED"})
        if arguments.command == "record-setup-success":
            payload = record_setup_success(
                project_root,
                settings,
                interpreter_path=Path(sys.executable),
                node_version=arguments.node_version,
            )
            return _command_result(
                {
                    "status": payload["status"],
                    "schema_version": payload["schema_version"],
                }
            )
        report = preflight_local_fallback(
            project_root,
            settings,
            interpreter_path=Path(sys.executable),
            require_setup_success=not arguments.allow_unrecorded_setup,
        )
        return _command_result(report.as_dict())
    except LocalFallbackPreflightError as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "code": error.code,
                    "recovery_action": error.recovery_action,
                },
                sort_keys=True,
            )
        )
        return 1
    except CoreSafeError as error:
        code = getattr(error.code, "value", str(error.code))
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "code": code,
                    "recovery_action": "CORRECT_CONFIGURATION_AND_RETRY",
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
