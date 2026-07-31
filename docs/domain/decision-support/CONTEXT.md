# Decision Support

This context evaluates governed intervention options and produces constraint-aware action recommendations from evidence. It advises the manager without authorizing or executing an action.

## Language

**Intervention Option**:
A governed action type that could alter future exposure or its consequences, with defined eligibility rules and assumptions. It exists independently of a particular case and makes no benefit claim by itself.
_Avoid_: Mitigation, Recommendation, Next-Best Action

**Action Recommendation**:
A case-specific proposal selecting an eligible Intervention Option using the Evidence Verdict, operational constraints, and declared trade-off assumptions. It advises but does not authorize or execute.
_Avoid_: Decision, Command, Intervention

**Recommendation Candidate**:
A case-specific Intervention Option projection presented for comparison within one Decision Support Evaluation. It may represent a Pareto-frontier option, a value-sensitive option presented without a Pareto-optimality claim, an explicitly disclosed robust safety alternative, or the governed monitoring baseline. It has no authority and is not an Action Recommendation.
_Avoid_: Recommendation, Selected Action, Approved Option

**Advice Currentness**:
A point-in-time proof that a Decision Support Evaluation remains authoritative, its governed dependencies remain effective, and its consumed operational facts remain within their declared validity horizons. An authorization-bound proof permits Governance & Audit to record its separate Manager Decision; the proof is not that decision and is not a permanent property of an evaluation or Action Recommendation.
_Avoid_: Timeless Validity, Still Good, Recommendation Status

**Operational Validity Horizon**:
The explicit inclusive boundary through which an operational fact or assumption may support current advice, or an explicit declaration that it does not expire. Absence never means no expiry.
_Avoid_: Freshness Guess, Default Expiry, Observation Time

**Decision Support Evaluation**:
One immutable application of exact Decision Support policy and library versions after a verified Subject Verdict permits Decision Support. An active-driver evaluation additionally uses a Case Constraint Snapshot and declared assumptions; an inactive-driver evaluation stops before option evaluation.
_Avoid_: Recommendation Run, Ranking, Decision

**Subject Driver State**:
The exact upstream `high_load_exposure` or preview-only `provisional_high_load_preview` boolean for one subject at its causal cutoff. It governs option applicability without attributing an outcome to the driver or to one Order Line.
_Avoid_: Root Cause, Delay Cause, Manager Exposure Override

**Case Constraint Snapshot**:
The immutable point-in-time set of typed operational facts and attestations used to evaluate Intervention Options for one subject at an explicit operational `constraints_as_of` cutoff. That cutoff may be later than the subject's causal `decision_at`; it never retimes causal evidence or makes an option eligible by itself.
_Avoid_: Form State, User Inputs, Constraint List

**Release-Timing Preview**:
An immutable operational what-if for a later candidate release or commitment of the exact proactive proposal being evaluated. It is constraint evidence only and never replaces Subject Driver State or creates a canonical Order Line or High-Load Exposure.
_Avoid_: Revised Subject Profile, New Causal Cutoff, Canonical Exposure

**Driver-Action Link**:
A versioned, externally reviewed link between a supported driver and one governed Intervention Option. It is either an `ACTION_MECHANISM` with a plausible mechanism or a non-mechanistic `MONITORING_BASELINE`; neither estimates an action effect.
_Avoid_: Action Effect, Recommendation Evidence

**Monitoring Escalation Trigger**:
An immutable, versioned, externally reviewed atomic predicate for one exact `ACCEPT_AND_MONITOR` option version and its declared trigger-mode applicability. A match requests manager review but never authorizes or executes an action.
_Avoid_: Automatic Escalation, Alert Rule, Action Trigger

**Advisory Rubric**:
A versioned, externally reviewed rule set that derives one Decision Support comparison ordinal from declared typed case evidence. Without an approved applicable rubric and sufficient evidence, its result is `UNKNOWN`.
_Avoid_: Manager Rating, Free-Text Score, Hidden Weight

**Schedule Protection**:
The assumption-based `PROJECT_DELAY_DAYS` protected by a schedule-affecting Intervention Option after any required critical-path translation. Recovered supplier-milestone days are a separate audit measure, not Schedule Protection.
_Avoid_: Recovered Supplier Days, Supplier-Day Benefit
