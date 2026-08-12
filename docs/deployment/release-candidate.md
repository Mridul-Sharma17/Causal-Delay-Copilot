# Release Candidate deployment

The repository contains one manually dispatched workflow,
`.github/workflows/release-candidate.yml`. It builds the Docker image once,
extracts the compiled SPA from that same image, hashes the source/lockfiles,
schemas, migrations, policies, model identity, references, image, and SPA, and
publishes one immutable `build_manifest_id`.

The workflow then:

1. binds the release IDs on Railway and deploys Railway first;
2. waits for the Railway readiness and `/api/release` preflight;
3. deploys the exact extracted SPA plus the Vercel release guard without
   assigning the production domain;
4. fails closed unless the Railway API, Vercel `release.json`, and Vercel
   `/api/release` expose the same `release_candidate_id` and `build_manifest_id`;
5. waits for the protected `production` environment approval before promoting
   Vercel; and
6. re-reads the final public origin after activation.

Configure required reviewers on the GitHub `production` environment. The
`release-candidate` environment may be used for non-public candidate checks,
but it must still have the repository's normal approval policy.

## GitHub Actions secrets and variables

Required GitHub Actions secrets are platform credentials and identifiers:

```text
RAILWAY_TOKEN
RAILWAY_PROJECT_ID
RAILWAY_SERVICE_ID
RAILWAY_ENVIRONMENT_ID
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_PROJECT_ID
```

Required environment-scoped variables are public origins, not API keys:

```text
RAILWAY_PUBLIC_ORIGIN=https://<railway-service-origin>
VERCEL_PUBLIC_ORIGIN=https://<vercel-production-origin>
```

The build job pushes the pinned backend image to GHCR with the automatic
`GITHUB_TOKEN`, then Railway is pointed at that exact image digest. The Railway
service must already have pull access to the GHCR package (make the package
public or configure its private-registry credential in Railway's service
settings); that registry credential is platform configuration, not a frontend
or Vercel variable.

The workflow never copies Gemini credentials into Vercel or into `VITE_*`
variables. On Railway, configure these service variables:

```text
CORE_PROFILE=HOSTED
CORE_STATE_ROOT=/data/core
CORE_RAILWAY_VOLUME_PATH=/data
CORE_PUBLIC_ORIGIN=https://<vercel-production-origin>
CORE_GEMINI_ENABLED=true
```

If Gemini drafting is enabled, put the existing raw Gemini key in the Railway
service's secret variable named `CORE_GEMINI_API_KEY`. A Windows environment
variable is local machine configuration; Railway does not read it automatically.
If the key is absent or Gemini is disabled, the deterministic drafting fallback
remains authoritative.

The workflow sets `CORE_RELEASE_CANDIDATE_ID` and `CORE_BUILD_MANIFEST_ID` from
the manifest for each deployment. Do not hand-edit those two values between the
Railway and Vercel checks.

## Hosted qualification

After activation, run the manually dispatched
`.github/workflows/hosted-qualification.yml` workflow against the successful
release workflow run and its artifact, for example:

```powershell
gh workflow run hosted-qualification.yml -f release_run_id=31550053794 -f release_artifact_name=release-rc-c36a01fc9358 -f budget_alert_record_ref=<railway-alert-ref> -f budget_alert_actor=<operator> -f budget_alert_observed_at=2026-08-12T00:00:00Z
```

For a deliberate fresh Railway volume, dispatch the release workflow with an
explicit new state root, for example `-f railway_state_root=/data/core2`.
The default remains `/data/core`; the selected root must be below the mounted
Railway volume and must already contain either a matching sealed state or no
state so the application can initialize it for that exact release.

The workflow fetches the `source_commit` in the downloaded release manifest
for exact deployment-configuration checks, checks only the public Vercel
origin for browser behavior,
and uses the pinned Railway and Vercel CLIs for platform state. The browser
seam then exercises the real Vercel-to-Railway-to-SQLite path for the validated
reference, typed abstention, workspace isolation, mutation/rate limits, queue
capacity, and restart recovery. A separate immutable preview with deliberately
mismatched release IDs must receive `RELEASE_IDENTITY_MISMATCH` before the
release-mismatch check can pass.

The browser checks intentionally create bounded workspaces, audit mutations,
and durable operations. Run the qualification once for a release candidate;
repeat it only when the resulting mutation and workspace consumption is
acceptable for that hosted environment.

Every run with a valid release manifest writes `hosted-delivery-attestation.json`
and its SHA-256 sidecar, including blocked runs. An invalid invocation writes a
typed `hosted-qualification-failure.json` artifact instead and cannot qualify.
The attestation is `QUALIFIED` only when every required check is `VERIFIED`;
local tests, the static reference fallback, a missing reference, or a missing
budget-alert record remain typed blocking states. The Railway budget
notification is recorded alert evidence only: it must identify the `$4`
threshold, `hard_cap: false`, the operator, observation time, and the external
record reference. Its external verification state remains `UNAVAILABLE`
because the CLI cannot independently read billing alerts.

## Rollback

Rollback is a new deployment occurrence. The workflow records an append-only
`release-rollback-occurrence.v1` artifact before invoking Railway and Vercel
rollback commands. It does not delete or rewrite SQLite state, audit history,
evidence bundles, release manifests, or attestations. A rollback whose target
identities cannot pass the same release preflight stays unavailable.

For a rollback dispatch, provide the currently active release and build IDs,
the target release and build IDs, the target source commit, the target Railway
image reference and digest, the immutable Vercel deployment ID, and a non-empty
reason. The workflow preflights Railway before the Vercel rollback and verifies
both public services after the mutation.
