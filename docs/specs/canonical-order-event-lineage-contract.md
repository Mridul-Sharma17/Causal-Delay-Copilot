# Canonical Order-Event and Lineage Contract

## Status and authority

This document specifies the logical ingestion boundary for Core. It is the
accepted resolution of the Wayfinder ticket
[Define the canonical order-event and lineage contract](https://github.com/Mridul-Sharma17/Causal-Delay-Copilot/issues/5).
The Stage 2 strategy remains authoritative for product and scientific intent.

This contract deliberately does not specify serialization, physical storage,
API endpoints, exposure or outcome computation, analysis-run artifacts, risk
signals, audit replay, or user-upload behavior. Those decisions belong to
neighboring Wayfinder tickets.

## Contract principles

1. Source history is immutable. Corrections append and supersede; they never
   rewrite prior facts.
2. Canonical identity is deterministic, opaque, and scoped to one logical
   dataset. No cross-dataset supplier resolution is inferred.
3. Decision-time availability is distinct from occurrence time and ingestion
   time.
4. A canonical value is usable only with explicit semantics, missingness, and
   field-level lineage.
5. Adapters map, normalize, and validate. They do not impute, select an
   analysis cohort, or calculate causal variables.
6. A successful ingestion publishes an immutable `DatasetVersion`; failed
   attempts remain `IngestionRun` records without a published version.
7. Restricted raw values remain in their protected source package and never
   appear in distributable lineage or validation messages.

## Shared value types

### `FieldValue<T>`

Every optional canonical field is represented by a state and, only when
present, a typed value. The wrapper itself is always serialized; optionality
never means omitting the field.

| Field | Type | Rule |
| --- | --- | --- |
| `state` | enum | `present`, `absent`, `unknown`, `not_applicable`, `redacted`, or `invalid` |
| `value` | `T` | Required only when `state = present`; prohibited otherwise |

State semantics:

- `absent`: the source has no corresponding field.
- `unknown`: the source explicitly records null, blank, unknown, or not
  captured.
- `not_applicable`: the field does not semantically apply.
- `redacted`: a value exists but was deliberately withheld.
- `invalid`: a source value exists but cannot be interpreted safely.

Adapters must not replace non-present states with zeroes, empty strings,
guessed dates, or imputed values.

### `TemporalValue`

A present temporal value records:

| Field | Type | Rule |
| --- | --- | --- |
| `kind` | enum | `date`, `local_datetime`, or `instant` |
| `normalized_value` | ISO-8601 value | Must match `kind` |
| `precision` | enum | Source precision, such as `date`, `minute`, `second`, or `microsecond` |
| `timezone_status` | enum | `known`, `assumed`, `unknown`, or `not_applicable` |
| `source_timezone` | `FieldValue<string>` | Present for `known` or `assumed` zones; otherwise explicit non-present state |

Rules:

- Date-only values remain calendar dates; adapters do not manufacture
  midnight instants.
- Zoned timestamps normalize to UTC while their source zone remains recorded
  in lineage.
- Unzoned timestamps remain `timezone_status = unknown` unless a
  dataset-level mapping assumption supplies a zone. Assumed zones are
  provenance-bearing transformations and emit `TIMEZONE_ASSUMED`.
- Comparisons that need unavailable precision or timezone knowledge emit a
  validation finding rather than inventing an order.
- `ingested_at` is always a UTC instant.

### Quantities, money, and classifications

- Quantity is `{amount, unit}`. Unit conversion requires a named, versioned
  transformation rule.
- Money is `{amount, currency}` using an ISO currency code. Ingestion performs
  no exchange-rate conversion.
- Material, complexity, project phase, urgency, geography, and contract-form
  classifications use dataset-local canonical codes plus display labels.
- Cross-dataset pooling, entity matching, and ontology alignment are outside
  this contract.

## Identifier rules

- `dataset_id` identifies one logical dataset instance and remains stable
  across its refreshed versions.
- `order_line_id`, `order_group_id`, and `supplier_id` are deterministic from
  `dataset_id`, the entity kind, and the adapter-declared canonical
  serialization of the preserved source-key tuple.
- The default deterministic ID rule is UUIDv5 under the dataset namespace.
  Any alternative is a schema-versioned mapping decision and must preserve
  the same stability and scoping properties.
- Source keys remain in lineage and are not used as public canonical IDs.
- `event_id` is deterministic from the dataset namespace, event kind, source
  locator, and source revision key. Exact re-ingestion therefore deduplicates.
- `DatasetVersion` IDs use a `sha256:` content digest over canonical schema
  version, reviewed source-schema identity/version, adapter identity/version,
  mapping assumptions, input hashes, and canonical semantic-payload hashes
  computed before record envelopes receive their `dataset_version_id`. This
  avoids a circular hash. Per-record `ingested_at` values, first-publication
  timestamps, run IDs, predecessor links, and final serialized-file hashes are
  publication metadata and are excluded from version identity; final file
  hashes remain recorded for integrity.
- A source row disappearing from a later extract does not mean cancellation
  or deletion. Only an explicit source fact may create a cancellation event.

## Canonical records

### `IngestionRun`

One adapter execution attempt.

| Field | Type | Requirement |
| --- | --- | --- |
| `ingestion_run_id` | opaque ID | Required; unique per attempt |
| `adapter_id`, `adapter_version` | string | Required |
| `source_schema_id`, `source_schema_version` | string | Required; use a reviewed structural `sha256:` fingerprint when the source publishes no version |
| `canonical_schema_version` | string | Required |
| `source_objects` | list | Required; logical name, SHA-256, size, and protected locator |
| `mapping_assumptions` | list of versioned IDs | Required, possibly empty |
| `started_at` | UTC instant | Required |
| `completed_at` | `FieldValue<UTC instant>` | `absent` while running; present when terminal |
| `status` | enum | `running`, `succeeded`, or `failed` |
| `published_dataset_version_id` | `FieldValue<ID>` | Present only after successful publication or deterministic reuse |
| `validation_summary` | `FieldValue<object>` | `absent` while running; present with counts by code/disposition when terminal |
| `validation_finding_ids` | `FieldValue<list<ID>>` | `absent` while running; present, possibly empty, when terminal |

Repeated ingestion of identical inputs may reuse an existing
`DatasetVersion`; the new `IngestionRun` records that reuse without creating a
second version or rewriting its original publication metadata.

### `DatasetVersion`

An immutable publishable canonical dataset manifest.

| Field | Type | Requirement |
| --- | --- | --- |
| `dataset_id`, `dataset_version_id` | ID | Required |
| `predecessor_dataset_version_id` | `FieldValue<ID>` | Present for a changed refresh; `absent` for first publication or exact reuse |
| `source_kind` | enum | `semi_synthetic`, `olist`, or `scms` |
| `intended_role` | enum | `semi_synthetic_hero`, `out_of_domain_validation`, or `rejection_vignette` |
| `canonical_schema_version` | string | Required |
| `adapter_id`, `adapter_version` | string | Required |
| `source_schema_id`, `source_schema_version` | string | Required |
| `input_hashes` | non-empty list | Required source-object hashes |
| `semantic_payload_hashes` | non-empty list | Required; participates in version identity |
| `output_hashes` | non-empty list | Required final serialized-file integrity hashes |
| `first_published_at` | UTC instant | Required; excluded from content identity |
| `first_published_by_run_id` | ID | Required; excluded from content identity |
| `record_counts` | object | Order Line, event, observation, finding, and quarantine counts |
| `mapping_assumptions` | list of versioned IDs | Required, possibly empty |
| `validation_summary` | counts by code/disposition | Required |
| `license_and_attribution_ref` | `FieldValue<string>` | Explicit even when unknown |
| `data_classification` | enum | `generated`, `public`, `restricted`, or `confidential` |
| `raw_redistribution_policy` | enum + explanation | `allowed`, `attribution_required`, `prohibited`, or `unknown` |
| `derived_redistribution_policy` | enum + explanation | Same enum |
| `provenance_summary` | counts by provenance axes | Required |
| `generator_metadata` | `FieldValue<object>` | Present only for `semi_synthetic`; `not_applicable` otherwise |

Present `generator_metadata` contains `generator_version`, `seed`,
`scenario_id`, `parameter_set_hash`, `calibration_evidence_refs`, and the
separate evaluation-only ground-truth artifact hash. It contains no planted
effect values or protected ground-truth locator.

### `OrderLine`

The identity anchor and commitment-time baseline facts for one atomic supplier
commitment.

Universally required:

| Field | Type | Semantics |
| --- | --- | --- |
| `dataset_version_id` | ID | Version containing this record |
| `order_line_id` | ID | Atomic commitment identity |
| `order_group_id` | ID | PO/order/package group; self-grouped when the source has none |
| `supplier_id` | ID | Supplier identity within this dataset only |

Typed optional commitment-time facts:

- `material_class`
- `complexity_class`
- `quantity`
- `value`
- `project_id`
- `project_phase`
- `urgency_class`
- `geography_code`
- `contract_form`

Each uses `FieldValue<T>`. A field may be populated only when its
effective `known_at` is no later than the present
`committed.occurred_at`—the commitment decision cutoff—not
`committed.known_at`. An Order Line without a present commitment occurrence
clock cannot populate commitment-time baseline facts. Later source changes
never overwrite the baseline. They remain in the protected source package or
a namespaced extension until a future schema revision defines a governed
event.

Requested lead time, supplier-history measures, load, exposure, outcome, and
eligibility are derived by later contracts and are not `OrderLine` fields.

`extensions` may preserve adapter-specific attributes under a namespace owned
by that adapter. Core validation and analysis must ignore extensions unless a
later canonical schema version promotes their semantics.

### `OrderLineEvent`

An immutable time-qualified fact about one Order Line.

| Field | Type | Requirement |
| --- | --- | --- |
| `dataset_version_id`, `event_id`, `order_line_id` | ID | Required |
| `kind` | enum | `committed`, `promise_recorded`, `promise_revised`, `milestone_reached`, or `cancelled` |
| `milestone_kind` | `FieldValue<enum>` | Present for promise and reached-milestone events; `not_applicable` otherwise |
| `occurred_at` | `FieldValue<TemporalValue>` | Domain occurrence clock |
| `known_at` | `FieldValue<TemporalValue>` | First decision-time availability clock |
| `ingested_at` | UTC instant | Required |
| `promised_for` | `FieldValue<TemporalValue>` | Present for promise events; `not_applicable` otherwise |
| `reason` | `FieldValue<string>` | Required wrapper; may be present for revision or cancellation |
| `revises_promise_event_id` | `FieldValue<ID>` | Present for `promise_revised`; `not_applicable` otherwise |
| `supersedes_event_id` | `FieldValue<ID>` | Present only for an evidenced correction; `absent` otherwise |

`milestone_kind` is one of:

- `supplier_completion`
- `supplier_handoff`
- `customer_delivery`
- `other`

Additional invariants:

- `milestone_reached` requires a present `occurred_at`.
- `cancelled` is emitted only when a reliable cancellation occurrence clock
  exists.
- `promise_revised` must reference the immediately preceding unsuperseded
  `promise_recorded` or `promise_revised` event for the same Order Line and
  milestone kind through `revises_promise_event_id`.
- A correction uses the same domain event kind, receives a new `event_id`,
  and references its predecessor. There is no generic `updated` event.
- Revision and supersession targets must exist in the same dataset lineage,
  target the same Order Line, and must not create a cycle.
- Events never contain exposure, outcome, eligibility, or causal verdicts.

Point-in-time consumers filter on `known_at <= decision_at`; they do not infer
availability from `occurred_at`. Construction of those snapshots belongs to
the temporal-eligibility and analysis-artifact contracts.

### `SourceObservation`

The field-level lineage record for a canonical value or event fact.

| Field | Type | Requirement |
| --- | --- | --- |
| `source_observation_id` | deterministic ID | Required |
| `ingestion_run_id` | ID | Required |
| `target_record_type`, `target_record_id`, `target_field_path` | string/ID | Required |
| `source_object_hash` | SHA-256 | Required |
| `source_locator_token` | opaque string | Required; resolves through the protected source package |
| `source_field_path` | `FieldValue<string>` | Present only when redistribution policy permits; otherwise `redacted` |
| `known_at` | `FieldValue<TemporalValue>` | Required, including an explicit non-present state |
| `origin` | enum | `observed` or `simulated` |
| `derivation` | enum | `direct`, `normalized`, or `derived` |
| `calibration` | enum | `none` or `externally_calibrated` |
| `transformation_rule_id`, `transformation_rule_version` | `FieldValue<string>` | Required for normalized or derived values |
| `evidence_refs` | list | Required when externally calibrated; otherwise empty |
| `source_value_fingerprint` | `FieldValue<string>` | Required wrapper; present only when policy permits |

These provenance axes are independent. For example, a semi-synthetic
completion date may be both `simulated` and `externally_calibrated`; an Olist
timestamp may be `observed` and `normalized`.

`source_observation_id` is deterministic from the dataset namespace, target,
source-object hash, locator token, and transformation rule; it excludes
`ingestion_run_id`. An exact re-ingestion reuses the already-published
observation and leaves its original run reference unchanged.

Raw source values are not copied into this record. A value fingerprint is
permitted only when the manifest's confidentiality and redistribution policy
allows it. The locator token must never contain a PO number, supplier key,
contractual identifier, raw JSON key, or other source value. A protected,
backend-only locator map resolves the token to the exact row/key and field path;
that map remains part of the protected source package and is not a
distributable lineage artifact.

For an `OrderLine` field, effective `known_at` is evaluated from its linked
observations and is not duplicated on the baseline record. For a direct fact,
that effective clock equals its contributing `SourceObservation.known_at`.
For a normalized or derived fact, it is no earlier than the latest `known_at`
among every contributing observation. An `OrderLineEvent.known_at` follows the
same rule over its contributing observations. If any required input has
unresolved `known_at`, the field's effective clock or the stored event clock
is also unresolved. A target clock earlier than an input emits
`LINEAGE_TIME_INCONSISTENT`; adapters may never backdate a derived fact.

### `ValidationFinding`

A stable machine-readable result from one validation rule.

| Field | Type | Requirement |
| --- | --- | --- |
| `validation_finding_id` | ID | Required |
| `ingestion_run_id` | ID | Required |
| `code`, `code_registry_version` | string | Required |
| `severity` | enum | `error`, `warning`, or `info` |
| `disposition` | enum | `reject_run`, `quarantine_record`, `invalidate_field`, or `advisory` |
| `scope` | enum | `run`, `dataset`, `record`, or `field` |
| `affected_refs` | bounded list | Record/field references, never raw values |
| `affected_count` | non-negative integer | Required |
| `rule_id`, `rule_version` | string | Required |
| `message` | string | Human explanation without restricted raw data |
| `remediation` | string | Constructive next step |

Disposition semantics:

- `reject_run`: publish no `DatasetVersion`.
- `quarantine_record`: retain lineage but exclude the record from canonical
  consumers.
- `invalidate_field`: retain the record with that field set to `invalid`.
- `advisory`: retain the value and surface the named concern.

Repeated defects may be aggregated using `affected_count` and bounded example
references. Consumers branch on stable codes and dispositions, never message
text.

## Baseline validation-code registry

The registry is closed and versioned. New codes require a schema-compatible
registry revision; adapters may not invent private codes that Core must
interpret.

| Code | Minimum disposition | Meaning |
| --- | --- | --- |
| `INPUT_HASH_MISMATCH` | `reject_run` | Input content differs from its declared fingerprint |
| `SOURCE_SCHEMA_UNSUPPORTED` | `reject_run` | No reviewed mapping exists for the observed source schema |
| `ADAPTER_CONTRACT_VIOLATION` | `reject_run` | Adapter output violates this logical contract |
| `OUTPUT_HASH_MISMATCH` | `reject_run` | Published output differs from the content manifest |
| `EVENT_ID_CONTENT_CONFLICT` | `reject_run` | One deterministic event ID resolves to different content |
| `LINEAGE_REQUIRED_MISSING` | `reject_run` | A populated canonical field lacks required lineage |
| `REQUIRED_ID_MISSING` | `quarantine_record` | A required canonical identity cannot be formed |
| `IDENTITY_COLLISION` | `quarantine_record` | Distinct source identities map to one canonical identity |
| `UNKNOWN_ORDER_LINE_REFERENCE` | `quarantine_record` | An event targets no canonical Order Line |
| `SUPERSESSION_INVALID` | `quarantine_record` | A correction target is absent, cross-line, or cyclic |
| `PROMISE_REVISION_INVALID` | `quarantine_record` | A promise revision target is absent, incompatible, or cyclic |
| `UNRESOLVED_RECORD_CONFLICT` | `quarantine_record` | Conflicting observations cannot establish one coherent record |
| `VALUE_PARSE_FAILED` | `invalidate_field` | A source token cannot be parsed as its declared type |
| `VALUE_OUT_OF_RANGE` | `invalidate_field` | A typed value violates its semantic domain |
| `UNIT_UNSUPPORTED` | `invalidate_field` | A unit has no reviewed canonical interpretation |
| `CURRENCY_INVALID` | `invalidate_field` | A monetary value lacks a valid currency |
| `TIMESTAMP_INVALID` | `invalidate_field` | A temporal token or calendar value is invalid |
| `MISSINGNESS_TOKEN_UNMAPPED` | `invalidate_field` | A source sentinel has no reviewed missingness meaning |
| `LINEAGE_TIME_INCONSISTENT` | `invalidate_field` | A target fact is dated earlier than one of its required inputs |
| `UNRESOLVED_FIELD_CONFLICT` | `invalidate_field` | Conflicting observations cannot establish one canonical field value |
| `TIMEZONE_ASSUMED` | `advisory` | A declared dataset-level timezone assumption was applied |
| `TIMEZONE_UNKNOWN` | `advisory` | A datetime has no trustworthy timezone |
| `KNOWN_AT_UNKNOWN` | `advisory` | Decision-time availability cannot be established |
| `PROMISE_HISTORY_UNVERIFIED` | `advisory` | A promise exists but its frozen-at-commitment status is unsupported |
| `MILESTONE_KIND_UNSUPPORTED` | `advisory` | A source milestone maps only to `other` or a non-supplier role |
| `SOURCE_DUPLICATE_DEDUPED` | `advisory` | Exact repeated observations were idempotently deduplicated |
| `EXTENSION_FIELD_IGNORED` | `advisory` | An adapter-specific field is preserved but unavailable to Core |
| `PROMISE_ACTUAL_EQUALITY_SUSPICIOUS` | `advisory` | Promise/actual equality is frequent enough to question source semantics |

Registry dispositions are minimums, ordered:
`advisory < invalidate_field < quarantine_record < reject_run`. A
schema-versioned rule may escalate a finding when its scope demands it, but no
adapter or runtime policy may downgrade it. Emitting a disposition below the
registry minimum is itself `ADAPTER_CONTRACT_VIOLATION` and rejects the run.

The temporal-eligibility contract decides which advisories prevent a specific
analysis. Ingestion does not convert scientific ineligibility into silent data
loss.

## Duplicate, conflict, and correction rules

1. Exact repeated observations deduplicate and emit an aggregate
   `SOURCE_DUPLICATE_DEDUPED` advisory.
2. One deterministic event ID with different content rejects the run.
3. Conflicting observations never use last-write-wins.
4. A promise conflict becomes a valid revision only when source evidence
   establishes its `known_at` and `revises_promise_event_id`; a correction
   separately requires `supersedes_event_id`.
5. Otherwise both source observations remain traceable and the target field is
   invalidated or the record quarantined according to scope.
6. Missing rows in newer extracts do not erase earlier facts.

## Adapter responsibilities

An adapter must:

1. verify source fingerprints and the reviewed source-schema version;
2. declare its identity, version, mapping assumptions, license reference, data
   classification, and redistribution policy;
3. deterministically map source keys, Order Lines, events, and missingness;
4. normalize types, timezones, units, and currencies only through versioned
   rules;
5. emit one or more `SourceObservation` records for every populated canonical
   field, enumerating every input to a multi-source derivation;
6. derive target `known_at` from all contributing observations without
   backdating;
7. declare unsupported or ambiguous semantics instead of guessing;
8. run canonical validation and publish atomically only when no finding has
   `reject_run`;
9. produce identical canonical content for identical declared inputs.

An adapter must not:

- calculate Supplier Load Snapshots, High-Load Exposure, Supplier Milestone
  Slippage, eligibility, or causal variables;
- impute values or select an analysis cohort;
- infer identities across datasets;
- silently repair contradictions or promote extension fields;
- treat a column-name resemblance as semantic proof;
- redistribute restricted raw or transformed source data.

There is no end-user generic upload adapter in Core.

## Dataset mappings

### Semi-synthetic construction

- Emits the same canonical Order Lines and events as every other source.
- Every generated fact has explicit `occurred_at` and `known_at`.
- The manifest records generator version, seed, scenario ID, parameter-set
  hash, calibration evidence, and the ground-truth artifact hash in
  `generator_metadata`.
- Provenance uses `origin = simulated`; externally calibrated parameters are
  marked independently.
- Olist microdata and identifiers never enter the generated dataset.
- Planted effects, potential outcomes, hidden confounders, and oracle policy
  values live in a separate evaluation-only ground-truth artifact keyed by
  `order_line_id`. They are prohibited from canonical fields, extensions, and
  estimator-visible inputs.

### Olist

| Canonical semantic | Olist mapping |
| --- | --- |
| Order Line identity | `order_id` + `order_item_id` |
| Order group | `order_id` |
| Supplier | `seller_id` |
| `committed.occurred_at` | `order_purchase_timestamp` |
| Original `supplier_handoff` promise | `shipping_limit_date` |
| Reached `supplier_handoff` | `order_delivered_carrier_date` |
| Material class | Normalized product category |
| Quantity | `1` per order-item row |
| Value | Item price in BRL |

The promise's `known_at` equals purchase time only under the explicit,
reviewable assumption `olist.shipping_limit_known_at_purchase.v1`. Withdrawing
that assumption sets `known_at` to `unknown`; the adapter does not substitute
another clock.

Multi-seller orders remain canonical. The later computation contract owns the
single-seller primary-analysis restriction. Cancellation/unavailable status
may be preserved in an Olist extension, but no `cancelled` event is emitted
without a reliable occurrence timestamp.

The manifest prohibits redistribution of raw or transformed Olist files and
links the required attribution/license reference.

### SCMS

- Each shipment row becomes one self-grouped Order Line.
- Supplier identity maps from the source vendor field.
- `PO Sent to Vendor Date` creates `committed` only when genuinely present.
- `Scheduled Delivery Date` maps to a promised `customer_delivery`.
- `Delivered to Client Date` maps to a reached `customer_delivery`.
- Neither field is relabelled as supplier-controlled.
- Scheduled-delivery `known_at` remains `unknown`; SCMS exposes no trustworthy
  promise-history clock.
- `N/A - From RDC` maps to `not_applicable`; `Date Not Captured` maps to
  `unknown`.
- The equality/backfill pattern emits
  `PROMISE_ACTUAL_EQUALITY_SUSPICIOUS` with counts and bounded examples.

SCMS remains publishable as a `rejection_vignette`, but it cannot supply a
canonical supplier-handoff outcome. Its manifest prohibits raw-file
redistribution while the source's license status remains inconsistent.

### Kaya platform and sample boundary

Kaya platform access and a de-identified sample will not be provided for this
effort. Core therefore defines no `kaya_sample` source kind, candidate-domain
sample role, credential path, or Kaya-specific adapter.

If access is reconsidered in a future effort, the canonical schema must be
versioned before adding new source and role enum values. A developer-authored
adapter must then provide a reviewed mapping manifest covering:

- de-identification, confidentiality, and source identity;
- Order Line, order-group, and supplier keys;
- commitment semantics;
- original promise and revision history;
- actual milestone role;
- timezone, precision, and `known_at` evidence;
- units, currencies, classifications, and field mappings.

Unproven semantics remain missing or unsupported. Any future restricted data
stays local and cannot enter external services. Risk-signal integration belongs
to the separate generic risk-signal contract and must not imply a tested Kaya
integration.

## Conformance checks

An implementation conforms only if automated contract tests demonstrate:

1. identical declared inputs produce the same semantic-payload hashes and
   `DatasetVersion` ID, reuse the first published version, and do not rewrite
   its publication metadata;
2. a changed input, adapter version, mapping assumption, source-schema
   version, canonical-schema version, or canonical semantic payload changes
   the version identity;
3. exact duplicates deduplicate while conflicting event content rejects;
4. corrections preserve the predecessor and reject broken or cyclic
   supersession;
5. promise revisions reference the immediately preceding compatible promise
   and reject broken or cyclic revision chains;
6. derived facts cannot have `known_at` earlier than any required lineage
   input, and unresolved input knowledge time propagates;
7. date-only and timezone-unknown values are never converted to invented UTC
   instants;
8. every missingness state round-trips without sentinel substitution;
9. every populated canonical field has at least one complete lineage path,
   with every input enumerated for multi-source derivations;
10. restricted raw values and business-key locators are absent from
    distributable lineage and validation messages;
11. Order Line baselines cannot be overwritten by later-known observations;
12. Olist mapping retains multi-seller lines and keeps cohort selection out of
    ingestion;
13. SCMS maps client-delivery semantics honestly and emits the named
    backfill/availability findings;
14. semi-synthetic generator metadata is complete while planted ground-truth
    values remain absent from canonical and estimator-visible artifacts;
15. extensions cannot affect Core behavior without a canonical schema change;
16. a finding cannot be emitted below its registry minimum disposition;
17. a run with any `reject_run` finding publishes no `DatasetVersion`.
