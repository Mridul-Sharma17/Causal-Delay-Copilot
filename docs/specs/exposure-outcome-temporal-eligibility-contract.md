# Exposure, Outcome, and Temporal-Eligibility Contract

## Status and authority

This specification resolves the deterministic computation and pre-estimation
eligibility decisions for the Core supplier-congestion estimand.

It is subordinate to:

- `docs/causal_delay_copilot_stage2_strategy.md` for product and scientific
  intent; and
- `docs/specs/canonical-order-event-lineage-contract.md` for canonical records,
  clocks, missingness states, lineage, corrections, and validation.

If those sources disagree, the Stage 2 strategy controls intent and the
canonical lineage contract controls what source facts may be used. This
specification does not define serialized analysis artifacts, estimator
execution, post-estimation validity grades, APIs, storage, or UI presentation.
Those remain with downstream decisions.

## Core invariants

1. The Order Line is the analysis unit and the counted load unit.
2. Every run fixes one target milestone kind: `supplier_completion` or
   `supplier_handoff`. Customer delivery and `other` are never relabelled.
3. Historical and reactive lines use commitment occurrence as the decision
   cutoff. A proactive proposed subject uses its pre-award hook's frozen
   decision timestamp without fabricating a commitment event.
4. Point-in-time inputs use facts known by the applicable cutoff. Occurrence or
   ingestion time is never substituted for missing knowledge time.
5. History is strictly expanding. The subject and same-time commitments never
   enter their own history.
6. Exposure, outcome, and eligibility are derived facts. They never overwrite
   canonical source records or events.
7. Missing, invalid, ambiguous, censored, or unsupported facts are never
   guessed, coerced to zero, or silently dropped.
8. A current subject profile is separate from the historical estimation
   cohort and is never inserted into its own estimator input.
9. Every exclusion has stable codes, counts, and evidence pointers.
10. A cohort-level gate failure emits no treatment-effect estimate. A
    line-level failure excludes only that line, subject to the coverage and
    support gates; a subject-level failure abstains only for that subject.

## Frozen run inputs

Before any derived value is inspected, a run fixes the following logical
inputs:

- immutable `dataset_version_id`;
- canonical `intended_role`;
- versioned, outcome-independent estimator-window selector, its applicable
  source/time bounds, and a hash of the selected Order Line identities;
- versioned, outcome-independent history-lookback selector, its applicable
  source/time bounds, and a hash of the selected Order Line identities;
- target supplier milestone kind;
- trigger mode (`historical`, `reactive`, or `proactive`);
- observation cutoff;
- dataset-specific follow-up horizon;
- primary threshold rule and all sensitivity variants;
- dataset-specific adjustment set and missingness encodings;
- dataset timezone assumptions, if any;
- domain plausibility bounds, if any; and
- versioned propensity specification, including algorithm and dependency
  versions, feature preprocessing, hyperparameters or outcome-blind tuning
  procedure, fold assignment, repeat count, seeds, calibration, and the
  subject-scoring ensemble rule; and
- all coverage, sample-support, overlap, and subject-support thresholds in this
  contract.

The later analysis-artifact contract owns their physical representation. A run
must not change any frozen input after exposure or outcome results are seen.
The history selector must use the same dataset version, include the estimator
window before subject-role removal, and may extend only backward to supply
prior history. Neither selector may inspect exposure, promise validity,
covariates, outcome availability/value, treatment-effect results, or later
eligibility codes. If a time-bounded selector cannot classify a record because
its selection clock is non-present, that indeterminate membership and its
disposition must be fixed by the selector version rather than silently
dropping the record.

## Temporal comparison

Temporal values are comparable only when the canonical lineage contract can
establish their ordering at their retained precision.

- Date/date comparisons use calendar dates.
- Compatible local datetimes or instants use their normalized timeline.
- A versioned dataset-level timezone assumption is allowed and remains visible
  in provenance.
- Unknown timezone, incompatible temporal kinds, or insufficient precision
  makes a comparison unresolved when the ambiguity could change a result.
- No rule manufactures midnight, UTC, or an event order.

For an exact comparable timestamp, intervals are half-open: an Order Line is
open from commitment inclusive until its target milestone or cancellation
exclusive.

## Supplier Load Snapshot

### Decision cutoff

For a historical or reactive Order Line `i`, resolve all canonical
`committed` events in the frozen dataset version:

1. the correction/supersession graph must be valid;
2. exactly one unsuperseded `committed` event must remain;
3. its `occurred_at` and `known_at` must be present and comparable; and
4. `known_at <= occurred_at`.

Let `t_i` be that event's `occurred_at`. Zero or multiple heads, an invalid
chain, a later-known correction of the cutoff, or an unavailable clock emits
`COMMITMENT_CUTOFF_UNUSABLE`.

For a proactive proposed subject, let `t_i` be the pre-award hook's frozen
`decision_at`. The proposal must provide a usable dataset-scoped supplier,
target milestone, proposed original promise, and adjustment-set inputs known
by `decision_at`. It remains outside the canonical dataset, does not create a
`committed` event, and never contributes to its own load or history. Missing,
unmapped, or late-known proposal inputs emit
`PROACTIVE_SUBJECT_INPUT_UNUSABLE`. The result is labelled provisional and is
recomputed if the eventual commitment changes the supplier, promise,
covariates, or decision time.

The proactive computation is a preview, not a canonical Supplier Load Snapshot
or High-Load Exposure. Its logical fields are
`provisional_concurrent_load_count`, `provisional_load_percentile`, and
`provisional_high_load_preview`. Canonical facts are derived only after a real
Order Line commitment and a fresh computation.

### Open-line predicate

Another canonical Order Line `j` contributes one unit to the canonical
subject's Supplier Load Snapshot, or to the proactive subject's preview count,
only when all of the following are true:

1. `j.supplier_id` equals the canonical or proposed subject supplier;
2. for a canonical subject, `j.order_line_id != i.order_line_id`; a proactive
   proposal is external to the dataset and therefore cannot equal `j`;
3. `j` has a usable commitment that occurred strictly before `t_i` and was
   known by `t_i`;
4. as of facts known by `t_i`, no reached event for the run's target supplier
   milestone occurred at or before `t_i`; and
5. as of facts known by `t_i`, no reliable cancellation occurred at or before
   `t_i`.

Corrections and supersessions affect this predicate only when they were known
by `t_i`. Later-known facts never rewrite the point-in-time snapshot. Promise
events, promise revisions, customer-delivery events, and milestones of another
kind do not close the line.

A closure exactly at `t_i` means closed. A commitment exactly at `t_i` is not
previously placed and does not count. If an ambiguity could change membership,
the subject receives `LOAD_SNAPSHOT_UNRESOLVABLE`; the implementation must not
choose a favourable bound.

For a canonical subject, `concurrent_load_count` is the count of distinct Order
Lines satisfying this predicate. For a proactive proposal, the identical
calculation is named `provisional_concurrent_load_count`.

## Expanding supplier history and treatment

### Valid history

The expanding history for the canonical or proposed subject contains the
`concurrent_load_count` from each same-supplier canonical Order Line whose
commitment is strictly earlier than `t_i` and whose own load snapshot was
resolvable at its own commitment.

A prior load snapshot remains in history even if that prior line later fails a
promise, outcome, covariate, follow-up, or estimation-cohort rule. Removing it
would select the exposure threshold on later analyzability. Same-time
commitments are not ordered by identifier and do not enter one another's
history.

Let `H_i` be the sorted valid history and `n_i = |H_i|`.

### Primary threshold

The primary rule requires `n_i >= 10`.

For percentile `p`, the nearest-rank threshold is:

```text
rank(p, n_i) = ceil(p * n_i)       # one-indexed
threshold(p, H_i) = H_i[rank(p, n_i)]
```

The primary threshold is `threshold(0.67, H_i)`.

```text
high_load_exposure =
    concurrent_load_count > threshold(0.67, H_i)
```

Equality is unexposed. The subject and its current load never enter `H_i`.
Fewer than 10 valid snapshots emits `SUPPLIER_HISTORY_INSUFFICIENT`.
For historical/reactive canonical lines, this boolean is the High-Load
Exposure. For a proactive proposal, the same comparison yields only
`provisional_high_load_preview`.

### Continuous fields

Every canonical exposure-eligible line retains:

- `concurrent_load_count`; and
- a within-supplier expanding-history midrank:

```text
load_percentile =
    (count(h in H_i where h < concurrent_load_count)
     + 0.5 * count(h in H_i where h = concurrent_load_count))
    / n_i
```

The binary treatment always uses the nearest-rank rule. The continuous
continuous-load linear-slope sensitivity uses `load_percentile`; the raw count remains the
auditable operational measure. A proactive proposal exposes the same numeric
calculation only as `provisional_load_percentile`.

### Pre-registered sensitivity variants

The complete Core set is:

| Variant | Percentile | Minimum valid history |
| --- | ---: | ---: |
| Primary | 0.67 | 10 |
| Stricter threshold | 0.75 | 10 |
| Short-history sensitivity | 0.67 | 5 |
| Long-history sensitivity | 0.67 | 20 |
| Continuous sensitivity | midrank `load_percentile` | 10 |

All variants reuse the same source version, cutoffs, adjustment set, rule
definitions, and gate thresholds. Only the declared percentile and/or minimum
history changes. A binary variant therefore derives its own eligible rows,
exposure labels, first-exposure block, and frozen gate denominators; otherwise
the minimum-history variants would not test the specification they name. The
continuous sensitivity reuses the primary first-exposure block because it has
no binary first-exposure event. No sensitivity variant replaces the primary
result. Specification reversal is evaluated later by the validity contract; it
is not a reason to change this construction.

## Frozen Promised Milestone

For the fixed target milestone kind and historical/reactive cutoff `t_i`:

1. consider only valid `promise_recorded` and `promise_revised` events of the
   target kind that occurred and were known no later than `t_i`;
2. resolve only corrections and supersessions known by `t_i`;
3. follow the valid revision chain and select its latest state at `t_i`; and
4. freeze that state's present `promised_for` value.

The frozen promise may equal but must not precede commitment. Post-commitment
promise revisions are preserved but ignored for this outcome. A later
correction that contradicts the selected commitment-time baseline makes the
line ineligible rather than silently rewriting history.

Missing or late-known promises, incompatible chains, unsupported milestone
kinds, conflicting contemporaneous states, and contradictory later
corrections use this precedence:

1. unsupported target kind emits `TARGET_MILESTONE_UNSUPPORTED`;
2. a broken/cyclic revision chain, multiple incompatible states, or a
   contradictory later correction emits `FROZEN_PROMISE_CONFLICT`; and
3. a selected present `promised_for` value earlier than `t_i`, or not
   comparable with `t_i` at retained precision/timezone, emits
   `FROZEN_PROMISE_TEMPORALLY_INVALID`; and
4. otherwise, absence of one present promise both occurred and known by `t_i`
   emits `FROZEN_PROMISE_UNAVAILABLE`.

Independent failure families may add other codes, but this promise family emits
only its first applicable code.

For a proactive subject, the pre-award hook's proposed original promise is a
proposed-promise preview when it is present, uses the fixed target kind, is
known by `decision_at`, and is not earlier than `decision_at`. It is neither a
canonical Promised Milestone nor an `OrderLineEvent`. Failure emits
`PROACTIVE_SUBJECT_INPUT_UNUSABLE`.

## Supplier Milestone Slippage

This outcome is required for historical estimation lines but not for a current
subject profile.

As of the frozen observation cutoff, an eligible estimation line must have
exactly one valid, unsuperseded reached event for the target supplier
milestone. Its clocks must satisfy:

```text
commitment <= occurred_at <= known_at <= observation_cutoff
```

Multiple incompatible reached events are a conflict; the implementation must
not choose the earliest or latest opportunistically.

Slippage is signed:

```text
supplier_milestone_slippage_days =
    actual_target_milestone - frozen_promised_milestone
```

- Date/date uses signed calendar-day difference and records
  `supplier_milestone_slippage_duration_basis = CALENDAR_DAY`.
- Compatible datetimes or instants use signed elapsed seconds divided by
  86,400 and record
  `supplier_milestone_slippage_duration_basis = ELAPSED_86400_SECOND_DAY`.
- Fractional days and negative values are retained.
- `supplier_milestone_late = supplier_milestone_slippage_days > 0`.
- Zero is on time; negative is early.

Outcome failure precedence is:

1. a reliable cancellation after commitment and no later than observation
   cutoff emits `CANCELLED_BEFORE_MILESTONE` when no valid target actual
   occurred at or before the cancellation, including when no target actual
   exists;
2. multiple/conflicting actuals, actual occurrence before commitment, actual
   occurrence after observation cutoff, `known_at < occurred_at`, cancellation
   at or before commitment, incompatible precision, unresolved timezone, or
   simultaneous cancellation and actual emit `OUTCOME_TEMPORALLY_INVALID`; and
3. otherwise, absence of exactly one target actual both occurred and known by
   observation cutoff emits `OUTCOME_UNOBSERVED`.

Independent failure families may add other codes, but this outcome family emits
only its first applicable code.

Before any released `S8_OUTCOME(m)` bundle is serialized, take the union of
rows across the primary and every releasable sensitivity variant. Exactly one
slippage duration basis must be present in that union. That value becomes the
immutable request-wide `canonical_slippage_duration_basis`, exactly
`CALENDAR_DAY` or `ELAPSED_86400_SECOND_DAY`, and every released row must carry
the same value. If both values occur, emit the run-scoped scientific abstention
`SLIPPAGE_DURATION_BASIS_MIXED`; do not choose a majority basis, convert a row,
drop an otherwise eligible row, construct a `CausalEngineSuiteRequest`, or fit
an estimator. The ordered conflicting-basis counts and row-identity hashes are
retained as non-effect evidence.

## Estimation-line and subject-line roles

### Estimation line

A historical `ESTIMATION_LINE` must satisfy the exposure, frozen-promise,
outcome, covariate, cohort-design, and follow-up rules. Its observed outcome is
used only after every pre-estimation gate passes.

### Subject line

A current `SUBJECT_LINE` must satisfy load, history, promise, and covariate
rules at its decision cutoff. A reactive line uses canonical commitment-time
facts; a proactive proposal uses the preview-only `decision_at` rules above. A
subject does not require a reached milestone or slippage outcome. It is
evaluated separately against propensity and distribution support and is never
appended to historical estimator input.

For a reactive canonical subject, role selection removes its
`order_line_id` before `S0_SOURCE` is formed. This is not line ineligibility and
does not enter any gate denominator or exclusion count; it is recorded as
subject-role provenance. A proactive proposal is already outside the canonical
source population.

## Abstention scope

- `LINE_INELIGIBLE`: one historical line is excluded and retains all applicable
  codes. The cohort may continue only if every later coverage and support gate
  passes.
- `COHORT_INELIGIBLE`: the run emits no treatment-effect estimate and no
  subject-specific causal verdict.
- `SUBJECT_INELIGIBLE`: only the selected reactive/proactive subject receives
  `insufficient - abstain`. A valid historical population estimate may remain
  available, but it is not applied to that subject.

Planned cohort-design exclusions, such as structural warm-up,
`POST_FIRST_EXPOSURE_EXCLUDED`, and Olist multi-seller exclusion, are counted
as line ineligibility and remain visible in denominators.

## Follow-up maturity and cancellation

Each dataset fixes a follow-up horizon from domain or service semantics before
effect results are inspected. The horizon is expressed in whole days,
compatible with the target milestone:

- date values add calendar days; and
- comparable datetime/instant values add exact 86,400-second days.

An estimation line enters the outcome risk set only when:

```text
frozen_promised_milestone + follow_up_horizon <= observation_cutoff
```

This rule applies even when a newer line completed early. Such a line receives
`FOLLOW_UP_IMMATURE` and is excluded so that completion speed cannot determine
inclusion. If promise plus horizon cannot be compared with observation cutoff
at retained precision and timezone semantics, the line instead receives
`FOLLOW_UP_UNRESOLVABLE`.

A reliable cancellation by observation cutoff, with no valid target actual at
or before it, emits
`CANCELLED_BEFORE_MILESTONE`; slippage is undefined, never zero. Because
cancellation may be caused by exposure, one otherwise-eligible mature
pre-milestone cancellation makes the cohort ineligible under
`CANCELLATION_COMPETING_EVENT_PRESENT`. Core defines no competing-risk
estimand. Cancellation exactly simultaneous with the target actual is an
unresolved terminal-state conflict and emits `OUTCOME_TEMPORALLY_INVALID`;
cancellation after a valid target actual does not change that outcome.

For this rule, a reliable cancellation has exactly one valid unsuperseded event
with `commitment < occurred_at <= known_at <= observation_cutoff`.
Multiple/conflicting cancellation events or foreknowledge ordering emit
`OUTCOME_TEMPORALLY_INVALID`.

## Pre-treatment covariates

A covariate is eligible only when:

1. it is declared in the dataset's pre-registered adjustment set;
2. the value and every derivation input were known by commitment;
3. every history input is strictly prior to commitment;
4. its transformation is named and versioned; and
5. it is not downstream of load, emerging slippage, or a later intervention.

Eligibility uses `known_at <= t_i`, where `t_i` is the canonical commitment
cutoff or the accepted proactive `decision_at`. Neither `occurred_at` alone nor
`ingested_at` can prove availability.

Requested lead time is pre-treatment when the frozen future promise was known
at commitment. Calendar features derive only from commitment and a versioned
calendar. Supplier-history features use expanding, then-known history only.

Production progress, escalation activity, post-risk expediting, revised
promises, premium freight, recovery plans, and later supplier performance are
always prohibited.

State handling is fixed before estimation:

- `present` uses the typed value;
- `not_applicable` may be a separate category only when semantically valid;
- `absent`, `unknown`, and `redacted` may be used only through a
  pre-registered missing-category or indicator encoding; and
- `invalid`, temporally unresolved required values, or any detected leakage
  make the line ineligible.

No imputation or confounder removal may be selected after exposure or outcome
results are seen. Structurally unavailable concepts are disclosed as
unobserved assumptions, not disguised as ordinary row missingness.

## Cohort-design restrictions

### First exposure per supplier-project pair

Where genuine project identity exists, group otherwise exposure-eligible lines
by `(supplier_id, project_id)` and order them by comparable commitment time.
Retain:

- every unexposed line before the pair's first exposed commitment;
- all lines tied at that first exposed commitment; and
- no later line.

Never-exposed pairs retain their eligible untreated history. Later lines emit
`POST_FIRST_EXPOSURE_EXCLUDED`.

For a binary sensitivity variant, "exposed" means that variant's frozen
exposure rule. The continuous sensitivity reuses the primary rule's retained
first-exposure block.

If project identity is genuinely unavailable, no proxy is invented. The
restriction is recorded as unavailable and the run cannot support a
construction-domain causal claim. Olist may continue only in its explicit
out-of-domain validation role.

### Olist multi-seller groups

For Olist only, an Order Line is estimation-eligible only when every canonical
line in its `order_group_id` has the same `supplier_id`. Otherwise the
order-level carrier timestamp cannot prove a seller-specific handoff, and all
lines in the group emit `MULTI_SUPPLIER_MILESTONE_AMBIGUOUS`.

The system does not collapse sellers or copy the shared timestamp to each
seller. This restriction does not apply where the source proves line-specific
supplier milestones.

## Line-level eligibility codes

The registry is closed and versioned. A line may carry multiple codes; each
instance includes affected fields and source/derivation evidence pointers.

### Common to estimation and subject lines

| Code | Condition |
| --- | --- |
| `COMMITMENT_CUTOFF_UNUSABLE` | Commitment cutoff is absent, invalid, late-known, conflicting, or temporally incomparable |
| `TARGET_MILESTONE_UNSUPPORTED` | Run target is not a reviewed supplier-controlled milestone for this line |
| `LOAD_SNAPSHOT_UNRESOLVABLE` | At least one material open-line membership comparison is unresolved |
| `SUPPLIER_HISTORY_INSUFFICIENT` | Valid expanding history is below the selected variant's minimum |
| `FROZEN_PROMISE_UNAVAILABLE` | No usable target promise was established by commitment |
| `FROZEN_PROMISE_CONFLICT` | Promise chain or later correction contradicts the frozen baseline |
| `FROZEN_PROMISE_TEMPORALLY_INVALID` | Selected promise is earlier than, or not safely comparable with, the decision cutoff |
| `COVARIATE_TEMPORAL_LEAKAGE` | A selected covariate or derivation input crosses the commitment cutoff or is post-treatment |
| `REQUIRED_COVARIATE_UNUSABLE` | A required covariate is invalid or lacks its pre-registered missingness handling |

### Estimation-only

| Code | Condition |
| --- | --- |
| `FOLLOW_UP_IMMATURE` | Frozen promise plus horizon is later than observation cutoff |
| `FOLLOW_UP_UNRESOLVABLE` | Promise plus horizon cannot be compared with observation cutoff without inventing precision or timezone |
| `OUTCOME_UNOBSERVED` | No single target actual both occurs and is known by observation cutoff |
| `OUTCOME_TEMPORALLY_INVALID` | Actual is conflicting, outside the commitment-to-observation window, simultaneous with cancellation, or cannot be subtracted safely |
| `CANCELLED_BEFORE_MILESTONE` | Reliable cancellation precedes the target actual |
| `POST_FIRST_EXPOSURE_EXCLUDED` | Line is later than the first-exposure block for its supplier-project pair |
| `MULTI_SUPPLIER_MILESTONE_AMBIGUOUS` | Olist order group has more than one supplier |

## Frozen cohort sets and denominators

Construct these sets separately for the primary and each binary sensitivity
variant. The continuous sensitivity reuses the primary sets. Set membership is
immutable once the next set is formed.

| Set | Exact population |
| --- | --- |
| `H0_HISTORY_SOURCE` | Every non-quarantined Order Line selected by the frozen history-lookback selector, including the estimator window and selected reactive subject; used only to reconstruct point-in-time load histories |
| `H1_HISTORY_COMMITMENT` | `H0_HISTORY_SOURCE` lines with supported target semantics and one usable canonical commitment cutoff |
| `S0_SOURCE` | `H0_HISTORY_SOURCE` lines selected by the frozen estimator-window selector, excluding the selected reactive subject identity before any estimator denominator is formed |
| `S1_COMMITMENT` | `S0_SOURCE` lines with supported target semantics and one usable canonical commitment cutoff |
| `S2_WARMED(m)` | `S1_COMMITMENT` lines with at least `m` strictly prior `H1_HISTORY_COMMITMENT` lines for the same supplier, where `m` is the variant minimum |
| `S2_SNAPSHOT_OK(m)` | Auxiliary subset of `S2_WARMED(m)` whose current Supplier Load Snapshot is resolvable, regardless of whether `m` prior snapshots are valid |
| `S3_EXPOSURE(m)` | `S2_WARMED(m)` lines with a resolvable current load snapshot and at least `m` valid prior load snapshots, yielding that variant's exposure |
| `S4_DESIGN(m)` | `S3_EXPOSURE(m)` after Olist multi-seller exclusion and that binary variant's first-exposure restriction |
| `S5_PROMISE(m)` | `S4_DESIGN(m)` lines with one valid frozen promise |
| `S6_MATURE(m)` | `S5_PROMISE(m)` lines with a resolvable comparison satisfying frozen promise plus follow-up horizon no later than observation cutoff |
| `S7_COVARIATE(m)` | `S6_MATURE(m)` lines passing every required pre-treatment covariate rule |
| `S8_OUTCOME(m)` | `S7_COVARIATE(m)` lines with one valid target actual and no cancellation conflict |
| `S9_OVERLAP(m)` | `S8_OUTCOME(m)` lines retained after the frozen propensity common-support rule |

Gate denominators are fixed:

- commitment coverage: `S0_SOURCE`;
- exposure measurement coverage: `S2_WARMED(m)`;
- frozen-promise coverage: `S4_DESIGN(m)`;
- covariate missingness and retention: `S6_MATURE(m)`;
- cancellation and outcome completeness: `S7_COVARIATE(m)`;
- pre-trim treatment and outcome support: `S8_OUTCOME(m)`; and
- trimming rates: `S8_OUTCOME(m)`, with post-trim support evaluated on
  `S9_OVERLAP(m)`.

The outcome-completeness numerator counts `S7_COVARIATE(m)` lines that would
enter `S8_OUTCOME(m)` on outcome availability and temporal validity; it never
changes the denominator. Planned exclusions and failures are counted at the
transition where they occur.

For any transition from denominator `D` to retained numerator `N`:

```text
overall_rate = |N| / |D|
arm_rate(a) = |N intersect D where exposure = a| /
              |D where exposure = a|
arm_gap = abs(arm_rate(1) - arm_rate(0))
```

Per-covariate non-present rates use the same denominators and count every state
other than `present` in the numerator. Per-supplier snapshot coverage is that
supplier's `S2_SNAPSHOT_OK(m)` count divided by its `S2_WARMED(m)` count.

A required zero denominator never passes vacuously:

- empty `S0_SOURCE` emits `COHORT_SUPPORT_INSUFFICIENT`;
- empty `S2_WARMED(m)` or zero candidate suppliers emits
  `EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT`;
- empty `S4_DESIGN(m)` emits `CORE_TEMPORAL_COVERAGE_INSUFFICIENT`;
- empty `S6_MATURE(m)` emits `COVARIATE_COVERAGE_INSUFFICIENT`;
- empty `S7_COVARIATE(m)` emits `OUTCOME_COVERAGE_INSUFFICIENT`; and
- a zero treatment-arm denominator emits `COHORT_SUPPORT_INSUFFICIENT` in
  addition to the applicable coverage failure.

## Pre-estimation cohort gates

Canonical ingestion rejection precedes these scientific gates and is not an
abstention.

All percentages use the frozen pre-drop denominator named by the gate.
Threshold comparisons are inclusive unless the rule says "over" or "more
than."

The cohort-level registry is:

| Code | Scope |
| --- | --- |
| `SOURCE_SEMANTICS_INELIGIBLE` | Source or target-field meaning cannot support the estimand |
| `EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT` | Load snapshots are too selectively or sparsely measurable |
| `CORE_TEMPORAL_COVERAGE_INSUFFICIENT` | Commitment or frozen-promise coverage fails |
| `OUTCOME_COVERAGE_INSUFFICIENT` | Mature target-outcome coverage fails |
| `CANCELLATION_COMPETING_EVENT_PRESENT` | A reliable pre-milestone cancellation makes the continuous estimand selection-dependent |
| `COVARIATE_COVERAGE_INSUFFICIENT` | Pre-registered adjustment-set coverage fails |
| `SLIPPAGE_DURATION_BASIS_MIXED` | Otherwise releasable outcome rows do not share one request-wide calendar-day or elapsed-86,400-second-day basis |
| `COHORT_SUPPORT_INSUFFICIENT` | Treatment-arm, supplier, or within-supplier support fails |
| `OUTCOME_DEGENERATE` | Continuous slippage has no usable variation |
| `OVERLAP_COHORT_INSUFFICIENT` | Propensity trimming or post-trim support fails |

### Source semantics

Emit `SOURCE_SEMANTICS_INELIGIBLE` when:

- canonical `intended_role` is not eligible under the mapping below;
- target milestone lacks a reviewed supplier-controlled mapping;
- a required mapping assumption is withdrawn or unverified;
- `PROMISE_ACTUAL_EQUALITY_SUSPICIOUS` remains active for the target fields; or
- protected lineage cannot prove commitment, promise, or actual-event
  semantics.

Canonical role mapping is exact:

- `semi_synthetic_hero` may run the Core causal estimand for the disclosed
  semi-synthetic construction role;
- `out_of_domain_validation` may run the same estimator only for explicitly
  out-of-domain validation and cannot support a construction effect claim;
- `rejection_vignette` cannot enter causal estimation.

These are the only Core `DatasetVersion.intended_role` values. A future domain
sample cannot enter this contract through an authorization or extension field;
it first requires a versioned canonical-schema and contract revision. SCMS
remains `rejection_vignette`.
A versioned timezone assumption is allowed and disclosed; an unknown timezone
that affects ordering or subtraction is not.

### Exposure measurement coverage

`S2_WARMED(m)` is the denominator. Structural warm-up counts strictly prior
`H1_HISTORY_COMMITMENT` lines irrespective of whether their load snapshots are
valid.
For the primary `m = 10`; binary sensitivity variants substitute their declared
minimum:

- `|S2_SNAPSHOT_OK(m)| / |S2_WARMED(m)| >= 0.95`; and
- at least 90% of suppliers represented in `S2_WARMED(m)` must have snapshot
  coverage of at least 90%.

Structural warm-up, current-snapshot failures, and insufficient valid expanding
history are reported separately. The coverage gate measures only the accepted
current-snapshot rule; `SUPPLIER_HISTORY_INSUFFICIENT` remains a line code and
the later support gates assess the retained exposure cohort. Coverage failure
emits `EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT`.

### Core temporal coverage

Require:

- `|S1_COMMITMENT| / |S0_SOURCE| >= 0.95`;
- `|S5_PROMISE(m)| / |S4_DESIGN(m)| >= 0.95`;
- frozen-promise coverage must be at least 90% in each treatment arm; and
- the arm coverage gap must be no more than 5 percentage points.

Failure emits `CORE_TEMPORAL_COVERAGE_INSUFFICIENT`.

### Outcome completeness

The denominator is frozen `S7_COVARIATE(m)`, before dropping missing or invalid
outcomes.
Require:

- at least 95% observed target outcomes overall;
- at least 90% in each treatment arm;
- no more than a 5-percentage-point observation-rate gap between arms; and
- zero reliable pre-milestone cancellations.

If any reliable pre-milestone cancellation exists, emit
`CANCELLATION_COMPETING_EVENT_PRESENT` and stop this gate. Otherwise, failed
coverage emits `OUTCOME_COVERAGE_INSUFFICIENT`. Percentages are never
recomputed after dropping missing outcomes.

### Covariate coverage

On frozen `S6_MATURE(m)`, for every covariate in the pre-registered dataset
adjustment set:

- encoded non-present states must be no more than 20% overall;
- encoded non-present states must be no more than 30% in either arm; and
- the arm missingness gap must be no more than 10 percentage points.

After required-covariate eligibility:

- `|S7_COVARIATE(m)| / |S6_MATURE(m)| >= 0.80`; and
- the arm retention gap must be no more than 10 percentage points.

Failure emits `COVARIATE_COVERAGE_INSUFFICIENT`. A failed run cannot be rescued
by removing a confounder after results are seen.

### Minimum treatment support

On both `S8_OUTCOME(m)` and `S9_OVERLAP(m)`, require:

- at least 500 eligible estimation lines;
- at least 100 exposed and 100 unexposed;
- exposure prevalence from 10% through 90%;
- at least 30 suppliers overall;
- each arm represented across at least 20 suppliers; and
- at least 20 suppliers containing both exposed and unexposed lines.

Failure emits `COHORT_SUPPORT_INSUFFICIENT`. Passing is a feasibility
condition, not proof of power, exchangeability, or validity.

### Outcome variation

On `S8_OUTCOME(m)`, the primary continuous outcome requires at least two
distinct values and variance greater than zero at retained source precision.
Failure emits `OUTCOME_DEGENERATE`.

The binary `supplier_milestone_late` sensitivity requires at least 50 late and
50 non-late lines. Insufficient binary support marks only that variant
unavailable; it does not invalidate an otherwise eligible continuous-outcome
run.

No implementation adds jitter, winsorizes, or removes extremes after outcome
inspection. Any plausibility bounds must be frozen in the dataset manifest.

### Propensity overlap

After every preceding gate passes, fit only the frozen, versioned propensity
specification on `S8_OUTCOME(m)`. No treatment-effect estimate may yet be fit.
Preprocessing is fit inside each training fold.

For historical line `i`, its propensity is the arithmetic mean of its one
out-of-fold probability from each frozen repeat. No model contributing to that
mean may have trained on `i`.

For an external subject, propensity is the arithmetic mean of the probability
from every fitted fold model across every repeat, using each model's paired
training-fold preprocessing. No full-cohort refit or alternative aggregation
is allowed for subject gating. Fold assignments, repeats, algorithm,
hyperparameters, tuning procedure, calibration, dependency versions, and seeds
come only from the frozen propensity specification.

Common support is inclusive:

```text
0.10 <= propensity <= 0.90
```

Historical out-of-fold propensity is computed for `S8_OUTCOME(m)`. Trim lines
outside that interval to form `S9_OVERLAP(m)`. Emit
`OVERLAP_COHORT_INSUFFICIENT` when:

- trimming removes more than 20% overall;
- trimming removes more than 20% from either arm; or
- any minimum-treatment-support gate fails after trimming.

Thresholds are never moved and the model is never selected to obtain a
preferred treatment effect.

## Subject-level gates

The subject is scored against the frozen historical propensity ensemble
defined above and post-trim cohort.

The subject-level registry is:

| Code | Scope |
| --- | --- |
| `PROACTIVE_SUBJECT_INPUT_UNUSABLE` | Provisional decision cutoff, supplier, target promise, or required covariate input is missing, unmapped, or late-known |
| `SUBJECT_OVERLAP_INSUFFICIENT` | Subject propensity is outside common support |
| `SUBJECT_DISTRIBUTION_UNSUPPORTED` | Subject covariates lack marginal or local two-arm support |

### Propensity

Propensity outside the inclusive `[0.10, 0.90]` interval emits
`SUBJECT_OVERLAP_INSUFFICIENT`.

### Distribution support

All calculations use post-trim historical lines only.

1. Every subject categorical level must occur in at least 20 lines from each
   arm.
2. The subject's full vector of pre-registered missingness states must occur in
   at least 20 lines from each arm.
3. Every numeric value must lie within the closed 1st-to-99th-percentile range
   of each arm. Both endpoints use the one-indexed nearest-rank rule
   `ceil(p * n)` over that arm's sorted present historical values.
4. Gower distance is computed over the pre-registered covariates:
   - each covariate contributes exactly once;
   - when either value is non-present, compare the two explicit value states:
     equal states contribute `0` and different states contribute `1`;
   - when both values are present, categorical values contribute `0` when
     equal and `1` otherwise;
   - when both values are present, numeric contribution is
     `min(abs(x - y) / pooled_training_range, 1)`, where
     `pooled_training_range` is the post-trim 99th percentile minus 1st
     percentile, using the same nearest-rank convention;
   - a zero numeric range contributes `0` only for exact equality and `1`
     otherwise; and
   - total distance is the unweighted mean of feature contributions.
5. At least 20 neighbours from each arm must have Gower distance no greater
   than `0.25`.

Failure emits `SUBJECT_DISTRIBUTION_UNSUPPORTED`. This is an applicability
check, not permission to display an individualized effect.

## Deterministic gate order

1. Freeze the immutable dataset version and run inputs.
2. Apply canonical ingestion validation, then validate source semantics.
3. Form `H0_HISTORY_SOURCE` and `H1_HISTORY_COMMITMENT`. Remove the selected
   reactive subject identity only from the estimator population, then form
   `S0_SOURCE` and `S1_COMMITMENT`; evaluate source-window and commitment
   coverage.
4. Derive chronological load snapshots and histories from the `H` sets, then form
   `S2_WARMED(m)`, `S2_SNAPSHOT_OK(m)`, and `S3_EXPOSURE(m)` before any promise,
   covariate, or outcome filtering.
5. Apply Olist single-supplier and first-exposure restrictions to form
   `S4_DESIGN(m)`. No later maturity or outcome fact determines which exposure
   was first.
6. Select frozen promises, evaluate temporal coverage, and form
   `S5_PROMISE(m)`.
7. Apply the follow-up rule to form `S6_MATURE(m)`. Maturity is evaluated only
   after a valid frozen promise exists.
8. Evaluate pre-treatment covariate missingness and retention, then form
   `S7_COVARIATE(m)`.
9. Evaluate cancellation and outcome completeness against frozen
   `S7_COVARIATE(m)`, then form `S8_OUTCOME(m)`, require one request-wide
   slippage duration basis across every releasable variant, and check treatment
   and outcome support.
10. Compute only cross-fitted propensity scores, trim to form
    `S9_OVERLAP(m)`, and re-check support.
11. Check the separate subject against the frozen propensity ensemble and
    distribution support.
12. Release `S9_OVERLAP(m)` as estimator input only if every applicable cohort
    gate passes.

No later gate may change an earlier denominator, recompute history, alter the
threshold, or reclassify a source fact.

## Logical derived output

The downstream analysis-artifact contract must preserve, at minimum, the
following logical facts and their lineage without changing their semantics:

- estimator-window and history-lookback selector versions, bounds, and
  selected-identity hashes;
- decision cutoff, cutoff source (`canonical_commitment` or
  `proactive_decision`), trigger mode, and target milestone kind;
- canonical concurrent load count, or preview-only
  `provisional_concurrent_load_count` for a proactive proposal;
- valid history count;
- threshold-rule identifier and threshold value;
- canonical high-load exposure, or preview-only
  `provisional_high_load_preview` for a proactive proposal;
- canonical load percentile, or preview-only `provisional_load_percentile` for
  a proactive proposal;
- frozen Promised Milestone for canonical lines, or the proposed-promise
  preview for a proactive proposal;
- actual target milestone for estimation lines;
- signed slippage days, the per-line slippage duration basis, the exact
  request-wide `canonical_slippage_duration_basis`, and binary late variant;
- role (`ESTIMATION_LINE` or `SUBJECT_LINE`);
- all line, cohort, and subject eligibility codes;
- every gate denominator, numerator, threshold, and result; and
- evidence pointers to contributing canonical events and transformations.

This section is not a serialization design.

## Conformance examples

Implementations must pass these boundary examples in addition to surrounding
tests.

### Load and history

1. **Half-open load:** at subject time `10:00`, a prior line closing exactly at
   `10:00` is closed; a prior line closing at `10:01` is open.
2. **Same-time commitment:** another line committed exactly at subject time is
   excluded from load and history; identifiers never break the tie.
3. **Known-late closure:** a milestone occurring before subject time but first
   known afterward does not close the point-in-time snapshot.
4. **Cancellation:** a reliable cancellation occurring and known before
   subject time closes the line; a later cancellation does not.
5. **Wrong milestone:** customer delivery does not close a
   `supplier_handoff` load interval.
6. **Ambiguous precision:** a same-date commitment whose within-day order could
   change membership produces `LOAD_SNAPSHOT_UNRESOLVABLE`.
7. **Minimum history:** under the primary rule, nine valid prior snapshots are
   ineligible and ten are eligible. Five snapshots are eligible only for the
   short-history sensitivity; nineteen are ineligible for the long-history
   sensitivity and twenty are eligible.
8. **Nearest rank and ties:** for history
   `[0,1,1,2,2,3,3,4,5,7]`, the 67th-percentile rank is `7`, threshold is `3`,
   current load `3` is unexposed, and `4` is exposed.
9. **Midrank:** with that history and current load `4`,
   `load_percentile = (7 + 0.5 * 1) / 10 = 0.75`.
10. **History independence:** a prior line with a valid load snapshot remains
    in history even when its later outcome is missing.

### Promise and outcome

11. **Pre-commitment revision:** a valid promise revised before and known by
    commitment freezes the revised value.
12. **Post-commitment revision:** a later revision is retained in history but
    does not change the frozen promise.
13. **Later contradiction:** a later correction contradicting the frozen
    baseline produces `FROZEN_PROMISE_CONFLICT`.
14. **Signed date outcome:** promise `2026-01-22` and actual `2026-01-20`
    produce `-2` days and `supplier_milestone_late = false`.
15. **Fractional outcome:** comparable instants 36 hours apart produce `1.5`
    days.
16. **No truncation:** early completion remains negative; equality remains
    zero.
17. **Unresolved actual:** mixed temporal kinds that cannot be compared safely
    produce `OUTCOME_TEMPORALLY_INVALID`.
18. **Cancellation boundary:** cancellation with no target actual, or before
    the target actual, produces `CANCELLED_BEFORE_MILESTONE`; exact simultaneity
    produces `OUTCOME_TEMPORALLY_INVALID`; cancellation after the target actual
    leaves the outcome unchanged.

### Roles, follow-up, and covariates

19. **Open subject:** a current subject with no actual milestone can pass
    subject eligibility but can never become an estimation line.
20. **Maturity boundary:** a line passes when promise plus horizon equals the
    observation cutoff and fails with `FOLLOW_UP_IMMATURE` when it is later.
21. **Early completion bias guard:** an immature line is excluded even if its
    actual milestone is already observed.
22. **Post-treatment leakage:** a progress field known after commitment emits
    `COVARIATE_TEMPORAL_LEAKAGE`.
23. **Future-valued baseline:** requested lead time is allowed when its future
    promise was known by commitment.
24. **Missing encoding:** `unknown` is usable only when the frozen adjustment
    manifest defines its encoding; `invalid` remains ineligible.
25. **First-exposure block:** two tied first-exposed lines are both retained;
    every later line in the supplier-project pair is excluded.
26. **Olist ambiguity:** all lines in a two-seller order group receive
    `MULTI_SUPPLIER_MILESTONE_AMBIGUOUS`.

### Gate boundaries

27. **Coverage inclusivity:** exactly 95% overall outcome coverage passes;
    94.999% fails. Exactly a 5-point arm gap passes; a larger gap fails.
28. **Cancellation:** one reliable pre-milestone cancellation in the mature
    otherwise-eligible cohort emits
    `CANCELLATION_COMPETING_EVENT_PRESENT`.
29. **Minimum support:** exactly 500 lines, 100 per arm, 30 suppliers, 20
    suppliers per arm, and 20 mixed-arm suppliers pass their respective
    inclusive boundaries.
30. **Degenerate outcome:** 500 identical slippage values emit
    `OUTCOME_DEGENERATE`; no jitter is added.
31. **Overlap boundary:** propensities `0.10` and `0.90` are retained; values
    outside are trimmed. Exactly 20% trimmed passes; more than 20% fails.
32. **Subject categorical support:** 19 historical examples in either arm
    fail; 20 pass that marginal condition.
33. **Subject numeric support:** a value equal to an arm's 1st or 99th
    percentile passes the range boundary.
34. **Subject neighbourhood:** 20 neighbours per arm at Gower distance `0.25`
    pass; 19 in either arm or distance greater than `0.25` fails.
35. **Source role:** SCMS always emits `SOURCE_SEMANTICS_INELIGIBLE` for causal
    estimation while remaining available as a rejection vignette.
36. **Denominator immutability:** removing a later-unobserved outcome must not
    improve or recompute an earlier exposure, promise, or coverage denominator.
37. **Commitment correction:** exactly one valid unsuperseded commitment head
    known by its corrected occurrence time supplies `t_i`; multiple heads or a
    correction known only later produces `COMMITMENT_CUTOFF_UNUSABLE`.
38. **Future-dated actual:** a reached event known today but with occurrence
    after the observation cutoff produces `OUTCOME_TEMPORALLY_INVALID`.
39. **Proactive subject:** a proposal with frozen `decision_at`, mapped
    supplier, target promise, and eligible covariates receives a provisional
    subject result without creating a canonical commitment or entering its own
    load. Missing supplier mapping produces
    `PROACTIVE_SUBJECT_INPUT_UNUSABLE`.
40. **Scope isolation:** a line failure may still yield a cohort estimate when
    all cohort gates pass; a subject support failure preserves that population
    estimate but emits no verdict for that subject; a cohort failure emits no
    treatment-effect estimate.
41. **Zero denominator:** an empty required set emits its specified failure
    code; it never passes because a ratio is undefined.
42. **Canonical roles:** `semi_synthetic_hero` permits the disclosed
    construction demonstration, `out_of_domain_validation` permits the
    disclosed Olist validation estimate, `rejection_vignette` rejects SCMS
    estimation, and every other role fails strict input validation.
43. **Propensity reproducibility:** with two repeats and five folds, each
    historical propensity averages two out-of-fold predictions and an external
    subject averages all ten fold-model predictions using their paired
    preprocessing.
44. **Follow-up ambiguity:** promise plus horizon that cannot be compared with
    observation cutoff emits `FOLLOW_UP_UNRESOLVABLE`, not
    `FOLLOW_UP_IMMATURE`.
45. **Actual foreknowledge:** a reached milestone with
    `known_at < occurred_at` emits `OUTCOME_TEMPORALLY_INVALID` even when both
    clocks precede observation cutoff.
46. **Preview-only semantics:** a proactive check emits only
    `provisional_concurrent_load_count`, `provisional_load_percentile`, and
    `provisional_high_load_preview`; it emits no canonical Supplier Load
    Snapshot, High-Load Exposure, or Promised Milestone.
47. **Reactive subject extraction:** the selected canonical subject identity is
    removed before `S0_SOURCE`; its missing current outcome cannot reduce an
    historical coverage rate. It remains in `H0_HISTORY_SOURCE` only so a later
    canonical line can reconstruct the load that was observable at that later
    commitment.
48. **Snapshot-versus-history coverage:** a warmed line with a resolvable
    current snapshot but fewer than `m` valid historical snapshots counts in
    `S2_SNAPSHOT_OK(m)` for the accepted snapshot-coverage rate, then receives
    `SUPPLIER_HISTORY_INSUFFICIENT` before `S3_EXPOSURE(m)`.
49. **Promise chronology:** a selected promise earlier than commitment, or
    incomparable with commitment at retained precision/timezone, emits
    `FROZEN_PROMISE_TEMPORALLY_INVALID` and cannot enter `S5_PROMISE(m)`.
50. **Warm-up universe:** both `S2_WARMED(m)` construction and its coverage gate
    count strictly prior `H1_HISTORY_COMMITMENT` lines; neither substitutes
    `S1_COMMITMENT`.
51. **Frozen windows:** identical dataset, estimator-selector version,
    history-selector version, selector bounds, and selected-identity hashes
    reconstruct identical `H0_HISTORY_SOURCE` and pre-subject `S0_SOURCE`
    populations without consulting exposure, outcomes, or eligibility.
52. **Mixed slippage bases:** otherwise releasable date/date and
    datetime/instant outcome rows produce `SLIPPAGE_DURATION_BASIS_MIXED`,
    preserve counts and identity hashes for both bases, and produce no causal-
    engine request or estimate. An all-date union freezes `CALENDAR_DAY`; an
    all-datetime/instant union freezes `ELAPSED_86400_SECOND_DAY`.

## Domain-language impact

This contract sharpens the existing Supplier Load Snapshot, High-Load
Exposure, Promised Milestone, and Supplier Milestone Slippage terms without
changing their canonical ownership. Proactive outputs are explicitly
preview-only analysis fields: they do not instantiate or redefine those
canonical terms before an Order Line is committed. No new ubiquitous-language
term is introduced, so algorithmic detail remains here rather than in the
context glossaries.
