# Validity Verdict, Robustness Grade, and Abstention Contract

## Status and authority

This contract records the confirmed decisions for
[Define validity verdicts, evidence grades, and abstention precedence](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/8).
It is planning-only and does not implement the validity service.

The Stage 2 strategy controls product and scientific intent. The exposure,
outcome, and temporal-eligibility contract controls upstream scientific
eligibility and abstention. The executable causal-engine contract controls
estimation outputs and engine failures. The analysis-run and reproducibility
artifact contract controls immutable storage and verification. This contract
owns diagnostic evaluation, Evidence Verdict derivation, Robustness Grade,
causal-language permission, and downstream abstention precedence.

## Core invariants

1. Execution outcome and Evidence Verdict are separate state machines.
2. An engine or artifact-integrity failure has no Evidence Verdict and exposes
   no estimate.
3. A scientific abstention before a valid estimate maps to Insufficient and
   exposes no effect-bearing field.
4. Association Only requires a technically valid estimate whose diagnostics
   prohibit causal interpretation. The adjusted association may remain visible
   only with non-causal wording.
5. Association Only and Insufficient both prohibit causal recommendations.
6. Robustness Grade is a separate diagnostic classification and never
   substitutes for the Evidence Verdict.

## Canonical Evidence Verdict vocabulary

| Stable code | User-facing label |
| --- | --- |
| `SUPPORTED_UNDER_ASSUMPTIONS` | Supported under stated assumptions |
| `TENTATIVE` | Tentative — fragile |
| `ASSOCIATION_ONLY` | Association only |
| `INSUFFICIENT` | Insufficient evidence — abstain |

The label `causally supported` is prohibited because it elides the stated
identification assumptions. An Evidence Verdict is neither probability nor
proof.

## Execution and verdict boundary

| Upstream result | Evidence Verdict | Effect display | Causal use |
| --- | --- | --- | --- |
| Technical, runtime, schema, or integrity `failed` | None | Prohibited | Prohibited |
| Scientific `abstained` before a valid estimate | `INSUFFICIENT` | Prohibited | Prohibited |
| Valid estimate with a causal-validity veto | `ASSOCIATION_ONLY` | Adjusted association only | Prohibited |
| Valid estimate without a causal-validity veto | Derived by the remaining diagnostic rules | Governed by that verdict | Governed by that verdict |

`INSUFFICIENT` has two closed reason classes:

| Reason class | Rule | Effect display |
| --- | --- | --- |
| `NOT_ESTIMABLE` | Scientific abstention occurred before a valid estimate existed. | Prohibited |
| `INCONCLUSIVE` | A valid estimate exists but cannot support a decision under the frozen validity policy. | Estimate and interval shown only with explicit inconclusive wording |

`INCONCLUSIVE` does not become `ASSOCIATION_ONLY`: the former lacks
decision-useful precision or signal, while the latter has a causal-validity
veto.

## Claim scope and source-role permissions

Every validity input and Evidence Verdict preserves the engine's canonical
`intended_role` and exact permitted claim scope. The validity service derives
and stores the role ceilings
`subject_application_role_permitted` and
`decision_support_role_permitted`. It then derives the only downstream action
permission exactly:

```text
decision_support_evaluation_permitted =
    verdict_code == SUPPORTED_UNDER_ASSUMPTIONS
    and decision_support_role_permitted
```

Every downgraded or insufficient verdict therefore stores
`decision_support_evaluation_permitted = false`.

| Intended role | Subject application | Decision Support after a supported verdict |
| --- | --- | --- |
| `semi_synthetic_hero` | Permitted for the disclosed construction-demonstration role | Permitted |
| `out_of_domain_validation` | Prohibited | Prohibited |
| `rejection_vignette` | Prohibited; upstream cannot estimate | Prohibited |

An `out_of_domain_validation` run may receive a Population Verdict for its own
validation population. Every rendered verdict begins exactly:
“Out-of-domain validation only — this result describes
{dataset_display_name}'s validation population and is not a construction effect
claim.” Its only supported-result next step is to report the validation result;
it never enters subject application or Decision Support.

These are the only Core roles. A payload carrying another role, including a
future domain-sample role, fails strict input-schema validation and produces no
Evidence Verdict. `analysis_authorization_ref` is not part of the Core input or
result schema and cannot widen the Dataset Version's intended role. After
upstream validation, a subject payload when
`subject_application_role_permitted` is false, or a downstream request
exceeding the validated claim scope, is an input or artifact-integrity failure
and produces no Evidence Verdict. A scientific verdict never widens the
Dataset Version's intended role.

## Diagnostic status model

Every diagnostic registry entry has exactly one evaluation status:

| Status | Meaning |
| --- | --- |
| `PASS` | The diagnostic executed with valid inputs and met its frozen evaluation rule. |
| `FAIL` | The diagnostic executed with valid inputs and violated its frozen evaluation rule. |
| `UNSUPPORTED` | The diagnostic is scientifically inapplicable or lacks its declared scientific support. |
| `NOT_RUN` | An earlier-precedence result stopped evaluation before this diagnostic executed. |

`UNSUPPORTED` is never an exception path. A runtime exception, malformed result,
missing required artifact, or invalid input is an execution failure and produces
no Evidence Verdict. `NOT_RUN` is not treated as `UNSUPPORTED`, and neither
status may be reported as if a check executed.

## Evaluation policy

Pre-estimation eligibility, cohort-support, or overlap abstention stops
estimation. Every downstream diagnostic that consequently cannot execute is
`NOT_RUN`.

After a valid estimate exists, the service evaluates every applicable
diagnostic even if another diagnostic returns `FAIL` or `UNSUPPORTED`. It
records the complete ordered trigger set and derives the Evidence Verdict only
after evaluation finishes. A post-estimation diagnostic result never hides
another applicable diagnostic or its constructive next step.

## Evidence Verdict precedence

The service applies the following strict severity order:

1. execution or integrity failure: no Evidence Verdict;
2. upstream `NOT_ESTIMABLE`: `INSUFFICIENT`;
3. valid estimate with an inconclusive primary interval: `INSUFFICIENT`;
4. one or more causal-validity vetoes: `ASSOCIATION_ONLY`;
5. no veto and one or more declared fragilities: `TENTATIVE`;
6. all required evidence rules pass: `SUPPORTED_UNDER_ASSUMPTIONS`.

Every trigger remains visible. One trigger becomes the primary explanation
using the frozen trigger-registry order; discovery order, task completion order,
and free-text sorting never affect precedence.

`UNSUPPORTED` has no universal verdict effect. Each diagnostic registry entry
declares whether its unsupported state is a causal-validity veto, a fragility,
or verdict-neutral. That mapping is versioned with the validity policy.

## Verdict scope

Every Evidence Verdict has exactly one scope:

| Scope | Meaning |
| --- | --- |
| `population` | Verdict for the historical cohort and population estimand |
| `subject` | Verdict for applying the population evidence to one supplied current Order Line |

A subject verdict is evaluated whenever permitted subject application is
requested through `SubjectInput` and can never be stronger than its population
verdict. A `scientifically_unavailable` SubjectInput derives subject-level
`INSUFFICIENT` without a `SubjectProfile`; an `eligible` SubjectInput evaluates
its profile's overlap and distribution support. Subject support failure leaves
the population verdict unchanged. The case UI uses the subject verdict; the
audit read model preserves both.

The sole permitted Subject Verdict without a Population Verdict is an unusable
proactive `decision_at` that emitted `PROACTIVE_SUBJECT_INPUT_UNUSABLE` and
explicitly prevented historical-population selection upstream. That Subject
Verdict is `INSUFFICIENT` / `NOT_ESTIMABLE`, has
`population_verdict_ref = null`, exposes no effect, and references the upstream
population-selection abstention. The same subject code caused by another
unusable proposal field still references the Population Verdict when historical
selection completed. No other null Population Verdict reference is valid.

For this ceiling only, verdict strength is ordered:

```text
SUPPORTED_UNDER_ASSUMPTIONS
> TENTATIVE
> ASSOCIATION_ONLY
> INSUFFICIENT
```

This is a permission ordering, not a probability or confidence scale.

When SubjectInput is eligible and both subject overlap and subject distribution
support pass, the Subject Verdict equals the Population Verdict and references
the same Population Verdict, Robustness Grade, effect, and population triggers.
Passing subject gates add applicability evidence but cannot improve the
population result. If any subject input, overlap, or distribution gate fails,
the Subject Verdict is `INSUFFICIENT` / `NOT_ESTIMABLE`, records the applicable
subject triggers, exposes no effect, and leaves the Population Verdict
unchanged.

## Inherited eligibility, overlap, and support outcomes

The validity service does not recompute or reinterpret upstream gates. Each of
these cohort codes maps to population `INSUFFICIENT` with reason class
`NOT_ESTIMABLE`:

```text
SOURCE_SEMANTICS_INELIGIBLE
EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT
CORE_TEMPORAL_COVERAGE_INSUFFICIENT
OUTCOME_COVERAGE_INSUFFICIENT
CANCELLATION_COMPETING_EVENT_PRESENT
COVARIATE_COVERAGE_INSUFFICIENT
COHORT_SUPPORT_INSUFFICIENT
OUTCOME_DEGENERATE
OVERLAP_COHORT_INSUFFICIENT
```

Each of these subject codes maps to subject `INSUFFICIENT` with reason class
`NOT_ESTIMABLE` and leaves the population verdict unchanged:

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
SUBJECT_OVERLAP_INSUFFICIENT
SUBJECT_DISTRIBUTION_UNSUPPORTED
```

Line-level ineligibility remains denominator evidence and affects a verdict only
through its owning frozen cohort or subject gate. Canonical-ingestion rejection,
engine failure, artifact-integrity failure, and unknown or mis-scoped codes
produce no Evidence Verdict.

## Primary interval diagnostic

The primary claim is directional: High-Load Exposure increases Supplier
Milestone Slippage. The engine still supplies its two-sided, supplier-clustered
95% interval.

The interval diagnostic is deterministic:

| Condition | Status | Verdict effect |
| --- | --- | --- |
| `ci_lower > 0` | `PASS` | No downgrade |
| `ci_lower <= 0 <= ci_upper` | `FAIL` | `INSUFFICIENT` with reason class `INCONCLUSIVE` |
| `ci_upper < 0` | `FAIL` | `INSUFFICIENT` with reason class `INCONCLUSIVE`; disclose that evidence points opposite to the proposed delay driver |

Endpoints equal to zero fail because the interval includes the null. The
estimate and interval remain visible under the inconclusive-display rule.
The primary-estimate p-value is a measurement and is not a verdict input.

This validity policy has no universal interval-width or minimum-material-effect
threshold. Practical materiality belongs to downstream Decision Support and
action economics.

## Covariate-balance diagnostic

Balance is evaluated on the primary post-trim `S9_OVERLAP(10)` cohort using the
authoritative mean out-of-fold propensity `p`.

The ATTE weights are:

```text
exposed:   w = 1
unexposed: w = p / (1 - p)
```

Unexposed weights are normalized so their sum equals the exposed-arm row count,
matching the engine comparison contract. For every numeric, binary, one-hot,
and explicit missingness-indicator column in the materialized adjustment
matrix, compute:

```text
absolute_weighted_smd =
    abs(weighted_mean_exposed - weighted_mean_unexposed)
    / sqrt((unweighted_variance_exposed + unweighted_variance_unexposed) / 2)
```

The variances are within-arm sample variances over the unweighted post-trim arm
distributions, with denominator `n - 1` and retained source precision. An arm
with fewer than two rows contradicts the inherited support gate and is an
artifact-integrity failure. If the pooled denominator is zero and the weighted
means are equal, the value is exactly zero. If the pooled denominator is zero
and the weighted means differ, the value is positive infinity and fails.

The diagnostic `PASS`es only when every absolute weighted standardized mean
difference is at most `0.10`. Any value greater than `0.10` is a
causal-validity veto and produces `ASSOCIATION_ONLY`. The result records the
maximum and every offending feature in canonical feature order. No model,
feature, cohort, or threshold may be changed after inspecting balance.

## Refuter estimator identity

Every required refuter re-runs the authoritative primary ATTE recipe on its
declared transformed dataset. It preserves the feature contract, grouped
inference, versioned configuration identity, and evidence lineage.

DoWhy may orchestrate a refutation through an exact-estimator adapter. A
simpler DoWhy estimator, comparison estimator, or separately tuned model cannot
stand in for the primary DoubleML estimate. The only permitted refuter
`UNSUPPORTED` class is a well-formed transformed or restricted simulation that
fails the adapter matrix's declared two-arm or primary support requirement. It
is a causal-validity veto producing `ASSOCIATION_ONLY`. Adapter absence,
unimplemented behavior, exceptions, malformed transformations, invalid fits,
or malformed results are execution failures, not unsupported science.

### Exact refuter-adapter execution matrix

Every simulation starts from the canonical primary `S9_OVERLAP(10)` rows,
ordered features, outcome, exposure, supplier groups, two outer-repeat
assignments, inner calibration assignments, and authoritative propensity
artifacts. Refuters do not rerun ingestion, eligibility, or trimming and never
silently change the target cohort beyond their declared transformation.

| Refuter | Rows and values | Outer and inner splits | Propensity | Outcome nuisances |
| --- | --- | --- | --- | --- |
| `placebo_treatment_within_supplier` | Keep all primary rows, features, outcome, and suppliers; replace exposure only. | Rebuild both outer and inner stratified supplier-grouped splits from transformed exposure using the simulation root and the engine's exact split rules. | Refit and recalibrate on transformed exposure and unchanged features. | Refit both arms against transformed exposure and unchanged outcome. |
| `random_common_cause_standard_normal` | Keep all primary rows, exposure, outcome, and suppliers; append the one generated feature. | Reuse the exact primary outer and inner row assignments. | Refit and recalibrate using the augmented feature matrix. | Refit both arms using the augmented feature matrix. |
| `data_subset_supplier_arm_80pct` | Keep only the declared sampled rows; all retained values are unchanged. | Restrict each exact primary outer and inner assignment to retained rows; never regenerate it. | Refit and recalibrate on the retained rows. | Refit both arms on the retained rows. |
| `dummy_outcome_standard_normal` | Keep all primary rows, features, exposure, and suppliers; replace outcome only. | Reuse the exact primary outer assignments. Inner assignments are not executed. | Reuse the exact primary repeat-specific propensity predictions and their provenance. | Refit both arms against the generated outcome. |

Every refit preserves the primary ATTE score, fixed learners and
hyperparameters, external-prediction construction, supplier-clustered
inference, feature ordering apart from the one declared appended feature, and
sequential execution. No refuter performs a second overlap trim.

Every executed learner uses the applicable engine component seed derived from
that simulation's root. A reused prediction or split retains and references its
primary seed provenance instead. A transformed or restricted split that lacks
the engine's required two-arm training support makes that simulation
scientifically unsupported and makes the complete refuter `UNSUPPORTED`; it is
recorded as such rather than omitted. A malformed transformation, coordinate,
prediction, or provenance reference is an execution failure.

## Refuter Monte Carlo policy

Every stochastic refuter executes exactly `100` simulations. Significance uses
an explicitly selected two-sided empirical bootstrap test with
`alpha = 0.05`; DoWhy's `AUTO` selection is prohibited. A p-value equal to
`0.05` fails.

Execution uses `n_jobs = 1`. Refuter simulation roots use the separate
`sha256-refuter-coordinate-seeds` policy, version `v1`; they do not add an
undeclared component or coordinate to the engine's closed
`sha256-coordinate-seeds.v1` policy.

Encode this base material with `canonical-scientific-json.v1`:

```text
root_seed
dataset_version_id
causal_question_id
causal_question_version
engine_config_id
engine_config_version
suite_id
suite_version
validity_policy_id
validity_policy_version
refuter_adapter_id
refuter_adapter_version
battery_id = core-refuter-battery
battery_version = 1
```

Interpret the first eight bytes of `SHA-256(base_material)` as an unsigned
big-endian 64-bit integer `base`. The battery's canonical refuter order is the
table order below, zero-based. For `simulation_index` in `0..99`:

```text
coordinate_ordinal = refuter_index * 100 + simulation_index
simulation_root_seed = (base + coordinate_ordinal) mod 2^64
```

This yields 400 distinct simulation-root seeds for one battery. The
transformation uses `simulation_root_seed` through a local NumPy
`default_rng`; no process-global RNG is allowed. The exact-estimator adapter
passes the same value as the refit's `root_seed`, after which the engine derives
all split and learner seeds through its unchanged `sha256-coordinate-seeds.v1`
policy and coordinate matrix.

The artifact records the full base material, base digest, refuter ID and index,
simulation index, coordinate ordinal, simulation-root seed, every downstream
engine seed coordinate, transformed-input identity, and exactly 100 simulation
records—not only their aggregate. A `PASS` or `FAIL` refuter has 100 valid
effect results. An `UNSUPPORTED` refuter retains each completed effect plus the
canonical unsupported coordinate and reason. An absent simulation record,
duplicate coordinate or seed, malformed fit, or malformed effect is an
execution failure.

## Required refuter battery

All four refuters are required and use the exact-estimator adapter and Monte
Carlo policy above.

| Refuter ID | Transformation |
| --- | --- |
| `placebo_treatment_within_supplier` | Independently permute the binary exposure within each supplier. Supplier membership, row membership, and each supplier's exposed/unexposed counts remain exact. A single-arm supplier is unchanged. |
| `random_common_cause_standard_normal` | Add one refuter-only covariate drawn independently from `N(0,1)` for every row. The feature appears once and no original feature changes. |
| `data_subset_supplier_arm_80pct` | Within every supplier-by-exposure stratum, sample without replacement exactly `ceil(0.80 * n)` rows. All original rows remain eligible for different simulations; no outcome-dependent resampling is allowed. |
| `dummy_outcome_standard_normal` | Preserve exposure and covariates but replace the continuous outcome with independent `N(0,1)` values in canonical day units. The declared true causal effect is exactly zero. |

Random draws consume each simulation's local generator in a closed order.
Canonical supplier order is first appearance in canonical primary `S9` row
order; rows within a supplier or stratum retain canonical `S9` order. Placebo
permutations scan suppliers in that order. Grouped subsets scan each supplier
with exposure arm `0` before arm `1`, then re-sort retained rows to canonical
`S9` order. Random-common-cause and dummy-outcome transformations draw exactly
one value per canonical row in canonical row order.

The placebo and subset transformations deliberately override DoWhy's global
row permutation and unstratified row subsampling. Their grouped forms preserve
the supplier-clustered design and target estimand. The override is part of the
versioned adapter, not a runtime option.

## Refuter pass and fail rules

The refuter reference target is:

| Refuter | Reference target |
| --- | --- |
| `placebo_treatment_within_supplier` | `0` |
| `dummy_outcome_standard_normal` | `0` |
| `random_common_cause_standard_normal` | Primary ATTE estimate |
| `data_subset_supplier_arm_80pct` | Primary ATTE estimate |

For simulation estimates `x_0..x_99` and the reference target above, reproduce
DoWhy 0.14's two-sided percentile-bootstrap rule explicitly:

```text
half_p =
    (count(x_i > reference_target)
     + 0.5 * count(x_i == reference_target))
    / 100
p_value = 2 * min(half_p, 1 - half_p)
```

Comparisons use the stored float64 estimates and target without display
rounding. Compute the median from the 100 estimates sorted numerically; for this
even count it is the arithmetic mean at zero-based sorted indices `49` and
`50` (one-based positions 50 and 51). The refuter `PASS`es only when both
conditions hold:

```text
p_value > 0.05
abs(median_simulation_estimate - reference_target)
    <= primary_atte_standard_error
```

Equality at one primary standard error passes. A p-value equal to `0.05`
fails. Any failed required refuter is a causal-validity veto and produces
`ASSOCIATION_ONLY`. A scientifically unsupported required refuter has the same
verdict effect. An invalid computation is an execution failure and produces no
Evidence Verdict.

## Negative-control outcome eligibility

Every dataset manifest names exactly one reviewed negative-control outcome. It
is eligible only when all of these hold:

1. its value and semantics were fixed strictly before the High-Load Exposure
   cutoff;
2. the reviewed causal graph contains no directed path from exposure to the
   control outcome;
3. it does not participate in exposure, eligibility, adjustment-set,
   subject-support, or primary-outcome derivation;
4. its provenance and temporal meaning are verified from source semantics and
   are not inferred from a field name; and
5. over frozen primary `S9_OVERLAP(10)`, valid finite control values cover at
   least `95%` of all rows and at least `90%` of each exposure arm, and the
   absolute difference between exposed- and unexposed-arm observation rates is
   at most `0.05`.

There is no inferred or generic fallback. Contracted unit price is eligible
only when reviewed quote and price chronology proves all five requirements.
An absent, ambiguous, post-exposure, causally reachable, or inadequately covered
control is `UNSUPPORTED`, is a causal-validity veto, and produces
`ASSOCIATION_ONLY`.

## Negative-control outcome test

After the declared coverage gate passes, materialize
`S9_NEGATIVE_CONTROL_PRESENT` as the canonical-order subset of primary
`S9_OVERLAP(10)` rows whose reviewed negative-control value is valid and
finite. No row is imputed. Standardize over this frozen present-control
subcohort to mean `0` and population standard deviation `1`. A zero or
non-finite standard deviation makes the diagnostic `UNSUPPORTED`.

The negative-control adapter then:

1. restricts each exact primary outer-fold assignment to the frozen subcohort;
2. requires the subcohort to satisfy the primary treatment-arm, total-row,
   supplier, mixed-supplier, and clustered-inference support invariants and
   every restricted training partition to retain both exposure arms;
3. reuses the exact primary repeat-specific authoritative propensity
   predictions and provenance for retained rows, with no refit or second trim;
4. refits both outcome nuisances on the restricted training rows using the
   primary outcome-learner seed coordinates and all other fixed learner
   settings; and
5. fits the primary ATTE score with supplier-clustered inference on the
   subcohort.

Subcohort or split support failure makes the diagnostic `UNSUPPORTED`. Any
unregistered row drop, imputation, regenerated split, propensity change,
malformed value, or provenance mismatch is an execution or artifact-integrity
failure. The equivalence region is closed:

```text
[-0.10, +0.10] standard deviations
```

The negative-control diagnostic `PASS`es only when its complete two-sided 95%
interval lies inside that region. An endpoint equal to `-0.10` or `+0.10`
passes. Any wider or displaced valid interval `FAIL`s. Both `FAIL` and
`UNSUPPORTED` are causal-validity vetoes producing `ASSOCIATION_ONLY`.
P-values are recorded measurements and are not used for this test.

## Same-estimand specification stability

The stability comparison includes only the primary ATTE and these
continuous-slippage, binary-exposure variants:

```text
sensitivity_stricter_atte_slippage
sensitivity_short_history_atte_slippage
sensitivity_long_history_atte_slippage
```

For each estimated variant:

```text
compatibility_z =
    abs(variant_estimate - primary_estimate)
    / sqrt(variant_standard_error^2 + primary_standard_error^2)
```

The complete diagnostic result is:

| Condition | Status | Verdict effect |
| --- | --- | --- |
| Any variant point estimate is `<= 0` | `FAIL` | Causal-validity veto: `ASSOCIATION_ONLY` |
| All estimated variant effects are positive, but any `compatibility_z > 1.96` | `FAIL` | Fragility: `TENTATIVE` |
| Any variant has a permitted scientific `UNSUPPORTED` state | `UNSUPPORTED` unless a simultaneous reversal makes the aggregate status `FAIL` | Incomplete stability evidence: `TENTATIVE`; retain this trigger even when a reversal controls the final verdict |
| All three variants are estimated and positive, and every `compatibility_z <= 1.96` | `PASS` | No downgrade |

Equality at zero is a reversal; equality at `1.96` passes. The binary-late
outcome and continuous-load sensitivities are excluded from magnitude
compatibility because their outcome or exposure units differ.

## Cross-form directional stability

The binary-late and continuous-load sensitivities are evaluated only for
direction, not magnitude.

| Sensitivity result | Status | Verdict effect |
| --- | --- | --- |
| Two-sided 95% interval lies entirely above zero | `PASS` | No downgrade |
| Point estimate is positive and the interval includes zero | `FAIL` | Fragility: `TENTATIVE` |
| Point estimate is `<= 0` | `FAIL` | Causal-validity veto: `ASSOCIATION_ONLY` |

The binary-late sensitivity's permitted scientific `UNSUPPORTED` state means
incomplete directional evidence and produces `TENTATIVE`. The continuous-load
sensitivity has no permitted unsupported state; invalid execution is an engine
failure and produces no Evidence Verdict.

## Comparison-estimator triangulation

The naive mean difference is reported for pedagogy but is verdict-neutral
because adjustment may legitimately change it.

Direction-only triangulation uses:

```text
covariate_ols
normalized_ipw_atte
supplier_fe_ols
```

| Condition | Status | Verdict effect |
| --- | --- | --- |
| All three point estimates are `> 0` | `PASS` | No downgrade |
| One or two point estimates are `<= 0` | `FAIL` | Model-dependence fragility: `TENTATIVE` |
| All three point estimates are `<= 0` while primary DML is positive | `FAIL` | Causal-validity veto: `ASSOCIATION_ONLY` |

Magnitude compatibility is prohibited because the comparison estimators do not
all target exactly the same estimand. The engine contract already makes an
invalid or unidentified comparison an execution failure.

## Hidden-confounding benchmark construction

The dataset's reviewed adjustment-set manifest pre-marks one or more canonical
covariate groups as sensitivity-benchmark eligible. A group contains all
materialized value columns, category indicators, and missingness indicators
owned by that canonical covariate. The selection is frozen before an effect is
inspected.

For every eligible group, execute DoubleML 0.11.3
`sensitivity_benchmark()` with that complete group as `benchmarking_set`.
The short-form refit preserves the original cohort, folds, seed policy,
learners, hyperparameters, inference, and every other configuration value.

Evaluate the returned `cf_y`, `cf_d`, and `rho` using
`sensitivity_analysis()` with:

```text
level = 0.95
null_hypothesis = 0
```

Rank valid groups by adverse impact on the positive claim: the group with the
lowest sensitivity-adjusted lower confidence bound is strongest. Ties use
canonical covariate order. No eligible valid group yields Robustness Grade
`UNAVAILABLE`; no group is inferred or substituted after results are seen.

## Robustness Grade

Sort valid benchmark groups from most to least adverse. For `n` groups, the
median benchmark is the zero-based index `floor((n - 1) / 2)`; this selects the
more adverse middle group when `n` is even.

| Grade | Exact rule | Verdict effect |
| --- | --- | --- |
| `STRONG` | The strongest benchmark's sensitivity-adjusted 95% lower bound is `> 0`. | No downgrade |
| `MODERATE` | The strongest bound is `<= 0`, but the median benchmark's bound is `> 0`. | Fragility: `TENTATIVE` |
| `WEAK` | The median benchmark's bound is `<= 0`. | Causal-validity veto: `ASSOCIATION_ONLY` |
| `UNAVAILABLE` | A scientifically `NOT_ESTIMABLE` run has no primary estimate, or a valid estimate has no eligible valid benchmark. | With a valid estimate: `ASSOCIATION_ONLY`; with upstream `NOT_ESTIMABLE`: `INSUFFICIENT`; execution or integrity failure still produces no grade and no verdict |

The Robustness Grade measures only benchmark-relative hidden-confounding
sensitivity. Overlap, balance, refuters, negative controls, and specification
stability remain separate Diagnostic Results. Leave-one-supplier-out analysis
is not silently added to Core or to this grade.

## Repeat stability

The two repeat-specific primary ATTE results already required by the engine are
the complete Core fold-and-seed stability input. No additional ad hoc rerun is
added.

```text
repeat_compatibility_z =
    abs(repeat_1_estimate - repeat_2_estimate)
    / sqrt(repeat_1_standard_error^2 + repeat_2_standard_error^2)
```

| Condition | Status | Verdict effect |
| --- | --- | --- |
| Either repeat point estimate is `<= 0` | `FAIL` | Causal-validity veto: `ASSOCIATION_ONLY` |
| Both repeat estimates are positive, but `repeat_compatibility_z > 1.96` | `FAIL` | Fragility: `TENTATIVE` |
| Both repeat estimates are positive and `repeat_compatibility_z <= 1.96` | `PASS` | No downgrade |

Equality at `1.96` passes.

## Constructive next-step policy

Every trigger code maps to one closed, versioned next-step template. There is no
free-text fallback.

Templates may interpolate only sanitized aggregate facts already present in the
verified evidence bundle. Quantitative advice is allowed only when the exact
deficit is derivable from a frozen threshold and denominator. The service never
converts a row, supplier, coverage, or support deficit into elapsed time unless
the dataset manifest defines and supports that conversion.

A next step recommends evidence collection, semantic review, data repair, or
investigation. It never recommends or authorizes an operational Intervention
Option. The primary trigger's next step appears first; secondary trigger steps
remain accessible in registry order.

Optional Gemini wording may paraphrase only the template's allowed facts. The
deterministic offline renderer remains authoritative. An unknown trigger,
missing required template, disallowed interpolation, or unregistered output is
an integrity failure and produces no Evidence Verdict.

## Closed trigger registry

The final verdict class selects the applicable table below. The numeric ranges
encode verdict precedence, so all active triggers across all tables are sorted
by numeric priority. The first active trigger in the final verdict's class is
primary; every other active trigger remains an ordered secondary trigger even
when it belongs to a lower-precedence class. Discovery order and asynchronous
completion never affect this selection.

### Insufficient

| Priority | Trigger code | Condition | Deterministic next step |
| ---: | --- | --- | --- |
| 100 | `SOURCE_SEMANTICS_INELIGIBLE` | Inherited cohort code | Review and approve the source-to-estimand mapping before any new run; do not infer semantics from field names. |
| 110 | `EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT` | Inherited cohort code | Repair verifiable load-snapshot coverage for the reported overall and supplier deficits, then create a new Dataset Version. |
| 120 | `CORE_TEMPORAL_COVERAGE_INSUFFICIENT` | Inherited cohort code | Repair commitment and frozen-promise chronology for the reported deficits; later-known promises cannot fill the gap. |
| 130 | `CANCELLATION_COMPETING_EVENT_PRESENT` | Inherited cohort code | Specify and review a competing-event estimand; the current continuous-slippage estimand must remain abstained. |
| 140 | `OUTCOME_COVERAGE_INSUFFICIENT` | Inherited cohort code | Add verified supplier-controlled actual milestones for the exact reported coverage deficits, then create a new Dataset Version. |
| 150 | `COVARIATE_COVERAGE_INSUFFICIENT` | Inherited cohort code | Improve the pre-treatment covariate records that miss their frozen coverage rules; do not remove a confounder after seeing results. |
| 160 | `COHORT_SUPPORT_INSUFFICIENT` | Inherited cohort code | Add the exact reported eligible-line, arm, supplier, or mixed-supplier deficit; do not loosen the support threshold. |
| 170 | `OUTCOME_DEGENERATE` | Inherited cohort code | Use a newly pre-registered eligible observation window with genuine outcome variation; never add jitter or outcome-selected exclusions. |
| 180 | `OVERLAP_COHORT_INSUFFICIENT` | Inherited cohort code | Collect comparable exposed and unexposed orders for the reported deficient support; do not move the propensity threshold or retune for the result. |
| 190 | `PROACTIVE_SUBJECT_INPUT_UNUSABLE` | Inherited subject code | Complete or verify the subject's pre-cutoff supplier, promise, and covariate inputs before applying population evidence. |
| 191 | `COMMITMENT_CUTOFF_UNUSABLE` | Inherited subject code | Repair and verify the subject's decision-time cutoff and source chronology; later-known values cannot backfill the cutoff. |
| 192 | `TARGET_MILESTONE_UNSUPPORTED` | Inherited subject code | Select a reviewed supplier-controlled milestone supported by source semantics; do not infer eligibility from a field name. |
| 193 | `LOAD_SNAPSHOT_UNRESOLVABLE` | Inherited subject code | Resolve every material open-line membership comparison using information known by the cutoff; do not guess unresolved membership. |
| 194 | `SUPPLIER_HISTORY_INSUFFICIENT` | Inherited subject code | Add the exact reported deficit of valid prior supplier snapshots; do not lower the frozen history threshold. |
| 195 | `FROZEN_PROMISE_UNAVAILABLE` | Inherited subject code | Establish a source-verified target promise known by commitment; a later-known promise cannot replace it. |
| 196 | `FROZEN_PROMISE_CONFLICT` | Inherited subject code | Reconcile the promise provenance chain and publish a new Dataset Version; do not choose the favorable promise. |
| 197 | `FROZEN_PROMISE_TEMPORALLY_INVALID` | Inherited subject code | Repair the promise and cutoff chronology so the frozen baseline is safely comparable at decision time. |
| 198 | `COVARIATE_TEMPORAL_LEAKAGE` | Inherited subject code | Pre-register a strictly pre-treatment covariate derivation and execute a new run; do not use later-known values. |
| 199 | `REQUIRED_COVARIATE_UNUSABLE` | Inherited subject code | Repair the required pre-treatment covariate or its declared missingness handling; do not drop it after seeing results. |
| 200 | `SUBJECT_OVERLAP_INSUFFICIENT` | Inherited subject code | Do not apply the population effect to this order; collect comparable historical cases or use the non-causal risk workflow. |
| 210 | `SUBJECT_DISTRIBUTION_UNSUPPORTED` | Inherited subject code | Do not apply the population effect to this order; add comparable two-arm history for the reported unsupported profile. |
| 220 | `PRIMARY_INTERVAL_INCLUDES_NULL` | `ci_lower <= 0 <= ci_upper` | Treat congestion as an unconfirmed delay driver; gather additional eligible evidence or investigate another pre-specified driver. |
| 230 | `PRIMARY_EFFECT_OPPOSITE_DIRECTION` | `ci_upper < 0` | Do not recommend a congestion-targeted action; review the causal question and investigate an alternative driver or protective mechanism. |

### Association only

| Priority | Trigger code | Condition | Deterministic next step |
| ---: | --- | --- | --- |
| 300 | `COVARIATE_BALANCE_FAILED` | Any absolute weighted SMD is `> 0.10` | Pre-register a revised graph, adjustment set, or propensity specification using separate evidence, then execute a new run; never repair this run after seeing balance. |
| 310 | `NEGATIVE_CONTROL_UNSUPPORTED` | No eligible, non-degenerate reviewed control | Add a provenance-verified pre-exposure negative-control outcome or narrow the causal claim. |
| 320 | `NEGATIVE_CONTROL_FAILED` | Its 95% interval is not wholly within `[-0.10, 0.10]` SD | Review residual confounding, temporal semantics, and the causal graph before making a causal claim. |
| 330 | `PLACEBO_REFUTER_UNSUPPORTED` | The exact transformed placebo fit lacks scientific support | Add the reported grouped support or narrow the claim; do not substitute a proxy estimator. |
| 340 | `PLACEBO_REFUTER_FAILED` | Placebo pass rule fails | Investigate exposure construction, estimator calibration, and residual structure before a new policy-version run. |
| 350 | `DUMMY_OUTCOME_REFUTER_UNSUPPORTED` | The exact transformed dummy-outcome fit lacks scientific support | Add the reported scientific support or narrow the claim; do not substitute a proxy estimator. |
| 360 | `DUMMY_OUTCOME_REFUTER_FAILED` | Dummy-outcome pass rule fails | Investigate estimator calibration and false-effect behavior before a new policy-version run. |
| 370 | `RANDOM_COMMON_CAUSE_REFUTER_UNSUPPORTED` | The exact transformed random-common-cause fit lacks scientific support | Add the reported scientific support or narrow the claim; do not substitute a proxy estimator. |
| 380 | `RANDOM_COMMON_CAUSE_REFUTER_FAILED` | Random-common-cause pass rule fails | Review estimator instability and adjustment behavior before a new policy-version run. |
| 390 | `DATA_SUBSET_REFUTER_UNSUPPORTED` | The exact grouped subset lacks scientific support | Add sufficient grouped support; do not fall back to unclustered row sampling. |
| 400 | `DATA_SUBSET_REFUTER_FAILED` | Grouped-subset pass rule fails | Review supplier concentration and subset instability; add eligible supplier support before rerunning. |
| 410 | `SPECIFICATION_DIRECTION_REVERSED` | Any same-estimand variant estimate is `<= 0` | Revisit and domain-review the exposure threshold and history definition; do not select the favorable specification. |
| 420 | `CROSS_FORM_DIRECTION_REVERSED` | Binary-late or continuous-load estimate is `<= 0` | Review whether the alternate exposure or outcome represents the same causal story before retaining the driver claim. |
| 430 | `REPEAT_DIRECTION_UNSTABLE` | Either repeat estimate is `<= 0` | Inspect grouped-fold sensitivity and add support if needed; do not select or retry seeds for a favorable sign. |
| 440 | `ROBUSTNESS_WEAK` | Median benchmark adjusted lower bound is `<= 0` | Measure the plausible omitted-confounder proxies represented by the adverse benchmarks or revise the graph before a causal claim. |
| 450 | `ROBUSTNESS_UNAVAILABLE` | Valid estimate but no eligible valid benchmark | Register and collect reviewed benchmark covariates before assigning hidden-confounding robustness. |
| 460 | `COMPARISON_ONLY_COMPLEX_SUPPORT` | All three adjusted comparison estimates are `<= 0` | Review model dependence, adjustment choices, and estimand alignment before relying on the primary DML result. |

### Tentative

| Priority | Trigger code | Condition | Deterministic next step |
| ---: | --- | --- | --- |
| 500 | `SPECIFICATION_MAGNITUDE_DIVERGENT` | Same-estimand `compatibility_z > 1.96` without reversal | Investigate threshold and history sensitivity before using the magnitude for decision support. |
| 510 | `SPECIFICATION_VARIANT_UNSUPPORTED` | A same-estimand variant has permitted `UNSUPPORTED` | Add the exact missing coverage or support for that pre-registered variant before strengthening the claim. |
| 520 | `CROSS_FORM_INTERVAL_INCLUDES_NULL` | Alternate-form point estimate is positive but its interval includes zero | Add support for the alternate exposure or outcome form before strengthening the claim. |
| 530 | `BINARY_LATE_SENSITIVITY_UNSUPPORTED` | The late-risk variant lacks frozen 50/50 outcome support | Add the exact late or non-late deficit before relying on outcome-form stability. |
| 540 | `REPEAT_MAGNITUDE_DIVERGENT` | Repeat `compatibility_z > 1.96` without reversal | Review grouped-fold instability and add supplier support; do not seed-shop or average away the disagreement. |
| 550 | `ROBUSTNESS_MODERATE` | Median benchmark survives but strongest does not | Measure or control the strongest credible observed-confounder analogue before strengthening the claim. |
| 560 | `COMPARISON_DIRECTION_MIXED` | One or two adjusted comparison estimates are `<= 0` | Review model dependence and estimand differences; keep the claim tentative until the disagreement is explained. |

### Supported under stated assumptions

When no trigger above is active and every required diagnostic passes, emit
`EVIDENCE_POLICY_PASSED`. The ordered trigger list is exactly
`[EVIDENCE_POLICY_PASSED]`, and that success sentinel is the primary trigger.
When
`decision_support_evaluation_permitted=true`, its next step is: evaluate
eligible Intervention Options under the separate Decision Support contract.
Otherwise its next step is: report the result within the recorded claim scope;
Decision Support is prohibited. It neither recommends nor authorizes an action
by itself.

## Language and downstream-use permissions

`primary_trigger_label` is rendered deterministically from the registered
trigger code by replacing underscores with single spaces and applying lowercase
ASCII. It is never model-generated, and the code remains visible in progressive
disclosure.

| Evidence Verdict | Permitted evidence language | Downstream use |
| --- | --- | --- |
| `SUPPORTED_UNDER_ASSUMPTIONS` | “High-Load Exposure is estimated to increase Supplier Milestone Slippage by {estimate} {unit} ({interval_level} interval {lower} to {upper}), under the stated assumptions.” | Decision Support may evaluate an eligible Intervention Option only when `decision_support_evaluation_permitted=true`, under its own constraints and assumptions. This verdict does not recommend or authorize one. |
| `TENTATIVE` | “Evidence suggests a possible increase, but it is fragile because {primary_trigger_label}.” | Investigation only. A driver-based Action Recommendation is prohibited. |
| `ASSOCIATION_ONLY` | “The adjusted association is {estimate} {unit} ({interval_level} interval {lower} to {upper}); causal interpretation is not supported because {primary_trigger_label}.” | All causal verbs and driver-linked Action Recommendations are prohibited. A separately governed non-causal risk workflow may continue. |
| `INSUFFICIENT` | “The proposed driver is not supported for this {scope} because {primary_trigger_label}.” | A driver-based Action Recommendation is prohibited. `NOT_ESTIMABLE` exposes no effect field; `INCONCLUSIVE` may append the estimate and interval only with explicit inconclusive wording. |

For `INCONCLUSIVE`, the appendage is also closed:

- `PRIMARY_INTERVAL_INCLUDES_NULL`: “The estimate is {estimate} {unit}; its
  two-sided 95% interval, {lower} to {upper}, includes zero, so the proposed
  increase is inconclusive.”
- `PRIMARY_EFFECT_OPPOSITE_DIRECTION`: “The estimate is {estimate} {unit}; its
  two-sided 95% interval, {lower} to {upper}, lies below zero and points
  opposite to the proposed delay-driver direction.”

All interpolated values come from the verified read model. The renderer cannot
change verbs, omit “under the stated assumptions,” convert Association Only
into causal wording, or imply that an Evidence Verdict authorizes action.

## Versioned policy and record contracts

The following identifiers are fixed for Core:

| Contract | Identifier | Version |
| --- | --- | --- |
| Verdict policy | `causal-validity-verdict-policy` | `1` |
| Diagnostic result schema | `diagnostic-result` | `1` |
| Evidence Verdict schema | `evidence-verdict` | `2` |
| Robustness Grade schema | `robustness-grade` | `1` |
| Trigger registry | `validity-trigger-registry` | `1` |
| Next-step template registry | `validity-next-step-templates` | `1` |
| Exact refuter adapter | `exact-doubleml-dowhy-refuter-adapter` | `1` |
| Refuter seed policy | `sha256-refuter-coordinate-seeds` | `v1` |

An unknown identifier or unsupported version is an artifact-integrity failure.
It produces no Evidence Verdict.

### Diagnostic Result

Every required or applicable diagnostic emits one structured record containing:

- `diagnostic_id` and `diagnostic_version`;
- `scope`;
- `status`;
- `rule_id` and `rule_version`;
- typed `observed` facts and typed `threshold` facts;
- `verdict_effect`, exactly one of `NONE`, `FRAGILITY`, `VETO`, or
  `INSUFFICIENT`;
- an ordered list of trigger codes; and
- evidence references to inputs, fit artifacts, and derived results.

`NOT_RUN` additionally records the upstream short-circuit trigger and has no
observed result. `UNSUPPORTED` records the scientific support deficit. Neither
status accepts technical exception text as evidence.

### Robustness Grade result

The Robustness Grade record contains the grade, ordered benchmark-group
references, strongest and median group references, their adjusted interval
bounds, the sensitivity method and configuration references, and evidence
references. It contains no overlap, refuter, repeat, or leave-one-supplier-out
result.

### Evidence Verdict result

Every Evidence Verdict record contains:

- `scope`, verdict code, and nullable insufficient-evidence reason class;
- `intended_role`, exact permitted claim scope,
  `subject_application_role_permitted`,
  `decision_support_role_permitted`, and the final
  `decision_support_evaluation_permitted`;
- for a Subject Verdict, its Population Verdict reference, nullable only for
  the closed unusable-proactive-`decision_at` case above;
- engine and artifact-integrity status references;
- a nullable Robustness Grade reference;
- `effect_display`, exactly one of `NONE`, `INCONCLUSIVE_ESTIMATE`,
  `ADJUSTED_ASSOCIATION`, or `CAUSAL_ESTIMATE`;
- when `effect_display != NONE`, the exact engine effect-result reference/hash,
  canonical unit, and `canonical_slippage_duration_basis`; the basis is exactly
  `CALENDAR_DAY` or `ELAPSED_86400_SECOND_DAY` for every slippage-day effect and
  must match the sealed `causal-engine-suite-request.v2` and result;
- the primary trigger, complete ordered trigger list, and deterministic
  next-step template identifiers;
- the language-policy identifier; and
- evidence references.

The record contains no generated free text. Rendering is a separate,
deterministic projection of the versioned language and next-step registries.
For slippage effects, `{unit}` renders exactly `calendar days` for
`CALENDAR_DAY` or `elapsed 86,400-second days` for
`ELAPSED_86400_SECOND_DAY`. A missing or mismatched required basis is artifact
integrity failure and produces no Evidence Verdict; no renderer supplies one.

## Minimum conformance cases

An implementation of this contract must prove at least these cases:

1. execution failure produces no Evidence Verdict or effect;
2. upstream `NOT_ESTIMABLE` produces Insufficient with no effect;
3. a valid positive estimate whose primary interval includes zero produces
   Insufficient / `INCONCLUSIVE` with the estimate visible;
4. a valid negative estimate and interval produce Insufficient /
   `INCONCLUSIVE` with opposite-direction wording;
5. a positive conclusive estimate plus one causal veto produces Association
   Only;
6. a positive conclusive estimate plus one fragility trigger produces
   Tentative;
7. all required diagnostics passing produces Supported under stated
   assumptions;
8. simultaneous fragility and veto triggers retain both and select Association
   Only;
9. multiple same-class triggers choose the registry's lowest numeric priority;
10. a balance SMD exactly `0.10` passes, a value just above it fails, and the
    sample-variance and zero-denominator rules are reproduced exactly;
11. every permitted reactive or proactive SubjectInput-unavailable code
    produces subject Insufficient / `NOT_ESTIMABLE` with no effect;
12. an unusable proactive `decision_at` produces the sole permitted Subject
    Verdict with a null Population Verdict reference;
13. an eligible subject passing both support gates inherits the Population
    Verdict, while subject-only support failure leaves the Population Verdict
    unchanged;
14. the four-refuter battery derives exactly 400 unique, replay-stable
    simulation-root coordinates and seeds without extending the engine seed
    registry;
15. each refuter proves its exact cohort, split, propensity, and outcome-nuisance
    reuse-or-refit rule, with no undeclared retrimming;
16. each grouped or row-wise refuter transformation consumes random draws in
    the canonical order and reproduces an identical transformed-input digest;
17. the percentile-bootstrap p-value reproduces the strict-greater and
    half-weighted-equality counts, and the even-sample median uses zero-based
    sorted indices `49` and `50`;
18. `p = 0.05` fails a refuter while `p > 0.05` still requires the median-shift
    rule;
19. negative-control coverage uses frozen primary `S9` as the overall and
    per-arm denominator, including the closed arm-gap boundary;
20. a partially missing but coverage-eligible negative control whose present
    subcohort fails a primary support invariant is `UNSUPPORTED`;
21. a supported partially missing negative control uses only its frozen
    present-value subcohort with the exact restriction and reuse rules;
22. a negative-control interval exactly on both equivalence-band endpoints
    passes;
23. a comparison-estimator disagreement cannot improve a verdict;
24. an out-of-domain validation run can receive only a qualified Population
    Verdict and cannot enter subject application or Decision Support;
25. an `intended_role` outside the three canonical Core values fails strict
    input-schema validation and produces no verdict;
26. every Tentative, Association Only, or Insufficient result stores
    `decision_support_evaluation_permitted=false` even when its role ceiling
    would allow evaluation after a supported verdict;
27. a legacy payload containing `analysis_authorization_ref` fails strict
    input-schema validation and produces no verdict;
28. a fully passing result stores `[EVIDENCE_POLICY_PASSED]` as its complete
    ordered trigger list;
29. an unknown policy identifier or version produces an integrity failure and
    no verdict; and
30. optional Gemini paraphrasing cannot change a verdict, trigger, numeric
    fact, causal permission, or deterministic next step; and
31. every effect-bearing slippage Verdict preserves the exact matching
    request/result `canonical_slippage_duration_basis`, renders its closed unit
    label, and rejects a missing or mismatched basis as artifact-integrity
    failure.
