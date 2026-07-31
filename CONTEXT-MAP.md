# Context Map

## Contexts

- [**Intake & Lineage**](docs/domain/intake-lineage/CONTEXT.md) — accepts external risk signals, preserves source order facts, and owns the provenance of source and derived records.
- [**Causal Evidence**](docs/domain/causal-evidence/CONTEXT.md) — defines the causal question and produces reproducible analyses, diagnostics, and calibrated evidence verdicts.
- [**Decision Support**](docs/domain/decision-support/CONTEXT.md) — evaluates governed intervention options and produces constraint-aware action recommendations from evidence.
- [**Artefact Composition**](docs/domain/artefact-composition/CONTEXT.md) — renders checked draft artefacts from sanitized structured inputs without authority to invent facts or actions.
- [**Governance & Audit**](docs/domain/governance-audit/CONTEXT.md) — records manager decisions and the immutable history needed to replay what was known, recommended, and authorized.

Context glossaries live under `docs/domain/<context>/CONTEXT.md`.

## Relationships

- **Intake & Lineage → Causal Evidence**: supplies provenance-bearing order facts and point-in-time snapshots; it does not supply causal conclusions.
- **Intake & Lineage → Decision Support**: supplies reviewed source-mapped Monitoring Observations with canonical subject, typed value, source first-availability time, and lineage; Decision Support evaluates the governed trigger but does not remap raw source fields.
- **Causal Evidence → Decision Support**: supplies an evidence verdict and its supporting effect and diagnostic results; it does not choose an action.
- **Decision Support → Artefact Composition**: supplies one governed recommendation and an allow-listed evidence object; composition may change presentation, not substance.
- **Decision Support → Governance & Audit**: supplies the recommendation and evidence snapshot presented to the manager.
- **Governance & Audit → Decision Support**: supplies a Trade-off Selection bound to an unchanged evaluation; selection may form one recommendation but never authorizes it.
- **Governance & Audit → Decision Support**: supplies an immutable manager authorization attempt bound to one exact Action Recommendation and its accepted selection claim when applicable; the attempt is not itself an authorizing Manager Decision.
- **Decision Support → Governance & Audit**: returns the operation-bound authorization-currentness result for that exact attempt; Governance & Audit alone records the Manager Decision, and neither context claims action execution.
- **Artefact Composition → Governance & Audit**: supplies the exact drafted and edited artefact versions shown during authorization.
- **All contexts → Governance & Audit**: supply references to material occurrences for append-only recording without transferring ownership of the underlying domain objects.
