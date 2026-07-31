# Intake & Lineage

This context accepts external triggers, preserves source order facts, and owns the provenance of source and derived records. It supplies point-in-time facts to downstream contexts without making causal or decision claims.

## Language

**Risk Signal**:
A point-in-time indication from an upstream predictor that an Order Line may miss a future milestone. It has its own stable source identity and source Order Line reference; the adapter must resolve that reference deterministically to exactly one canonical Order Line in one Dataset Version. Supplier or equipment context carried by the signal is advisory and cross-checked, never an alternative identity path. Missing, ambiguous, or conflicting reactive resolution is rejected before an Investigation Request is created. Its `generated_at`, `known_at`, and UTC `received_at` clocks respectively record source production, first Copilot availability, and adapter receipt; none may substitute for another. A Risk Signal may trigger an investigation and explain its own prediction, but its score, label, threshold, attribution, and duplicated business facts never become estimator inputs, weights, cohort selectors, or causal evidence. A Risk Signal starts a reactive investigation but is neither causal evidence nor a decision; proactive checks do not require one.
_Avoid_: Risk Event, Cause, Evidence Verdict

**Investigation Request**:
A normalized, point-in-time request to run the shared causal investigation for exactly one subject. It freezes an observation cutoff when accepted. A reactive request combines an untrusted Risk Signal with a canonical Order Line reference while retaining the canonical commitment occurrence as its causal subject cutoff; signal timing never retimes exposure or admits post-treatment covariates. Reactive business facts are reloaded from the frozen canonical Dataset Version, and duplicated signal context is cross-checked only. A proactive request carries a frozen proposed subject and remains preview-only; its typed, lineage-bearing facts may describe only that preview subject when known by its decision time. Historical comparison facts always come from the frozen canonical Dataset Version. The two ingress contracts retain their distinct provenance and normalize into one downstream request without creating separate analysis paths. Missing or contradictory required clocks fail closed, and receipt time is never used as a substitute.
_Avoid_: Risk Signal when referring to both trigger modes, Analysis Run

**Proactive Proposal**:
An immutable, revisioned description of a possible supplier commitment evaluated before award or release. Its stable source-system proposal identity and revision freeze the decision time, proposed supplier, original promise, target milestone, and required then-known covariates. It has no canonical Order Line identity and produces preview-only derived facts. A changed supplier, promise, covariate, or decision time creates a new revision and Investigation Request; eventual commitment requires fresh canonical ingestion and computation rather than promotion of the preview.
_Avoid_: Order Line, Commitment, Risk Signal

**Predictive Stub**:
The deliberately ordinary, versioned reactive-trigger model that estimates the probability that the configured original supplier milestone will be missed. It uses only point-in-time inputs available at commitment, is trained once on a versioned historical cohort, and applies a fixed versioned alert threshold without online or case-specific tuning. It may include load-at-placement and a planted predictive correlate for baseline comparison, but excludes later progress, promise revisions, escalation, and outcomes. It does not run for proactive checks and its prediction is never causal evidence.
_Avoid_: Causal Engine, Driver Model, Evidence Verdict

**Predictive Attribution**:
A versioned SHAP `PermutationExplainer` explanation of the Predictive Stub's final calibrated positive-class probability. It records the frozen background-cohort selector and hash, subject feature values and missingness, base probability, every signed feature contribution, reconstructed probability, and additivity residual. Evaluation may aggregate mean absolute contributions over a frozen cohort; presentation may collapse all but the five largest local contributions into an "other features" total. It is confined to prediction provenance and evaluation/demo comparison, carries the label "predictive attribution - not causal evidence," and never appears as causal support on the operational evidence card.
_Avoid_: Driver Evidence, Feature Effect, Causal Contribution

**Order Line**:
The atomic supplier commitment used as the unit of analysis. It normally maps to one purchase-order line; source lines sharing an indivisible production slot are represented as one Order Line.
_Avoid_: Order, PO, Item, Fabrication Package when referring to the normalized unit

**Order Line Event**:
An immutable, time-qualified fact about an Order Line's commitment, promised milestone, reached milestone, or cancellation. Corrections supersede earlier events without erasing them.
_Avoid_: Order Update, Mutable Status, History Row

**Source Observation**:
The field-level lineage link between a canonical fact and the exact source location, mapping rule, and provenance by which it was obtained. It preserves what was observed without treating a transformation or simulation as a source fact.
_Avoid_: Raw Record, Audit Event, Citation

**Dataset Version**:
An immutable, content-addressed publication of canonical Order Lines, Order Line Events, lineage, and validation results produced from declared source inputs and mapping rules.
_Avoid_: Dataset, Latest Data, Import

**Supplier Load Snapshot**:
A point-in-time record of a supplier's observable concurrent open Order Lines at the subject Order Line's commitment time, calculated solely from information then available. It measures observed load, not capacity, congestion, or exposure.
_Avoid_: Backlog, Supplier Capacity, Congestion

**Promised Milestone**:
The original supplier-controlled completion or handoff commitment recorded when an Order Line is committed. Later revisions are preserved separately and never replace it when measuring causal slippage.
_Avoid_: Delivery Date, Due Date, Current Promise
