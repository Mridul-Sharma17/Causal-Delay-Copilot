from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import hashlib
import html
import http.server
import json
from pathlib import Path
import re
import threading
from typing import Any, Mapping
from http import HTTPStatus

from .canonical import canonical_json


REFERENCE_FALLBACK_SCHEMA_VERSION = "reference-fallback.v1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ReferenceFallbackError(RuntimeError):
    """A static fallback package failed its closed identity/read-only contract."""


@dataclass(frozen=True, slots=True)
class ReferenceFallbackIdentity:
    capture_id: str
    run_id: str
    release_candidate_id: str
    bundle_manifest_hash: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceFallbackManifest:
    capture_id: str
    run_id: str
    release_candidate_id: str
    interactive_failure_code: str
    html_sha256: str
    captured_at: str
    bundle_manifest_hash: str | None = None


class ReferenceFallbackServer:
    def __init__(self, server: http.server.ThreadingHTTPServer, thread: threading.Thread) -> None:
        self._server = server
        self._thread = thread
        self._close_lock = threading.Lock()
        self._closed = False

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def wait(self) -> None:
        self._thread.join()

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self._server.shutdown()
            self._server.server_close()
        self._thread.join(timeout=2)


def build_reference_fallback(
    root: Path,
    *,
    identity: ReferenceFallbackIdentity,
    interactive_failure_code: str,
    captured_at: str | None = None,
) -> ReferenceFallbackManifest:
    """Build one immutable, read-only reference fallback package."""

    _validate_identity(identity)
    _validate_identifier(interactive_failure_code, "interactive failure code")
    try:
        if root.exists():
            if not root.is_dir() or root.is_symlink():
                raise ReferenceFallbackError("REFERENCE_FALLBACK_ROOT_INVALID")
            if any(root.iterdir()):
                raise ReferenceFallbackError("REFERENCE_FALLBACK_ALREADY_EXISTS")
        root.mkdir(parents=True, exist_ok=True)
    except ReferenceFallbackError:
        raise
    except OSError as error:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_WRITE_FAILED") from error
    captured = captured_at or datetime.now(timezone.utc).isoformat()
    document = _render_html(identity, interactive_failure_code, captured)
    html_path = root / "index.html"
    try:
        html_path.write_text(document, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_WRITE_FAILED") from error
    html_digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
    manifest = ReferenceFallbackManifest(
        capture_id=identity.capture_id,
        run_id=identity.run_id,
        release_candidate_id=identity.release_candidate_id,
        interactive_failure_code=interactive_failure_code,
        html_sha256=html_digest,
        captured_at=captured,
        bundle_manifest_hash=identity.bundle_manifest_hash,
    )
    try:
        (root / "reference-fallback-manifest.json").write_text(
            canonical_json(_manifest_payload(manifest)) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as error:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_WRITE_FAILED") from error
    return manifest


def verify_reference_fallback(root: Path) -> ReferenceFallbackManifest:
    """Verify the static package and return only its identity projection."""

    try:
        if not root.is_dir() or root.is_symlink():
            raise ValueError("fallback root is unavailable")
        if {path.name for path in root.iterdir()} != {
            "index.html",
            "reference-fallback-manifest.json",
        }:
            raise ValueError("fallback package contains unexpected files")
        payload = json.loads(
            (root / "reference-fallback-manifest.json").read_text(encoding="utf-8")
        )
        if not isinstance(payload, Mapping):
            raise ValueError("fallback manifest is not an object")
        if payload.get("schema_version") != REFERENCE_FALLBACK_SCHEMA_VERSION:
            raise ValueError("fallback manifest schema is unsupported")
        if payload.get("label") != "reference fallback":
            raise ValueError("fallback manifest label is invalid")
        html_path = root / "index.html"
        document = html_path.read_text(encoding="utf-8")
        manifest = ReferenceFallbackManifest(
            capture_id=_required_text(payload, "capture_id"),
            run_id=_required_text(payload, "run_id"),
            release_candidate_id=_required_text(payload, "release_candidate_id"),
            interactive_failure_code=_required_text(payload, "interactive_failure_code"),
            html_sha256=_required_text(payload, "html_sha256"),
            captured_at=_required_text(payload, "captured_at"),
            bundle_manifest_hash=(
                None
                if payload.get("bundle_manifest_hash") is None
                else _required_text(payload, "bundle_manifest_hash")
            ),
        )
        _validate_identity(
            ReferenceFallbackIdentity(
                capture_id=manifest.capture_id,
                run_id=manifest.run_id,
                release_candidate_id=manifest.release_candidate_id,
                bundle_manifest_hash=manifest.bundle_manifest_hash,
            )
        )
        if hashlib.sha256(document.encode("utf-8")).hexdigest() != manifest.html_sha256:
            raise ValueError("fallback HTML digest does not match")
        if "reference fallback" not in document or "fresh computation" not in document:
            raise ValueError("fallback label is missing")
        for value in (
            manifest.capture_id,
            manifest.run_id,
            manifest.release_candidate_id,
        ):
            if value not in document:
                raise ValueError("fallback identity is not displayed")
        return manifest
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_INVALID") from error


def launch_reference_fallback(
    root: Path,
    *,
    interactive_failure_code: str,
    host: str = "127.0.0.1",
    port: int = 8001,
    block: bool = False,
) -> ReferenceFallbackServer:
    """Serve the verified static package on a separate loopback origin."""

    _validate_identifier(interactive_failure_code, "interactive failure code")
    manifest = verify_reference_fallback(root)
    if manifest.interactive_failure_code != interactive_failure_code:
        raise ReferenceFallbackError("INTERACTIVE_FAILURE_DECLARATION_MISMATCH")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_MUST_BIND_LOOPBACK")
    if not 0 <= port <= 65535:
        raise ReferenceFallbackError("REFERENCE_FALLBACK_PORT_INVALID")

    handler = partial(_StaticFallbackHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="reference-fallback-server",
        daemon=True,
    )
    thread.start()
    launched = ReferenceFallbackServer(server, thread)
    if block:
        try:
            launched.wait()
        except KeyboardInterrupt:
            launched.close()
    return launched


class _StaticFallbackHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler hook
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler hook
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler hook
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler hook
        if self.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler hook
        if self.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_HEAD()


def _render_html(
    identity: ReferenceFallbackIdentity,
    interactive_failure_code: str,
    captured_at: str,
) -> str:
    values = {
        "capture_id": html.escape(identity.capture_id),
        "run_id": html.escape(identity.run_id),
        "release_candidate_id": html.escape(identity.release_candidate_id),
        "failure_code": html.escape(interactive_failure_code),
        "captured_at": html.escape(captured_at),
        "bundle_manifest_hash": html.escape(identity.bundle_manifest_hash or "UNAVAILABLE"),
    }
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Causal Delay Copilot - reference fallback</title>
    <style>
      :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
      body {{ margin: 0; background: #f4f4f4; color: #161616; }}
      main {{ max-width: 56rem; margin: 4rem auto; padding: 2rem; background: #fff; }}
      h1 {{ margin-top: 0; }}
      .label {{ color: #8a3ffc; font-weight: 700; text-transform: uppercase; }}
      dl {{ display: grid; grid-template-columns: minmax(12rem, 1fr) 2fr; gap: .75rem 1rem; }}
      dt {{ font-weight: 700; }}
      dd {{ margin: 0; overflow-wrap: anywhere; }}
      code {{ font-family: Consolas, monospace; }}
    </style>
  </head>
  <body>
    <main>
      <p class="label">reference fallback</p>
      <h1>Read-only reference evidence</h1>
      <p>The interactive path failed with <code>{values['failure_code']}</code>.</p>
      <p>This static reference is not fresh computation, is not live, and cannot accept writes.</p>
      <dl>
        <dt>Capture identity</dt><dd><code>{values['capture_id']}</code></dd>
        <dt>Run identity</dt><dd><code>{values['run_id']}</code></dd>
        <dt>Release identity</dt><dd><code>{values['release_candidate_id']}</code></dd>
        <dt>Bundle manifest</dt><dd><code>{values['bundle_manifest_hash']}</code></dd>
        <dt>Captured at</dt><dd><code>{values['captured_at']}</code></dd>
      </dl>
    </main>
  </body>
</html>
"""


def _manifest_payload(manifest: ReferenceFallbackManifest) -> dict[str, object]:
    return {
        "schema_version": REFERENCE_FALLBACK_SCHEMA_VERSION,
        "label": "reference fallback",
        "capture_id": manifest.capture_id,
        "run_id": manifest.run_id,
        "release_candidate_id": manifest.release_candidate_id,
        "interactive_failure_code": manifest.interactive_failure_code,
        "html_sha256": manifest.html_sha256,
        "captured_at": manifest.captured_at,
        "bundle_manifest_hash": manifest.bundle_manifest_hash,
    }


def _validate_identity(identity: ReferenceFallbackIdentity) -> None:
    _validate_identifier(identity.capture_id, "capture identity")
    _validate_identifier(identity.run_id, "run identity")
    _validate_identifier(identity.release_candidate_id, "release identity")
    if identity.bundle_manifest_hash is not None and not re.fullmatch(
        r"sha256:[0-9a-f]{64}", identity.bundle_manifest_hash
    ):
        raise ReferenceFallbackError("REFERENCE_FALLBACK_IDENTITY_INVALID")


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ReferenceFallbackError("REFERENCE_FALLBACK_IDENTITY_INVALID")


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"fallback manifest field is invalid: {key}")
    return value


def _parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(description="Separate static reference fallback")
    parser.add_argument("command", choices=("prepare", "launch"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--capture-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--release-candidate-id", default="")
    parser.add_argument("--bundle-manifest-hash", default=None)
    parser.add_argument("--interactive-failure-code", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        if arguments.command == "prepare":
            manifest = build_reference_fallback(
                arguments.root,
                identity=ReferenceFallbackIdentity(
                    capture_id=arguments.capture_id,
                    run_id=arguments.run_id,
                    release_candidate_id=arguments.release_candidate_id,
                    bundle_manifest_hash=arguments.bundle_manifest_hash,
                ),
                interactive_failure_code=arguments.interactive_failure_code,
            )
            print(json.dumps(_manifest_payload(manifest), sort_keys=True))
            return 0
        server = launch_reference_fallback(
            arguments.root,
            interactive_failure_code=arguments.interactive_failure_code,
            host=arguments.host,
            port=arguments.port,
            block=False,
        )
        print(f"Reference fallback listening on http://{arguments.host}:{server.port}")
        try:
            server.wait()
        except KeyboardInterrupt:
            server.close()
        return 0
    except ReferenceFallbackError as error:
        print(json.dumps({"status": "FAILED", "code": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
