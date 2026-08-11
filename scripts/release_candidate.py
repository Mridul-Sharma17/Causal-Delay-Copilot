from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

RELEASE_BUILD_SCHEMA_VERSION = "release-build-manifest.v1"
RELEASE_IDENTITY_SCHEMA_VERSION = "release-identity.v1"
ROLLBACK_SCHEMA_VERSION = "release-rollback-occurrence.v1"

LOCKFILE_PATHS = (
    "package-lock.json",
    "uv.lock",
    ".python-version",
)

BOUNDING_PATTERNS: dict[str, tuple[str, ...]] = {
    "migrations": (
        "backend/app/state.py",
        "backend/app/audit.py",
        "backend/app/ingestion.py",
        "backend/app/governance.py",
        "backend/app/operations.py",
        "backend/app/workspace.py",
        "backend/app/drafts.py",
        "backend/app/manager_decisions.py",
        "backend/app/tradeoff_selection.py",
    ),
    "schemas": (
        "backend/app/contracts.py",
        "frontend/src/contracts.ts",
        "backend/app/data/*.mapping.json",
    ),
    "policies": (
        "backend/app/settings.py",
        "backend/app/eligibility_contract.py",
        "backend/app/validity.py",
        "backend/app/decision_support_constraints.py",
        "backend/app/draft_context.py",
    ),
    "model_identity": (
        "backend/app/predictive.py",
        "backend/app/evaluation.py",
        "backend/app/data/predictive_baseline_report.json",
        "backend/app/data/predictive_baseline.joblib",
    ),
    "reference_manifests": (
        "backend/app/data/semi_synthetic_hero.mapping.json",
        "backend/app/data/olist_validation.mapping.json",
        "backend/app/data/scms_rejection_vignette.mapping.json",
        "backend/app/data/temporal_eligibility_release.json",
        "backend/app/data/*protected_sources.json",
    ),
}


class ReleaseContractError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ReleaseContractError(f"{label.upper()}_INVALID")
    return value


def _validate_digest(value: str, label: str = "digest") -> str:
    if not DIGEST_PATTERN.fullmatch(value):
        raise ReleaseContractError(f"{label.upper()}_INVALID")
    return value


def _validate_origin(value: str, label: str) -> str:
    parsed = urlsplit(value.rstrip("/"))
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ReleaseContractError(f"{label.upper()}_INVALID")
    return f"{parsed.scheme}://{parsed.netloc}"


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReleaseContractError(f"RELEASE_INPUT_MISSING:{_relative_path(root, path)}")
    data = path.read_bytes()
    return {
        "path": _relative_path(root, path),
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def _expand_paths(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        if not matches:
            raise ReleaseContractError(f"RELEASE_INPUT_MISSING:{pattern}")
        for path in matches:
            if path.is_file() and path not in seen:
                paths.append(path)
                seen.add(path)
    return paths


def _tree_digest(root: Path) -> tuple[str, int]:
    if not root.is_dir():
        raise ReleaseContractError("SPA_ARTIFACT_MISSING")
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ReleaseContractError("SPA_ARTIFACT_EMPTY")
    for path in files:
        digest.update(_relative_path(root, path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}", len(files)


def _write_json(path: Path, value: object, *, immutable: bool = False) -> None:
    data = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    encoded = data.encode("utf-8")
    if immutable and path.exists():
        if path.read_bytes() != encoded:
            raise ReleaseContractError("IMMUTABLE_RELEASE_OCCURRENCE_CONFLICT")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        temporary.unlink()
    temporary.write_bytes(encoded)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseContractError("RELEASE_MANIFEST_INVALID") from error
    if not isinstance(value, dict):
        raise ReleaseContractError("RELEASE_MANIFEST_INVALID")
    return value


def build_manifest(args: argparse.Namespace) -> None:
    source_root = Path(args.source_root).resolve()
    source_commit = args.source_commit.strip()
    if not COMMIT_PATTERN.fullmatch(source_commit):
        raise ReleaseContractError("SOURCE_COMMIT_INVALID")
    release_candidate_id = _validate_identifier(
        args.release_candidate_id,
        "release_candidate_id",
    )
    image_digest = _validate_digest(args.image_digest, "image_digest")
    spa_root = Path(args.spa_root).resolve()
    spa_digest, spa_file_count = _tree_digest(spa_root)

    lockfiles = [
        _file_record(source_root, source_root / path)
        for path in LOCKFILE_PATHS
    ]
    bindings = {
        name: [
            _file_record(source_root, path)
            for path in _expand_paths(source_root, patterns)
        ]
        for name, patterns in BOUNDING_PATTERNS.items()
    }
    payload: dict[str, Any] = {
        "schema_version": RELEASE_BUILD_SCHEMA_VERSION,
        "release_candidate_id": release_candidate_id,
        "source_commit": source_commit,
        "lockfiles": lockfiles,
        "image": {
            "ref": args.image_ref,
            "digest": image_digest,
        },
        "spa": {
            "digest": spa_digest,
            "file_count": spa_file_count,
        },
        "runtime": {
            "node": "22.12.0",
            "python": "3.12.13",
            "uv": "0.11.8",
        },
        "bindings": bindings,
    }
    build_manifest_id = "build-" + hashlib.sha256(_canonical(payload)).hexdigest()
    manifest = {
        **payload,
        "build_manifest_id": build_manifest_id,
    }
    manifest["content_hash"] = _sha256_bytes(_canonical(manifest))
    _write_json(Path(args.output).resolve(), manifest)
    print(json.dumps({"build_manifest_id": build_manifest_id}, sort_keys=True))


def _render_vercel_config(source_root: Path, railway_origin: str) -> dict[str, Any]:
    template = _read_json(source_root / "vercel.json.template")
    rewrites = template.get("rewrites")
    if not isinstance(rewrites, list):
        raise ReleaseContractError("VERCEL_CONFIG_INVALID")
    rendered = json.loads(json.dumps(template))
    rendered.pop("buildCommand", None)
    rendered.pop("installCommand", None)
    rendered.pop("outputDirectory", None)
    rendered["rewrites"] = [
        rewrite
        for rewrite in rendered["rewrites"]
        if not (
            isinstance(rewrite, dict)
            and rewrite.get("source") == "/api/:path*"
        )
    ]
    return rendered


def render_release_assets(args: argparse.Namespace) -> None:
    source_root = Path(args.source_root).resolve()
    spa_root = Path(args.spa_root).resolve()
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ReleaseContractError("RELEASE_ASSET_OUTPUT_NOT_EMPTY")
    railway_origin = _validate_origin(args.railway_origin, "railway_origin")
    release_candidate_id = _validate_identifier(
        args.release_candidate_id,
        "release_candidate_id",
    )
    build_manifest_id = _validate_identifier(
        args.build_manifest_id,
        "build_manifest_id",
    )
    if not spa_root.is_dir():
        raise ReleaseContractError("SPA_ARTIFACT_MISSING")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(spa_root, output)
    _write_json(
        output / "release.json",
        {
            "schema_version": RELEASE_IDENTITY_SCHEMA_VERSION,
            "profile": "HOSTED",
            "release_candidate_id": release_candidate_id,
            "build_manifest_id": build_manifest_id,
        },
    )
    _write_json(
        output / "vercel.json",
        _render_vercel_config(source_root, railway_origin),
    )
    guard_template = source_root / "api" / "release.ts.template"
    if not guard_template.is_file():
        raise ReleaseContractError("VERCEL_RELEASE_GUARD_TEMPLATE_MISSING")
    guard = guard_template.read_text(encoding="utf-8")
    guard = guard.replace("__RAILWAY_PUBLIC_ORIGIN__", railway_origin)
    guard = guard.replace("__RELEASE_CANDIDATE_ID__", release_candidate_id)
    guard = guard.replace("__BUILD_MANIFEST_ID__", build_manifest_id)
    guard_path = output / "api" / "release.ts"
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    guard_path.write_text(guard, encoding="utf-8", newline="\n")
    proxy_template = source_root / "api" / "proxy.ts.template"
    if not proxy_template.is_file():
        raise ReleaseContractError("VERCEL_API_PROXY_TEMPLATE_MISSING")
    proxy = proxy_template.read_text(encoding="utf-8")
    proxy = proxy.replace("__RAILWAY_PUBLIC_ORIGIN__", railway_origin)
    proxy = proxy.replace("__RELEASE_CANDIDATE_ID__", release_candidate_id)
    proxy = proxy.replace("__BUILD_MANIFEST_ID__", build_manifest_id)
    proxy_path = output / "api" / "[...path].ts"
    proxy_path.write_text(proxy, encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output)}, sort_keys=True))


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise ReleaseContractError("RELEASE_REMOTE_UNAVAILABLE") from error
    if not isinstance(payload, dict):
        raise ReleaseContractError("RELEASE_REMOTE_INVALID")
    return payload


def _assert_identity(payload: dict[str, Any], expected: dict[str, str]) -> None:
    if (
        payload.get("schema_version") != RELEASE_IDENTITY_SCHEMA_VERSION
        or payload.get("release_candidate_id") != expected["release_candidate_id"]
        or payload.get("build_manifest_id") != expected["build_manifest_id"]
        or payload.get("profile") != "HOSTED"
    ):
        raise ReleaseContractError("RELEASE_IDENTITY_MISMATCH")


def _with_retries(
    callback: Callable[[], None],
    retries: int,
    delay_seconds: float,
) -> None:
    last_error: ReleaseContractError | None = None
    for attempt in range(max(1, retries)):
        try:
            callback()
            return
        except ReleaseContractError as error:
            last_error = error
            if attempt + 1 < max(1, retries):
                time.sleep(max(0.0, delay_seconds))
    if last_error is not None:
        raise last_error


def _expected_identity(manifest_path: str) -> dict[str, str]:
    manifest = _read_json(Path(manifest_path).resolve())
    if manifest.get("schema_version") != RELEASE_BUILD_SCHEMA_VERSION:
        raise ReleaseContractError("RELEASE_MANIFEST_INVALID")
    content_hash = manifest.get("content_hash")
    if not isinstance(content_hash, str) or _sha256_bytes(
        _canonical(
            {
                key: value
                for key, value in manifest.items()
                if key != "content_hash"
            }
        )
    ) != content_hash:
        raise ReleaseContractError("RELEASE_MANIFEST_INTEGRITY_INVALID")
    build_payload = {
        key: value
        for key, value in manifest.items()
        if key not in {"build_manifest_id", "content_hash"}
    }
    expected_build_manifest_id = "build-" + hashlib.sha256(
        _canonical(build_payload)
    ).hexdigest()
    if manifest.get("build_manifest_id") != expected_build_manifest_id:
        raise ReleaseContractError("RELEASE_MANIFEST_ID_INVALID")
    release_candidate_id = manifest.get("release_candidate_id")
    build_manifest_id = manifest.get("build_manifest_id")
    if not isinstance(release_candidate_id, str) or not isinstance(build_manifest_id, str):
        raise ReleaseContractError("RELEASE_MANIFEST_INVALID")
    return {
        "release_candidate_id": _validate_identifier(
            release_candidate_id,
            "release_candidate_id",
        ),
        "build_manifest_id": _validate_identifier(
            build_manifest_id,
            "build_manifest_id",
        ),
    }


def verify_railway(args: argparse.Namespace) -> None:
    expected = _expected_identity(args.manifest)
    origin = _validate_origin(args.railway_origin, "railway_origin")

    def check() -> None:
        _assert_identity(
            _fetch_json(f"{origin}/api/release", args.timeout_seconds),
            expected,
        )
        health = _fetch_json(f"{origin}/api/health/ready", args.timeout_seconds)
        if health.get("state") not in {"ready", "degraded"}:
            raise ReleaseContractError("RAILWAY_READINESS_FAILED")

    _with_retries(check, args.retries, args.delay_seconds)
    print(json.dumps({"railway": "verified"}, sort_keys=True))


def verify_match(args: argparse.Namespace) -> None:
    expected = _expected_identity(args.manifest)
    railway_origin = _validate_origin(args.railway_origin, "railway_origin")
    vercel_origin = _validate_origin(args.vercel_origin, "vercel_origin")

    def check() -> None:
        _assert_identity(
            _fetch_json(f"{railway_origin}/api/release", args.timeout_seconds),
            expected,
        )
        _assert_identity(
            _fetch_json(f"{vercel_origin}/release.json", args.timeout_seconds),
            expected,
        )
        _assert_identity(
            _fetch_json(f"{vercel_origin}/api/release", args.timeout_seconds),
            expected,
        )

    _with_retries(check, args.retries, args.delay_seconds)
    print(json.dumps({"release": "matched"}, sort_keys=True))


def record_rollback(args: argparse.Namespace) -> None:
    from_release_candidate_id = _validate_identifier(
        args.from_release_candidate_id,
        "from_release_candidate_id",
    )
    from_build_manifest_id = _validate_identifier(
        args.from_build_manifest_id,
        "from_build_manifest_id",
    )
    to_release_candidate_id = _validate_identifier(
        args.to_release_candidate_id,
        "to_release_candidate_id",
    )
    to_build_manifest_id = _validate_identifier(
        args.to_build_manifest_id,
        "to_build_manifest_id",
    )
    if not args.target_deployment_id.strip():
        raise ReleaseContractError("ROLLBACK_TARGET_INVALID")
    target_image_ref = args.target_image_ref.strip()
    if not target_image_ref:
        raise ReleaseContractError("ROLLBACK_IMAGE_REF_REQUIRED")
    target_image_digest = _validate_digest(
        args.target_image_digest,
        "target_image_digest",
    )
    if not COMMIT_PATTERN.fullmatch(args.source_commit.strip()):
        raise ReleaseContractError("SOURCE_COMMIT_INVALID")
    if not args.reason.strip():
        raise ReleaseContractError("ROLLBACK_REASON_REQUIRED")
    occurred_at = args.occurred_at or datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "schema_version": ROLLBACK_SCHEMA_VERSION,
        "kind": "RELEASE_ROLLBACK",
        "mutation": "NEW_IMMUTABLE_DEPLOYMENT",
        "from": {
            "release_candidate_id": from_release_candidate_id,
            "build_manifest_id": from_build_manifest_id,
        },
        "to": {
            "release_candidate_id": to_release_candidate_id,
            "build_manifest_id": to_build_manifest_id,
        },
        "target_deployment_id": args.target_deployment_id,
        "target_image": {
            "ref": target_image_ref,
            "digest": target_image_digest,
        },
        "source_commit": args.source_commit.strip(),
        "reason": args.reason.strip(),
        "occurred_at": occurred_at,
    }
    payload["occurrence_id"] = "rollback-" + hashlib.sha256(
        _canonical(payload)
    ).hexdigest()
    _write_json(Path(args.output).resolve(), payload, immutable=True)
    print(json.dumps({"occurrence_id": payload["occurrence_id"]}, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify immutable Core releases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-manifest")
    build.add_argument("--source-root", default=str(ROOT))
    build.add_argument("--source-commit", required=True)
    build.add_argument("--release-candidate-id", required=True)
    build.add_argument("--image-digest", required=True)
    build.add_argument("--image-ref", default=None)
    build.add_argument("--spa-root", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=build_manifest)

    render = subparsers.add_parser("render-release-assets")
    render.add_argument("--source-root", default=str(ROOT))
    render.add_argument("--spa-root", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--railway-origin", required=True)
    render.add_argument("--release-candidate-id", required=True)
    render.add_argument("--build-manifest-id", required=True)
    render.set_defaults(handler=render_release_assets)

    railway = subparsers.add_parser("verify-railway")
    railway.add_argument("--manifest", required=True)
    railway.add_argument("--railway-origin", required=True)
    railway.add_argument("--retries", type=int, default=1)
    railway.add_argument("--delay-seconds", type=float, default=2.0)
    railway.add_argument("--timeout-seconds", type=float, default=10.0)
    railway.set_defaults(handler=verify_railway)

    match = subparsers.add_parser("verify-match")
    match.add_argument("--manifest", required=True)
    match.add_argument("--railway-origin", required=True)
    match.add_argument("--vercel-origin", required=True)
    match.add_argument("--retries", type=int, default=1)
    match.add_argument("--delay-seconds", type=float, default=2.0)
    match.add_argument("--timeout-seconds", type=float, default=10.0)
    match.set_defaults(handler=verify_match)

    rollback = subparsers.add_parser("record-rollback")
    rollback.add_argument("--output", required=True)
    rollback.add_argument("--from-release-candidate-id", required=True)
    rollback.add_argument("--from-build-manifest-id", required=True)
    rollback.add_argument("--to-release-candidate-id", required=True)
    rollback.add_argument("--to-build-manifest-id", required=True)
    rollback.add_argument("--target-deployment-id", required=True)
    rollback.add_argument("--target-image-ref", required=True)
    rollback.add_argument("--target-image-digest", required=True)
    rollback.add_argument("--source-commit", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--occurred-at")
    rollback.set_defaults(handler=record_rollback)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
    except ReleaseContractError as error:
        print(f"RELEASE_CONTRACT_FAILED:{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
