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

For manual development, run the backend and frontend in separate PowerShell sessions:

```powershell
uv --cache-dir .uv-cache run --locked --no-sync uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
npm.cmd run dev
```

The Vite server proxies relative `/api` requests to the backend. The FastAPI app can optionally mount a compiled SPA when `CORE_SPA_DIST_DIR` is explicitly configured; it does not assume that delivery profile by default.

To run the same browser smoke against that optional one-origin package, start the backend with `CORE_SPA_DIST_DIR` pointing at `frontend/dist`, set `CORE_E2E_BASE_URL` to that origin, and run `npm.cmd run test:e2e`. The Playwright config skips its development web servers when that external base URL is present.

## Locked versions

The parent specification's React, Vite, TypeScript, FastAPI, Uvicorn, Python, scientific, and test pins are committed in `package.json`/`package-lock.json`, `pyproject.toml`/`uv.lock`, and `.python-version`. The parent's Carbon Charts `1.29.2` pair is not published in the npm registry at implementation time; the lock uses the published `1.27.18` React/core pair so the workspace remains installable. This is the only resolved pin difference.
