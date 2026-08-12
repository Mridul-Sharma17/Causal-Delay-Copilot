from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.canonical import canonical_json, sha256
from backend.app.hosted_qualification import (
    REQUIRED_HOSTED_CHECK_IDS,
    build_hosted_attestation,
    write_hosted_attestation,
)
from scripts.release_candidate import _expected_identity


RAILWAY_CLI_VERSION = "5.37.4"
VERCEL_CLI_VERSION = "58.9.3"
PLAYWRIGHT_PACKAGE_VERSION = "1.58.2"
FORBIDDEN_PUBLIC_TEXT = re.compile(
    r"\b(?:secret|api[_ -]?key|authorization|password|source rows?|prompts?|"
    r"provider responses?|stack traces?|filesystem paths?|private key)\b",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(r"(?:AQ\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,})")


class QualificationRunError(RuntimeError):
    """A qualification collector failed before it could complete a check."""


def _railway_runtime_root(state_root: str) -> str:
    normalized = state_root.rstrip("/")
    if normalized != "/data" and not normalized.startswith("/data/"):
        raise QualificationRunError("RAILWAY_STATE_ROOT_INVALID")
    return f"{normalized}/runtime"


def _disk_policy_is_safe(
    policy: Mapping[str, Any],
    metric: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(metric, Mapping):
        return False
    warning = policy.get("disk_warning_bytes")
    block = policy.get("disk_block_bytes")
    current_mb = metric.get("current_mb")
    limit_mb = metric.get("limit_mb")
    numeric = (int, float)
    if not all(
        isinstance(value, numeric) and not isinstance(value, bool)
        for value in (warning, block, current_mb, limit_mb)
    ):
        return False
    available_bytes = (float(limit_mb) - float(current_mb)) * 1024 * 1024
    return (
        float(current_mb) >= 0
        and float(limit_mb) > float(current_mb)
        and 0 < int(block)
        and int(block) <= int(warning)
        and int(warning) <= available_bytes
    )


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandLedger:
    def __init__(self) -> None:
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
        display = _display_command(arguments)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            completed = subprocess.run(
                arguments,
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
        redacted = _redact(result.stdout + result.stderr)
        self.records.append(
            {
                "command": display,
                "cli": cli,
                "version": version,
                "target": target,
                "exit_status": result.returncode,
                "redacted_output_digest": sha256(redacted.encode("utf-8")),
            }
        )
        return result


@dataclass(frozen=True, slots=True)
class HttpObservation:
    status: int
    headers: Mapping[str, str]
    body: str
    payload: Mapping[str, Any] | None


class QualificationCollector:
    def __init__(self, args: argparse.Namespace, manifest: Mapping[str, Any]) -> None:
        self.args = args
        self.manifest = manifest
        self.expected = _expected_identity(str(args.release_manifest))
        self.ledger = CommandLedger()
        self.checks: dict[str, dict[str, Any]] = {
            check_id: {
                "check_id": check_id,
                "status": "NOT_RUN",
                "code": "CHECK_NOT_RUN",
                "evidence": {},
            }
            for check_id in REQUIRED_HOSTED_CHECK_IDS
        }
        self.platform: dict[str, Any] = {
            "budget_alert": {
                "state": "UNAVAILABLE",
                "hard_cap": False,
                "code": "RAILWAY_BUDGET_ALERT_CLI_UNAVAILABLE",
            }
        }
        self.railway_status: Mapping[str, Any] = {}
        self.railway_metrics: Mapping[str, Any] = {}
        self.railway_volume: Mapping[str, Any] = {}
        self.runtime_policy: Mapping[str, Any] = {}
        self.runtime_fingerprint: Mapping[str, Any] = {}
        self._raw_logs = ""
        self._railway_logs_exit_status: int | None = None
        self._public_health: HttpObservation | None = None
        self._public_release: HttpObservation | None = None

    def collect(self) -> dict[str, Any]:
        self._record_cli_versions()
        self._record_github_provenance()
        self._probe_release_and_public_surface()
        self._collect_railway_platform()
        self._run_browser_qualification()
        self._qualify_release_mismatch_refusal()
        self._qualify_budget_alert()
        self._qualify_judging_availability()
        target = {
            "profile": "HOSTED",
            "vercel_origin": _origin(self.args.vercel_origin),
            "railway_origin": _origin(self.args.railway_origin),
            "railway_project_id": self.args.railway_project_id,
            "railway_service_id": self.args.railway_service_id,
            "railway_environment_id": self.args.railway_environment_id,
        }
        return build_hosted_attestation(
            source_commit=str(self.manifest["source_commit"]),
            release_candidate_id=self.expected["release_candidate_id"],
            build_manifest_id=self.expected["build_manifest_id"],
            target=target,
            checks=self.checks.values(),
            commands=self.ledger.records,
            platform=self.platform,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _record_cli_versions(self) -> None:
        npx = _npx()
        playwright = self.ledger.run(
            [npx, "--no-install", "playwright", "--version"],
            cli="playwright",
            version=PLAYWRIGHT_PACKAGE_VERSION,
            target="repository-local",
        )
        railway = self.ledger.run(
            [npx, "--yes", f"@railway/cli@{RAILWAY_CLI_VERSION}", "--version"],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        vercel = self.ledger.run(
            [npx, "--yes", f"vercel@{VERCEL_CLI_VERSION}", "--version"],
            cli="vercel",
            version=VERCEL_CLI_VERSION,
            target=self.args.vercel_project_id or "production",
        )
        if playwright.returncode != 0 or railway.returncode != 0 or vercel.returncode != 0:
            raise QualificationRunError("QUALIFICATION_CLI_UNAVAILABLE")

    def _record_github_provenance(self) -> None:
        repository = self.args.github_repository or os.environ.get("GITHUB_REPOSITORY")
        source_commit = str(self.manifest["source_commit"])
        gh_version = self.ledger.run(
            ["gh", "--version"],
            cli="gh",
            version="unknown",
            target="github",
        )
        if gh_version.returncode == 0:
            version_match = re.search(r"gh version ([^\s]+)", gh_version.stdout)
            if version_match:
                self.ledger.records[-1]["version"] = version_match.group(1)
        if not repository:
            self._set(
                "judging_availability",
                "UNAVAILABLE",
                "GITHUB_REPOSITORY_UNAVAILABLE",
                {"source_commit": source_commit},
            )
            return
        result = self.ledger.run(
            [
                "gh",
                "api",
                f"repos/{repository}/commits/{source_commit}",
                "--jq",
                ".sha",
            ],
            cli="gh",
            version="unknown",
            target=f"github:{repository}",
        )
        observed = result.stdout.strip()
        if result.returncode == 0 and observed == source_commit:
            self.platform["github_provenance"] = {
                "repository": repository,
                "source_commit": source_commit,
                "state": "VERIFIED",
            }
        else:
            self.platform["github_provenance"] = {
                "repository": repository,
                "source_commit": source_commit,
                "state": "UNAVAILABLE",
            }

    def _probe_release_and_public_surface(self) -> None:
        vercel_release = self._http_probe(
            self.args.vercel_origin,
            "/api/release",
            target="vercel-public",
        )
        railway_release = self._http_probe(
            self.args.railway_origin,
            "/api/release",
            target="railway-public",
        )
        if not (
            _matches_identity(vercel_release.payload, self.expected)
            and _matches_identity(railway_release.payload, self.expected)
        ):
            self._set(
                "judging_availability",
                "BLOCKED",
                "RELEASE_IDENTITY_MISMATCH",
                {
                    "vercel_status": vercel_release.status,
                    "railway_status": railway_release.status,
                },
            )
        health = self._http_probe(
            self.args.vercel_origin,
            "/api/health",
            target="vercel-public",
        )
        if health.status == 200 and isinstance(health.payload, Mapping) and health.payload.get(
            "state"
        ) in {"ready", "degraded"}:
            self.platform["public_health"] = {
                "state": "VERIFIED",
                "status": health.status,
                "health_state": health.payload.get("state"),
                "health_code": health.payload.get("code"),
            }
        else:
            self._set(
                "judging_availability",
                "BLOCKED",
                "PUBLIC_HEALTH_UNAVAILABLE",
                {"status": health.status},
            )

        reference = self._http_probe(
            self.args.vercel_origin,
            "/api/evidence/reference",
            target="vercel-public",
        )
        if (
            reference.status == 200
            and isinstance(reference.payload, Mapping)
            and reference.payload.get("verification_state") == "reference_validated"
            and reference.payload.get("release_candidate_id")
            == self.expected["release_candidate_id"]
        ):
            self._set(
                "browser_reference_journey",
                "VERIFIED",
                "HOSTED_REFERENCE_VERIFIED",
                {
                    "status": reference.status,
                    "reference_slot_id": reference.payload.get("reference_slot_id"),
                    "bundle_manifest_hash": reference.payload.get("bundle_manifest_hash"),
                },
            )
        else:
            self._set(
                "browser_reference_journey",
                "BLOCKED",
                "HOSTED_REFERENCE_UNAVAILABLE",
                {"status": reference.status, "verification_state": "UNAVAILABLE"},
            )

        root = self._qualify_cache_headers()
        self._qualify_security_headers(root)
        self._public_health = health
        self._public_release = vercel_release

    def _qualify_cache_headers(self) -> HttpObservation:
        root = self._http_probe(self.args.vercel_origin, "/", target="vercel-public")
        health = self._http_probe(
            self.args.vercel_origin,
            "/api/health",
            target="vercel-public",
        )
        release = self._http_probe(
            self.args.vercel_origin,
            "/api/release",
            target="vercel-public",
        )
        no_store = all(
            item.status == 200
            and item.headers.get("cache-control", "").lower() == "no-store"
            for item in (root, health, release)
        )
        asset_state = "NOT_CHECKED"
        asset_available = False
        asset_path = _first_asset_path(root.body)
        if asset_path:
            asset = self._http_probe(
                self.args.vercel_origin,
                asset_path,
                target="vercel-public",
            )
            asset_state = asset.headers.get("cache-control", "")
            asset_available = asset.status == 200
            no_store = no_store and asset_available and asset_state.lower() == (
                "public, max-age=31536000, immutable"
            )
        else:
            no_store = False
        if no_store:
            self._set(
                "no_store_behavior",
                "VERIFIED",
                "CACHE_POLICY_VERIFIED",
                {"asset_cache_control": asset_state},
            )
        else:
            self._set(
                "no_store_behavior",
                "BLOCKED",
                "CACHE_POLICY_MISMATCH",
                {"asset_cache_control": asset_state, "asset_available": asset_available},
            )
        return root

    def _qualify_security_headers(self, root_response: HttpObservation) -> None:
        required = {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "strict-transport-security": "max-age=31536000; includeSubDomains",
        }
        observed = {
            key: root_response.headers.get(key, "")
            for key in required
        }
        passed = root_response.status == 200 and all(
            observed[key].lower() == value.lower() for key, value in required.items()
        )
        csp = root_response.headers.get("content-security-policy", "")
        permissions = root_response.headers.get("permissions-policy", "")
        passed = passed and "default-src 'self'" in csp and "camera=()" in permissions
        self._set(
            "security_headers",
            "VERIFIED" if passed else "BLOCKED",
            "SECURITY_HEADERS_VERIFIED" if passed else "SECURITY_HEADERS_MISMATCH",
            {
                "status": root_response.status,
                "observed": observed,
                "csp_present": bool(csp),
                "permissions_policy_present": bool(permissions),
            },
        )

    def _qualify_redacted_surface(
        self,
        health: HttpObservation,
        release: HttpObservation,
    ) -> None:
        logs = self._raw_logs
        surfaces = " ".join(
            value
            for value in (
                health.body,
                release.body,
                logs if isinstance(logs, str) else "",
            )
        )
        logs_available = self._railway_logs_exit_status == 0
        public_available = health.status == 200 and release.status == 200
        unsafe = FORBIDDEN_PUBLIC_TEXT.search(surfaces) or SECRET_VALUE.search(surfaces)
        passed = logs_available and public_available and not unsafe
        self._set(
            "redacted_health_log_surfaces",
            "VERIFIED" if passed else "BLOCKED",
            "PUBLIC_SURFACE_REDACTED"
            if passed
            else "PUBLIC_SURFACE_LEAKAGE"
            if unsafe
            else "PUBLIC_SURFACE_UNAVAILABLE",
            {
                "health_status": health.status,
                "release_status": release.status,
                "logs_exit_status": self._railway_logs_exit_status,
            },
        )

    def _collect_railway_platform(self) -> None:
        npx = _npx()
        railway_prefix = [npx, "--yes", f"@railway/cli@{RAILWAY_CLI_VERSION}"]
        status_result = self.ledger.run(
            railway_prefix
            + [
                "status",
                "--json",
                "--project",
                self.args.railway_project_id,
                "--environment",
                self.args.railway_environment_id,
            ],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        self.railway_status = _parse_json_output(status_result.stdout)
        volume_result = self.ledger.run(
            railway_prefix
            + [
                "volume",
                "--project",
                self.args.railway_project_id,
                "--environment",
                self.args.railway_environment_id,
                "list",
                "--json",
            ],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        self.railway_volume = _parse_json_output(volume_result.stdout)
        metrics_result = self.ledger.run(
            railway_prefix
            + [
                "metrics",
                "--json",
                "--since",
                "1h",
                "--project",
                self.args.railway_project_id,
                "--service",
                self.args.railway_service_id,
                "--environment",
                self.args.railway_environment_id,
            ],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        self.railway_metrics = _parse_json_output(metrics_result.stdout)
        logs_result = self.ledger.run(
            railway_prefix
            + [
                "logs",
                "--json",
                "--lines",
                "80",
                "--project",
                self.args.railway_project_id,
                "--service",
                self.args.railway_service_id,
                "--environment",
                self.args.railway_environment_id,
            ],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        raw_logs = logs_result.stdout + logs_result.stderr
        self._raw_logs = raw_logs
        self._railway_logs_exit_status = logs_result.returncode
        self._collect_runtime_files(railway_prefix)
        self._qualify_platform_shape()
        if self._public_health is not None and self._public_release is not None:
            self._qualify_redacted_surface(self._public_health, self._public_release)

    def _collect_runtime_files(self, railway_prefix: list[str]) -> None:
        runtime_root = _railway_runtime_root(str(self.args.railway_state_root))
        listing_result = self.ledger.run(
            railway_prefix
            + [
                "service",
                "files",
                "--project",
                self.args.railway_project_id,
                "--service",
                self.args.railway_service_id,
                "--environment",
                self.args.railway_environment_id,
                "list",
                runtime_root,
                "--json",
            ],
            cli="railway",
            version=RAILWAY_CLI_VERSION,
            target=self.args.railway_project_id,
        )
        listing = _parse_json_output(listing_result.stdout)
        self.platform["runtime_files"] = sorted(
            item.get("name")
            for item in listing.get("files", [])
            if isinstance(item, Mapping) and isinstance(item.get("name"), str)
        )
        with tempfile.TemporaryDirectory(prefix="hosted-qualification-") as temporary:
            for name in ("quota_policy.json", "runtime_fingerprint.json"):
                destination = Path(temporary) / name
                result = self.ledger.run(
                    railway_prefix
                    + [
                        "service",
                        "files",
                        "--project",
                        self.args.railway_project_id,
                        "--service",
                        self.args.railway_service_id,
                        "--environment",
                        self.args.railway_environment_id,
                        "download",
                        f"{runtime_root}/{name}",
                        str(destination),
                    ],
                    cli="railway",
                    version=RAILWAY_CLI_VERSION,
                    target=self.args.railway_project_id,
                )
                if result.returncode != 0 or not destination.is_file():
                    continue
                try:
                    payload = json.loads(destination.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if name == "quota_policy.json" and isinstance(payload, Mapping):
                    self.runtime_policy = payload
                if name == "runtime_fingerprint.json" and isinstance(payload, Mapping):
                    self.runtime_fingerprint = payload

    def _qualify_platform_shape(self) -> None:
        service = _service_instance(self.railway_status)
        deployment = _active_deployment(service)
        volume = next(
            (
                item
                for item in self.railway_volume.get("volumes", [])
                if isinstance(item, Mapping) and item.get("mountPath") == "/data"
            ),
            None,
        )
        persistent = isinstance(volume, Mapping) and volume.get("status") == "Ready"
        self._set(
            "persistent_volume",
            "VERIFIED" if persistent else "BLOCKED",
            "PERSISTENT_VOLUME_READY" if persistent else "PERSISTENT_VOLUME_UNAVAILABLE",
            {
                "mount_path": volume.get("mountPath") if isinstance(volume, Mapping) else None,
                "status": volume.get("status") if isinstance(volume, Mapping) else None,
            },
        )

        deploy_config = (
            deployment.get("meta", {}).get("serviceManifest", {}).get("deploy", {})
            if isinstance(deployment, Mapping)
            else {}
        )
        instances = deployment.get("instances", []) if isinstance(deployment, Mapping) else []
        dockerfile = self._source_file("Dockerfile")
        railway_config = self._source_file("railway.toml")
        process_limits = (
            self.runtime_policy.get("max_running_operations") == 1
            and self.runtime_policy.get("max_waiting_operations") == 2
            and self.runtime_policy.get("max_outstanding_operations_per_workspace") == 1
            and 'CORE_WEB_WORKER_COUNT=1' in dockerfile
            and 'CORE_SQLITE_WRITER_COUNT=1' in dockerfile
            and 'CORE_COMPUTE_SUBPROCESS_COUNT=1' in dockerfile
            and '--workers 1' in dockerfile
            and '--workers 1' in railway_config
        )
        self._set(
            "one_writer_process_limits",
            "VERIFIED" if process_limits else "BLOCKED",
            "PROCESS_LIMITS_VERIFIED" if process_limits else "PROCESS_LIMITS_UNAVAILABLE",
            {
                "max_running_operations": self.runtime_policy.get("max_running_operations"),
                "max_waiting_operations": self.runtime_policy.get("max_waiting_operations"),
                "max_outstanding_operations_per_workspace": self.runtime_policy.get(
                    "max_outstanding_operations_per_workspace"
                ),
                "configured_single_worker": 'CORE_WEB_WORKER_COUNT=1' in dockerfile
                and '--workers 1' in railway_config,
                "configured_single_writer": 'CORE_SQLITE_WRITER_COUNT=1' in dockerfile,
                "configured_single_compute_subprocess": 'CORE_COMPUTE_SUBPROCESS_COUNT=1'
                in dockerfile,
                "source_commit": self.manifest["source_commit"],
            },
        )

        serverless_disabled = (
            deploy_config.get("sleepApplication") is False
            and deploy_config.get("cronSchedule") is None
            and deploy_config.get("numReplicas") == 1
            and len(instances) == 1
        )
        self._set(
            "serverless_disabled",
            "VERIFIED" if serverless_disabled else "BLOCKED",
            "SERVERLESS_DISABLED" if serverless_disabled else "SERVERLESS_CONFIGURATION_UNAVAILABLE",
            {
                "sleep_application": deploy_config.get("sleepApplication"),
                "cron_schedule": deploy_config.get("cronSchedule"),
                "replica_count": deploy_config.get("numReplicas"),
                "active_instance_count": len(instances),
            },
        )

        disk_metrics = self.railway_metrics.get("volumes", [])
        metric = next(
            (
                item
                for item in disk_metrics
                if isinstance(item, Mapping) and item.get("mount_path") == "/data"
            ),
            None,
        )
        disk_policy = _disk_policy_is_safe(self.runtime_policy, metric)
        available_mb = (
            metric["limit_mb"] - metric["current_mb"]
            if isinstance(metric, Mapping)
            and isinstance(metric.get("current_mb"), (int, float))
            and isinstance(metric.get("limit_mb"), (int, float))
            else None
        )
        self._set(
            "disk_thresholds",
            "VERIFIED" if disk_policy else "BLOCKED",
            "DISK_THRESHOLDS_VERIFIED"
            if disk_policy
            else "DISK_THRESHOLDS_UNAVAILABLE",
            {
                "warning_bytes": self.runtime_policy.get("disk_warning_bytes"),
                "block_bytes": self.runtime_policy.get("disk_block_bytes"),
                "current_mb": metric.get("current_mb") if isinstance(metric, Mapping) else None,
                "limit_mb": metric.get("limit_mb") if isinstance(metric, Mapping) else None,
                "available_mb": available_mb,
            },
        )

        self.platform["railway_status"] = {
            "service_name": service.get("serviceName") if isinstance(service, Mapping) else None,
            "active_deployment_id": deployment.get("id") if isinstance(deployment, Mapping) else None,
            "active_instance_count": len(instances),
        }
        self.platform["volume_metrics"] = {
            "mount_path": metric.get("mount_path") if isinstance(metric, Mapping) else None,
            "current_mb": metric.get("current_mb") if isinstance(metric, Mapping) else None,
            "limit_mb": metric.get("limit_mb") if isinstance(metric, Mapping) else None,
        }
        self.platform["runtime_policy"] = {
            key: self.runtime_policy.get(key)
            for key in (
                "max_workspaces",
                "max_workspace_mutations",
                "max_workspace_mutations_per_minute",
                "max_global_mutations_per_minute",
                "max_running_operations",
                "max_waiting_operations",
                "max_outstanding_operations_per_workspace",
                "compute_timeout_seconds",
                "disk_warning_bytes",
                "disk_block_bytes",
            )
        }
        self.platform["railway_metrics"] = {
            "cpu_utilization_pct": self.railway_metrics.get("cpu", {}).get("utilization_pct"),
            "memory_utilization_pct": self.railway_metrics.get("memory", {}).get("utilization_pct"),
            "http_error_rate": self.railway_metrics.get("http", {}).get("error_rate"),
        }

    def _run_browser_qualification(self) -> None:
        npx = _npx()
        environment = {
            "CORE_E2E_BASE_URL": _origin(self.args.vercel_origin),
            "HOSTED_QUALIFICATION": "1",
            "HOSTED_RELEASE_CANDIDATE_ID": self.expected["release_candidate_id"],
            "HOSTED_BUILD_MANIFEST_ID": self.expected["build_manifest_id"],
            "HOSTED_MAX_WORKSPACE_MUTATIONS": str(
                self.runtime_policy.get("max_workspace_mutations", 200)
            ),
            "RAILWAY_PROJECT_ID": self.args.railway_project_id,
            "RAILWAY_SERVICE_ID": self.args.railway_service_id,
            "RAILWAY_ENVIRONMENT_ID": self.args.railway_environment_id,
        }
        result = self.ledger.run(
            [
                npx,
                "--no-install",
                "playwright",
                "test",
                self.args.browser_spec,
                "--config",
                "playwright.config.ts",
                "--reporter=json",
            ],
            cli="playwright",
            version=PLAYWRIGHT_PACKAGE_VERSION,
            target=_origin(self.args.vercel_origin),
            env=environment,
            timeout=float(self.args.browser_timeout_seconds),
        )
        report = _parse_json_output(result.stdout)
        if result.returncode != 0 and not report:
            raise QualificationRunError("PLAYWRIGHT_QUALIFICATION_UNAVAILABLE")
        summary = {
            "exit_status": result.returncode,
            "passed_test_count": _playwright_count(report, "expected")[0],
            "failed_test_count": _playwright_count(report, "unexpected")[0],
            "skipped_test_count": _playwright_count(report, "skipped")[0],
        }
        required_test_fragments = (
            "reference journey",
            "workspace isolation",
            "queue saturation",
            "global mutation rate/quota refusal",
        )
        title_states = _playwright_title_states(report)
        missing_tests = [
            fragment
            for fragment in required_test_fragments
            if not any(fragment in title.lower() for title in title_states)
        ]
        if missing_tests:
            raise QualificationRunError("PLAYWRIGHT_QUALIFICATION_TEST_MISSING")
        check_titles = {
            "browser_reference_journey": ("reference journey",),
            "browser_abstention_boundary": ("reference journey",),
            "workspace_isolation": ("workspace isolation",),
            "mutation_rate_and_quota_limits": ("mutation rate/quota refusal",),
            "queue_saturation": ("queue saturation",),
            "restart_recovery": ("queue saturation",),
        }
        for check_id, needles in check_titles.items():
            if self.checks[check_id]["status"] == "BLOCKED":
                continue
            matching = [
                passed_state
                for title, passed_state in title_states.items()
                if any(needle in title.lower() for needle in needles)
            ]
            check_passed = bool(matching) and all(matching)
            self._set(
                check_id,
                "VERIFIED" if check_passed else "BLOCKED",
                "PLAYWRIGHT_QUALIFICATION_PASSED"
                if check_passed
                else "PLAYWRIGHT_QUALIFICATION_FAILED",
                {**summary, "matched_titles": [title for title in title_states if any(needle in title.lower() for needle in needles)]},
            )
        if result.returncode != 0:
            for check_id in (
                "browser_reference_journey",
                "browser_abstention_boundary",
                "workspace_isolation",
                "mutation_rate_and_quota_limits",
                "queue_saturation",
                "restart_recovery",
            ):
                self._set(
                    check_id,
                    "BLOCKED",
                    "PLAYWRIGHT_QUALIFICATION_FAILED",
                    summary,
                )

    def _qualify_release_mismatch_refusal(self) -> None:
        if not self.args.vercel_token or not self.args.vercel_org_id or not self.args.vercel_project_id:
            self._set(
                "release_mismatch_refusal",
                "UNAVAILABLE",
                "VERCEL_PREVIEW_CREDENTIALS_UNAVAILABLE",
                {},
            )
            return
        spa_root = Path(self.args.release_artifact_dir).resolve() / "spa"
        if not spa_root.is_dir():
            self._set(
                "release_mismatch_refusal",
                "UNAVAILABLE",
                "RELEASE_SPA_ARTIFACT_UNAVAILABLE",
                {},
            )
            return
        npx = _npx()
        mismatch_id = "mismatch-" + uuid4().hex[:12]
        mismatch_build = "build-mismatch-" + uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix="hosted-mismatch-") as temporary:
            output = Path(temporary) / "vercel"
            rendered = self.ledger.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "release_candidate.py"),
                    "render-release-assets",
                    "--source-root",
                    str(ROOT),
                    "--spa-root",
                    str(spa_root),
                    "--output",
                    str(output),
                    "--railway-origin",
                    _origin(self.args.railway_origin),
                    "--release-candidate-id",
                    mismatch_id,
                    "--build-manifest-id",
                    mismatch_build,
                ],
                cli="repository",
                version="hosted-qualification.v1",
                target="vercel-release-mismatch-preview",
            )
            if rendered.returncode != 0:
                self._set(
                    "release_mismatch_refusal",
                    "BLOCKED",
                    "MISMATCH_PREVIEW_RENDER_FAILED",
                    {},
                )
                return
            deployed = self.ledger.run(
                [
                    npx,
                    "--yes",
                    f"vercel@{VERCEL_CLI_VERSION}",
                    "deploy",
                    str(output),
                    "--token",
                    self.args.vercel_token,
                    "--scope",
                    self.args.vercel_org_id,
                    "--project",
                    self.args.vercel_project_id,
                    "--yes",
                    "--json",
                ],
                cli="vercel",
                version=VERCEL_CLI_VERSION,
                target=self.args.vercel_project_id,
                timeout=180.0,
            )
            deployed_payload = _parse_json_output(deployed.stdout)
            preview_url = _vercel_deployment_url(deployed_payload)
            if not isinstance(preview_url, str) or not preview_url:
                self._set(
                    "release_mismatch_refusal",
                    "BLOCKED",
                    "MISMATCH_PREVIEW_DEPLOY_FAILED",
                    {},
                )
                return
            preview_url = preview_url if preview_url.startswith("https://") else "https://" + preview_url
            curl = self.ledger.run(
                [
                    npx,
                    "--yes",
                    f"vercel@{VERCEL_CLI_VERSION}",
                    "curl",
                    f"{preview_url}/api/release",
                    "--scope",
                    self.args.vercel_org_id,
                    "--yes",
                    "--json",
                ],
                cli="vercel",
                version=VERCEL_CLI_VERSION,
                target=preview_url,
            )
            mismatch_payload = _parse_json_output(curl.stdout)
            mismatch_refused = _contains_code(mismatch_payload, "RELEASE_IDENTITY_MISMATCH")
            if not mismatch_refused:
                observed = self._http_probe(
                    preview_url,
                    "/api/release",
                    target="vercel-mismatch-preview",
                )
                mismatch_refused = (
                    observed.status == 503
                    and isinstance(observed.payload, Mapping)
                    and observed.payload.get("code") == "RELEASE_IDENTITY_MISMATCH"
                )
            self._set(
                "release_mismatch_refusal",
                "VERIFIED" if mismatch_refused else "BLOCKED",
                "RELEASE_MISMATCH_REFUSED" if mismatch_refused else "RELEASE_MISMATCH_SERVED",
                {"preview_url": preview_url, "expected_response": "RELEASE_IDENTITY_MISMATCH"},
            )

    def _qualify_budget_alert(self) -> None:
        evidence_path = os.environ.get("HOSTED_BUDGET_ALERT_EVIDENCE")
        if not evidence_path:
            self._set(
                "budget_alert_recorded",
                "UNAVAILABLE",
                "RAILWAY_BUDGET_ALERT_CLI_UNAVAILABLE",
                {"threshold_usd": 4, "hard_cap": False},
            )
            return
        try:
            payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = None
        valid = (
            isinstance(payload, Mapping)
            and payload.get("state") == "RECORDED"
            and payload.get("threshold_usd") == 4
            and payload.get("hard_cap") is False
            and payload.get("external_verification") == "UNAVAILABLE"
            and all(
                isinstance(payload.get(key), str) and payload[key].strip()
                for key in ("record_ref", "actor", "source", "cli_gap", "observed_at")
            )
            and payload.get("source") == "operator-recorded-Railway-billing-alert"
        )
        self.platform["budget_alert"] = (
            dict(payload)
            if valid
            else {
                "state": "BLOCKED",
                "hard_cap": False,
                "code": "RAILWAY_BUDGET_ALERT_EVIDENCE_INVALID",
            }
        )
        self._set(
            "budget_alert_recorded",
            "VERIFIED" if valid else "BLOCKED",
            "BUDGET_ALERT_RECORDED" if valid else "BUDGET_ALERT_EVIDENCE_INVALID",
            {"threshold_usd": 4, "hard_cap": False},
        )

    def _source_file(self, relative_path: str) -> str:
        source_commit = str(self.manifest["source_commit"])
        result = self.ledger.run(
            ["git", "show", f"{source_commit}:{relative_path}"],
            cli="git",
            version="repository",
            target=f"{source_commit}:{relative_path}",
        )
        if result.returncode != 0:
            raise QualificationRunError("QUALIFICATION_SOURCE_UNAVAILABLE")
        return result.stdout

    def _qualify_judging_availability(self) -> None:
        if self._public_release is None or self._public_health is None:
            self._set(
                "judging_availability",
                "BLOCKED",
                "PUBLIC_SURFACE_UNAVAILABLE",
                {},
            )
            return
        release = self._public_release
        health = self._public_health
        release_match = _matches_identity(release.payload, self.expected)
        ready = health.status == 200 and isinstance(health.payload, Mapping) and health.payload.get(
            "state"
        ) in {"ready", "degraded"}
        if self.checks["judging_availability"]["status"] == "BLOCKED":
            return
        self._set(
            "judging_availability",
            "VERIFIED" if release_match and ready else "BLOCKED",
            "HOSTED_JUDGING_AVAILABLE" if release_match and ready else "HOSTED_JUDGING_UNAVAILABLE",
            {"release_status": release.status, "health_status": health.status},
        )

    def _http_probe(self, origin: str, path: str, *, target: str) -> HttpObservation:
        url = _origin(origin) + path
        request = Request(url, headers={"accept": "application/json"})
        status = 599
        headers: dict[str, str] = {}
        body = ""
        try:
            with urlopen(request, timeout=float(self.args.http_timeout_seconds)) as response:
                status = int(response.status)
                headers = {key.lower(): value for key, value in response.headers.items()}
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            status = int(error.code)
            headers = {key.lower(): value for key, value in error.headers.items()}
            try:
                body = error.read().decode("utf-8", errors="replace")
            except OSError:
                body = ""
        except (OSError, URLError):
            body = ""
        payload = _parse_json_text(body)
        self.ledger.records.append(
            {
                "command": f"GET {url}",
                "cli": "python-urllib",
                "version": f"python-{sys.version_info.major}.{sys.version_info.minor}",
                "target": target,
                "exit_status": 0,
                "redacted_output_digest": sha256(_redact(body).encode("utf-8")),
            }
        )
        return HttpObservation(status, headers, body, payload)

    def _set(
        self,
        check_id: str,
        status: str,
        code: str,
        evidence: Mapping[str, Any],
    ) -> None:
        if check_id not in self.checks:
            raise QualificationRunError(f"unknown hosted check: {check_id}")
        self.checks[check_id] = {
            "check_id": check_id,
            "status": status,
            "code": code,
            "evidence": dict(evidence),
        }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the production hosted-delivery qualification protocol."
    )
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--release-artifact-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--vercel-origin", required=True)
    parser.add_argument("--railway-origin", required=True)
    parser.add_argument(
        "--railway-state-root",
        default=os.environ.get("RAILWAY_STATE_ROOT", "/data/core"),
    )
    parser.add_argument("--railway-project-id", default=os.environ.get("RAILWAY_PROJECT_ID", ""))
    parser.add_argument("--railway-service-id", default=os.environ.get("RAILWAY_SERVICE_ID", ""))
    parser.add_argument("--railway-environment-id", default=os.environ.get("RAILWAY_ENVIRONMENT_ID", ""))
    parser.add_argument("--vercel-token", default=os.environ.get("VERCEL_TOKEN", ""))
    parser.add_argument("--vercel-org-id", default=os.environ.get("VERCEL_ORG_ID", ""))
    parser.add_argument("--vercel-project-id", default=os.environ.get("VERCEL_PROJECT_ID", ""))
    parser.add_argument("--github-repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--browser-spec", default="tests/e2e/hosted_qualification.spec.ts")
    parser.add_argument("--browser-timeout-seconds", type=int, default=900)
    parser.add_argument("--http-timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = _read_json(Path(args.release_manifest))
        if not isinstance(manifest, Mapping) or not isinstance(manifest.get("source_commit"), str):
            raise QualificationRunError("RELEASE_MANIFEST_INVALID")
        collector = QualificationCollector(args, manifest)
        try:
            payload = collector.collect()
        except Exception as error:
            failure_code = _safe_failure_code(error)
            for check_id in REQUIRED_HOSTED_CHECK_IDS:
                collector.checks[check_id] = {
                    "check_id": check_id,
                    "status": "BLOCKED",
                    "code": "QUALIFICATION_RUN_FAILED",
                    "evidence": {"failure_code": failure_code},
                }
            collector.platform["run_failure"] = {"code": failure_code}
            payload = build_hosted_attestation(
                source_commit=str(manifest["source_commit"]),
                release_candidate_id=collector.expected["release_candidate_id"],
                build_manifest_id=collector.expected["build_manifest_id"],
                target={
                    "profile": "HOSTED",
                    "vercel_origin": _origin(args.vercel_origin),
                    "railway_origin": _origin(args.railway_origin),
                    "railway_project_id": args.railway_project_id,
                    "railway_service_id": args.railway_service_id,
                    "railway_environment_id": args.railway_environment_id,
                },
                checks=collector.checks.values(),
                commands=collector.ledger.records,
                platform=collector.platform,
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
        path = write_hosted_attestation(Path(args.output_dir), payload)
    except Exception as error:
        failure_artifact: str | None = None
        try:
            failure_artifact = str(
                _write_failure_evidence(
                    Path(args.output_dir),
                    _safe_failure_code(error),
                )
            )
        except Exception:
            pass
        print(
            json.dumps(
                {
                    "schema_version": "hosted-qualification-run.v1",
                    "status": "BLOCKED",
                    "code": _safe_failure_code(error),
                    "failure_artifact": failure_artifact,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "schema_version": "hosted-qualification-run.v1",
                "status": payload["qualification_status"],
                "attestation": str(path),
                "content_hash": payload["content_hash"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["qualification_status"] == "QUALIFIED" else 1


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise QualificationRunError("JSON_INPUT_INVALID") from error
    if not isinstance(payload, Mapping):
        raise QualificationRunError("JSON_INPUT_INVALID")
    return payload


def _write_failure_evidence(output_dir: Path, code: str) -> Path:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    body_payload: dict[str, Any] = {
        "schema_version": "hosted-qualification-failure.v1",
        "status": "BLOCKED",
        "code": code,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    body_payload["content_hash"] = sha256(canonical_json(body_payload).encode("utf-8"))
    body = canonical_json(body_payload).encode("utf-8") + b"\n"
    path = output_dir / "hosted-qualification-failure.json"
    sidecar = output_dir / "hosted-qualification-failure.sha256"
    if path.exists() or sidecar.exists():
        if path.is_file() and sidecar.is_file() and path.read_bytes() == body:
            return path
        raise QualificationRunError("QUALIFICATION_FAILURE_ARTIFACT_ALREADY_EXISTS")
    path.write_bytes(body)
    sidecar.write_text(f"{sha256(body)}\n", encoding="utf-8")
    return path


def _safe_failure_code(error: Exception) -> str:
    candidate = str(error).split(":", 1)[0].strip().upper()
    return candidate if re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,95}", candidate) else "QUALIFICATION_RUN_FAILED"


def _parse_json_text(value: str) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _parse_json_output(value: str) -> Mapping[str, Any]:
    payload = _parse_json_text(value.strip())
    if payload is not None:
        return payload
    decoder = json.JSONDecoder()
    for index, character in enumerate(value):
        if character not in "[{":
            continue
        try:
            parsed, _ = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            return parsed
    return {}


def _vercel_deployment_url(payload: Mapping[str, Any]) -> str | None:
    direct = payload.get("url")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    deployment = payload.get("deployment")
    if isinstance(deployment, Mapping):
        nested = deployment.get("url")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _matches_identity(payload: Mapping[str, Any] | None, expected: Mapping[str, str]) -> bool:
    return bool(
        isinstance(payload, Mapping)
        and payload.get("schema_version") == "release-identity.v1"
        and payload.get("profile") == "HOSTED"
        and payload.get("release_candidate_id") == expected["release_candidate_id"]
        and payload.get("build_manifest_id") == expected["build_manifest_id"]
    )


def _origin(value: str) -> str:
    parsed = urlsplit(str(value).rstrip("/"))
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise QualificationRunError("HOSTED_ORIGIN_INVALID")
    return f"https://{parsed.netloc}"


def _npx() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def _display_command(arguments: list[str]) -> str:
    redacted: list[str] = []
    redact_next = False
    for argument in arguments:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        if argument in {"--token", "--api-token", "--password"}:
            redacted.append(argument)
            redact_next = True
        else:
            redacted.append(argument)
    return " ".join(redacted)


def _redact(value: str) -> str:
    value = SECRET_VALUE.sub("<redacted-secret>", value)
    return re.sub(
        r"(?i)(api[_ -]?key|authorization|password|secret|token)\s*[:=]\s*([^,\s}\]]+)",
        r"\1=<redacted>",
        value,
    )


def _first_asset_path(body: str) -> str | None:
    match = re.search(r"(?:src|href)=\"(/assets/[^\"]+)\"", body)
    return match.group(1) if match else None


def _service_instance(status: Mapping[str, Any]) -> Mapping[str, Any]:
    environments = status.get("environments", {}).get("edges", [])
    if not environments or not isinstance(environments[0], Mapping):
        return {}
    environment = environments[0].get("node", {})
    service_edges = environment.get("serviceInstances", {}).get("edges", [])
    if not service_edges or not isinstance(service_edges[0], Mapping):
        return {}
    node = service_edges[0].get("node", {})
    return node if isinstance(node, Mapping) else {}


def _active_deployment(service: Mapping[str, Any]) -> Mapping[str, Any]:
    deployments = service.get("activeDeployments", [])
    if isinstance(deployments, list) and deployments and isinstance(deployments[0], Mapping):
        return deployments[0]
    return {}


def _contains_code(value: Any, code: str) -> bool:
    if isinstance(value, Mapping):
        return any(key == code or _contains_code(item, code) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_code(item, code) for item in value)
    return value == code


def _playwright_count(report: Mapping[str, Any], status: str) -> tuple[int, int]:
    count = 0
    failed = 0

    def walk(value: Any) -> None:
        nonlocal count, failed
        if isinstance(value, Mapping):
            if value.get("status") == status:
                count += 1
                if status == "unexpected":
                    failed += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(report)
    return count, failed


def _playwright_title_states(report: Mapping[str, Any]) -> dict[str, bool]:
    states: dict[str, bool] = {}

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            title = value.get("title")
            tests = value.get("tests")
            if isinstance(title, str) and isinstance(tests, list) and tests:
                statuses = [
                    test.get("status")
                    for test in tests
                    if isinstance(test, Mapping)
                ]
                states[title] = bool(statuses) and all(status == "expected" for status in statuses)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(report)
    return states


if __name__ == "__main__":
    raise SystemExit(main())
