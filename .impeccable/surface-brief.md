# Surface brief: Causal workbench

<!-- impeccable:surface-brief 1 -->

## Approved direction

The approved composition is the evidence workbench (Option 1): a compact Attention Inbox on the left, a focused case workspace in the center, and a right-side Action Brief that connects the verdict to the manager's next action. The first viewport must answer, in order: what needs attention, why it matters, and what the manager can do now.

The workbench is an operational surface, not a report. The Carbon system in `DESIGN.md` remains authoritative: IBM Plex Sans, white and cool-gray layers, charcoal text, IBM Blue as the single accent, hairline borders, and flat geometry. The generated comps are references for composition only; all core copy, controls, states, and responsive behavior remain semantic HTML/CSS.

Approved north-star comp: `.impeccable/mocks/causal-workbench-option-1.png`.

## Direction contract

- Keep the selected case visually dominant without relying on a colored border thicker than 1px.
- Make the evidence chain the primary organizing element: Signal, Eligibility, Causal analysis, Verdict.
- Keep the right rail action-first and visibly distinguish recommendation, editability, and authorization.
- Use progressive disclosure for technical lineage, replay, diagnostics, and recovery states.
- Preserve truthful API-backed loading, unavailable, abstained, read-only, and error states.
- Make the hero journey keyboard-operable and usable at narrow widths.

## Fidelity inventory

| Visible ingredient | Implementation medium |
| --- | --- |
| Product header, inbox, tabs, status marks, buttons | Semantic HTML/CSS with existing Carbon icon components |
| Evidence chain and timeline cues | Semantic HTML/CSS; no decorative chart raster |
| Decision brief and email draft | Semantic HTML form controls and API-backed state |
| Technical evidence and audit records | Existing typed React components behind progressive disclosure |
| Illustrative visual texture | Omitted; the operational interface is the visual driver |
