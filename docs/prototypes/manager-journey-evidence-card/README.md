# Throwaway manager-journey prototype

This prototype answers issue #9: what responsive interaction model should carry a manager from a reactive risk signal or proactive pre-award check through eligibility, verdict-first evidence, action comparison, drafting, authorization, reruns, and audit replay?

There is no product route in the checkout yet, so this uses the prototype skill's new-page shape: one static route with three structurally and visually different variants. It is not production code and has no persistence or backend.

## Run

From the repository root, run:

    node docs/prototypes/manager-journey-evidence-card/serve.cjs

Open http://localhost:4173/?variant=B.

Selected direction: **Variant B — Decision brief**. It is the canonical interaction model; A and C remain available as comparison references.

- ?variant=A — Signal desk
- ?variant=B — Decision brief
- ?variant=C — Command ledger

Use the bottom switcher or the left/right arrow keys to compare variants. The trigger buttons, stage navigation, progressive evidence disclosure, action comparison, draft authorization, rerun, and audit replay controls are intentionally lightweight interaction probes.

## Prototype boundary

- Mock state lives in memory and resets on reload.
- The main case uses the supported-evidence path so the action lane can be inspected; the abstention guardrail is shown as a separate read-only example.
- No action is sent, no recommendation is executed, and no causal claim is made about an intervention benefit.
- Once the human decision is known, the chosen interaction model should be rewritten into the real React + Carbon implementation and the losing variants removed.
