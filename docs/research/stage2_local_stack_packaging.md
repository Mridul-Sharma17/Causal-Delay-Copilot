# Stage 2 local stack and packaging decision

**Status:** implementation-planning research, verified 25 July 2026  
**Decision scope:** local Windows prototype only; no product code was written

## Verdict

Use a React/TypeScript single-page application built with Vite and Carbon v11, backed by a separate FastAPI/Python analytical service. During development, Vite proxies `/api` to FastAPI. For the demo, build the SPA once and let FastAPI serve the compiled assets and `/api` from one `127.0.0.1` origin. This yields one browser URL and one runtime process without collapsing the frontend/backend code boundary.

Package the prototype as source plus exact lockfiles, a prebuilt frontend, validated analysis artifacts, and two **Windows PowerShell 5.1-compatible** launchers: a one-time `setup.ps1` and a repeatable `start.ps1`. Do not put Docker, Electron, SSR, notebooks, or a frozen `.exe` in Core.

This is the smallest stack that satisfies the authoritative requirements: fully local operation, cached validated results with genuine reruns, a zero-LLM fallback, inspectable technical depth, and Carbon-governed frontend behavior ([Stage 2 strategy](../causal_delay_copilot_stage2_strategy.md), especially §§14 and 17; [DESIGN.md](../../DESIGN.md)).

## Concrete baseline

Pin exact versions in lockfiles; do not use floating ranges in the demo environment.

| Layer | Baseline | Why |
|---|---|---|
| Windows runtime | Windows 10/11 x64 | Python 3.12 supports Windows, and the selected scientific packages publish/support Windows distributions ([Python on Windows](https://docs.python.org/3.12/using/windows.html), [EconML 0.16.0 files](https://pypi.org/project/econml/0.16.0/#files)). |
| Node | Node 24 LTS; record the exact installed patch in `.node-version` | Vite 8 requires Node `^20.19.0 || >=22.12.0`; Node 24 is the supported LTS line appropriate for a new build ([Vite guide](https://vite.dev/guide/), [Node release schedule](https://nodejs.org/en/about/previous-releases)). |
| Frontend | React `19.2.8`, React DOM `19.2.8`, TypeScript `7.0.2`, Vite `8.1.5`, `@vitejs/plugin-react` `6.0.4` | Vite's official React/TypeScript template uses this client-only architecture; Vite produces static build output and needs no SSR ([create-vite React TypeScript template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts), [Vite build guide](https://vite.dev/guide/build.html)). |
| Design system | `@carbon/react` `1.112.0`, Sass `1.102.0`, `@ibm/plex` `6.4.1`, `@carbon/charts-react` `1.27.16` | `@carbon/react` is the Carbon v11 React package, supports React 19, requires Dart Sass for styles, and includes TypeScript declarations; Carbon Charts uses the same visual system ([Carbon React package](https://www.npmjs.com/package/@carbon/react), [Carbon React source](https://github.com/carbon-design-system/carbon/tree/main/packages/react), [IBM Plex package](https://www.npmjs.com/package/@ibm/plex), [Carbon Charts](https://charts.carbondesignsystem.com/)). |
| Python | CPython `3.12.13` x64, managed by uv; `.python-version` committed | The exact causal stack's declared Python intersection is `>=3.10,<3.14`; Python 3.12 is the conservative middle of that range. uv can install/pin Python and creates a cross-platform lockfile ([uv Python versions](https://docs.astral.sh/uv/concepts/python-versions/), [uv project layout](https://docs.astral.sh/uv/concepts/projects/layout/)). |
| API | FastAPI `0.140.0`, Uvicorn `0.51.0`, Pydantic `2.13.4` | Typed request/response models generate an explicit OpenAPI contract, while FastAPI/Starlette can serve static files for the one-process demo ([FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/), [Uvicorn deployment](https://fastapi.tiangolo.com/deployment/manually/)). |
| Causal analysis | DoubleML `0.11.3`, EconML `0.16.0`, DoWhy `0.14` | These are the exact strategy-approved libraries/classes: `DoubleMLIRM`, `CausalForestDML`, and DoWhy refuters ([DoubleML API](https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLIRM.html), [EconML causal forest API](https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html), [DoWhy refuters](https://www.pywhy.org/dowhy/main/user_guide/refuting_causal_estimates/index.html)). |
| Scientific compatibility pins | `scikit-learn==1.6.1`, `numpy==2.2.6`, `scipy==1.15.3` | DoubleML 0.11.3 requires scikit-learn `>=1.6.0` and NumPy `>=2.0`; EconML 0.16.0 requires scikit-learn `<1.7`; DoWhy 0.14 requires NumPy `>2.0` and, on Python 3.12, SciPy `<=1.15.3`. These pins satisfy the narrow intersection ([DoubleML 0.11.3 metadata](https://pypi.org/pypi/DoubleML/0.11.3/json), [EconML 0.16.0 metadata](https://pypi.org/pypi/econml/0.16.0/json), [DoWhy 0.14 metadata](https://pypi.org/pypi/dowhy/0.14/json)). |
| Persistence | Python standard-library `sqlite3`; versioned JSON/Parquet/model artifacts on disk | This matches the confirmed local SQLite audit decision without adding an ORM. Python ships the DB-API SQLite module ([Python `sqlite3`](https://docs.python.org/3.12/library/sqlite3.html)). |
| Tests | pytest `9.1.1`; Vitest `4.1.10`; `@playwright/test` `1.62.0` with Chromium only | pytest provides isolated temporary paths and monkeypatching; Vitest is Vite-native and allows a fixed sequencing seed. Playwright owns one browser-level Core-journey smoke test; `setup.ps1` installs its matching Chromium binary hermetically with `PLAYWRIGHT_BROWSERS_PATH=0`, so later test runs do not fetch browsers ([pytest fixtures](https://docs.pytest.org/en/stable/reference/fixtures.html), [Vitest sequence configuration](https://vitest.dev/config/sequence), [Playwright browser installation](https://playwright.dev/docs/browsers#install-browsers), [hermetic install](https://playwright.dev/docs/browsers#hermetic-install)). |

Version numbers above were checked against the official npm/PyPI registries on the verification date. The lockfiles, rather than this table, become the executable source of truth once implementation begins.

## Compatibility result observed on the target machine

A resolution-only uv check for Python 3.12 succeeded with all proposed backend pins. A temporary Windows import smoke test then loaded:

```text
DoubleML 0.11.3
EconML 0.16.0
DoWhy 0.14
scikit-learn 1.6.1
NumPy 2.2.6
SciPy 1.15.3
DoubleMLIRM
CausalForestDML
```

No repository environment or product file was created by the check. DoWhy emitted several nonfatal Python `SyntaxWarning`s for invalid escape sequences during first import. Treat these as known upstream noise unless they become errors under a future Python runtime; this is another reason to pin Python 3.12 and test warnings explicitly before upgrades.

## Smallest credible choices

| Concern | Candidates considered | Decision |
|---|---|---|
| Frontend toolchain | Vite SPA; hand-built bundler setup; SSR framework | Choose Vite SPA. It is the official template path for React/TypeScript, produces static assets, and avoids an unused server-rendering layer ([Vite guide](https://vite.dev/guide/)). |
| Backend transport | FastAPI/Pydantic; a hand-built standard-library HTTP layer | Choose FastAPI. The extra dependency buys validated schemas, generated OpenAPI, a test client, and static serving; rebuilding those boundaries would be false economy ([FastAPI features](https://fastapi.tiangolo.com/features/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)). |
| JavaScript dependency management | npm lockfile; introduce another package manager | Choose npm because it ships with Node. Commit `package-lock.json` and use `npm ci`, which performs a frozen clean install and errors when the lock disagrees with `package.json` ([npm `ci`](https://docs.npmjs.com/cli/v11/commands/npm-ci/)). |
| Python dependency management | uv project/lock; pip plus manually maintained requirement files | Choose uv. Commit `pyproject.toml`, `uv.lock`, and `.python-version`; setup uses `uv sync --locked`. Developer/test invocations that use uv add `--no-sync --no-python-downloads`; demo startup executes the prepared `.venv` Python directly. This prevents startup from resolving, synchronizing, or downloading dependencies ([uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/), [disabling automatic sync](https://docs.astral.sh/uv/concepts/projects/sync/#automatic-lock-and-sync)). |
| Charts | Carbon Charts; bespoke interactive SVG; backend-rendered static images | Use Carbon Charts for standard evidence charts and tables because it shares Carbon styling and React support. Use one small, accessible, Carbon-styled static SVG for the causal DAG unless graph interaction becomes a proven requirement. Do not add a second general chart system ([Carbon Charts React installation](https://charts.carbondesignsystem.com/react/)). |
| Process orchestration | Native PowerShell launcher; an additional process-manager package | Use scripts restricted to Windows PowerShell 5.1 syntax for the Windows-only prototype; this avoids requiring PowerShell 7. Development may run Vite and Uvicorn as child processes; the demo should run only Uvicorn after the SPA build. This keeps orchestration dependency-free and makes process cleanup explicit. |
| Packaging | Source + lockfiles + prebuilt SPA; PyInstaller executable; container | Choose source + locks for Core. PyInstaller bundles are OS/Python-specific and must be built on the target OS; freezing the compiled scientific stack adds a separate failure surface with no product value ([PyInstaller operating modes](https://pyinstaller.org/en/stable/operating-mode.html), [platform notes](https://pyinstaller.org/en/stable/usage.html#supporting-multiple-operating-systems)). A container adds installation and startup requirements that conflict with the smallest local Windows demo. |

## Runtime topology and commands to specify before coding

Keep one repository but two modules:

```text
frontend/     React + TypeScript + Carbon
backend/      FastAPI + causal/decision services
artifacts/    versioned validated analysis outputs
data/         generated fixtures and loader metadata, never restricted raw data
scripts/      setup/start/dev launchers
```

Define these behaviors in the implementation plan:

1. `setup.ps1` checks Node/uv, runs `npm.cmd ci`, runs `uv sync --locked`, installs the lock-matched Chromium binary once with `PLAYWRIGHT_BROWSERS_PATH=0`, builds the frontend, initializes a local audit DB from migrations/schema, and performs import/health smoke checks.
2. `start.ps1` performs no uv/npm command and no network installation. It verifies the built SPA, `.venv\Scripts\python.exe`, SQLite path, and validated artifact manifest. If any prerequisite is absent, it fails closed with “run `setup.ps1` while online”; it never attempts repair. It then starts one worker with `.venv\Scripts\python.exe -m uvicorn ...` on a fixed `127.0.0.1` port, waits for `/api/health`, and opens the system browser.
3. `dev.ps1` starts Uvicorn reload and Vite, with Vite proxying `/api` to the fixed backend port. The proxy is development-only ([Vite server proxy](https://vite.dev/config/server-options.html#server-proxy)).
4. The demo package contains the prebuilt SPA and validated artifacts. A fresh causal rerun writes a new immutable artifact version and audit event; it never overwrites the validated default.
5. Gemini remains optional and backend-only. Startup and every Core journey must succeed with network disabled by selecting the deterministic template fallback, as required by the strategy.

All launchers and documented verification commands must run under the Windows-inbox `powershell.exe` using PowerShell 5.1 syntax: no `&&`, no PowerShell 7-only operators, and explicit `npm.cmd` on Windows. For the demo runtime, bind only to `127.0.0.1`, use a single Uvicorn worker, and keep SQLite writes in short explicit transactions. Multiple workers provide no useful prototype benefit and would complicate local job state and SQLite ownership.

## Deterministic verification contract

Before implementation is considered ready, require all of the following:

- Commit `package-lock.json`, `uv.lock`, and `.python-version`; CI/demo setup uses frozen install commands.
- Seed the DGP, train/test splitting, nuisance learners, causal forest, refuters where supported, and every shuffled test. Record every seed in the artifact manifest.
- Run numerical golden tests with declared tolerances, not exact floating-point equality. Run the critical golden suite with thread counts fixed to one to reduce BLAS/OpenMP scheduling variance.
- Freeze time and environment-dependent paths in API/UI tests. Vitest's shuffle seed must be fixed when shuffling is enabled; pytest tests use isolated temporary directories and patched environment variables ([Vitest seed](https://vitest.dev/config/sequence), [pytest `tmp_path`](https://docs.pytest.org/en/stable/how-to/tmp_path.html), [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)).
- Contract-test each artifact/API schema and verify that unknown or stale schema versions fail closed.
- Smoke-test the exact imports/classes above, then fit a tiny deterministic dataset before running the expensive harness.
- Build the frontend with separate `npm.cmd ci` and `npm.cmd run build` commands, start the packaged app offline, assert `/api/health`, load the main journey through the preinstalled Playwright Chromium, exercise one approval write, and confirm replay from SQLite.
- Verify one validated-result journey, one genuine rerun, one abstention, and the zero-LLM artifact fallback. These are product claims, not optional polish.

## Material install and runtime risks

1. **Narrow scikit-learn window.** DoubleML 0.11.3 and EconML 0.16.0 overlap only on scikit-learn 1.6.x. Pin `1.6.1`; a casual upgrade to 1.7+ breaks the declared EconML constraint.
2. **Do not install `econml[dowhy]`.** EconML 0.16.0's optional `dowhy` extra declares `dowhy<0.13`, which conflicts with the strategy's DoWhy 0.14. Install the three base packages individually, or use the exact lock generated from the explicit top-level pins ([EconML metadata](https://pypi.org/pypi/econml/0.16.0/json)).
3. **Large scientific environment.** The resolved graph includes compiled/heavy packages such as SciPy, scikit-learn, LightGBM, Numba/llvmlite, CVXPY solvers, Matplotlib, Plotly, and Optuna. Preinstall and warm the demo machine; startup must never resolve or download packages.
4. **Graphviz risk on Windows.** DoWhy's `pygraphviz` support is optional and requires an external/native Graphviz toolchain. Do not select that extra for Core; render the planned DAG in the frontend instead ([DoWhy install guide](https://www.pywhy.org/dowhy/main/getting_started/install.html)).
5. **Carbon Sass and TypeScript edges.** Carbon requires Dart Sass, and its own package guidance still notes incomplete component typings and recommends `skipLibCheck: true`. Keep that relaxation limited to dependency declarations; application code remains strict ([Carbon React package](https://www.npmjs.com/package/@carbon/react)).
6. **Chart semantics.** Carbon Charts handles standard statistical displays, but a causal DAG is not a standard chart. Prefer a static accessible SVG over adding a graph library until interaction or automatic layout is required.
7. **Browser binary size and coupling.** Playwright browser binaries consume substantial disk space and must match the Playwright package. Install only Chromium during online setup and never run `playwright install` from startup ([Playwright browsers](https://playwright.dev/docs/browsers)).
8. **SQLite concurrency.** A single local app process is deliberate. If background analyses are later parallelized, serialize audit writes or give one owner process responsibility for persistence.
9. **Offline truthfulness.** Gemini cannot be part of the critical path. The demo must visibly distinguish validated cached results from freshly computed results and record whether prose came from Gemini or the deterministic fallback.

## Pre-coding gates

Lock this stack only after these short checks pass on the actual demo laptop:

1. Generate and commit the uv/npm locks from the exact pins above.
2. Re-run the import smoke test and a tiny fit/refuter/sensitivity smoke test.
3. Prove Carbon React and Carbon Charts compile under Vite with strict application TypeScript.
4. Prove the built SPA is served by FastAPI with correct deep-link fallback and no CORS dependency.
5. Prove `start.ps1` works with Wi-Fi disabled and no already-running developer process.
6. Record cold start, validated-result load, and fresh-run timings before deciding what is safe to execute live.

Until those gates pass, the versions are a researched baseline, not a claim that the full application has been verified.

## Wayfinder branch note

The repository has no commits (`HEAD` does not exist), so Wayfinder's throwaway research-branch convention cannot be satisfied yet. This asset was therefore written directly in the current uncommitted worktree, with no branch creation, commit, push, issue mutation, or other tracker action.
