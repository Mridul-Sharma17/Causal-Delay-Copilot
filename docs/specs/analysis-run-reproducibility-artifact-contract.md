# Analysis-Run and Reproducibility-Artifact Contract

## Status and authority

This specification resolves the Core physical boundary for an Analysis Run. It
defines immutable run identities, reproducibility inputs, artifact envelopes,
runtime and model metadata, cache identity and reuse, atomic publication,
validation attestations, retention, failure recovery, and the safe read boundary
used by the browser UI.

It is subordinate to:

- `docs/causal_delay_copilot_stage2_strategy.md` for product and scientific
  intent;
- `docs/specs/canonical-order-event-lineage-contract.md` for source facts,
  Dataset Version identity, validation, missingness, provenance, and
  confidentiality;
- `docs/specs/exposure-outcome-temporal-eligibility-contract.md` for frozen run
  inputs, cohort stages, scientific gates, and abstention; and
- `docs/specs/executable-causal-engine-contract.md` for the executable request,
  exact runtime and seed policy, logical result, required components, error
  precedence, and replay tolerance.

If these sources disagree, the Stage 2 strategy controls intent, the canonical
lineage contract controls source-fact and confidentiality semantics, the
temporal-eligibility contract controls scientific eligibility, and the engine
contract controls estimation semantics. This contract controls only physical
run execution, storage, validation, reuse, and UI consumption.

This is a planning artifact. It does not implement the product.

### `Run fresh` is not `Refresh investigation`

The ingress contract already defines an investigation rerun as a new
Investigation Request with a later source decision clock, newly frozen
observation cutoff, and explicit configuration references. That operation may
legitimately change the scientific input and result.

The UI command **Run fresh** has a narrower meaning: execute the selected
Analysis Run's exact frozen `CausalEngineSuiteRequest` again in a new local
process under the same runtime contract and root seed. It creates a new
Analysis Run with `reproduces_run_id` and the same scientific request digest.
It does not create a new Investigation Request, advance an observation cutoff,
refresh a Dataset Version, or inspect newer facts.

A later **Refresh investigation** feature must use the ingress rerun contract
and a new Analysis Run. It is not part of this Core contract.

## Canonical terms

- **Analysis Run** is one uniquely identified execution. Repeating identical
  inputs creates a new Analysis Run; run identity is never a content digest.
- **Analysis Artifact Bundle** is the immutable, atomically sealed set of
  content-addressed files that preserves one Analysis Run's reproducibility
  inputs, result, and verification evidence.
- **Validation Attestation** is a separate immutable statement that one exact
  bundle hash passed one exact release-validation policy. It never changes the
  bundle it references.
- **Validated Reference** is a release-registry designation pointing to a
  bundle with a valid Validation Attestation. It is not a mutation of the run.
- **Run delivery mode** records whether one UI request caused
  `fresh_execution` or `existing_run_reuse`. It is carried by a
  Governance-owned Audit Event, not treated as a scientific result or
  persistent property of an Analysis Run.

## Core invariants

1. One execution has one opaque `analysis_run_id`; every repeat has a new ID.
2. Run IDs, wall-clock timestamps, audit actors, and UI request IDs never enter
   scientific hashes, cache keys, fold assignment, or seed derivation.
3. Every scientific input, configuration reference, root and derived seed,
   runtime pin, thread rule, model recipe, output, and required diagnostic is
   retained directly or through a hash-bound immutable object.
4. A completed bundle is immutable. Correction, recomputation, changed input,
   changed configuration, or changed runtime creates a new Analysis Run.
5. An Analysis Run is logically self-contained. Reproduction never resolves
   mutable `latest` aliases or depends on an upstream object that can change.
6. Physical object files may be deduplicated by hash without weakening the
   logical completeness or retention rules of a run.
7. Raw source files, adapter secrets, evaluation-only ground truth, and fitted
   Python model objects never enter a bundle.
8. No pickle, joblib, executable Python object, notebook, or arbitrary archive
   is a supported artifact type.
9. Only a manifest published last by same-filesystem atomic replacement seals
   a bundle. A directory's existence does not imply validity.
10. The browser UI never opens artifact files or SQLite rows. The Python
    backend verifies and projects a closed, versioned read model.
11. `estimated` and `abstained` are valid scientific outcomes. A failed,
    interrupted, corrupt, or incompatible run exposes no estimate.
12. A cache hit reuses an existing immutable Analysis Run and records new
    Governance Audit Events for the delivery attempt. It never fabricates a
    run.
13. **Run fresh** bypasses cache and performs a genuine new execution.
14. Cache validity has no time-to-live. Any scientific, schema, application,
    or compute-runtime fingerprint change creates a cache miss.
15. `fresh_execution`, `existing_run_reuse`, scientific outcome, lifecycle,
    availability, and validation are separate dimensions.
16. Machine verification permits safe local display but never silently makes a
    run a Validated Reference.
17. Only the developer-operated release-validation workflow may issue a
    Validation Attestation or update a validated-reference registry.
18. Validation and promotion never rewrite, relabel, or copy-edit a bundle.
19. The reference-validation gate fails closed on any missing check,
    out-of-tolerance replay, unsupported schema, or confidentiality finding.
20. The single-user Core permits one fresh execution at a time. Sealed-bundle
    reads remain available while it runs.
21. Interrupted executions are never resumed. Retry creates a new Analysis Run.
22. Validated References and runs referenced by an Audit Event or Manager
    Decision are pinned against cleanup.
23. Core has no automatic expiry. Cleanup is explicit, developer-operated, and
    must refuse pinned runs.
24. SHA-256 hashes and the release allow-list detect corruption and accidental
    mismatch; they do not claim protection against a malicious local operator.
25. The OS account and local filesystem are the Core confidentiality and
    access-control boundary. Artifact signing and application-level encryption
    at rest are outside Core.

## Closed identifier and version registry

| Logical item | Required ID or version |
| --- | --- |
| Contract | `analysis-run-artifacts.v1` |
| Bundle manifest schema | `analysis-run-bundle-manifest.v1` |
| Artifact descriptor schema | `analysis-artifact-descriptor.v1` |
| Runtime fingerprint schema | `analysis-runtime-fingerprint.v1` |
| Cache-key schema | `analysis-run-cache-key.v1` |
| Verification-report schema | `analysis-run-verification.v1` |
| Reproduction-projection schema | `analysis-run-reproduction-projection.v1` |
| Reproduction-comparison schema | `analysis-run-reproduction-comparison.v1` |
| Failure-manifest schema | `analysis-run-failure-manifest.v1` |
| Quarantine-manifest schema | `analysis-run-quarantine-manifest.v1` |
| Validation-attestation schema | `analysis-run-validation-attestation.v1` |
| Validated-reference registry | `validated-analysis-references.v1` |
| UI read-model schema | `analysis-run-read-model.v1` |
| Run-delivery Audit Event payload | `analysis-run-delivery-audit-payload.v1` |
| Integrity-finding Audit Event payload | `analysis-run-integrity-audit-payload.v1` |
| Run error registry | `analysis-run-errors.v1` |
| Cleanup-intent schema | `analysis-artifact-cleanup-intent.v1` |
| Cleanup-result schema | `analysis-artifact-cleanup-result.v1` |
| Scientific canonical encoding | `canonical-scientific-json.v1` |

Changing field meaning, required artifact roles, canonical bytes, hash payload,
state semantics, cache membership, validation gates, or safe UI projection
increments the owning version. Additive free-form extension maps are
prohibited.

## Identity and hash model

### Analysis Run ID

`analysis_run_id` is `analysis-run-` followed by a lower-case RFC 4122 UUIDv4.
It identifies an execution, not its inputs or result. It is generated before
temporary run material is written, immediately after the execution lease is
acquired, and must not be reused after any failure. A request rejected with
`RUN_EXECUTION_BUSY` never becomes an Analysis Run and receives no run ID.

The manifest may contain:

- `reproduces_run_id` only for exact technical reproduction;
- `retries_run_id` only after an interrupted, quarantined, or orchestration-
  failed attempt; and
- `investigation_request_id` when the run serves an Investigation Request.

The three relationships have different meanings and never substitute for one
another. A reproduction retains the original Investigation Request reference
only as provenance; it is not a new accepted request.

### Scientific request digest

`scientific_request_digest` is the lower-case `sha256:` digest of the complete
canonical `CausalEngineSuiteRequest` bytes. Those bytes include the exact
engine request schema, Dataset Version, frozen cutoffs, all cohort rows and
lineage references, configuration and suite versions, root seed, adjustment
set, propensity specification, and optional subject.

The digest excludes `analysis_run_id`, execution timestamps, process identity,
delivery mode, audit actor, UI route, and validation state.

### Runtime fingerprint

`runtime_fingerprint` is a closed record containing:

- schema version;
- application build ID and the SHA-256 hashes of `uv.lock` and the installed
  environment lock/export used by the prepared environment;
- CPython implementation and exact version;
- exact versions of every direct or transitive package loaded by the engine;
- exact engine, question, suite, propensity, seed-policy, feature-schema,
  output-schema, and artifact-contract versions;
- operating-system family, version and build, machine architecture, byte order,
  and C/Python floating-point representation;
- numerical backend identities and versions for BLAS, LAPACK, OpenMP, MKL, or
  equivalent loaded backends;
- the allow-listed numerical thread variables and their effective values; and
- the engine's single-thread execution policy.

It contains no general environment dump, user name, host name, filesystem path,
credential, token, or unrelated installed-package inventory.

`runtime_fingerprint_digest` hashes this record under
`canonical-scientific-json.v1`.

### Cache key

The cache key is:

```text
sha256(canonical-scientific-json.v1({
  "schema_version": "analysis-run-cache-key.v1",
  "scientific_request_digest": <digest>,
  "runtime_fingerprint_digest": <digest>,
  "engine_output_schema_version": <version>,
  "bundle_manifest_schema_version": "analysis-run-bundle-manifest.v1",
  "artifact_contract_version": "analysis-run-artifacts.v1"
}))
```

The output is stored as lower-case `sha256:<hex>`. No timestamp, run ID,
investigation ID, validation designation, or filesystem location participates.
Changing any scientific request byte, root seed, model recipe, dependency,
thread rule, application build, numerical backend, or owning schema changes the
key.

### Object and bundle hashes

Every artifact object uses SHA-256 over its exact file bytes. The object path is
derived only from its closed confidentiality class and that digest.

`bundle_manifest_hash` is SHA-256 over the canonical manifest core, including
the complete ordered artifact-descriptor list, but excluding the
`bundle_manifest_hash` field itself. The manifest does not list itself as an
artifact. A Validation Attestation and validated-reference registry are
external and therefore cannot create a self-reference or mutate the bundle
hash.

Hash collision or a pre-existing object whose bytes do not match its requested
digest is `RUN_ARTIFACT_INTEGRITY_MISMATCH`; the new run is quarantined and the
existing object is never overwritten.

## Orthogonal run state

### Lifecycle

| State | Meaning | UI evidence consumable |
| --- | --- | --- |
| `executing` | Exclusive lease is live; only temporary files exist | No |
| `sealed` | Atomic manifest exists and all required artifacts verify | According to scientific outcome |
| `failed` | A safe terminal failure manifest was sealed; no valid evidence bundle exists | No |
| `quarantined` | Partial, corrupt, interrupted, or reproducibility-violating material is isolated | No |

Transitions are one-way:

```text
executing -> sealed
executing -> failed
executing -> quarantined
```

No terminal state returns to `executing`. A retry creates a new run ID.

### Scientific outcome

The engine result remains exactly:

```text
estimated | abstained | failed
```

A `sealed` run may contain `estimated` or `abstained`. An engine `failed`
result produces lifecycle `failed`, with only the safe failure artifacts
allowed below. No runtime layer translates abstention into failure or failure
into abstention.

### Verification state

| State | Meaning |
| --- | --- |
| `machine_verified` | Bundle integrity, schema, required-role, safe-format, and logical cross-reference checks passed |
| `reference_validated` | A valid external attestation and current release-registry entry additionally exist |
| `invalid` | Any required verification or reproduction check failed |

`reference_validated` is derived at read time from the bundle hash, attestation,
and release registry. It is not written into the bundle.

### Availability state

Terminal lifecycle is immutable. A separate, rebuildable availability state is:

| State | Meaning |
| --- | --- |
| `available` | Current verification supports cache selection and read-model projection |
| `suppressed` | Post-seal verification found corruption, unsafe paths/formats, unsupported schema, or inconsistent references |

Suppressing a run never changes `sealed`, moves a bundle, or rewrites evidence.
The index records the safe reason code and an
`analysis_run_integrity_failed` Audit Event binds the run ID, bundle hash,
affected confidentiality-class/object-digest pair when safe,
verification-policy version, and UTC time.
If a shared object fails verification, every bundle descriptor referencing that
confidentiality-class/object-digest pair is suppressed. Suppressed bundles are
`invalid` under the current verification policy and are excluded from cache and
UI evidence until a new verified run or prepared release is selected; Core
does not repair them in place.

### Run delivery mode and Audit Events

Governance & Audit owns persistence of material workflow occurrences. This
contract supplies a closed `analysis-run-delivery-audit-payload.v1`; it does
not introduce a competing event type.

Each accepted UI load or fresh command creates one
`analysis_run_delivery_requested` Audit Event containing:

- an opaque `delivery_attempt_id`;
- requested policy: `reuse_allowed` or `fresh_required`;
- target run/reference slot and requesting workflow references when known; and
- UTC request timestamp.

Exactly one terminal Audit Event with the same `delivery_attempt_id` follows:

- `analysis_run_delivery_succeeded`, with actual delivery mode
  `fresh_execution` or `existing_run_reuse`, `analysis_run_id`,
  `bundle_manifest_hash`, cache key, verification state, and UTC delivery
  timestamp; or
- `analysis_run_delivery_failed`, with one closed safe run error code, any
  available run ID, and UTC failure timestamp.

Startup reconciliation emits `analysis_run_delivery_failed` with
the terminal run-manifest code when a failure/quarantine manifest exists. If a
valid success manifest exists but no terminal Audit Event does, the run remains
sealed and available while the attempt receives `RUN_DELIVERY_INTERRUPTED`.
If no terminal manifest exists, a matching temporary executing-state record
proves the fresh execution began and yields `RUN_EXECUTION_INTERRUPTED`;
without that record the command yields `RUN_DELIVERY_INTERRUPTED` because
execution never became observable. An unterminated reuse attempt likewise
receives `RUN_DELIVERY_INTERRUPTED` and does not change its target run. A
request rejected before acceptance creates no Audit Event.
`RUN_EXECUTION_BUSY` occurs after an accepted fresh command but before a run ID
exists, so its ordinary failure event has no run ID.

Audit Events never change the run. A Validated Reference can be reused; a newly
machine-verified run can have been freshly executed. Delivery mode, validation,
and scientific outcome are deliberately separate.
`analysis_run_delivery_succeeded` means the backend durably committed a
verified response for return; it is not proof that the browser rendered it or
that a manager viewed it. Presentation/decision Audit Events own those later
claims.

## Physical storage layout

All paths are relative to one configured, local `<artifact_root>`:

```text
<artifact_root>/
  objects/
    <confidentiality_class>/
      sha256/
        <first-two-hex>/
          <remaining-sixty-two-hex>
  runs/
    <analysis_run_id>/
      manifest.json
      failure-manifest.json
  attestations/
    <validation_attestation_id>.json
  releases/
    <release_id>/
      validated-references.json
  index/
    analysis-runs.sqlite3
  leases/
    fresh-execution.lock
    maintenance.lock
  temporary/
    <analysis_run_id>/
  quarantine/
    <analysis_run_id>/
      quarantine-manifest.json
  maintenance/
    cleanup/
      <cleanup_operation_id>/
        intent.json
        result.json
  developer-logs/
```

The later application-architecture decision chooses the absolute
`<artifact_root>` and module boundaries. This relative layout and its
semantics are fixed.

Object, manifest, attestation, registry, and maintenance entries are regular
files. Symlinks, junctions, mount points, alternate data streams, and other
reparse-point traversal are prohibited beneath `<artifact_root>`. No API
accepts a caller-supplied artifact path. Every derived path is resolved and
verified to remain beneath its expected root before access.

SQLite is a rebuildable search/cache/pin index only. It never stores analytical
rows, matrices, model payloads, estimates as authority, or artifact bytes.
Governance Audit Events reference run and bundle identities from their own
append-only store.

## Bundle manifest

The manifest core contains:

| Field | Rule |
| --- | --- |
| `manifest_schema_version` | Exactly `analysis-run-bundle-manifest.v1` |
| `artifact_contract_version` | Exactly `analysis-run-artifacts.v1` |
| `analysis_run_id` | Required opaque execution identity |
| `delivery_attempt_id` | Required for a UI-delivery execution; absent for developer/release-validation execution and excluded from scientific identity |
| `investigation_request_id` | Optional provenance reference |
| `reproduces_run_id`, `retries_run_id` | Optional, mutually independent typed relationships |
| `scientific_request_digest` | Required |
| `runtime_fingerprint_digest` | Required |
| `cache_key` | Required |
| `engine_result_status` | `estimated` or `abstained` for a sealed evidence bundle |
| `started_at`, `completed_at` | UTC instants; audit-only |
| `producer_application_build_id` | Required versioned build |
| `artifact_descriptors` | Complete ordered non-empty list |

`bundle_manifest_hash` accompanies the core in `manifest.json`. Descriptor
order is ascending canonical UTF-8 bytes of `logical_role`, then
`logical_id`, then object digest.

Each `ArtifactDescriptor` contains only:

| Field | Rule |
| --- | --- |
| `descriptor_schema_version` | Exactly `analysis-artifact-descriptor.v1` |
| `logical_role` | Closed role registry below |
| `logical_id` | Stable within the bundle; no path |
| `producer_schema_id`, `producer_schema_version` | Required |
| `media_type` | Closed safe type |
| `sha256` | Exact object-byte digest |
| `scientific_content_digest` | Required when the producer schema defines a canonical logical-content digest |
| `byte_count` | Non-negative integer |
| `record_count` | Required for JSONL; otherwise absent |
| `array_shape`, `array_dtype`, `array_order` | Required only for `.npy` |
| `confidentiality_class` | Closed canonical class inherited from source/derived facts |
| `evidence_refs` | Ordered immutable lineage or derivation references |

No descriptor contains an absolute path, URI, display prose, arbitrary
metadata map, executable type, or mutable alias.

### Required logical roles

Every sealed `estimated` or `abstained` bundle contains:

1. `engine_request` — exact canonical request bytes;
2. `runtime_fingerprint` — the complete closed runtime record;
3. `model_recipe_registry` — model classes, libraries, exact versions,
   hyperparameters, preprocessing, training-row hashes, fold coordinates, and
   seeds, with no fitted object;
4. `derived_seed_registry` — every component coordinate and seed, including
   explicit null coordinates;
5. `cohort_stage_records` — frozen membership, counts, codes, identity hashes,
   and content hashes from required temporal/overlap stages;
6. `estimator_visible_rows` — exact released `S8` inputs and any `S9`
   membership decision;
7. `feature_schema` and `feature_matrix` — ordered names, types, missingness
   encodings, row identities, and exact numeric values;
8. `fold_assignments` — supplier-grouped train/test/calibration membership for
   every repeat and fold;
9. `nuisance_predictions` — every required out-of-fold and subject prediction,
   plus authoritative aggregates;
10. `engine_result` — the complete logical `estimated` or `abstained` result;
11. `diagnostic_artifacts` — every required engine, gate, balance, overlap,
    comparison, and supported-sensitivity result produced for the run;
12. `verification_report` — structural and integrity verification of the
    bundle; and
13. `reproduction_comparison` when `reproduces_run_id` is present.

An `estimated` bundle additionally contains every effect, comparison,
sensitivity, trim, propensity, and optional subject-support payload required by
the engine contract. An `abstained` bundle contains the frozen counts, codes,
scope, stage, and evidence references but no effect-bearing field.

Diagnostics whose scientific semantics belong to the
[validity verdict contract](validity-verdict-evidence-abstention-contract.md)
remain schema-versioned producer artifacts. This contract requires their immutable
presence, identity, provenance, and safe serialization; it does not invent
their thresholds, verdict precedence, or causal wording.

### Failure and quarantine manifests

A lifecycle `failed` run publishes
`runs/<run_id>/failure-manifest.json` last by same-filesystem atomic
replacement under `analysis-run-failure-manifest.v1`. Exactly one of
`manifest.json` and `failure-manifest.json` may exist for a run.

The failure manifest may retain only:

- failure-manifest schema and error-registry versions;
- run identity, UI `delivery_attempt_id` when applicable, and typed
  relationships;
- scientific request and runtime digests, when computed before failure;
- start/completion timestamps;
- one primary and ordered secondary codes from the closed run or engine error
  registry;
- safe detail facts allowed by the engine contract;
- last completed non-effect stage; and
- an opaque `developer_diagnostic_id`.

It contains no estimate, prediction, matrix, row value, confidential identity,
traceback, path, or arbitrary exception text. It is never cache-eligible and is
not an Analysis Artifact Bundle.

A lifecycle `quarantined` run moves its temporary directory beneath
`quarantine/<run_id>/` and publishes `quarantine-manifest.json` last under
`analysis-run-quarantine-manifest.v1`. The quarantine manifest contains only
its schema and error-registry versions, run ID, UI `delivery_attempt_id` when
applicable, quarantine reason code, safe observed counts/digests where allowed,
start/quarantine timestamps,
`developer_diagnostic_id`, and cleanup eligibility.

No success or failure manifest is published for a quarantined run. Quarantined
bytes remain outside `objects/`, are never cache-eligible, and are never opened
by the UI reader. The rebuildable index may expose only lifecycle
`quarantined`, the safe reason code, and the quarantine-manifest identity.

## Safe serialization

Supported physical media are:

- canonical UTF-8 JSON for one structured object;
- canonical UTF-8 JSONL for ordered records; and
- NumPy `.npy` for dense numeric or boolean arrays only.

JSON and JSONL use `canonical-scientific-json.v1`. JSONL applies the canonical
encoding independently to each object, joins records with one LF, and has no
final LF.

`.npy` readers must:

- call `numpy.load(..., allow_pickle=False)`;
- cap the header size at the contract's registered limit;
- reject object, string, structured, datetime, void, or unknown dtypes;
- allow only explicitly registered little-endian numeric and boolean dtypes;
- verify declared dtype, rank, shape, order, byte count, finite-value rules,
  and object hash before exposing values; and
- open the hash-derived object selected by a verified descriptor, never a
  supplied path.

The current official
[NumPy `load` documentation](https://numpy.org/doc/stable/reference/generated/numpy.load.html)
warns that object arrays use pickle and documents `allow_pickle=False` as the
safe default. This contract additionally rejects non-numeric dtypes and
verifies the descriptor before use.

CSV, Parquet, pickle, joblib, `.npz`, executable archives, and database blobs
are unsupported in `v1`. Exact strings, IDs, and nullable field states remain
in canonical JSONL; they are never coerced into object arrays.

## Model and library metadata

Each fitted logical model has a `model_recipe` containing:

- stable model role and coordinate;
- exact fully qualified class name;
- owning distribution and exact version;
- complete explicitly set constructor and fit parameters;
- feature-schema digest and ordered training-row identity hash;
- fold/split references;
- root and derived seed references;
- calibration and aggregation rules;
- thread-policy reference;
- expected input/output shape and dtype;
- prediction artifact references; and
- status or safe failure code.

No omitted field inherits an undocumented library default. Defaults used by
design are materialized into the versioned recipe.

Fitted Python objects are neither reproducibility evidence nor cache payloads.
A fresh reproduction rebuilds them from the retained inputs, recipe, pins,
folds, and seeds. UI reads never import estimator libraries or deserialize
model state.

## Atomic execution and sealing

1. Acquire the single fresh-execution lease.
2. Generate a new run ID.
3. Create `<artifact_root>/temporary/<run_id>` on the same filesystem as
   `objects/` and `runs/`.
4. Write the executing state, any UI `delivery_attempt_id`, and immutable
   request/runtime inputs before model fitting.
5. Keep every analytical object beneath the temporary run. Flush the language
   buffer, call the platform's durable file-flush primitive, and verify each
   staged object's bytes, format, digest, and logical content without
   publishing it globally.
6. Build any required reproduction projection/comparison, the verification
   report, complete artifact descriptors, and manifest core against the staged
   objects. Independently verify the complete candidate.
7. If the candidate must be quarantined, move only its unpublished temporary
   material beneath the quarantine root and publish
   `quarantine-manifest.json`; publish no analytical object.
8. If engine/orchestration failure permits lifecycle `failed`, publish only the
   durably flushed `failure-manifest.json` and delete unpublished analytical
   temporary files. A restart may finish that deletion from the closed failure
   manifest.
9. Only for a fully verified `sealed` candidate, publish each staged object to
   its global hash path by same-filesystem atomic replacement. If the target
   exists, verify and reuse identical bytes; never overwrite conflicting bytes.
10. Write and durably flush `manifest.json` inside the final run directory and
    publish it last by same-filesystem atomic replacement.
11. In one SQLite transaction, add the rebuildable run/cache index entry after
    the applicable terminal manifest is visible.
12. Durably record the terminal Governance Audit Event, release the execution
    lease, and only then return a UI response.

The implementation may use Python `os.replace` only within one filesystem.
The current official
[CPython `os.replace` documentation](https://docs.python.org/3.12/library/os.html#os.replace)
documents successful same-filesystem replacement as atomic and replacement
semantics are available on Windows; cross-filesystem movement is prohibited.
Before replacement, the implementation calls
[CPython `os.fsync`](https://docs.python.org/3.12/library/os.html#os.fsync) on
the flushed file handle; CPython documents this as forcing file data to disk
and using `_commit` on Windows.

Core's guaranteed crash model covers process termination, forced application
shutdown, and restart while the OS and filesystem remain operational. Atomic
replacement prevents a partially named terminal manifest from becoming
visible. Core does not claim survival of sudden power loss, kernel failure,
storage-controller data loss, or damaged media; validated bundled references
remain recoverable from the prepared release package.

If publication or index update fails, startup reconciliation trusts verified
terminal manifests, not the index, and never exposes temporary files. A process
crash after one or more fully verified objects are globally published but
before `manifest.json` exists may leave unreferenced immutable objects. They are
unreachable from the UI and cache, are classified as `orphan_verified`, and
may be deleted only by the recoverable maintenance cleanup protocol. Unverified
or reproduction-violating bytes never enter `objects/`.

## Cache and reuse

### Eligibility

Only an `available`, `sealed`, `machine_verified` run with scientific outcome
`estimated` or `abstained` is cache-eligible. Failed, quarantined, suppressed,
invalid, unsupported-schema, or partially verified runs are excluded.

The cache maps one exact cache key to one or more eligible immutable run IDs.
Selection is deterministic:

1. current-release Validated Reference, if one exactly matches the key;
2. otherwise the earliest successfully sealed machine-verified run by
   `completed_at`, breaking impossible timestamp ties by run ID.

This ordering prevents a later divergent or merely newer artifact from
silently replacing a known eligible run.

### Reuse

An ordinary load may reuse the selected run, after re-verifying the manifest,
object hashes, supported schemas, and current release designation. It records
`existing_run_reuse` in the successful terminal Audit Event. It does not create
a new Analysis Run or claim fresh computation.

**Run fresh** ignores the cache selection, creates a new ID, starts a new
process, and records `fresh_execution` only in a successful terminal Audit
Event after execution actually occurred.

### Invalidation

Cache invalidation is identity-based, never mutation-based:

- changed request/configuration/data/seed -> different scientific digest;
- changed application/runtime/library/backend/thread policy -> different
  runtime digest;
- changed output/bundle/artifact schema -> different cache key;
- failed post-seal re-verification -> run and every bundle sharing the affected
  object are marked `suppressed` in the rebuildable index and an integrity
  Audit Event is appended; immutable lifecycle and files do not change;
- removed unpinned run -> entry disappears during reconciliation; and
- changed release registry -> reference selection changes but the underlying
  run and cache key do not.

There is no TTL, manual "mark stale" bit, silent in-place regeneration, or
cache-key exception.

## Fresh reproduction

A target and candidate are compared only through
`analysis-run-reproduction-projection.v1`. The projection is run-neutral and
cannot contain:

- run, retry, reproduction, Investigation Request, delivery-attempt, audit, or
  actor identities;
- start, completion, request, validation, or delivery timestamps;
- manifest, descriptor-byte, object-byte, bundle, attestation, registry, or
  physical-path identities;
- `verification_report`, `reproduction_comparison`, failure, quarantine,
  cleanup, or developer-log artifacts; or
- validation designation and UI badge.

The projection requires the same scientific-role set after excluding those
administrative roles. It compares exactly:

- canonical engine-request and runtime-fingerprint content;
- model recipes, seed coordinates and values;
- ordered row identities, stage membership, codes, counts, and scientific
  content hashes;
- feature names, types, order, missingness encodings, and matrix values;
- fold, split, calibration, trim, and support membership;
- statuses, units, estimand metadata, evidence references, and every
  non-numeric scientific field.

Fitted numeric predictions, propensities, estimates, standard errors,
intervals, test statistics, p-values, and numeric Diagnostic Result measures
are compared elementwise using only the engine contract's registered replay
tolerances. Producer schemas may classify a numeric field as exact only when
the engine contract already requires exact equality; they cannot loosen a
tolerance or exempt a required field.

Both projection objects and their per-role canonical digests are retained in
the reproduction comparison. Run-specific differences therefore cannot cause
a false violation, while every scientific difference remains covered.

A fresh reproduction must:

- set `reproduces_run_id`;
- load the target's exact verified engine request and runtime contract;
- require the same scientific request and runtime-fingerprint digests;
- reuse the same root seed and derive every component seed again;
- execute in a new process with network disabled;
- create a new run ID and timestamps;
- build and compare both run-neutral reproduction projections; and
- emit `analysis-run-reproduction-comparison.v1`.

The reproduction comparison lists each registered comparison class, expected
and observed digests or numeric summary, tolerance where applicable, and
pass/fail. It includes no free-form waiver.

Any exact mismatch or out-of-tolerance value emits
`RUN_REPRODUCIBILITY_VIOLATION`. The new run is invalid and quarantined, only a
safe quarantine manifest is published, and no divergent estimate reaches the
UI. The target Validated Reference or prior machine-verified run remains
unchanged.

A different root seed is a different scientific request and is not a
reproduction of the target.

## Machine verification

Before sealing, verification checks:

1. manifest, descriptor, and producer schemas are supported exactly;
2. every required logical role exists once unless its schema declares a fixed
   cardinality;
3. no unexpected role or file exists;
4. every object is regular, path-safe, byte-count exact, and hash-valid;
5. JSON/JSONL canonical bytes and record order are exact;
6. every `.npy` descriptor, header, dtype, shape, finite-value rule, and byte
   count matches;
7. request, runtime, cache, cohort, feature, fold, seed, prediction, model, and
   result cross-references reconcile;
8. engine branch rules prohibit partial estimates on abstention or failure;
9. raw source, ground-truth, prohibited model object, traceback, secret, path,
   and executable-content checks pass;
10. timestamps are valid UTC audit clocks and absent from scientific hashes;
11. a reproduction comparison is present and successful when required; and
12. the read-model projector can construct the complete safe DTO without
    reading any unregistered object.

The verification report records a closed check ID, policy version, status, and
safe expected/observed facts for every check. All must pass for
`machine_verified`.

## Validation Attestation and reference promotion

Only a developer-operated release-validation command outside the product UI may
promote a bundle. It accepts a run ID, a reference-slot ID, and a release ID;
it never accepts a filesystem path. The application must be stopped, and the
command must hold the exclusive maintenance lease through attestation and
registry publication.

Promotion requires:

1. successful machine verification from a clean process;
2. exact supported runtime pins and lock hashes;
3. the complete causal-engine conformance fixture pack;
4. two fresh-process reproductions with the same root seed, satisfying exact
   and tolerant replay rules;
5. the engine's different-seed fixture behavior without claiming numeric
   equality;
6. UI read-model construction and schema validation for estimated, abstained,
   and safe-error paths;
7. network-disabled execution;
8. confidentiality, raw-source, secret, and evaluation-ground-truth exclusion
   scans;
9. absence of pickle, joblib, object arrays, executable content, unsafe paths,
   symlinks, junctions, and reparse traversal;
10. declared demo-laptop runtime evidence; and
11. successful hostile review of the release evidence.

The attestation contains:

- schema and policy versions;
- opaque attestation ID;
- run ID and bundle manifest hash;
- scientific request and runtime digests;
- release and reference-slot IDs;
- every validation check ID and immutable evidence digest;
- validation-tool build and lock hashes;
- UTC validation timestamp; and
- developer actor identity from the local release process.

It contains no signature in Core. Hashes and the release allow-list are
corruption/mismatch controls, not malicious-tamper proof.

After an attestation is written, the release command writes a new immutable
`validated-references.json` for the release. The registry contains one active
entry per `reference_slot_id`, each binding the slot, run, bundle, attestation,
supported read-model version, and intended dataset/case role. An existing
registry is never edited; a new release ID supersedes it.

The product UI has no promote, validate, relabel, or registry-write capability.

## UI-safe read boundary

The browser requests a run by opaque ID or a versioned reference slot. It never
receives a filesystem path, SQLite query surface, object-store key, raw
manifest, matrix, row-level cohort, nuisance prediction vector, traceback, or
model recipe.

The backend:

1. resolves the ID from the controlled index/registry;
2. resolves and verifies every path beneath `<artifact_root>`;
3. verifies the manifest and required objects;
4. derives validation state from the current release registry;
5. projects only `analysis-run-read-model.v1`; and
6. records the terminal Governance Audit Event.

The read model may contain:

- run ID and typed relationship IDs;
- delivery mode;
- `machine_verified` or `reference_validated`;
- exact UI badge: **Fresh local run**, **Existing run reused**, or
  **Validated reference**;
- scientific outcome and its allowed effect/abstention fields;
- Causal Question, Dataset Version, intended role, target milestone, frozen
  observation cutoff, configuration, seed-policy, and runtime version labels;
- started/completed timestamps and provenance/evidence references;
- aggregate cohort, overlap, model, effect, comparison, sensitivity, and
  diagnostic facts already allowed by their producer schemas;
- safe validation/check summaries; and
- closed error code plus safe detail facts when evidence is unavailable.

The UI must display validation/delivery separately from outcome. In particular:

- **Fresh local run** does not mean reference-validated;
- **Existing run reused** does not mean stale or invalid;
- **Validated reference** says nothing about whether the current interaction
  executed code; and
- `abstained` remains a scientific outcome, not an artifact error.

Unsupported, unsealed, suppressed, corrupt, quarantined, or path-invalid
material fails closed before any estimate is projected.

## Concurrency, interruption, and recovery

While the application is running, it holds a shared OS-backed maintenance lease
at `leases/maintenance.lock`. Developer validation, registry publication, and
cleanup require the application to be stopped and hold the exclusive
maintenance lease. No Core process may write Audit Events, Manager Decisions,
manifests, attestations, registries, indexes, or pin references while another
process holds that exclusive lease.

After acquiring the shared lease, application startup refuses with
`RUN_MAINTENANCE_RECOVERY_REQUIRED` if any cleanup intent lacks a terminal
result. The developer must resume that cleanup under the exclusive lease before
the application can create new pins or Audit Events.

Within the application's shared maintenance lease, fresh execution uses one
OS-backed exclusive lease at `leases/fresh-execution.lock`. Reads do not
require the fresh-execution lease. A second fresh request receives
`RUN_EXECUTION_BUSY`; it is neither queued nor converted into a cache reuse.

On startup, after acquiring the lease:

- reconcile verified success, failure, and quarantine manifests into the
  SQLite index;
- remove index entries whose manifests are absent or invalid;
- propagate `suppressed` to every run sharing a failed object verification;
- classify globally published zero-reference objects as `orphan_verified`;
- delete non-authoritative temporary remnants whose matching verified success
  or failure terminal manifest already exists;
- treat only an abandoned temporary run with no terminal manifest as
  interrupted, move its material to `quarantine/<run_id>` without opening it
  as evidence, and write a quarantine manifest;
- reconcile each unterminated delivery attempt from its requested Audit Event
  plus matching `delivery_attempt_id` in a terminal manifest: success-manifest
  attempts become `RUN_DELIVERY_INTERRUPTED`, failure/quarantine attempts use
  their terminal safe code, no-manifest fresh attempts with a matching
  temporary executing-state record become `RUN_EXECUTION_INTERRUPTED`, and
  no-state fresh or reuse attempts become `RUN_DELIVERY_INTERRUPTED`; and
- permit a new retry with a new run ID.

Interrupted executions are non-resumable because library state, RNG state, and
partially written model outputs cannot be proven equivalent. An expired lease
never authorizes publication of partial files.

## Retention and cleanup

The pin set is the transitive union of:

- every run and object referenced by the current or retained validated-
  reference registries;
- every run and bundle referenced by an Audit Event;
- every run and bundle referenced by a Manager Decision;
- every run needed as the target of a retained reproduction or validation
  attestation; and
- every object shared with a pinned bundle.

Core performs no age-, size-, startup-, or quota-based automatic deletion.

An explicit developer cleanup command:

1. requires the application to be stopped, acquires the exclusive maintenance
   lease, then acquires the fresh-execution lease in that order;
2. resumes any prior intent lacking `result.json` before proposing another
   operation;
3. rebuilds the index and pin graph from authoritative manifests,
   attestations, registries, and governance references;
4. lists candidate unpinned terminal runs and `orphan_verified` objects;
5. requires an explicit confirmation containing their run IDs and every
   object's confidentiality-class/digest pair;
6. rebuilds and rechecks the pin graph while still holding both leases and
   refuses any run whose pin state changed;
7. writes and durably atomically publishes immutable `intent.json` under
   `analysis-artifact-cleanup-intent.v1`, containing operation ID, exact
   run/manifest targets, exact confidentiality-class/object-digest targets,
   expected byte counts, pin-graph digest, reason, tool version, actor, and UTC
   timestamp;
8. idempotently deletes only the intent's run manifests and then objects whose
   reference count is zero;
9. never touches active temporary, lease, registry, attestation, audit, or
   developer-log paths; and
10. durably atomically publishes immutable `result.json` under
    `analysis-artifact-cleanup-result.v1`, recording each target as
    `deleted`, `already_absent_after_recovery`, or `retained`, with actual byte
    counts and a terminal UTC timestamp, before releasing the leases.

Deleting an unpinned run removes its future availability; the cleanup result
does not preserve its evidence. Pinned evidence is not deletable through this
Core command.

If the process stops after intent publication, application startup refuses to
run and the next cleanup invocation resumes the exact operation. It rechecks
pins before deleting any still-present target, treats an already absent target
as deleted before recovery, completes remaining safe deletions, and publishes
the result. The immutable intent plus terminal result therefore records every
target even when the deleting process terminates between filesystem changes.

## Developer diagnostics and confidentiality

Developer tracebacks and operational logs live only under `developer-logs/`.
They are outside bundle identity, cache identity, validation evidence, UI
responses, and scientific reproducibility.

Logs may contain safe codes, stages, library exceptions, and local diagnostic
context needed to debug the implementation. They must never contain raw source
rows, full canonical records, subject/supplier/project names, payloads,
credentials, tokens, environment dumps, evaluation ground truth, or secrets.
A failure manifest references them only by opaque `developer_diagnostic_id`.

Bundle confidentiality classifications propagate from the most restrictive
input represented by each derived artifact. The confidentiality class is a
validated path component above the SHA-256 namespace, so content-addressed
deduplication occurs only when both bytes and confidentiality class match. The
artifact root remains local and is never served as a static directory.

## Run error registry

| Code | Meaning |
| --- | --- |
| `RUN_MAINTENANCE_BUSY` | Application or another maintenance writer prevents exclusive validation/promotion/cleanup |
| `RUN_MAINTENANCE_RECOVERY_REQUIRED` | An immutable cleanup intent lacks a terminal result and must be resumed before app startup |
| `RUN_EXECUTION_BUSY` | Another fresh execution owns the exclusive lease |
| `RUN_DELIVERY_INTERRUPTED` | An accepted load/fresh attempt has no terminal Audit Event although execution may have completed |
| `RUN_REQUEST_INTEGRITY_MISMATCH` | Canonical request bytes and declared scientific digest disagree |
| `RUN_RUNTIME_INCOMPATIBLE` | Runtime fingerprint differs from the required engine configuration |
| `RUN_ARTIFACT_SCHEMA_UNSUPPORTED` | Manifest, descriptor, producer, attestation, registry, or read-model schema is unsupported |
| `RUN_ARTIFACT_ROLE_MISSING` | A required logical role is absent or has invalid cardinality |
| `RUN_ARTIFACT_PATH_INVALID` | A path escapes its root or uses a prohibited link/reparse mechanism |
| `RUN_ARTIFACT_FORMAT_UNSAFE` | Media type, dtype, header, executable content, or deserialization mode is prohibited |
| `RUN_ARTIFACT_INTEGRITY_MISMATCH` | Bytes, byte count, record count, shape, cross-reference, or SHA-256 identity disagree |
| `RUN_ARTIFACT_UNSEALED` | No valid atomically published manifest exists |
| `RUN_EXECUTION_INTERRUPTED` | The execution ended without a seal and cannot resume |
| `RUN_REPRODUCIBILITY_VIOLATION` | Exact or tolerance-governed reproduction comparison failed |
| `RUN_VALIDATION_FAILED` | One or more required reference-promotion checks failed |
| `RUN_REFERENCE_INVALID` | Registry, attestation, bundle, slot, or release binding is inconsistent |
| `RUN_RETENTION_PINNED` | Cleanup targeted a pinned run or object |
| `RUN_INTERNAL_ERROR` | Unexpected orchestration defect with no narrower code |

Precedence follows maintenance/execution availability, request integrity,
runtime, schema, role, path, format, object integrity, sealing, interruption,
reproducibility, validation/reference, retention, then internal error. Engine
error precedence remains internal to the engine and is never remapped to a run
error unless this physical boundary independently fails.

Safe run-detail facts are limited to registered schema/role/check enums,
non-negative expected and observed counts/shapes, expected and observed version
strings, lifecycle/verification enums, and repeat/fold coordinates. Paths,
hashes in user-facing errors, IDs of business entities, raw values, exception
text, and free-form messages are prohibited.

## Conformance scenarios

1. **Identical ordinary load:** two loads of one eligible sealed bundle return
   the same run ID and record two successful Governance Audit Events with
   `existing_run_reuse`.
2. **Exact fresh reproduction:** **Run fresh** creates a new run ID, retains the
   same scientific and runtime digests, reproduces within contract rules, and
   records a successful Governance Audit Event with `fresh_execution`.
3. **Business refresh is distinct:** a later observation cutoff creates a new
   Investigation Request, scientific digest, cache key, and Analysis Run; it
   does not set `reproduces_run_id`.
4. **Timestamp neutrality:** changing only execution timestamps changes the
   bundle hash and run ID but not the scientific digest, seeds, or cache key.
5. **Audit-field neutrality:** changing only request/audit actor metadata
   excluded by the ingress projection preserves the scientific digest.
6. **Seed sensitivity:** changing the root seed changes the scientific digest
   and cache key and is not an exact reproduction.
7. **Runtime sensitivity:** changing one loaded dependency or numerical backend
   changes the runtime digest and cache key before fitting.
8. **Cache reuse:** a cache hit creates no new run directory or manifest.
9. **Cache bypass:** **Run fresh** executes even when a Validated Reference
   exactly matches the key.
10. **Abstention:** a complete abstained bundle is sealed, verifiable,
    cache-eligible, and contains no effect field.
11. **Engine failure:** a required model failure seals only the safe failure
    manifest at its closed path/schema and is not cache-eligible.
12. **Execution crash:** process termination after the temporary executing
    state but before terminal-manifest publication quarantines temporary
    material on restart, records `RUN_EXECUTION_INTERRUPTED`, and retry uses a
    new run ID.
13. **Post-seal delivery crash:** process termination after a success manifest
    but before a terminal Audit Event preserves the sealed available run and
    records `RUN_DELIVERY_INTERRUPTED`, not execution failure.
14. **Reuse delivery crash:** an unterminated reuse attempt records
    `RUN_DELIVERY_INTERRUPTED` and does not change the existing run.
15. **Index loss:** deleting the rebuildable SQLite index does not lose
    evidence; verified manifests rebuild it.
16. **Index lie:** an index row pointing to a missing or invalid manifest is
    removed and exposes no data.
17. **Partial publication:** verified objects exist but `manifest.json` does
    not; the run is unsealed and invisible, and zero-reference objects are
    `orphan_verified`.
18. **Unsafe model object:** a pickle/joblib/object-array artifact is rejected
    before deserialization.
19. **Path traversal:** a descriptor, symlink, junction, reparse point, or
    supplied path cannot escape the artifact root.
20. **Hash collision defense:** an existing object at the digest path with
    different bytes quarantines the new run and preserves the old file.
21. **Post-seal corruption:** failed re-verification preserves immutable
    lifecycle, suppresses every bundle sharing the object, removes them from
    cache/UI selection, and appends one integrity Audit Event per run.
22. **Reproduction projection:** different run IDs, timestamps, verification
    reports, comparison artifacts, and physical hashes are excluded, while one
    changed scientific field is detected.
23. **Reproduction mismatch:** one out-of-tolerance estimate publishes only a
    quarantine manifest and never replaces the target evidence.
24. **Promotion:** successful validation adds an external attestation and new
    registry version without changing any bundle byte.
25. **Failed promotion:** one failed confidentiality or fixture check issues no
    attestation and no registry entry.
26. **Old schema:** a supported read-only adapter may project it without
    rewriting; an unsupported version fails closed and requires a new run.
27. **Pinned cleanup:** a run referenced by an Audit Event, Manager Decision,
    attestation, or reference registry cannot be deleted.
28. **Maintenance exclusion:** cleanup/promotion cannot start while the
    application runs; while the exclusive lease is held, no new pin or Audit
    Event can race the pin graph.
29. **Unpinned cleanup:** confirmed cleanup publishes immutable intent, removes
    one unpinned manifest and only now-unreferenced objects, then publishes its
    immutable result.
30. **Cleanup crash recovery:** termination after intent or partial deletion
    blocks application startup; resume records already-absent targets,
    completes safe deletions, and publishes the terminal result.
31. **Orphan cleanup:** an explicitly confirmed
    confidentiality-class/object-digest `orphan_verified` identity with zero
    references is covered by cleanup intent/result and can be removed without
    touching equal bytes in another class.
32. **No UI filesystem access:** every browser-visible field can be produced
    from the closed read model; raw artifact/static-file access is absent.

## Acceptance checklist

This decision is implementation-ready only when:

1. all closed IDs, schemas, logical roles, and error codes are represented as
   closed types;
2. the run ID is execution-unique and excluded from scientific identity;
3. complete engine requests and runtime fingerprints hash canonically;
4. every seed, fold, feature, model recipe, input, output, prediction, and
   required diagnostic is retained or hash-bound;
5. no fitted model object, raw source, secret, or evaluation ground truth can
   enter a bundle;
6. exact safe media types and `.npy` dtype/header rules are enforced before
   value access;
7. durable file flush plus manifest-last same-filesystem publication is
   process-crash-tested on Windows without claiming power-loss durability;
8. analytical objects remain staged through full candidate verification, and
   interrupted publication can create only unreachable `orphan_verified`
   objects;
9. SQLite loss/corruption cannot become loss/corruption of authoritative
   evidence;
10. cache hits reuse existing runs and fresh requests bypass cache;
11. every cache-affecting change produces a different key;
12. lifecycle, availability, outcome, verification, and delivery mode remain
    orthogonal;
13. post-seal corruption suppresses every affected shared-object consumer
    without changing terminal lifecycle or files;
14. abstention is safely consumable while failure and quarantine expose no
   estimate;
15. exact technical reproduction is distinct from an investigation refresh;
16. the run-neutral reproduction projection excludes every administrative
   difference and covers every scientific field;
17. reproduction mismatch fails closed, publishes only a quarantine manifest,
   and preserves prior evidence;
18. failure and quarantine manifests have closed, mutually exclusive schemas
   and paths;
19. validation requires the complete fixture, replay, UI, offline,
   confidentiality, and hostile-review gates;
20. attestation and release promotion never mutate a bundle;
21. UI access is backend-mediated, versioned, allow-listed, and path-safe;
22. requested/succeeded/failed run delivery uses Governance-owned Audit Events,
    terminal manifests carry the correlation ID, and startup distinguishes
    execution interruption from delivery interruption;
23. the maintenance and single-execution leases plus non-resumable crash
    recovery are tested;
24. pin-graph cleanup under exclusive maintenance refuses
    audit/decision/reference evidence;
25. cleanup publishes recoverable immutable intent before deletion and terminal
    result afterward;
26. all 32 conformance scenarios pass; and
27. the full fresh run is benchmarked on the demo laptop before the UI promises
   a duration.

## Explicitly deferred and out of scope

- Absolute application-data root, Python module names, API route paths, and
  SQLite table DDL belong to the later architecture/storage decision.
- Evidence Verdict, refuter, negative-control, hidden-confounding, robustness,
  and diagnostic scientific semantics belong to the
  [validity verdict contract](validity-verdict-evidence-abstention-contract.md);
  this contract stores their versioned artifacts without duplicating those
  semantics.
- UI component layout, click paths beyond the semantic distinction between
  load and **Run fresh**, progress presentation, and detailed error copy belong
  to the manager-journey/UI decision.
- Artifact signing, adversarial local tamper resistance, application-managed
  encryption at rest, cloud/object storage, remote execution, multi-user
  access, network distribution, and server synchronization are outside Core.
- Automatic quota eviction, TTL expiry, resumable fitting, concurrent fresh
  execution, fitted-model serving, online learning, and cross-runtime cache
  reuse are outside Core.
