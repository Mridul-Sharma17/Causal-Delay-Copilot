# Intervention Eligibility and Trade-off Contract

## Status and authority

This contract records the confirmed decisions for
[Define intervention eligibility and trade-off semantics](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/10).
It is planning-only and does not implement Decision Support.

This effort does not claim practitioner or domain-expert validation. Issue #17 is
explicitly out of scope for this hackathon. The reviewer roles, approval gates,
and domain-attestation schemas below remain normative safeguards for a future
validated deployment; no link, rubric, trigger, or composite review is
`APPROVED` on the basis of this work alone. Research-backed strategy and
synthetic or analytical evidence must not be represented as practitioner
approval.

### Locked closure scope

Issue #10 owns logical eligibility, comparison, recommendation, advice-chain,
and currentness semantics only. It does not define physical tables,
transactions, locks, transport retries, or a generic source-extraction
language; issue #12 owns those implementation choices while preserving this
contract's logical identities and replay outcomes. It also does not make the
substantive domain judgment that a composite plan is compatible. This hackathon
does not perform issue #17's practitioner validation; review-dependent records
remain provisional or unavailable, and a future domain review requires a fresh
effort or explicit scope redraw. Those deferred implementation and expert-
judgment details cannot reopen this contract unless they contradict one of its
locked logical invariants.

The Stage 2 strategy controls product and scientific intent. The canonical
order-event and lineage contract controls source semantics and money
representation. The exposure, outcome, and temporal-eligibility contract
controls subject facts and the signed Supplier Milestone Slippage day basis.
The validity-verdict contract controls Evidence Verdicts, claim scope, causal
language, and the sole permission to enter Decision Support. The analysis-run
contract controls verified upstream artifact reads.

This contract owns the governed Core Intervention Library, driver-action
links, case constraints, assumption-labelled benefit arithmetic, option
suppression, comparison, trade-off selection, and the logical Action
Recommendation record. It does not own:

- Gemini or deterministic artifact drafting, which is decided by
  [Design Gemini-assisted artifact drafting and deterministic fallback](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/11);
- physical audit storage, actor persistence, or replay tables, which are
  decided by
  [Define audit, persistence, and replay semantics](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/12);
- evaluation-harness policy or utility ground truth, which is decided by
  [Define evaluation-harness acceptance gates and policy comparisons](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/13); or
- any future domain-expert review, deferred outside this hackathon and requiring
  a fresh effort or explicit scope redraw of
  [Validate the causal and decision model with domain experts](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/17).

The Stage 2 strategy's shorthand
`estimated exposure effect * recoverable fraction - action cost` is not a
normative formula because it mixes days and money and does not translate
supplier-milestone time to critical-path time. This confirmed contract
replaces that shorthand with the dimensionally typed calculations below while
preserving the strategy's decision intent.

## Core invariants

1. Decision Support evaluates exactly one current subject case. A Population
   Verdict alone never permits an Action Recommendation.
2. Option evaluation starts only when the verified Subject Verdict records
   `decision_support_evaluation_permitted = true`.
3. `SUPPORTED_UNDER_ASSUMPTIONS` is necessary but not independently
   sufficient: the recorded role and claim-scope permission must also permit
   Decision Support.
4. Tentative, Association Only, Insufficient, a missing verdict, and an
   upstream execution or integrity failure produce no driver-linked Action
   Recommendation. `ACCEPT_AND_MONITOR` does not bypass this gate.
5. Evidence that High-Load Exposure changes Supplier Milestone Slippage is not
   evidence that any Intervention Option works. Every option states
   `INTERVENTION_EFFECT_NOT_ESTIMATED`.
6. Runtime may select only a versioned governed library option. It may not use
   free-form or LLM-generated actions and may not assemble new composites.
7. Only an approved driver-action link may enter constraints or an applicable
   benefit calculation. An approved monitoring baseline may enter constraints
   but makes no mechanism or benefit claim. Provisional, rejected, missing,
   and speculative links fail closed.
8. A required constraint is satisfied only by eligible point-in-time evidence.
   `UNKNOWN` suppresses an option; absence is never silently false or true.
9. Advisory uncertainty remains visible. It does not silently suppress an
   option and cannot support a dominance claim.
10. Supplier-milestone benefit, project-delay benefit, and money remain
    dimensionally separate. No arithmetic subtracts currency from days.
11. A recoverable fraction is an editable, declared assumption, never a
    learned parameter or an observed intervention effect.
12. Recovered supplier-milestone time is not automatically critical-path time.
    Monetary value requires a separate declared critical-path translation
    fraction.
13. Consequence-mitigation benefits use separate operational assumptions and
    never inherit the exposure-effect estimate.
14. Lower, central, and upper option projections are assumption-based
    projections. They are not an intervention-effect confidence interval or a
    probability distribution.
15. All monetary comparison uses one ISO currency and the upstream canonical
    slippage-day basis. Core performs no exchange-rate conversion.
16. Active options require positive central net assumption value. An
    interval-sensitive value case cannot become a sole dominant
    recommendation.
17. Dominance is strict Pareto dominance over declared comparison dimensions.
    No hidden score, learned policy, or unrecorded weight exists.
18. An unresolved Pareto trade-off yields two candidates and no Action
    Recommendation until the manager selects one.
19. A trade-off selection chooses a candidate; it does not approve, authorize,
    execute, or communicate the action.
20. Each Decision Support Evaluation is immutable. Input edits produce a new
    occurrence and never mutate causal evidence or an earlier recommendation.
21. A valid output captures the exact values presented and immutable
    provenance references. Later registry changes cannot reinterpret it.
22. Immutable history is not timeless advice. Every current rendering,
    selection, authorization, or monitoring use must prove the authoritative
    head, governed-dependency lifecycle, and operational validity horizons at
    its exact currentness cutoff.
23. Option evaluation additionally requires the exact upstream Subject Driver
    State to be true at the causal cutoff. A false state is a non-causal
    applicability result and never evaluates an option, including monitoring.

## Canonical language and ownership

### Decision Support Evaluation

A `Decision Support Evaluation` is one immutable application of exact
Decision Support policy and library versions to one verified Subject Verdict
and Subject Driver State. When the driver is active, it additionally consumes
one Case Constraint Snapshot and one set of declared assumptions. It produces
exactly one terminal Decision Support outcome.

It exists only after a permission attempt establishes
`decision_support_evaluation_permitted = true`. A refused permission attempt
may produce `NOT_PERMITTED`, but is not a Decision Support Evaluation.

It is not an Analysis Run. Editing a cost, constraint, or benefit assumption
does not change or rerun causal evidence.

### Case Constraint Snapshot

A `Case Constraint Snapshot` is the immutable, point-in-time set of typed
operational facts and attestations used to evaluate Intervention Options for
one subject at one operational cutoff, `constraints_as_of`. It does not make
an option eligible by itself and does not retime the subject's causal
`decision_at`.

### Subject Driver State

A `Subject Driver State` is the exact boolean carried by the verified upstream
Subject Profile at the causal cutoff: canonical `high_load_exposure` for a
reactive Order Line or preview-only `provisional_high_load_preview` for a
proactive proposal. It establishes whether this driver is active for option
applicability; it does not attribute an outcome to the driver or to one Order
Line.

### Release-Timing Preview

A `Release-Timing Preview` is an immutable operational what-if for a candidate
later release or commitment of the exact proactive proposal being evaluated.
It may provide constraint evidence for `RELEASE_TIMING_ADJUSTMENT`, but it
never replaces the Subject Driver State, retimes causal evidence, changes the
Subject Verdict, or creates a canonical Order Line, Supplier Load Snapshot, or
High-Load Exposure.

### Driver-Action Link

A `Driver-Action Link` is a versioned reviewed statement connecting one
governed Intervention Option to a supported driver in a declared trigger mode.
An `ACTION_MECHANISM` link records a plausible mechanism for changing future
exposure or consequences. A `MONITORING_BASELINE` link records a reviewed
non-mechanistic response baseline and makes no mechanism or benefit claim.
Neither link kind estimates the option's effect.

### Monitoring Escalation Trigger

A `Monitoring Escalation Trigger` is one immutable, versioned, externally
reviewed atomic predicate for one exact `ACCEPT_AND_MONITOR` option version and
its declared trigger-mode applicability. It observes one registered typed
value and, when matched later, requests manager review; it never authorizes or
executes an action, changes causal evidence, or revises an earlier evaluation
or recommendation.

### Recommendation Candidate

A `Recommendation Candidate` is an eligible option projection within one
Decision Support Evaluation. It has no authority and is not an Action
Recommendation.

### Trade-off selection

A trade-off selection is the manager's choice of one of the two candidates
from an unchanged `TRADEOFF_REQUIRES_MANAGER_CHOICE` result. It creates the
basis for a singular Action Recommendation but is not a Manager Decision or
authorization.

### Canonical Action Recommendation

The existing canonical definition remains authoritative: an Action
Recommendation selects exactly one eligible Intervention Option. It advises
but does not authorize or execute.

## Closed identifiers and versions

Core recognizes only the following identifiers and versions:

| Contract or registry | Identifier | Version |
| --- | --- | --- |
| Decision Support policy | `decision-support-policy` | `1` |
| Decision Support permission-attempt schema | `decision-support-permission-attempt` | `1` |
| Decision Support evaluation schema | `decision-support-evaluation` | `1` |
| Decision Support evaluation-series-head schema | `decision-support-evaluation-series-head` | `1` |
| Advice currentness policy | `decision-support-advice-currentness` | `1` |
| Advice currentness-operation schema | `advice-currentness-operation` | `1` |
| Advice currentness-check schema | `advice-currentness-check` | `1` |
| Advice currentness-invalidation schema | `advice-currentness-invalidation` | `1` |
| Advice currentness-reason registry | `decision-support-currentness-reasons` | `1` |
| Current-advice render-request schema | `current-advice-render-request` | `1` |
| Current-advice render-result schema | `current-advice-render-result` | `1` |
| Manager authorization-attempt schema | `manager-authorization-attempt` | `1` |
| Authorization currentness-result schema | `authorization-currentness-result` | `1` |
| Subject Driver State schema | `subject-driver-state` | `1` |
| Case Constraint Snapshot schema | `case-constraint-snapshot` | `1` |
| Release-Timing Preview schema | `release-timing-preview` | `1` |
| Composite Compatibility Review schema | `composite-compatibility-review` | `1` |
| Composite compatibility-criteria schema | `composite-compatibility-criteria` | `1` |
| Intervention Library | `core-intervention-library` | `1` |
| Intervention Option schema | `intervention-option` | `1` |
| Driver-Action Link registry | `supplier-congestion-driver-action-links` | `1` |
| Driver-Action Link schema | `driver-action-link` | `1` |
| Monitoring observation registry | `decision-support-monitoring-observations` | `1` |
| Monitoring Observation schema | `monitoring-observation` | `1` |
| Monitoring Escalation Trigger registry | `decision-support-monitoring-escalation-triggers` | `1` |
| Monitoring Escalation Trigger schema | `monitoring-escalation-trigger` | `1` |
| Monitoring match-result schema | `monitoring-match-result` | `1` |
| Monitoring review-request schema | `monitoring-review-request` | `1` |
| Constraint fact registry | `decision-support-constraint-facts` | `1` |
| Constraint rule registry | `decision-support-constraint-rules` | `1` |
| Advisory rubric registry | `decision-support-advisory-rubrics` | `1` |
| Advisory Rubric schema | `advisory-rubric` | `1` |
| Advisory Result schema | `advisory-result` | `1` |
| Benefit policy | `assumption-based-benefit-policy` | `1` |
| Action-cost policy | `declared-case-action-cost` | `1` |
| Comparison policy | `pareto-tradeoff-comparison-policy` | `1` |
| Suppression registry | `decision-support-suppression-reasons` | `1` |
| Language policy | `decision-support-language-policy` | `1` |
| Trade-off selection schema | `tradeoff-selection` | `1` |
| Trade-off selection-delivery-attempt schema | `tradeoff-selection-delivery-attempt` | `1` |
| Trade-off selection-claim schema | `tradeoff-selection-claim` | `1` |
| Trade-off selection-validation-result schema | `tradeoff-selection-validation-result` | `1` |
| Trade-off selection-result schema | `tradeoff-selection-result` | `1` |
| Action Recommendation schema | `action-recommendation` | `1` |
| Digest canonicalization | `canonical-scientific-json` | `v1` |

An unknown identifier, unsupported version, unknown option, unknown
constraint code, unknown response class, unknown link kind, unknown action
mechanism class, unknown Monitoring Escalation Trigger operator or response,
or unknown result code is a Decision Support integrity failure. Runtime never
substitutes a nearest or newer version.

Every schema, registry, policy, library, formula, and other governed version
above has an authoritative immutable version envelope containing its exact
kind, identifier/version, content hash, canonical `published_at`, and
supersession reference or explicit `NOT_APPLICABLE`. The closed table is the
supported identifier/version set; the corresponding hash and publication time
come only from that exact referenced envelope, never from runtime code,
retrieval metadata, or the consuming record. Record-level approval metadata
remains additional to this envelope. For a case-wide version consumed by an active
evaluation, a supported version with `published_at > constraints_as_of`
produces `DECISION_SUPPORT_POLICY_NOT_AVAILABLE_AT_CUTOFF`; an unresolved
temporal comparison produces
`DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`. Runtime does not substitute
the earlier head.

The Intervention Library and Driver-Action Link registry envelopes additionally
form immutable predecessor chains. For an active-driver evaluation at
`constraints_as_of`, the supplied library and link-registry versions must each
be the unique unsuperseded supported head among versions published by that
cutoff. A supplied older head is
`DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED`; a supplied future-published
library or registry version is
`DECISION_SUPPORT_POLICY_NOT_AVAILABLE_AT_CUTOFF`; and a malformed chain or
multiple heads is `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`. Runtime
never chooses by wall-clock retrieval order or silently substitutes another
version.

Every governed predecessor chain in this contract is chronology-valid only
when each predecessor and successor publication time is comparable and
`predecessor.published_at <= successor.published_at`. For a Driver-Action Link,
Monitoring Escalation Trigger, Advisory Rubric, or Composite Compatibility
Review in `APPROVED`, `REJECTED`, or `RETIRED` status, its canonical review
temporal value and immutable review-reference `available_at` must each be
comparable with and no later than the record's `published_at`. A provably
reversed chain, future review, or late review reference is
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; an unresolved required
comparison is `DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`. Runtime never
uses retrieval time, assumes a timezone, or backdates review evidence.

Exact numeric library defaults, approved Driver-Action Link review references,
concrete Monitoring Escalation Trigger observations or thresholds, and
concrete advisory-rubric applicability mappings or thresholds are not invented
by this contract. Candidate content must exist explicitly before the
domain-expert-validation ticket reviews it. Until the required review exists,
a link or Monitoring Escalation Trigger remains `PROVISIONAL`, and an
advisory-rubric declaration remains `UNAVAILABLE_PENDING_REVIEW` or references
a non-approved rubric that can produce only `UNKNOWN`.

## Evaluation identity and input envelope

The upstream Investigation Request field `trigger_mode` has the exact
lowercase values `reactive` or `proactive`. Decision Support uses the closed
normalized codes `REACTIVE` and `PROACTIVE` throughout this contract, with the
only permitted mapping:

```text
reactive  -> REACTIVE
proactive -> PROACTIVE
```

Every structurally valid permission digest and every non-`FAILED` result
preserves both the exact upstream literal and the mapped Decision Support code.
Any other spelling, missing mapping, or disagreement between the two is
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; runtime never case-folds or
guesses a mode.

`subject_identity` is a closed discriminated union:

```text
CANONICAL_ORDER_LINE {
  dataset_version_id,
  order_line_id
}

PROACTIVE_PROPOSAL {
  source_system,
  proposal_id,
  proposal_revision,
  dataset_version_id
}
```

`CANONICAL_ORDER_LINE` is valid only with `trigger_mode = REACTIVE`.
`PROACTIVE_PROPOSAL` is valid only with `trigger_mode = PROACTIVE`. Its
Dataset Version identifies the frozen historical context; it does not make the
proposal a canonical record. Decision Support copies this identity exactly
from the verified upstream Subject Profile chain. It never relinks a proposal,
promotes a preview, or fabricates an Order Line identity.

`subject_driver_state` is a second closed discriminated union:

```text
REACTIVE_CANONICAL {
  state_code = high_load_exposure,
  value: boolean,
  subject_profile_ref_and_hash,
  derivation_evidence_refs
}

PROACTIVE_PREVIEW {
  state_code = provisional_high_load_preview,
  value: boolean,
  subject_profile_ref_and_hash,
  derivation_evidence_refs
}
```

`REACTIVE_CANONICAL` is valid only for `CANONICAL_ORDER_LINE` and
`trigger_mode = REACTIVE`; `PROACTIVE_PREVIEW` is valid only for
`PROACTIVE_PROPOSAL` and `trigger_mode = PROACTIVE`. The referenced Subject
Profile identity, Dataset Version, decision cutoff, state value, and evidence
references must match the verified upstream chain exactly. The state cannot be
manager-attested, copied from a Case Constraint Snapshot, recomputed, or
changed at `constraints_as_of`.

Every request begins as a contract-local permission attempt carrying an opaque
unique `decision_support_permission_attempt_id`. Only a permission-true attempt
creates an opaque unique `decision_support_evaluation_id`; a refusal is not
mislabelled as a Decision Support Evaluation. Every structurally readable
permission envelope derives:

```text
decision_support_permission_digest =
    sha256(canonical-scientific-json.v1({
      permission_schema_and_policy_versions,
      supplied_subject_verdict_ref_and_hash_or_null,
      supplied_population_verdict_ref_and_hash_or_null,
      upstream_trigger_mode,
      trigger_mode,
      requested_use = DECISION_SUPPORT,
      exact_requested_claim_scope
    }))
```

The Population Verdict reference/hash is null only when the supplied Subject
Verdict is the upstream contract's sole permitted null-population case: an
unusable proactive `decision_at` that prevented historical-population
selection, produced `PROACTIVE_SUBJECT_INPUT_UNUSABLE`, and yielded an
`INSUFFICIENT` / `NOT_ESTIMABLE`, permission-false Subject Verdict. Every other
null Population Verdict reference is invalid. The null is explicit and enters
the permission digest; it does not prevent a deterministic `NOT_PERMITTED`
result.

Every permission-true request first derives:

```text
decision_support_driver_state_digest =
    sha256(canonical-scientific-json.v1({
      driver_state_schema_and_policy_versions,
      investigation_request_ref_and_hash,
      subject_verdict_ref_and_hash,
      population_verdict_ref_and_hash,
      exact_permitted_claim_scope,
      subject_identity,
      causal_decision_at,
      upstream_trigger_mode,
      trigger_mode,
      subject_driver_state,
      intervention_library_version
    }))
```

Only a request whose verified Subject Driver State is true proceeds to the
complete active-driver envelope and derives:

```text
decision_support_input_digest =
    sha256(canonical-scientific-json.v1({
      schema_and_policy_versions,
      investigation_request_ref_and_hash,
      subject_verdict_ref_and_hash,
      population_verdict_ref_and_hash,
      exact_permitted_claim_scope,
      exact_effect_and_interval_values,
      subject_identity,
      causal_decision_at,
      subject_driver_state,
      constraints_as_of,
      upstream_trigger_mode,
      trigger_mode,
      case_constraint_snapshot_content,
      release_timing_preview_content_or_null,
      verified_analysis_run_bundle_binding,
      intervention_library_version,
      driver_action_link_versions,
      monitoring_observation_and_escalation_trigger_registry_and_schema_versions,
      monitoring_escalation_trigger_content_or_null,
      constraint_and_advisory_rule_versions,
      cost_inputs,
      benefit_assumptions
    }))
```

Each digest is lower-case `sha256:<hex>` and reuses the exact
`canonical-scientific-json.v1` encoding defined by the executable causal-engine
contract. Upstream finite floats retain that encoding's exact
`f64:<CPython-float.hex()>` strings. Decision Support decimal inputs are
strings prefixed `decimal:` followed by a canonical base-10 decimal:

- no exponent, leading plus sign, grouping separator, whitespace, or redundant
  leading integer zero is permitted;
- an absolute value below one uses exactly one zero before the decimal point;
- any signed zero normalizes to `decimal:0`;
- a non-zero integer has no decimal point; and
- a non-integer has one decimal point, at least one fractional digit, and no
  trailing fractional zero.

Thus `decimal:-0.25`, `decimal:0`, and `decimal:12.34` are canonical, while
`decimal:+1`, `decimal:01`, `decimal:1.0`, and `decimal:1e0` are not.
Timestamps retain their owning contract's canonical UTC representation.

Every plural digest field has one closed representation; discovery, retrieval,
or asynchronous completion order never enters canonical bytes:

- `driver_action_link_versions` is an array with exactly one explicit
  present/missing state per Core option in Intervention Library display order;
- `constraint_and_advisory_rule_versions` is a keyed object whose Constraint
  Rule array is in numeric registry-priority order and whose Advisory Rubric
  entries are in library display order, then the fixed dimension order
  `CONTRACTUAL_RELATIONSHIP_RISK`, `OPERATIONAL_DISRUPTION`, `REVERSIBILITY`;
- `cost_inputs` is a keyed object containing the single case-scoped critical-
  path delay rate state once, followed by an option-cost array in library
  display order;
- `benefit_assumptions` is an array in library display order; within an option,
  fields use the fixed schema-key order and explicit `NOT_APPLICABLE` or
  missing states rather than omission;
- registry/schema version groups are fixed-key objects in the key order shown
  by the governing schema, never free-form maps; and
- a nested semantic set of references is sorted by canonical bytes of
  `{reference_type, id, version_or_null, content_hash}`, while a list whose
  owning registry declares semantic order retains exactly that declared order.

The Case Constraint Snapshot orders case-scoped facts by fact-registry order,
then option/component-scoped facts by Intervention Library display order,
component path, and fact-registry order. Duplicate logical keys fail snapshot
schema validation. These rules apply recursively before hashing; no
implementation may sort a semantically ordered array lexically or preserve an
unordered container's iteration order.

Every Decision Support-authored decimal input has at most 20 integer digits and
18 fractional digits, at most 38 coefficient digits total, and absolute value
strictly less than `10^20`. Every Decision Support-authored integer input used
as an arithmetic or comparison value has at most 20 decimal digits and the
same absolute-value bound. A required case-wide numeric input outside this
closed domain is an arithmetic-domain failure. An option-conditional cost,
rate, benefit assumption, or constraint fact outside the domain uses its
existing option-suppression or `UNKNOWN` rule before arithmetic. Runtime never
truncates or rounds a value into the domain.

An upstream finite `f64:` retains the upstream type's fixed binary domain and
is not rejected merely because its exact decimal expansion exceeds these input
digit limits. Derived values are canonical reduced rationals governed by the
4,096-bit resource limit below; they are not reparsed through the decimal-input
scale bound.

All three digests exclude the permission-attempt ID, evaluation occurrence ID,
evaluation-series ID, predecessor/current-head metadata, execution timestamp,
actor display name, UI route, presentation order, drafted prose, Manager
Decision, and audit storage location. Two occurrences may share a digest but
never share an occurrence ID of the same kind.

Every permission-true Decision Support workflow has one opaque
`decision_support_evaluation_series_id`, bound to the exact upstream
Investigation Request, subject identity, causal `decision_at`, and trigger
mode. A new constraint snapshot, cost, or benefit assumption creates a
successor evaluation in the same series; a new upstream request, subject, or
causal cutoff creates a new series.

Each permission-true evaluation records its nullable predecessor occurrence
ID and canonical `evaluation_published_at`, fixed by the first successful atomic
evaluation/result/head publication and returned unchanged on replay. A logical
authoritative series-head projection has exactly one closed kind:

| Head kind | Meaning |
| --- | --- |
| `EVALUATION` | Points to the latest successfully published permission-true evaluation occurrence and applicable digest, including an inactive-driver occurrence |
| `PERMISSION_INVALIDATION` | Points to a later immutable `NOT_PERMITTED` permission-attempt result that invalidates the predecessor after an authoritative upstream evidence downgrade |
| `EVIDENCE_INTEGRITY_INVALIDATION` | Points to a later immutable `FAILED` integrity-invalidation result after an authoritative source explicitly invalidates an artifact referenced by the current advice chain |
| `ADVICE_CURRENTNESS_INVALIDATION` | Points to a later immutable currentness-invalidation result after a governed dependency ceases to be current, an operational fact expires, or a required currentness comparison becomes unresolved |

Publishing a successor advances that head without mutating an earlier
evaluation. When a later authoritative Subject or Population Verdict explicitly
supersedes a verdict referenced by a series and makes Decision Support
permission false, Decision Support must publish a `PERMISSION_INVALIDATION`
head for every affected series. It never infers supersession merely from a
similar subject or a newer wall-clock timestamp; the upstream predecessor
reference and content hash are required. The
prior evaluation and Action Recommendation remain immutable history but are no
longer current and cannot be selected, authorized, or rendered as current
advice. A later return to supported evidence requires a new permission-true
evaluation occurrence; it never reactivates an old head.

Likewise, when an authoritative owning record explicitly quarantines, revokes,
suppresses, or declares corrupt an evidence bundle, read model, validation
result, Governance Trade-off Selection occurrence, accepted selection claim,
Action Recommendation dependency, or other content-hash-bound artifact
referenced anywhere in the current evaluation-to-advice chain, Decision Support
must publish an
`EVIDENCE_INTEGRITY_INVALIDATION` head for every affected series. The
invalidation requires the exact predecessor head, invalidated artifact
reference/hash, authoritative invalidation reference/hash, and a registered
reason. It is never inferred from a later timestamp, retrieval failure, or
similar identifier. The prior evaluation and recommendation remain immutable
history but are no longer current or actionable; restored or replacement
evidence requires a new permission-true evaluation.

An invalidated post-evaluation selection or recommendation dependency also
marks the per-evaluation selection claim non-current. A new delivery attempt
for that selection no longer returns its recommendation because authoritative-
head validation returns `TRADEOFF_SELECTION_STALE`. Exact replay of an already
terminal delivery attempt returns only its immutable historic result and does
not make the claim current. The claim and recommendation remain audit history.
Recovery requires a new permission-true evaluation and,
when that result is a trade-off, a new Governance selection; runtime never
reuses or silently repairs the invalidated claim.

### Advice currentness and expiry

Currentness is proved at one exact operation time; it is never a timeless
boolean copied onto an evaluation or Action Recommendation. Every successfully
published `EVALUATION` head contains:

- an ordered `advice_currentness_dependency_set` containing exact references,
  versions, and content hashes for every governed library, option, link, rule,
  rubric, trigger, composite review, and other governed record whose resolution
  or content affected the terminal result, including the exact lifecycle
  disposition observed by the evaluation;
- every eligible operational fact, cost, and assumption actually consumed by
  option evaluation, value calculation, comparison, or monitoring eligibility,
  with its exact validity horizon and provenance; and
- `advice_valid_through`, derived from those consumed operational inputs as
  described below.

Every consumed operational input has one explicit closed validity horizon:

```text
valid_through = NO_EXPIRY | <finite canonical-lineage TemporalValue>
```

`NO_EXPIRY` is an explicit provenance-bearing source declaration or valid
Manager Attestation, never null, omission, or a runtime default. A finite
horizon is inclusive. The input is current at an exact time `t` only when
`t <= valid_through` is provable under the canonical temporal partial order.
At original evaluation, an input whose finite horizon is earlier than
`constraints_as_of`, or whose comparison with that cutoff is unresolved, is
not eligible evidence and follows its existing `UNKNOWN`, suppression, or
case-wide failure rule; runtime never extends its horizon.

`advice_valid_through` is the earliest finite horizon in the consumed
operational-input set. It is `NO_EXPIRY` only when every consumed operational
input explicitly declares `NO_EXPIRY`, including when the set is empty. All
finite horizons needed to derive the minimum must be mutually comparable. If
no unique earliest finite horizon can be proved, the evaluation cannot publish
an `EVALUATION` head and returns
`DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`.

Every governed dependency record carries exactly one closed `dependency_kind`.
Currentness applies the kind-specific predicate below; it never tests a status
literal that the owning schema does not define:

| Dependency kind | Consumed record | Required state at `currentness_checked_at` |
| --- | --- | --- |
| `GOVERNED_VERSION_ENVELOPE` | Policy, schema, registry, constraint-rule, language, digest, benefit, cost, comparison, suppression, or reviewed formula version | The exact identifier/version/hash remains supported. When its envelope declares predecessor, supersession, retirement, review, or applicability fields, no effective successor or retirement exists, the exact consumed disposition is unchanged, and a formula that produced a known result remains approved and applicable. No generic `ACTIVE` or `APPROVED` field is required. |
| `INTERVENTION_LIBRARY_VERSION` | Exact Intervention Library version | It remains the unique unsuperseded supported library head published by the check time. |
| `INTERVENTION_OPTION_VERSION` | Exact option version in the effective library | The exact option/version remains the effective library mapping with the consumed `ACTIVE` or `RETIRED` disposition; an option that supported an eligible result must remain `ACTIVE`. |
| `DRIVER_ACTION_LINK_VERSION` | Exact link for driver, option/version, and trigger mode | It remains the unique unsuperseded effective link and retains the consumed `PROVISIONAL`, `APPROVED`, or `REJECTED` review status; a link that supported an eligible result must remain `APPROVED`. |
| `MONITORING_ESCALATION_TRIGGER_VERSION` | Exact trigger for option/version and trigger-mode applicability | It remains the unique unsuperseded applicable trigger, retains the consumed lifecycle status, and, when it supported monitoring eligibility, remains `APPROVED`, fully specified, and not `RETIRED`. |
| `ADVISORY_RUBRIC_VERSION` | Exact rubric for dimension, option/version, and trigger mode | It remains the unique unsuperseded applicable rubric and retains the consumed `PROVISIONAL`, `APPROVED`, or `REJECTED` status; a rubric that produced a known ordinal must remain `APPROVED`. |
| `COMPOSITE_COMPATIBILITY_REVIEW_VERSION` | Exact subject/snapshot/composite/link/trigger-bound review result | It remains the unique unsuperseded identity-matching result and retains the consumed lifecycle status; a result that made compatibility `SATISFIED` or `UNSATISFIED` must remain `APPROVED` and fully specified. |

The dependency set records the exact fields needed by its row's predicate,
including applicability and consumed disposition or explicit
`NOT_APPLICABLE`. An unknown kind, missing required field, or attempt to apply
one row's status vocabulary to another kind is a currentness comparison that
cannot be proved and fails closed.

Every currentness-gated use presents one immutable
`advice-currentness-operation` version `1` envelope before the check. Only an
intrinsically valid envelope may be atomically claimed as an operation
occurrence. It contains a stable operation occurrence ID and content hash; one closed
`operation_kind`; the exact evaluation-series, evaluation occurrence, terminal
result, branch-closed recommendation reference/hash or null, and accepted
selection-claim reference/hash or null being used; one immutable operation-
payload reference/hash; and `currentness_checked_at`. The operation payload and
advice-chain cardinality have this closed mapping:

| `operation_kind` | Required operation payload | Recommendation in operation | Accepted selection claim in operation |
| --- | --- | --- | --- |
| `CURRENT_ADVICE_RENDER` | Exact immutable render-request occurrence reference/hash | Exactly the request's branch-correct recommendation reference/hash or null | Non-null exactly for an `ACCEPTED_TRADEOFF_SELECTION` request; otherwise null |
| `TRADEOFF_SELECTION_ACCEPTANCE` | Exact immutable trade-off selection-delivery-attempt occurrence reference/hash | Always null because this operation creates, rather than consumes, a recommendation | Always null because this operation creates, rather than consumes, the claim |
| `MANAGER_AUTHORIZATION` | Exact immutable Governance & Audit authorization-attempt occurrence reference/hash created before any Manager Decision | Exactly one non-null recommendation matching the attempt | Non-null exactly when that recommendation's selection basis is `MANAGER_TRADEOFF_SELECTION`; otherwise null |
| `MONITORING_TRIGGER_MATCH` | Exact Monitoring Observation occurrence reference/hash | Exactly one non-null `ACCEPT_AND_MONITOR` recommendation | Non-null exactly when that recommendation's selection basis is `MANAGER_TRADEOFF_SELECTION`; otherwise null |

For every non-null accepted selection claim, its schema is exactly
`tradeoff-selection-claim.v1` and its evaluation, result, selection,
recommendation key/reference/hash, candidate, and creation-currentness proof
must agree with the complete chain. No consumer discovers or chooses this field
after claiming an operation; the table above fixes it before the deterministic
operation key is derived. A non-null claim is current only while it remains the
one exact per-evaluation claim, its recommendation and creation proof match,
and the same evaluation remains the authoritative `EVALUATION` head. An
integrity invalidation of the claim or recommendation advances the head and
therefore makes every new consuming operation stale.

The operation time is fixed by payload kind: render-request `available_at`,
trade-off selection-delivery-attempt `available_at`, authorization-attempt
`available_at`, or Monitoring Observation `available_at`, respectively. It must equal
`currentness_checked_at` exactly. Each payload owns a canonical event/request
time that must be provably no later than its verified `available_at`. Runtime
never substitutes processing time, accepts a caller-supplied earlier cutoff, or
backdates an operation.

A `current-advice-render-request` version `1` contains a stable request
occurrence ID and content hash; `render_mode = CURRENT_ADVICE`; exact evaluation-
series, evaluation occurrence/digest, immutable evaluation terminal-result
reference/hash, one closed `advice_chain_kind`, a branch-correct recommendation
reference/hash or null, and an accepted selection-claim reference/hash or null;
canonical `advice_chain_published_at`, `requested_at`; and verified
`available_at`. The chain mapping is:

| `advice_chain_kind` | Evaluation result | Recommendation | Accepted selection claim |
| --- | --- | --- | --- |
| `EVALUATION_ONLY_NO_RECOMMENDATION` | `NO_ELIGIBLE_OPTION`, or an unresolved `TRADEOFF_REQUIRES_MANAGER_CHOICE` | Null | Null |
| `IMMEDIATE_EVALUATION_RECOMMENDATION` | `RECOMMENDATION_AVAILABLE` | Exact one result-bound recommendation | Null |
| `ACCEPTED_TRADEOFF_SELECTION` | `TRADEOFF_REQUIRES_MANAGER_CHOICE` | Exact one manager-selected recommendation | Exact one current `tradeoff-selection-claim.v1` that binds this evaluation result, the accepted selection/candidate, and that recommendation |

The immutable evaluation result remains unchanged after manager selection; the
third row is the sole renderable chain for the selected side record. A claim or
recommendation that is missing, multiple, cross-evaluation, hash-mismatched, or
not current makes the request invalid. `advice_chain_published_at` equals
`evaluation_published_at` for the first two rows and the accepted selection
claim's `published_at` for the third. The request requires the complete
provable order
`advice_chain_published_at <= requested_at <= available_at`, and
`currentness_checked_at = available_at`; neither time is caller-editable. Its
deterministic logical key is:

```text
current_advice_render_request_key =
    sha256(canonical-scientific-json.v1({
      schema_identifier_and_version,
      render_mode,
      evaluation_series_id,
      evaluation_occurrence_id,
      evaluation_digest,
      terminal_result_ref_and_hash,
      advice_chain_kind,
      recommendation_ref_and_hash_or_null,
      accepted_selection_claim_ref_and_hash_or_null,
      advice_chain_published_at,
      requested_at,
      available_at
    }))
```

Exactly one logical render-request occurrence/reference/hash exists per request
key; exact redelivery returns it and conflicting content is invalid.

A successful render publishes one `current-advice-render-result` version `1`
with stable occurrence ID, content hash, exact request reference/hash, exact
evaluation-result and branch-correct advice-chain projection,
`current_as_of = currentness_checked_at`, and the bound
currentness-operation/check references/hashes. Its deterministic result key is
exactly:

```text
current_advice_render_result_key =
    sha256(canonical-scientific-json.v1({
      render_request_ref_and_hash,
      currentness_operation_ref_and_hash,
      currentness_check_ref_and_hash
    }))
```

Exactly one logical render-result occurrence/reference/hash exists per result
key.

The check and render result publish atomically under the operation's
terminal claim and final exact-head comparison; a concurrent successor leaves
no successful check or render result. The result cannot add generated prose or
change the frozen evaluation.

A `tradeoff-selection-delivery-attempt` version `1` is a distinct immutable
occurrence for one delivery of an already immutable Governance & Audit Trade-
off Selection. It contains a stable attempt occurrence ID, content hash, and
exact schema identifier/version; the exact Trade-off Selection reference/hash;
the exact evaluation-series ID, evaluation occurrence/digest, terminal-result
reference/hash, and selected-candidate reference copied from and equal to that
selection; canonical `delivered_at`; and verified `available_at`. It requires
the cross-record order
`selection.available_at <= delivered_at <= available_at` to be provable under
the canonical temporal partial order, and
`currentness_checked_at = available_at`; neither time is caller-editable. Its
deterministic logical key is:

```text
tradeoff_selection_delivery_attempt_key =
    sha256(canonical-scientific-json.v1({
      schema_identifier_and_version,
      tradeoff_selection_ref_and_hash,
      evaluation_series_id,
      evaluation_occurrence_id,
      evaluation_digest,
      terminal_result_ref_and_hash,
      selected_candidate_ref,
      delivered_at,
      available_at
    }))
```

Exactly one logical delivery-attempt occurrence/reference/hash exists per
attempt key. Exact network replay of that same hash-bound attempt returns the
existing attempt and, after processing, its one immutable terminal result. A
later delivery of the same Trade-off Selection is a new delivery attempt with
its own authoritative delivery and availability times, operation key, and
currentness check. Conflicting content under one attempt key is invalid.

A `manager-authorization-attempt` version `1` contains a stable attempt
occurrence ID and content hash; `requested_disposition = APPROVE`; exactly one
evaluation-series ID, evaluation occurrence/digest, terminal-result
reference/hash, and non-null Action Recommendation reference/hash; the exact
accepted selection-claim reference/hash when that recommendation has
`selection_basis = MANAGER_TRADEOFF_SELECTION`, otherwise null; an immutable
manager actor reference; canonical `advice_chain_published_at`, `requested_at`;
and verified `available_at`.
The recommendation must be the exact one bound to that evaluation result;
zero, multiple, cross-evaluation, or hash-mismatched recommendations are
invalid. The accepted selection claim must satisfy the operation-kind
cardinality table and match the recommendation's selection basis and complete
chain exactly. `advice_chain_published_at` equals the evaluation's
`evaluation_published_at` for an immediate recommendation and the accepted
selection claim's `published_at` for a manager-selected one. It requires the
complete provable order
`advice_chain_published_at <= requested_at <= available_at`, and
`currentness_checked_at = available_at`; neither time is caller-editable. Its
deterministic logical key is:

```text
manager_authorization_attempt_key =
    sha256(canonical-scientific-json.v1({
      schema_identifier_and_version,
      requested_disposition,
      evaluation_series_id,
      evaluation_occurrence_id,
      evaluation_digest,
      terminal_result_ref_and_hash,
      recommendation_ref_and_hash,
      accepted_selection_claim_ref_and_hash_or_null,
      manager_actor_ref,
      advice_chain_published_at,
      requested_at,
      available_at
    }))
```

Exactly one logical authorization-attempt occurrence/reference/hash exists per
attempt key; exact redelivery returns it and conflicting content is invalid.

A successful authorization-currentness check publishes one
`authorization-currentness-result` version `1` owned by Decision Support. It
has a stable occurrence ID and content hash;
`authorization_currentness = PROVEN`; the exact authorization-attempt,
evaluation/result, Action Recommendation, and branch-correct accepted
selection-claim references/hashes; `current_as_of = currentness_checked_at =
authorization_attempt.available_at`; the exact `manager_actor_ref` copied from
the attempt; and the bound currentness-operation/check references/hashes. It
may not accept a second actor or override any copied field. Its deterministic
result key is exactly:

```text
authorization_currentness_result_key =
    sha256(canonical-scientific-json.v1({
      authorization_attempt_ref_and_hash,
      recommendation_ref_and_hash,
      accepted_selection_claim_ref_and_hash_or_null,
      manager_actor_ref,
      currentness_operation_ref_and_hash,
      currentness_check_ref_and_hash
    }))
```

Exactly one logical authorization-currentness result occurrence/reference/hash
exists per result key.

The check and authorization-currentness result publish atomically under
the operation's terminal claim and final exact-head comparison; a concurrent
successor leaves no successful check or result. The result proves only that
the exact authorization attempt could use the named advice at that operation
time; it is not a Manager Decision, approval record, or execution claim.

Governance & Audit alone may record the resulting Manager Decision. An
authorizing decision may be created only from one exact
`authorization-currentness-result.v1` with `PROVEN`; it derives, without
override, the attempt's `requested_disposition`, recommendation, accepted
selection claim or null, evaluation/result identity, `manager_actor_ref`, and
`decided_at = authorization_attempt.available_at =
authorization_currentness_result.current_as_of`. It retains the result and its
operation/check proof. A
mismatch in any duplicated field, zero or multiple proof results, or a failed
currentness operation permits no authorizing Manager Decision. Governance &
Audit owns that decision occurrence and its append-only persistence. Its
downstream logical identity must include the exact authorization-attempt and
authorization-currentness-result references/hashes, attempt-derived
disposition, recommendation, accepted selection claim or null,
`manager_actor_ref`, and that exact `decided_at`; omitting or overriding the actor
cannot produce the same decision identity. Later append-only persistence merely
records that already time-bound decision event; replay of an old `PROVEN`
result cannot express a new authorization after advice changes. New
authorization intent requires a new attempt and currentness operation.

The occurrence carries this deterministic logical key:

```text
currentness_operation_key =
    sha256(canonical-scientific-json.v1({
      currentness_policy_identifier_and_version,
      operation_kind,
      evaluation_series_id,
      evaluation_occurrence_id,
      terminal_result_ref_and_hash,
      recommendation_ref_and_hash_or_null,
      accepted_selection_claim_ref_and_hash_or_null,
      operation_payload_ref_and_hash,
      currentness_checked_at
    }))
```

Exactly one logical currentness-operation occurrence, reference, and content
hash exists per `currentness_operation_key`. Creation atomically claims an
absent key with that exact occurrence. Redelivery of the same hash-bound tuple
must return the existing occurrence/reference/hash and cannot create another;
different content under an existing key is an integrity failure. Changing any
tuple field creates a distinct operation key and requires a new claim. Issue
#12 owns the physical uniqueness mechanism but may not weaken this logical
cardinality.

The operation occurrence does not contain a currentness-check reference, so
its hash is acyclic. Its subject, series, evaluation, result, recommendation,
accepted selection claim, payload type, and check time must agree exactly with
its bound use. A malformed
proposed envelope fails before an operation occurrence is claimed. Presenting
a valid stored operation to any different consumer, kind, payload, subject,
series, evaluation, result, recommendation, or check time is an invocation
mismatch; it cannot claim that operation's terminal result or prevent its
later exact bound use.

Before any evaluation result or recommendation is rendered as current, before
a trade-off selection is accepted, before a Manager Decision may authorize a
recommended action, and before a monitoring predicate may emit a review
request, Decision Support performs one currentness check at an immutable,
canonical `currentness_checked_at`. The check time is the authoritative time
of that operation and cannot be caller-selected or backdated. The check is
bound to the exact `operation_kind` and currentness-operation reference/hash;
no other operation may consume it. It resolves one exact expected evaluation
head from the advice being checked, then follows this total procedure:

1. Validate the proposed immutable operation envelope intrinsically, including
   its required fields, content hash, deterministic key, closed operation kind,
   and kind-specific payload shape. A failure returns
   `CURRENTNESS_OPERATION_INVALID`, claims no operation occurrence or terminal
   result, publishes no currentness-check occurrence, denies the use, and
   mutates no series head.
2. Atomically claim or resolve the one valid currentness-operation occurrence
   under its deterministic key. Different valid content under an existing key
   is an integrity failure and cannot replace or terminate the existing
   occurrence.
3. Verify that the attempted consumer and use context exactly equal the stored
   operation's bound kind, payload, subject, series, evaluation, result,
   recommendation, accepted selection claim, and check time. A cross-use difference returns
   `CURRENTNESS_OPERATION_MISMATCH`, claims no terminal result, publishes no
   currentness-check occurrence, denies the use, mutates no series head, and
   leaves the valid operation available to its exact bound consumer.
4. If that exact valid bound operation's terminal claim already exists, return
   its exact terminal check and consuming result or refusal without re-reading
   any current state, then stop.
5. Load the authoritative series head once. If it is not the exact expected
   `EVALUATION` occurrence/digest/result hash, atomically claim
   `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` with the observed head, deny the
   attempted use, publish no invalidation or consuming result, and stop.
6. Apply every dependency-kind predicate above at
   `currentness_checked_at`.
7. Prove `currentness_checked_at <= advice_valid_through` when the horizon is
   finite and the same comparison for every consumed finite operational
   horizon.
8. Stage either `CURRENTNESS_PROVEN_AT_CHECK` plus the kind-specific consuming
   result, or `ADVICE_CURRENTNESS_INVALIDATION` plus its invalidation head and
   `FAILED` result.
9. In one logical compare-and-use/publish operation, require both that the
   currentness-operation terminal claim is still absent and that the exact
   expected `EVALUATION` remains the authoritative head. For success, publish
   the check occurrence and consuming result together. For invalidation,
   publish the invalidation occurrence/result and replacement head together.
   Only then does either outcome exist.
10. If the final head comparison loses to a concurrent successor, publish none
   of the staged records, load the head exactly once more, and atomically claim
   `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` with that successor and no consuming
   result. If any terminal-claim race loses, return the one winning terminal
   claim. The procedure never retries, never creates a second terminal result,
   and never re-evaluates the same operation against changed state.

The closed currentness invocation/check results are therefore as follows. The first two
are pre-check invocation refusals and never create a terminal claim or an
`advice-currentness-check` occurrence; the remaining results are terminal for
one exact valid bound operation:

| Check result | Meaning |
| --- | --- |
| `CURRENTNESS_OPERATION_INVALID` | The proposed operation envelope is intrinsically missing, malformed, hash-mismatched, deterministically key-mismatched, or has an invalid kind-specific payload shape; no operation or terminal claim is created, no advice is used, and no series head is mutated |
| `CURRENTNESS_OPERATION_MISMATCH` | A valid stored operation is presented through a different consumer or use context than its exact bound kind/payload tuple; no terminal claim is created, the valid operation is not poisoned, no advice is used, and no series head is mutated |
| `CURRENTNESS_PROVEN_AT_CHECK` | The named evaluation was the exact head and all kind-specific lifecycle and operational-horizon checks passed at the check time |
| `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` | The named evaluation was already not the exact head, or the invalidation compare-and-publish lost to a successor; no newer head is mutated |
| `ADVICE_CURRENTNESS_INVALIDATION` | The named evaluation was the exact head, one or more closed invalidation reasons applied, and the compare-and-publish installed the invalidation head |

Each valid currentness-operation key, when invoked through its exact bound
consumer, has one logical terminal claim, initially absent and thereafter
immutable:

```text
currentness_operation_terminal_claim = {
  currentness_operation_key,
  currentness_operation_ref_and_hash,
  currentness_check_key,
  terminal_currentness_ref_and_hash,
  currentness_outcome,
  observed_authoritative_head_ref_and_hash,
  consuming_result_kind,
  consuming_result_ref_and_hash_or_null,
  refusal_result_ref_and_hash_or_null,
  installed_invalidation_head_ref_and_hash_or_null
}
```

For `CURRENTNESS_PROVEN_AT_CHECK`, `consuming_result_kind` and its non-null
reference/hash are determined only by this closed mapping and publish atomically
with the check:

| Operation kind | Consuming result |
| --- | --- |
| `CURRENT_ADVICE_RENDER` | Exactly one `current-advice-render-result` version `1` |
| `TRADEOFF_SELECTION_ACCEPTANCE` | Exactly one `tradeoff-selection-result` version `1`; an accepted new selection also atomically publishes its selection claim and Action Recommendation, while an idempotent result references the existing recommendation |
| `MANAGER_AUTHORIZATION` | Exactly one `authorization-currentness-result` version `1`; Governance & Audit may separately record the Manager Decision only from this exact `PROVEN` result |
| `MONITORING_TRIGGER_MATCH` | Exactly one `monitoring-match-result` version `1`, which contains either `NO_REVIEW_REQUEST` with a null request or `REQUEST_MANAGER_REVIEW` with exactly one request reference/hash |

Every other terminal currentness outcome has
`consuming_result_kind = NOT_APPLICABLE`
and a null consuming-result reference/hash. A
`TRADEOFF_SELECTION_ACCEPTANCE` refusal additionally stores exactly one
`tradeoff-selection-result` reference/hash with the applicable closed refusal
code; all other refusal-result fields are null in Core. Exactly one logical
terminal claim exists per operation key. The terminal claim, check or
invalidation occurrence, consuming or refusal result, any selection/
recommendation/request side record, and any installed invalidation head have
all-or-nothing logical visibility. Issue #12 owns the physical transaction/
replay implementation but may not split this atomicity or cardinality.

Every permitted operation result retains both the exact currentness-operation
reference/hash and the exact successful currentness-check reference/hash. This
means the current render response, an accepted selection claim and its
manager-selected Action Recommendation, an authorization-currentness result, and
a monitoring review request each carry the proof bound to themselves. The
operation kind and reference/hash in the check must equal the consuming result.
A redelivery of the same operation occurrence must return its one existing
terminal check and consuming result or refusal without re-reading current
state. A different occurrence, operation kind, payload, evaluation,
recommendation, accepted selection claim, or check time requires a new
currentness operation and check.
A render check can never authorize, select, or fire monitoring, and no operation
may consume an unreferenced or differently bound success.

For currentness hashing, governed dependencies are ordered by canonical bytes
of `{dependency_kind, id, version, content_hash}`. Consumed operational
horizons are ordered by their unique canonical input path within the frozen
evaluation envelope. The check derives:

```text
currentness_evidence_digest =
    sha256(canonical-scientific-json.v1({
      currentness_policy_identifier_and_version,
      operation_kind,
      currentness_operation_ref_and_hash,
      evaluation_series_id,
      predecessor_head_occurrence_id,
      predecessor_head_digest,
      predecessor_result_hash,
      accepted_selection_claim_ref_and_hash_or_null,
      observed_authoritative_head_kind_and_ref_and_hash,
      currentness_checked_at,
      advice_valid_through,
      ordered_governed_dependency_resolutions,
      ordered_consumed_operational_horizons,
      currentness_outcome,
      ordered_currentness_reasons
    }))
```

For a structurally valid operation, the logical check key is:

```text
currentness_check_key =
    sha256(canonical-scientific-json.v1({
      currentness_operation_key
    }))
```

Exactly one logical terminal currentness occurrence exists per check key. Its
content records the one evidence digest and outcome that won the operation's
terminal claim. Replay of that operation must return the same occurrence and
consuming result or refusal without recomputing current state. A later check,
including one after a head, dependency, or horizon change, requires a new
currentness operation with a different operation time or payload and therefore
a different operation and check key.

For a structurally valid operation, `operation_kind` and the exact immutable
currentness-operation reference/hash are always present. For success,
`currentness_outcome = CURRENTNESS_PROVEN_AT_CHECK`, the observed
head equals the expected predecessor, and the reason array is empty. For an
installed invalidation, `currentness_outcome = ADVICE_CURRENTNESS_INVALIDATION`
and the ordered reason array is non-empty. For a pre-existing or racing
successor, `currentness_outcome = CURRENTNESS_NOT_AUTHORITATIVE_HEAD`, the
observed successor head is exact, and the invalidation-reason array is empty
because no invalidation was installed by this check. Only the newly created
currentness-check or currentness-invalidation occurrence ID is excluded from
this digest. The expected predecessor occurrence ID and the bound operation
occurrence ID enter through the explicit fields above. Processing order,
display labels, and retrieval order do not enter the digest.

A `CURRENTNESS_PROVEN_AT_CHECK` or `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` result
records an immutable `advice-currentness-check` version `1` occurrence with
stable occurrence ID, deterministic `currentness_check_key`, content hash,
exact check result/time, operation kind, currentness-operation reference/hash,
expected evaluation-head reference/hash,
observed authoritative-head reference/hash, resolved dependency references/
hashes when evaluated, the accepted selection-claim reference/hash or null,
and the currentness-evidence digest. A successful
occurrence proves currentness only for that exact hash-bound operation at that
time. A stale-head occurrence proves only refusal and cannot be reused as
success. `CURRENTNESS_OPERATION_INVALID` and
`CURRENTNESS_OPERATION_MISMATCH` create no currentness-check occurrence or
digest. `NO_EXPIRY` bypasses only the operational-expiry
comparison; it never bypasses operation binding, kind-specific governed-
dependency, or authoritative-head checks.

A dependency, expiry, or comparison failure found while the expected
evaluation remains the exact head attempts an `ADVICE_CURRENTNESS_INVALIDATION`
through the single compare-and-publish above. All applicable invalidation
reasons are retained in this closed order; the first is primary:

| Priority | Currentness reason | Condition |
| ---: | --- | --- |
| 100 | `GOVERNED_DEPENDENCY_NOT_CURRENT` | A consumed governed record fails its exact `dependency_kind` predicate, including a changed disposition, an effective successor, or loss of the kind-specific eligible-support state |
| 200 | `OPERATIONAL_FACT_EXPIRED` | The check time is provably later than one or more consumed finite validity horizons |
| 300 | `CURRENTNESS_COMPARISON_UNRESOLVED` | A required comparison among the check time, advice horizon, input horizon, or governed lifecycle time cannot establish the required order |

The immutable `advice-currentness-invalidation` version `1` occurrence records
its stable occurrence ID and content hash; the exact predecessor head,
evaluation, result, recommendation or null, and accepted selection-claim or
null references/hashes; `currentness_checked_at`; prior
`advice_valid_through`; the bound operation kind and currentness-operation
reference/hash; the ordered reasons; every offending dependency or horizon;
and the currentness-evidence digest. A concurrent successor prevents
publication against the older predecessor and terminates as
`CURRENTNESS_NOT_AUTHORITATIVE_HEAD` after the one required re-read; the newer
head is never invalidated by the losing operation.

The prior evaluation, candidates, selection claim, and Action Recommendation
remain immutable audit history but immediately cease to be current, selectable,
authorizable, or renderable as current advice. A new delivery attempt or other
new currentness-gated use of that predecessor is stale, not idempotent success.
Exact replay of an operation that already reached a terminal result returns
that immutable historic result but does not establish a new current use. Only
a fresh permission-true evaluation using a fresh
Case Constraint Snapshot and currently effective governed dependencies can
restore current advice; an old head is never reactivated.

The audit/persistence ticket owns the physical table, transaction, and replay
implementation; this contract owns the logical current-head and invalidation
semantics.

The permission-true Subject Driver State envelope includes:

- one verified Subject Verdict and its Population Verdict reference;
- the exact upstream Investigation Request reference and content hash;
- the exact Subject Verdict role, claim scope, effect display, trigger list,
  and Decision Support permission;
- exact discriminated subject identity, causal `decision_at`, upstream trigger
  mode literal, mapped Decision Support trigger mode, and Subject Driver State;
- the Subject Driver State schema/policy and supported Intervention Library
  version; and
- evidence references and content hashes for the upstream Subject Profile and
  every driver-state derivation input.

Only an active-driver request adds the complete option-evaluation envelope:

- operational `constraints_as_of`;
- all identifiers and versions in the closed registry above;
- one verified sealed Analysis Run bundle binding containing the exact
  `analysis_run_id`, bundle reference and manifest hash, scientific request
  digest, canonical `engine_request` descriptor object hash, and producer
  schema/version; the binding must be the artifact/verdict evidence-chain run
  that supplied the exact Subject Profile and effect values;
- one Case Constraint Snapshot;
- the exact Release-Timing Preview content when one is supplied, otherwise
  null;
- exact option-scoped costs and benefit assumptions; and
- evidence references, content hashes, and verified availability times for
  every external evidence/read-model record.

Every case-wide verified evidence or read-model record consumed by an active
evaluation must have a verified `available_at <= constraints_as_of`. A record
that became available later cannot be backdated through `known_at`, copied from
the UI, or used to retime causal evidence. Option-scoped facts apply the same
availability rule through their Constraint Result or input-suppression policy.
The explicit later-recorded Manager Attestation rule below remains the sole
exception: it may attest that an operational fact was known by the cutoff, but
cannot attest that a late-created upstream evidence/read-model record was
available earlier.

## Global permission, integrity, and outcome boundary

### Permission gate

The service first validates the supplied verified verdict read model's schema,
identity, content hash, and internal consistency. A failure at that boundary
is `FAILED`.

When no Subject Verdict exists, exactly one refusal branch is valid: a
verified Population Verdict whose `intended_role` is
`out_of_domain_validation` and whose subject-application and Decision Support
role permissions are both false produces `NOT_PERMITTED`. It references that
Population Verdict and its registered role-limitation next step, evaluates no
option, and never fabricates a Subject Verdict. Any other Population
Verdict-only request is `FAILED`.

For an otherwise valid verdict,
`decision_support_evaluation_permitted = false` produces `NOT_PERMITTED`
before any option is evaluated. The request cannot override that verdict.
This includes valid Tentative, Association Only, Insufficient, and
out-of-domain role cases.

Only a verdict whose permission is true proceeds to the Subject Driver State
check. It must satisfy all of:

```text
subject_verdict.scope == subject
subject_verdict.schema_identifier == evidence-verdict
subject_verdict.schema_version == 2
subject_verdict.verdict_code == SUPPORTED_UNDER_ASSUMPTIONS
subject_verdict.effect_display == CAUSAL_ESTIMATE
subject_verdict.decision_support_evaluation_permitted == true
subject_verdict.decision_support_role_permitted == true
subject_verdict.intended_role == semi_synthetic_hero
resolved_subject_identity(subject_verdict) == input.subject_identity
subject_verdict.decision_at == input.causal_decision_at
population_verdict.schema_identifier == evidence-verdict
population_verdict.schema_version == 2
```

`resolved_subject_identity` means the exact identity on the verified
Subject Profile referenced through the Subject Verdict and engine result. It
is a dereference-and-compare operation, not a heuristic lookup or mutable
business-key match.

The effect estimate and its interval must be present, finite, denominated in
Supplier Milestone Slippage days under the exact sealed
`causal-engine-suite-request.v2` `canonical_slippage_duration_basis`, and
satisfy:

```text
0 < interval_lower <= effect_estimate <= interval_upper
```

The corresponding `causal-engine-suite-result.v2` duration basis and every
released Estimator Row basis must equal that request-wide value. An older
engine input/output schema is unsupported; a missing basis or request/result/
row mismatch is `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`. An upstream
`SLIPPAGE_DURATION_BASIS_MIXED` abstention has no estimate or permitted Subject
Verdict and therefore cannot enter Decision Support.

The verified upstream Investigation Request and Subject Profile chain must then
satisfy:

```text
investigation_request.trigger_mode == input.upstream_trigger_mode
normalize_trigger_mode(investigation_request.trigger_mode) == input.trigger_mode
subject_profile.identity == input.subject_identity
subject_profile.decision_at == input.causal_decision_at
subject_profile.content_hash == input.subject_driver_state.subject_profile_hash
```

`normalize_trigger_mode` is exactly the two-row mapping above. Trigger mode is
owned by the Investigation Request and verified result chain; Decision Support
does not invent a duplicate Subject Profile field.

For a reactive subject, `subject_driver_state` must copy the exact canonical
`high_load_exposure` boolean. For a proactive subject, it must copy the exact
preview-only `provisional_high_load_preview` boolean. The state kind, value,
Dataset Version, or derivation evidence disagreeing with the verified Subject
Profile is `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; a missing or
malformed state is `DECISION_SUPPORT_INPUT_SCHEMA_INVALID`.

When the verified state is false, the evaluation returns
`NO_ELIGIBLE_OPTION` with primary reason `SUBJECT_DRIVER_NOT_ACTIVE`. It does
not consume `constraints_as_of`, a Case Constraint Snapshot, links, rules,
costs, benefit assumptions, or advisory results. Every Core option, including
`ACCEPT_AND_MONITOR`, is recorded as `NOT_EVALUATED`.

Only a true Subject Driver State proceeds to active option evaluation. That
branch additionally requires:

```text
input.case_constraint_snapshot.constraints_as_of == input.constraints_as_of
input.constraints_as_of >= input.causal_decision_at
```

`NOT_PERMITTED` evaluates no library option, including
`ACCEPT_AND_MONITOR`. The result references the verdict and exposes only its
registered next step.

A missing verdict, hash mismatch, internally inconsistent true permission,
wrong scope, wrong subject, effect/interval inconsistency, missing or
mismatched Subject Driver State, or true-permission request that exceeds claim
scope is `FAILED`, not weak evidence.

For active option evaluation, the two cutoffs must use compatible canonical
temporal representations.
`causal_decision_at` remains the upstream commitment-time or proactive
proposal-time cutoff that governs exposure, covariates, and Subject Verdict
applicability. `constraints_as_of` is the later-or-equal operational knowledge
cutoff for this Decision Support Evaluation. It never admits a later fact into
the causal estimate or changes the upstream verdict.

### Closed terminal outcomes

Every permission attempt produces exactly one terminal workflow outcome. Only
a permission-true branch creates a Decision Support Evaluation; therefore
`FAILED` and `NOT_PERMITTED` may exist without an evaluation occurrence.

| Outcome | Meaning | Action Recommendation |
| --- | --- | --- |
| `FAILED` | Evaluation schema, version, integrity, currency, or arithmetic failure; no valid evaluation result exists | Prohibited |
| `NOT_PERMITTED` | Valid upstream evidence explicitly prohibits Decision Support; options were not evaluated | Prohibited |
| `NO_ELIGIBLE_OPTION` | Evaluation succeeded, but the subject driver is inactive or no option is recommendation-eligible under the value and monitoring-baseline policy | Prohibited |
| `TRADEOFF_REQUIRES_MANAGER_CHOICE` | Exactly two candidates and a deterministic pivot are presented | Absent until a valid trade-off selection |
| `RECOMMENDATION_AVAILABLE` | One singular Action Recommendation exists | Present |

`SUBJECT_DRIVER_NOT_ACTIVE` is the sole closed pre-library
`NO_ELIGIBLE_OPTION` reason. It is valid only for a verified false Subject
Driver State. It is case-wide, never an option-suppression code, and takes
precedence by short-circuiting before any option-level reason exists.

### Closed failure codes and precedence

| Priority | Code | Condition |
| ---: | --- | --- |
| 100 | `DECISION_SUPPORT_INPUT_SCHEMA_INVALID` | A case-wide required envelope input, including a required identifier or version field, is missing, malformed, non-finite, or has an unknown closed code |
| 200 | `DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED` | A present, well-formed required identifier or version is not in the exact supported set |
| 250 | `DECISION_SUPPORT_POLICY_NOT_AVAILABLE_AT_CUTOFF` | A supported case-wide policy, library, registry, schema, or formula version has `published_at > constraints_as_of` |
| 300 | `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH` | A referenced hash, subject, cutoff, role, or cross-record identity disagrees |
| 325 | `DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED` | A required case-wide temporal comparison cannot establish order at retained precision/timezone semantics |
| 350 | `DECISION_SUPPORT_EVIDENCE_UNAVAILABLE_AT_CUTOFF` | A required case-wide verified evidence/read-model record is suppressed, absent, or has `available_at > constraints_as_of` |
| 375 | `DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED` | A later authoritative invalidation explicitly targets a content-hash-bound artifact referenced by the current series head |
| 390 | `DECISION_SUPPORT_ADVICE_NOT_CURRENT` | A later currentness check proves or cannot disprove that the current advice chain is stale under the closed currentness-reason registry |
| 400 | `DECISION_SUPPORT_VERDICT_PERMISSION_INCONSISTENT` | Verdict, role, effect display, or permission fields contradict the upstream contract |
| 500 | `DECISION_SUPPORT_CURRENCY_MISMATCH` | Monetized inputs do not use one exact ISO currency |
| 600 | `DECISION_SUPPORT_ARITHMETIC_INVALID` | A required case-wide numeric input exceeds the closed magnitude/scale domain; arithmetic is undefined; or an exact arithmetic/comparison integer exceeds 4,096 bits |

The failure table governs the case-wide envelope and cross-option integrity.
An absent or invalid option-conditional cost, rate, or benefit assumption uses
the closed option-suppression registry instead; it does not become a global
schema failure merely because an option cannot use it.
`DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED` is valid only for the later
series-head invalidation branch; it is not fabricated as an original-evaluation
validation result. `DECISION_SUPPORT_ADVICE_NOT_CURRENT` is likewise valid only
for a later `ADVICE_CURRENTNESS_INVALIDATION`; original evaluation-time
temporal failures use the existing cutoff, `UNKNOWN`, suppression, or temporal-
comparison rules.

Validation is staged:

1. Validate only the permission envelope's schema and permission-policy
   version, then its referenced hashes/identities and verdict consistency.
2. If those checks pass and permission is false, return `NOT_PERMITTED`.
   Driver state, snapshot, library, cost, assumption, and arithmetic inputs are
   neither required nor consumed, so malformed unused evaluation data cannot
   change the refusal into `FAILED`.
3. If permission is true, validate only the Subject Driver State envelope,
   including its schema/policy, supported Intervention Library version,
   upstream Subject Profile hash, identity, cutoff, trigger mode, exact state,
   and derivation references.
4. If those checks pass and the Subject Driver State is false, return
   `NO_ELIGIBLE_OPTION` with `SUBJECT_DRIVER_NOT_ACTIVE`. Snapshot, link, rule,
   cost, assumption, advisory, and arithmetic inputs are neither required nor
   consumed.
5. Only when the state is true, validate the complete active-driver envelope,
   including verified evidence/read-model availability, in the priority order
   above.

Every safely decidable failure is retained and sorted by numeric priority,
then code. The first is primary and all others are ordered secondary failures.
A failure that prevents safe parsing or dereferencing stops only dependent
checks; it is never replaced by a lower-priority guess.

Raw exception text, stack traces, credentials, local paths, and environment
dumps are developer diagnostics, not domain evidence or user-facing reasons.

## Case Constraint Snapshot contract

`constraints_as_of` is one present canonical-lineage `TemporalValue`, including
its exact kind, retained precision, and timezone status. Every comparison in
this contract uses the canonical temporal partial order: date/date compares
calendar dates; compatible local datetimes or instants use their normalized
timeline; and a timezone or precision assumption is permitted only when it is
versioned and provenance-bearing. Runtime never manufactures midnight, UTC, a
timezone, or an order.

If a required case-wide comparison with `causal_decision_at`, `published_at`,
or `available_at` is unresolved, the result is
`DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`. For an option-scoped fact,
preview, rule, or monitoring review time, unresolved ordering uses that
artifact's existing `UNKNOWN`, invalid, or integrity rule and suppresses only
the affected option unless a supplied reference itself is malformed or
identity-mismatched.

Every snapshot contains:

- `snapshot_id`, schema identifier, and schema version;
- exact discriminated subject identity, exact causal `decision_at`, and exact
  `constraints_as_of`;
- an immutable ordered list of typed facts;
- a content hash over canonical snapshot content;
- snapshot creation time; and
- evidence references for all upstream records and attestations.

Each fact contains:

- stable fact code and optional option/component scope;
- typed value and unit or currency where applicable;
- `source_type`, exactly `VERIFIED_UPSTREAM_RECORD` or
  `MANAGER_ATTESTATION`;
- source record or immutable attestation reference;
- `known_at`, the time by which the underlying fact was known;
- `valid_through`, exactly `NO_EXPIRY` or one finite canonical-lineage
  `TemporalValue`, with source or attestation provenance;
- `source_available_at` for `VERIFIED_UPSTREAM_RECORD`, the verified time its
  referenced evidence/read model became available;
- `recorded_at`, when this snapshot captured it; and
- optional registered rationale code.

`constraints_as_of >= causal_decision_at` and
`known_at <= constraints_as_of` are required. A `VERIFIED_UPSTREAM_RECORD`
additionally requires `source_available_at <= constraints_as_of`; a later
source record cannot prove earlier availability. A finite validity horizon
additionally requires `constraints_as_of <= valid_through`; a provably expired
or temporally unresolved fact is ineligible and follows the same `UNKNOWN`
path as an unavailable fact. A manager may attest after `constraints_as_of`
that an operational fact was known and still valid at the cutoff, but the
later `recorded_at` remains visible and the attestation must explicitly
preserve the asserted `known_at` and `valid_through`. The attestation cannot
substitute for or backdate a required upstream evidence/read-model record. A
fact that first became known after `constraints_as_of` is ineligible for this
evaluation.

Free text may explain a fact but cannot provide its typed value, satisfy a
constraint, set an ordinal, or enter arithmetic. Conflicting eligible facts
produce `UNKNOWN`; the system never chooses the favorable source.

Moving `constraints_as_of`, editing a fact, or adding a newly known fact
creates a new snapshot and a new Decision Support Evaluation. An upstream
subject, causal `decision_at`, exposure, promise, covariate, support, or
Evidence Verdict change requires the appropriate new upstream run/verdict,
not a constraint-snapshot edit.

### Closed constraint fact registry

Core recognizes only these Case Constraint Snapshot fact codes. `option-scoped`
means the fact key also contains the exact option code/version.

| Fact code | Type and scope |
| --- | --- |
| `TIME_TO_INITIATE_DAYS` | Finite non-negative decimal plus explicit duration basis; option-scoped |
| `AVAILABLE_FLOAT_DAYS` | Finite non-negative decimal plus explicit duration basis; case-scoped |
| `PROTECTED_SLOT_MECHANISM_KIND` | `PROTECTED_SLOT` or `CAPACITY_RESERVATION`; option-scoped |
| `PROTECTED_SLOT_SUPPLIER_ACCEPTED` | Boolean; option-scoped |
| `QUALIFIED_SOURCE_COUNT` | Non-negative integer; option-scoped |
| `SPLIT_SPEC_PERMITTED` | Boolean; option-scoped |
| `SPLIT_CONTRACT_PERMITTED` | Boolean; option-scoped |
| `SPLIT_MINIMUM_QUANTITIES_SATISFIED` | Boolean; option-scoped |
| `ALTERNATE_CURRENTLY_QUALIFIED` | Boolean plus alternate-supplier reference; option-scoped |
| `ALTERNATE_SUBSTITUTION_PERMITTED` | Boolean; option-scoped |
| `ALTERNATE_WORK_TRANSFERABLE` | Boolean; option-scoped |
| `RELEASE_DATE_MOVABLE` | Boolean; option-scoped |
| `RELEASE_MILESTONE_FEASIBLE` | Boolean plus proposed release/milestone references; option-scoped |
| `REVISED_PROVISIONAL_HIGH_LOAD_PREVIEW` | Boolean plus exact hash-bound Release-Timing Preview reference; option-scoped |
| `ACCELERATION_MECHANISM_KIND` | `OVERTIME_CAPACITY` or `SLOT_SWAP`; option-scoped |
| `ACCELERATION_SUPPLIER_ACCEPTED` | Boolean; option-scoped |
| `ACCELERATION_CONTRACT_PERMITTED` | Boolean; option-scoped |
| `PHASED_HANDOFF_FEASIBLE` | Boolean; option-scoped |
| `PHASED_DOWNSTREAM_CONSUMABLE` | Boolean; option-scoped |
| `PHASED_CONTRACT_PERMITTED` | Boolean; option-scoped |
| `RESEQUENCE_PLAN_REVIEWED` | Boolean plus reviewed-plan reference; option-scoped |
| `RESEQUENCE_PREREQUISITES_VALID` | Boolean plus prerequisite-set reference; option-scoped |
| `RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH` | Boolean plus reviewed schedule reference; option-scoped |
| `ESCALATION_BASIS_ENFORCEABLE` | Boolean plus contract-clause reference; option-scoped |
| `ESCALATION_NOTICE_WINDOW_OPEN` | Boolean plus notice-window bounds; option-scoped |
| `ESCALATION_RECORDS_COMPLETE` | Boolean plus required-record-set reference; option-scoped |
| `MONITORING_OWNER_REF` | Non-empty local accountable-owner reference; option-scoped |
| `MONITORING_NEXT_REVIEW_AT` | Canonical `TemporalValue`; option-scoped |
| `MONITORING_ESCALATION_TRIGGER_REF` | Exactly one hash-bound Monitoring Escalation Trigger reference; option-scoped |
| `COMPOSITE_COMPATIBILITY_REVIEW_REF` | Exactly one hash-bound Composite Compatibility Review result reference; composite-scoped |

An unknown fact code fails snapshot schema validation. A known code with the
wrong type, scope, unit, or required companion reference evaluates as
`UNKNOWN`; it never coerces from text or another field.

Advisory Results are Decision Support-derived outputs, not Case Constraint
Snapshot facts. The snapshot therefore has no advisory-result-reference fact
code, and an Advisory Rubric input declaration cannot name an Advisory Result.
A supplied legacy `*_RESULT_REF`, free-text assessment, or bare ordinal cannot
bypass typed-input derivation.

## Release-Timing Preview contract

`RELEASE_TIMING_ADJUSTMENT` may use only one `Release-Timing Preview` bound to
the exact base proactive proposal being evaluated. The immutable preview
contains:

- schema identifier/version, preview ID, content hash, and creation time;
- the base Subject Profile reference and content hash;
- the base Investigation Request reference and content hash;
- the verified sealed Analysis Run bundle reference/hash and scientific request
  digest that supplied the Subject Profile and verdict evidence;
- the exact base `PROACTIVE_PROPOSAL` identity, including source system,
  proposal ID, proposal revision, and Dataset Version;
- the same supplier and target milestone kind as the base Subject Profile;
- the original causal `decision_at` and the operational `constraints_as_of`;
- the exact primary `VariantCohortInput.selector_refs` and
  `threshold_rule_ref` copied from that bundle's canonical `engine_request`;
- `candidate_release_at`, the candidate promised target milestone, and
  `alternate_decision_at`;
- the resulting `provisional_concurrent_load_count`,
  `provisional_load_percentile`, and `provisional_high_load_preview`; and
- the ordered calculation inputs and evidence references, each with its exact
  value, `known_at`, and content hash.

The preview must satisfy all of:

```text
preview.base_subject_profile_ref_and_hash == input.subject_profile_ref_and_hash
preview.base_investigation_request_ref_and_hash == input.investigation_request_ref_and_hash
preview.base_analysis_run_bundle_ref_and_hash == input.verified_analysis_run_bundle_ref_and_hash
preview.scientific_request_digest == input.verified_analysis_run_bundle.scientific_request_digest
preview.base_proactive_proposal_identity == input.subject_identity
preview.supplier == input.subject_profile.supplier
preview.target_milestone_kind == input.subject_profile.target_milestone_kind
preview.dataset_version_id == input.subject_identity.dataset_version_id
preview.base_causal_decision_at == input.causal_decision_at
preview.constraints_as_of == input.constraints_as_of
preview.selector_refs == input.verified_analysis_run_bundle.engine_request.primary.selector_refs
preview.threshold_rule_ref == input.verified_analysis_run_bundle.engine_request.primary.threshold_rule_ref
preview.alternate_decision_at == preview.candidate_release_at
preview.alternate_decision_at > input.causal_decision_at
preview.alternate_decision_at >= input.constraints_as_of
preview.candidate_promised_target_milestone >= preview.alternate_decision_at
every preview calculation input known_at <= input.constraints_as_of
```

All temporal values above must be comparable under the canonical temporal
partial order. In particular, a promised target milestone earlier than, or
incomparable with, `alternate_decision_at` is a chronology mismatch. The
preview reuses the exposure contract's open-line, expanding-history, and
threshold semantics over the same frozen Dataset Version. Its only candidate
changes are the release or commitment time and promised target milestone; its
derived provisional values remain operational what-if outputs, not upstream
Subject Profile fields or causal facts.

The verified Analysis Run bundle must be sealed and its exact canonical
`engine_request` must be the request bound through the supplied verdict and
artifact-integrity evidence chain. Decision Support never dereferences selector
or threshold fields from the Investigation Request, because that upstream
schema does not own them.

The Case Constraint Snapshot's
`REVISED_PROVISIONAL_HIGH_LOAD_PREVIEW` value and its
`RELEASE_MILESTONE_FEASIBLE` candidate release and milestone references must
match the preview exactly. A content-hash, proposal/revision, supplier,
milestone-kind, Dataset-Version, Analysis Run bundle, scientific-request,
selector, threshold-rule, candidate-value, or chronology mismatch is
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`. A malformed preview uses
the existing schema failure, and an unsupported preview version uses the
existing version failure.

When no eligible preview exists, or any required preview calculation input was
not known by `constraints_as_of`, `RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD` is
`UNKNOWN` and suppresses only `RELEASE_TIMING_ADJUSTMENT`. An exact eligible
preview whose `provisional_high_load_preview = true` makes that rule
`UNSATISFIED`; false makes it `SATISFIED`. No preview from another proposal,
revision, or supplier may be borrowed.

## Duration-basis contract

Every duration used by this contract carries its numeric value and one closed
`duration_basis`:

```text
CALENDAR_DAY
ELAPSED_86400_SECOND_DAY
BUSINESS_DAY {
  calendar_id,
  calendar_version,
  calendar_content_hash
}
```

The referenced Business Calendar version fixes working-day membership,
working intervals, and its fractional-day convention. `BUSINESS_DAY` is valid
only for `TIME_TO_INITIATE_DAYS` and `AVAILABLE_FLOAT_DAYS`; it is never a
`PROJECT_DELAY_DAYS` or monetary-rate basis.

Two duration bases are compatible only when their complete canonical values
are equal. Thus two `BUSINESS_DAY` values require the exact same calendar ID,
version, and content hash. Runtime never converts between calendar, elapsed,
or Business Calendar days.

`TIME_TO_INITIATE_DAYS` may be compared with `AVAILABLE_FLOAT_DAYS` only when
their bases are compatible. A missing, malformed, or incompatible basis makes
the applicable within-float Constraint Result `UNKNOWN` and suppresses that
option through `REQUIRED_CONSTRAINT_UNKNOWN`; neither value is coerced.

The verified sealed `causal-engine-suite-request.v2` carries exactly one
`canonical_slippage_duration_basis`, either `CALENDAR_DAY` or
`ELAPSED_86400_SECOND_DAY`, already frozen by the upstream temporal-eligibility
contract. Decision Support copies and validates this hash-bound field; it never
derives a basis from target-milestone kind, inspects row-majority basis, or
converts an effect.

Every exposure-derived recovered Supplier Milestone Slippage duration and
`PROJECT_DELAY_DAYS` value inherits that resolved basis; multiplication by a
dimensionless recoverable or critical-path translation fraction never changes
it. A `PROJECT_DELAY_DAYS` Consequence Benefit Assumption must declare the
same resolved basis. The cost-of-critical-path-delay record retains
`day_basis = CANONICAL_SLIPPAGE_DAY` and must record that same
`resolved_duration_basis`.

A missing or mismatched Consequence Benefit Assumption basis produces
`CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID`. A missing or mismatched resolved rate
basis produces `CRITICAL_PATH_DELAY_RATE_INVALID`. The affected option is
suppressed before multiplication or Pareto comparison. A direct-monetary or
monitor-only option carries schedule basis `NOT_APPLICABLE` and no duration
basis is fabricated for it.

Pareto comparison of two applicable `TIME_TO_INITIATE_DAYS` values also
requires their complete canonical duration bases to be equal, including an
exact Business Calendar ID, version, and content hash when applicable. A basis
mismatch makes that dimension incomparable, records
`INCOMPATIBLE_INITIATION_DURATION_BASIS` when it blocks candidate selection,
and routes through the evidence-gap rule. Runtime never converts either value.

## Governed Intervention Library

### Intervention Option record

Each immutable option version contains:

- stable option code, version, nullable predecessor-version reference, display
  label, and library display order;
- `ATOMIC` or `COMPOSITE`;
- allowed trigger modes;
- response class;
- ordered component references for a composite;
- required Constraint Rule references in registry order;
- for each of `CONTRACTUAL_RELATIONSHIP_RISK`, `OPERATIONAL_DISRUPTION`, and
  `REVERSIBILITY`, an atomic option has exactly one advisory-rubric declaration
  discriminated as an exact rubric reference or
  `UNAVAILABLE_PENDING_REVIEW`; a composite instead has exactly one closed
  derivation declaration, either `LEAST_FAVORABLE_COMPONENT_RESULTS.v1` or an
  exact `COMPOSITE_SPECIFIC_RUBRIC` reference;
- exact action-cost formula identifier;
- benefit-policy and required-assumption-kind declarations; the option record
  contains no default-assumption reference;
- an atomic option has `DECLARED_CASE_INITIATION_TIME.v1`; a composite has one
  closed time-composition declaration, exactly `PARALLEL`, `SEQUENTIAL`, an
  exact approved formula reference, or `UNAVAILABLE_PENDING_REVIEW`;
- deterministic explanation-template identifier; and
- lifecycle status, exactly `ACTIVE` or `RETIRED`.

Retirement prevents new evaluations and never mutates an earlier result. At or
after the retirement's effective publication time, however, an earlier advice
chain that depended on the option being `ACTIVE` fails the
`INTERVENTION_OPTION_VERSION` currentness predicate and advances through
`ADVICE_CURRENTNESS_INVALIDATION` when it is still the exact head. Each
Intervention Library version maps every Core option code to exactly one option
version and status. Runtime resolves only that mapping; it cannot search for a
newer option record, create an option, or create a component list.

### Closed Core option set

| Display order | Option code | Option version | Status | Trigger mode | Response class | Shape |
| ---: | --- | --- | --- | --- | --- | --- |
| 10 | `PROTECTED_PRODUCTION_SLOT` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `MILESTONE_ACCELERATION` | Atomic |
| 20 | `QUALIFIED_SOURCE_SPLIT` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `EXPOSURE_REDUCTION` | Atomic |
| 30 | `PREQUALIFIED_ALTERNATE` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `EXPOSURE_REDUCTION` | Atomic |
| 40 | `RELEASE_TIMING_ADJUSTMENT` | `1` | `ACTIVE` | `PROACTIVE` | `EXPOSURE_REDUCTION` | Atomic |
| 50 | `CAPACITY_BACKED_ACCELERATION` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `MILESTONE_ACCELERATION` | Atomic |
| 60 | `PHASED_DELIVERY` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `CONSEQUENCE_MITIGATION` | Atomic |
| 70 | `DEPENDENT_WORK_RESEQUENCING` | `1` | `ACTIVE` | `REACTIVE` | `CONSEQUENCE_MITIGATION` | Atomic |
| 80 | `CONTRACTUAL_ESCALATION` | `1` | `ACTIVE` | `REACTIVE` | `CONSEQUENCE_MITIGATION` | Atomic |
| 90 | `ACCEPT_AND_MONITOR` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `MONITOR_ONLY` | Atomic |
| 100 | `PROTECTED_SLOT_WITH_PHASED_DELIVERY` | `1` | `ACTIVE` | `REACTIVE`, `PROACTIVE` | `MILESTONE_ACCELERATION` | Composite |

`PROTECTED_SLOT_WITH_PHASED_DELIVERY` has ordered components
`[PROTECTED_PRODUCTION_SLOT, PHASED_DELIVERY]`. Its projected benefit comes
only from its approved composite Driver-Action Link; component projections are
never summed.

There is no `GENERIC_EXPEDITE` option. The user-facing expedite concept is
`CAPACITY_BACKED_ACCELERATION`, which requires a verified overtime-capacity or
slot-swap mechanism. Without one, the option is listed as suppressed.

### Closed response classes

| Code | Meaning | Permitted benefit basis |
| --- | --- | --- |
| `EXPOSURE_REDUCTION` | Plausibly reduces future High-Load Exposure for remaining or future scope | Exposure translation assumption |
| `MILESTONE_ACCELERATION` | Uses a concrete mechanism to reduce the consequences of current load for the supplier-controlled milestone | Exposure translation assumption |
| `CONSEQUENCE_MITIGATION` | Protects downstream project or contractual consequences without claiming recovered supplier-milestone days | Consequence Benefit Assumption |
| `MONITOR_ONLY` | Accepts the current exposure and creates no benefit claim | No benefit claim |

An option's response class determines the one benefit model it may use.
`MONITOR_ONLY` is explicitly non-mechanistic. Composites cannot add or blend
benefit models.

## Driver-Action Link contract

Each immutable link version contains:

- stable link ID/version, exact registry ID/version, content hash, canonical
  `published_at`, and nullable predecessor-version reference;
- driver code, fixed in Core to `SUPPLIER_CONGESTION_HIGH_LOAD`;
- exact Causal Question and Subject Verdict claim-scope references;
- option code and version;
- exactly one trigger mode, `REACTIVE` or `PROACTIVE`;
- `link_kind`, exactly `ACTION_MECHANISM` or `MONITORING_BASELINE`;
- one discriminated link payload:
  - `ACTION_MECHANISM` requires one mechanism class and a deterministic
    mechanism-explanation template;
  - `MONITORING_BASELINE` requires a deterministic baseline-rationale template,
    while mechanism class and mechanism-explanation template are
    `NOT_APPLICABLE`;
- proposed or reviewed source/evidence references;
- `intervention_effect_estimated`, fixed to `false` in Core;
- default recoverable-fraction or consequence-assumption reference where
  applicable;
- review status, exactly `PROVISIONAL`, `APPROVED`, or `REJECTED`;
- explicitly available or unavailable reviewer role, review date, immutable
  review reference, and registered review-reason code.

Review-field cardinality is status-dependent:

| Status | Reviewer role/date/reference | Review-reason code |
| --- | --- | --- |
| `PROVISIONAL` | All explicitly `unavailable_pending_review` | `unavailable_pending_review` |
| `APPROVED` | All required | Optional registered qualification or `not_applicable` |
| `REJECTED` | All required | Required registered rejection reason |

Every status transition publishes an immutable successor link version and
preserves its predecessor; no record mutates in place. A review-only successor
may retain the exact definition content. A change to link kind, mechanism or
baseline rationale, trigger scope, source references, default benefit
assumption, or option version creates a new successor whose status is
`PROVISIONAL`.

Within the exact effective Driver-Action Link registry version, resolution for
an option uses the exact driver code, option code/version, and normalized
trigger mode. A supplied matching link whose `published_at` is after, or not
provably no later than, `constraints_as_of` produces
`DRIVER_ACTION_LINK_NOT_AVAILABLE_AT_CUTOFF`; runtime does not substitute an
older published link. Among matching link versions provably published by the
cutoff, the supplied version must be the unique unsuperseded head. No matching
version produces `DRIVER_ACTION_LINK_MISSING`; an older supplied version
produces `DRIVER_ACTION_LINK_SUPERSEDED`; and a malformed predecessor graph or
multiple unsuperseded heads produces global
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`. Only after this resolution is
the effective head's `PROVISIONAL`, `APPROVED`, or `REJECTED` status applied.

`ACCEPT_AND_MONITOR` requires `link_kind = MONITORING_BASELINE`; its default
recoverable-fraction and consequence-assumption references are
`NOT_APPLICABLE`. Every other Core option requires
`link_kind = ACTION_MECHANISM`, and the link's mechanism class must equal the
option's response class. A kind-option or mechanism-class mismatch is a
cross-record identity disagreement and produces
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; it is not downgraded to an
option suppression.

Link identity includes exactly one trigger mode. An option allowed in both
reactive and proactive flows therefore requires two separately reviewable
links and may carry different default assumptions in each.

The effective approved Driver-Action Link is the sole authority for the exact
default recoverable-fraction or Consequence Benefit Assumption reference in
that trigger mode. The Intervention Option declares only which assumption kind
its benefit policy requires. A link whose default-reference kind disagrees
with the option's required kind is a cross-record identity disagreement and
produces `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; runtime never looks
for, reconciles, or chooses a second option-level default.

Accepted reviewer-role codes are
`PRACTISING_CONSTRUCTION_PROJECT_MANAGER` and
`PRACTISING_PROCUREMENT_ENGINEER`. No sensitive reviewer identity enters the
link. The domain-expert-validation artifact owns any consented contact details
outside this record.

Only `APPROVED` links are eligible.

The Stage 2 strategy is product intent, not by itself the external domain
review required to mark a link `APPROVED`.

## Monitoring Escalation Trigger contract

Core schema version `1` permits one atomic predicate only. Each immutable
Monitoring Escalation Trigger version contains:

- stable trigger ID/version, exact trigger-registry ID/version, and content
  hash;
- exact `option_code = ACCEPT_AND_MONITOR` and option version;
- a non-empty, sorted, duplicate-free set of trigger modes supported by that
  option version;
- one exact monitoring-observation registry ID/version and registered
  observation code, with the registered value type, unit or `NOT_APPLICABLE`,
  source schema identifier/version/content hash, and reviewed Intake & Lineage
  source-mapping manifest reference/hash plus mapping-entry code;
- exactly one operator: `LT`, `LTE`, `EQ`, `NEQ`, `GTE`, `GT`, or `IN_SET`;
- exactly one typed threshold for every operator except `IN_SET`, or one
  non-empty, duplicate-free allowed set for `IN_SET`;
- `response_code = REQUEST_MANAGER_REVIEW`;
- ordered provenance/source references and canonical `published_at`;
- lifecycle status, exactly `PROVISIONAL`, `APPROVED`, `REJECTED`, or
  `RETIRED`;
- reviewer role, review date, immutable reviewer reference, and registered
  review-reason code; and
- nullable predecessor trigger version plus the immutable registry
  supersession metadata needed to resolve the effective version.

Each immutable monitoring-observation registry entry contains one stable code,
value type, exact unit or `NOT_APPLICABLE`, equality and total-order
capabilities, source schema identifier/version/content hash, ordered
provenance references and content hashes, one reviewed Intake & Lineage source-
mapping manifest reference/hash and mapping-entry code, and publication time.
That mapping entry produces exactly the closed canonical output fields
`subject_identity`, `observed_value`, `observed_unit`, `observed_at`,
`first_available_at`, and `source_record_ref_and_hash`. Intake & Lineage owns
the adapter and mapping execution; issue #10 validates this canonical output
and does not define or execute a second extraction language. The trigger's
copied observation definition must match that exact entry; a mismatch is a
cross-record identity disagreement. An approved trigger cannot predate its
referenced observation-registry version.

The observation registration owns its value type, exact unit, orderability,
and source schema. A predicate literal must have that exact type and unit; Core
performs no coercion or unit conversion. `LT`, `LTE`, `GTE`, and `GT` require an
observation type registered as totally ordered. `EQ` and `NEQ` require an
equality-comparable type. `IN_SET` compares against values of the same
registered type and unit; its allowed set is stored in canonical value order.
A compound predicate, Boolean composition, second observation, second
operator, or second response is not valid under schema version `1` and
requires a future supported schema version.

A well-formed trigger may explicitly mark concrete definition content
`UNAVAILABLE_PENDING_REVIEW`; this is an under-specified trigger rather than a
runtime default. A missing required schema field, unknown closed operator or
response, invalid literal type, or non-atomic schema is malformed. Runtime
never invents an observation, threshold, allowed set, source schema, unit, or
compound relation.

Review-field cardinality is status-dependent:

| Status | Reviewer role/date/reference | Review-reason code |
| --- | --- | --- |
| `PROVISIONAL` | All explicitly `unavailable_pending_review` | `unavailable_pending_review` |
| `APPROVED` | All required | Optional registered qualification or `not_applicable` |
| `REJECTED` | All required | Required registered rejection reason |
| `RETIRED` | All required | Required registered retirement reason |

Accepted reviewer-role codes are the same closed codes used by Driver-Action
Links. Every definition or lifecycle change publishes an immutable successor
and preserves its predecessor; no trigger version mutates in place. The
registry version records immutable successor relations. At an evaluation's
`constraints_as_of`, a supplied trigger is superseded when another version
published no later than that cutoff reaches it through the predecessor chain.

`MONITORING_ESCALATION_TRIGGER_REGISTERED` is `SATISFIED` only when the Case
Constraint Snapshot contains exactly one trigger fact and its exact referenced
version is:

- available with `published_at <= constraints_as_of`;
- `APPROVED` and fully specified;
- applicable to the exact `ACCEPT_AND_MONITOR` option version and evaluation
  trigger mode; and
- the unique unsuperseded applicable version at that cutoff.

Otherwise the Constraint Result is `UNKNOWN`, monitoring is suppressed through
the existing `REQUIRED_CONSTRAINT_UNKNOWN` suppression reason, and every
applicable reason is retained in this closed precedence:

| Priority | Reason code | Condition |
| ---: | --- | --- |
| 100 | `MONITORING_TRIGGER_REFERENCE_MISSING` | No trigger fact is present |
| 110 | `MONITORING_TRIGGER_REFERENCE_MULTIPLE` | More than one trigger fact is present; duplicate facts are not collapsed |
| 120 | `MONITORING_TRIGGER_NOT_AVAILABLE_AT_CUTOFF` | The referenced version is not provably published no later than `constraints_as_of`, whether later or temporally incomparable |
| 130 | `MONITORING_TRIGGER_NOT_APPROVED` | The referenced version is `PROVISIONAL` or `REJECTED` |
| 140 | `MONITORING_TRIGGER_RETIRED` | The referenced version is `RETIRED` |
| 150 | `MONITORING_TRIGGER_NOT_APPLICABLE` | The option version or trigger mode is outside the trigger's applicability |
| 160 | `MONITORING_TRIGGER_UNDER_SPECIFIED` | Concrete observation, predicate, provenance, or review content is explicitly unavailable |
| 170 | `MONITORING_TRIGGER_SUPERSEDED` | A successor was published by the cutoff |
| 180 | `MONITORING_TRIGGER_EFFECTIVE_VERSION_AMBIGUOUS` | The registry has more than one unsuperseded applicable version at the cutoff |

No trigger fact and an explicit unavailable definition therefore fail closed
as `UNKNOWN`. A supplied malformed, dangling, hash-mismatched, wrong-registry,
or cross-identity trigger reference uses the existing global
`DECISION_SUPPORT_INPUT_SCHEMA_INVALID` or
`DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH` result as applicable; it is
not downgraded to an option-scoped unknown.

The Decision Support Evaluation checks only whether an eligible monitoring
predicate has been registered. Later matching uses an immutable Monitoring
Observation occurrence containing:

- exact schema identifier/version `monitoring-observation.v1`, a stable
  occurrence ID, deterministic logical key, and exact observation-registry
  ID/version/code;
- the exact reviewed source-mapping manifest reference/hash and mapping-entry
  code copied from the registry entry;
- the exact canonical discriminated subject identity supplied by Intake &
  Lineage through that mapping entry;
- the typed value and exact unit or `NOT_APPLICABLE`;
- the source-schema identifier/version/content hash and source-record
  reference/content hash;
- canonical `observed_at`, source-record `first_available_at`, and
  `available_at = source_record.first_available_at`; and
- an occurrence content hash.

Its deterministic logical key is:

```text
monitoring_observation_key =
    sha256(canonical-scientific-json.v1({
      schema_identifier_and_version,
      observation_registry_id_version_and_code,
      source_mapping_manifest_ref_and_hash,
      mapping_entry_code,
      canonical_subject_identity,
      typed_value_and_unit,
      source_schema_id_version_and_hash,
      source_record_ref_and_hash,
      observed_at,
      source_record_first_available_at
    }))
```

Exactly one logical Monitoring Observation occurrence/reference/hash exists
per key; exact replay returns it. Rewrapping the same logical source
observation under another occurrence ID is a cardinality violation, and
different content under one key is an integrity failure. A wrapper receipt or
redelivery time can never replace the source record's immutable first-
availability time or create another observation key.

For a match, the observation's canonical subject identity must equal the
Action Recommendation's exact subject identity, and
`recommendation.monitoring_activated_at <= observed_at <= available_at` must be
provable under the canonical temporal
partial order. The immutable `available_at` is the
`trigger_match_as_of`; processing or replay time has no decision semantics. At
that cutoff, `currentness_checked_at = trigger_match_as_of`; the value is bound
to the immutable source observation and is not caller-selected or backdated.
Decision Support derives the deterministic currentness operation with
`operation_kind = MONITORING_TRIGGER_MATCH` and payload equal to the exact
Monitoring Observation occurrence/hash, then performs the complete advice-
currentness check, including all consumed operational horizons. The source
Action Recommendation must still
bind the authoritative `EVALUATION` series head, select
`ACCEPT_AND_MONITOR`, and reference the exact trigger. A manager-selected
monitoring recommendation additionally requires the exact current accepted
selection claim in the operation; an immediate recommendation requires null.
That trigger must still
be `APPROVED`, fully specified, applicable, and the unique unsuperseded
applicable trigger version provably published no later than
`trigger_match_as_of`. A cross-subject observation, an observation before
monitoring activation, or an unresolved required identity/temporal comparison
emits no request and fails with the applicable schema, reference-integrity, or
temporal result. A dependency, expiry, or comparison failure against the
exact head publishes the applicable `ADVICE_CURRENTNESS_INVALIDATION` and emits
no review request. `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` likewise emits no
request and never mutates the observed successor. A stale recommendation, any
invalidation head, a retired/rejected/provisional/
superseded/ambiguous trigger, an expired consumed fact, an invalid or
temporally unresolved observation/currentness comparison, or an identity/hash
mismatch likewise emits no review request. Runtime never substitutes a
successor trigger into the old recommendation.

If all checks pass, Decision Support stages one `monitoring-match-result`
version `1` containing stable occurrence ID, deterministic result key, and
content hash; the exact trigger, observation, recommendation, currentness-
operation, currentness-check, and branch-correct accepted selection-claim
references/hashes or null; and one closed outcome. A
false exact typed predicate yields
`NO_REVIEW_REQUEST` with a null request reference/hash. A true predicate yields
`REQUEST_MANAGER_REVIEW` with exactly one logical request reference/hash whose
deterministic key is:

```text
monitoring_review_request_key =
    sha256(canonical-scientific-json.v1({
      evaluation_series_id,
      recommendation_occurrence_id,
      trigger_id_and_version,
      monitoring_observation_key,
      monitoring_observation_ref_and_hash,
      accepted_selection_claim_ref_and_hash_or_null,
      currentness_operation_ref_and_hash,
      currentness_check_ref_and_hash,
      response_code = REQUEST_MANAGER_REVIEW
    }))
```

The match-result key is computed without either occurrence content hash:

```text
monitoring_match_result_key =
    sha256(canonical-scientific-json.v1({
      recommendation_ref_and_hash,
      trigger_id_and_version,
      monitoring_observation_key,
      monitoring_observation_ref_and_hash,
      accepted_selection_claim_ref_and_hash_or_null,
      currentness_operation_ref_and_hash,
      currentness_check_ref_and_hash,
      match_outcome,
      monitoring_review_request_key_or_null
    }))
```

The emitted `monitoring-review-request` version `1` stores a stable occurrence
ID, the deterministic request key, content hash, precomputed
`monitoring_match_result_key`, exact trigger/observation/recommendation and both
currentness references/hashes, the branch-correct accepted selection-claim
reference/hash or null, and
`response_code = REQUEST_MANAGER_REVIEW`; it does not contain the match-result
occurrence reference/hash. The request content hash is therefore computed
before the match-result content hash. The match result then contains the exact
request reference/hash for `REQUEST_MANAGER_REVIEW`, or null for
`NO_REVIEW_REQUEST`. Exactly one logical request exists per request key and one
logical match result exists per result key. The currentness check, match result,
and optional request publish atomically under the currentness-operation terminal
claim and a final exact-head comparison. A concurrent successor produces the
stale terminal result and publishes none of them. Replay or repeated delivery
of that same hash-bound tuple returns the existing terminal claim and cannot
create a second logical request. The response cannot select an
Intervention Option, create a Manager Decision, authorize or execute work,
mutate the source evaluation, or silently create a successor evaluation.
Issue #12 owns physical deduplication and persistence but may not weaken this
logical cardinality. Concrete observation definitions and trigger thresholds
remain subject to the domain-expert-validation ticket before any version
becomes `APPROVED`.

## Evidence tags and mandatory disclosure

Every option evaluation carries exactly the following four closed evidence-tag
slots:

| Tag slot | Closed values | Rule |
| --- | --- | --- |
| `DRIVER_EVIDENCE` | `SUPPORTED_UNDER_ASSUMPTIONS`, `NOT_EVALUATED` | An evaluated option references the exact permitted Subject Verdict |
| `MECHANISTIC_LINK` | `REVIEWED_PLAUSIBLE`, `REVIEWED_BASELINE`, `PROVISIONAL`, `REJECTED`, `MISSING`, `NOT_EVALUATED` | Derived only from the exact Driver-Action Link version; `NOT_EVALUATED` applies when an earlier trigger-mode gate prevents link resolution |
| `RULE_BASED_ELIGIBILITY` | `ELIGIBLE`, `SUPPRESSED`, `NOT_EVALUATED` | Derived from required Constraint Results |
| `ASSUMPTION_BASED_BENEFIT` | `EXPOSURE_TRANSLATION_ASSUMPTION`, `OPERATIONAL_ASSUMPTION_ONLY`, `NO_BENEFIT_CLAIM`, `UNAVAILABLE`, `NOT_EVALUATED` | Identifies the permitted benefit basis, never strength |

An approved `ACTION_MECHANISM` maps to
`MECHANISTIC_LINK = REVIEWED_PLAUSIBLE`. An approved
`MONITORING_BASELINE` maps to `MECHANISTIC_LINK = REVIEWED_BASELINE` and
`ASSUMPTION_BASED_BENEFIT = NO_BENEFIT_CLAIM`. `REVIEWED_BASELINE` asserts
external review of the response baseline, not a mechanism, benefit, or action
effect.

Every option shown to a user also exposes:

```text
action_effect_evidence = INTERVENTION_EFFECT_NOT_ESTIMATED
```

A separate `speculative_disclosure` is derived as `PRESENT` exactly when the
resolved link status is `PROVISIONAL`, and `ABSENT` otherwise. It is not a
fifth evidence tag, and `ABSENT` is not rendered on an eligible card. A
candidate, runner-up, or Action Recommendation therefore shows exactly the
four evidence tags above plus the mandatory action-effect disclosure.

`speculative_disclosure = PRESENT` suppresses the option before constraint
evaluation or benefit calculation. It may appear only in progressive
disclosure, with no projected days or value. It cannot be recommended, be a
trade-off candidate, or be a runner-up.

The tags are categorical provenance labels, not probabilities or a score.
They provide the strategy's evidence-confidence disclosure. Evidence
confidence is not a seventh Pareto dimension: the permitted Subject Verdict is
case-wide, while exact link review status and rule evidence are eligibility
gates or disclosures rather than orderable option strength.

## Constraint semantics

### Rule types and statuses

Every Constraint Rule is `REQUIRED` or `ADVISORY`.

Every evaluated rule produces one of:

| Status | Meaning |
| --- | --- |
| `SATISFIED` | All required typed facts prove the rule true |
| `UNSATISFIED` | Eligible typed facts prove the rule false |
| `UNKNOWN` | A required fact is missing, late-known, conflicting, malformed, or not provenance-eligible |
| `NOT_APPLICABLE` | The rule's registered applicability predicate is false |

For a required rule, only `SATISFIED` or a valid `NOT_APPLICABLE` permits the
option to continue. `NOT_APPLICABLE` cannot be asserted by input; the rule
derives it.

All applicable required rules are evaluated without stopping at the first
failure, then sorted in registry order. Advisory rules never suppress an
option.

Every Constraint Result contains rule ID/version, option/component scope,
status, typed observed facts, typed threshold or allowed set, evidence
references, and a deterministic explanation code. Exception text is not a
Constraint Result.

### Required Constraint Rule registry

Equality at a numeric boundary passes unless a row states otherwise.

| Priority | Rule code | Option | `SATISFIED` condition |
| ---: | --- | --- | --- |
| 100 | `PROTECTED_SLOT_MECHANISM_VERIFIED` | `PROTECTED_PRODUCTION_SLOT` | A protected production slot or capacity-reservation mechanism is verified |
| 110 | `PROTECTED_SLOT_SUPPLIER_ACCEPTED` | `PROTECTED_PRODUCTION_SLOT` | Supplier acceptance is confirmed |
| 120 | `PROTECTED_SLOT_WITHIN_FLOAT` | `PROTECTED_PRODUCTION_SLOT` | Compatible duration bases and `time_to_initiate_days <= available_float_days` |
| 200 | `SPLIT_TWO_QUALIFIED_SOURCES` | `QUALIFIED_SOURCE_SPLIT` | At least two currently qualified sources are available |
| 210 | `SPLIT_SPEC_PERMITTED` | `QUALIFIED_SOURCE_SPLIT` | The governing specification permits the split |
| 220 | `SPLIT_CONTRACT_PERMITTED` | `QUALIFIED_SOURCE_SPLIT` | The contract permits the split |
| 230 | `SPLIT_MINIMUM_QUANTITIES_SATISFIED` | `QUALIFIED_SOURCE_SPLIT` | Every source satisfies its minimum-order quantity |
| 240 | `SPLIT_WITHIN_FLOAT` | `QUALIFIED_SOURCE_SPLIT` | Compatible duration bases and `time_to_initiate_days <= available_float_days` |
| 300 | `ALTERNATE_CURRENTLY_QUALIFIED` | `PREQUALIFIED_ALTERNATE` | The named alternate is currently qualified |
| 310 | `ALTERNATE_SUBSTITUTION_PERMITTED` | `PREQUALIFIED_ALTERNATE` | The contract permits substitution |
| 320 | `ALTERNATE_WORK_TRANSFERABLE` | `PREQUALIFIED_ALTERNATE` | The relevant future or remaining work is transferable |
| 330 | `ALTERNATE_WITHIN_FLOAT` | `PREQUALIFIED_ALTERNATE` | Compatible duration bases and `time_to_initiate_days <= available_float_days` |
| 400 | `RELEASE_DATE_MOVABLE` | `RELEASE_TIMING_ADJUSTMENT` | The release date is contractually and operationally movable |
| 410 | `RELEASE_MILESTONE_FEASIBLE` | `RELEASE_TIMING_ADJUSTMENT` | The revised release preserves the required milestone feasibility |
| 420 | `RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD` | `RELEASE_TIMING_ADJUSTMENT` | The exact eligible Release-Timing Preview has `provisional_high_load_preview = false` |
| 500 | `ACCELERATION_MECHANISM_VERIFIED` | `CAPACITY_BACKED_ACCELERATION` | Mechanism kind is exactly `OVERTIME_CAPACITY` or `SLOT_SWAP`, with evidence |
| 510 | `ACCELERATION_SUPPLIER_ACCEPTED` | `CAPACITY_BACKED_ACCELERATION` | Supplier acceptance is confirmed |
| 520 | `ACCELERATION_CONTRACT_PERMITTED` | `CAPACITY_BACKED_ACCELERATION` | The contract permits the mechanism |
| 530 | `ACCELERATION_WITHIN_FLOAT` | `CAPACITY_BACKED_ACCELERATION` | Compatible duration bases and `time_to_initiate_days <= available_float_days` |
| 600 | `PHASED_HANDOFF_FEASIBLE` | `PHASED_DELIVERY` | Partial supplier handoff is operationally feasible |
| 610 | `PHASED_DOWNSTREAM_CONSUMABLE` | `PHASED_DELIVERY` | The downstream sequence can consume the phases |
| 620 | `PHASED_CONTRACT_PERMITTED` | `PHASED_DELIVERY` | The contract permits partial acceptance |
| 700 | `RESEQUENCE_PLAN_REVIEWED` | `DEPENDENT_WORK_RESEQUENCING` | A reviewed alternative sequence exists |
| 710 | `RESEQUENCE_PREREQUISITES_VALID` | `DEPENDENT_WORK_RESEQUENCING` | All alternative-sequence prerequisites are valid |
| 720 | `RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH` | `DEPENDENT_WORK_RESEQUENCING` | The alternative introduces no new critical-path breach |
| 800 | `ESCALATION_BASIS_ENFORCEABLE` | `CONTRACTUAL_ESCALATION` | An enforceable contractual basis exists |
| 810 | `ESCALATION_NOTICE_WINDOW_OPEN` | `CONTRACTUAL_ESCALATION` | The governing notice window remains open |
| 820 | `ESCALATION_RECORDS_COMPLETE` | `CONTRACTUAL_ESCALATION` | Required supporting records are complete |
| 900 | `MONITORING_OWNER_ASSIGNED` | `ACCEPT_AND_MONITOR` | A named accountable monitoring owner is recorded |
| 910 | `MONITORING_REVIEW_TIME_VALID` | `ACCEPT_AND_MONITOR` | A deterministic `next_review_at > constraints_as_of` is recorded |
| 920 | `MONITORING_ESCALATION_TRIGGER_REGISTERED` | `ACCEPT_AND_MONITOR` | Exactly one approved, fully specified, applicable, unsuperseded Monitoring Escalation Trigger published by `constraints_as_of` is referenced |
| 1000 | `COMPOSITE_COMPONENTS_COMPATIBLE` | `PROTECTED_SLOT_WITH_PHASED_DELIVERY` | The reviewed composite compatibility rule passes |

`MONITORING_REVIEW_TIME_VALID` requires `next_review_at` and
`constraints_as_of` to be comparable under the canonical temporal partial
order. An unresolved order is `UNKNOWN`; it never assumes a timezone or
precision and cannot make monitoring eligible.

Trigger-mode compatibility is evaluated before this registry. The composite
inherits every required rule of both components and adds
`COMPOSITE_COMPONENTS_COMPATIBLE`. Component results retain their component
scope; the composite never collapses them into one Boolean.

#### Composite Compatibility Review result

Core schema `composite-compatibility-review.v1` is an immutable, case-specific
hard-gate input. Its only supported compatibility-criteria schema is
`composite-compatibility-criteria.v1`; an unknown or different criteria
identifier/version is unsupported and cannot produce a decisive review. That
criteria schema contains exactly these domain-review attestations in this fixed
order:

| Order | Attestation code | Reviewed compatibility question |
| ---: | --- | --- |
| 10 | `COMPONENT_IDENTITIES_ALIGNED` | Are the named component versions, links, plan, subject, milestone, trigger mode, and scoped quantity/unit the intended common case? |
| 20 | `PROTECTED_SLOT_PHASE_PLAN_ALIGNED` | Does the reviewed phased-handoff plan remain compatible with the named protected-slot mechanism, supplier acceptance, and slot timing? |
| 30 | `PHASE_TOTAL_AND_SEQUENCE_VALID` | Is the reviewed phase quantity/unit total and milestone sequence operationally valid for the scoped plan? |
| 40 | `COMPONENT_OBLIGATIONS_NON_CONFLICTING` | Are the inherited contractual, supplier, capacity, and downstream-consumption obligations jointly compatible for this plan? |

These are governed domain-expert attestations owned by issue #17, not runtime
predicates. Decision Support never derives “preserves,” “valid,” or “conflicts”
from source columns or implements a second expert rules engine. Each
attestation occurs exactly once in schema order and contains its code, exactly
`ATTESTED_COMPATIBLE` or `ATTESTED_INCOMPATIBLE`, the immutable reviewer
reference/date/role, a registered rationale code, and non-empty ordered
evidence references/hashes. Duplicate, omitted, reordered, unknown, or
unevidenced attestations are malformed. The overall outcome is `COMPATIBLE`
exactly when all four values are `ATTESTED_COMPATIBLE`; it is `INCOMPATIBLE`
when at least one is `ATTESTED_INCOMPATIBLE`, with every incompatible code
retained in schema order. A review is fully specified only when all four
attestations and their required review/evidence fields exist; unavailable
content keeps the review `PROVISIONAL` and cannot make the gate decisive. Each
result contains:

- stable result ID/version, content hash, canonical `published_at`, nullable
  predecessor version, and supersession metadata;
- exact `composite_option_code = PROTECTED_SLOT_WITH_PHASED_DELIVERY` and
  option version, its ordered component option/version references, exact
  composite Driver-Action Link ID/version/hash, and trigger mode;
- exact subject identity, predeclared Case Constraint Snapshot ID,
  `composite_compatibility_input_digest`, and `constraints_as_of`;
- one closed outcome, `COMPATIBLE` or `INCOMPATIBLE`;
- exact compatibility-criteria identifier/version
  `composite-compatibility-criteria.v1` and ordered attestation results;
- review status, exactly `PROVISIONAL`, `APPROVED`, `REJECTED`, or `RETIRED`;
  and
- reviewer role, review date, immutable review reference, registered review
  reason, and ordered evidence references/hashes under the same status-dependent
  cardinality used by Monitoring Escalation Triggers.

The compatibility input digest is acyclic and computed before the review
result exists:

```text
composite_compatibility_input_digest =
    sha256(canonical-scientific-json.v1({
      snapshot_id,
      subject_identity,
      causal_decision_at,
      constraints_as_of,
      ordered_snapshot_facts_excluding_COMPOSITE_COMPATIBILITY_REVIEW_REF
    }))
```

The final Case Constraint Snapshot then includes the exact review result
reference/hash and computes its ordinary content hash. Decision Support
recomputes the excluded-field projection from that final snapshot and requires
the digest to match the review result; neither hash includes itself.

The snapshot reference must resolve to the exact unique unsuperseded result
provably published no later than `constraints_as_of`. Only an `APPROVED`, fully
specified, identity-matching result is decisive: `COMPATIBLE` makes
`COMPOSITE_COMPONENTS_COMPATIBLE` `SATISFIED`, while `INCOMPATIBLE` makes it
`UNSATISFIED`. An absent fact, a later or temporally incomparable result, a
`PROVISIONAL`, `REJECTED`, or `RETIRED` result, or a supplied superseded result
makes the Constraint Result `UNKNOWN` and therefore suppresses the composite
through `REQUIRED_CONSTRAINT_UNKNOWN`. Its deterministic explanation records
exactly `COMPOSITE_REVIEW_MISSING`, `COMPOSITE_REVIEW_NOT_AVAILABLE_AT_CUTOFF`,
`COMPOSITE_REVIEW_NOT_APPROVED`, `COMPOSITE_REVIEW_RETIRED`, or
`COMPOSITE_REVIEW_SUPERSEDED`, as applicable. Multiple effective results,
malformed/dangling references, or any component/link/trigger/subject/snapshot
identity or compatibility-input-digest mismatch produces the global
schema/reference-integrity failure instead of guessing compatibility. Concrete
review content remains owned by issue #17.

### Advisory comparison values

Every active option attempts to derive:

| Dimension | Closed representation | Better direction |
| --- | --- | --- |
| Time to initiate | finite non-negative decimal `time_to_initiate_days`, or `UNKNOWN` | Lower |
| Contractual/relationship risk | `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN` | Lower |
| Operational disruption | `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN` | Lower |
| Reversibility | `EASILY_REVERSIBLE`, `PARTIALLY_REVERSIBLE`, `DIFFICULT_TO_REVERSE`, or `UNKNOWN` | More reversible |

Decision Support owns the advisory-rubric schema, registry, applicability
mapping, and result semantics. Library content may select a rubric but cannot
assert a case result. Free text cannot override an ordinal.

#### Advisory Rubric record and lifecycle

Each immutable Advisory Rubric version contains:

- stable rubric ID/version and nullable predecessor-version reference;
- exactly one dimension:
  `CONTRACTUAL_RELATIONSHIP_RISK`,
  `OPERATIONAL_DISRUPTION`, or `REVERSIBILITY`;
- a closed applicability declaration over exact option code/version and
  trigger mode;
- an ordered list of typed input declarations, each naming a closed Case
  Constraint Snapshot fact code, exact type, unit when applicable, and whether
  it is required;
- ordered rules with stable rule IDs, unique integer priorities, predicates
  over only the declared typed inputs, and exactly one value from the
  dimension's closed output scale;
- explicit rule precedence and completeness constraints;
- proposed or reviewed source/evidence references;
- review status, exactly `PROVISIONAL`, `APPROVED`, or `REJECTED`;
- reviewer role, review date, immutable review reference, and registered
  review-reason code using the same status-dependent cardinality as a
  Driver-Action Link; and
- content hash, `published_at`, and optional supersession reference.

An `APPROVED` rubric requires at least one recorded review from
`PRACTISING_CONSTRUCTION_PROJECT_MANAGER` or
`PRACTISING_PROCUREMENT_ENGINEER`. Approval also requires valid, non-overlapping
rule priorities and deterministic output for every complete input combination
claimed by the rubric. A status, applicability, typed-input, threshold,
priority, or output change creates a `PROVISIONAL` successor; it never mutates
an approved predecessor.

The domain-expert-validation ticket may review concrete candidate content but
does not originate hidden thresholds. Core has no implied default rubric,
ordinal, or option-to-rubric mapping.

#### Advisory result derivation

For each atomic option, and for a composite dimension declared with an exact
`COMPOSITE_SPECIFIC_RUBRIC`, evaluation follows this fixed order:

1. Resolve the option version's advisory-rubric declaration.
2. If it is `UNAVAILABLE_PENDING_REVIEW`, record `UNKNOWN`.
3. If it references a `PROVISIONAL` or `REJECTED` rubric, or one not published
   by `constraints_as_of`, record `UNKNOWN`.
4. If the approved rubric does not apply to the exact option version and
   trigger mode, record `UNKNOWN`.
5. Resolve every declared typed input using only eligible Case Constraint
   Snapshot evidence. An Advisory Result, result reference, free-text
   assessment, or bare ordinal is never an input.
6. If required evidence is missing, invalid, conflicting, or first known after
   `constraints_as_of`, record `UNKNOWN`.
7. Otherwise evaluate rules by ascending priority. Exactly one rule must
   determine the ordinal; no match or multiple matches records `UNKNOWN`.

Every `UNKNOWN` Advisory Result carries all applicable reasons in this closed
precedence:

| Priority | Reason code | Condition |
| ---: | --- | --- |
| 100 | `RUBRIC_UNAVAILABLE` | Declaration is `UNAVAILABLE_PENDING_REVIEW` |
| 110 | `RUBRIC_NOT_APPROVED` | Referenced rubric is provisional, rejected, or not yet published |
| 120 | `RUBRIC_NOT_APPLICABLE` | Approved rubric does not cover the exact option version and trigger mode |
| 200 | `RUBRIC_INPUT_MISSING` | A required declared input has no eligible evidence |
| 210 | `RUBRIC_INPUT_INVALID` | A declared input has the wrong type, unit, or value domain |
| 220 | `RUBRIC_INPUT_CONFLICT` | Eligible evidence does not establish one input value |
| 300 | `RUBRIC_RULE_NO_MATCH` | Complete inputs match no rule |
| 310 | `RUBRIC_RULE_AMBIGUOUS` | Complete inputs match more than one rule |
| 320 | `RUBRIC_COMPONENT_RESULT_UNKNOWN` | A `LEAST_FAVORABLE_COMPONENT_RESULTS.v1` composite has at least one component Advisory Result that is `UNKNOWN` |

A non-`UNKNOWN` Advisory Result contains the exact rubric ID/version/hash,
option code/version, trigger mode, subject and snapshot references,
`constraints_as_of`, ordered typed inputs and evidence references, matched rule
ID/priority, and closed ordinal. A malformed or dangling purported rubric
reference remains the global integrity failure defined above; the explicit
unavailability and review states are not dangling references.

`PROTECTED_SLOT_WITH_PHASED_DELIVERY` declares
`LEAST_FAVORABLE_COMPONENT_RESULTS.v1` for all three ordinal dimensions. For
each dimension, Decision Support evaluates the exact
`PROTECTED_PRODUCTION_SLOT` and `PHASED_DELIVERY` option-version rubric
declarations through steps 2-7 above against the same trigger mode,
`constraints_as_of`, and Case Constraint Snapshot. This component-scoped
advisory derivation runs even if the atomic component's standalone option
evaluation stopped before advisory evaluation; it does not resolve the
component's Driver-Action Link, make the component eligible, or borrow a
component benefit.

If either component result is `UNKNOWN`, the composite result is `UNKNOWN` with
`RUBRIC_COMPONENT_RESULT_UNKNOWN` plus every component-scoped underlying
reason; runtime does not select the known component. Otherwise risk and
disruption use the maximum under `LOW < MEDIUM < HIGH`, and reversibility uses
the least reversible value under
`EASILY_REVERSIBLE < PARTIALLY_REVERSIBLE < DIFFICULT_TO_REVERSE`. The
composite result stores both component Advisory Results and the derivation
policy version. A future `COMPOSITE_SPECIFIC_RUBRIC` declaration instead uses
only that exact approved/applicable rubric through the standard path and never
mixes it with component aggregation.

Atomic options use `DECLARED_CASE_INITIATION_TIME.v1`: one finite,
non-negative `time_to_initiate_days` fact with provenance. For a composite,
`PARALLEL` means the exact maximum of component times and `SEQUENTIAL` means
their exact sum; both require complete compatible component duration bases.
Any other reviewed composition must name an exact approved, applicable,
published-by-cutoff closed formula version and its typed inputs. A malformed or
dangling formula reference is the global schema/reference failure. The Core
`PROTECTED_SLOT_WITH_PHASED_DELIVERY` option declares
`UNAVAILABLE_PENDING_REVIEW`; runtime never guesses `PARALLEL`, `SEQUENTIAL`,
or another relation.

Every `UNKNOWN` time-to-initiate result carries all applicable reasons in this
closed precedence:

| Priority | Reason code | Condition |
| ---: | --- | --- |
| 100 | `TIME_TO_INITIATE_INPUT_UNAVAILABLE` | An atomic or component initiation-time fact is absent or not eligible by the cutoff |
| 110 | `TIME_TO_INITIATE_INPUT_INVALID` | A present initiation-time fact has an invalid value, type, provenance, or basis |
| 200 | `TIME_COMPOSITION_RULE_UNAVAILABLE` | The composite declaration is `UNAVAILABLE_PENDING_REVIEW` |
| 210 | `TIME_COMPOSITION_FORMULA_NOT_APPROVED` | The exact referenced formula is provisional, rejected, inapplicable, or not provably published by the cutoff |
| 220 | `TIME_COMPONENT_RESULT_UNKNOWN` | At least one component time is `UNKNOWN` under an otherwise usable composition declaration |
| 230 | `TIME_COMPONENT_BASIS_INCOMPATIBLE` | Component duration bases are not exactly compatible for maximum or sum |

An unavailable declaration is valid library content, not a missing schema
field. An actually absent or unknown declaration fails the library schema.
`UNKNOWN` remains visible and makes that dimension pairwise incomparable. It
does not become the favorable or unfavorable endpoint.

## Assumption and money contracts

Every selected benefit assumption, critical-path delay rate, direct action
cost, and case-specific composition input below carries `known_at`,
`recorded_at`, explicit `valid_through`, provenance, and the exact snapshot
reference. Its `known_at <= constraints_as_of` and, for a finite horizon,
`constraints_as_of <= valid_through` must both be provable; otherwise that
input is unavailable for the evaluation. `NO_EXPIRY` must be explicit. Editing
or adding one creates a new evaluation and never changes the upstream causal
`decision_at`.

Every referenced library, link, rule, rubric, default, and formula version
must have an immutable publication or approval time no later than
`constraints_as_of`. A later registry version may be used only in a new
snapshot and evaluation.

### Recoverable Fraction Assumption

An exposure-reduction or milestone-acceleration link has one:

```text
0 <= recoverable_fraction_assumption <= 1
```

The scalar represents the total share of the estimated exposure-effect days
assumed recoverable for that link in the current trigger mode, including
partial future or remaining scope where relevant.

The record contains link/version reference, trigger mode, reviewed default,
selected value, registered rationale, provenance, edited/not-edited status,
and review reference. It is never inferred from data.

The canonical ingestion contract contains original quantity but no trustworthy
remaining/undelivered-quantity fact. Core therefore does not calculate a
separate remaining-quantity share. A future source contract may add such a
fact only through a new contract and policy version.

### Critical Path Translation Assumption

An exposure-reduction or milestone-acceleration projection also has one:

```text
0 <= critical_path_translation_fraction_assumption <= 1
```

This scalar represents the declared share of assumption-based recovered
Supplier Milestone Slippage days that protects project critical-path days for
this subject and option. It is distinct from the recoverable fraction: one
translates the exposure effect to assumed supplier-milestone recovery, while
the other translates supplier-milestone recovery to assumed project-delay
protection.

There is no library or Driver-Action Link default for this case-specific
translation. The active-driver envelope requires at most one immutable
Critical Path Translation Assumption record for each exact subject identity,
option version, link/version, and trigger mode. The record contains its schema
version and occurrence/content hash; one selected value; registered rationale;
project/float provenance; `known_at` and `recorded_at`; and the exact immutable
Manager Attestation reference/hash that reviewed the selected value. It is
eligible only when its asserted operational fact was known no later than
`constraints_as_of`; the ordinary attestation rule cannot backdate required
upstream evidence.

No eligible record produces `CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE`.
Multiple eligible records or conflicting identities/values produce
`CRITICAL_PATH_TRANSLATION_FRACTION_INVALID`; runtime never chooses a favorable
record. An edited value is a new immutable reviewed record and therefore a new
Decision Support Evaluation. The fraction is never inferred from the causal
estimate, available float, or absence of a downstream delay fact.

Missing or invalid values suppress monetary evaluation for an active
exposure-reduction or milestone-acceleration option.

### Consequence Benefit Assumption

A consequence-mitigation link has exactly one basis:

| Basis | Required values | Meaning |
| --- | --- | --- |
| `PROJECT_DELAY_DAYS` | lower, central, and upper non-negative project-delay days protected plus the resolved canonical slippage duration basis | Operational project-impact assumption |
| `DIRECT_MONETARY_VALUE` | lower, central, and upper non-negative money values | Avoided contractual or operational cost assumption |

For either basis:

```text
lower <= central <= upper
```

The record contains reviewed default values, selected values, currency when
applicable, rationale, provenance, edited/not-edited status, and review
reference. It is always tagged `OPERATIONAL_ASSUMPTION_ONLY`.

It never references the causal effect estimate and never populates recovered
Supplier Milestone Slippage days.

### Cost of critical-path delay

`cost_of_critical_path_delay_per_day` is:

```text
{
  amount: finite non-negative decimal,
  currency: ISO currency code,
  day_basis: CANONICAL_SLIPPAGE_DAY,
  resolved_duration_basis: CALENDAR_DAY | ELAPSED_86400_SECOND_DAY
}
```

This is one case-scoped parameter, not an option-scoped parameter. The active-
driver envelope contains at most one hash-bound rate record, and every
schedule-valued option in that evaluation consumes that same exact record.
When at least one schedule-valued option reaches rate validation, absence of
the case rate records `CRITICAL_PATH_DELAY_RATE_UNAVAILABLE` for every such
option. More than one rate record, an option-qualified rate, or conflicting
case-rate identities is a case-wide cardinality error and produces
`DECISION_SUPPORT_INPUT_SCHEMA_INVALID`; runtime never chooses among rates.
The single selected/default value, provenance, edit indicator, and content hash
enter the Decision Support input digest once.

`CANONICAL_SLIPPAGE_DAY` means the upstream outcome contract's calendar day for
date values or exact 86,400-second day for datetimes/instants. This fixes the
duration unit only; the monetary rate values a project critical-path delay
day, not a Supplier Milestone Slippage day. A business-day, shift-day, or
unspecified basis is invalid. `resolved_duration_basis` must equal the sealed
engine request's exact `canonical_slippage_duration_basis`.

The record preserves reviewed default, selected value, rationale, provenance,
and edited/not-edited status.

The rate is required only by a schedule-valued option: every
exposure-reduction or milestone-acceleration option, and a
consequence-mitigation option whose basis is `PROJECT_DELAY_DAYS`. A
consequence-mitigation option with `DIRECT_MONETARY_VALUE` and the
`ACCEPT_AND_MONITOR` option do not consume this rate.

For each schedule-valued option, an absent rate or one unavailable because
`known_at > constraints_as_of` produces
`CRITICAL_PATH_DELAY_RATE_UNAVAILABLE`. A present rate with a malformed or
negative amount, invalid ISO currency code, unsupported day basis, or invalid
provenance produces `CRITICAL_PATH_DELAY_RATE_INVALID`. Either reason suppresses
only that option before arithmetic; it does not suppress a direct-monetary or
monitor-only option.

### Direct action cost

Every atomic option uses `DECLARED_TOTAL_COST.v1`: one required finite,
non-negative total case cost in the evaluation currency, with provenance,
rationale, and assumption status. An optional ordered component breakdown may
contain at most 100 components and may be shown only when its exact sum equals
the declared total. Absence of a breakdown never authorizes the system to
invent one.

`ACCEPT_AND_MONITOR` uses `DECLARED_MONITORING_TOTAL.v1`. A total of zero is
valid only when explicitly recorded; missing cost is not silently zero.

The governed composite uses `DECLARED_COMPOSITE_TOTAL.v1`: one required
reviewed case total plus an optional component-and-overlap breakdown that must
contain at most 100 components and reconcile exactly to that total. Runtime
never sums atomic defaults or guesses which costs overlap.

Core does not infer recurring horizons, discount cash flows, calculate tax,
convert currencies, or use a negative cost to represent a benefit.

Missing required total cost produces `ACTION_COST_UNAVAILABLE`; an invalid or
non-reconciling total, or a breakdown over 100 components, produces
`ACTION_COST_INVALID`.

Every present, otherwise valid monetized value in one evaluation uses the exact
same currency. Two different well-formed ISO currency codes produce global
`DECISION_SUPPORT_CURRENCY_MISMATCH`, even if one affected option has another
suppression reason; runtime does not convert. Absence or an invalid currency
field is governed by the applicable option-suppression reason and is not
fabricated into a currency mismatch.

### Exact arithmetic and rounding

Decision arithmetic interprets each upstream `f64:` hexadecimal value as its
exact finite binary rational and each `decimal:` input as its exact decimal
rational. The formulas in this contract use only multiplication, addition, and
subtraction, so their denominators contain only factors of two and five and
have an exact finite decimal representation. There is no intermediate
rounding. Comparisons use the exact unrounded rational values. Presentation
rounding is controlled by the language/presentation policy and never feeds
back into eligibility, dominance, or a digest.

Every rational is reduced to a canonical signed numerator and positive
denominator after each operation. Every integer materialized for parsing,
normalization, arithmetic, or exact comparison, including a cross-product,
must have bit length at most `4096`. Exceeding that bound produces global
`DECISION_SUPPORT_ARITHMETIC_INVALID`; partial option results are not retained.
The fixed Core formulas and the bounded numeric inputs above remain within the
limit. Implementations must use integer/rational operations whose behavior is
independent of ambient Decimal precision, rounding mode, locale, or process
configuration.

Every unrounded calculated value is stored and hashed as
`{numerator, denominator}` using canonical base-10 integers with no plus sign,
whitespace, or redundant leading zero; the denominator is positive and the
pair is relatively prime. A decimal rendering is presentation derived from
that pair and is never a replacement input to later arithmetic.

## Benefit and value calculations

### Exposure translation

Let:

- `L`, `E`, and `U` be the lower bound, point estimate, and upper bound of the
  verified supported exposure effect in Supplier Milestone Slippage days;
- `f` be the selected recoverable fraction;
- `p` be the selected critical-path translation fraction;
- `D` be cost of project critical-path delay per canonical day; and
- `C` be direct action cost.

Then:

```text
recovered_supplier_milestone_days_lower   = L * f
recovered_supplier_milestone_days_central = E * f
recovered_supplier_milestone_days_upper   = U * f

project_delay_days_protected_lower   = recovered_supplier_milestone_days_lower   * p
project_delay_days_protected_central = recovered_supplier_milestone_days_central * p
project_delay_days_protected_upper   = recovered_supplier_milestone_days_upper   * p

gross_avoided_delay_value_lower   = project_delay_days_protected_lower   * D
gross_avoided_delay_value_central = project_delay_days_protected_central * D
gross_avoided_delay_value_upper   = project_delay_days_protected_upper   * D

net_assumption_value_lower   = gross_avoided_delay_value_lower   - C
net_assumption_value_central = gross_avoided_delay_value_central - C
net_assumption_value_upper   = gross_avoided_delay_value_upper   - C
```

The schedule-protection basis is `PROJECT_DELAY_DAYS`, and the Pareto schedule
value is `project_delay_days_protected_central`. These durations inherit the
sealed engine request's exact `canonical_slippage_duration_basis`. Both
recovered supplier-milestone days and protected project-delay days remain visible;
neither is renamed as the other. Recovered supplier-milestone days are an
auditable intermediate result, never the schedule-comparison value.

### Consequence mitigation

For `PROJECT_DELAY_DAYS`, let `PL`, `PE`, and `PU` be the declared lower,
central, and upper project-delay days protected:

```text
gross_consequence_value_{lower,central,upper} = P{L,E,U} * D
net_assumption_value_{lower,central,upper} =
    gross_consequence_value_{lower,central,upper} - C
```

The schedule-protection basis is `PROJECT_DELAY_DAYS`; its declared duration
basis and the rate's resolved duration basis both equal the sealed engine
request's exact `canonical_slippage_duration_basis` before multiplication.

For `DIRECT_MONETARY_VALUE`, let `ML`, `ME`, and `MU` be the declared monetary
benefit range:

```text
net_assumption_value_{lower,central,upper} = M{L,E,U} - C
```

The schedule-protection basis is `NOT_APPLICABLE`.

### Monitor-only

`ACCEPT_AND_MONITOR` exposes no recovered-days or benefit projection. Its
schedule-protection basis is `NOT_APPLICABLE`. Any declared monitoring cost
remains visible, but the option is governed by the fallback policy rather than
the active positive-value gate.

### Projection semantics

Every lower/central/upper result is labelled:

```text
ASSUMPTION_BASED_PROJECTION_RANGE
```

The range is not:

- a confidence or prediction interval for the Intervention Option;
- a probability that the option succeeds;
- an expected intervention effect;
- evidence that the action recovers the projected days; or
- permission to say the action "will save" time or money.

### Active value gate

For each active option whose required constraints and assumptions pass:

| Condition | Value status | Recommendation eligibility |
| --- | --- | --- |
| `net_central <= 0` | `NON_POSITIVE_CENTRAL_VALUE` | Suppressed |
| `net_central > 0` and `net_lower <= 0` | `VALUE_SENSITIVE` | Eligible for trade-off; prohibited as sole dominant recommendation |
| `net_lower > 0` | `ROBUSTLY_POSITIVE` | Eligible for comparison and possible sole recommendation |

The word `ROBUSTLY` here qualifies the option's assumption-based monetary
range only. It is not the causal Robustness Grade and must never be rendered
without `VALUE`.

## Composite derivation

For `PROTECTED_SLOT_WITH_PHASED_DELIVERY`:

1. Required constraints are the ordered union of both component rule sets plus
   `COMPOSITE_COMPONENTS_COMPATIBLE`.
2. Any component `UNSATISFIED` or `UNKNOWN` suppresses the composite.
3. Benefit is calculated once from the composite's approved primary
   Driver-Action Link and one recoverable fraction.
4. Component benefit projections are never summed.
5. The composite record supplies an explicit versioned cost formula. Runtime
   cannot guess whether component costs overlap.
6. Time to initiate uses the exact closed declaration above. Core explicitly
   records `UNAVAILABLE_PENDING_REVIEW`, yielding
   `TIME_COMPOSITION_RULE_UNAVAILABLE`; runtime never guesses sum versus
   maximum.
7. Contractual/relationship risk and disruption use the exact composite
   advisory-derivation declaration above.
8. Reversibility uses that same closed declaration and unknown-propagation
   rule.
9. Every value retains component evidence and derivation-rule references.

A missing composite cost total produces `ACTION_COST_UNAVAILABLE`; an invalid
or non-reconciling total produces `ACTION_COST_INVALID`. A missing component
time or time-composition rule is advisory `UNKNOWN` and never by itself
suppresses the composite. An incompatible currency is the global failure
defined above. Runtime never fills a default.

## Option suppression and inspectability

### Evaluation stages

For each option entry in the exact Intervention Library version, in display
order:

1. Check the exact option version's lifecycle status. If it is `RETIRED`,
   record `OPTION_RETIRED`, set all four evidence-tag slots to
   `NOT_EVALUATED`, and stop that option.
2. Check trigger-mode compatibility.
3. If trigger mode is incompatible, record
   `TRIGGER_MODE_INCOMPATIBLE`, set `MECHANISTIC_LINK`,
   `RULE_BASED_ELIGIBILITY`, and `ASSUMPTION_BASED_BENEFIT` to
   `NOT_EVALUATED`, and stop that option before link resolution.
4. Otherwise resolve the exact effective Driver-Action Link.
5. If the link is missing, not available by the cutoff, superseded,
   provisional, or rejected, suppress before constraints and benefit
   calculation.
6. Otherwise evaluate every applicable required and advisory rule.
7. Validate every option-applicable cost, critical-path delay rate, and benefit
   assumption even when a required constraint is unsatisfied, so independently
   knowable reasons remain visible.
8. Calculate projections only when all required constraints and inputs pass.
9. Apply the active value gate.

Dominated options are not suppressed. They remain eligible, retain all values,
and appear in the comparison disclosure.

### Closed suppression reasons and precedence

Every reason stores its stable code, category rank, applicable Constraint Rule
priority, option/component scope, evidence references, and deterministic
explanation template.

| Category rank | Code | Condition |
| ---: | --- | --- |
| 90 | `OPTION_RETIRED` | The exact library-bound option version is retired |
| 100 | `TRIGGER_MODE_INCOMPATIBLE` | Current trigger mode is not allowed |
| 200 | `DRIVER_ACTION_LINK_MISSING` | No exact link version exists |
| 205 | `DRIVER_ACTION_LINK_NOT_AVAILABLE_AT_CUTOFF` | The supplied exact link version is not provably published no later than `constraints_as_of` |
| 210 | `DRIVER_ACTION_LINK_PROVISIONAL` | Exact link is provisional and therefore speculative/unreviewed |
| 220 | `DRIVER_ACTION_LINK_REJECTED` | Exact link was rejected |
| 230 | `DRIVER_ACTION_LINK_SUPERSEDED` | The supplied link version has an effective successor published by `constraints_as_of` |
| 300 | `REQUIRED_CONSTRAINT_UNSATISFIED` | Required rule is `UNSATISFIED`; tie-break by Constraint Rule priority |
| 400 | `REQUIRED_CONSTRAINT_UNKNOWN` | Required rule is `UNKNOWN`; tie-break by Constraint Rule priority |
| 500 | `RECOVERABLE_FRACTION_UNAVAILABLE` | Required exposure-translation assumption is absent |
| 510 | `RECOVERABLE_FRACTION_INVALID` | Fraction is outside `[0,1]` or malformed |
| 520 | `CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE` | Required critical-path translation assumption is absent |
| 530 | `CRITICAL_PATH_TRANSLATION_FRACTION_INVALID` | Critical-path fraction is outside `[0,1]` or malformed |
| 540 | `CRITICAL_PATH_DELAY_RATE_UNAVAILABLE` | A schedule-valued option's required critical-path delay rate is absent or not available by `constraints_as_of` |
| 550 | `CRITICAL_PATH_DELAY_RATE_INVALID` | A schedule-valued option's rate amount, currency code, day basis, or provenance is invalid |
| 560 | `CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE` | Required consequence assumption is absent |
| 570 | `CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID` | Range, basis, unit, provenance, or ordering is invalid |
| 580 | `ACTION_COST_UNAVAILABLE` | Required direct-cost component is absent |
| 590 | `ACTION_COST_INVALID` | Direct cost is malformed, negative, or unsupported |
| 600 | `NON_POSITIVE_CENTRAL_NET_VALUE` | Active option has `net_central <= 0` |

Within one option, reasons sort by category rank, then Constraint Rule priority
where present, then registered code order. The first is primary; all others
remain ordered secondary reasons. Discovery time, asynchronous completion,
display label, and free-text sorting never affect precedence.

`NOT_APPLICABLE` is never a suppression reason when legitimately derived.

The evaluation-level reason
`VALUE_SENSITIVE_BASELINE_UNAVAILABLE` applies only when no active option is
`ROBUSTLY_POSITIVE`, one or more active options are `VALUE_SENSITIVE`, and
`ACCEPT_AND_MONITOR` is ineligible. The sensitive options remain visible as
evaluated but are not recommendation-eligible. The result is
`NO_ELIGIBLE_OPTION`, with the monitoring option's exact constraint reasons.
The system never pairs two value-sensitive active options merely to force a
choice. When any robustly positive option exists, monitoring ineligibility does
not suppress it or change the active comparison branch.

## Pareto comparison

### Comparison dimensions

Active recommendation-eligible options compare on the following closed,
versioned dimension and normal-pivot codes:

| Frozen order | Pivot code | Dimension | Better direction |
| ---: | --- | --- | --- |
| 1 | `SCHEDULE_PROTECTION` | Central assumption-based schedule protection | Higher |
| 2 | `DIRECT_ACTION_COST` | Direct action cost | Lower |
| 3 | `TIME_TO_INITIATE` | Time to initiate | Lower |
| 4 | `CONTRACTUAL_RELATIONSHIP_RISK` | Contractual/relationship risk | Lower |
| 5 | `OPERATIONAL_DISRUPTION` | Operational disruption | Lower |
| 6 | `REVERSIBILITY` | Reversibility | More reversible |

The only non-dimension pivot codes are `VALUE_UNCERTAINTY`,
`TIED_UNDER_POLICY`, `EQUAL_COMPARISON_PROFILE`, and
`INCOMPARABLE_EVIDENCE_GAP`. These ten values are the complete pivot-code set
for comparison policy version `1`; an unknown pivot code is an integrity
failure. `TIED_UNDER_POLICY` may additionally appear as the explicitly named
ordering annotation described below, but no display label is serialized as a
pivot.

Net assumption value is the active eligibility gate and candidate-ordering
value. It is not a second Pareto dimension that double counts schedule
protection and direct cost.

Schedule protection has one comparison basis:

- `PROJECT_DELAY_DAYS` for every schedule-affecting option; or
- `NOT_APPLICABLE` for a direct-monetary or monitor-only option.

For exposure-reduction and milestone-acceleration options, the comparison value
is `project_delay_days_protected_central` after applying the separately
declared critical-path translation fraction. Recovered supplier-milestone days
remain visible and auditable but never enter the Pareto schedule dimension.
Consequence-mitigation options with a `PROJECT_DELAY_DAYS` basis compare their
declared central project-delay days protected directly.

All eligible `PROJECT_DELAY_DAYS` comparison values therefore have the same
resolved canonical slippage duration basis. An option with a missing or
incompatible basis is suppressed before this stage; Pareto comparison never
converts duration values.

Applicable `TIME_TO_INITIATE` values retain their exact duration bases and are
comparable only when those complete bases are equal. An incompatible pair is
incomparable; it never becomes equality or a unitless ordering.

If both options use `NOT_APPLICABLE`, the schedule dimension is not
pair-applicable and is omitted from that pair's dominance/equality proof. If
exactly one option uses `NOT_APPLICABLE`, the dimension is incomparable and
records `ONE_SIDED_NOT_APPLICABLE` when it blocks candidate selection.
`NOT_APPLICABLE` never becomes zero or equality.

Any `UNKNOWN` advisory value makes that dimension incomparable. Incomparability
never becomes equality.

### Dominance

Option A strictly Pareto-dominates option B only when:

1. every pair-applicable comparison dimension is comparable and no dimension
   is applicable to only one option;
2. A is no worse than B on every pair-applicable dimension; and
3. A is strictly better than B on at least one pair-applicable dimension.

A dimension that is `NOT_APPLICABLE` to both options is absent from this proof,
not equal. A pair with no pair-applicable dimensions cannot establish strict
dominance.

A sole dominant action exists only when one `ROBUSTLY_POSITIVE` option
dominates every other active recommendation-eligible option. The result then
becomes `RECOMMENDATION_AVAILABLE`.

A `VALUE_SENSITIVE` option can never become the sole dominant recommendation,
even if its central values otherwise dominate.

### Accept-and-monitor fallback

`ACCEPT_AND_MONITOR` is not an ordinary active option in every Pareto set:

1. If at least one active option is `ROBUSTLY_POSITIVE`, compare active
   positive options only. Keep monitoring visible as a baseline outside
   dominance, candidate, and runner-up selection. Monitoring eligibility does
   not change which robust/value-sensitive comparison branch applies.
2. If active options are only `VALUE_SENSITIVE`, present the highest-central-
   value sensitive option and eligible monitoring as a trade-off with pivot
   `VALUE_UNCERTAINTY`. An exact central-value tie uses ascending library
   display order and records `TIED_UNDER_POLICY`. The sensitive candidate has
   `candidate_basis = VALUE_SENSITIVE_OPTION`; monitoring has
   `candidate_basis = MONITORING_BASELINE`. Neither basis claims Pareto
   optimality.
3. If active options are only `VALUE_SENSITIVE` and monitoring is ineligible,
   emit `NO_ELIGIBLE_OPTION` with
   `VALUE_SENSITIVE_BASELINE_UNAVAILABLE`.
4. If no active option has positive central net value, emit a monitoring Action
   Recommendation when all monitoring constraints and cost inputs pass, with
   `selection_basis = MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION` and
   `runner_up = null`.
5. If monitoring also fails or is unknown, emit `NO_ELIGIBLE_OPTION`.

Monitoring is never evaluated when the global verdict permission gate is
false.

## Recommendation, runner-up, and trade-off rules

Every Action Recommendation has exactly one closed `selection_basis`:

| Selection basis | Applicable branch | `runner_up` |
| --- | --- | --- |
| `SOLE_ELIGIBLE_OPTION` | Exactly one active recommendation-eligible option exists and is `ROBUSTLY_POSITIVE` | `null` |
| `UNIVERSAL_PARETO_DOMINANCE` | One robustly positive option dominates every other active recommendation-eligible option | Highest-central-net remaining active eligible option, with the tie rule below |
| `MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION` | No active option has positive central net value and monitoring is eligible | `null` |
| `MANAGER_TRADEOFF_SELECTION` | One candidate is selected from an unchanged current trade-off result | `null`; the other candidate is `presented_alternative` |

No other selection-basis code is valid. A null runner-up is explicit and never
filled with a suppressed, retired, monitoring-baseline, or unselected trade-off
option.

### Universal-dominance case

When exactly one active recommendation-eligible option exists and it is
`ROBUSTLY_POSITIVE`, it becomes the singular Action Recommendation with:

```text
selection_basis = SOLE_ELIGIBLE_OPTION
```

This is selection by absence of an alternative, not a dominance claim.
Unknown advisory values remain visible. `runner_up = null`.

When two or more active recommendation-eligible options exist and one robustly
positive option dominates every other active recommendation-eligible option:

- it becomes the singular Action Recommendation;
- `selection_basis = UNIVERSAL_PARETO_DOMINANCE`;
- the dominance matrix and exact proof are stored; and
- the runner-up is the remaining active recommendation-eligible option with the
  highest central net assumption value.

Runner-up ties use ascending Intervention Library display order and record
`TIED_UNDER_POLICY`. Display order does not imply superiority.

### Value-sensitive frontier with robust safety alternative

When at least one active `ROBUSTLY_POSITIVE` option exists but every option on
the active Pareto frontier is `VALUE_SENSITIVE`:

1. Candidate A is the frontier option with highest central net assumption
   value. A tie uses ascending library display order and records
   `TIED_UNDER_POLICY`.
2. Candidate B is the active `ROBUSTLY_POSITIVE` option with highest central
   net assumption value, even though it is Pareto-dominated. A tie uses
   ascending library display order and records `TIED_UNDER_POLICY`.
3. Candidate A has `candidate_basis = PARETO_FRONTIER_OPTION`; Candidate B has
   `candidate_basis = ROBUST_SAFETY_ALTERNATIVE`. The result explicitly says
   that Candidate B is a governed robust safety alternative and makes no
   frontier, Pareto-optimality, or superiority claim for it.
4. The pivot is `VALUE_UNCERTAINTY`. The exact dominance matrix and the value
   intervals for both candidates remain visible.
5. The terminal outcome is `TRADEOFF_REQUIRES_MANAGER_CHOICE`. Neither option
   becomes an automatic Action Recommendation; a valid manager trade-off
   selection may select either exact candidate under the ordinary selection
   rules.
6. Monitoring remains visible when applicable but cannot be Candidate B or
   alter this branch. Monitoring ineligibility does not suppress the trade-off.
7. Every other eligible frontier option and every other active robustly
   positive option remains available in progressive disclosure.

This branch does not apply when no active `ROBUSTLY_POSITIVE` option exists.
The only-value-sensitive monitoring-baseline rules above remain authoritative
for that case.

### Frontier trade-off case

Otherwise, if no permitted robustly positive option universally dominates and
the active Pareto frontier retains at least one `ROBUSTLY_POSITIVE` option:

1. Form the active Pareto frontier.
2. Candidate A is the frontier option with highest central net assumption
   value. A tie uses library display order and records `TIED_UNDER_POLICY`.
3. If Candidate A and at least one other frontier option have exactly equal
   central net assumption value, and every comparison dimension applicable to
   the pair is known, basis-compatible, comparable, and exactly equal,
   Candidate B is the first such option in ascending library display order,
   the pivot is `TIED_UNDER_POLICY`, and no superiority claim is made. A
   dimension that is `UNKNOWN`, incompatible, or applicable to only one option
   cannot satisfy this branch.
4. Otherwise, in the frozen comparison-dimension order, find the first
   dimension on which
   another frontier option is comparably and strictly better than A.
5. If such a normal pivot exists, Candidate B is the frontier option best on
   that pivot dimension. Remaining ties use higher central net value, then
   library display order.
6. If no normal strict pivot exists and one or more remaining frontier options
   have every pair-applicable dimension known, basis-compatible, comparable,
   and exactly equal to Candidate A, no dimension is applicable to only one
   option, but a different central net assumption value, Candidate B is the
   highest-central-net such option. A remaining tie uses library display order.
   The pivot is `EQUAL_COMPARISON_PROFILE`.
7. For `EQUAL_COMPARISON_PROFILE`, store both complete comparison profiles and
   exact central net values. The net difference is candidate-ordering context
   only; it is not a Pareto dimension, superiority claim, or dominance proof.
8. If neither a normal pivot nor an equal-profile pivot exists, apply the
   evidence-gap fallback below.
9. Store the exact pivot, values, units, bases, and difference or equality
   proof, as applicable.
10. Keep every other eligible frontier option available in progressive
   disclosure.

The terminal outcome is `TRADEOFF_REQUIRES_MANAGER_CHOICE`; neither candidate
is called recommended or runner-up. Both candidates have
`candidate_basis = PARETO_FRONTIER_OPTION`.

Each `Recommendation Candidate` is a nested immutable projection of one exact
eligible option version within one Decision Support Evaluation. Its closed
identity inside that evaluation is `{option_code, option_version}`; the
Intervention Library guarantees that this pair occurs at most once. A complete
candidate reference is
`{evaluation_occurrence_id, option_code, option_version}`. There is no separate
opaque or randomly generated candidate ID. A trade-off result contains exactly
two distinct candidate records, labeled A and B only for presentation order.
Each record includes its complete candidate reference, exact comparison
profile, provenance, deterministic ordering evidence, and one closed
`candidate_basis` value: `PARETO_FRONTIER_OPTION`, `VALUE_SENSITIVE_OPTION`,
`ROBUST_SAFETY_ALTERNATIVE`, or `MONITORING_BASELINE`.
`ROBUST_SAFETY_ALTERNATIVE` is valid only for Candidate B in the value-
sensitive-frontier branch above; `MONITORING_BASELINE` is valid only for the
only-value-sensitive fallback trade-off, where its paired active option uses
`VALUE_SENSITIVE_OPTION`. Every candidate in the ordinary frontier trade-off
uses `PARETO_FRONTIER_OPTION`. The result content hash covers both records and
their order.

### Evidence-gap fallback

If the frontier is unresolved only because one or more dimensions are
`UNKNOWN`, initiation-duration bases are incompatible, or a dimension is
applicable to only one option, and no candidate is known to be strictly better
than A on a normal pivot:

- Candidate B is the remaining frontier option with next-highest central net
  assumption value; a central-net tie uses ascending Intervention Library
  display order and records `TIED_UNDER_POLICY` as an ordering annotation;
- the pivot is `INCOMPARABLE_EVIDENCE_GAP`;
- every blocking dimension records exactly one of `UNKNOWN`,
  `INCOMPATIBLE_INITIATION_DURATION_BASIS`, or
  `ONE_SIDED_NOT_APPLICABLE`; and
- no superiority claim is made.

As a trade-off pivot, `TIED_UNDER_POLICY` is reserved for exact equality of
central net value and every pair-applicable comparison dimension after all
such dimensions are known, basis-compatible, and comparable. Its use as an
ordering annotation elsewhere records equality only of that explicitly named
ordering key; it does not assert equal comparison profiles.

## Trade-off selection and authorization boundary

A valid trade-off selection contains:

- schema identifier/version, immutable selection occurrence ID, and selection
  envelope content hash;
- Decision Support evaluation-series ID;
- evaluation occurrence ID and input digest;
- exact terminal result reference and content hash;
- exactly one of the two complete candidate references;
- an immutable Governance & Audit occurrence reference and content hash; and
- canonical `selected_at` and verified `available_at`, with provable
  `selected_at <= available_at`; and
- no changed assumption, constraint, or option value.

Decision Support validates one selection delivery attempt in this closed
precedence:

1. Validate the delivery-attempt envelope and referenced Trade-off Selection
   envelope shapes and exact supported schema versions. Verify every copied
   evaluation/result/candidate field in the attempt exactly equals its
   selection source. A malformed or unsupported envelope is an ingress
   rejection rather than a structurally valid delivery attempt.
2. Resolve the named evaluation series. If it does not exist, atomically
   publish the attempt's one immutable pre-currentness validation result and
   stop.
3. Verify the Governance & Audit occurrence type, identity, and content hash
   and its exact agreement with the selection envelope. A failure atomically
   publishes the attempt's one immutable pre-currentness validation result and
   stops.
4. At the immutable delivery-attempt time, invoke the complete advice-
   currentness procedure with
   `operation_kind = TRADEOFF_SELECTION_ACCEPTANCE` and operation payload equal
   to this exact trade-off selection-delivery-attempt occurrence/hash, with
   `currentness_checked_at = delivery_attempt.available_at`. Its intrinsic
   validation, unique operation claim, exact consumer binding, and terminal
   replay all run before any authoritative-head read. Therefore exact replay
   of this delivery attempt returns its one prior terminal result. For a new
   operation, defer its kind-specific consuming-result staging and terminal
   publication until steps 6 through 8 complete.
5. Continue the currentness procedure. The authoritative series head must be
   `EVALUATION`, and its occurrence ID, digest, and result hash must equal the
   selection. An installed
   `ADVICE_CURRENTNESS_INVALIDATION` or
   `CURRENTNESS_NOT_AUTHORITATIVE_HEAD` returns
   `TRADEOFF_SELECTION_STALE`; only the former publishes an invalidation, and
   neither can mutate a successor or accept snapshot-valid but expired advice.
6. Verify the unchanged head outcome is
   `TRADEOFF_REQUIRES_MANAGER_CHOICE`.
7. Verify that exactly one of its exact two candidates is named.
8. Under the currentness-operation terminal claim and one final exact-head
   comparison, atomically publish the currentness check, selection result, and
   every applicable selection side record. Inspect the selection claim for the
   exact evaluation occurrence. If absent, claim it with this
   exact selection and the successful currentness-operation/check references
   and publish once. If it already contains the same selection occurrence/hash
   and candidate reference, return the existing recommendation idempotently;
   the new delivery attempt's selection-result occurrence retains the new
   operation-bound check,
   while the existing recommendation retains its original creation proof. If
   it contains any different selection, publish the conflict selection result
   with its operation-bound check but publish no claim or recommendation.

The selection cannot supply or override the current head. Decision Support
does not rerun, recalculate, or rerank. A valid selection produces one Action
Recommendation with:

```text
selection_basis = MANAGER_TRADEOFF_SELECTION
```

The other candidate remains referenced as the presented alternative.

A changed assumption or Case Constraint Snapshot publishes a successor and
makes the prior candidates stale. A repeated identical evaluation also has a
new occurrence ID and becomes the series head; a selection bound to the older
occurrence is stale even when the digest recurs. A
`PERMISSION_INVALIDATION`, `EVIDENCE_INTEGRITY_INVALIDATION`, or
`ADVICE_CURRENTNESS_INVALIDATION` head also makes every predecessor-bound
selection stale. Any non-accepted selection result produces no Action
Recommendation.

Selection validation has its own closed response vocabulary and never mutates the referenced
Decision Support Evaluation:

| Priority | Selection result | Meaning |
| ---: | --- | --- |
| 100 | `TRADEOFF_SELECTION_SCHEMA_INVALID` | A required envelope field is missing, malformed, has invalid cardinality, or contains an unknown closed code |
| 110 | `TRADEOFF_SELECTION_SCHEMA_UNSUPPORTED` | The schema identifier or version is not the exact supported value |
| 200 | `TRADEOFF_SELECTION_SERIES_NOT_FOUND` | The named evaluation series does not exist |
| 300 | `TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH` | The Governance & Audit reference is missing, malformed, hash-mismatched, wrong-type, or disagrees with the envelope |
| 400 | `TRADEOFF_SELECTION_STALE` | Named occurrence/digest/result hash does not exactly equal the authoritative current series head, or that head is any invalidation kind |
| 500 | `TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF` | The unchanged current head is not `TRADEOFF_REQUIRES_MANAGER_CHOICE` |
| 600 | `TRADEOFF_SELECTION_INVALID_CANDIDATE` | The selection does not name exactly one of the exact candidate pair |
| 650 | `TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT` | The same immutable selection was accepted by an earlier delivery attempt for this evaluation occurrence; return its existing recommendation and publish only this attempt-bound result/check, never a second claim or recommendation |
| 660 | `TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED` | A different selection already claimed this evaluation occurrence; publish no recommendation |
| 700 | `TRADEOFF_SELECTION_ACCEPTED` | Evaluation and digest are current and the named candidate is one of the exact pair |

Codes 100 and 110 reject malformed or unsupported ingress before a structurally
valid delivery attempt exists; safely parsed identifiers may appear in that
response but are never guessed. Codes 200 and 300 apply to a structurally valid
supported attempt before a currentness operation exists. They publish exactly
one immutable `tradeoff-selection-validation-result.v1`, whose deterministic
key is
`sha256(canonical-scientific-json.v1({schema_identifier_and_version,
delivery_attempt_ref_and_hash}))`. That result contains the exact attempt
reference/hash, one closed validation code, safely resolved series and
Governance references or explicit nulls, and no currentness fields. Exactly one
logical validation-result occurrence/reference/hash exists per key; replay
returns it without resolving changed state. Codes 400 through 700 are retained
operation-bound terminal `tradeoff-selection-result.v1` records. A supported
structurally valid delivery attempt has exactly one terminal result of one of
those two schema kinds, never both. The lowest applicable numeric priority is
primary. Exactly one of
`TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT` or `TRADEOFF_SELECTION_ACCEPTED`
applies on a successful delivery. A conflict is not approval and returns no
recommendation. Every retained `tradeoff-selection-result.v1` identifies the
exact delivery-attempt reference/hash and its one operation-bound terminal
claim. Exact network replay of the same delivery attempt returns that same
result; it never creates an idempotent successor result.

The currentness-operation terminal claim, final authoritative-head comparison,
currentness check, selection result, and any Action Recommendation publication
form one logical compare-and-publish operation. Its per-evaluation selection claim
is either absent or exactly one immutable `tradeoff-selection-claim.v1`
occurrence/reference/hash keyed by the evaluation series and occurrence. The
claim contains the accepted selection occurrence/hash, candidate reference,
creation-currentness operation/check references/hashes, resulting Action
Recommendation key/occurrence/hash, and canonical `published_at =
creation_currentness_checked_at`. Its evaluation, original
`TRADEOFF_REQUIRES_MANAGER_CHOICE` result, selection, candidate, and
recommendation identities must agree exactly. Its deterministic key is
`sha256(canonical-scientific-json.v1({schema_identifier_and_version,
evaluation_series_id, evaluation_occurrence_id}))`; exactly one logical claim
occurrence/reference/hash may exist per key, and replay returns it. If the head changes after
validation but before publication, the operation yields
`TRADEOFF_SELECTION_STALE` and publishes no recommendation. Two racing distinct
selections cannot both claim; one may publish and the other must return
`TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED`. A later delivery attempt for
the exact winning selection must return
`TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT` with the existing recommendation;
exact replay of the original delivery attempt instead returns its original
`TRADEOFF_SELECTION_ACCEPTED` terminal result. Issue #12 owns the physical
transaction, locking, deduplication, and retry mechanism; it may not weaken
this logical atomicity or cardinality.

Trade-off selection is not approval. The later Governance & Audit contract
owns actor identity, selection-event persistence, and the separate Manager
Decision to approve, edit, reject, or investigate further.

## Logical result records

### Permission-attempt and Decision Support Evaluation results

Every terminal result contains:

- permission-attempt occurrence ID, nullable evaluation occurrence ID, outcome
  code, and a branch-nullable applicable deterministic digest;
- safely parsed schema, permission-policy, and deterministic
  explanation-template identifiers/versions needed to interpret that branch,
  each nullable only when that field could not be safely established; and
- no generated free text.

The applicable digest is required whenever the supported branch's canonical
digest projection can be assembled. It is null only for a pre-digest `FAILED`
result whose `DECISION_SUPPORT_INPUT_SCHEMA_INVALID` or
`DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED` condition prevents that
projection: a required digest field is absent/malformed, an unknown closed code
prevents structural interpretation, or the supplied schema/policy identifier
or version cannot be interpreted by the supported projection. Safely parsed
supplied identifiers/versions remain visible even when another required field
is null. Runtime never hashes raw bytes, exception text, or a partially guessed
projection to fill these nulls.

The evaluation occurrence ID is required for every permission-true outcome and
null for an initial `FAILED` or `NOT_PERMITTED` result. A
`PERMISSION_INVALIDATION` is a later `NOT_PERMITTED` permission-attempt result,
not a Decision Support Evaluation, and therefore also has a null evaluation
occurrence ID. An `EVIDENCE_INTEGRITY_INVALIDATION` is a later `FAILED` result,
not a Decision Support Evaluation, and likewise has a null evaluation
occurrence ID. An `ADVICE_CURRENTNESS_INVALIDATION` is also a later `FAILED`
result rather than a Decision Support Evaluation and has a null evaluation
occurrence ID.

Every permission-true Decision Support Evaluation occurrence and its terminal
result contain the same canonical `evaluation_published_at`. The first
successful atomic evaluation/result/head publication fixes that value before
their content hashes are computed; an immediate Action Recommendation carries
the same value. All three content hashes cover it, and exact replay returns it
unchanged. Failed, not-permitted, and invalidation results do not manufacture an
evaluation publication time.

A `FAILED` result contains only safely established identifiers, the primary
failure, every ordered secondary failure, and sanitized registered
explanations. It never echoes an untrusted value merely because parsing
started.

When the `FAILED` result is an `EVIDENCE_INTEGRITY_INVALIDATION`, it additionally
contains the existing evaluation-series ID, predecessor head occurrence
ID/digest/result hash, invalidated artifact reference/hash, authoritative
invalidation reference/hash, and registered invalidation reason. Its applicable
digest is:

```text
decision_support_integrity_invalidation_digest =
    sha256(canonical-scientific-json.v1({
      evaluation_series_id,
      predecessor_head_occurrence_id,
      predecessor_head_digest,
      predecessor_result_hash,
      invalidated_artifact_ref_and_hash,
      authoritative_invalidation_ref_and_hash,
      registered_invalidation_reason
    }))
```

It contains no recalculated option projection and cannot mutate the predecessor.

When the `FAILED` result is an `ADVICE_CURRENTNESS_INVALIDATION`, its primary
failure is `DECISION_SUPPORT_ADVICE_NOT_CURRENT`. It contains the exact
evaluation-series ID, predecessor head occurrence ID/digest/result hash,
evaluation, recommendation, and accepted selection-claim references/hashes as
applicable,
`currentness_checked_at`, bound operation kind and currentness-operation
reference/hash, prior `advice_valid_through`, ordered closed currentness
reasons, every offending governed dependency or operational horizon, and the
currentness-evidence digest. The invalidation digest is:

```text
decision_support_currentness_invalidation_digest =
    sha256(canonical-scientific-json.v1({
      evaluation_series_id,
      predecessor_head_occurrence_id,
      predecessor_head_digest,
      predecessor_result_hash,
      evaluation_ref_and_hash,
      recommendation_ref_and_hash_or_null,
      accepted_selection_claim_ref_and_hash_or_null,
      operation_kind,
      currentness_operation_ref_and_hash,
      currentness_checked_at,
      prior_advice_valid_through,
      ordered_currentness_reasons,
      ordered_offending_dependencies_and_horizons,
      currentness_evidence_digest
    }))
```

It contains no recalculated option projection and cannot mutate or reactivate
the predecessor.

A `NOT_PERMITTED` result contains:

- `decision_support_permission_digest`;
- the exact supplied Subject and/or Population Verdict references and hashes;
- their recorded role, requested claim scope, and permission fields;
- exact subject identity and causal `decision_at` only when a valid Subject
  Verdict supplied them;
- exact upstream and mapped trigger modes; and
- the registered permission or role-limitation next step.

When it is a `PERMISSION_INVALIDATION`, it additionally contains the existing
evaluation-series ID, predecessor head occurrence ID/digest/result hash, the
superseding Subject and Population Verdict references/hashes, and the exact
registered evidence-downgrade reason. An initial refusal contains no series or
predecessor fields.

It contains no `constraints_as_of`, Case Constraint Snapshot, effect-bearing
Decision Support projection, library/rule/link versions, costs, assumptions,
or option evaluations.

A `NO_ELIGIBLE_OPTION` result whose primary reason is
`SUBJECT_DRIVER_NOT_ACTIVE` contains:

- evaluation-series ID and nullable predecessor evaluation occurrence ID;
- `decision_support_driver_state_digest`;
- exact Investigation Request, Subject Verdict, Population Verdict, and
  Subject Profile references and hashes;
- exact discriminated subject identity, causal `decision_at`, upstream trigger
  mode literal, mapped Decision Support trigger mode, Subject Driver State
  kind/value, and derivation evidence references;
- the supported Intervention Library identifier/version;
- the exact `advice_currentness_dependency_set` and
  `advice_valid_through = NO_EXPIRY`;
- every closed Core option code in library display order, each with
  `evaluation_state = NOT_EVALUATED`, reason
  `SUBJECT_DRIVER_NOT_ACTIVE`, and all four evidence-tag slots set to
  `NOT_EVALUATED`; and
- the exact inactive-driver explanation-template identifier.

It contains no `constraints_as_of`, Case Constraint Snapshot, Driver-Action
Link or rule resolution, cost or benefit input, projection, advisory result,
dominance matrix, candidate, runner-up, monitoring fallback, or Action
Recommendation.

An active-driver `NO_ELIGIBLE_OPTION`,
`TRADEOFF_REQUIRES_MANAGER_CHOICE`, and `RECOMMENDATION_AVAILABLE`
additionally contain:

- evaluation-series ID and nullable predecessor evaluation occurrence ID;
- `decision_support_input_digest`;
- exact upstream Investigation Request reference and content hash;
- exact verified Analysis Run bundle binding, including manifest hash,
  scientific request digest, and canonical `engine_request` descriptor hash;
- all schema, policy, library, link, Monitoring Escalation Trigger, rule,
  benefit, comparison, suppression, and language versions;
- exact discriminated subject identity, causal `decision_at`, operational
  `constraints_as_of`, upstream trigger mode literal, mapped Decision Support
  trigger mode, Subject Driver State, Subject Verdict, Population Verdict,
  role, and claim-scope references;
- exact effect and interval values permitted for Decision Support;
- Case Constraint Snapshot ID and content hash;
- ordered `advice_currentness_dependency_set`, every consumed operational
  validity horizon, and derived `advice_valid_through`;
- complete option evaluations in library display order;
- for every option: tags, constraint and advisory results, assumptions, costs,
  calculations, value status, suppression reasons, and evidence references;
- complete dominance/incomparability matrix when comparison ran; and
- candidate, pivot, closed selection basis, required nullable runner-up,
  required nullable presented alternative, or monitoring-fallback facts as
  applicable.

The terminal result also contains `action_recommendation_ref_and_hash` with
closed cardinality: exactly one non-null reference/hash for an immediate
`RECOMMENDATION_AVAILABLE` result, and explicit null for
`NO_ELIGIBLE_OPTION` or `TRADEOFF_REQUIRES_MANAGER_CHOICE`. An immediate
evaluation occurrence, its terminal result, its one Action Recommendation,
and the new authoritative `EVALUATION` series head publish as one logical
operation. Zero or multiple recommendation records make the operation invalid;
an evaluation head cannot become visible without its exact result-bound
recommendation. Issue #12 owns the physical transaction and retry mechanism
but may not weaken this cardinality.

### Action Recommendation record

Every Action Recommendation has one deterministic logical occurrence key:

```text
action_recommendation_key =
    sha256(canonical-scientific-json.v1({
      evaluation_series_id,
      evaluation_occurrence_id,
      decision_support_input_digest,
      selected_option_code_and_version,
      selection_basis,
      governance_tradeoff_selection_ref_and_hash_or_null
    }))
```

The Governance selection field is null for an immediate recommendation and
required for a manager-selected trade-off candidate. Re-evaluating identical
inputs uses a new evaluation occurrence and therefore a new key. Retrying the
same logical publication cannot create a second recommendation key. Exactly
one logical Action Recommendation occurrence, reference, and content hash
exists per `action_recommendation_key`; exact replay returns that occurrence.
A second occurrence or reference, even with identical semantic content, is a
cardinality violation, while different content under the same key is an
integrity failure.

Every Action Recommendation contains:

- stable recommendation occurrence ID and schema version;
- the exact deterministic `action_recommendation_key`;
- owning evaluation-series ID, evaluation occurrence ID, and input digest;
- exact upstream Investigation Request reference and content hash;
- exact verified Analysis Run bundle binding and content hashes;
- exact discriminated subject identity, causal `decision_at`, operational
  `constraints_as_of`, upstream trigger mode literal, mapped Decision Support
  trigger mode, true Subject Driver State, verdict, and role/claim-scope
  references;
- selected option and exact option version;
- ordered component references for a composite;
- exact Driver-Action Link and Intervention Library versions;
- exact Monitoring Escalation Trigger version and hash when the selected option
  is `ACCEPT_AND_MONITOR`, otherwise `NOT_APPLICABLE`;
- canonical `monitoring_activated_at` when the selected option is
  `ACCEPT_AND_MONITOR`, otherwise `NOT_APPLICABLE`; for an immediate
  recommendation it equals the atomic evaluation
  `evaluation_published_at`, and for a
  manager-selected recommendation it equals the accepted selection claim's
  `published_at`, itself equal to the creating delivery attempt's
  `currentness_checked_at`;
- exact ordered `advice_currentness_dependency_set`, every consumed operational
  validity horizon, and derived `advice_valid_through`;
- every Constraint Result, including passing and advisory results;
- all evidence tags and `INTERVENTION_EFFECT_NOT_ESTIMATED`;
- exact default and selected assumptions with edit indicators;
- exact cost components, formula versions, unrounded lower/central/upper
  calculations, units, duration bases, currencies, and schedule-protection
  basis;
- complete comparison dimensions;
- dominance proof, monitoring-fallback reason, or trade-off-selection
  reference;
- creation-currentness operation and successful check references/hashes for a
  manager-selected trade-off candidate, or explicit
  `NOT_APPLICABLE_ATOMIC_EVALUATION_PUBLICATION` for an immediate recommendation
  published with its evaluation head;
- exact closed `selection_basis`, required nullable `runner_up`, and required
  nullable `presented_alternative` according to the selection-basis table;
- exact deterministic explanation-template identifiers; and
- immutable evidence/content hashes needed to prove provenance.

It contains no approval, authorization, execution status, outbound-send
status, generated prose, or claim that the action effect was estimated.

## Deterministic language policy

### Required inactive-driver wording

For `REACTIVE_CANONICAL`:

> The verified subject was not in High-Load Exposure at the causal decision
> cutoff. No driver-linked option was evaluated. This does not state what
> caused any observed or future delay.

For `PROACTIVE_PREVIEW`:

> The verified proposal's provisional preview did not meet the High-Load
> Exposure threshold at the causal decision cutoff. No driver-linked option was
> evaluated. This preview is not a canonical exposure fact and does not state
> what caused any delay.

### Required exposure-translation wording

An eligible exposure-reduction or milestone-acceleration option renders the
upstream supported-effect sentence under the validity language policy, then:

> This option's own effect was not estimated. If it recovers
> {recoverable_fraction_percent} of the estimated exposure effect, the declared
> assumption produces {supplier_lower} to {supplier_upper}
> supplier-milestone days, with central projection {supplier_central}. Under
> the separate critical-path translation assumption, this corresponds to
> {project_lower} to {project_upper} project-delay days protected, with central
> projection {project_central}. This is an assumption-based projection range,
> not an intervention-effect confidence interval.

### Required consequence wording

> This option's own effect was not estimated. Its projected value uses the
> declared {consequence_basis_label} assumption of {lower} to {upper}, with
> central value {central}; it does not use or claim recovered Supplier
> Milestone Slippage.

### Required monitoring wording

> No intervention benefit is claimed. Monitor under the named owner, review
> time, and approved atomic escalation trigger recorded for this case. A
> trigger match requests manager review; it does not authorize or execute an
> action.

### Required suppression wording

> Not eligible because {primary_suppression_label}.

Secondary reasons remain available in registered order.

The deterministic renderer may interpolate only exact result fields and
registered labels. Prohibited language includes:

- "will save", "will recover", or a probability of action success;
- "estimated intervention effect" or "intervention confidence interval";
- "optimized policy", "next-best action", or model-generated ranking;
- "the cause of this order's delay";
- any claim that a false Subject Driver State proves congestion had no causal
  role;
- any omission of `INTERVENTION_EFFECT_NOT_ESTIMATED`; and
- any implication that selection or recommendation is authorization.

Artifact Composition may change connective presentation only under its own
contract. It cannot change calculations, tags, action identity, eligibility,
or causal strength.

## Conformance scenarios

Implementations must pass at least the following cases.

1. An in-domain supported Population Verdict without its required Subject
   Verdict produces `FAILED` and no option evaluation.
2. A valid Tentative Subject Verdict with permission false produces
   `NOT_PERMITTED`; monitoring is not evaluated.
3. A valid Association Only Subject Verdict produces `NOT_PERMITTED` and no
   driver-linked recommendation.
4. A valid Insufficient Subject Verdict produces `NOT_PERMITTED` and exposes
   only its registered evidence next step. The sole upstream unusable-proactive-
   `decision_at` case with a null Population Verdict reference preserves that
   explicit null in the permission digest and produces the same refusal.
5. A verified supported out-of-domain Population Verdict with subject
   application and Decision Support role permissions false produces
   `NOT_PERMITTED` without fabricating a Subject Verdict.
6. A supported semi-synthetic Subject Verdict with all permission fields true,
   an exact matching discriminated subject identity, and a verified true
   Subject Driver State may enter the Intervention Library; a proactive
   proposal identity creates no Order Line.
7. A supported verdict whose effect display is not `CAUSAL_ESTIMATE` fails
   with `DECISION_SUPPORT_VERDICT_PERMISSION_INCONSISTENT`.
8. A missing required identifier/version field produces `FAILED` with
   `DECISION_SUPPORT_INPUT_SCHEMA_INVALID`; a present, well-formed unsupported
   policy/library identifier or version produces
   `DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED`. Neither falls back. If either
   failure prevents the supported digest projection from being assembled, the
   applicable digest is null and only safely parsed version fields are retained.
9. A reactive case suppresses `RELEASE_TIMING_ADJUSTMENT` with
   `TRIGGER_MODE_INCOMPATIBLE`.
10. A provisional Driver-Action Link is disclosed as speculative and receives
    `DRIVER_ACTION_LINK_PROVISIONAL` with no constraint or benefit calculation.
11. A rejected Driver-Action Link cannot become eligible even when every case
    constraint would otherwise pass; it records
    `DRIVER_ACTION_LINK_REJECTED`.
12. A required constraint proved false emits `UNSATISFIED` and suppresses the
    option with `REQUIRED_CONSTRAINT_UNSATISFIED`.
13. A missing required fact emits `UNKNOWN` and
    `REQUIRED_CONSTRAINT_UNKNOWN`; absence does not pass.
14. A constraint fact known after causal `decision_at` but no later than
    `constraints_as_of` is eligible without retiming the causal evidence; a
    fact first known after `constraints_as_of` emits `UNKNOWN`.
15. A manager attestation recorded after `constraints_as_of` may be used only
    when it explicitly and validly attests
    `known_at <= constraints_as_of`; all three timestamps remain visible.
16. Two conflicting eligible facts emit `UNKNOWN`; the favorable fact is not
    chosen.
17. An advisory `UNKNOWN` does not suppress the option but prevents dominance
    on that dimension.
18. With compatible duration bases,
    `time_to_initiate_days == available_float_days` satisfies a within-float
    constraint.
19. A release-timing option with an exact eligible Release-Timing Preview whose
    `provisional_high_load_preview = true` is suppressed.
20. Capacity-backed acceleration without an `OVERTIME_CAPACITY` or `SLOT_SWAP`
    fact is suppressed; no generic expedite option appears.
21. A recoverable fraction or critical-path translation fraction below `0` or
    above `1` records `RECOVERABLE_FRACTION_INVALID` or
    `CRITICAL_PATH_TRANSLATION_FRACTION_INVALID`, respectively; a missing
    required critical-path fraction records
    `CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE` and suppresses monetary
    evaluation.
22. A recoverable fraction of `0` is valid input but makes an exposure-
    translation option's central gross value zero and central net value
    non-positive; that option is suppressed with
    `NON_POSITIVE_CENTRAL_NET_VALUE`.
23. A recoverable fraction of `1` is valid and visibly labelled a full-recovery
    assumption, not an estimated action effect.
24. With exposure interval `[6,14]`, estimate `10`, recoverable fraction
    `0.4`, critical-path translation fraction `1`, critical-path delay cost
    `INR 100000/day` on the matching resolved canonical duration basis, and
    action cost `INR 150000`, recovered supplier days
    and protected project days are both `[2.4,4,5.6]`, and net values are
    `[INR 90000, INR 250000, INR 410000]`; value status is
    `ROBUSTLY_POSITIVE`.
25. With case 24 inputs except critical-path translation fraction `0.5`,
    protected project days are `[1.2,2,2.8]` and net values are
    `[INR -30000, INR 50000, INR 130000]`; value status is `VALUE_SENSITIVE`.
26. With case 24 inputs and action cost `INR 400000`, central net value is
    exactly zero and the option is suppressed.
27. The range in cases 24-26 is never labelled an intervention-effect
    confidence interval.
28. A `PROJECT_DELAY_DAYS` assumption `[1,3,5]` with the matching resolved
    canonical duration basis, `INR 100000/day`, and `INR 150000` cost yields net values
    `[INR -50000, INR 150000, INR 350000]`, tagged
    `OPERATIONAL_ASSUMPTION_ONLY`.
29. A `DIRECT_MONETARY_VALUE` range `[INR 200000, INR 300000,
    INR 450000]` with `INR 100000` cost yields net values
    `[INR 100000, INR 200000, INR 350000]` and schedule basis
    `NOT_APPLICABLE`.
30. A well-formed INR critical-path delay rate with a well-formed BRL action
    cost produces global `FAILED` with
    `DECISION_SUPPORT_CURRENCY_MISMATCH`; runtime does not convert currency.
31. Cost of critical-path delay with a business-day basis suppresses every
    schedule-valued option with `CRITICAL_PATH_DELAY_RATE_INVALID`; a
    direct-monetary option and monitoring do not consume that rate.
32. Exact calculations are compared before presentation rounding.
33. A composite with one unknown component constraint is suppressed and
    retains the component-scoped reason.
34. A composite uses one approved benefit link; it never adds protected-slot
    and phased-delivery benefits.
35. A composite lacking an explicit cost total is suppressed; one whose
    time-composition declaration is `UNAVAILABLE_PENDING_REVIEW` retains
    advisory time as `UNKNOWN` with `TIME_COMPOSITION_RULE_UNAVAILABLE`; the
    former records `ACTION_COST_UNAVAILABLE`, and neither guesses a derivation.
36. An eligible `ROBUSTLY_POSITIVE` option that is no worse on all comparable
    dimensions and strictly better on at least one may dominate.
37. An otherwise dominant `VALUE_SENSITIVE` option does not become the sole
    recommendation.
38. If exposure option A recovers `10` supplier-milestone days with
    critical-path translation fraction `0.1`, while exposure option B recovers
    `5` supplier-milestone days with fraction `1`, their central schedule
    protection values are respectively `1` and `5` `PROJECT_DELAY_DAYS` on the
    same resolved canonical duration basis.
    With every other comparison dimension equal, B is strictly better on
    schedule protection; A's larger supplier-day recovery cannot reverse the
    comparison.
39. An option with a direct-monetary consequence basis cannot dominate another
    option through a fabricated schedule-days value.
40. When robustly positive active options exist, monitoring stays visible but
    outside active dominance and runner-up selection.
41. When only value-sensitive active options exist and monitoring is eligible,
    the result is a `VALUE_UNCERTAINTY` trade-off.
42. When no active option has positive central value and monitoring passes,
    monitoring becomes the Action Recommendation.
43. When active options are only value-sensitive and monitoring has an unknown
    required fact, `NO_ELIGIBLE_OPTION` records
    `VALUE_SENSITIVE_BASELINE_UNAVAILABLE` and exposes the monitoring
    suppression list.
44. A universally dominant robust option yields one Action Recommendation and
    the highest-central-net remaining active option as runner-up.
45. When exactly one active recommendation-eligible option exists and it is
    `ROBUSTLY_POSITIVE`, selection basis is `SOLE_ELIGIBLE_OPTION` and
    `runner_up = null`. The basis is not used merely because only one robustly
    positive option exists among multiple recommendation-eligible options.
46. A frontier trade-off emits exactly two headline candidates and no Action
    Recommendation. Except for the explicit robust safety alternative in case
    129, a candidate described as a frontier option is on the active Pareto
    frontier.
47. Candidate B is selected on the first frozen dimension where a frontier
    option is comparably better than Candidate A. If that dimension is central
    schedule protection, the serialized pivot is exactly
    `SCHEDULE_PROTECTION`, not its display label; the other five normal
    dimensions use their exact closed pivot codes.
48. If incomparability alone prevents a normal pivot, Candidate B is the
    next-highest-central-net frontier option and the pivot is
    `INCOMPARABLE_EVIDENCE_GAP`; a central-net tie uses library order and
    records `TIED_UNDER_POLICY` as an ordering annotation only.
49. Every unknown or incompatible dimension causing the evidence-gap fallback
    is listed.
50. A true trade-off tie requires equal central net values and every
    pair-applicable Pareto dimension to be known, basis-compatible, comparable,
    and exactly equal. It uses library display order, records pivot
    `TIED_UNDER_POLICY`, and does not claim superiority.
51. A valid trade-off selection of Candidate B whose complete candidate
    reference, occurrence, digest, and result hash exactly match the
    authoritative evaluation-series head emits an Action Recommendation with
    `TRADEOFF_SELECTION_ACCEPTED` through one logical compare-and-publish
    operation and does not record approval.
52. A selection naming a third option is invalid and emits no recommendation.
53. An assumption or snapshot edit publishes a successor series head; a
    selection bound to the predecessor is stale.
54. Repeating identical inputs creates a new occurrence ID with the same input
    digest, candidate option identities/order, and deterministic value
    projection; the occurrence-scoped candidate references change with the new
    occurrence. It advances the series head and makes a predecessor-bound
    selection stale.
55. Editing critical-path delay cost changes only Decision Support; the
    referenced Analysis Run and Evidence Verdict remain unchanged.
56. Moving `constraints_as_of` creates a new Decision Support Evaluation;
    editing an upstream subject or causal `decision_at` instead requires a new
    upstream run and verdict.
57. Every Action Recommendation includes passing constraints, not only failed
    or salient ones.
58. Every visible candidate and recommendation includes
    `INTERVENTION_EFFECT_NOT_ESTIMATED`.
59. A dominated option remains visible as eligible; it is not relabelled
    suppressed.
60. Discovery order and asynchronous execution do not change primary
    suppression, candidate order, pivot, or runner-up.
61. An approved `MONITORING_BASELINE` link for `ACCEPT_AND_MONITOR` maps to
    `MECHANISTIC_LINK = REVIEWED_BASELINE` and
    `ASSUMPTION_BASED_BENEFIT = NO_BENEFIT_CLAIM`; it creates no mechanism,
    projected-days, monetary-benefit, or action-effect claim.
62. An `ACTION_MECHANISM` link for `ACCEPT_AND_MONITOR`, or a
    `MONITORING_BASELINE` link for any other Core option, produces global
    `FAILED` with `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH` before option
    evaluation.
63. `UNAVAILABLE_PENDING_REVIEW` or a referenced non-approved Advisory Rubric
    yields `UNKNOWN` with `RUBRIC_UNAVAILABLE` or `RUBRIC_NOT_APPROVED`; it does
    not suppress an otherwise eligible option and cannot support dominance.
64. An approved applicable Advisory Rubric with complete typed inputs and
    exactly one matched rule emits that rule's closed ordinal and preserves the
    rubric, input, evidence, and rule references.
65. Missing, invalid, conflicting, or post-cutoff rubric input evidence yields
    `UNKNOWN` with `RUBRIC_INPUT_MISSING`, `RUBRIC_INPUT_INVALID`, or
    `RUBRIC_INPUT_CONFLICT`, as applicable; a free-text assessment or bare
    ordinal cannot replace it.
66. An applicability mismatch, no matched rule, or multiple matched rules
    yields `UNKNOWN` with `RUBRIC_NOT_APPLICABLE`, `RUBRIC_RULE_NO_MATCH`, or
    `RUBRIC_RULE_AMBIGUOUS`, respectively.
67. A permitted reactive subject whose exact canonical
    `high_load_exposure = false` produces `NO_ELIGIBLE_OPTION` with
    `SUBJECT_DRIVER_NOT_ACTIVE`; every Core option is `NOT_EVALUATED`, and no
    operational input is consumed.
68. A permitted proactive proposal whose exact
    `provisional_high_load_preview = false` produces the same terminal reason,
    retains its preview-only label, and creates no canonical High-Load
    Exposure or Order Line fact.
69. A missing Subject Driver State is
    `DECISION_SUPPORT_INPUT_SCHEMA_INVALID`; a manager-attested, recomputed,
    wrong-kind, wrong-value, wrong-cutoff, wrong-Dataset-Version, or
    hash-mismatched state is `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`.
70. A verified true Subject Driver State proceeds to the complete active-driver
    envelope; the state and upstream Subject Profile reference are included in
    the input digest and every resulting recommendation.
71. An exact Release-Timing Preview bound to the evaluated proactive proposal,
    supplier, target milestone kind, Dataset Version, verified sealed Analysis
    Run bundle/scientific request, and that bundle's primary selector and
    threshold-rule references, with `alternate_decision_at` equal to the
    candidate release time, strictly after causal `decision_at`, not before
    `constraints_as_of`, and `provisional_high_load_preview = false`, satisfies
    `RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD` without changing the original
    Subject Driver State, Subject Verdict, or causal cutoff.
72. A Release-Timing Preview from another proposal, revision, supplier, target
    milestone kind, Dataset Version, Analysis Run bundle/scientific request,
    primary selector, or threshold rule, or one whose candidate
    release/milestone disagrees with the snapshot, produces
    `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; it cannot be borrowed to
    satisfy the rule.
73. A well-formed preview whose `alternate_decision_at` differs from the
    candidate release time, is not strictly after the original causal
    `decision_at`, or precedes `constraints_as_of` produces
    `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`.
74. A missing Release-Timing Preview, or one whose required calculation input
    was first known after `constraints_as_of`, makes
    `RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD` `UNKNOWN` and suppresses only
    `RELEASE_TIMING_ADJUSTMENT`; another option cannot consume that preview.
75. A missing critical-path delay rate suppresses every otherwise evaluable
    exposure-translation or `PROJECT_DELAY_DAYS` consequence option with
    `CRITICAL_PATH_DELAY_RATE_UNAVAILABLE`; an otherwise evaluable
    `DIRECT_MONETARY_VALUE` option and `ACCEPT_AND_MONITOR` continue.
76. `TIME_TO_INITIATE_DAYS = 3` and `AVAILABLE_FLOAT_DAYS = 3` on the exact
    same hash-bound Business Calendar satisfy an applicable within-float rule.
77. Initiation and float values using different duration kinds or different
    Business Calendar identities, versions, or hashes produce `UNKNOWN`; the
    affected option is suppressed without converting either value.
78. Exposure-derived recovered supplier days and protected project days
    inherit the exact hash-bound `canonical_slippage_duration_basis` from the
    sealed `causal-engine-suite-request.v2`; dimensionless fraction
    multiplication cannot change it.
79. A `PROJECT_DELAY_DAYS` Consequence Benefit Assumption with a different or
    missing duration basis is suppressed with
    `CONSEQUENCE_BENEFIT_ASSUMPTION_INVALID`; a rate whose resolved basis
    differs is suppressed with `CRITICAL_PATH_DELAY_RATE_INVALID`. Neither is
    converted, while direct-monetary and monitoring options remain unaffected.
80. If Candidate A and another frontier option have fully known, compatible,
    comparable, and equal pair-applicable Pareto dimensions but different
    central net values, and no normal strict pivot exists, Candidate B is the
    highest-central-net equal-profile option and the pivot is
    `EQUAL_COMPARISON_PROFILE`. The result makes no superiority claim.
81. An `UNKNOWN`, incompatible, or one-sided-applicable dimension cannot prove
    an equal comparison profile or a true tie; when it alone blocks a normal
    pivot, the result uses `INCOMPARABLE_EVIDENCE_GAP` instead and records
    `ONE_SIDED_NOT_APPLICABLE` for the one-sided case.
82. A comparably strict normal pivot takes precedence over
    `EQUAL_COMPARISON_PROFILE`, even when a different frontier option shares
    Candidate A's comparison profile.
83. Exactly one fully specified `APPROVED` Monitoring Escalation Trigger whose
    exact version is published by `constraints_as_of`, applicable to the exact
    `ACCEPT_AND_MONITOR` option version and trigger mode, and uniquely
    unsuperseded makes `MONITORING_ESCALATION_TRIGGER_REGISTERED` satisfied.
84. An absent trigger fact records `MONITORING_TRIGGER_REFERENCE_MISSING`;
    multiple facts record `MONITORING_TRIGGER_REFERENCE_MULTIPLE`; a
    post-cutoff trigger records `MONITORING_TRIGGER_NOT_AVAILABLE_AT_CUTOFF`;
    and a non-approved, retired, inapplicable, under-specified, superseded, or
    ambiguous trigger records `MONITORING_TRIGGER_NOT_APPROVED`,
    `MONITORING_TRIGGER_RETIRED`, `MONITORING_TRIGGER_NOT_APPLICABLE`,
    `MONITORING_TRIGGER_UNDER_SPECIFIED`, `MONITORING_TRIGGER_SUPERSEDED`, or
    `MONITORING_TRIGGER_EFFECTIVE_VERSION_AMBIGUOUS`, respectively. Each
    produces `UNKNOWN`, suppresses monitoring through
    `REQUIRED_CONSTRAINT_UNKNOWN`, and invents no replacement threshold.
85. A malformed, dangling, hash-mismatched, wrong-registry, wrong-option, or
    wrong-version trigger reference produces the applicable global schema or
    reference-integrity failure rather than an option-scoped unknown.
86. Trigger literals must match the registered observation type and unit
    exactly; runtime performs no coercion or unit conversion.
87. A compound predicate, second observation, second operator, or response
    other than `REQUEST_MANAGER_REVIEW` is invalid under trigger schema version
    `1`; runtime does not approximate it as one atomic predicate.
88. A later observation that matches an eligible trigger may request manager
    review only; it does not select an option, authorize or execute work,
    mutate the source evaluation, or silently publish a successor.
89. `decimal:99999999999999999999.999999999999999999` is inside the closed
    numeric domain. A required case-wide value with 21 integer digits, 19
    fractional digits, more than 38 coefficient digits, or absolute value at
    least `10^20` produces `DECISION_SUPPORT_ARITHMETIC_INVALID`; the same
    defect in an option-conditional value uses its registered option-scoped
    invalid/unknown result. Neither is truncated or rounded. Derived exact
    rationals use the separate 4,096-bit bound rather than the input scale.
90. Exact rational arithmetic and comparisons produce identical results under
    different ambient Decimal precisions, rounding modes, locales, and process
    configurations; presentation rounding never feeds back into a digest or
    decision.
91. Any integer materialized during parsing, rational normalization,
    arithmetic, or comparison whose bit length exceeds `4096` produces global
    `DECISION_SUPPORT_ARITHMETIC_INVALID` and no partial option result.
92. Upstream `trigger_mode = reactive` maps only to `REACTIVE`, and
    `trigger_mode = proactive` maps only to `PROACTIVE`; both forms are
    preserved in the digest. Case variants or a mismatched pair produce
    `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`.
93. A required case-wide verified evidence/read-model record with
    `available_at > constraints_as_of` produces
    `DECISION_SUPPORT_EVIDENCE_UNAVAILABLE_AT_CUTOFF`. A later Manager
    Attestation cannot backdate that record's availability.
94. The supported Core Intervention Library maps every option code to the exact
    version and `ACTIVE` status shown in the closed table. A duplicate or
    missing mapping is a reference-integrity failure; runtime does not search
    for a replacement option version.
95. A future library-bound `RETIRED` option is recorded with
    `OPTION_RETIRED`, all evidence tags `NOT_EVALUATED`, and no link,
    constraint, or projection evaluation. Retirement does not mutate an
    earlier evaluation.
96. A supplied superseded Intervention Library or Driver-Action Link registry
    version is unsupported. Multiple effective registry heads or a malformed
    predecessor chain produce `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`.
97. A supplied Driver-Action Link version with a successor published by
    `constraints_as_of` is suppressed as `DRIVER_ACTION_LINK_SUPERSEDED`; a
    unique effective head is then evaluated according to its exact review
    status.
98. When no active option has positive central net value and monitoring is
    eligible, its Action Recommendation has
    `selection_basis = MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION` and
    `runner_up = null`.
99. An initial permission refusal has a permission-attempt occurrence ID but no
    Decision Support Evaluation occurrence ID or evaluation-series ID.
100. A later authoritative evidence downgrade for the same series identity
     publishes a `PERMISSION_INVALIDATION` head. The prior evaluation and
     recommendation remain immutable history but are no longer current or
     selectable.
101. A later return to supported evidence creates a new permission-true
     evaluation occurrence; it does not reactivate the invalidated predecessor.
102. A malformed selection envelope returns
     `TRADEOFF_SELECTION_SCHEMA_INVALID`; an unsupported selection schema
     returns `TRADEOFF_SELECTION_SCHEMA_UNSUPPORTED`; an unknown series returns
     `TRADEOFF_SELECTION_SERIES_NOT_FOUND`; a bad Governance reference/hash
     returns `TRADEOFF_SELECTION_GOVERNANCE_REFERENCE_INTEGRITY_MISMATCH`; a
     non-trade-off current target returns
     `TRADEOFF_SELECTION_TARGET_NOT_TRADEOFF`; and an invalid candidate returns
     `TRADEOFF_SELECTION_INVALID_CANDIDATE`. Each produces no Action
     Recommendation.
103. If the authoritative head changes after selection validation but before
     Action Recommendation publication, the logical compare-and-publish
     returns `TRADEOFF_SELECTION_STALE` and publishes no recommendation.
104. A selection against a `PERMISSION_INVALIDATION` head is stale even when
     its predecessor occurrence and digest otherwise match the selection.
105. A missing effective Driver-Action Link records
     `DRIVER_ACTION_LINK_MISSING` and stops the option before constraint or
     benefit evaluation.
106. A missing required recoverable fraction records
     `RECOVERABLE_FRACTION_UNAVAILABLE`; a missing required Consequence Benefit
     Assumption records `CONSEQUENCE_BENEFIT_ASSUMPTION_UNAVAILABLE`. Each
     suppresses only the affected option.
107. A malformed or negative direct action cost records
     `ACTION_COST_INVALID`; runtime does not coerce it to zero or reuse another
     option's cost. A breakdown with 101 components records the same reason and
     is not summed.
108. Advisory Results are derived only from the option's exact Advisory Rubric
     and eligible typed snapshot inputs. A supplied legacy `*_RESULT_REF` is an
     unknown fact code and fails snapshot schema validation; a free-text
     assessment or bare ordinal is never reconciled or trusted as an input.
109. With one robustly positive active option, one value-sensitive active
     option, and ineligible monitoring, Decision Support compares the active
     positive options under the normal recommendation/trade-off rules.
     `VALUE_SENSITIVE_BASELINE_UNAVAILABLE` does not apply and cannot suppress
     the robustly positive option.
110. Two applicable `TIME_TO_INITIATE_DAYS` values with the exact same duration
     basis are comparable. Different duration kinds or different Business
     Calendar IDs, versions, or hashes make only that Pareto dimension
     incomparable and record
     `INCOMPATIBLE_INITIATION_DURATION_BASIS` when it causes the evidence-gap
     fallback; runtime performs no conversion.
111. Date/date cutoff comparisons use calendar-date order. A required case-wide
     temporal comparison whose retained precision or timezone semantics cannot
     establish order produces
     `DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`; the same unresolved
     ordering for an option-scoped timing fact produces its closed `UNKNOWN` or
     not-available result and suppresses only that option. Neither branch
     manufactures midnight, UTC, a timezone, or an order.
112. A Release-Timing Preview whose candidate promised target milestone is
     earlier than, or temporally incomparable with, its
     `alternate_decision_at` produces
     `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; it cannot satisfy a
     release-timing rule.
113. A supported case-wide library or registry version published after
     `constraints_as_of` produces
     `DECISION_SUPPORT_POLICY_NOT_AVAILABLE_AT_CUTOFF` with no older-head
     substitution. A supplied option-level Driver-Action Link version that is
     later than, or temporally incomparable with, the cutoff records
     `DRIVER_ACTION_LINK_NOT_AVAILABLE_AT_CUTOFF`, suppresses only that option,
     and likewise cannot borrow an older link.
114. An authoritative, hash-bound quarantine, revocation, suppression, or
     corruption record targeting an artifact referenced by the current advice
     chain
     publishes an `EVIDENCE_INTEGRITY_INVALIDATION` head and a `FAILED` result
     with `DECISION_SUPPORT_EVIDENCE_INTEGRITY_INVALIDATED`. The predecessor
     evaluation and recommendation remain immutable but are no longer current,
     actionable, or selectable. A later timestamp or retrieval failure without
     that explicit authoritative record does not invalidate the head.
115. A hash-bound Monitoring Observation is evaluated at its verified source-
     record `first_available_at = available_at` only when the source monitoring recommendation and exact
     approved trigger remain current. A false predicate emits no request; a
     true predicate emits exactly one `REQUEST_MANAGER_REVIEW` key. Replay of
     the same recommendation/trigger/observation tuple yields that same key,
     while a stale recommendation or retired, superseded, or ambiguous trigger
     emits none.
116. One case-scoped critical-path delay rate is shared by every schedule-valued
     option. Its absence suppresses each such option with
     `CRITICAL_PATH_DELAY_RATE_UNAVAILABLE`; multiple, conflicting, or
     option-scoped rate records produce
     `DECISION_SUPPORT_INPUT_SCHEMA_INVALID`. Direct-monetary and monitor-only
     options do not consume the rate.
117. The first valid delivery attempt for one immutable selection atomically
     claims the unchanged trade-off evaluation and publishes exactly one Action
     Recommendation with `TRADEOFF_SELECTION_ACCEPTED`. Exact network replay
     of that same delivery attempt returns its original terminal result. A
     later delivery attempt for the same immutable selection returns
     `TRADEOFF_SELECTION_ACCEPTED_IDEMPOTENT` and the existing recommendation;
     a delivery attempt for a distinct selection of either candidate returns
     `TRADEOFF_SELECTION_CONFLICT_ALREADY_RESOLVED`. Neither path publishes a
     duplicate or contradictory recommendation.
118. Reordering retrieval or asynchronous completion of the same logical links,
     rules, costs, benefit assumptions, or semantic reference sets produces the
     same `decision_support_input_digest` under the closed collection orders.
     A duplicate Case Constraint Snapshot logical fact key fails schema
     validation rather than being collapsed or hashed in arrival order.
119. The Core composite derives each ordinal through
     `LEAST_FAVORABLE_COMPONENT_RESULTS.v1` from both exact component rubrics,
     even when one standalone component stopped before advisory evaluation. If
     either component Advisory Result is `UNKNOWN`, the composite is `UNKNOWN`
     with `RUBRIC_COMPONENT_RESULT_UNKNOWN` and the component reasons;
     otherwise the exact least-favorable closed ordinal is retained with both
     component results.
120. The exact approved trigger-specific Driver-Action Link is the sole owner
     of a recoverable-fraction or consequence-assumption default reference. The
     Intervention Option declares only the required assumption kind; a
     link/option kind mismatch produces
     `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`, and no second default is
     reconciled or selected.
121. A Critical Path Translation Assumption has no hidden default. Exactly one
     subject/option/link/trigger-bound, hash-bound selected value reviewed by an
     immutable Manager Attestation and known by `constraints_as_of` is
     eligible. Absence records
     `CRITICAL_PATH_TRANSLATION_FRACTION_UNAVAILABLE`; multiple or conflicting
     eligible records produce `CRITICAL_PATH_TRANSLATION_FRACTION_INVALID`.
122. The Core composite's explicit `UNAVAILABLE_PENDING_REVIEW` time-
     composition declaration is valid library content and yields
     `TIME_COMPOSITION_RULE_UNAVAILABLE`. An absent or unknown declaration is
     schema-invalid. A missing eligible atomic/component fact yields
     `TIME_TO_INITIATE_INPUT_UNAVAILABLE`; an invalid one yields
     `TIME_TO_INITIATE_INPUT_INVALID`; a non-approved formula yields
     `TIME_COMPOSITION_FORMULA_NOT_APPROVED`; an approved `PARALLEL` or
     `SEQUENTIAL` declaration with an unknown component yields
     `TIME_COMPONENT_RESULT_UNKNOWN`; and incompatible component bases yield
     `TIME_COMPONENT_BASIS_INCOMPATIBLE`. No branch guesses a relation or
     converts units.
123. An exact `APPROVED` Composite Compatibility Review bound to the composite,
     ordered components, link, trigger mode, subject, predeclared snapshot ID,
     and the acyclic compatibility-input digest that excludes its own result
     reference contains each of the four exact issue-#17-owned
     `composite-compatibility-criteria.v1` attestations once in schema order
     with reviewer identity, rationale, and evidence. Decision Support consumes
     but never re-derives those judgments. The review makes
     `COMPOSITE_COMPONENTS_COMPATIBLE` satisfied only when its closed outcome
     is `COMPATIBLE`; `INCOMPATIBLE` is unsatisfied. Missing, post-cutoff,
     non-approved, retired, or superseded review results are `UNKNOWN` with
     `COMPOSITE_REVIEW_MISSING`,
     `COMPOSITE_REVIEW_NOT_AVAILABLE_AT_CUTOFF`,
     `COMPOSITE_REVIEW_NOT_APPROVED`, `COMPOSITE_REVIEW_RETIRED`, or
     `COMPOSITE_REVIEW_SUPERSEDED`, respectively, while a malformed, ambiguous,
     identity-mismatched, or compatibility-input-digest-mismatched review is a global
     schema/reference-integrity failure. The final snapshot hash includes the
     result reference without creating a hash cycle.
124. Two direct-monetary options both carrying schedule protection
     `NOT_APPLICABLE` omit that dimension from their pairwise proof and may be
     ordered or shown equal only through the remaining pair-applicable
     dimensions. One schedule-valued and one direct-monetary option instead
     records `ONE_SIDED_NOT_APPLICABLE` when the asymmetry blocks candidate
     selection; neither branch converts `NOT_APPLICABLE` to zero or equality.
125. Every governed successor is published no earlier than its predecessor,
     and every non-provisional review time and review-reference availability is
     no later than the reviewed record's publication. A provably reversed
     chronology produces `DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH`; an
     unresolved required ordering produces
     `DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED`. A future-dated or late-
     available review cannot make an earlier record approved.
126. If an authoritative integrity record invalidates the Governance selection,
     selection claim, or another post-evaluation dependency of the current
     Action Recommendation, the series advances to
     `EVIDENCE_INTEGRITY_INVALIDATION`. A new delivery attempt for the old
     selection is `TRADEOFF_SELECTION_STALE`, not idempotent success; exact
     replay of a delivery attempt that terminated before invalidation returns
     only its immutable historic result and cannot establish current advice.
     Recovery requires a fresh evaluation and, if needed, a fresh selection.
127. An immediate `RECOMMENDATION_AVAILABLE` result contains exactly one
     Action Recommendation reference/hash. The evaluation occurrence, result,
     recommendation, and authoritative head publish logically atomically under
     the deterministic recommendation key. Exactly one logical occurrence,
     reference, and hash may exist per key; zero, same-key duplicate, or
     contradictory recommendation records cannot coexist with that result.
128. A sealed `causal-engine-suite-request.v2` with one concrete request-wide
     basis, matching released-row bases, and a matching
     `causal-engine-suite-result.v2` effect basis supplies the only schedule
     basis Decision Support may consume. A missing/mismatched basis is a global
     integrity failure, while upstream `SLIPPAGE_DURATION_BASIS_MIXED` produces
     no estimate, permitted Subject Verdict, or Decision Support Evaluation.
129. At least one active robustly positive option exists, but value-sensitive
     options occupy the entire active Pareto frontier. Candidate A is the
     highest-central-net value-sensitive frontier option; Candidate B is the
     highest-central-net active robustly positive option and is explicitly
     marked `ROBUST_SAFETY_ALTERNATIVE` despite being Pareto-dominated. The
     pivot is `VALUE_UNCERTAINTY`, monitoring eligibility does not change the
     branch, no automatic Action Recommendation exists, and a valid manager
     trade-off selection may select either exact candidate.
130. Consumed operational inputs have finite validity horizons `T1` and `T2`
     with `T1 < T2`, while every other consumed input declares `NO_EXPIRY`.
     The evaluation records `advice_valid_through = T1`; a currentness check at
     exactly `T1` succeeds because the boundary is inclusive.
131. A currentness check provably after `advice_valid_through` publishes one
     `ADVICE_CURRENTNESS_INVALIDATION` with primary reason
     `OPERATIONAL_FACT_EXPIRED` and a `FAILED` result whose primary failure is
     `DECISION_SUPPORT_ADVICE_NOT_CURRENT`. The predecessor remains immutable
     but cannot be rendered as current, selected, or used for authorization,
     and any new delivery/use attempt is stale rather than idempotent success.
132. Every consumed operational input declares `NO_EXPIRY`, but a governed
     dependency fails its exact kind-specific predicate: an option is no
     longer `ACTIVE`; a supporting link, trigger, rubric, or composite review
     is no longer `APPROVED` as its schema defines that status; or a library or
     governed-version envelope has an effective successor. Currentness fails
     with `GOVERNED_DEPENDENCY_NOT_CURRENT`; runtime never applies `ACTIVE` to a
     schema that lacks it, and `NO_EXPIRY` cannot preserve the old advice.
133. A required comparison between `currentness_checked_at` and a finite
     operational or governed-lifecycle horizon cannot establish order under
     the canonical temporal partial order. The system publishes
     `ADVICE_CURRENTNESS_INVALIDATION` with
     `CURRENTNESS_COMPARISON_UNRESOLVED` and never guesses a timezone,
     precision, or ordering.
134. A unique `monitoring-observation.v1` occurrence binds its reviewed Intake
     & Lineage source-mapped subject identity exactly to the recommendation, proves
     `monitoring_activated_at <= observed_at <= available_at`, and binds
     `currentness_checked_at = trigger_match_as_of = available_at`. If a consumed operational
     fact expired before that cutoff or the governed trigger/dependency is no
     longer current at it, Decision Support publishes the applicable
     currentness invalidation and emits no `REQUEST_MANAGER_REVIEW`; processing
     or replay time cannot substitute a different cutoff.
135. A currentness operation names evaluation `E1`, but the first authoritative
     head read is a successor evaluation or any invalidation kind. The result
     is `CURRENTNESS_NOT_AUTHORITATIVE_HEAD`; the attempted render, selection,
     authorization, or monitoring use is denied, no currentness invalidation is
     published against the successor, and the procedure does not evaluate `E1`
     dependencies or horizons.
136. Evaluation `E1` is the exact head when a currentness failure is found, but
     another operation advances the head before the invalidation compare-and-
     publish. The losing operation reads the new head exactly once, records
     `CURRENTNESS_NOT_AUTHORITATIVE_HEAD`, denies the attempted use, publishes
     nothing against the successor, and terminates without retrying.
137. A successful currentness check bound to a `CURRENT_ADVICE_RENDER`
     operation can support only that exact render response, which stores the
     currentness-operation and check references/hashes. Reusing it for a
     Trade-off Selection, authorization attempt, different render
     request, or Monitoring Observation returns
     `CURRENTNESS_OPERATION_MISMATCH` without terminating the valid render
     operation; each distinct operation requires its own exact operation-bound
     check.
138. An accepted Trade-off Selection claim, its manager-selected Action
     Recommendation, an authorization-currentness result, and a
     `REQUEST_MANAGER_REVIEW` occurrence each retain the successful
     currentness-operation/check references bound to themselves. A missing,
     malformed, or intrinsically hash/key-mismatched proposed envelope returns
     `CURRENTNESS_OPERATION_INVALID`; a valid envelope presented to a wrong
     kind, payload, or consumer returns `CURRENTNESS_OPERATION_MISMATCH`.
     Neither refusal creates a terminal claim/check, permits advice use, or
     mutates a series head.
139. Two deliveries have the exact same currentness-operation tuple. Both
     derive the same `currentness_operation_key`; one atomically creates the
     sole operation occurrence/reference/hash and the other must return it.
     Duplicate operation occurrences with different IDs or hashes cannot feed
     different check or monitoring-request keys.
140. One immutable currentness operation already has a terminal success when a
     later governed-dependency or head change occurs. Exact redelivery returns
     the original terminal check and consuming result without re-reading the
     changed state. A new use at a later authoritative operation time creates a
     new operation key and may then return stale or install an invalidation;
     one operation can never acquire two outcomes.
141. A `current-advice-render-request` has the exact evaluation/result,
     branch-correct advice-chain kind, recommendation, and accepted selection-
     claim cardinality, provable
     `advice_chain_published_at <= requested_at <= available_at`, and
     `currentness_checked_at = available_at`. The successful check and render
     result become visible together only if the final exact-head comparison
     passes; a malformed, backdated, or racing request produces no current
     render.
142. A `manager-authorization-attempt` names exactly one Action Recommendation
     bound to its exact evaluation result and has the required authoritative
     times, manager actor, and branch-correct selection claim or null. The
     successful check and Decision Support authorization-currentness result
     publish atomically. Governance & Audit may then record its separate
     Manager Decision with `decided_at = authorization_attempt.available_at =
     authorization_currentness_result.current_as_of` and every duplicated field derived exactly from
     that attempt and proof. Zero, multiple, cross-evaluation, actor-mismatched,
     hash-mismatched, backdated, or concurrently stale attempts produce no
     successful proof and therefore no authorizing decision.
143. For selection and monitoring, a concurrent successor between evaluation
     of currentness and final publication prevents visibility of the successful
     check, selection result/recommendation, monitoring match result, and review
     request. The operation instead terminates once as
     `CURRENTNESS_NOT_AUTHORITATIVE_HEAD`; replay returns that refusal.
144. A Trade-off Selection carries canonical `selected_at` and verified
     `available_at` with provable order. Each
     `tradeoff-selection-delivery-attempt.v1` separately carries canonical
     `delivered_at` and verified `available_at` with the complete provable order
     `selection.available_at <= delivered_at <= attempt.available_at`, and its
     currentness operation uses exactly the attempt's `available_at`. A
     reversed or unresolved order, copied-field mismatch, or different or
     caller-selected check time cannot accept the delivery or publish an Action
     Recommendation.
145. A valid render operation is mistakenly or maliciously submitted through
     the manager-authorization consumer. That invocation returns
     `CURRENTNESS_OPERATION_MISMATCH` without a terminal claim. The later exact
     render invocation can still perform its check and reach its one terminal
     result; the cross-use attempt cannot poison the operation key.
146. A Monitoring Observation missing exact schema identity
     `monitoring-observation.v1`, carrying another version, or disagreeing with
     its registered observation definition or reviewed Intake & Lineage source-
     mapping manifest entry is
     rejected before predicate evaluation. A cross-subject or pre-activation
     observation likewise cannot emit a monitoring review request.
147. A Composite Compatibility Review referencing anything other than exact
     `composite-compatibility-criteria.v1`, or omitting, duplicating,
     reordering, mistyping, or leaving unevidenced any of its four closed
     domain-review attestations, is unsupported/malformed and cannot make
     `COMPOSITE_COMPONENTS_COMPATIBLE` satisfied or unsatisfied.
148. A Governance & Audit Manager Decision whose `manager_actor_ref`,
     disposition, recommendation, evaluation/result identity, time, accepted
     selection claim, or authorization-currentness proof differs from its
     attempt is invalid and cannot publish. Decision Support never creates that
     decision occurrence.
149. Two proposed Action Recommendation occurrences share one deterministic
     `action_recommendation_key`. Exact replay returns the sole stored
     occurrence/reference/hash; a second occurrence is a cardinality violation
     even if its semantic content is identical, and conflicting content is an
     integrity failure.
150. Selection schema, unsupported-version, series-not-found, and Governance-
     reference failures occur before a valid currentness operation. Malformed
     or unsupported ingress has no structurally valid attempt. A supported,
     structurally valid attempt that finds no series or has a Governance-
     reference failure publishes its one immutable
     `tradeoff-selection-validation-result.v1`; replay returns it without
     reevaluating later state. It never also receives an operation-bound result.
151. A manager-selected recommendation leaves the immutable evaluation result
     as `TRADEOFF_REQUIRES_MANAGER_CHOICE` with its recommendation field null.
     A current render, authorization attempt, or monitoring match instead binds
     `advice_chain_kind = ACCEPTED_TRADEOFF_SELECTION` where applicable and
     carries the exact accepted selection claim plus recommendation; a missing,
     multiple, stale, or cross-evaluation chain fails closed.
152. Two envelopes rewrap the same source record, observation definition,
     source-mapped subject, typed value, and times under different occurrence IDs.
     They derive one `monitoring_observation_key`; only one logical occurrence/
     reference/hash can exist and therefore they cannot emit duplicate manager-
     review requests.
153. Every consumed schema, registry, policy, library, and formula resolves one
     exact immutable governed-version envelope with identifier/version, content
     hash, `published_at`, and supersession state. A missing hash/time or future,
     unresolved, or unsupported envelope fails closed; runtime metadata cannot
     fill it.
154. The recommendation and accepted selection-claim cardinalities in a
     currentness operation are fixed before key derivation by operation kind.
     Selection acceptance always uses both null; authorization and monitoring
     use one recommendation and a claim exactly for manager selection; render
     follows its closed advice-chain kind. No post-claim discovery may change
     the operation key.
155. The referenced source record has one immutable
     `first_available_at = T1`. A wrapper received again at `T2 > T1` must still
     set observation `available_at = T1` and derive the same observation key;
     wrapper or replay time cannot create a second monitoring request.
156. A permission-true evaluation/result/head and immediate recommendation
     share one hash-covered `evaluation_published_at`; exact replay preserves
     it. An immediate monitoring recommendation activates at that time. Render
     or authorization whose request time predates the applicable evaluation or
     accepted-selection publication fails the complete advice-chain chronology
     and cannot perform currentness at a backdated cutoff.

## Acceptance checklist

1. The contract is planning-only; no product code is introduced.
2. Global entry begins as a permission attempt; only a verified permitted
   Subject Verdict whose discriminated subject identity and exact upstream
   Subject Driver State match the input creates a Decision Support Evaluation.
3. Weak, invalid, out-of-domain, and driver-inactive cases cannot reach option
   evaluation; a false driver state yields `SUBJECT_DRIVER_NOT_ACTIVE` without
   making a subject-level causal attribution.
4. Monitoring cannot bypass upstream evidence permission.
5. The Core option set, exact option versions/statuses, composite membership,
   and effective library/link-registry heads are closed and deterministic at
   `constraints_as_of`.
6. Runtime cannot invent an action or composite.
7. Driver-Action Links are versioned, evidence-referenced, externally reviewed
   before approval, and discriminated as `ACTION_MECHANISM` or
   `MONITORING_BASELINE` without giving monitoring a mechanism or benefit
   claim.
8. Every option declares that its intervention effect was not estimated.
9. Speculative options are disclosed but never evaluated or recommended.
10. Case constraints are typed, provenance-bearing, and immutable at
    `constraints_as_of`; the operational cutoff never retimes causal
    `decision_at`. A Release-Timing Preview is exact proposal-bound operational
    evidence only and cannot replace Subject Driver State or create a canonical
    Order Line or exposure fact. Every consumed verified evidence/read-model
    record is available by that operational cutoff; a Manager Attestation
    cannot backdate a late-created upstream record.
11. Required `UNKNOWN` fails closed.
12. Advisory ordinals require an approved, applicable, versioned rubric over
    typed evidence; every unavailable, non-approved, inapplicable, or
    underdetermined result is visibly `UNKNOWN` and prevents unsupported
    dominance without suppressing the option.
13. All hard-constraint rules have deterministic status and registry order.
14. The conditional expedite rule requires a concrete acceleration mechanism.
15. Recoverable fractions are bounded, editable, reviewed assumptions.
16. Core does not fabricate remaining quantity.
17. Initiation, float, project-delay, and rate durations carry explicit closed
    bases. The schedule basis is the exact hash-bound request-wide value from
    `causal-engine-suite-request.v2`; every released row and result must match.
    Comparisons and multiplication require compatible bases with no implicit
    conversion; an absent or invalid rate suppresses only schedule-valued
    options.
18. A separate critical-path translation assumption prevents supplier days
    from being silently valued as project days.
19. Monetary inputs use one ISO currency with no conversion.
20. Exact arithmetic has no intermediate rounding, accepts only the closed
    20-integer-digit/18-fractional-digit decimal domain, caps every materialized
    arithmetic/comparison integer at 4,096 bits, and is independent of ambient
    Decimal settings.
21. Exposure-translation arithmetic separates supplier days, project days,
    gross value, and net
    value.
22. Consequence benefits use a separate operational assumption.
23. Projection ranges are never action-effect intervals or success
    probabilities.
24. Active central value must be positive.
25. Value-sensitive options cannot become sole recommendations. When they
    occupy the entire frontier despite an active robustly positive option, the
    deterministic trade-off retains the highest-central-net robust option as a
    disclosed safety alternative without calling it Pareto-optimal.
26. Composite benefit cannot double count components.
27. Suppression precedence is deterministic and preserves all reasons.
28. Dominated options remain inspectable and eligible.
29. Pareto comparison has no hidden score or weight.
30. Every schedule-affecting option compares central schedule protection in
    `PROJECT_DELAY_DAYS` on the same resolved canonical duration basis;
    recovered supplier-milestone days remain a separate audit value, while
    direct-monetary and monitor-only options use `NOT_APPLICABLE`.
31. Monitoring is a fallback baseline with explicit constraints and exactly
    one approved, atomic, applicable, unsuperseded escalation trigger; a match
    requires one reviewed Intake & Lineage source-mapped observation with the
    exact subject identity, immutable source first-availability time, and post-
    activation chronology, then requests manager review only.
    A fallback recommendation has the closed monitoring selection basis and a
    null runner-up.
32. When no robustly positive option exists, value-sensitive options cannot be
    forced into a choice when the monitoring baseline is unavailable.
33. Runner-up, evidence-gap tie annotation, monitoring fallback, robust safety
    alternative, and two-candidate trade-off rules are deterministic.
34. A sole eligible option is not falsely labelled universally dominant.
35. Evidence-gap incomparability and equal-profile candidate ordering cannot
    masquerade as superiority.
36. Trade-off selection is distinct from authorization, has a closed validation
    result vocabulary, and compares, once-only claims, and publishes against
    the authoritative evaluation-series head as one logical operation with
    exact delivery-attempt replay, later-delivery idempotence, and deterministic
    conflict handling. Pre-currentness invocation refusals are distinct from
    retained operation-bound selection results; every supported structurally
    valid attempt has one immutable terminal result of exactly one kind.
37. Evaluation edits create immutable successor occurrences without mutating
    prior evaluations. Later permission downgrade, authoritative evidence-
    integrity invalidation, governed-dependency lifecycle change, operational
    expiry, or unresolved currentness comparison advances the head to the
    corresponding invalidation kind rather than leaving old advice current.
    Rendering, trade-off selection, authorization-currentness proof, and monitoring firing each
    require currentness proved at their exact operation cutoff. Currentness
    uses closed kind-specific lifecycle predicates and has total terminal
    handling for a pre-existing or racing successor without invalidating it.
    Every permitted operation retains its exact operation-bound successful
    currentness proof; a proof cannot be reused across operation kinds or
    occurrences. An invalid envelope or cross-operation invocation cannot
    claim or poison a valid operation. Each deterministic operation key has one
    occurrence and one terminal claim, and its check plus consuming result
    publish atomically under a final exact-head comparison. Governance & Audit,
    not Decision Support, owns the resulting Manager Decision, whose
    `decided_at` is the authorization attempt's exact `available_at`.
38. Action Recommendations preserve exact values and provenance; current
    rendering, authorization, and monitoring use the complete branch-correct
    immediate or accepted-selection advice chain and prove its publication no
    later than the request time.
39. Generated prose, audit storage, harness utility, future domain review
    execution, source-mapping execution, generic extraction language, and
    action execution remain with their owning downstream tickets; issue #10
    only validates their locked logical inputs and outcomes. No practitioner
    review is claimed in this effort.
40. All 156 minimum conformance scenarios pass.

## Explicitly deferred and out of scope

- Estimating or learning an Intervention Option effect.
- CATE, individualized benefit, policy trees, reinforcement learning, or
  optimized sourcing policies.
- Free-form, LLM-generated, or runtime-composed actions.
- A second driver or a reusable cross-driver ontology.
- Automatic remaining-quantity inference.
- Currency conversion, tax, discounting, NPV, or recurring-cost forecasting.
- Arbitrary user-defined scoring weights.
- Physical SQLite schema, audit event layout, retention, concurrency, and
  replay implementation.
- Intake & Lineage adapter execution or a generic source-extraction language.
- Producing substantive composite-compatibility attestations; no such
  attestation is approved in this hackathon.
- Practitioner validation of the causal DAG, intervention library, assumptions,
  or evidence-card comprehension.
- Artifact drafting, Gemini prompts, sending, or autonomous operational action.
- Exact UI component geometry and click paths.
- Evaluation-harness oracle utility and acceptance thresholds.
- Claiming domain-expert approval before the downstream review occurs.
- Multi-user authorization, production tenancy, or cloud execution.

## Domain-language impact

This contract adds `Decision Support Evaluation`, `Subject Driver State`,
`Case Constraint Snapshot`, `Release-Timing Preview`, `Schedule Protection`,
`Driver-Action Link`, `Monitoring Escalation Trigger`, `Recommendation
Candidate`, `Advisory Rubric`, `Advice Currentness`, and `Operational Validity
Horizon` to the Decision Support language.
It sharpens
`Intervention Option` and `Action Recommendation` without changing their
ownership. `Trade-off selection` is a manager-originated Governance & Audit
occurrence consumed by Decision Support; it is not a Manager Decision or
authorization. `Permission attempt` is contract-local workflow terminology for
the pre-evaluation gate and is not a canonical domain term.
