# Round 2 hosting path for the locked Core stack

Research date: 2026-08-04  
Wayfinder ticket: [Verify a deployable hosting path for the locked Core stack](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/67)  
Map: [Plan the Round 2 hosted delivery of Causal Delay Copilot](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/66)

## Conclusion

There is **no verified deployable hosting path for the Core stack exactly as it is currently pinned**. The blocker is upstream of hosting: the authoritative Core specification pins `EconML==0.16.0` and `SHAP==0.49.1`, but EconML 0.16.0's published package metadata requires `shap>=0.38.1,<0.49.0`. A Linux/Python 3.12 `uv` dry run therefore fails before it selects a host image. This is a real dependency-contract contradiction, not a platform limitation ([authoritative Core specification](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/18), [EconML 0.16.0 metadata](https://pypi.org/pypi/econml/0.16.0/json)).

After the scientific pin contract is explicitly reconciled, the strongest **one-host prototype candidate** is:

> **One Railway Hobby service built from one multi-stage Dockerfile, with one Railway volume mounted at a configured data root, one Uvicorn worker, and the compiled Vite SPA served by FastAPI.**

This is a candidate, not yet a deployment decision. Railway's service-plus-volume topology fits the locked single-writer SQLite ledger and content-addressed filesystem artifacts unusually well: one volume is mounted into one service, replicas cannot be used with volumes, and volume-backed redeploys deliberately avoid two live deployments sharing the disk. Hobby permits a 5 GB volume and much larger compute/image ceilings than the Free plan ([Railway volume reference](https://docs.railway.com/volumes/reference), [Railway plan limits](https://docs.railway.com/pricing/plans)). The unresolved build, peak-memory, fresh-run-duration, cold-start, and SQLite recovery facts require one bounded throwaway deployment prototype before Railway can be locked.

No fully free option examined satisfies the current state contract:

- Railway Free is capped at 0.5 GB RAM, a 0.5 GB volume, a 4 GB image, and $1/month of included resource usage. Those ceilings are not evidence that this 86-package native scientific runtime can complete the required workflow ([Railway plan limits](https://docs.railway.com/pricing/plans)).
- Render Free has only 512 MB RAM and 0.1 CPU, sleeps after 15 idle minutes, loses its local filesystem on sleep/restart/redeploy, and cannot attach a persistent disk. A local SQLite ledger on it would be knowingly disposable ([Render Free limitations](https://render.com/docs/free), [Render instance types](https://render.com/docs/compute-plans)).
- Hugging Face CPU Basic offers adequate-looking compute at zero hourly cost, but creating a Docker Space now requires a $9/month PRO account. Its persistence mechanism is an attached mutable Storage Bucket rather than a documented local block volume; the docs do not establish the locking, fsync, atomic-rename, or crash-recovery semantics needed to approve SQLite plus manifest-last artifact publication without a prototype ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [Hugging Face pricing](https://huggingface.co/pricing), [Spaces storage](https://huggingface.co/docs/hub/spaces-storage), [Storage Buckets](https://huggingface.co/docs/hub/storage-buckets)).

## Authority and actual Core requirements

The live [Implement the local Causal Delay Copilot Core prototype](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/18) issue is the current, self-contained implementation authority. The older [Stage 2 local stack and packaging note](stage2_local_stack_packaging.md) is useful provenance, but its later-drifted versions are not pin authority.

The host must preserve these existing contracts rather than reshape the product to fit a frontend host:

- one real React/FastAPI application for local fallback, video, and the public deployed link, with no separate hosted demo logic;
- a Vite 7.3.1 / React 19.2.8 / TypeScript 5.9.3 frontend compiled to static assets and served by the same FastAPI process as `/api`;
- CPython 3.12.13, FastAPI 0.135.1, Uvicorn 0.41.0 standard, and the exact scientific package set named by the Core specification;
- a single backend worker/write lease;
- an authoritative append-only SQLite Governance & Audit ledger plus content-addressed analysis artifacts outside SQLite, with manifest-last atomic same-filesystem publication;
- bundled semi-synthetic, Olist, and SCMS fixtures only within their locked source-role ceilings; no uploads or confidential contractor/supplier/Kaya data;
- a validated-reference default journey and a genuine fresh-run path that never masquerades as cached computation;
- scientific/evidence boundaries, manager authority, deterministic checks, and a zero-LLM fallback. Gemini remains optional and may not become a hosting dependency.

The repository is still planning-only. It contains no `package-lock.json`, `pyproject.toml`, `uv.lock`, `.python-version`, Dockerfile, built SPA, SQLite database, or bundled dataset/artifact payload. Consequently, final source-context size, Docker image size, disk usage, build duration, peak RSS, and hosted fresh-run duration do not yet exist as measurable artifacts. Documentation alone cannot honestly settle them.

## Dependency and footprint verification

### Confirmed

1. The exact authoritative pins do not resolve:

   ```text
   EconML 0.16.0 -> shap>=0.38.1,<0.49.0
   Core pin      -> shap==0.49.1
   Result        -> unsatisfiable
   ```

   PyPI is the package publisher's distribution metadata authority here; it also declares Python 3.12 and Linux support for EconML 0.16.0 and publishes a CPython 3.12 manylinux x86_64 wheel ([EconML 0.16.0 metadata](https://pypi.org/pypi/econml/0.16.0/json)). SHAP 0.49.1 independently publishes a CPython 3.12 manylinux x86_64 wheel, so wheel absence is not the conflict ([SHAP 0.49.1 metadata](https://pypi.org/pypi/shap/0.49.1/json)).

2. A diagnostic-only substitution of `SHAP==0.48.0` made the complete named backend set resolve for CPython 3.12 on Linux x86_64: 86 packages, with no installation performed by that cross-platform dry run. This does **not** authorize changing the Core pin; it only shows that the hosting problem is probably isolated from a broader Linux-wheel failure.

3. Installing that diagnostic reconciled set into a disposable Windows target occupied 769,460,021 bytes (733.8 MiB) across 20,441 files. That is a dependency-directory observation, not a Docker image measurement. A final Linux image will also contain the interpreter, OS libraries, application, compiled SPA, and bundled data/artifacts, while a multi-stage build can exclude Node and build caches from the runtime layer.

### Unknown until the specification and implementation exist

- Which SHAP/EconML reconciliation preserves both the CausalForestDML contract and the locked predictive `PermutationExplainer` behavior.
- Whether the final lock selects only wheels in the chosen Linux base image or triggers any source compilation.
- Compressed and unpacked image size, build time, cache behavior, and build memory.
- Bundled dataset, validated-reference, release-pack, browser fallback, and runtime artifact sizes.
- Peak runtime memory and CPU for startup, validated-reference replay, and the representative 5,000-order-line fresh analysis.

## Candidate comparison

Facts in this table come from current first-party platform documentation. “Inference” means a project-specific conclusion drawn from those facts; it is not a platform promise.

| Requirement | Railway Hobby service + volume | Render web service + persistent disk | Hugging Face Docker Space + Storage Bucket |
|---|---|---|---|
| Build/image | Dockerfiles are supported. Hobby allows images up to 100 GB; the final image is unmeasured. The diagnostic dependency directory was 733.8 MiB ([Railway plans](https://docs.railway.com/pricing/plans), [Railway Dockerfile builds](https://docs.railway.com/builds/dockerfiles)). | Docker is supported. Starter build pipeline provides 2 CPU, 8 GB RAM, 16 GB disk, and a 120-minute build timeout; the final image is unmeasured ([Render web services](https://render.com/docs/web-services), [Render build pipeline](https://render.com/docs/build-pipeline)). | Docker Spaces accept an arbitrary Dockerfile and configure one app port. Official docs found in this research do not state an image-size or build-time limit, so those remain prototype facts ([Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)). |
| Native Python compatibility | Conditional pass after pin reconciliation: the complete named set resolved for CPython 3.12/Linux x86_64 in `uv`; EconML and SHAP publish cp312 manylinux wheels. | Same conditional Linux-wheel result; Render can build either a native Python service or Docker image. | Same conditional Linux-wheel result; Docker gives control of the Python 3.12 base image. |
| CPU/RAM | Free is only 1 vCPU/0.5 GB. Hobby permits up to 48 vCPU/48 GB per service aggregate and charges actual use. Exact required limits are unknown; prototype at 1 vCPU/2 GB, then adjust from measured peak ([Railway plans](https://docs.railway.com/pricing/plans), [Railway pricing](https://docs.railway.com/pricing)). | Free: 0.1 CPU/512 MB; Starter: 0.5 CPU/512 MB; Standard: 1 CPU/2 GB. The Standard tier is the first defensible prototype size, not a proven size ([Render instance types](https://render.com/docs/compute-plans)). | CPU Basic: 2 vCPU, 16 GB RAM, 50 GB ephemeral disk. Compute capacity looks strongest, but application creation requires PRO ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [Hugging Face pricing](https://huggingface.co/pricing)). |
| Request/job duration | HTTP requests may run 15 minutes only while transferring data and are closed after 5 minutes without data. The app should model a fresh run as an accepted operation plus status polling/WebSocket, not one silent blocking request. A long-lived service itself has no documented five-minute execution cap ([Railway networking limits](https://docs.railway.com/networking/public-networking/specs-and-limits)). | The reviewed web-service docs do not publish a general request-duration limit. A workflow task can run 30 seconds to 24 hours, but moving Core computation to a separate workflow would violate the preferred one-host/single-process simplicity unless later justified ([Render workflows](https://render.com/docs/workflows-defining)). | No authoritative proxy/request-duration limit was found. This is a prototype blocker for the fresh-run path. |
| Filesystem/persistence | One persistent volume mounted at one path; Hobby default/limit is 5 GB. One volume per service, no replicas, 3,000 read/write IOPS, and volume-backed redeploys prevent two active mounts. This structurally matches one SQLite writer plus artifacts under one data root ([Railway volumes](https://docs.railway.com/volumes/reference)). | Disk is available only to paid services and persists only its mount subtree. A disk belongs to one service instance, prevents multi-instance scaling, is unavailable during build/pre-deploy, and has daily snapshots. This also matches the single-writer topology ([Render disks](https://render.com/docs/disks)). | Container disk is ephemeral. A read-write Storage Bucket can be attached as a local-looking volume, but buckets are mutable S3-like storage and are non-versioned. POSIX/SQLite durability semantics were not documented ([Spaces storage](https://huggingface.co/docs/hub/spaces-storage), [bucket access patterns](https://huggingface.co/docs/hub/storage-buckets-access), [Storage Buckets](https://huggingface.co/docs/hub/storage-buckets)). |
| Cold start / sleep / expiry | Optional Serverless sleep after more than 10 minutes without outbound packets. First wake has delay and may return 502; in rare cases it may require a rebuild. Disable Serverless for a judging window unless a measured warm-up experience is accepted ([Railway Serverless](https://docs.railway.com/deployments/serverless)). | Free sleeps after 15 idle minutes and takes about one minute to wake; paid instances do not sleep. Free filesystem changes are lost on sleep ([Render Free](https://render.com/docs/free), [Render FAQ](https://render.com/docs/faq)). | CPU Basic sleeps after 48 hours of inactivity and a visitor restarts it. Exact wake latency is not stated ([Spaces GPU/lifecycle documentation](https://huggingface.co/docs/hub/spaces-gpus)). |
| HTTPS / URL | Instant Railway domain, automatic TLS, custom domains, HTTP/1.1 and HTTP/2 ([Railway public networking](https://docs.railway.com/networking/public-networking)). | Public `onrender.com` URL, managed TLS, custom domains; bind one public port at `0.0.0.0:$PORT` ([Render web services](https://render.com/docs/web-services)). | Public app at `https://<space-subdomain>.hf.space`; custom domains are supported for public/protected Spaces. Docker Space selects `app_port`, conventionally 7860 ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)). |
| Variables/secrets | Service/shared variables are injected at build and runtime; values can be sealed so they cannot be read back from UI/API ([Railway variables](https://docs.railway.com/variables)). | Environment variables and secrets are configured per service; platform variables include public URL and port ([Render web services](https://render.com/docs/web-services), [Render environment variables](https://render.com/docs/environment-variables)). | Settings provide public variables and private secrets as environment variables. Secrets are not copied when a Space is duplicated ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview)). |
| Egress/build friction | $0.05/GB egress; 5 GB Hobby volume storage costs $0.15/GB/month by used storage. One Docker build should compile Vite then install the locked Linux runtime. Public-safe bundled data and zero-LLM fallback mean runtime egress is not required for the Core journey ([Railway pricing](https://docs.railway.com/pricing)). | Free bandwidth/build minutes are quota-limited; paid pipeline and service costs apply. A persistent disk is unavailable to build steps, so seed/reference material must be in the image or copied/validated into the mounted data root at runtime ([Render Free](https://render.com/docs/free), [Render disks](https://render.com/docs/disks)). | Public repo source is visible in a public Space. Docker/Gradio compute creation requires PRO. Runtime outbound requests are limited to ports 80, 443, and 8080, which does not affect the zero-required-egress Core path ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview)). |
| Account/cost | Free provides $1/month; Hobby is $5/month including $5 of usage, then metered CPU/RAM/egress/storage. Railway requires a post-paid card. Hard usage limits can take workloads offline at the configured ceiling ([Railway plans](https://docs.railway.com/pricing/plans), [Railway cost control](https://docs.railway.com/pricing/cost-control)). | Hobby workspace has no base workspace fee, but a persistence-correct app requires a paid service plus disk. Current exact service/disk price should be confirmed in the dashboard before commitment because the public pricing page did not expose a stable machine-readable price table during this research ([Render FAQ](https://render.com/docs/faq), [Render disks](https://render.com/docs/disks)). | Personal PRO is $9/month and is required to create Docker Spaces; CPU Basic then has no hourly charge. Bucket storage has a free allowance and metered storage above it, but the exact included allowance was not stated on the reviewed docs ([Hugging Face pricing](https://huggingface.co/pricing), [Storage Buckets](https://huggingface.co/docs/hub/storage-buckets)). |
| Operational fit | Best fit if prototype passes: one service, one volume, one public origin, one worker, configurable resource cap, and optional sleep. Volume redeploys have some downtime. | Technically clean and always-on when paid, but Standard is the first plausible size and is likely a higher fixed-cost path. | Attractive RAM/CPU, but PRO gating and unproven bucket filesystem semantics add more project-specific uncertainty than Railway. |

## Recommended conditional deployment shape

Do not amend the Core plan to “Railway” yet. If the pin contradiction is resolved, prototype this exact shape and lock it only if every gate passes:

1. One multi-stage Dockerfile:
   - Node stage installs from the committed `package-lock.json` and builds the Vite SPA.
   - CPython 3.12.13 runtime stage installs only from the committed `uv.lock`, copies the SPA and public-safe bundles, and excludes Node, package-manager caches, test browsers, credentials, and source-only build artifacts from the runtime image.
2. One Railway Hobby service:
   - one Uvicorn worker;
   - bind `0.0.0.0:$PORT` in deployed mode;
   - serve SPA and `/api` from the same origin;
   - preserve the local mode's fixed `127.0.0.1` bind through typed configuration, not a second application.
3. One Railway volume mounted at a single configured data root:
   - SQLite ledger, content-addressed member store, manifests, quarantine, backups/archives, and runtime logs use explicit subdirectories under this root;
   - packaged read-only reference inputs may remain in the image, but any authoritative runtime state must be on the volume;
   - retain the one-write-lease and one-worker rules.
4. No required external service:
   - no hosted Postgres migration merely for deployment;
   - no object-store split;
   - no required Gemini/API call;
   - no uploads or real data.
5. Fresh analysis is a durable manager operation with status polling or WebSocket progress, not one silent HTTP request held open near an edge timeout. This transport statement does not weaken the existing run, evidence, idempotency, or cancellation contracts.

## Required throwaway prototype

The prototype is evidence collection, not product implementation. Use a disposable service/repository or branch and synthetic/public-safe data only. Do not carry prototype shortcuts into Core.

### Build and compatibility gate

- Reconcile the SHAP/EconML contract first and regenerate an exact `uv.lock` for CPython 3.12/Linux x86_64.
- Build with the intended Python 3.12.13 and Node/Vite stages.
- Prove `uv sync --locked` uses compatible Linux distributions and import-smoke `DoubleMLIRM`, `CausalForestDML`, DoWhy refuters, Statsmodels, PyArrow, and the selected SHAP `PermutationExplainer` path.
- Record build duration, peak build RAM, compressed image size, unpacked image size, cache-hit rebuild duration, and whether any package compiled from source.
- Fail if the final image exceeds the selected plan limit or the lock differs from the authoritative contract.

### Runtime and workflow gate

- Start with explicit 1 vCPU / 2 GB limits; record idle RSS, import/startup peak RSS, validated-reference peak RSS, fresh-run peak RSS/CPU, and OOM/restart events.
- Run the representative 5,000-order-line scientific path three times with locked seeds and single-thread settings; record time to terminal artifact. Do not claim the local-laptop under-five-minute qualification from hosted timings.
- Exercise the browser journey through the real SPA/API origin, including validated reference, one genuine fresh run, one abstention, replay, manager write, and zero-LLM fallback.
- Verify the request/status transport survives Railway's five-minute no-data and 15-minute streaming bounds without pretending a cached result is fresh.
- Test SIGTERM/cancellation and confirm incomplete artifacts are quarantined and no false terminal audit event is published.

### Persistence and recovery gate

- Put SQLite and the entire mutable artifact tree on the mounted volume; verify mount ownership for the non-root runtime user.
- Commit an audit event and atomically publish an artifact member set plus manifest; restart the service and verify exact replay and every hash/size/schema reference.
- Redeploy a new image and repeat the verification after Railway's volume-backed deployment handoff.
- Force an interrupted transaction and an interrupted pre-manifest artifact write; verify rollback/quarantine and absence of a selectable partial bundle.
- Create and restore a volume backup/archive using the proposed operator runbook; confirm `event_seq`, immutable snapshots, idempotency, and content-addressed references survive.
- Fill the volume near its alert threshold and verify fail-closed behavior before SQLite or manifest corruption.

### Availability, URL, and cost gate

- Verify the Railway-provided HTTPS URL, health/readiness distinction, forwarded HTTPS handling, SPA deep-link fallback, and mobile browser access.
- Measure Serverless sleep and wake, including whether the first request returns 502. For the submission/judging window, test with Serverless disabled and record the actual daily cost at the measured resource settings.
- Set a compute hard limit and alert high enough not to take the judged app offline; document the deliberate trade-off.
- Confirm the account can provision Hobby service, volume, chosen region, and payment method from the team's location.
- Audit the runtime environment and built frontend to prove secrets are absent; only non-sensitive public configuration may enter `VITE_*` build variables.

### Pass/fail rule

Railway becomes the hosting decision only if all build, runtime, persistence, recovery, public-URL, and cost gates pass with the reconciled lock. Any failure returns to the hosting decision; it must not be patched by weakening scientific checks, replacing SQLite/artifact authority, using separate demo logic, removing manager authority, uploading real data, or making Gemini required.

## Confirmed facts, inferences, and unresolved facts

### Confirmed

- The authoritative Core dependency pins are unsatisfiable because of the EconML/SHAP constraint.
- The rest of the named stack resolves for Linux x86_64/Python 3.12 when SHAP is diagnostically changed to 0.48.0.
- Railway Hobby supplies a persistent single-service volume and ample configurable image/resource ceilings; Railway Free does not supply an evidenced adequate RAM budget.
- Render Free cannot preserve the SQLite/artifact state.
- Hugging Face Docker Spaces require PRO, and their durable storage is now a Storage Bucket volume.
- NotebookLM could not be used: `notebooklm auth check --test --json` returned `status=error` and `token_fetch=false`; an allowed in-place refresh did not restore authentication. Research therefore continued against selected current primary sources directly.

### Inferences

- Railway Hobby is the lowest-friction topology because its platform constraints reinforce rather than fight the existing one-worker/single-writer design.
- A 2 GB/1 vCPU prototype starting point is reasonable, but it is not a capacity claim.
- A multi-stage image should fit comfortably under Railway Hobby's 100 GB image limit, but only the final implementation can measure this.
- Serverless should probably be disabled during the judged availability window because an initial 502 is incompatible with a dependable submission link; the resulting cost must be measured before this becomes a decision.

### Unresolved

- The approved SHAP/EconML reconciliation and its scientific regression evidence.
- Final lockfile, image, dataset/reference, disk, and memory sizes.
- Hosted fresh-run time, peak resource use, and one-worker responsiveness.
- Exact SQLite/WAL, atomic rename, restart, redeploy, backup, and restore behavior on a Railway volume.
- Railway cold-boot behavior for this large image and the always-on judging-window cost.
- Team account/payment/region availability.
- Whether the deployed link must remain continuously warm for a stated judging period; the organizer instruction only establishes that it must be live and accessible.

## Validation commands run

Read-only repository and tracker inspection:

```powershell
git status --short
rg --files -g '!*node_modules*' -g '!*.pyc' | Sort-Object
rg -n -i "sqlite|artifact|filesystem|one-worker|uvicorn|python 3.12|fastapi|vite|react|DoubleML|EconML|DoWhy|shap|pyarrow|dataset|bundled|single writer|single-user|local browser|deployment|host|persist|ledger" ...
gh issue view 66 --repo Mridul-Sharma17/Causal-Delay-Copilot --json number,title,body,url,labels,state,assignees
gh issue view 67 --repo Mridul-Sharma17/Causal-Delay-Copilot --json number,title,body,url,labels,state,assignees
gh issue view 18 --repo Mridul-Sharma17/Causal-Delay-Copilot --json body --jq .body
```

Context7 (two commands; within the three-command cap):

```powershell
npx.cmd ctx7@latest library "Hugging Face Hub" "Docker Spaces CPU Basic hardware persistent storage secrets variables sleep custom domains and port 7860"
npx.cmd ctx7@latest docs /huggingface/hub-docs "Docker Spaces CPU Basic hardware persistent storage secrets variables sleep custom domains and port 7860"
```

NotebookLM availability check:

```powershell
notebooklm --version
notebooklm auth check --test --json
notebooklm list --json
notebooklm auth refresh
notebooklm auth check --test --json
```

PyPI metadata verification:

```powershell
Invoke-RestMethod -Uri 'https://pypi.org/pypi/econml/0.16.0/json'
Invoke-RestMethod -Uri 'https://pypi.org/pypi/shap/0.49.1/json'
```

Exact-pin Linux/Python 3.12 resolution check (failed as expected at the EconML/SHAP contradiction):

```powershell
uv pip install --dry-run --target "$env:TEMP\cdc-hosting-linux-dryrun" --python-version 3.12 --python-platform x86_64-unknown-linux-gnu `
  "fastapi==0.135.1" "uvicorn[standard]==0.41.0" "pydantic-settings==2.13.1" `
  "DoubleML==0.11.3" "EconML==0.16.0" "DoWhy==0.14" `
  "scikit-learn==1.6.1" "numpy==2.2.6" "scipy==1.15.3" `
  "statsmodels==0.14.6" "pandas==2.3.3" "pyarrow==23.0.1" `
  "joblib==1.5.3" "threadpoolctl==3.6.0" "shap==0.49.1"
```

Diagnostic-only reconciliation and footprint checks:

```powershell
uv pip install --dry-run --target "$env:TEMP\cdc-hosting-linux-dryrun-reconciled" --python-version 3.12 --python-platform x86_64-unknown-linux-gnu <same pins, with "shap==0.48.0">
uv pip install --target "$env:TEMP\cdc-hosting-footprint-shap048" --python-version 3.12 <same pins, with "shap==0.48.0">
Get-ChildItem -LiteralPath "$env:TEMP\cdc-hosting-footprint-shap048" -File -Recurse | Measure-Object -Property Length -Sum
```

The diagnostic substitution is evidence only. It is not a proposed silent edit to the authoritative Core specification.
