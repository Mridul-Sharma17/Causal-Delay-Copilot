# Governance & Audit

This context exclusively owns and records Manager Decisions and the immutable history needed to replay what was known, recommended, and authorized. It records other domain activity without taking ownership of upstream evidence or decisions.

## Language

**Demo Workspace**:
An anonymous isolation boundary for one browser's mutable journey, audit view, and replay. It is not an account, tenant, or authentication boundary.
_Avoid_: User Session, Account, Tenant, Authenticated Workspace

**Anonymous Demo Manager**:
The workspace-scoped actor whose explicit disposition may form a prototype Manager Decision without claiming verified organizational identity or real-world execution authority.
_Avoid_: Authenticated Manager, User Account, Organizational Approver

**Manager Decision**:
The manager's explicit recorded disposition of an Action Recommendation or Drafted Artefact: approve, edit, reject, or investigate further. An authorizing disposition references Advice Currentness proved for that exact authorization attempt. It records authorization intent, not proof of execution.
_Avoid_: User Action, Recommendation Outcome, Execution

**Trade-off Selection**:
The manager's recorded choice of one of the exact two candidates from a specific unchanged Decision Support Evaluation whose current result requires manager choice. A candidate may be a Pareto-frontier option, a value-sensitive option presented without a Pareto-optimality claim, an explicitly disclosed robust safety alternative, or the governed monitoring baseline. The selection allows Decision Support to form one Action Recommendation but does not approve, authorize, or execute it.
_Avoid_: Manager Decision, Approval, Recommendation

**Audit Event**:
An append-only, timestamped record of one material workflow occurrence, identifying its actor and referenced object versions so the experience can be replayed. It records domain activity without owning the underlying objects.
_Avoid_: Log Entry, History Row, Mutable Audit Record

**Decision Brief Snapshot**:
An immutable Governance & Audit record of the exact manager-visible decision brief for one presentation, including its allow-listed evidence, analysis, recommendation, artefact, explicit unavailable states, and presentation contract. It proves delivery or rendering only when the corresponding Audit Event exists; it never proves that the manager read it or changes upstream objects.
_Avoid_: Current Brief, Live Recommendation, Screenshot, UI State

**Replay**:
A read-only reconstruction of one Investigation Request's historical manager-visible state at an explicit Audit Event cutoff, using the immutable versions referenced by its events and snapshots. It performs no new analysis, currentness check, selection, or decision; unresolved or incompatible references yield an unavailable result rather than current-state substitution.
_Avoid_: Re-run, Refresh, Playback
