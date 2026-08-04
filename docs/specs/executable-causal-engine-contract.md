# Executable Causal-Engine Contract

## Status and authority

This specification resolves the executable estimation decisions for the Core
supplier-congestion Causal Question. It defines the logical input boundary,
estimator configurations, cross-fitting and seed policy, overlap integration,
comparison estimators, logical outputs, execution errors, and engine
conformance fixtures.

It is subordinate to:

- `docs/causal_delay_copilot_stage2_strategy.md` for product and scientific
  intent;
- `docs/specs/canonical-order-event-lineage-contract.md` for canonical source
  facts, clocks, missingness, identity, and provenance; and
- `docs/specs/exposure-outcome-temporal-eligibility-contract.md` for exposure,
  outcome, covariate eligibility, cohort construction, overlap thresholds,
  subject support, and scientific abstention.

If these sources disagree, the Stage 2 strategy controls intent, the canonical
lineage contract controls what may be treated as a source fact, and the
temporal-eligibility contract controls which derived facts and cohort rows may
reach estimation.

### `S8` to `S9` ownership

The temporal-eligibility contract defines the complete gate order, the
authoritative propensity semantics, the inclusive overlap rule, and the
conditions under which `S9_OVERLAP(m)` may be released to an estimator. Its
phrase "release `S9_OVERLAP(m)` as estimator input" names the boundary into the
effect estimator, not a second public engine request.

The public engine suite request therefore begins with frozen, validated
`S8_OUTCOME(m)` bundles and their upstream stage evidence. This engine performs
the contractually required cross-fitted propensity calculation, forms
`S9_OVERLAP(m)`, records the new stage evidence, and only then passes `S9` to
DoubleML and the comparison estimators. No upstream layer and engine layer may
each fit a propensity model or each trim the cohort.

This specification does not define:

- physical Analysis Run serialization, cache keys, file layout, retention, or
  invalidation, which belong to
  [Define the analysis-run and reproducibility artifact contract](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/7);
- Diagnostic Result thresholds, refuters, sensitivity grades, Evidence
  Verdicts, or user-facing abstention precedence, which belong to
  [Validity Verdict, Robustness Grade, and Abstention Contract](validity-verdict-evidence-abstention-contract.md);
- reactive or proactive trigger transport schemas, which belong to
  [Define the risk-signal adapter, pre-award hook, and predictive baseline contract](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/15);
- the five-scenario scientific acceptance harness, which belongs to
  [Define evaluation-harness acceptance gates and policy comparisons](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/13); or
- any product implementation.

### Scope resolution for heterogeneous effects

The Stage 2 strategy discusses `CausalForestDML` in its scientific-method and
architecture narrative, but its final scope map classifies gated subgroup/CATE
surfacing as Stretch. The Wayfinder destination is Core-only and explicitly
excludes Stretch. This contract therefore resolves the ambiguity in favour of
the final scope boundary: Core neither fits nor displays `CausalForestDML`.
Reintroducing it requires a fresh planning effort or an explicit redraw of the
Wayfinder destination.

## Core invariants

1. The engine executes one versioned Causal Question; it does not discover or
   rewrite the question after inspecting an effect.
2. The engine accepts only a validated, lineage-bearing input bundle. It has no
   public arbitrary-DataFrame or arbitrary-feature entry point.
3. `S8_OUTCOME(m)` is the last pre-overlap cohort. The engine fits the
   authoritative propensity ensemble on that set, applies the frozen inclusive
   `[0.10, 0.90]` rule, and alone forms `S9_OVERLAP(m)`.
4. There is one authoritative propensity ensemble for historical overlap,
   subject overlap, and DoubleML scoring. DoubleML does not fit a second
   propensity model.
5. Primary and contextual estimates use the same `S9_OVERLAP`, folds, feature
   schema, and cross-fitted nuisance predictions.
6. Supplier identity is a grouping and inference variable, not a primary
   nuisance feature. Only pre-registered, pre-treatment supplier traits and
   history features may enter the primary adjustment set.
7. The primary estimand is continuous-slippage ATTE. A trimmed-cohort ATE is
   context, not a replacement headline.
8. `CausalForestDML`, subgroup effects, and individualized effects are outside
   Core. The engine never emits a CATE.
9. A scientific gate failure emits no effect estimate. A required engine
   component failure emits no consumable partial result.
10. Identical logical inputs and runtime pins reproduce the same identities,
    feature layout, folds, seeds, and status. Numeric replay is checked at
    declared tolerances; no contract promises cross-platform bitwise equality
    for floating-point estimates.
11. The engine produces measurements and estimates, not an Evidence Verdict,
    recommendation, or causal prose.
12. No learner, threshold, feature, fold, sensitivity, or comparison is
    selected because it yields a preferred effect.

## Core Causal Question

### Logical definition

The Core Causal Question fixes:

| Element | Core value |
| --- | --- |
| Eligible population | Order Lines released as `S8_OUTCOME(m)` by the temporal-eligibility contract for one dataset version and variant |
| Primary exposure | Binary High-Load Exposure for the primary 0.67 expanding-history rule with minimum history 10 |
| Primary outcome | Continuous Supplier Milestone Slippage in days |
| Primary estimand | Average treatment effect among exposed Order Lines (ATTE) |
| Context estimand | Average treatment effect (ATE) on the same overlap-trimmed primary cohort |
| Cluster | `supplier_id`, one-way |
| Adjustment set | The dataset's frozen, versioned pre-treatment adjustment set |
| Design restrictions | The exact temporal, first-exposure, source-role, maturity, missingness, support, and overlap rules in the temporal-eligibility contract |

The engine configuration references this definition by a versioned
`causal_question_id`; it does not reconstruct scientific meaning from field
names.

### Core estimand suite

The complete Core suite is:

| ID | Exposure | Outcome | Estimator and score | Cohort |
| --- | --- | --- | --- | --- |
| `primary_atte_slippage` | Primary binary High-Load Exposure | Continuous slippage days | `DoubleMLIRM`, `score="ATTE"` | Primary `S9_OVERLAP(10)` |
| `context_ate_slippage` | Primary binary High-Load Exposure | Continuous slippage days | `DoubleMLIRM`, `score="ATE"` | Identical primary `S9_OVERLAP(10)` |
| `sensitivity_stricter_atte_slippage` | 0.75 threshold, minimum history 10 | Continuous slippage days | `DoubleMLIRM`, `score="ATTE"` | That variant's `S9_OVERLAP(10)` |
| `sensitivity_short_history_atte_slippage` | 0.67 threshold, minimum history 5 | Continuous slippage days | `DoubleMLIRM`, `score="ATTE"` | That variant's `S9_OVERLAP(5)` |
| `sensitivity_long_history_atte_slippage` | 0.67 threshold, minimum history 20 | Continuous slippage days | `DoubleMLIRM`, `score="ATTE"` | That variant's `S9_OVERLAP(20)` |
| `sensitivity_late_risk_atte` | Primary binary High-Load Exposure | Binary `supplier_milestone_late` | `DoubleMLIRM`, `score="ATTE"` | Primary `S9_OVERLAP(10)` |
| `sensitivity_continuous_load_slope` | Continuous `load_percentile` | Continuous slippage days | `DoubleMLPLR`, `score="partialling out"` | Primary `S9_OVERLAP(10)` |

The binary late-outcome estimate is a risk difference. The continuous-load
coefficient is a linear average slope over `[0, 1]`; the output reports
`0.10 * coefficient` as days per 0.10 increase in load percentile. It is not a
nonlinear dose-response curve or individualized effect.

Only the primary binary exposure receives an ATE context estimate. Replicating
ATE context across every sensitivity is outside Core.

### Closed identifier and version registry

This contract freezes:

| Logical artifact | ID or version |
| --- | --- |
| Engine input schema | `causal-engine-suite-request.v2` |
| Engine output schema | `causal-engine-suite-result.v2` |
| Causal Question | ID `supplier-congestion-to-milestone-slippage`, version `v1` |
| Engine configuration | ID `core-local-cpu-hgb-doubleml`, version `v1` |
| Estimand suite | ID `core-supplier-congestion-suite`, version `v1` |
| Propensity specification | ID `supplier-grouped-calibrated-hgb-5x2`, version `v1` |
| Seed policy | ID `sha256-coordinate-seeds`, version `v1` |
| Engine error registry | `causal-engine-errors.v1` |
| Conformance fixture pack | ID `core-causal-engine-conformance`, version `v2` |

An ID or version not listed here is unsupported by this contract. Changing any
scientific meaning, field semantics, learner setting, split, seed coordinate,
threshold, aggregation, or required result increments the owning version.

### Canonical scientific encoding

Every content hash, seed payload, fixture object, and numerical matrix digest
uses `canonical-scientific-json.v1`:

1. reject NaN and positive or negative infinity;
2. normalize every string, including keys, to Unicode NFC;
3. encode every finite logical float as the string
   `f64:<CPython-float.hex()>`, lower-case, with both `-0.0` and `0.0`
   normalized to `f64:0x0.0p+0`;
4. retain integers as JSON integers and booleans/null as JSON booleans/null;
5. preserve declared array order and sort set-like reference arrays by their
   canonical UTF-8 bytes;
6. serialize with pinned CPython `3.12.13`
   `json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
   separators=(",", ":"))`; and
7. encode the result as UTF-8 without a BOM or trailing newline.

Floats are transformed before `json.dumps`, so no JSON implementation chooses
decimal or exponent spellings. Hashing a matrix means encoding an object with
its ordered column names, shape, and row-major values under this rule. Hashing
JSONL means applying the rule independently to each object and joining objects
with one LF, with no final LF. No other canonicalization scheme is permitted
under `v1`.

## Logical input boundary

### `CausalEngineSuiteRequest`

One logical request executes the complete Core suite. Common scientific and
runtime configuration appears once; cohort identities remain variant-specific.
The request contains:

| Field | Type | Rule |
| --- | --- | --- |
| `engine_input_schema_version` | versioned string | Required and supported exactly |
| `engine_output_schema_version` | versioned string | Declares the only result schema the caller accepts |
| `error_registry_version` | versioned string | Must be `causal-engine-errors.v1` |
| `causal_question_id`, `causal_question_version` | ID and version | Required; must resolve to the Core question above |
| `engine_config_id`, `engine_config_version` | ID and version | Required; immutable estimator configuration |
| `dataset_version_id` | immutable ID | Required; identical on every row and evidence reference |
| `intended_role` | canonical enum | Required; must already be eligible under the temporal-eligibility contract |
| `target_milestone_kind` | canonical enum | Fixed for the request |
| `canonical_slippage_duration_basis` | canonical enum | Exactly `CALENDAR_DAY` or `ELAPSED_86400_SECOND_DAY`; fixed for the request and every released row |
| `trigger_mode` | canonical enum | `historical`, `reactive`, or `proactive` |
| `observation_cutoff` | canonical temporal value | Frozen upstream |
| `suite_id`, `suite_version` | ID and version | Must resolve to the complete Core estimand suite |
| `variant_inputs` | four `VariantCohortInput` entries | Exactly primary, stricter threshold, short history, and long history; no duplicates or extras |
| `adjustment_set` | `AdjustmentSetSpec` | Required and versioned |
| `propensity_spec` | `PropensitySpec` | Must equal the engine configuration in this contract |
| `root_seed` | unsigned 64-bit integer | Required; no hidden default |
| `subject` | optional `SubjectInput` | Separate from every variant's `rows`; absent means no subject requested |
| `evidence_refs` | non-empty reference set | Points to upstream validation and derivation evidence |

The four entries are ordered by this fixed sequence:

```text
primary
stricter_threshold
short_history
long_history
```

### `VariantCohortInput`

Each entry contains:

| Field | Type | Rule |
| --- | --- | --- |
| `variant_id` | closed enum | Exactly one fixed suite member |
| `threshold_rule_ref` | versioned reference | Must match the variant |
| `selector_refs` | versioned selectors, bounds, hashes | Required for estimator and history windows |
| `cohort_stage_summaries` | immutable set/count summaries | Required from `H0` through the last completed stage; never recomputed later |
| `upstream_status` | `released` or `scientifically_unavailable` | Discriminates rows from an upstream sensitivity failure |
| `s8_identity_hash` | optional `sha256:` digest | Required only when `released` |
| `s8_content_hash` | optional `sha256:` digest | Required only when `released`; binds complete scientific row content and evidence |
| `rows` | optional ordered `EstimatorRow` list | Exactly `S8_OUTCOME(m)` when `released`; absent otherwise |
| `scientific_code`, `gate_stage` | optional registered code and stage | Required only when scientifically unavailable |
| `evidence_refs` | non-empty reference set | Variant-specific derivation and gate evidence |

A scientifically unavailable primary bundle makes the suite `abstained`. A
scientifically unavailable binary sensitivity becomes `unsupported` only
under the closed mapping below and only if the primary bundle remains
eligible. The engine never fabricates an empty `S8` to represent either state.

### Closed scientific-state mapping

`scientifically_unavailable` is accepted only with a code registered by the
temporal-eligibility contract and evidence for its declared gate:

```text
SOURCE_SEMANTICS_INELIGIBLE
EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT
CORE_TEMPORAL_COVERAGE_INSUFFICIENT
OUTCOME_COVERAGE_INSUFFICIENT
CANCELLATION_COMPETING_EVENT_PRESENT
COVARIATE_COVERAGE_INSUFFICIENT
COHORT_SUPPORT_INSUFFICIENT
OUTCOME_DEGENERATE
```

`SLIPPAGE_DURATION_BASIS_MIXED` is a run-scoped upstream abstention that
prevents construction of a `CausalEngineSuiteRequest`; it is therefore not a
per-variant `scientifically_unavailable` code accepted here. Receiving that
code inside a request, or receiving a request without one concrete common
basis, is `ENGINE_INPUT_INTEGRITY_MISMATCH`.

The mapping is closed:

- if the primary entry carries one of these pre-`S8` scientific codes, the
  complete suite is `abstained`;
- if primary is released, a stricter-, short-, or long-history entry may be
  `unsupported` only with one of the same codes except
  `SOURCE_SEMANTICS_INELIGIBLE`, which is common to the Causal Question and
  therefore cannot fail for one sensitivity alone;
- `OVERLAP_COHORT_INSUFFICIENT` is produced only by this engine after a
  released entry is trimmed: primary makes the suite `abstained`, while a
  non-primary binary exposure variant becomes `unsupported`;
- the binary late-outcome sensitivity may be `unsupported` only with
  `COHORT_SUPPORT_INSUFFICIENT` from its frozen 50-late/50-non-late support
  rule;
- the continuous-load sensitivity has no permitted unsupported state once
  primary `S8` is released; invalid load input or PLR failure makes the suite
  `failed`; and
- a valid subject-only ineligibility record under the exact registry below
  preserves the population suite but produces subject-only `unsupported` with
  no subject scoring; `SUBJECT_OVERLAP_INSUFFICIENT` or
  `SUBJECT_DISTRIBUTION_UNSUPPORTED` suppresses only subject-facing support and
  does not change the valid population suite result.

An unknown code, a code at the wrong gate or scope, missing frozen
denominators, or inconsistent evidence is
`ENGINE_INPUT_INTEGRITY_MISMATCH`. An ingestion rejection, schema defect,
cohort-variant line-level eligibility code, or runtime/model error may never be
relabelled as scientific unavailability. A present `SubjectProfile` that is
malformed or contradicts its upstream evidence is an engine input failure, not
subject scientific unavailability.

Within every released entry, row order is deterministic: ascending by canonical
`order_line_id` byte representation after that variant's `S8_OUTCOME` identity
set is frozen. Input order supplied by a caller is not trusted.

`s8_identity_hash` covers only the canonical ordered identity list.
`s8_content_hash` covers `canonical-scientific-json.v1` containing the dataset version,
variant and selector/threshold references, adjustment-set ID/version, variant
evidence references in canonical byte order, and every field of every
`EstimatorRow` in canonical row order. Each row's lineage references are also
ordered canonically. There are no
excluded scientific fields or caller-supplied transport fields. The two
digests are distinct and neither substitutes for the other.

### `EstimatorRow`

Each row contains:

| Field | Type | Rule |
| --- | --- | --- |
| `order_line_id` | canonical ID | Unique within its variant; the same eligible identity may appear in multiple variants |
| `supplier_id` | canonical ID | Required cluster identity; excluded from primary features |
| `high_load_exposure` | boolean | The request variant's binary exposure |
| `supplier_milestone_slippage_days` | finite float | Required continuous outcome |
| `supplier_milestone_slippage_duration_basis` | canonical enum | Must exactly equal the request-wide `canonical_slippage_duration_basis` |
| `supplier_milestone_late` | boolean | Required for the binary sensitivity when supported |
| `load_percentile` | finite float in `[0,1]` | Required for the continuous sensitivity |
| `covariates` | typed values and explicit value states | Exactly the declared adjustment set |
| `lineage_refs` | non-empty reference set | Covers exposure, outcome, covariates, and cluster identity |

No row may contain a subject flag, recommendation, post-treatment field,
evaluation-only ground truth, source-only extension, or planted-effect value.

### `AdjustmentSetSpec`

The adjustment-set specification contains:

- an immutable ID and version;
- ordered covariate definitions;
- logical type for every covariate;
- transformation rule ID and version;
- whether a covariate is numeric or categorical at estimation;
- an exhaustive, ordered categorical vocabulary when categorical;
- the exact explicit-state or indicator encoding for `absent`, `unknown`,
  `redacted`, and any semantically valid `not_applicable`;
- the output feature names and order; and
- evidence that every covariate and derivation input is pre-treatment.

`supplier_id`, `order_line_id`, `project_id`, outcome values, exposure values,
post-treatment values, and evaluation-only ground truth are prohibited primary
features. A separately named pre-treatment supplier trait or expanding-history
feature may enter only through the adjustment set.

### `PropensitySpec`

The request's propensity specification is a closed record with these exact
values:

| Field | Exact value |
| --- | --- |
| `propensity_spec_id`, `propensity_spec_version` | `supplier-grouped-calibrated-hgb-5x2`, `v1` |
| `training_stage` | `S8_OUTCOME` |
| `feature_schema_ref` | The request's exact `AdjustmentSetSpec` ID and version |
| `outer_splitter` | `sklearn.model_selection.StratifiedGroupKFold` |
| `outer_n_splits`, `outer_n_repeats` | `5`, `2` |
| `outer_stratify`, `outer_group`, `outer_shuffle` | `high_load_exposure`, `supplier_id`, `true` |
| `base_learner` | `sklearn.ensemble.HistGradientBoostingClassifier` |
| `base_learner_parameters` | Exactly the propensity-nuisance block below |
| `calibrator` | `sklearn.calibration.CalibratedClassifierCV` |
| `calibration_method`, `calibration_splits` | `sigmoid`, `3` supplier-grouped stratified splits |
| `calibration_ensemble`, `calibration_n_jobs` | `true`, `1` |
| `historical_aggregation` | Arithmetic mean of the two repeat-specific out-of-fold probabilities |
| `subject_aggregation` | Arithmetic mean of all ten primary outer-fold models |
| `support_interval` | Inclusive lower `0.10`, upper `0.90` |
| `doubleml_integration` | Authoritative mean supplied externally and replicated into both repeat slots |
| `seed_policy_id`, `seed_policy_version` | `sha256-coordinate-seeds`, `v1` |

No omitted field takes a library default. The versioned record resolves to the
exact feature, split, learner, calibration, aggregation, support, and seed
definitions in this specification; a mismatch is
`ENGINE_INPUT_SCHEMA_UNSUPPORTED`, not permission to coerce the request.

### `SubjectInput` and `SubjectProfile`

When present, `SubjectInput` is a discriminated union:

```text
eligible | scientifically_unavailable
```

`eligible` contains one `SubjectProfile`. `scientifically_unavailable`
contains `scope=SUBJECT_INELIGIBLE`, a non-empty canonically ordered set from
the closed registry below, the last gate stage, safe frozen summary counts, and
evidence references:

```text
PROACTIVE_SUBJECT_INPUT_UNUSABLE
COMMITMENT_CUTOFF_UNUSABLE
TARGET_MILESTONE_UNSUPPORTED
LOAD_SNAPSHOT_UNRESOLVABLE
SUPPLIER_HISTORY_INSUFFICIENT
FROZEN_PROMISE_UNAVAILABLE
FROZEN_PROMISE_CONFLICT
FROZEN_PROMISE_TEMPORALLY_INVALID
COVARIATE_TEMPORAL_LEAKAGE
REQUIRED_COVARIATE_UNUSABLE
```

The last nine are the temporal contract's exact codes common to estimation and
subject lines; here they are accepted only at subject scope.
`PROACTIVE_SUBJECT_INPUT_UNUSABLE` is accepted only for a provisional subject.
The unavailable branch contains no partially trusted profile values and
triggers no subject scoring. Either branch remains separate from every
historical cohort.

An eligible current `SubjectProfile` contains:

- its canonical Order Line identity or external proposal identity;
- its supplier;
- its canonical exposure or provisional exposure preview;
- the identical ordered adjustment-set values and value states;
- the applicable decision cutoff and target milestone;
- upstream pre-estimation subject-eligibility facts; and
- lineage or proposal-evidence references.

It contains no observed outcome and never changes any cohort denominator,
feature fit, split, learner, or population estimate.

## Input validation and causal-question assembly

Validation runs in this order:

1. require a supported input schema, Causal Question, suite, and engine
   configuration;
2. verify exact runtime versions;
3. require exactly the four ordered variant inputs and verify dataset, role,
   milestone, request-wide slippage duration basis, trigger, selector,
   threshold-rule, and variant consistency;
4. preserve upstream scientific-unavailability records without fitting;
5. for each released variant, reject duplicate row identities, sort the rows,
   then recompute and match both its `s8_identity_hash` and
   `s8_content_hash`;
6. verify every released `S8_OUTCOME` count against its frozen stage summary;
7. require binary exposure, finite outcomes, every row's exact equality to the
   request-wide slippage duration basis, finite load percentiles in range, and
   one non-empty supplier cluster per row;
8. validate the adjustment-set schema, feature order, values, explicit states,
   and temporal evidence;
9. prove that IDs, exposure, outcomes, prohibited fields, and evaluation ground
   truth are absent from the primary feature matrix;
10. verify the minimum-support gates already recorded upstream;
11. validate or construct deterministic folds for each released variant;
12. only then fit propensity nuisance models.

A mismatch never causes the engine to repair, infer, drop, reorder
semantically, or reinterpret a row. Deterministic sorting is the only permitted
normalization at this boundary.

## Feature materialization

Feature materialization is deterministic and versioned.

### Numeric covariates

- Present finite numeric values pass through as `float64`.
- There is no scaling, winsorization, clipping, or learned imputation.
- A non-present value is represented only by its pre-registered value-state or
  indicator encoding. Any numeric placeholder used alongside an indicator is
  fixed by the adjustment-set version and cannot be confused with presence.
- NaN, positive infinity, and negative infinity are prohibited in the final
  design matrix.

### Categorical covariates

Categorical output is equivalent to:

```python
OneHotEncoder(
    categories=<ordered vocabularies from AdjustmentSetSpec>,
    drop=None,
    sparse_output=False,
    handle_unknown="error",
    dtype=np.float64,
)
```

The vocabulary is configuration, not learned from all rows. An explicitly
declared `other` category is allowed only when the upstream mapping
semantically assigned it; the engine never maps an unknown value to `other`.

### Model matrices

- Tree nuisance models use the complete fixed one-hot layout.
- Linear comparisons use the same numeric fields but deterministic reference
  coding: the first configured category is omitted for each categorical field.
- Supplier fixed-effects OLS additionally omits the first supplier in canonical
  supplier-ID order.
- An intercept is added only by the comparison estimator that declares it.
- Column order and a `sha256:` feature-schema digest are returned as logical
  output facts.

## Runtime and seed policy

### Runtime pins

The engine requires:

| Dependency | Exact version |
| --- | --- |
| CPython | `3.12.13` |
| DoubleML | `0.11.3` |
| scikit-learn | `1.6.1` |
| NumPy | `2.2.6` |
| SciPy | `1.15.3` |
| Statsmodels | `0.14.6` |

Statsmodels is an explicit direct dependency even though DoWhy also requires
`statsmodels>=0.14`. A different resolved version is an engine-configuration
change, not an invisible transitive upgrade.

EconML remains installed for the wider researched stack but the Core engine
does not import or execute `CausalForestDML`.

### Seed derivation

Every stochastic component receives a derived unsigned 32-bit seed. No
component reads NumPy's or Python's process-global RNG.

The seed material uses `canonical-scientific-json.v1` and these fields:

```text
root_seed
dataset_version_id
causal_question_id
causal_question_version
engine_config_id
engine_config_version
suite_id
suite_version
fixture_id or null
variant_id or null
repeat_index or null
outer_fold_index or null
inner_fold_index or null
component
```

The derived seed is the big-endian integer represented by the first four bytes
of `SHA-256(seed_material)`. Indices are zero-based. Component names are a
closed registry:

```text
outer_split
inner_calibration_split
propensity_learner
outcome_learner_unexposed
outcome_learner_exposed
binary_outcome_learner_unexposed
binary_outcome_learner_exposed
continuous_outcome_learner
continuous_exposure_learner
fixture_generator
```

The coordinate matrix is exact:

| Component | `fixture_id` | `variant_id` | `repeat_index` | `outer_fold_index` | `inner_fold_index` |
| --- | --- | --- | --- | --- | --- |
| `outer_split` | `null` | required | required | `null` | `null` |
| `inner_calibration_split` | `null` | required | required | required | `null` |
| `propensity_learner` | `null` | required | required | required | `null` |
| `outcome_learner_unexposed`, `outcome_learner_exposed` | `null` | required | required | required | `null` |
| `binary_outcome_learner_unexposed`, `binary_outcome_learner_exposed` | `null` | required | required | required | `null` |
| `continuous_outcome_learner`, `continuous_exposure_learner` | `null` | required | required | required | `null` |
| `fixture_generator` | required fixture ID | `null` | `null` | `null` | `null` |

Unused coordinates are JSON `null`; omission and empty strings are invalid.
One `inner_calibration_split` seed draws the complete three-way split. The
three `CalibratedClassifierCV` base-estimator clones deliberately share their
outer model's single `propensity_learner` seed; there is no independently
seeded inner learner in `v1`. `inner_fold_index` is reserved and therefore
always `null` in `v1`.

Every derived seed is retained logically with the complete component
coordinates, including explicit nulls.

### Execution concurrency

- `DoubleML.fit(n_jobs_cv=1)` is mandatory.
- The engine process fixes OpenMP, BLAS, MKL, and equivalent numerical worker
  counts to one before importing numerical libraries.
- Calibration uses `n_jobs=1`.
- Fold and variant fitting is sequential.
- A different thread policy requires a new engine configuration version.

This policy prioritizes replay stability over maximum throughput. The
operations ticket must benchmark it on the demo laptop; runtime pressure never
permits silent parallelism or remote training.

## Cross-fitting contract

### Outer splits

Every binary variant uses two repeated five-fold splits:

```python
StratifiedGroupKFold(
    n_splits=5,
    shuffle=True,
    random_state=<derived outer_split seed>,
)
```

- `y` is the variant's binary High-Load Exposure.
- `groups` is `supplier_id`.
- Each supplier appears in exactly one test fold per repeat.
- The two repeats use distinct derived seeds.
- Every row receives exactly one out-of-fold prediction per repeat.
- Exact row and supplier assignments are retained logically.

Before fitting, each repeat must satisfy:

- disjoint train/test row identities;
- disjoint train/test suppliers;
- complete test-row partition;
- complete test-supplier partition;
- both exposure arms in every outer training set; and
- no empty train or test set after any permitted restriction.

Failure is `ENGINE_SPLIT_INFEASIBLE`. Any observed overlap, omission,
duplication, or coordinate mismatch after construction is
`ENGINE_SPLIT_INTEGRITY_VIOLATION`.

### Inner calibration splits

Within each outer training set, propensity calibration uses:

```python
StratifiedGroupKFold(
    n_splits=3,
    shuffle=True,
    random_state=<derived inner_calibration_split seed>,
)
```

with the same exposure label and supplier grouping. Every inner training and
calibration partition must contain both exposure arms. Invalid inner support
fails closed with `ENGINE_SPLIT_INFEASIBLE`; no uncalibrated fallback is
allowed.

### Split reuse

The propensity ensemble is fit on `S8_OUTCOME`. After trimming, every
`S9_OVERLAP` supplier and row retains its original outer-fold assignment.
Empty or arm-deficient restricted training partitions make estimation
infeasible.

Primary ATTE, contextual ATE, the binary late-outcome sensitivity, and all
primary-cohort comparisons reuse the restricted primary splits. The continuous
load sensitivity also reuses them. A binary exposure sensitivity constructs
its own folds from its own `S8_OUTCOME` exposure labels.

## Nuisance learner contract

### Fixed gradient-boosting baseline

There is no adaptive hyperparameter search, early stopping, or
result-conditioned model selection in Core.

The shared fixed parameters are:

```text
learning_rate = 0.05
max_iter = 200
max_leaf_nodes = 15
max_depth = None
min_samples_leaf = 20
l2_regularization = 1.0
max_features = 1.0
max_bins = 255
categorical_features = None
monotonic_cst = None
interaction_cst = None
early_stopping = False
warm_start = False
scoring = "loss"
validation_fraction = None
n_iter_no_change = 10
tol = 1e-7
verbose = 0
```

Every learner receives its derived `random_state`.

### Continuous outcome nuisance

Both `g(0, X)` and `g(1, X)` use:

```python
HistGradientBoostingRegressor(
    loss="squared_error",
    quantile=None,
    learning_rate=0.05,
    max_iter=200,
    max_leaf_nodes=15,
    max_depth=None,
    min_samples_leaf=20,
    l2_regularization=1.0,
    max_features=1.0,
    max_bins=255,
    categorical_features=None,
    monotonic_cst=None,
    interaction_cst=None,
    early_stopping=False,
    warm_start=False,
    scoring="loss",
    validation_fraction=None,
    n_iter_no_change=10,
    tol=1e-7,
    verbose=0,
    random_state=<derived seed>,
)
```

The unexposed learner trains only on unexposed rows of the outer training set;
the exposed learner trains only on exposed rows. No fold may borrow a row from
its outer test set.

### Propensity nuisance

The base classifier is:

```python
HistGradientBoostingClassifier(
    loss="log_loss",
    learning_rate=0.05,
    max_iter=200,
    max_leaf_nodes=15,
    max_depth=None,
    min_samples_leaf=20,
    l2_regularization=1.0,
    max_features=1.0,
    max_bins=255,
    categorical_features=None,
    monotonic_cst=None,
    interaction_cst=None,
    early_stopping=False,
    warm_start=False,
    scoring="loss",
    validation_fraction=None,
    n_iter_no_change=10,
    tol=1e-7,
    verbose=0,
    class_weight=None,
    random_state=<derived seed>,
)
```

It is wrapped inside each outer training set as:

```python
CalibratedClassifierCV(
    estimator=<base classifier>,
    method="sigmoid",
    cv=<three exact inner supplier-grouped splits>,
    n_jobs=1,
    ensemble=True,
)
```

The calibrated outer model predicts only its held-out outer fold for
historical out-of-fold propensity. It also remains one member of the
subject-scoring ensemble.

### Binary outcome nuisance

The binary late-outcome sensitivity uses separate
`HistGradientBoostingClassifier` learners for unexposed and exposed training
rows with the same fixed parameters. They are not calibrated. Propensity
calibration remains unchanged.

### Continuous load nuisances

`DoubleMLPLR` uses:

- `HistGradientBoostingRegressor` for `E[Y|X]`; and
- a separate `HistGradientBoostingRegressor` for
  `E[load_percentile|X]`.

Both use the same fixed parameters and restricted primary folds. The continuous
exposure learner is not the binary propensity learner.

### Nuisance reuse

The engine constructs nuisance predictions itself from the declared folds and
component-specific seeds. DoubleML never internally fits a nuisance learner.
The primary ATTE and contextual ATE are computed with the exact same:

- `S9_OVERLAP` rows;
- outer splits;
- `g(0, X)` predictions;
- `g(1, X)` predictions; and
- authoritative mean calibrated propensity.

Both fits use DoubleML external predictions. The only intended difference is
the score and estimand weighting.

### External prediction arrays

For every IRM estimand, the engine builds:

```text
external_predictions = {
  <exposure column>: {
    "ml_g0": float64[n_s9, 2],
    "ml_g1": float64[n_s9, 2],
    "ml_m":  float64[n_s9, 2]
  }
}
```

Rows follow canonical `S9` order and columns follow repeat indices `0,1`.
Every `ml_g0` or `ml_g1` cell is produced by the arm-specific model for the
row's held-out outer fold and repeat. Every `ml_m` column contains the same
authoritative mean propensity described below. The engine validates exact
shape and order, finite continuous-outcome predictions, propensities in range,
fold provenance, and exclusion of the row and its supplier from the
contributing training set. For the binary late outcome, `ml_g0` and `ml_g1`
are the positive-class `predict_proba` columns and must also lie in `[0,1]`.

Primary, context, each binary exposure sensitivity, and the binary late
outcome sensitivity all pass their complete arrays to:

```text
fit(
  n_jobs_cv=1,
  store_predictions=True,
  external_predictions=<validated arrays>
)
```

The `ml_g` and `ml_m` objects supplied to the `DoubleMLIRM` constructor are
unfitted, interface-valid prototypes of the exact configured learner classes;
they are never a second training path.

For `DoubleMLPLR`, the engine likewise builds and validates repeat-indexed
`ml_l` and continuous-exposure `ml_m` arrays from the declared restricted
primary folds and component seeds, then supplies both as external predictions.
Its constructor learners are also unfitted interface prototypes. No DoubleML
estimator may silently clone and fit one seed across folds or repeats.

## Propensity and overlap contract

For each binary variant:

1. fit the two-repeat, five-fold calibrated propensity ensemble on
   `S8_OUTCOME(m)`;
2. retain the two out-of-fold probabilities for every historical row;
3. compute their arithmetic mean;
4. require each probability and mean to be finite and inside `[0,1]`;
5. apply the inclusive historical support rule:

```text
retain iff 0.10 <= mean_out_of_fold_propensity <= 0.90
```

6. form `S9_OVERLAP(m)` from retained identities;
7. compute overall and per-arm trimming rates against frozen `S8_OUTCOME(m)`;
8. re-run the temporal-eligibility contract's post-trim support gates; and
9. stop with `OVERLAP_COHORT_INSUFFICIENT` if any gate fails.

No threshold is moved. No propensity learner is changed. No row returns after
exclusion.

### DoubleML integration

DoubleML receives the stored historical propensities as external `ml_m`
predictions, restricted to `S9_OVERLAP`. The two raw out-of-fold probabilities
remain retained for audit, but their arithmetic mean is the authoritative
historical propensity used for both overlap and effect scoring. The engine
replicates that mean into both DoubleML repeat slots. It does not refit a
propensity model, and it does not pass the raw repeat probabilities into the
score.

`DoubleMLIRM` is configured with:

```text
n_folds = 5
n_rep = 2
draw_sample_splitting = False
normalize_ipw = False
weights = None
PSProcessorConfig(
    clipping_threshold=0.10,
    extreme_threshold=1e-12,
    calibration_method=None,
    cv_calibration=False,
)
```

The exact restricted row splits and matching supplier-cluster splits are
supplied with `set_sample_splitting`; DoubleML is not allowed to redraw either
partition.
DoubleML's `0.10` clipping is a numerical no-op because every supplied row has
already passed the inclusive rule. The engine verifies that processed and
supplied propensities are equal within `1e-15`; otherwise it fails with
`ENGINE_NUISANCE_PREDICTION_INVALID`.

Replicating the mean does not erase split evidence: the result retains both raw
repeat predictions, their mean, every contributing outer model, and the fold
coordinates. It prevents one raw repeat outside `[0.10, 0.90]` from creating a
second hidden clipping rule after the row passed the contractually authoritative
mean-propensity gate.

Repeated-cross-fit aggregation is the pinned DoubleML `0.11.3` behavior:

- the reported coefficient is the median of the two repeat coefficients; and
- the reported standard error is derived from the median repeat upper bound.

The output retains both per-repeat coefficient and standard-error pairs so
this aggregation remains auditable.

## Primary estimation and inference

### DoubleML data object

Every DoubleML estimator uses `DoubleMLClusterData` with:

```text
y_col = the declared outcome
d_cols = the declared exposure
x_cols = the ordered materialized adjustment features
cluster_cols = supplier_id
```

Only one cluster variable is permitted.

### Primary ATTE

The primary fit uses `DoubleMLIRM(score="ATTE")` on primary
`S9_OVERLAP(10)`.

The logical result includes:

- estimate in slippage days;
- native supplier-clustered standard error;
- two-sided 95% marginal confidence interval;
- t statistic and p value as measurements, not verdicts;
- per-repeat estimates and standard errors;
- cohort, arm, and supplier counts; and
- references to the exact nuisance and fold facts.

### Context ATE

The context fit uses `DoubleMLIRM(score="ATE")` on the identical primary
cohort and external nuisance predictions. It is labelled
`overlap_trimmed_context`; it is never promoted over the primary ATTE.

### Inference

Primary and DoubleML sensitivity inference use DoubleML's native one-way
supplier-clustered variance estimator and a two-sided 95% marginal interval.
The engine does not add a second cluster-bootstrap interval.

Bootstrap, refuter repetition, multiple-testing policy, interval-based
Diagnostic Results, and Evidence Verdict implications belong to the validity
contract.

## Sensitivity execution

### Binary exposure variants

Each binary exposure variant repeats the complete `S8` propensity, `S9`
overlap, nuisance, and `DoubleMLIRM(score="ATTE")` pipeline with its own
identities, labels, folds, and derived seeds. A primary propensity or fold is
never reused for a different exposure definition.

### Binary late-outcome variant

This variant reuses primary `S9_OVERLAP`, folds, and propensities but fits the
two binary outcome nuisances. Its estimate is an ATTE risk difference in
absolute probability units and is additionally rendered as percentage points.

If the temporal-eligibility contract's minimum late/non-late support fails,
this sensitivity is `unsupported` with `COHORT_SUPPORT_INSUFFICIENT` scoped to
`sensitivity_late_risk_atte`; the valid primary result remains available.
Unexpected learner or estimator failures fail the entire engine result.

### Continuous load variant

`DoubleMLPLR(score="partialling out")` runs on primary `S9_OVERLAP`, with
`load_percentile` as the continuous exposure. It uses the restricted primary
folds and supplier-clustered inference.

The primary logical value is the coefficient in days per full `[0,1]`
percentile span. The UI-consumable measurement is the deterministic
`coefficient * 0.10`, in days per 0.10 percentile increase. It is always
labelled `linear_average_slope`.

## Comparison estimator contract

Comparisons run only on primary `S9_OVERLAP` with the primary continuous
outcome and binary exposure. They are measurements for triangulation and
pedagogy, not alternate headline causal estimates.

The closed comparison IDs are:

```text
naive_mean_difference
covariate_ols
normalized_ipw_atte
supplier_fe_ols
```

All comparisons use Statsmodels `0.14.6`, one-way `supplier_id` cluster
covariance, `use_correction=True`, `df_correction=True`, `use_t=True`, and a
two-sided 95% t interval with inference degrees of freedom based on cluster
count minus one.

### Naive mean difference

Fit:

```text
slippage ~ intercept + high_load_exposure
```

with OLS. The exposure coefficient equals the unadjusted exposed-minus-
unexposed mean difference.

### Covariate-adjusted OLS

Fit:

```text
slippage ~ intercept + high_load_exposure + reference-coded adjustment features
```

The feature set is identical in meaning to the primary adjustment set. No
feature is selected by correlation or significance.

### Normalized propensity-weighted ATTE

Fit weighted:

```text
slippage ~ intercept + high_load_exposure
```

with:

```text
exposed weight = 1
unexposed weight = p / (1 - p)
```

where `p` is the authoritative mean out-of-fold propensity. Normalize the
unexposed weights to sum to the number of exposed rows before fitting. Return
effective sample size by arm:

```text
ESS = (sum weights)^2 / sum(weights^2)
```

### Supplier fixed-effects OLS

Fit:

```text
slippage
  ~ intercept
  + high_load_exposure
  + reference-coded adjustment features
  + reference-coded supplier fixed effects
```

Only suppliers present in primary `S9_OVERLAP` appear. This comparison is a
linear within-supplier diagnostic; it does not alter the primary DML feature
set or estimand.

### Comparison validity

Every comparison must:

- preserve the primary cohort identities;
- expose matrix rank, condition number, exposure coefficient, standard error,
  interval, and supplier count;
- have an estimable exposure coefficient;
- return finite values and an ordered interval; and
- use no post-treatment or evaluation-only field.

Rank deficiency that makes the exposure coefficient unidentified,
non-finite output, or a fit exception is `ENGINE_COMPARISON_FIT_FAILED`.
Because the comparison suite is required Core evidence, such failure makes the
engine result `failed`, not partially estimated.

Every comparison returns a closed `ComparisonResult`:

| Field | Rule |
| --- | --- |
| `comparison_id` | One of the four IDs above |
| `model_class` | Exact Statsmodels OLS or WLS class |
| `coefficient_name` | Exactly `high_load_exposure` |
| `estimate`, `standard_error` | Finite floats in slippage days |
| `t_statistic`, `p_value` | Finite measurements; `p_value` in `[0,1]` |
| `ci_level`, `ci_lower`, `ci_upper` | `0.95`; finite ordered t interval |
| `covariance_type`, `cluster_key` | `cluster`, `supplier_id` |
| `use_correction`, `df_correction`, `use_t` | All exactly `true` |
| `inference_df` | Exactly supplier count minus one |
| `row_count`, exposed/unexposed counts, `supplier_count` | Positive and reconciled to primary `S9` |
| `matrix_column_count`, `matrix_rank`, `condition_number` | Positive, finite, and consistent with the exact design matrix |
| `design_matrix_digest`, `feature_schema_digest` | `sha256:` digests of canonical column order and values/schema |
| `cohort_identity_hash` | Exact primary `S9` digest |
| `propensity_ref`, `fold_ref` | Required only for `normalized_ipw_atte`; absent for the other three |
| `weight_diagnostics` | Required only for `normalized_ipw_atte`; absent otherwise |

`weight_diagnostics` contains exposed and unexposed raw weight sums, normalized
weight sums, and effective sample size by arm, all finite and positive. The
unexposed normalized sum must equal the exposed row count within its declared
numeric tolerance; exposed weights remain exactly one.

There is no separate "AIPW comparison": the primary `DoubleMLIRM` orthogonal
score already provides the augmented estimate.

## Subject scoring

For an eligible subject, using only the primary variant's outer models:

1. validate the identical adjustment-set schema and fixed categories;
2. transform it with each outer model's paired feature materializer;
3. obtain one propensity from each of the ten calibrated outer models;
4. require every probability to be finite and in `[0,1]`;
5. compute the arithmetic mean of all ten probabilities;
6. apply the inclusive `[0.10,0.90]` subject overlap rule; and
7. compute and record the temporal-eligibility contract's categorical,
   missingness, marginal numeric, and Gower-neighbour support measurements
   against primary `S9_OVERLAP`.

No full-cohort propensity refit or alternate ensemble aggregation is allowed.
The subject output contains:

- canonical exposure or provisional exposure preview;
- ten model probabilities and their mean;
- overlap threshold and result;
- distribution-support measurements;
- applicable subject-level codes; and
- evidence references.

It contains no individualized effect. It does not relabel population ATTE as
the subject's effect. The
[validity verdict contract](validity-verdict-evidence-abstention-contract.md)
governs whether and how population evidence may support a subject-facing
Evidence Verdict.

## Logical output contract

The physical artifact contract will choose serialization and identity. The
engine's logical result is a discriminated union:

```text
estimated | abstained | failed
```

### Common fields

Every branch contains:

- exact input and output schemas, error registry, Causal Question, engine
  configuration, estimand suite, propensity specification, and seed-policy IDs
  and versions;
- dataset version and intended role;
- suite identity, all four variant identities, target milestone, and exact
  `canonical_slippage_duration_basis`;
- runtime versions and thread policy;
- root seed and derived seed registry;
- all four variant statuses, stage summaries, and any released `S8` identity
  and content hashes;
- feature-schema digest;
- start and completion timestamps supplied by the Analysis Run boundary;
- status; and
- evidence references.

Timestamps do not participate in deterministic scientific identity.

### `estimated`

An estimated result contains:

- every released variant's `S9` ordered identities and `sha256:` identity hash;
- every released variant's per-row/per-repeat and mean historical propensities;
- per-variant trimming decisions and overall/per-arm rates;
- per-variant fold row/supplier assignments;
- nuisance learner specifications and predictions;
- primary ATTE result;
- contextual ATE result;
- all required comparison results;
- each sensitivity's `estimated` or permitted `unsupported` state;
- optional subject-support output.

Version `v2` has no warning channel. A later warning must first enter a closed,
versioned code registry; free-text warnings and causal prose are prohibited.

An effect result contains:

| Field | Rule |
| --- | --- |
| `estimand_id` | Closed enum from the estimand table |
| `role` | `primary`, `context`, or `sensitivity` |
| `estimator_class`, `score` | Exact pinned class and score |
| `estimate`, `standard_error` | Finite canonical-unit floats; standard error strictly positive |
| `t_statistic`, `p_value` | Finite measurements; `p_value` in `[0,1]` |
| `ci_level` | Exactly `0.95` |
| `ci_lower`, `ci_upper` | Finite and ordered |
| `unit` | Canonical unit: `days`, `absolute_probability`, or `days_per_unit_load_percentile` |
| `duration_basis` | Exact request-wide basis for `days` and `days_per_unit_load_percentile`; `NOT_APPLICABLE` for `absolute_probability` |
| `display_transform` | Closed transform record described below |
| `cluster_key` | `supplier_id` |
| `cluster_count`, arm counts, row count | Positive integers consistent with `S9` |
| `repeat_results` | Both repeat estimates and finite, strictly positive standard errors |
| `cohort_identity_hash` | The applicable `S9` digest |
| `nuisance_refs`, `fold_ref` | Non-empty logical references |

The canonical binary-late estimate, standard error, interval, and repeat
results are stored in `absolute_probability`. Its display transform is
`scale=100` with unit `percentage_points`. The canonical continuous-load
coefficient, standard error, interval, and repeat results are stored in
`days_per_unit_load_percentile`, meaning a full change from `0` to `1`. Its
display transform is `scale=0.10` with unit
`days_per_0_10_load_percentile`. Other effects use `scale=1`.

Every `days` or `days_per_unit_load_percentile` value retains the exact
request-wide duration basis through canonical output and display. Runtime never
labels calendar-day and elapsed-86,400-second-day effects with one ambiguous
unit, converts between them, or drops the basis after estimation.

`display_transform` contains only `scale`, `display_unit`, and the
deterministically scaled estimate, standard error, and interval. All four
numeric quantities use the same scale; no display field is independently
estimated or substituted back into canonical inference.

### `abstained`

An abstained result contains:

- the existing scientific code;
- scope and gate stage;
- frozen denominator and numerator counts;
- evidence references; and
- no estimate, standard error, interval, comparison, or effect-bearing
  sensitivity field.

Within this engine, overlap and post-trim support failures are the normal
scientific abstention path. An orchestration layer may preserve an earlier
upstream abstention without invoking estimator fitting.

### `failed`

A failed result contains:

- one primary engine error code;
- ordered secondary engine error codes, if independently observed before
  stopping;
- ordered `DetailFact` values from the closed safe-detail schema;
- the last completed non-effect stage;
- evidence references; and
- no consumable estimate.

Tracebacks, local paths, raw data values, credentials, and confidential
identifiers never enter a UI-consumable error. Developer logs remain local and
are governed by the later artifact and operations contracts.

### Safe `DetailFact` schema

An error may contain only these tagged facts:

| Tag | Allowed payload |
| --- | --- |
| `stage` | One closed cohort or engine-stage enum |
| `component` | One closed seed-component or estimator-component enum |
| `variant` | One closed `variant_id` |
| `estimand` | One closed `estimand_id` |
| `schema_field` | One field name from the supported logical schema |
| `count` | Metric enum plus non-negative expected and observed integers |
| `shape` | Tensor enum plus expected and observed arrays of non-negative dimensions |
| `dependency_version` | Dependency enum plus expected and observed version strings |
| `coordinate` | Non-negative repeat, outer-fold, or inner-fold index |
| `threshold` | Registered threshold enum plus finite expected and observed aggregate values |

There is no generic string, message, map, or extension payload. Detail facts
must not contain row, supplier, project, dataset, run, or subject IDs; feature
or outcome values; free-form categories; hashes; file or network paths;
exception text; tracebacks; environment values; credentials; or causal
language. The error code and closed tags must be sufficient for UI rendering.

## Engine error registry

The registry is closed and versioned:

| Code | Meaning |
| --- | --- |
| `ENGINE_INPUT_SCHEMA_UNSUPPORTED` | Input, Causal Question, engine configuration, or error-registry version is unsupported |
| `ENGINE_INPUT_INTEGRITY_MISMATCH` | Identity hash, count, dataset reference, lineage reference, or frozen summary is inconsistent |
| `ENGINE_RUNTIME_INCOMPATIBLE` | Python, dependency, or thread-policy runtime differs from the exact engine configuration |
| `ENGINE_FEATURE_CONTRACT_VIOLATION` | Feature missing/extra/order/type/state/category/finite-value or prohibited-feature rule fails |
| `ENGINE_SPLIT_INFEASIBLE` | Required outer or inner supplier-grouped partitions cannot satisfy support |
| `ENGINE_SPLIT_INTEGRITY_VIOLATION` | A supplied or constructed split overlaps, omits, duplicates, leaks a supplier, or mismatches coordinates |
| `ENGINE_NUISANCE_FIT_FAILED` | Required nuisance or calibrator cannot fit |
| `ENGINE_NUISANCE_PREDICTION_INVALID` | Required nuisance output has wrong shape, non-finite/out-of-range values, leakage, or unauthorized processing |
| `ENGINE_ESTIMATOR_FIT_FAILED` | Required DoubleML primary, context, or sensitivity estimator raises or cannot solve |
| `ENGINE_COMPARISON_FIT_FAILED` | A required comparison raises, is unidentified, or returns invalid inference |
| `ENGINE_RESULT_INVALID` | A required logical result is non-finite, malformed, inconsistent, or violates interval/count/unit invariants |
| `ENGINE_REPRODUCIBILITY_VIOLATION` | Same logical input/runtime produces different exact identities, features, folds, seeds, codes, or out-of-tolerance numeric output |
| `ENGINE_INTERNAL_ERROR` | An unexpected engine defect occurred and no narrower registered code applies |

No runtime layer may translate an engine error into a scientific abstention or
vice versa. `ENGINE_INTERNAL_ERROR` is a fail-closed catch-all, never a license
to continue.

### Error precedence

When several conditions are observable without continuing a failed fit, choose
the first in this order:

1. input schema;
2. input integrity;
3. runtime;
4. feature contract;
5. split feasibility;
6. split integrity;
7. nuisance fit;
8. nuisance prediction;
9. estimator fit;
10. comparison fit;
11. result validity;
12. reproducibility; and
13. internal error.

Independent earlier findings may remain as secondary codes. The engine does
not continue into a later stage merely to collect more failures.

## Required component and partial-failure policy

For one suite execution, all of these are required:

- the four exact suite-member inputs and each released variant's propensity
  ensemble and overlap facts;
- primary ATTE;
- context ATE;
- four comparison estimators;
- every sensitivity whose upstream support gate passes; and
- subject scoring when an eligible `SubjectProfile` was supplied.

Failure of any required component makes the entire result `failed`. No caller
may consume an otherwise computed primary coefficient from that result.

Only a sensitivity whose declared scientific support rule fails may be
`unsupported` while preserving an `estimated` primary result. Model exceptions,
invalid predictions, or malformed inference are engine failures, not
unsupported science.

## Deterministic conformance fixtures

These fixtures test engine execution. They do not replace issue #13's
five-scenario scientific acceptance harness.

### Authoritative fixture pack

The authoritative engine fixture pack is:

```text
tests/fixtures/causal_engine/v1/manifest.json
tests/fixtures/causal_engine/v1/inputs/*.jsonl
tests/fixtures/causal_engine/v1/expected/*.json
```

The checked-in input snapshots, not a generator implementation, are the
authoritative test inputs. A generator may rebuild them for review, but a
conformance test never generates a fresh random cohort at test time.

`manifest.json` contains:

| Field | Rule |
| --- | --- |
| `fixture_pack_schema_version` | Supported exactly |
| `fixture_pack_id`, `fixture_pack_version` | `core-causal-engine-conformance`, `v2` |
| `engine_input_schema_version` | Exact request schema exercised |
| `causal_question_id`, `causal_question_version` | Exact Core question |
| `engine_config_id`, `engine_config_version` | Exact runtime and estimator configuration |
| `suite_id`, `suite_version` | Exact four-member Core suite |
| `root_seed` | Exactly `160016` unless a replay case declares its alternate seed |
| `generator_spec_id`, `generator_spec_version` | Identifies the reviewed offline builder; never interpreted by the engine |
| `fixtures` | Ordered, non-empty fixture definitions |

Each fixture definition contains:

- fixture ID and version;
- fixture kind: `full_fit` or `processor_micro`;
- ordered input paths plus `sha256:` content digests;
- exact row, supplier, arm, mixed-arm-supplier, and variant counts;
- exact subject input or `null`;
- exact injected-fault operation or `null`;
- expected result branch and primary/secondary codes;
- expected exact facts and their expected-output path;
- expected numeric facts, reference values, and per-field absolute and relative
  tolerances;
- the platform/runtime on which reference numeric values were approved; and
- the engine-configuration change that authorized the reference values.

Input JSONL uses `canonical-scientific-json.v1`: one object per line, LF
separators, no final LF, and rows in canonical identity order. Expected JSON
uses the same encoding. IDs, counts, categories, features, folds, seeds,
statuses, codes, units, and hashes compare exactly.
Floating-point comparisons use:

```text
abs(actual - expected) <= abs_tol + rel_tol * abs(expected)
```

Every numeric assertion declares both tolerances; neither may be inferred from
a global testing default. Replay within the pinned runtime uses
`abs_tol=1e-10` and `rel_tol=1e-8` unless a field declares a stricter value.
Issue #13, not this pack, owns tolerances against planted scientific truth.

The first engine implementation slice must check in this complete fixture pack
before its estimator implementation can be accepted. A test may never obtain
its expected value by running the system under test. Missing files, digest
mismatch, undeclared numeric tolerance, or a fixture definition not covered by
the closed list below fails the conformance suite. Golden values may change
only with an approved engine-configuration or fixture-pack version change and
an independently reviewed before/after record.

### Test-only nuisance seam

Boundary and malformed-prediction cases use a test-only
`ConformanceNuisanceInjection` seam. It accepts only manifest-hashed,
canonical-row-ordered nuisance arrays and subject propensities from a
`processor_micro` fixture. These arrays enter the same shape, range,
provenance, overlap, subject-support, external-prediction, and result validators
used after real fitting.

The seam is not part of `CausalEngineSuiteRequest`, is unavailable to the
application runtime, and cannot be selected by configuration or environment
variable. Production packaging must prove that its symbol and fixture files
are absent. This is the only permitted way to assert exact propensities such as
`0.10`, `0.90`, immediately adjacent values, NaN, or out-of-range values;
conformance never assumes that a fitted HGB-plus-sigmoid pipeline naturally
produces those exact numbers.

`full_fit` fixtures always execute the real feature materializers, grouped
splits, calibrated HGB nuisances, external-prediction assembly, DoubleML
estimators, comparisons, and result validation. They cannot use the injection
seam. Their checked-in canonical input snapshots and expected outputs are
authoritative; any optional generator is review tooling and cannot determine
pass/fail.

### Fixture rules

- Every fixture input is a `CausalEngineSuiteRequest` whose released variant entries
  begin at the `S8_OUTCOME` boundary; it does not masquerade as canonical
  source data.
- Every ordinary fitted fixture fixes one request-wide slippage duration basis
  and repeats that exact basis on every released row. Only the dedicated engine-
  input-integrity fixture introduces a mismatch, and it must fail before fitting.
- Every snapshotted fact is keyed by a stable fixture row ID and uses
  `root_seed=160016`.
- Fitted fixtures contain at least 1,500 rows, 50 suppliers, 300 rows in each
  exposure arm, and 30 mixed-arm suppliers so upstream support gates are not
  bypassed.
- Each supplier contributes the same declared row count unless the fixture is
  specifically testing imbalance.
- Feature and outcome generation uses the `fixture_generator` derived seed and
  an explicitly documented NumPy generator.
- No fixture reads wall-clock time, machine paths, unordered collections, or
  process-global randomness.
- Exact expected row identities, category order, feature names, fold
  assignments, seeds, codes, and hashes are generated from the contract
  algorithms and checked exactly.
- Estimated floating-point values use checked-in expected values plus declared
  absolute and relative tolerances. The expected values may be refreshed only
  after an approved engine-configuration change, never merely to make a test
  pass.

### `fixture_constant_effect`

Purpose:

- exercise primary ATTE, context ATE, all four comparisons, clustering, and
  repeated aggregation with a constant positive effect;
- require finite ordered intervals and identical estimand sign; and
- require ATTE and ATE to agree within the fixture's declared tolerance.

The planted effect lives only in the fixture generator's evaluation assertion,
never in the engine input.

### `fixture_atte_differs_from_ate`

Purpose:

- assign a larger planted effect to profiles more likely to be exposed;
- prove that ATTE and ATE use shared nuisances but different score weighting;
  and
- require the fitted ATTE to exceed the fitted ATE by the declared minimum
  tolerance.

### `fixture_continuous_load`

Purpose:

- generate a linear slippage response to `load_percentile`;
- require the `DoubleMLPLR` coefficient and derived per-0.10 value to have the
  analytically expected scale and sign; and
- prove the result is labelled `linear_average_slope`.

### `fixture_binary_late`

Purpose:

- provide sufficient late/non-late support;
- exercise binary outcome nuisances and the ATTE risk-difference output; and
- verify percentage-points conversion.

### `fixture_overlap_and_subject`

Purpose:

- run as a `processor_micro` fixture with exact manifest-hashed historical and
  subject propensity arrays;
- include historical means exactly at `0.10` and `0.90`, which must be
  retained;
- include values immediately outside both thresholds, which must be removed;
- require exact overall/per-arm trimming counts;
- score one supported subject from all ten outer models; and
- prove that no subject row enters `S8`, `S9`, a fold, or an effect estimate.

### `fixture_comparisons`

Purpose:

- exercise deterministic reference coding;
- require the naive, adjusted, weighted, and supplier-fixed-effects matrices
  to preserve the same cohort;
- verify normalized control weights and arm ESS; and
- verify supplier-clustered t intervals and degrees of freedom.

### `fixture_unsupported_sensitivity`

Purpose:

- pass the primary continuous-outcome run;
- fail only the binary late/non-late support rule; and
- require `sensitivity_late_risk_atte=unsupported` while the primary result
  remains `estimated`.

### `fixture_engine_errors`

Use one minimal fixture per error family, including:

- unknown schema;
- incorrect `S8` hash;
- missing request-wide duration basis or one row whose duration basis differs
  from it;
- runtime-version mismatch;
- unknown category and non-finite numeric input;
- too few supplier groups for an outer or inner split;
- supplier leakage across a supplied split;
- injected nuisance fit exception;
- NaN and out-of-range propensity;
- injected DoubleML exception;
- rank-deficient unidentified exposure in a comparison;
- non-finite interval;
- altered replay fold assignment; and
- sanitized unexpected exception.

Each fixture expects exactly one primary code according to registry precedence.
Prediction-boundary cases use `processor_micro`; split, learner, estimator,
comparison, and replay cases that require fitted behavior use `full_fit`.
Injected exceptions enter only through a manifest-declared test double at the
named component boundary. The manifest fixes the kind and injection point; a
test cannot switch either at runtime.

### `fixture_replay`

Run the constant-effect fixture twice in fresh processes:

- same root seed: exact identities, features, folds, seeds, statuses, and
  codes; numeric results within the declared strict replay tolerance;
- different root seed: at least one permitted fold assignment changes, all
  integrity checks still pass, and no claim is made that fitted coefficients
  remain equal.

## Conformance requirements

An implementation conforms only when:

1. unsupported schemas, roles, configurations, and runtimes fail before
   fitting;
2. exactly four ordered variant inputs are present, one concrete request-wide
   slippage duration basis is fixed, every released row matches it, and every
   `S8` identity hash, content hash, and stage count is reconciled;
3. prohibited fields cannot enter primary features;
4. category and feature order is invariant to input-row order;
5. suppliers never cross an outer train/test boundary;
6. every historical row has exactly two out-of-fold propensities;
7. a subject has exactly ten outer-model propensities;
8. `0.10` and `0.90` pass inclusively and immediately external values fail;
9. `S9` is formed once and DoubleML receives the authoritative mean propensity
   replicated unchanged across its two repeat slots;
10. primary ATTE and context ATE share nuisance predictions;
11. DoubleML reports native one-way supplier-clustered inference;
12. comparison estimators use the primary cohort and corrected supplier-cluster
    t inference;
13. the continuous sensitivity is a labelled linear slope;
14. no CATE, subgroup effect, action, Evidence Verdict, or causal prose is
    emitted;
15. required component failure exposes no consumable partial estimate;
16. permitted unsupported sensitivity preserves a valid primary result;
17. every registered error has a fixture and deterministic precedence;
18. replay satisfies exact and tolerant equality rules;
19. the engine starts and completes with network disabled; and
20. the complete fresh run is benchmarked on the demo laptop before its
    runtime is promised.

## Explicitly deferred and out of scope

- `CausalForestDML`, CATEs, subgroup displays, calibration tests for
  heterogeneity, and policy learning are Stretch or Future and require a fresh
  planning effort.
- DoWhy refuter configurations, negative-control rules, hidden-confounding
  sensitivity benchmarks, Robustness Grades, and Evidence Verdict logic belong
  to the
  [validity verdict contract](validity-verdict-evidence-abstention-contract.md).
- Analysis Run IDs, immutable artifact envelopes, cache keys, file hashes,
  storage paths, and validated-versus-fresh state belong to issue #7.
- DGP acceptance parameters, repetition counts, scientific power, regret
  policies, and walkthrough acceptance belong to issue #13.
- Remote training services, Google Colab, GPU requirements, and auto-tuning
  are outside Core. Core execution is CPU-only inside the same application
  runtime in hosted and local delivery profiles.
- Changing learner parameters after observing an effect is prohibited. A
  future learner change requires a new engine configuration, independent
  validation, and a new Analysis Run.
