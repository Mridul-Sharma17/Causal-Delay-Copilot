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

The Playwright smoke starts one Uvicorn worker and one Vite development server. The final offline `setup.ps1`/`start.ps1` lifecycle scripts and typed delivery-profile/sealed-state foundation belong to downstream tickets, as required by issue #19’s scope boundary.

For manual development, run the backend and frontend in separate PowerShell sessions:

```powershell
uv --cache-dir .uv-cache run --locked --no-sync uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
npm.cmd run dev
```

The Vite server proxies relative `/api` requests to the backend. The FastAPI app can optionally mount a compiled SPA when `CORE_SPA_DIST_DIR` is explicitly configured; it does not assume that delivery profile by default.

To run the same browser smoke against that optional one-origin package, start the backend with `CORE_SPA_DIST_DIR` pointing at `frontend/dist`, set `CORE_E2E_BASE_URL` to that origin, and run `npm.cmd run test:e2e`. The Playwright config skips its development web servers when that external base URL is present.

## Locked versions

The parent specification’s React, Vite, TypeScript, FastAPI, Uvicorn, Python, scientific, and test pins are committed in `package.json`/`package-lock.json`, `pyproject.toml`/`uv.lock`, and `.python-version`. The parent’s Carbon Charts `1.29.2` pair is not published in the npm registry at implementation time; the lock uses the published `1.27.18` React/core pair so the workspace remains installable. This is the only resolved pin difference.
