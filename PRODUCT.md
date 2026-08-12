# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a construction project manager or supply-chain manager who has received an upstream warning that a supplier commitment may put a project milestone at risk. They need to decide whether the warning is meaningful, what evidence supports it, and what response should be prepared.

Operations and supply-chain analysts are secondary users who inspect evidence, lineage, and decision history.

## Product Purpose

Causal Delay Copilot receives an Amber-shaped supplier-risk signal, investigates whether supplier congestion is supported as a driver of supplier-controlled milestone slippage, and turns the result into a plain-language Decision Brief and a governed next step.

The product succeeds when a manager can understand the case quickly, see why the Copilot reached its verdict, choose a permitted response, review an unsent email draft, and retain an exact replayable record of the decision. The manager remains the final decision-maker.

## Positioning

Causal Delay Copilot is a complementary decision layer over predictive supply-chain systems such as Amber. Amber identifies where delay might happen; Causal Delay Copilot investigates whether the warning is supported by causal evidence and helps the manager act without treating prediction as proof.

Its differentiator is the combination of formal evidence boundaries, explicit uncertainty and abstention, governed decision support, immutable draft history, and human-controlled action—not another risk dashboard or an Amber replacement.

## Operating Context

- The manager enters through a web sign-in experience and lands in an Attention Inbox of Amber-style cases requiring attention.
- The flagship workflow is a switchgear supplier-handoff case: Amber flags a possible delay, the manager investigates the evidence, selects a recovery-plan response, reviews an email draft, and opens Gmail to send it manually.
- The web product is the primary surface. Telegram is a planned secondary operating surface that should use the same cases, investigation results, decision history, and action boundaries.
- The judge-facing interface presents realistic operational cases. The report and video disclose that the current upstream signal and data are locally generated or semi-synthetic because no live Amber feed or Kaya sample-data dependency is available for this prototype.

## Capabilities and Constraints

- Reactive risk-signal intake and proactive pre-award proposal paths feed a shared causal investigation workflow.
- Canonical lineage, point-in-time clocks, eligibility checks, causal analysis, Evidence Verdicts, Decision Brief Snapshots, diagnostics, sensitivities, and historical replay are existing product capabilities and must remain fail-closed.
- The manager-facing experience must prioritize an answer, the reason for the verdict, and the next permitted step. Technical provenance and methodology are supporting evidence, not the default page narrative.
- The primary demo requires a dedicated deterministic governed scenario that can reach an actionable recovery-plan recommendation and DraftContext. The existing abstention/read-only hero baseline remains available as the safety case when evidence or authority is insufficient.
- Drafts are editable, immutable successors are recorded, and manager approval records intent. The app does not send email or execute operational actions directly.
- The final handoff uses a Gmail compose link with recipient, subject, and body prefilled. Gmail sends from the account active in the browser; the front-end demo account selector is not production authentication.
- Google and Microsoft sign-in, account selection, and sign-up are front-end-only demo states for the video until a real identity provider is added.
- The visible product must not fabricate causal evidence, a live Amber integration, a sent message, or an operational execution result. Unavailable, abstained, read-only, and review-required states remain explicit.
- UI work follows `DESIGN.md` as the design-system authority and uses the `impeccable` skill. The current report-like interface is being replaced with a task-first operating experience.

## Brand Commitments

- Product name: Causal Delay Copilot.
- The product should feel like a credible operational extension to Amber, not a research notebook or a static report.
- The manager-facing voice is direct, calm, evidence-led, and action-oriented. It must never imply that a predictive score is itself causal proof.
- Amber is an upstream system concept and integration boundary. Public Kaya positioning must not be expanded into claims of live API access or schema compatibility that the prototype does not possess.

## Evidence on Hand

- `docs/causal_delay_copilot_stage2_strategy.md` records the product strategy, Amber complement positioning, flagship causal question, demo story, and prototype constraints.
- `backend/app/data/predictive_risk_signal_fixture.json` contains the calibrated reactive risk-signal fixture used by the current core path.
- `backend/app/data/semi_synthetic_hero.json` contains the canonical semi-synthetic construction records for the switchgear hero scenario.
- `backend/app/data/risk_signal_fixtures.json` contains reactive conformance and failure cases for the risk-signal boundary.
- `backend/app/data/proactive_proposal_fixtures.json` contains the proactive proposal path.
- `frontend/src/App.tsx` and `frontend/src/api.ts` contain the existing Decision Brief, Decision Support, DraftContext, draft-edit, disposition, manager-decision, and replay seams.
- `docs/prototypes/manager-journey-evidence-card/` contains an earlier manager-journey prototype with the intended evidence-to-draft sequence.
- No live Amber API, production identity provider, Gmail API, or Telegram bot is currently part of the prototype. These are integration boundaries or future implementation work, not evidence to invent.

## Product Principles

- Start with the manager's task: alert, investigate, decide, act.
- Put the answer and next step before methodology; make proof available exactly where trust requires it.
- Keep prediction, causal evidence, recommendation, authorization, and execution as separate states.
- Fail closed and make abstention useful: explain what is missing and what the manager can do next.
- Use one governed decision model across the web and messaging surfaces.

## Accessibility & Inclusion

The web experience must remain keyboard-operable, semantically structured, responsive on phone and desktop, readable at narrow widths, and explicit about loading, unavailable, abstained, read-only, error, and success states. Touch interactions should honor the Carbon-oriented 48px minimum target guidance in `DESIGN.md`.
