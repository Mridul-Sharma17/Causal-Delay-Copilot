"""Qualify the Windows Local Fallback profile from recorded CLI evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor
import http.cookiejar

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.canonical import sha256
from backend.app.local_qualification import (
    REQUIRED_LOCAL_CHECK_IDS,
    build_local_qualification,
    write_local_qualification,
)
from backend.app.references import ReferenceVerificationError, ValidatedReferenceStore
from backend.app.settings import DeliveryProfile, Settings


ORIGIN = "http://127.0.0.1:8000"
RELEASE_CANDIDATE_ID = "local-fallback"
BUILD_MANIFEST_ID = "local-fallback"
PLAYWRIGHT_VERSION = "1.58.2"
QUALIFICATION_TIMEOUT_SECONDS = 300.0
FORBIDDEN_STARTUP_COMMANDS = re.compile(
    r"(?im)^\s*(?:&\s*)?(?:npm(?:\.cmd)?|uv(?:\.exe)?)\s+"
)
POSITIVE_PRACTITIONER_CLAIM = re.compile(
    r"\b(?:practitioner|clinical|production)\s+(?:validated|approved|confirmed)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandLedger:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root.resolve()
        self.records: list[dict[str, Any]] = []

    def run(
        self,
        arguments: list[str],
        *,
        cli: str,
        version: str,
        target: str,
        env: Mapping[str, str] | None = None,
        timeout: float = 120.0,
    ) -> CommandResult:
        started_at = datetime.now(timezone.utc)
        started = time.monotonic()
        merged_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("CORE_")
        }
        if env:
            merged_env.update(env)
        try:
            completed = subprocess.run(
                [str(argument) for argument in arguments],
                cwd=ROOT,
                env=merged_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            result = CommandResult(
                completed.returncode,
                completed.stdout,
                completed.stderr,
            )
        except (OSError, subprocess.SubprocessError) as error:
            result = CommandResult(127, "", str(error))
        finished_at = datetime.now(timezone.utc)
        self.records.append(
            {
                "command": self.display_command(arguments),
                "cli": cli,
                "version": version,
                "target": target,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
                "exit_status": result.returncode,
                "redacted_output_digest": sha256(
                    (result.stdout + result.stderr).encode("utf-8")
                ),
            }
        )
        return result

    def observation(
        self,
        command: str,
        *,
        target: str,
        payload: Mapping[str, Any],
        exit_status: int,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.records.append(
            {
                "command": command,
                "cli": "qualification-http",
                "version": "stdlib-urllib",
                "target": target,
                "started_at": now,
                "finished_at": now,
                "duration_ms": 0,
                "exit_status": exit_status,
                "redacted_output_digest": sha256(payload),
            }
        )

    def display_command(self, arguments: list[str]) -> str:
        text = " ".join(str(argument) for argument in arguments)
        text = text.replace(str(ROOT), "<repo>")
        text = text.replace(str(self.state_root), "<state-root>")
        return text


class LocalQualificationCollector:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root.resolve()
        self.ledger = CommandLedger(self.state_root)
        self.checks: dict[str, dict[str, Any]] = {
            check_id: {
                "check_id": check_id,
                "status": "NOT_RUN",
                "code": "CHECK_NOT_RUN",
                "evidence": {},
            }
            for check_id in REQUIRED_LOCAL_CHECK_IDS
        }
        self.platform: dict[str, Any] = {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "node_version": "UNAVAILABLE",
            "playwright_version": PLAYWRIGHT_VERSION,
            "network_state": "EXTERNAL_NETWORK_UNAVAILABLE",
        }
        self.dataset_version_id: str | None = None
        self.fresh_runs: list[dict[str, Any]] = []

    def collect(self) -> dict[str, Any]:
        source_commit = self._record_runtime_versions()
        self._run_online_setup()
        self._prepare_real_journey()
        self._run_offline_startup()
        self._run_browser_and_fresh_runs()
        self._run_evidence_pack_checks()
        self._run_recovery_checks()
        self._run_relevant_suite()
        target = {
            "profile": DeliveryProfile.LOCAL_FALLBACK.value,
            "host": "Windows",
            "origin": ORIGIN,
            "network_policy": "EXTERNAL_NETWORK_UNAVAILABLE",
        }
        return build_local_qualification(
            source_commit=source_commit,
            release_candidate_id=RELEASE_CANDIDATE_ID,
            build_manifest_id=BUILD_MANIFEST_ID,
            target=target,
            checks=self.checks.values(),
            commands=self.ledger.records,
            platform=self.platform,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _record_runtime_versions(self) -> str:
        git = self.ledger.run(
            ["git", "rev-parse", "HEAD"],
            cli="git",
            version="repository",
            target="source",
        )
        source_commit = git.stdout.strip()
        if git.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", source_commit):
            raise RuntimeError("SOURCE_COMMIT_UNAVAILABLE")
        status = self.ledger.run(
            ["git", "status", "--porcelain"],
            cli="git",
            version="repository",
            target="source",
        )
        if status.returncode != 0 or status.stdout.strip():
            raise RuntimeError("SOURCE_WORKTREE_NOT_CLEAN")
        node = self._record_version(["node", "--version"], "node")
        if node.returncode == 0 and node.stdout.strip():
            self.platform["node_version"] = node.stdout.strip()
        for executable, cli in (
            ("uv.exe", "uv"),
            ("npm.cmd", "npm"),
            (".venv\\Scripts\\python.exe", "python"),
            ("node_modules\\.bin\\playwright.cmd", "playwright"),
        ):
            self._record_version(
                [executable, "--version"],
                cli,
            )
        return source_commit

    def _record_version(self, arguments: list[str], cli: str) -> CommandResult:
        result = self.ledger.run(
            arguments,
            cli=cli,
            version="observed",
            target="local-fallback",
        )
        if result.returncode == 0 and result.stdout.strip():
            self.ledger.records[-1]["version"] = result.stdout.strip().splitlines()[0]
        return result

    def _prepare_real_journey(self) -> None:
        result = self.ledger.run(
            [
                "uv.exe",
                "--cache-dir",
                ".uv-cache",
                "run",
                "--locked",
                "--no-sync",
                "python",
                "-m",
                "scripts.prepare_core_journey",
                "--state-root",
                str(self.state_root),
                "--profile",
                "LOCAL_FALLBACK",
                "--public-origin",
                ORIGIN,
                "--spa-dist-dir",
                str(ROOT / "frontend" / "dist"),
                "--release-candidate-id",
                RELEASE_CANDIDATE_ID,
                "--build-manifest-id",
                BUILD_MANIFEST_ID,
            ],
            cli="uv",
            version="observed",
            target="local-fallback-state",
            env={
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
                "CORE_REQUIRE_FRESH_DEMO_QUALIFICATION": "false",
            },
            timeout=QUALIFICATION_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            self._set_all_unavailable("REAL_JOURNEY_PREPARATION_FAILED")
            return
        marker = re.search(r"CORE_JOURNEY_PREPARED (\{.*\})", result.stdout)
        if marker is None:
            self._set_all_unavailable("REAL_JOURNEY_METADATA_UNAVAILABLE")
            return
        try:
            prepared = json.loads(marker.group(1))
            value = prepared.get("dataset_version_id")
            if isinstance(value, str) and value:
                self.dataset_version_id = value
            else:
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            self._set_all_unavailable("REAL_JOURNEY_METADATA_UNAVAILABLE")

    def _run_online_setup(self) -> None:
        result = self.ledger.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts\\setup.ps1",
                "-StateRoot",
                str(self.state_root),
            ],
            cli="powershell",
            version="Windows PowerShell",
            target="online-setup",
            env={
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
                "CORE_REQUIRE_FRESH_DEMO_QUALIFICATION": "false",
            },
            timeout=900.0,
        )
        self._set(
            "online_setup",
            "VERIFIED" if result.returncode == 0 else "BLOCKED",
            "ONLINE_SETUP_VERIFIED" if result.returncode == 0 else "ONLINE_SETUP_FAILED",
            {
                "exit_status": result.returncode,
                "network_state": "ONLINE",
                "setup_success_hash": self._file_hash(
                    self.state_root / "runtime" / "setup_success.json"
                ),
            },
        )

    def _run_offline_startup(self) -> None:
        startup_files = (
            ROOT / "scripts" / "start.ps1",
            ROOT / "scripts" / "local-fallback-common.ps1",
        )
        package_manager_invocations = 0
        for path in startup_files:
            try:
                package_manager_invocations += len(
                    FORBIDDEN_STARTUP_COMMANDS.findall(path.read_text(encoding="utf-8"))
                )
            except (OSError, UnicodeError):
                package_manager_invocations += 1
        result = self.ledger.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts\\start.ps1",
                "-SmokeOnly",
                "-NoBrowser",
                "-QualificationRun",
                "-StateRoot",
                str(self.state_root),
            ],
            cli="powershell",
            version="Windows PowerShell",
            target="offline-startup",
            env={
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "CORE_REQUIRE_FRESH_DEMO_QUALIFICATION": "false",
            },
            timeout=120.0,
        )
        passed = result.returncode == 0 and package_manager_invocations == 0
        self._set(
            "offline_startup",
            "VERIFIED" if passed else "BLOCKED",
            "OFFLINE_STARTUP_VERIFIED" if passed else "OFFLINE_STARTUP_FAILED",
            {
                "exit_status": result.returncode,
                "network_state": "EXTERNAL_NETWORK_UNAVAILABLE",
                "package_manager_invocations": package_manager_invocations,
            },
        )

    def _run_browser_and_fresh_runs(self) -> None:
        if self.dataset_version_id is None:
            self._set("browser_reference_journey", "BLOCKED", "BROWSER_STATE_UNAVAILABLE", {})
            self._set("browser_abstention_boundary", "BLOCKED", "BROWSER_STATE_UNAVAILABLE", {})
            self._set("fresh_runs_under_five_minutes", "BLOCKED", "FRESH_STATE_UNAVAILABLE", {})
            return

        try:
            server = self._start_server()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            code = str(error) or "LOCAL_SERVER_NOT_READY"
            self._set("browser_reference_journey", "BLOCKED", code, {})
            self._set("browser_abstention_boundary", "BLOCKED", code, {})
            self._set("fresh_runs_under_five_minutes", "BLOCKED", code, {})
            self._set("accessibility", "BLOCKED", code, {})
            return
        try:
            browser = self.ledger.run(
                [
                    "node_modules\\.bin\\playwright.cmd",
                    "test",
                    "tests/e2e/core_journey.spec.ts",
                    "tests/e2e/local_qualification.spec.ts",
                    "tests/e2e/accessibility.spec.ts",
                    "--config",
                    "playwright.config.ts",
                    "--workers=1",
                ],
                cli="playwright",
                version=PLAYWRIGHT_VERSION,
                target=ORIGIN,
                env={
                    "CORE_E2E_BASE_URL": ORIGIN,
                    "CORE_PROFILE": "LOCAL_FALLBACK",
                    "CORE_STATE_ROOT": str(self.state_root),
                    "CORE_RELEASE_CANDIDATE_ID": RELEASE_CANDIDATE_ID,
                    "CORE_BUILD_MANIFEST_ID": BUILD_MANIFEST_ID,
                    "CORE_REQUIRE_FRESH_DEMO_QUALIFICATION": "false",
                    "PLAYWRIGHT_BROWSERS_PATH": "0",
                },
                timeout=900.0,
            )
            browser_passed = browser.returncode == 0
            self._set(
                "browser_reference_journey",
                "VERIFIED" if browser_passed else "BLOCKED",
                "BROWSER_REFERENCE_VERIFIED" if browser_passed else "BROWSER_REFERENCE_FAILED",
                {"exit_status": browser.returncode, "test": "core_journey.spec.ts"},
            )
            self._set(
                "browser_abstention_boundary",
                "VERIFIED" if browser_passed else "BLOCKED",
                "BROWSER_REJECTION_BOUNDARY_VERIFIED"
                if browser_passed
                else "BROWSER_REJECTION_BOUNDARY_FAILED",
                {"exit_status": browser.returncode, "test": "local_qualification.spec.ts"},
            )
            self._set(
                "accessibility",
                "VERIFIED" if browser_passed else "BLOCKED",
                "ACCESSIBILITY_BROWSER_VERIFIED"
                if browser_passed
                else "ACCESSIBILITY_BROWSER_FAILED",
                {"exit_status": browser.returncode, "test": "accessibility.spec.ts"},
            )
            self._run_three_fresh_runs()
        finally:
            self._stop_server(server)

    def _start_server(self) -> subprocess.Popen[str]:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts\\start.ps1",
            "-NoBrowser",
            "-QualificationRun",
            "-StateRoot",
            str(self.state_root),
        ]
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith("CORE_")
                },
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
                "CORE_PROFILE": "LOCAL_FALLBACK",
                "CORE_STATE_ROOT": str(self.state_root),
                "CORE_PUBLIC_ORIGIN": ORIGIN,
                "CORE_BIND_HOST": "127.0.0.1",
                "CORE_RELEASE_CANDIDATE_ID": RELEASE_CANDIDATE_ID,
                "CORE_BUILD_MANIFEST_ID": BUILD_MANIFEST_ID,
                "CORE_SPA_DIST_DIR": str(ROOT / "frontend" / "dist"),
                "CORE_OFFLINE_STARTUP": "true",
                "CORE_REQUIRE_FRESH_DEMO_QUALIFICATION": "false",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if not self._wait_ready(process):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            raise RuntimeError("LOCAL_SERVER_NOT_READY")
        self._server_command = command
        self._server_start_elapsed = started
        return process

    def _stop_server(self, process: subprocess.Popen[str]) -> None:
        stop = self.ledger.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts\\stop.ps1",
                "-StateRoot",
                str(self.state_root),
            ],
            cli="powershell",
            version="Windows PowerShell",
            target="offline-stop",
            timeout=60.0,
        )
        if process.poll() is None:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=30)
        self.ledger.records.append(
            {
                "command": self.ledger.display_command(self._server_command),
                "cli": "powershell",
                "version": "Windows PowerShell",
                "target": "local-fallback-server",
                "started_at": datetime.fromtimestamp(
                    time.time() - (time.monotonic() - self._server_start_elapsed),
                    timezone.utc,
                ).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": max(0, int((time.monotonic() - self._server_start_elapsed) * 1000)),
                "exit_status": process.returncode if process.returncode is not None else stop.returncode,
                "redacted_output_digest": sha256(b"local-fallback-server"),
            }
        )

    def _wait_ready(self, process: subprocess.Popen[str]) -> bool:
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return False
            status, _ = self._request("GET", "/api/health/ready")
            if status == 200:
                return True
            time.sleep(0.5)
        return False

    def _run_three_fresh_runs(self) -> None:
        if self.dataset_version_id is None:
            self._set("fresh_runs_under_five_minutes", "BLOCKED", "FRESH_STATE_UNAVAILABLE", {})
            return
        for index in range(3):
            started = time.monotonic()
            session = _HttpSession(self.ledger)
            try:
                workspace_status, workspace = session.request("GET", "/api/workspace")
                if workspace_status != 200 or not isinstance(workspace, Mapping):
                    raise RuntimeError("WORKSPACE_UNAVAILABLE")
                fixture_status, fixture = session.request(
                    "POST",
                    "/api/investigations/reactive/fixtures",
                    {
                        "dataset_version_id": self.dataset_version_id,
                        "fixture_id": "hero-reactive-risk-predictive-baseline-v1",
                    },
                )
                request = (
                    fixture.get("attempt", {}).get("investigation_request_id")
                    if isinstance(fixture, Mapping)
                    else None
                )
                if fixture_status not in {200, 201} or not isinstance(request, str):
                    raise RuntimeError("INVESTIGATION_UNAVAILABLE")
                operation_status, admitted = session.request(
                    "POST",
                    "/api/operations",
                    {
                        "operation_kind": "FRESH_ANALYSIS",
                        "idempotency_key": f"local-qualification-fresh-{index + 1}",
                        "memory_required_bytes": 1024,
                        "request": {
                            "investigation_request_id": request,
                            "root_seed": index + 100,
                        },
                    },
                )
                if operation_status not in {200, 202} or not isinstance(admitted, Mapping):
                    raise RuntimeError("FRESH_OPERATION_NOT_ADMITTED")
                operation = admitted.get("operation")
                operation_id = operation.get("operation_id") if isinstance(operation, Mapping) else None
                if not isinstance(operation_id, str):
                    raise RuntimeError("FRESH_OPERATION_ID_UNAVAILABLE")
                terminal = self._poll_operation(session, operation_id)
                duration_ms = int((time.monotonic() - started) * 1000)
                analysis_run = terminal.get("analysis_run") if isinstance(terminal, Mapping) else None
                if (
                    terminal.get("state") != "SUCCEEDED"
                    or not isinstance(analysis_run, Mapping)
                    or analysis_run.get("lifecycle") != "sealed"
                    or analysis_run.get("verification_state") != "machine_verified"
                    or duration_ms >= 300_000
                ):
                    raise RuntimeError("FRESH_RUN_NOT_VERIFIED_UNDER_FIVE_MINUTES")
                run_id = analysis_run.get("analysis_run_id")
                bundle_hash = analysis_run.get("bundle_manifest_hash")
                if not isinstance(run_id, str) or not isinstance(bundle_hash, str):
                    raise RuntimeError("FRESH_ARTIFACT_IDENTITY_UNAVAILABLE")
                settings = Settings(
                    profile=DeliveryProfile.LOCAL_FALLBACK,
                    state_root=self.state_root,
                    public_origin=ORIGIN,
                    release_candidate_id=RELEASE_CANDIDATE_ID,
                    build_manifest_id=BUILD_MANIFEST_ID,
                )
                verified_hash = ValidatedReferenceStore(
                    settings.artifact_root,
                    release_candidate_id=RELEASE_CANDIDATE_ID,
                    runtime_fingerprint=settings.runtime_fingerprint.model_dump(mode="json"),
                ).verify_analysis_run(run_id)
                if verified_hash != bundle_hash:
                    raise RuntimeError("FRESH_ARTIFACT_HASH_MISMATCH")
                self.fresh_runs.append(
                    {
                        "run_number": index + 1,
                        "duration_ms": duration_ms,
                        "analysis_run_id": run_id,
                        "bundle_manifest_hash": bundle_hash,
                        "verification_state": "machine_verified",
                    }
                )
            except (RuntimeError, ReferenceVerificationError, OSError, TypeError, ValueError) as error:
                self.fresh_runs.append(
                    {
                        "run_number": index + 1,
                        "status": "BLOCKED",
                        "code": str(error),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                )
        passed = len(self.fresh_runs) == 3 and all(
            item.get("verification_state") == "machine_verified"
            and isinstance(item.get("duration_ms"), int)
            and item["duration_ms"] < 300_000
            for item in self.fresh_runs
        )
        self._set(
            "fresh_runs_under_five_minutes",
            "VERIFIED" if passed else "BLOCKED",
            "THREE_FRESH_RUNS_VERIFIED" if passed else "THREE_FRESH_RUNS_NOT_VERIFIED",
            {"runs": self.fresh_runs, "required_count": 3, "limit_ms": 300_000},
        )

    def _poll_operation(self, session: "_HttpSession", operation_id: str) -> Mapping[str, Any]:
        deadline = time.monotonic() + QUALIFICATION_TIMEOUT_SECONDS
        terminal = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "INTERRUPTED", "REJECTED"}
        while time.monotonic() < deadline:
            status, payload = session.request("GET", f"/api/operations/{operation_id}")
            if status != 200 or not isinstance(payload, Mapping):
                raise RuntimeError("FRESH_OPERATION_STATUS_UNAVAILABLE")
            if payload.get("state") in terminal:
                return payload
            time.sleep(0.25)
        raise RuntimeError("FRESH_OPERATION_TIMEOUT")

    def _run_evidence_pack_checks(self) -> None:
        result = self.ledger.run(
            [
                "uv.exe",
                "--cache-dir",
                ".uv-cache",
                "run",
                "--locked",
                "--no-sync",
                "python",
                "scripts/run_scientific_evaluation.py",
                "--verify-pack",
                "tests/fixtures/scientific_evaluation/v1",
            ],
            cli="uv",
            version="observed",
            target="scientific-evaluation-pack",
            timeout=120.0,
        )
        verification = _last_json(result.stdout)
        accepted = (
            result.returncode == 0
            and isinstance(verification, Mapping)
            and verification.get("state") == "ACCEPTED"
        )
        self._set(
            "mandatory_claims",
            "VERIFIED" if accepted else "BLOCKED",
            "MANDATORY_CLAIMS_ACCEPTED" if accepted else "MANDATORY_CLAIMS_UNAVAILABLE",
            {
                "exit_status": result.returncode,
                "pack_state": verification.get("state") if isinstance(verification, Mapping) else "UNAVAILABLE",
            },
        )
        self._set(
            "artifact_integrity",
            "VERIFIED"
            if accepted and all(item.get("verification_state") == "machine_verified" for item in self.fresh_runs)
            else "BLOCKED",
            "ARTIFACT_HASHES_VERIFIED" if accepted else "ARTIFACT_HASHES_UNAVAILABLE",
            {
                "fresh_run_count": len(self.fresh_runs),
                "pack_state": verification.get("state") if isinstance(verification, Mapping) else "UNAVAILABLE",
            },
        )

        required_labels = {
            "SYNTHETIC",
            "TEST_ONLY",
            "NO_PRACTITIONER_VALIDATION",
            "NOT_SHIPPED",
        }
        manifest = ROOT / "tests" / "fixtures" / "decision_support" / "v1" / "manifest.json"
        try:
            body = manifest.read_bytes()
            text = body.decode("utf-8")
            labels_present = all(label in text for label in required_labels)
            no_positive_claim = POSITIVE_PRACTITIONER_CLAIM.search(text) is None
            synthetic_passed = labels_present and no_positive_claim
            manifest_hash = sha256(body)
        except (OSError, UnicodeError):
            synthetic_passed = False
            manifest_hash = None
        self._set(
            "synthetic_fixture_boundary",
            "VERIFIED" if synthetic_passed else "BLOCKED",
            "SYNTHETIC_FIXTURE_BOUNDARY_VERIFIED"
            if synthetic_passed
            else "SYNTHETIC_FIXTURE_BOUNDARY_FAILED",
            {"manifest_hash": manifest_hash, "labels": sorted(required_labels)},
        )

    def _run_recovery_checks(self) -> None:
        result = self.ledger.run(
            [
                "uv.exe",
                "--cache-dir",
                ".uv-cache",
                "run",
                "--locked",
                "--no-sync",
                "pytest",
                "backend/tests/test_local_fallback.py",
                "backend/tests/test_recovery.py",
                "backend/tests/test_reference_fallback.py",
                "--basetemp",
                str(self.state_root.parent / "pytest-recovery"),
            ],
            cli="uv",
            version="observed",
            target="local-recovery-and-reference-fallback",
            env={
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
            },
            timeout=300.0,
        )
        self._set(
            "recovery_and_fallback",
            "VERIFIED" if result.returncode == 0 else "BLOCKED",
            "RECOVERY_AND_FALLBACK_VERIFIED" if result.returncode == 0 else "RECOVERY_AND_FALLBACK_FAILED",
            {"exit_status": result.returncode},
        )

    def _run_relevant_suite(self) -> None:
        result = self.ledger.run(
            [
                "uv.exe",
                "--cache-dir",
                ".uv-cache",
                "run",
                "--locked",
                "--no-sync",
                "pytest",
                "--basetemp",
                ".tmp-pytest-local-qualification-full",
            ],
            cli="uv",
            version="observed",
            target="complete-python-suite",
            env={
                "CORE_GEMINI_ENABLED": "false",
                "CORE_GEMINI_API_KEY": "",
            },
            timeout=900.0,
        )
        self._set(
            "relevant_test_suites",
            "VERIFIED" if result.returncode == 0 else "BLOCKED",
            "RELEVANT_TEST_SUITE_VERIFIED" if result.returncode == 0 else "RELEVANT_TEST_SUITE_FAILED",
            {"exit_status": result.returncode},
        )

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> tuple[int, Any]:
        return _HttpSession(self.ledger).request(method, path, payload)

    def _set(
        self,
        check_id: str,
        status: str,
        code: str,
        evidence: Mapping[str, Any],
    ) -> None:
        self.checks[check_id] = {
            "check_id": check_id,
            "status": status,
            "code": code,
            "evidence": dict(evidence),
        }

    def _set_all_unavailable(self, code: str) -> None:
        for check_id in REQUIRED_LOCAL_CHECK_IDS:
            if self.checks[check_id]["status"] == "NOT_RUN":
                self._set(check_id, "UNAVAILABLE", code, {})

    @staticmethod
    def _file_hash(path: Path) -> str | None:
        try:
            return sha256(path.read_bytes())
        except OSError:
            return None


class _HttpSession:
    def __init__(self, ledger: CommandLedger) -> None:
        self.ledger = ledger
        self.cookies = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[int, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(ORIGIN + path, data=body, headers=headers, method=method)
        status = 0
        raw = ""
        try:
            with self.opener.open(request, timeout=35) as response:
                status = int(response.status)
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            status = int(error.code)
            raw = error.read().decode("utf-8", errors="replace")
        except (OSError, URLError):
            status = 599
        try:
            result: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = {}
        self.ledger.observation(
            f"{method} {path}",
            target="local-fallback-api",
            payload={"status": status, "body_hash": sha256(raw)},
            exit_status=0 if 200 <= status < 400 else 1,
        )
        return status, result


def _last_json(value: str) -> Any:
    for line in reversed(value.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify the Windows Local Fallback and install its immutable attestation."
    )
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for the immutable attestation; defaults to <state-root>/runtime.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state_root = args.state_root.resolve()
    output_dir = (args.output_dir or state_root / "runtime").resolve()
    try:
        payload = LocalQualificationCollector(state_root).collect()
        path = write_local_qualification(output_dir, payload)
    except Exception as error:
        print(
            json.dumps(
                {"status": "BLOCKED", "code": type(error).__name__},
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": payload["qualification_status"],
                "fresh_demo_control": payload["fresh_demo_control"],
                "content_hash": payload["content_hash"],
                "path": str(path),
            },
            sort_keys=True,
        )
    )
    return 0 if payload["qualification_status"] == "QUALIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
