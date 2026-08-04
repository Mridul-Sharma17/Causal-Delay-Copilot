# Risk-Signal, Pre-Award, and Predictive-Baseline Contract

## Status and authority

This specification resolves the Core ingress, predictive-baseline, and
shared-engine handoff decisions for the reactive Risk Signal and proactive
Proactive Proposal.

It is subordinate to:

- `docs/causal_delay_copilot_stage2_strategy.md` for product and scientific
  intent;
- `docs/specs/canonical-order-event-lineage-contract.md` for canonical
  identities, clocks, missingness, lineage, validation, and confidentiality;
  and
- `docs/specs/exposure-outcome-temporal-eligibility-contract.md` for the
  decision cutoff, provisional proactive semantics, eligibility, exposure,
  outcome, and downstream abstention codes.

If those sources disagree, the Stage 2 strategy controls intent, the canonical
lineage contract controls source-fact semantics, and the temporal-eligibility
contract controls derived subject and cohort semantics.

This contract does not define estimator execution, serialized Analysis Run
artifacts, Evidence Verdict precedence, intervention selection, UI layout,
storage tables, transport endpoints, or external-service integration. Those
remain with their owning decisions.

## Core invariants

1. Reactive and proactive ingress are separate contracts that normalize into
   one Investigation Request and one downstream engine path.
2. A Risk Signal is an untrusted prediction to investigate. Its score,
   threshold, label, Predictive Attribution, and duplicated business context
   are never causal evidence or causal-engine inputs.
3. Reactive business facts are reloaded from one frozen Dataset Version. No
   signal field silently overwrites, supplements, or relinks a canonical fact.
4. A Proactive Proposal is an immutable preview subject, not an Order Line. It
   creates no commitment event, Supplier Load Snapshot, or High-Load Exposure.
5. The reactive causal decision cutoff remains the canonical commitment
   occurrence. Signal clocks never retime exposure or admit post-treatment
   covariates.
6. A proactive decision cutoff is its frozen `decision_at`. Every proposed
   input used for the preview must have been known by that cutoff.
7. Receipt time is an audit clock and never substitutes for a missing source
   or decision-time clock.
8. Both trigger modes freeze one Dataset Version, target milestone kind,
   observation cutoff, causal-question version, and engine configuration
   before derived subject values are inspected. The reactive observation
   cutoff is Risk Signal `known_at`; the proactive observation cutoff is
   proposal `decision_at`.
9. Prediction and SHAP metadata cross the shared handoff only in a segregated
   metadata block excluded from causal-engine input and input hashing.
10. Structural envelope, integrity, revision, and Dataset Version failures are
    recorded and rejected before an Investigation Request exists. A
    structurally valid proactive proposal preserves missing, invalid, unmapped,
    ambiguous, or late-known subject facts as explicit states; the shared
    temporal-eligibility contract owns the resulting subject abstention.
11. Exact duplicate source revisions are idempotent. Conflicting reuse of an
    identity and revision is rejected; no last-write-wins rule exists.
12. All processing is local. Raw or advisory ingress content and Predictive
    Attributions never cross an external language-model or service boundary.

## Shared value types

This contract reuses `FieldValue<T>`, `TemporalValue`, deterministic
dataset-scoped identifiers, Source Observations, validation findings, and data
classification from the canonical lineage contract.

### `SourceEntityReference`

| Field | Type | Rule |
| --- | --- | --- |
| `namespace` | string | Required, versioned source-key namespace |
| `key` | structured scalar or tuple | Required; exact source representation |

The value is a source reference, never a public canonical identifier.

### `TriggerSourceEnvelope`

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Required; exact supported version |
| `source_system` | string | Required; stable integration identity |
| `source_payload_sha256` | digest | Required; hash of protected source bytes |
| `protected_source_locator` | protected reference | Required; never user-facing |
| `data_classification` | enum | Required; canonical lineage enum |

Unknown fields may remain in protected source storage but are ignored by Core.
An unknown required semantic is not inferred from an unknown field name.

## Reactive ingress

### `RiskSignal`

A Risk Signal is one source predictor's immutable assertion that one source
Order Line is at or above its declared alert threshold.

| Field | Type | Rule |
| --- | --- | --- |
| `source` | `TriggerSourceEnvelope` | Required |
| `source_signal_id` | string | Required; stable within `source_system` |
| `source_revision` | string | Required; immutable revision identity |
| `scored_dataset_version_ref` | canonical ID or versioned source-snapshot reference | Required; must resolve to exactly one Dataset Version |
| `source_order_line_ref` | `SourceEntityReference` | Required |
| `predictor_id` | string | Required |
| `predictor_version` | string | Required |
| `feature_contract_version` | string | Required |
| `target_definition_id` | string | Required; Core value `supplier_milestone_miss.v1` |
| `target_milestone_kind` | enum | `supplier_completion` or `supplier_handoff` |
| `score_semantic` | enum | Core value `probability_supplier_milestone_miss` |
| `score_value` | decimal | Required; finite and in `[0, 1]` |
| `alert_threshold` | decimal | Required; finite and in `[0, 1]` |
| `flagged` | boolean | Required; must be `true` and equal `score_value >= alert_threshold` |
| `generated_at` | `TemporalValue` | Required; predictor production/scoring clock |
| `known_at` | `TemporalValue` | Required; first availability to the integration |
| `received_at` | UTC instant | Adapter-assigned; never source-supplied |
| `predictor_artifact_ref` | `FieldValue<reference>` | Explicit missingness allowed |
| `predictive_attribution_ref` | `FieldValue<reference>` | Explicit missingness allowed |
| `advisory_context` | `FieldValue<RiskSignalAdvisoryContext>` | Optional closed allow-list; never an identity or fact source |

`RiskSignalAdvisoryContext` contains only these optional fields:

| Field | Type | Rule |
| --- | --- | --- |
| `source_supplier_ref` | `FieldValue<SourceEntityReference>` | Advisory supplier reference |
| `source_material_or_equipment_ref` | `FieldValue<SourceEntityReference>` | Advisory material or equipment reference |
| `source_target_milestone_kind` | `FieldValue<enum>` | `supplier_completion` or `supplier_handoff` |
| `source_original_promise` | `FieldValue<TemporalValue>` | Advisory original promise |
| `timeline_snapshot_as_of` | `FieldValue<TemporalValue>` | Source snapshot cutoff; when present, must not be later than `generated_at` |

Unknown advisory fields remain only in protected source storage and are not
normalized. A populated advisory value is compared only after its source
reference resolves through a versioned mapping and its temporal representation
is comparable under canonical precision and timezone rules.

`generated_at <= known_at <= received_at` must be established at retained
precision and timezone semantics. An unavailable or contradictory comparison
is not repaired with receipt time.

The canonical subject must be open at `generated_at` under facts known by that
time. Otherwise the signal did not describe an open-order risk and is rejected.
Whether the subject closes after scoring cannot be established from this
immutable scoring Dataset Version. Current-state reconciliation belongs to a
later operations contract that can compare an explicitly newer canonical
version; this adapter never consults or substitutes an implicit latest view.

The `scored_dataset_version_ref` resolves before the Order Line. For the
prototype it is the exact canonical `dataset_version_id` used for scoring. An
external integration may provide a versioned source-snapshot reference only
when a reviewed mapping resolves it to exactly one published Dataset Version.
The adapter never substitutes the latest version.

Within that version, `source_order_line_ref` must resolve deterministically to
exactly one `order_line_id`. The mapping records its rule and evidence
references.

Advisory supplier and material/equipment references are resolved with their
versioned mappings and compared as canonical identifiers. Target milestone
kind uses exact enum equality. Original promise uses `TemporalValue` equality
at retained precision and timezone semantics against the canonical original
promise known by `timeline_snapshot_as_of`, or by `generated_at` when no usable
snapshot cutoff is supplied. A usable `timeline_snapshot_as_of` must be
`<= generated_at` and `<= known_at`.

When both sides are comparable, any inequality or contradictory snapshot clock
rejects as `RISK_SIGNAL_CONTEXT_CONFLICT`. An absent, unresolved, or
non-comparable advisory member is ignored with
`RISK_SIGNAL_CONTEXT_UNVERIFIABLE`; it never supplies or overwrites a canonical
fact and never becomes an alternative identity path.

For the bundled Predictive Stub, `source_system` is fixed by its adapter and
`source_signal_id` is deterministic from Dataset Version, Order Line,
predictor version, target milestone kind, and canonicalized `generated_at`.
Re-scoring the same subject at a different scoring cutoff is a distinct signal;
re-emitting the same score at the same cutoff is idempotent.

### Reactive normalized result

A valid Risk Signal contributes the following normalized values:

- exact `dataset_version_id` and `order_line_id`;
- source-signal identity and revision;
- mapping-rule and Source Observation references;
- predictor and Predictive Attribution references in segregated metadata; and
- all ingress validation findings.

Canonical Order Line, event, promise, supplier, load, covariate, and outcome
facts are reloaded from the Dataset Version. None is copied from the signal.

## Proactive ingress

### `ProactiveProposal`

A Proactive Proposal is one immutable revision of a possible supplier
commitment before award or release.

| Field | Type | Rule |
| --- | --- | --- |
| `source` | `TriggerSourceEnvelope` | Required |
| `proposal_id` | string | Required; stable within `source_system` |
| `proposal_revision` | string | Required; immutable revision identity |
| `dataset_version_id` | ID | Required; exact frozen historical context |
| `proposed_supplier_ref` | `FieldValue<SourceEntityReference>` | Required wrapper; explicit unavailable or invalid states are preserved |
| `target_milestone_kind` | `FieldValue<enum>` | Required wrapper; value is `supplier_completion` or `supplier_handoff` |
| `proposed_original_promise` | `FieldValue<typed proposed fact>` | Required wrapper; a value carries effective `known_at` and lineage |
| `adjustment_inputs` | typed map | Every pre-registered subject covariate is represented with explicit missingness, effective `known_at`, and lineage |
| `decision_at` | `FieldValue<TemporalValue>` | Required wrapper; a usable value is the frozen pre-award decision cutoff |
| `received_at` | UTC instant | Adapter-assigned; never source-supplied |
| `requester_ref` | protected actor/system reference | Required |

The proposal receives no `order_line_id`. Supplier resolution is attempted
within the frozen Dataset Version and its result is preserved as a
`FieldValue<supplier_id>`. Missing, unmapped, or ambiguous supplier resolution
does not relink through advisory context and does not reject a structurally
valid proposal at ingress.

A usable proposed original promise is known by `decision_at`, comparable with
it, and not earlier than it. Each adjustment input used by Core is declared in
the pre-registered adjustment set and has an effective
`known_at <= decision_at`. Missingness and validation findings are preserved
exactly; no value is guessed, defaulted, or derived from a field name.

A structurally valid proposal normalizes even when its decision cutoff,
supplier, target, promise, or required covariate is missing, invalid, unmapped,
ambiguous, or late-known. The shared temporal-eligibility contract then emits
`PROACTIVE_SUBJECT_INPUT_UNUSABLE`: the subject receives
`SUBJECT_INELIGIBLE`, and no subject estimate or recommendation is produced.
When the decision and observation cutoffs are usable, an otherwise valid
historical population estimate may remain available without being applied to
that subject. When either cutoff is unusable, no time-frozen historical
population can be selected for this request and no population estimate is
produced.

The adapter computes a canonical preview-subject digest over:

- proposal source identity and revision;
- Dataset Version;
- supplier reference and resolution state;
- decision-time state;
- target milestone state;
- proposed original promise; and
- typed adjustment inputs with their missingness and lineage references.

Changing any digest input requires a new proposal revision and a new
Investigation Request. Prior previews remain immutable. Eventual commitment is
ingested canonically and recomputed; the preview is never promoted or mutated.

No risk score, alert threshold, flagged state, Predictive Attribution, or
fabricated Order Line identity is accepted in the proactive Core payload.

## Shared Investigation Request

### Logical schema

| Field | Type | Rule |
| --- | --- | --- |
| `investigation_request_id` | opaque ID | Required; unique accepted request |
| `schema_version` | string | Required |
| `trigger_mode` | enum | `reactive` or `proactive` |
| `ingress_ref` | tagged union | Exactly one Risk Signal or Proactive Proposal identity/revision |
| `rerun_of_request_id` | `FieldValue<ID>` | Present only for explicit fresh rerun |
| `dataset_version_id` | ID | Required and immutable |
| `subject` | tagged union | Reactive canonical Order Line or proactive preview subject |
| `decision_cutoff` | `FieldValue<TemporalValue>` | Reactive value is required; proactive preserves an unusable state for shared subject eligibility |
| `decision_cutoff_source` | enum | `canonical_commitment` or `proactive_decision` |
| `observation_cutoff` | `FieldValue<TemporalValue>` | Reactive value is required; proactive is its preserved `decision_at` state |
| `target_milestone_kind` | `FieldValue<enum>` | Reactive value is required; proactive preserves an unusable state |
| `causal_question_version` | string | Required; system-selected |
| `engine_configuration_ref` | versioned reference | Required; system-selected |
| `ingress_validation_refs` | list | Required, possibly empty |
| `provenance_refs` | non-empty list | Required |
| `prediction_metadata` | `FieldValue<object>` | Reactive-only segregated metadata; `not_applicable` for proactive |
| `accepted_at` | UTC instant | Required audit clock |

The reactive subject contains only `order_line_id`; the engine obtains all
business facts from `dataset_version_id`. The proactive subject contains the
preview-subject digest and explicit `FieldValue` states for resolved
`supplier_id`, promise, and typed decision-time inputs required by the
temporal-eligibility contract.

For a reactive request, `observation_cutoff` equals the accepted Risk Signal's
`known_at`. For a proactive request, it has the same explicit value or
unusable state as the Proactive Proposal's `decision_at`. `received_at` and
`accepted_at` are audit clocks only and never extend the available-fact view.
A later updated view requires an explicit new request or rerun with a later
source decision clock.

Ingress cannot choose or override the causal question, estimand, adjustment
set, selectors, gates, or engine configuration. Those are selected from
versioned system configuration before the request is accepted.

### `CausalEngineInput` trust-boundary projection

The shared handoff creates `CausalEngineInput` through a closed allow-list; it
never serializes the Investigation Request wholesale. Its exact logical fields
are:

| Field | Rule |
| --- | --- |
| `causal_input_schema_version` | Exactly `causal-input-projection.v2` |
| `dataset_version_id` | Exact frozen Dataset Version used by this run |
| `subject_analytical_values` | Mode-neutral typed values and explicit states for supplier, original promise, adjustment inputs, and subject exclusion identity |
| `decision_cutoff` | Typed value or explicit unusable state |
| `observation_cutoff` | Typed value or explicit unusable state |
| `target_milestone_kind` | Typed value or explicit unusable state |
| `canonical_slippage_duration_basis` | Exact `CALENDAR_DAY` or `ELAPSED_86400_SECOND_DAY` frozen by the temporal-eligibility release |
| `causal_question_version` | Fixed system-selected version |
| `engine_configuration_ref` | Fixed versioned configuration reference |
| `estimator_window_ref` | Versioned selector, bounds, ordered selected-identity hash, and subject-removal result |
| `history_lookback_ref` | Versioned selector, bounds, and ordered selected-identity hash |
| `historical_population_digest` | Digest of the ordered post-subject-removal analytical population |
| `analytical_fact_lineage_refs` | Ordered references for facts represented in this projection |

`subject_analytical_values` uses the same field names for reactive and
proactive computation. Canonical/provisional presentation labels remain
outside this projection.

The canonical serializer fixes field order, list order, scalar encodings,
explicit-state encodings, and temporal precision under
`causal_input_schema_version`. `causal_input_digest` is the lowercase
`sha256:` digest of those canonical bytes.

The shared handoff constructs `causal-engine-suite-request.v2` only when the
temporal-eligibility release supplies one concrete
`canonical_slippage_duration_basis` and every releasable row carries that exact
value. A run-scoped `SLIPPAGE_DURATION_BASIS_MIXED` result is persisted as
scientific unavailability and stops before engine-request construction. The
handoff never chooses the majority basis, converts a row, drops a conflicting
row, or relabels the abstention as an engine failure.

The projection explicitly has no field for `investigation_request_id`,
`trigger_mode`, `ingress_ref`, `rerun_of_request_id`, `accepted_at`,
`received_at`, requester data, raw payload locators, ingress findings,
trigger-provenance fields, `prediction_metadata`, Risk Signal score,
threshold, flagged state, Predictive Attribution, or advisory context.
Excluded values cannot affect feature assembly, weights, cohort selection,
question construction, diagnostics, or verdict.

Changing only an excluded value must preserve the exact projected bytes and
`causal_input_digest`. Changing an analytical fact or frozen selector must
change the projection and normally its digest; digest collision handling is
owned by the canonical lineage integrity policy.

### Idempotency and reruns

The adapter derives an idempotency key from the source system, source
identity, source revision, payload hash, frozen Dataset Version, target
milestone kind, and accepted configuration references.

- Exact redelivery returns the existing accepted request and records the
  duplicate receipt.
- Reuse of the same source identity and revision with a different payload hash
  rejects as a revision conflict.
- An explicit fresh rerun is a new command, not redelivery. It creates a new
  request with `rerun_of_request_id`, an explicit later source decision clock
  supplying its newly frozen observation cutoff, and explicit configuration
  references. Later run/artifact contracts own the resulting Analysis Run
  identity.

## Predictive Stub

### Purpose and target

The Predictive Stub is a deliberately ordinary prediction-only baseline. It
estimates:

```text
P(Supplier Milestone Slippage > 0
  for the configured original supplier milestone)
```

It exists only to produce reactive Risk Signals and the evaluation baseline.
It does not run for proactive checks and makes no driver, causal, or action
claim.

### Model discipline

- implementation: scikit-learn 1.6.1 `HistGradientBoostingClassifier`;
- base estimator: scikit-learn 1.6.1 constructor defaults made explicit
  in the artifact, except `random_state = 0`, `early_stopping = false`, and
  `class_weight = null`; no hyperparameter search is run;
- binary target: the same fixed target milestone kind used by the causal
  question;
- inputs: only versioned point-in-time features available at commitment,
  including load-at-placement and the harness's planted predictive correlate;
- forbidden inputs: later progress, promise revisions, escalation, expediting,
  premium freight, recovery actions, outcomes, and any post-treatment field;
- preprocessing, feature order, categorical and missingness encoding,
  hyperparameters, dependency versions, and random seed are explicit in the
  model artifact;
- fit, calibration, and evaluation rows must have usable commitment, frozen
  original promise, target outcome, follow-up maturity, and versioned
  point-in-time predictor features under the same canonical lineage and clock
  rules; prediction does not require exposure, causal-overlap, or
  effect-estimation eligibility;
- chronological partitions are fixed before training: model-fit window,
  disjoint sigmoid-calibration window, and untouched evaluation window;
- calibration fits scikit-learn 1.6.1 `CalibratedClassifierCV` with
  `method = "sigmoid"` around a `FrozenEstimator` containing the already-fitted
  base model, using only the disjoint calibration window;
- no random cross-window mixing, online learning, case-specific tuning, or
  outcome-dependent feature selection;
- the final score is the calibrated class-one probability;
- the Core alert threshold is exactly `0.50` and is never tuned after
  evaluation; and
- runtime loads a bundled versioned model/calibrator artifact and never trains
  or downloads a replacement.

If the artifact, calibrator, feature contract, target definition, dependency
versions, or required subject features are incompatible, the stub emits no
score and no Risk Signal.

### Scoring behavior

At one frozen scoring cutoff, the stub scores every eligible open canonical
Order Line in the frozen Dataset Version.

Every successful score creates an immutable `PredictionRecord`:

| Field | Type | Rule |
| --- | --- | --- |
| `prediction_record_id` | deterministic ID | Dataset Version + Order Line + model version + generated/scoring time |
| `dataset_version_id`, `order_line_id` | ID | Required |
| `predictor_id`, `predictor_version` | string | Required |
| `feature_contract_version` | string | Required |
| `target_definition_id`, `target_milestone_kind` | string/enum | Required |
| `generated_at` | `TemporalValue` | Frozen scoring cutoff |
| `score_semantic` | enum | `probability_supplier_milestone_miss` |
| `score_value` | decimal | Finite `[0, 1]` |
| `alert_threshold` | decimal | Core value `0.50` |
| `flagged` | boolean | `score_value >= 0.50` |
| `model_artifact_ref` | reference | Required |
| `feature_snapshot_hash` | digest | Required |
| `predictive_attribution_ref` | `FieldValue<reference>` | Explicit |

A Risk Signal is emitted only for `flagged = true`. A below-threshold
Prediction Record never enters the reactive journey. An unscorable subject
creates a named immutable prediction-failure record; no score, threshold
fallback, or substitute model is fabricated.

### Versioned predictive-baseline report

The bundled model artifact and report preserve:

- Dataset Version and fit/calibration/evaluation cohort hashes;
- chronological window boundaries;
- target and feature-contract versions;
- complete preprocessing, hyperparameters, feature order, seeds, and
  dependency versions;
- sample counts and outcome prevalence by partition;
- AUROC, average precision, Brier score, and calibration-curve data on the
  untouched evaluation partition;
- at threshold `0.50`, the confusion matrix, recall, precision, specificity,
  and alert rate;
- SHAP background/evaluation cohort selection rules and hashes; and
- the fixed label `prediction performance - not causal or decision evidence`.

No reported metric changes the model, features, calibrator, or threshold after
evaluation.

## Predictive Attribution

### Method and artifact

The attribution explains the final class-one calibrated probability, not a
base-tree output or causal quantity. It uses the version-pinned SHAP
`PermutationExplainer` over the callable
`calibrated_model.predict_proba(X)[:, 1]`, with the identity link and the frozen
background matrix as masker. Each subject explanation constructs a fresh
explainer with seed `0`; no mutable explainer RNG is shared between subjects or
between local and global output. For `p` ordered model features, each local
explanation fixes
`max_evals = 10 * (2 * p + 1)`, giving ten complete forward/reverse
permutation cycles.

The frozen background cohort is selected deterministically from the model-fit
population. Its selector is outcome-independent and retains the first at most
200 rows in ascending stable identity-hash order. The selector version,
ordered identities, ordered feature matrix, and content hash are retained.

Each local artifact records:

- SHAP and dependency versions, `PermutationExplainer`, identity link, seed
  `0`, feature count, and `max_evals`;
- predictor, feature-contract, and background-selector versions;
- background-cohort identity hash;
- Prediction Record and subject references;
- every ordered model feature value and missingness state;
- probability-scale base value;
- every signed probability-point feature contribution;
- reconstructed probability;
- final `score_value`; and
- additivity residual and validation status.

The artifact is valid only when the base value plus all contributions
reconstructs the final calibrated `score_value` with absolute residual
`<= 1e-6`. Failure suppresses the attribution but does not alter a valid
Prediction Record or causal investigation.

Presentation may show the five largest absolute local contributions and one
signed `other_features` sum. The complete artifact always retains every
feature contribution. Evaluation subjects are explained independently in
ascending stable identity-hash order under the same fresh-explainer procedure.
Global output is the mean absolute contribution of each feature over those
retained local results for the frozen untouched evaluation cohort.

Every local and global output carries:

> Predictive attribution - not causal evidence.

SHAP comparison belongs to evaluation, deck, video, and demo-comparison
surfaces. It is not a driver claim and never appears as supporting evidence on
the operational causal evidence card.

## Validation and failure behavior

### Result envelope

Every ingress attempt produces an audit-safe result with:

- source identity/revision and payload hash;
- status: `accepted`, `duplicate`, `rejected`, or `accepted_with_warning`;
- stable primary code and all supporting findings;
- scope: `reactive_ingress`, `proactive_ingress`, `shared_handoff`, or
  `predictive_stub`;
- evidence references;
- `retryable` boolean;
- constructive next step; and
- Investigation Request reference only when accepted.

Logs and ordinary result messages contain identifiers, codes, hashes, and
protected references, not raw payloads, supplier names, commercial values, or
free text.

### Primary-code precedence

Validation retains every finding that can be established without relying on a
failed earlier phase. When more than one rejecting finding is present, the
stable primary code is the first applicable code in this phase order:

1. schema and required structural wrappers;
2. envelope integrity and protected-payload checks;
3. source identity, revision conflict, and idempotency;
4. required reactive clock comparability and ordering;
5. frozen Dataset Version and reactive subject identity/state;
6. reactive target compatibility;
7. reactive score and threshold consistency;
8. comparable advisory-context conflict;
9. shared causal-question and engine-configuration availability.

Within a phase, the first code in the registry below is primary. A proactive
subject fact represented by a valid structural wrapper is not an ingress
failure: missing, invalid, unmapped, ambiguous, or late-known semantics remain
owned by downstream `PROACTIVE_SUBJECT_INPUT_UNUSABLE`.

Warnings do not outrank a rejection. Only after every rejecting phase passes
do one or more warnings change `accepted` to `accepted_with_warning`. All
supporting findings remain in deterministic phase and registry order.

### Stable ingress code registry

| Code | Disposition | Meaning |
| --- | --- | --- |
| `RISK_SIGNAL_SCHEMA_UNSUPPORTED` | reject | Reactive schema version or required semantic is unsupported |
| `RISK_SIGNAL_INTEGRITY_FAILED` | reject | Payload hash, protected locator, or envelope integrity failed |
| `RISK_SIGNAL_REVISION_CONFLICT` | reject | Same source identity/revision has different content |
| `RISK_SIGNAL_CLOCK_UNUSABLE` | reject | Required signal clocks are missing, incomparable, or contradictory |
| `RISK_SIGNAL_SUBJECT_UNRESOLVED` | reject | Dataset Version or Order Line cannot be resolved |
| `RISK_SIGNAL_SUBJECT_AMBIGUOUS` | reject | Version or subject resolves to more than one candidate |
| `RISK_SIGNAL_SUBJECT_NOT_OPEN` | reject | Canonical subject was not open when the signal was generated |
| `RISK_SIGNAL_TARGET_MISMATCH` | reject | Signal target conflicts with the configured supplier milestone |
| `RISK_SIGNAL_SCORE_UNUSABLE` | reject | Score/threshold is invalid or `flagged` is inconsistent |
| `RISK_SIGNAL_CONTEXT_CONFLICT` | reject | Comparable advisory context materially conflicts with canonical facts |
| `RISK_SIGNAL_CONTEXT_UNVERIFIABLE` | warning | Advisory context is absent, unresolved, or non-comparable and was ignored |
| `PROACTIVE_SCHEMA_UNSUPPORTED` | reject | Proactive schema version or required semantic is unsupported |
| `PROACTIVE_INTEGRITY_FAILED` | reject | Payload hash, protected locator, or envelope integrity failed |
| `PROACTIVE_REVISION_CONFLICT` | reject | Same proposal identity/revision has different content |
| `PROACTIVE_DATASET_UNAVAILABLE` | reject | Frozen Dataset Version is missing, invalid, or not authorized |
| `CAUSAL_QUESTION_VERSION_UNAVAILABLE` | reject | Required fixed causal-question version cannot be loaded |
| `ENGINE_CONFIGURATION_UNAVAILABLE` | reject | Required frozen engine configuration cannot be loaded |
| `PREDICTOR_ARTIFACT_UNAVAILABLE` | warning | External predictor artifact is unavailable; comparison view is suppressed |
| `PREDICTIVE_ATTRIBUTION_UNAVAILABLE` | warning | Attribution is absent or invalid; comparison view is suppressed |

### Predictive Stub failure codes

| Code | Meaning |
| --- | --- |
| `PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE` | Bundled model/calibrator artifact is absent or fails integrity/version checks |
| `PREDICTIVE_FEATURE_CONTRACT_MISMATCH` | Runtime feature schema or ordering differs from the model contract |
| `PREDICTIVE_SUBJECT_UNSCORABLE` | Required subject feature is invalid, prohibited, unresolved, or unsupported |
| `PREDICTIVE_SCORE_INVALID` | Model output is non-finite or outside `[0, 1]` |
| `PREDICTIVE_ATTRIBUTION_INVALID` | Attribution fails integrity, feature alignment, or additivity validation |

Predictive Stub failures create no Risk Signal. A missing external predictor
artifact or attribution remains a warning only after an otherwise valid
external Risk Signal has been accepted.

Canonical and downstream codes remain owned by their existing contracts,
including `COMMITMENT_CUTOFF_UNUSABLE` and
`PROACTIVE_SUBJECT_INPUT_UNUSABLE`. The adapter does not rename downstream
eligibility failures or turn them into prediction failures.

## Confidentiality and service boundary

1. Ingress is application-controlled and server-side, accepts only allow-listed
   bundled inputs, is size-bounded, and is validated before normalization.
2. Raw payloads remain in protected source storage. Normalized records retain
   hashes and evidence pointers, not copied free text.
3. A normalized or derived record inherits the most restrictive data
   classification among its contributing inputs.
4. Raw/advisory Risk Signal data, Proactive Proposal data, Prediction Records,
   model features, and Predictive Attributions cannot enter Gemini or another
   external service.
5. Only a later, separately governed artefact-composition boundary may receive
   explicitly sanitized structured evidence.
6. Unknown fields, prompt-like text, filenames, URLs, and source labels are
   data, never instructions.

## Trigger parity

Trigger parity is asserted only after mode-specific subject handling has
produced the same normalized analytical inputs. A reactive fixture starts with
its canonical subject in the Dataset Version and removes that subject from the
estimator population before the first eligibility stage. Its paired proactive
fixture starts with no canonical subject in the source population. The pair is
comparable only when the resulting historical-population projection has the
same ordered contents and digest, and the normalized subject analytical facts,
cutoffs, target, causal-question version, and engine configuration are equal.

For a comparable pair, both trigger modes use the same:

- causal-question version and target milestone kind;
- historical and estimator-window selectors;
- exposure and promise rules;
- adjustment set and missingness rules;
- estimator cohort;
- subject support and eligibility gates;
- estimators, diagnostics, refuters, sensitivity logic, and validity service;
- Evidence Verdict and abstention precedence; and
- downstream decision-support path.

The only permitted differences are:

- canonical Order Line versus immutable preview subject;
- canonical commitment cutoff versus proactive `decision_at`;
- Risk Signal provenance versus proposal provenance;
- canonical `concurrent_load_count`, `load_percentile`, and
  `high_load_exposure` versus explicitly provisional preview field names; and
- trigger-specific ingress validation codes.

Entry framing may differ in the UI. Trigger-specific ingress records,
pre-projection source-population counts, and subject-removal audit findings are
not parity targets. The normalized historical-population digest, analytical
subject transformations, final estimator inputs, shared evidence semantics,
estimates, diagnostics, verdicts, and decision rules are parity targets.

## Conformance examples

Implementations must pass these cases in addition to surrounding contract
tests.

1. **Version before subject:** a source Order Line key present in two Dataset
   Versions with no resolvable `scored_dataset_version_ref` rejects as
   `RISK_SIGNAL_SUBJECT_AMBIGUOUS`; latest is never chosen.
2. **Exact reactive mapping:** one source version and source Order Line mapping
   produce exactly one canonical `dataset_version_id + order_line_id` and
   preserve mapping evidence.
3. **Advisory mismatch:** a signal's advisory supplier differs from the
    canonical subject supplier; it rejects with
    `RISK_SIGNAL_CONTEXT_CONFLICT` and is not relinked. An unresolved advisory
    material reference instead produces `RISK_SIGNAL_CONTEXT_UNVERIFIABLE`,
    is ignored, and supplies no canonical fact.
4. **Signal time cannot retime treatment:** a signal generated months after
   commitment retains the commitment occurrence as causal cutoff; later
   progress fields remain prohibited.
5. **Clock substitution forbidden:** missing `known_at` with present
   `received_at` rejects with `RISK_SIGNAL_CLOCK_UNUSABLE`.
6. **Delayed reactive receipt:** a signal known at `10:00` and received at
   `10:05` freezes its observation cutoff at `10:00`; facts first known in the
   five-minute gap are unavailable.
7. **Delayed proactive receipt:** a proposal decided at `10:00` and received
   at `10:05` freezes its observation cutoff at `10:00`; facts first known in
   the five-minute gap are unavailable.
8. **Threshold equality:** a calibrated score of exactly `0.50` is flagged; a
   score immediately below is not.
9. **Flag inconsistency:** `score_value = 0.70`, `alert_threshold = 0.50`, and
   `flagged = false` rejects with `RISK_SIGNAL_SCORE_UNUSABLE`.
10. **Not open when scored:** a subject already closed under facts known at
   `generated_at` rejects with `RISK_SIGNAL_SUBJECT_NOT_OPEN`.
11. **Below-threshold persistence:** a valid `0.49` Prediction Record is retained
   for evaluation but emits no Risk Signal.
12. **No fallback model:** an incompatible feature contract emits
   `PREDICTIVE_FEATURE_CONTRACT_MISMATCH`, with no score or Risk Signal.
13. **Conflicting redelivery:** identical source signal identity/revision with
    a different payload hash rejects as `RISK_SIGNAL_REVISION_CONFLICT`.
14. **Exact redelivery:** identical source identity, revision, payload,
    Dataset Version, target, and configuration returns the existing
    Investigation Request.
15. **Proactive identity:** one proposal revision resolves one supplier and
    creates a preview-subject digest but no Order Line or commitment event.
16. **Late-known proactive field:** a required covariate first known after
    `decision_at` is preserved in the accepted request; shared eligibility
    emits subject-level `PROACTIVE_SUBJECT_INPUT_UNUSABLE`, with no subject
    estimate or recommendation. An unusable `decision_at` emits the same
    subject code but also prevents time-frozen historical-population selection
    and therefore produces no population estimate for that request.
17. **Promise before decision:** a proposed original promise earlier than
    `decision_at` is preserved in the accepted request; shared eligibility
    emits subject-level `PROACTIVE_SUBJECT_INPUT_UNUSABLE`.
18. **Proposal revision:** changing supplier, promise, covariate, or
    `decision_at` requires a new revision; the earlier preview remains
    unchanged.
19. **Commitment is fresh:** an eventually committed proposal is ingested and
    recomputed canonically; no preview identifier or provisional derived field
    is promoted.
20. **Prediction firewall:** changing Risk Signal score, threshold, SHAP
    values, or advisory timeline while holding the accepted canonical subject
    and shared configuration fixed cannot change causal-engine input bytes.
21. **SHAP reconstruction:** deterministic `PermutationExplainer` output for
    the final calibrated positive-class probability reconstructs that score
    with absolute residual `<= 1e-6`; otherwise the attribution is suppressed
    while the valid prediction remains.
22. **SHAP presentation:** the five displayed contributions plus
    `other_features` sum to the complete contribution total.
23. **Matched trigger pair:** a reactive fixture whose canonical subject is
    removed before eligibility and a proactive fixture in which that subject
    is absent begin with mode-appropriate Dataset Versions. With reactive
    `known_at` equal to proactive `decision_at`, the pair yields the same
    normalized historical-population digest, subject analytical facts, target,
    request-wide slippage duration basis, and configuration. It then produces
    identical shared load counts,
    percentiles, threshold values, eligibility outcomes, final estimator
    inputs, estimates, diagnostics, and verdicts; trigger-specific ingress and
    pre-projection audit facts may differ.
24. **No external transmission:** a confidential proposal and its SHAP-free
    Investigation Request complete through local validation without any
    external network payload.
25. **Duration-basis handoff:** an all-date released cohort serializes
    `CALENDAR_DAY` once in `causal-input-projection.v2` and on every engine row;
    an all-datetime/instant cohort analogously serializes
    `ELAPSED_86400_SECOND_DAY`. A mixed otherwise releasable union emits
    `SLIPPAGE_DURATION_BASIS_MIXED` and constructs no engine request.

## Acceptance checklist

The contract is satisfied only when:

1. separate reactive and proactive schemas validate independently;
2. every accepted trigger normalizes into the shared request without
   prediction fields entering causal input;
3. all identity, revision, timestamp, Dataset Version, and idempotency cases
   above pass;
4. the Predictive Stub is deterministic, bundled, offline, and thresholded at
   `0.50`;
5. Prediction Records and model reports are reproducible from their artifacts;
6. local and global Predictive Attributions are probability-scale,
   lineage-bearing, additive, and visibly non-causal;
7. ingress rejections, predictive failures, warnings, and downstream
   abstentions retain their distinct codes and scopes;
8. matched reactive/proactive parity passes at the shared-engine boundary; and
9. one request-wide slippage duration basis is preserved exactly or mixed-basis
   cohorts abstain before engine invocation; and
10. logs and external-service boundaries preserve confidentiality.
