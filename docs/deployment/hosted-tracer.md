# Hosted tracer bullet

Hosted delivery is the same React/FastAPI application as local delivery. Vercel
is the only browser origin; it serves `frontend/dist` and rewrites relative
`/api/*` requests to the one Railway service. The Railway service runs the
committed `Dockerfile`, and its `/data` volume is the only durable application
state location.

## Railway setup

The Railway service must have these variables before its first start:

```text
CORE_PROFILE=HOSTED
CORE_STATE_ROOT=/data/core
CORE_RAILWAY_VOLUME_PATH=/data
CORE_PUBLIC_ORIGIN=https://<final-vercel-origin>
CORE_RELEASE_CANDIDATE_ID=<release-candidate-id>
CORE_BUILD_MANIFEST_ID=<build-manifest-id>
```

The image supplies the one-worker, one-writer, one-compute-subprocess defaults
and serves the compiled SPA from `/app/frontend/dist`. Attach exactly one
Railway volume at `/data`; the state initializer refuses an unmounted or
misplaced hosted state root.

Use the Railway CLI for the linked project and service:

```powershell
npx.cmd @railway/cli@latest login
npx.cmd @railway/cli@latest link
npx.cmd @railway/cli@latest volume add --mount-path /data
npx.cmd @railway/cli@latest up --detach
npx.cmd @railway/cli@latest status
npx.cmd @railway/cli@latest logs
```

Keep Serverless/App Sleeping disabled for the judging service. That platform
toggle is not part of the repository's config-as-code surface, so it must be
verified in the linked Railway service configuration before qualification.

## Vercel setup

Vercel's static configuration cannot safely discover an arbitrary Railway
domain from browser code. `vercel.json.template` therefore contains one
explicit origin token. Render it only after the Railway public origin exists:

```powershell
$env:CORE_RAILWAY_PUBLIC_ORIGIN = "https://<railway-service-origin>"
& .\scripts\prepare-vercel.ps1
npx.cmd vercel@latest deploy --prod
```

The generated `vercel.json` is ignored locally and contains no client-side API
URL. It applies `no-store` to HTML/API responses, disables caching for the
external API rewrite, applies the public security policy, and makes Vite's
hashed `/assets/*` files immutable.

## Browser verification

After both services are live, run the repository-local smoke against the
Vercel origin:

```powershell
$env:CORE_E2E_BASE_URL = "https://<final-vercel-origin>"
npm.cmd run test:e2e
```

The smoke must show the typed health state, an active isolated Demo Workspace,
and one recorded immutable audit occurrence. No capability, source row,
prompt, provider response, note, stack trace, or filesystem path is rendered.

For the production Release Candidate workflow, see
[`release-candidate.md`](release-candidate.md). Production activation is a
protected GitHub Actions approval after Railway preflight and exact Vercel /
Railway release-identity matching.
