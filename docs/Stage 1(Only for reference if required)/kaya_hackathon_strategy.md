# Kaya AI India Hackathon 2026 — Final Strategy Reference

**Deadline (Stage 1):** 11 Jul 2026, 9:15am GMT+5:30
**Track:** Track 2 — Supply Chain
**Team size needed:** 2–4 (all members must be named with college affiliation in the submission)

This is the single reference document for this submission. It combines the strongest parts of four independently-generated strategies, discards the weak parts, and states clearly which facts have been verified against live sources vs. which numbers still need to be checked before they go in the proposal or video.

---

## 1. The one-line pitch

**"Kaya's platform tells you a delay is coming. We tell you why — and what to do about it."**

Most AI-for-construction tools (including, per verified research below, Kaya's own platform) are predictive/correlational: they flag risk based on patterns. We're building a **causal delay-diagnosis and intervention engine**: instead of just forecasting *that* a shipment will be late, it identifies *which specific factor caused the delay* (with an estimated effect size), and an agent turns that into one concrete recommended action.

This is not a general "AI supply chain platform." It is one narrow, well-evidenced causal claim, demoed end-to-end, wrapped in an agent that acts on it.

---

## 2. Why Track 2 (Supply Chain), not Procurement or Open Innovation

The brief's own framing of Track 2 is: *"Nobody has good answers [about delays] and delays cascade into missed schedules and blown budgets... What would it look like if construction supply chains finally had a brain?"* This idea answers that question directly — not with a bigger dashboard, but with causal reasoning the dashboard can't do. Track 3 (Procurement) was considered (see Section 9, "ideas we didn't pick") but the causal-delay angle fits Supply Chain more precisely.

---

## 3. Verified facts about Kaya AI — this is your competitive intelligence, and it's real

I independently searched and confirmed the following. These are safe to state in your proposal/video because they're publicly reported, not invented:

- **Kaya AI's own product is explicitly positioned as predictive, not causal-explanatory.** Multiple sources, including Kaya's own press materials, describe it as "the predictive supply-chain intelligence platform for mission-critical construction." *(Sources: PRNewswire, Dec 11 2025 release; usekaya.ai)*
- **Kaya's AI assistant is called "Jarvis."** It centralizes vendor communication, automates ordering, and surfaces delay risk in real time (e.g., alerting via text when a lead time changes). It is explicitly a correlational/pattern-surfacing assistant — it tells you *that* risk exists, not *why* in a causal sense. *(Sources: ENR, "Kaya Brings AI to Construction Supply Chains, Procurement"; Bluebeam/BUILT interview with co-founder Nicholas Selz, Dec 2025)*
- **Kaya's new CTO is Mukesh Jain**, who previously built and led Amazon's **Rufus** shopping assistant (a custom LLM using retrieval-augmented generation, reported to have driven $12B+ in commercial impact) and before that led Amazon's Product Graph. He joined Kaya in December 2025 to lead development of **"Amber,"** a domain-trained AI "knowledge worker" that unifies drawings, specs, submittals, RFIs, supplier quotes, schedules, and lead-time data into a single project graph. *(Source: PRNewswire, "Amazon's Rufus Architect Leaves to Build AI for a Trillion-Dollar Industry: Construction," Dec 11 2025)*
- **Kaya reports reducing procurement management time by ~80% and improving lead-time accuracy by ~90%** in customer deployments (e.g., with Suffolk Construction). *(Source: PRNewswire launch release, Jan 2025; ENR)*

**What this means for your pitch:** Amber and Jarvis are built by a team with serious applied-ML pedigree (Rufus is a real, technically respected system). Don't imply your team is more technically sophisticated than theirs — you're not, and claiming that will read as naive to judges who built Rufus-scale systems. Instead, position your idea as filling a **specific, named gap**: prediction and automation are covered; causal explanation and evidence-backed intervention are not. That's a precise, defensible claim, not a boast.

**Do not say "we'll beat Kaya" anywhere in the submission.** Frame it as the layer that sits on top of what they've already built. The judges are the Kaya team — this framing makes them read it as a roadmap idea, not a threat.

---

## 4. The technical core — verified research grounding

The central technique is **causal machine learning (CML) applied to delay diagnosis**, using Double Machine Learning (DML) / Generalized Random Forests (GRF) — the exact technique stack from your ReCAP/Inter-IIT work (EconML, LassoCV, LogisticRegressionCV for confounder identification).

I verified the supporting paper LLM 4 referenced:

- **"What if? Causal Machine Learning in Supply Chain Risk Management"** by Mateusz Wyrembek, George Baryannis, and Alexandra Brintrup (arXiv:2408.13556, 2024; extended journal version in *International Journal of Production Research*, 2025). This is a real paper. Its actual finding, confirmed from the paper text: in a maritime engineering supply chain case study (UK, 2015–2022 order data, three warehouses, 26% of suppliers shared across warehouses), **causal inference found an average treatment effect (ATE) of ~17 days additional delay when a supplier serves multiple warehouses**, compared to dedicated single-buyer suppliers. The paper explicitly argues for causal ML over purely correlational/predictive ML for exactly this reason — this is your strongest citable precedent, and it's real.

You can safely cite this paper by name and author in your proposal. Use it as **precedent for the technique**, not as a source of numbers about construction specifically — it's a maritime/logistics case study, not construction, so don't imply the 17-day figure applies to your (synthetic) construction dataset. Say something like: *"Recent work (Wyrembek et al., 2024) has shown causal ML can isolate specific, actionable drivers of supply chain delay in logistics settings — we apply the same class of technique to construction procurement and scheduling data."*

**One important caution:** one of the four draft strategies (not used in this final plan) cited a Microsoft paper as *"GraphRAG: Unsupervised Learning of Graph Representations for Rich Text Documents (2024)."* I checked — that title is wrong. The real paper is Edge et al., **"From Local to Global: A GraphRAG Approach to Query-Focused Summarization"** (Microsoft Research, 2024). This plan doesn't use GraphRAG as a core component, so it's not an issue here — but it's a reminder: **verify every citation you put in the proposal before submitting.** A wrong paper title in front of judges who include an ex-Amazon LLM architect is a real credibility risk, not a minor slip.

---

## 5. Verified industry stats — safe to use in the proposal/deck

From McKinsey Global Institute research (confirmed via multiple independent secondary sources reporting the same McKinsey figures, e.g. Autodesk's construction statistics compilation):

- Large capital projects typically run **~20% behind schedule** and up to **~80% over budget**.
- **98% of megaprojects** experience delays or cost overruns.
- **77% of megaprojects** are at least 40% behind schedule.

Use these as your opening hook stat (attribute to "McKinsey Global Institute research"). Don't use the "37% longer than planned" or "North America 98%" framing from the earlier drafts — I couldn't independently confirm that specific phrasing, and the McKinsey figures above are the well-sourced version of the same point.

---

## 6. The idea, scoped for a buildable overnight demo

This is where LLM 3's discipline matters more than LLM 4's ambition. Do **not** try to build a general "causal platform." Pick **one** narrow, well-defined causal question and demo it end-to-end. Everything else in the proposal should support that one demo, not compete with it.

**Recommended scope for the demo:**

- **One causal question:** e.g., "Does relying on a supplier who also serves other active projects/warehouses causally increase delivery delay, controlling for material type, order size, and season?" (directly modeled on the verified Wyrembek et al. precedent, adapted to a construction-flavored synthetic dataset).
- **One synthetic dataset**, construction-flavored: vendor, material/SKU, order quantity, promised lead time, actual delivery date, whether the vendor is shared across multiple active projects, season/weather exposure, and a few deliberately-injected confounders (e.g., larger orders both take longer *and* tend to go to specific vendors — a classic confounding structure DML is built to handle).
- **One causal engine:** DML or GRF (EconML) estimating the average treatment effect of "shared vendor" on delay days, with a policy tree or simple ranking showing which intervention (switch vendor / expedite / dual-source) has the best estimated effect for a given order profile.
- **One thin agent layer** (2–3 node LangGraph flow is enough — do not build LLM 1's five-pillar system):
  1. **Monitor/Trigger node** — flags an order at risk.
  2. **Causal Explain node** — runs the causal query, returns the top driver(s) with an estimated effect size.
  3. **Action node** — drafts one concrete artifact per top driver: an expedite email, a reroute/alternate-vendor suggestion, or a PM escalation note.
- **One visual** — a causal graph (nodes = vendors/materials/risk factors, edges = estimated effect size in days). This is your single best slide and your single best video moment.

**Explicitly do not build tonight:** real document parsing, a real WhatsApp/voice intake layer, a production RAG pipeline, GraphRAG, conformal prediction wrappers, or a self-improving RLHF/DPO loop. These are all legitimate ideas from the discarded drafts, but building any of them tonight risks turning this into LLM 1's unfocused kitchen-sink pitch. If you want to gesture at future scope, put it on the "what's next" slide as a roadmap bullet, not as a claimed current capability.

---

## 7. Judging-criteria mapping — what this idea hits and how to say it

The hackathon lists five criteria. Here's how this plan addresses each one directly — use this section to sanity-check every slide and every paragraph of the proposal against.

**Problem Relevance & Industry Fit**
Open with the McKinsey stats (Section 5) to establish the problem is real and large, then narrow immediately to the specific mechanism: teams don't just need to know a delay is coming, they need to know *why*, because the "why" is what tells them what action actually helps. This is explicitly what Track 2's brief description asks for ("nobody has good answers... what would it look like if supply chains finally had a brain").

**Technical Feasibility & Innovation**
DML/GRF-based causal effect estimation is a real, established technique (not invented for this pitch — you've used it before in ReCAP), applied to a domain-appropriate synthetic dataset. Name the actual mechanism (average treatment effect estimation via Double Machine Learning) rather than saying "AI." Cite Wyrembek et al. (2024) as precedent for the technique class. The thin 3-node agent layer keeps the "agentic" claim honest and demoable rather than aspirational.

**Impact & Scalability**
The causal engine is dataset-agnostic — the same DML pipeline generalizes to other delay drivers (weather exposure, single-sourcing, seasonal ordering patterns) without rearchitecting, and scales across projects the way Kaya's own project graph already does. Frame it as a layer that could sit on top of an existing project graph like Amber, not a replacement for it.

**Clarity & Quality of Submission**
Build the video and deck around **one concrete before/after scenario** (see Section 8), not a feature tour. A non-technical judge should be able to follow: risk flagged → causal graph lights up the real driver → recommended action → one click to send. That's a ~90-second story that needs zero ML background to follow.

**Originality & Creativity**
The differentiating sentence — *"Most AI in this space tells you a delay is coming. We tell you why, and what to do about it"* — is your headline. It works precisely because it's an accurate, non-hostile description of a real, verified gap in the judges' own product (Section 3), not a generic claim. Say it near the top of the written proposal and again, close to verbatim, in the video.

---

## 8. Demo storyline for the 2-minute video

1. **Hook (0:00–0:15):** McKinsey stat — large projects run ~20% behind schedule, 98% of megaprojects see delays or overruns. "Prediction isn't the hard part anymore. Explanation is."
2. **Problem (0:15–0:35):** A concrete scenario — a steel delivery is flagged at risk. Existing tools (a nod to predictive dashboards, without naming Kaya) tell the PM *that* it's at risk, not *why*, so the PM is guessing at the fix.
3. **The reveal (0:35–1:10):** Your causal graph lights up — the real driver is a shared vendor serving another active project. Show the estimated effect size on screen (e.g., "+X days, 90% CI"). This is the moment that makes the idea land.
4. **Action (1:10–1:35):** The agent drafts one concrete action (expedite email or alternate-vendor suggestion) tied directly to the causal driver, not a generic recommendation.
5. **Close (1:35–2:00):** Restate the one-line pitch. Team + college affiliations on screen per submission requirements.

---

## 9. 10-slide deck outline

1. **Hook** — the delay stat + "prediction isn't the hard part, explanation is"
2. **The problem, made concrete** — one real scenario (a PM reacting after the fact)
3. **Why current predictive/correlational tools hit a ceiling** — general, not Kaya-specific framing
4. **Your idea in one sentence**
5. **Architecture diagram** — dataset → causal engine (DML/GRF) → thin agent layer → action
6. **The causal engine** — what makes this not a wrapper; cite Wyrembek et al. (2024) as technique precedent
7. **The agent layer** — from "why" to "what to do"
8. **Demo screenshot(s)** — the causal graph visualization
9. **Impact & scalability** — how the same pipeline generalizes across delay drivers and projects
10. **Team + what's next** — names, college affiliations (IIT Bombay, ChemE/CS), and roadmap items (document intake, voice/WhatsApp field layer, etc.) explicitly framed as future scope, not current capability

---

## 10. Overnight execution plan (if you have ~12–15 hours and 2–4 people)

- **Person A — causal core:** Build the synthetic dataset with deliberately injected confounders, then EconML (DML or GRF) to estimate the treatment effect of the chosen driver(s). Sanity-check that your synthetic data produces a plausible, explainable effect size (doesn't need to match 17 days — needs to be a believable order of magnitude for construction).
- **Person B — agent layer:** Build the 2–3 node flow (Monitor → Causal Explain → Action) that turns the top causal driver into one drafted action artifact. Keep it thin and working over an ambitious-but-broken alternative.
- **Person C (+D) — interface, deck, video:** Build the causal graph visualization (this is the single highest-value visual asset), assemble the deck from Section 9, script and record the video from Section 8.

---

## 11. Ideas considered and set aside (for reference, in case you want to revisit)

- **Track 3 / DriftGraph** (contract → PO → invoice drift detection): well-scoped and genuinely buildable, and its execution discipline (one narrow workflow, 3-document demo, one risk score + one explanation + one action) is exactly what shaped Section 6 above. Set aside because the causal-delay angle is a sharper, more verifiably differentiated wedge against Kaya's actual product, and plays more directly to your DML/GRF background.
- **QuantBuild** (algorithmic hedging/procurement financial framing): interesting angle but rests on real-time commodity/freight/macro data access that's hard to make credible even at proposal stage, and introduces unexplained specific numbers (e.g., an arbitrary interest rate) that weaken credibility rather than strengthen it.
- **Cognitive Supply Chain Control Tower** (GraphRAG + Chronos + conformal prediction + VLM + DPO self-improvement, all combined): the most ambitious of the four, but combining five separate research pillars into one overnight build is a feasibility red flag against the "Technical Feasibility" judging criterion, and it's the source of the fabricated GraphRAG citation flagged in Section 4. If there's spare time after the core demo works, conformal prediction (calibrated uncertainty intervals around delay estimates, rather than a single point forecast) is the one piece of this idea worth revisiting — but verify the citation properly first (Angelopoulos & Bates have real, well-known conformal prediction survey work; don't reuse an unverified title).

---

## 12. Stage 1 submission checklist

- [ ] Written project proposal (problem, solution, chosen track — Track 2)
- [ ] Slide deck, max 10 slides (Google Slides or PDF) — outline in Section 9
- [ ] 2-minute video walkthrough (unlisted YouTube or Loom) — script beats in Section 8
- [ ] Names and college affiliations of all team members (2–4)
- [ ] Every statistic and citation in the final proposal double-checked against a live source before submission (Sections 3–5 are pre-verified; anything new you add is not)
- [ ] Submit before **11 Jul 2026, 9:15am GMT+5:30**
