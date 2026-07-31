# Governance & Audit

This context exclusively owns and records Manager Decisions and the immutable history needed to replay what was known, recommended, and authorized. It records other domain activity without taking ownership of upstream evidence or decisions.

## Language

**Manager Decision**:
The manager's explicit recorded disposition of an Action Recommendation or Drafted Artefact: approve, edit, reject, or investigate further. An authorizing disposition references Advice Currentness proved for that exact authorization attempt. It records authorization intent, not proof of execution.
_Avoid_: User Action, Recommendation Outcome, Execution

**Trade-off Selection**:
The manager's recorded choice of one of the exact two candidates from a specific unchanged Decision Support Evaluation whose current result requires manager choice. A candidate may be a Pareto-frontier option, a value-sensitive option presented without a Pareto-optimality claim, an explicitly disclosed robust safety alternative, or the governed monitoring baseline. The selection allows Decision Support to form one Action Recommendation but does not approve, authorize, or execute it.
_Avoid_: Manager Decision, Approval, Recommendation

**Audit Event**:
An append-only, timestamped record of one material workflow occurrence, identifying its actor and referenced object versions so the experience can be replayed. It records domain activity without owning the underlying objects.
_Avoid_: Log Entry, History Row, Mutable Audit Record
