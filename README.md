# Causal Delay Copilot Core

This checkout contains the first locked Core tracer bullet from issue #19: a React/Vite browser health state, typed FastAPI health responses, and one append-only SQLite audit occurrence with transactional sequencing and idempotent retry.

## CLI verification

The repository-local commands are PowerShell-compatible:

```powershell
npm.cmd ci --ignore-scripts --no-audit --no-fund
uv --cache-dir .uv-cache sync --locked
npm.cmd run typecheck
npm.cmd test
uv --cache-dir .uv-cache run --locked --no-sync pytest
npm.cmd run build
npm.cmd run test:e2e
```

The Playwright smoke starts one Uvicorn worker and one Vite development server. The prepared local fallback uses the compiled SPA and one loopback Uvicorn worker instead.

## Complete Core browser-to-ledger verification

Issue #64 has one bounded command for the full prepared seam:

```powershell
.\scripts\verify-core-journey.ps1
```

The command runs the TypeScript check, frontend tests, the complete Python suite, and the compiled SPA build. It then prepares a real `LOCAL_FALLBACK` state through the versioned API, SQLite transactions, and content-addressed artifacts, starts the compiled SPA from the same Uvicorn origin, and invokes the repository-local Playwright CLI against that origin. The prepared state is left under `.tmp\core-journey-*` for inspection and is not a shipped reference or a synthetic fixture. Hosted identity parity is covered by the parametrized API contract test in `backend/tests/test_core_journey.py`; the production hosted profile requires an HTTPS origin and Railway volume path.

## Prepared local fallback

Run the one-time setup while online from Windows PowerShell 5.1:

```powershell
.\scripts\setup.ps1
```

Setup uses only the committed npm/uv locks, installs Chromium with `PLAYWRIGHT_BROWSERS_PATH=0`, builds the SPA, initializes sealed SQLite state, runs health and browser smoke checks, and records setup success only after every step passes. It stops on failure without presenting a partial setup as ready.

After setup, start the application offline:

```powershell
.\scripts\start.ps1
```

Startup performs no package-manager, synchronization, repair, or download operation. It validates the prepared interpreter, SPA, current-release reference registry (or an explicit unavailable reference state), sealed state, writable runtime locations, fixed `127.0.0.1:8000` port, and exclusive lifecycle state before it opens the browser. Liveness, Core readiness, and Gemini-only degradation remain separate health states. Use `-NoBrowser` for a local smoke without opening the system browser; use `-StateRoot <path>` only when selecting a separate prepared state root.

## Local recovery and reference fallback

Recovery commands operate only on the `LOCAL_FALLBACK` profile. Set the same profile and state root used by the prepared launcher before invoking them:

```powershell
$env:CORE_PROFILE = "LOCAL_FALLBACK"
$env:CORE_STATE_ROOT = (Resolve-Path .\state).Path
$env:CORE_PUBLIC_ORIGIN = "http://127.0.0.1:8000"
$env:CORE_BIND_HOST = "127.0.0.1"
$env:CORE_OFFLINE_STARTUP = "true"

uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.recovery verify
uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.recovery archive
uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.recovery reset
uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.recovery restore --archive-id <archive-id>
uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.recovery restore-baseline
```

`reset` refuses an active or recovery-pending state, records an archive of the complete SQLite-plus-artifact root, restores the sealed baseline, and reports preflight status. Restore replaces the whole root; it does not merge audit histories. Corrupt current, archive, baseline, database, manifest, or referenced artifact state fails closed and preserves the affected bytes in quarantine with `RESTORE_CORE_STATE_AND_RETRY`.

The static reference fallback is a separate read-only package. Prepare it only after the interactive path has returned a declared failure, then launch it on its own loopback origin:

```powershell
uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.reference_fallback prepare `
  --root .\reference-fallback `
  --capture-id capture-20260811-01 `
  --run-id analysis-run-12345678-1234-4234-8234-123456789abc `
  --release-candidate-id release-20260811 `
  --interactive-failure-code INTERACTIVE_PATH_FAILED

uv --cache-dir .uv-cache run --locked --no-sync python -m backend.app.reference_fallback launch `
  --root .\reference-fallback `
  --interactive-failure-code INTERACTIVE_PATH_FAILED `
  --port 8001
```

The fallback displays `reference fallback`, capture/run/release identity, and its declared failure. It is not fresh computation, has no write/API route, and is never injected into the live UI or counted as hosted availability.

For manual development, run the backend and frontend in separate PowerShell sessions:

```powershell
uv --cache-dir .uv-cache run --locked --no-sync uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
npm.cmd run dev
```

The Vite server proxies relative `/api` requests to the backend. The FastAPI app can optionally mount a compiled SPA when `CORE_SPA_DIST_DIR` is explicitly configured; it does not assume that delivery profile by default.

To run the same browser smoke against that optional one-origin package, start the backend with `CORE_SPA_DIST_DIR` pointing at `frontend/dist`, set `CORE_E2E_BASE_URL` to that origin, and run `npm.cmd run test:e2e`. The Playwright config skips its development web servers when that external base URL is present.

## Locked versions

The parent specification's React, Vite, TypeScript, FastAPI, Uvicorn, Python, scientific, and test pins are committed in `package.json`/`package-lock.json`, `pyproject.toml`/`uv.lock`, and `.python-version`. The parent's Carbon Charts `1.29.2` pair is not published in the npm registry at implementation time; the lock uses the published `1.27.18` React/core pair so the workspace remains installable. This is the only resolved pin difference.
