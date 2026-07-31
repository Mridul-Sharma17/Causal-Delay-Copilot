# Gemini artifact drafting logic prototype

This is a throwaway logic prototype for Wayfinder issue #11.

It answers one question: for an already-approved action recommendation, does a
state model with sanitized evidence, one Gemini attempt plus one retry after a
deterministic check, and a deterministic fallback keep email drafting
conversational without allowing model output to become evidence or
authorization?

The prototype does not call Gemini, persist data, or represent production code.
It simulates safe, unsafe, malformed, timeout, and invalid-context outcomes so
the state transitions can be driven by hand.

Run it from the repository root with:

```text
node docs/prototypes/gemini-artifact-drafting-logic/prototype.cjs
```

Choose a scenario, then drive the flow with the displayed shortcuts. The
important boundary is that Gemini supplies only connective prose; deterministic
slots supply facts and the manager remains the authorizer.
