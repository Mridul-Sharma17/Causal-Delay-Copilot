# Causal Evidence

This context defines the causal question and produces reproducible analyses, diagnostics, and calibrated evidence verdicts. It evaluates evidence without selecting or authorizing an action.

## Language

**Causal Question**:
A versioned statement of the eligible population, exposure contrast, outcome, estimand, adjustment set, and design restrictions that an Analysis Run executes.
_Avoid_: Model Definition, Analysis Configuration, Query

**High-Load Exposure**:
The causal exposure assigned when an eligible Order Line's Supplier Load Snapshot exceeds its supplier-specific prior-history threshold at commitment. It is a state under study, not an intervention or proof that congestion caused slippage.
_Avoid_: Treatment, Congestion Flag, Capacity Stress Index

**Supplier Milestone Slippage**:
The signed difference in days between an Order Line's actual supplier-controlled completion or handoff and its original Promised Milestone. Positive is late, zero is on time, and negative is early.
_Avoid_: Delivery Delay, Project Delay, Lateness

**Analysis Run**:
A uniquely identified, reproducible execution of one causal question over one versioned input snapshot and configuration. Its completed outputs never change; repeating or modifying it creates a new Analysis Run.
_Avoid_: Model Run, Job, Session

**Analysis Artifact Bundle**:
The immutable, atomically sealed collection of hash-bound inputs, runtime and model recipes, outputs, diagnostics, and verification evidence for exactly one Analysis Run. It is the reproducibility boundary consumed through a verified read model, not a mutable folder or fitted-model package.
_Avoid_: Results Folder, Cache Entry, Model Bundle

**Validation Attestation**:
An immutable release-validation statement bound to one exact Analysis Artifact Bundle hash and validation-policy version. It may designate that bundle as a Validated Reference without changing the Analysis Run or claiming that an ordinary fresh run received the same review.
_Avoid_: Validation Flag, Approved Run, Freshness

**Diagnostic Result**:
The immutable result of one named validity check within an Analysis Run. It records the observed measure, evaluation rule, status, and explanation, but cannot independently determine the Evidence Verdict.
_Avoid_: Test Result, Pass/Fail, Verdict

**Evidence Verdict**:
The calibrated, explicitly scoped conclusion produced from an Analysis Run's effect estimate and Diagnostic Results. Its scope is Population or Subject, and its four states are Supported Under Stated Assumptions, Tentative, Association Only, and Insufficient. A Subject verdict applies population evidence to one current Order Line, can never be stronger than its Population verdict, and does not change that Population verdict. An Evidence Verdict governs permissible causal language and downstream recommendation strength; it is neither probability nor proof. Robustness Grade is a separate diagnostic classification and never substitutes for the verdict.
_Avoid_: Confidence Score, Causal Proof, Recommendation

**Robustness Grade**:
A benchmark-relative diagnostic classification of how the primary estimate responds to plausible omitted confounding represented by reviewed observed-covariate groups. Its states are Strong, Moderate, Weak, and Unavailable. It informs but does not replace the Evidence Verdict; overlap, refuters, repeat stability, and leave-one-supplier-out checks remain separate diagnostics.
_Avoid_: Confidence Level, Evidence Verdict, Proof Strength
