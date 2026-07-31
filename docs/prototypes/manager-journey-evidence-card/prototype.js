(function () {
  "use strict";

  var STAGES = [
    { key: "intake", label: "Risk intake" },
    { key: "eligibility", label: "Eligibility" },
    { key: "evidence", label: "Evidence" },
    { key: "actions", label: "Actions" },
    { key: "draft", label: "Draft & decide" },
    { key: "audit", label: "Audit replay" }
  ];

  var VARIANTS = [
    { key: "A", name: "Signal desk" },
    { key: "B", name: "Decision brief" },
    { key: "C", name: "Command ledger" }
  ];

  var params = new URLSearchParams(window.location.search);
  var initialVariant = (params.get("variant") || "B").toUpperCase();
  var validVariant = VARIANTS.some(function (item) { return item.key === initialVariant; });

  var state = {
    variant: validVariant ? initialVariant : "B",
    trigger: "reactive",
    stage: "evidence",
    details: false,
    auditOpen: false,
    chosenAction: "protected-slot",
    decision: "pending",
    runCount: 0,
    selectedCase: "SWG-0241"
  };

  var app = document.getElementById("app");
  var liveRegion = document.getElementById("live-region");
  var switcher = document.getElementById("prototype-switcher");
  var variantLabel = document.getElementById("variant-label");

  function currentVariant() {
    return VARIANTS.find(function (item) { return item.key === state.variant; });
  }

  function triggerLabel() {
    return state.trigger === "reactive" ? "Reactive risk signal" : "Proactive pre-award check";
  }

  function stageIndex() {
    return STAGES.findIndex(function (item) { return item.key === state.stage; });
  }

  function stageStatus(index) {
    if (index < stageIndex()) {
      return "Complete";
    }
    if (index === stageIndex()) {
      return "Current";
    }
    return "Next";
  }

  function tag(text, kind) {
    return '<span class="tag tag-' + (kind || "neutral") + '">' + text + "</span>";
  }

  function button(label, action, className, extra) {
    return '<button class="button ' + (className || "button-tertiary") + '" type="button" data-action="' + action + '"' + (extra || "") + ">" + label + "</button>";
  }

  function updateUrl() {
    var next = new URL(window.location.href);
    next.searchParams.set("variant", state.variant);
    window.history.replaceState({}, "", next);
  }

  function announce(message) {
    liveRegion.textContent = message;
  }

  function renderContextBar() {
    var triggerKind = state.trigger === "reactive" ? "red" : "blue";
    return [
      '<section class="context-bar" aria-label="Active investigation context">',
      "<div>",
      '<span class="overline">Active case</span>',
      '<strong class="context-title">SWG-0241 · Switchgear package</strong>',
      '<span class="context-subtitle">Northline Fabrication · supplier handoff milestone 18 Aug 2026 · run ' + (state.runCount + 1) + "</span>",
      "</div>",
      '<div class="context-actions">',
      '<div class="tag-row">' + tag(triggerLabel(), triggerKind) + tag("Semi-synthetic hero", "neutral") + "</div>",
      button("Open audit", "audit", "button-ghost", ' aria-expanded="' + String(state.auditOpen) + '"'),
      "</div>",
      "</section>"
    ].join("");
  }

  function renderStageRail() {
    var items = STAGES.map(function (stage, index) {
      var current = state.stage === stage.key;
      return [
        '<button class="stage-item" type="button" data-stage="' + stage.key + '"' + (current ? ' aria-current="step"' : "") + ">",
        '<span class="stage-index">0' + (index + 1) + "</span>",
        "<span>" + stage.label + "</span>",
        '<span class="stage-state">' + stageStatus(index) + "</span>",
        "</button>"
      ].join("");
    }).join("");

    return [
      '<aside class="journey-rail" aria-label="Manager journey stages">',
      '<h2 class="rail-heading">Decision journey</h2>',
      '<p class="rail-caption">One investigation, two entry points. The engine and evidence contract stay the same.</p>',
      '<div class="stage-list">' + items + "</div>",
      "</aside>"
    ].join("");
  }

  function renderProgressStepper() {
    var items = STAGES.map(function (stage, index) {
      var current = state.stage === stage.key;
      return [
        '<button class="step-button" type="button" data-stage="' + stage.key + '"' + (current ? ' aria-current="step"' : "") + ">",
        '<span class="step-number">0' + (index + 1) + "</span>",
        '<span class="step-label">' + stage.label + "</span>",
        "</button>"
      ].join("");
    }).join("");
    return '<nav class="journey-stepper" aria-label="Manager journey progress">' + items + "</nav>";
  }

  function renderIntakePanel() {
    var copy = state.trigger === "reactive"
      ? "The upstream risk score is an untrusted input to investigate, not a causal conclusion."
      : "The same investigation is being invoked before commitment, while supplier choice and release timing are still available.";
    return [
      '<section class="risk-panel">',
      '<div class="panel-header"><div><span class="section-kicker">Act 1 · Risk intake</span><h2>' + triggerLabel() + "</h2></div>" + '<span class="status-mark status-tentative">Needs investigation</span></div>',
      '<p class="verdict-line"><strong>72% predicted risk of missing supplier handoff.</strong><br />Prediction identifies a case to inspect; it does not identify a driver.</p>',
      "<p>" + copy + "</p>",
      '<div class="tag-row">' + tag("Risk score 0.72", "red") + tag("Decision cutoff 09:42", "neutral") + tag("Known before decision", "green") + "</div>",
      '<div class="button-row">' + button("Freeze context & check eligibility", "check", "button-primary") + "</div>",
      "</section>"
    ].join("");
  }

  function renderEligibilityPanel() {
    return [
      '<section class="eligibility-panel">',
      '<div class="panel-header"><div><span class="section-kicker">Act 2 · Context freeze</span><h2>Eligibility is visible before any estimate</h2></div><span class="status-mark status-supported">Eligible</span></div>',
      '<p>The cutoff is frozen at 31 Jul 2026, 09:42 local. Only pre-decision information enters the causal handoff.</p>',
      '<div class="metric-row">',
      '<div class="metric"><span class="metric-label">Supplier history</span><span class="metric-value">38 prior orders</span></div>',
      '<div class="metric"><span class="metric-label">Exposure measure</span><span class="metric-value">Usable</span></div>',
      '<div class="metric"><span class="metric-label">Subject overlap</span><span class="metric-value">Adequate</span></div>',
      "</div>",
      '<div class="tag-row">' + tag("Frozen promise", "green") + tag("No post-risk covariates", "green") + tag("Support in distribution", "green") + "</div>",
      '<div class="button-row">' + button("View evidence verdict", "investigate", "button-primary") + button("Back to intake", "back-intake", "button-ghost") + "</div>",
      "</section>"
    ].join("");
  }

  function renderSignalMap() {
    return [
      '<div class="signal-map" role="img" aria-label="Signal to decision handoff">',
      '<div class="signal-node"><span class="signal-node-index">01</span><span class="signal-node-copy"><strong>Risk signal</strong><small>Untrusted input</small></span></div>',
      '<span class="signal-connector" aria-hidden="true"></span>',
      '<div class="signal-node"><span class="signal-node-index">02</span><span class="signal-node-copy"><strong>Frozen context</strong><small>Pre-decision data</small></span></div>',
      '<span class="signal-connector" aria-hidden="true"></span>',
      '<div class="signal-node active"><span class="signal-node-index">03</span><span class="signal-node-copy"><strong>Evidence verdict</strong><small>Claim scope visible</small></span></div>',
      '<span class="signal-connector" aria-hidden="true"></span>',
      '<div class="signal-node"><span class="signal-node-index">04</span><span class="signal-node-copy"><strong>Human decision</strong><small>Authorization required</small></span></div>',
      "</div>"
    ].join("");
  }

  function renderDetails() {
    if (!state.details) {
      return "";
    }
    return [
      '<div class="detail-stack">',
      '<div class="detail-row"><span class="detail-label">Target population</span><span class="detail-value">Comparable exposed orders at this supplier; population evidence plus subject applicability, not an individualized CATE.</span></div>',
      '<div class="detail-row"><span class="detail-label">Adjustment set</span><span class="detail-value">Supplier history, material category, quantity/value bands, calendar controls, and pre-decision workload indicators actually used.</span></div>',
      '<div class="detail-row"><span class="detail-label">Refuter scoreboard</span><span class="detail-value">' + tag("Placebo passed", "green") + " " + tag("Dummy outcome passed", "green") + " " + tag("Subset stable", "green") + "</span></div>",
      '<div class="detail-row"><span class="detail-label">What could overturn it</span><span class="detail-value">An unobserved confounder would need strength comparable to the strongest observed workload and calendar controls; the grade remains separate from the verdict.</span></div>',
      '<div class="detail-row"><span class="detail-label">Not observed</span><span class="detail-value">This is not an estimated benefit of rerouting, expediting, or reserving a slot. Those action links remain separately tagged assumptions.</span></div>',
      "</div>"
    ].join("");
  }

  function renderEvidenceCard() {
    var rerunLabel = state.runCount ? "Rerun complete · inspect new result" : "Rerun investigation";
    return [
      '<section class="evidence-card">',
      '<div class="card-header"><div><span class="section-kicker">Act 3 · Verdict-first evidence</span><h2>Supplier congestion and milestone slippage</h2></div><span class="status-mark status-supported">Supported under stated assumptions</span></div>',
      renderSignalMap(),
      '<p class="verdict-line"><strong>High-load exposure is estimated to increase supplier milestone slippage by 6.8 days</strong> (95% interval 1.2 to 12.4), under the stated assumptions.</p>',
      '<div class="metric-row">',
      '<div class="metric"><span class="metric-label">Estimated effect</span><span class="metric-value">+6.8 days</span></div>',
      '<div class="metric"><span class="metric-label">95% interval</span><span class="metric-value">1.2–12.4</span></div>',
      '<div class="metric"><span class="metric-label">Robustness Grade</span><span class="metric-value">Moderate</span></div>',
      "</div>",
      '<div class="claim-scope"><strong>Claim scope:</strong> population evidence applies to this eligible subject. It is evidence about exposure, not proof that a particular intervention will save 6.8 days.</div>',
      '<div class="disclosure"><button class="disclosure-toggle" type="button" data-action="details" aria-expanded="' + String(state.details) + '">' + (state.details ? "Hide diagnostics and assumptions" : "Open diagnostics and assumptions") + " <span aria-hidden=\"true\">→</span></button>" + renderDetails() + "</div>",
      '<div class="button-row">' + button("Compare eligible actions", "proceed-actions", "button-primary") + button(rerunLabel, "rerun", "button-ghost") + "</div>",
      "</section>"
    ].join("");
  }

  function actionOption(title, body, tags, action, selected, suppressed) {
    var classes = "action-option" + (selected ? " selected" : "") + (suppressed ? " suppressed" : "");
    var actionButton = suppressed
      ? '<span class="status-mark status-abstain">Suppressed by constraint</span>'
      : button(selected ? "Selected for draft" : "Use for draft", action, selected ? "button-primary" : "button-tertiary", ' aria-pressed="' + String(selected) + '"');
    return [
      '<article class="' + classes + '">',
      "<h3>" + title + "</h3>",
      "<p>" + body + "</p>",
      '<div class="tag-row">' + tags.map(function (item) { return tag(item.text, item.kind); }).join("") + "</div>",
      actionButton,
      "</article>"
    ].join("");
  }

  function renderActionComparison() {
    return [
      '<section class="action-comparison">',
      '<div class="decision-header"><div><span class="section-kicker">Act 4 · Separate decision support</span><h2>Compare actions without laundering exposure evidence into intervention benefit</h2></div><span class="status-mark status-supported">Manager choice required</span></div>',
      '<p>Each option exposes its mechanism, constraints, and evidence basis. The action lane can be entered only because the current evidence scope permits it.</p>',
      '<div class="action-grid">',
      actionOption("Protected slot + phased release", "Ask the supplier for a capacity-backed slot and release the package in phases.", [
        { text: "Driver evidence", kind: "blue" },
        { text: "Mechanistic link", kind: "green" },
        { text: "Rule-based eligible", kind: "green" },
        { text: "Benefit assumption editable", kind: "yellow" }
      ], "choose-protected-slot", state.chosenAction === "protected-slot", false),
      actionOption("Reroute remaining quantity", "The alternate supplier misses the project float constraint for this package.", [
        { text: "Remaining quantity only", kind: "neutral" },
        { text: "Float constraint", kind: "red" }
      ], "choose-reroute", false, true),
      actionOption("Generic expedite request", "A congested supplier cannot be asked to go faster without a real acceleration mechanism.", [
        { text: "Driver logic blocks", kind: "red" },
        { text: "No mechanism", kind: "red" }
      ], "choose-expedite", false, true),
      actionOption("Accept and monitor", "Keep the supplier and require a milestone update without claiming causal benefit.", [
        { text: "Abstention-adjacent", kind: "yellow" },
        { text: "No action benefit claim", kind: "neutral" }
      ], "choose-monitor", state.chosenAction === "monitor", false),
      "</div>",
      '<div class="button-row">' + button("Draft selected action", "draft", "button-primary") + button("Back to evidence", "back-evidence", "button-ghost") + "</div>",
      "</section>"
    ].join("");
  }

  function renderDraftPanel() {
    var decisionClass = state.decision === "approved" ? "approved" : state.decision === "rejected" ? "rejected" : "";
    var decisionCopy = state.decision === "approved"
      ? "Manager approval recorded for this exact recommendation and evidence snapshot."
      : state.decision === "rejected"
        ? "Rejected for now. A reason or an investigation rerun is required before another draft."
        : "Nothing is sent automatically. The manager may edit, approve, reject, or investigate further.";
    return [
      '<section class="draft-panel">',
      '<div class="draft-header"><div><span class="section-kicker">Act 5 · Human authorization</span><h2>Draft the capacity-slot request</h2></div><span class="status-mark status-tentative">Awaiting manager</span></div>',
      '<p>Generated from the structured evidence and selected action. The intervention benefit remains an editable assumption, not an estimated causal effect.</p>',
      '<label class="table-label" for="draft-text">Draft artefact · editable</label>',
      '<textarea id="draft-text">Subject: Capacity-backed slot request for SWG-0241\n\nPlease confirm a protected production slot for the switchgear package and propose a phased release plan. The request is prompted by a supported supplier-load signal; the 6.8-day exposure estimate is not a promised recovery benefit.</textarea>',
      '<div class="decision-banner ' + decisionClass + '"><strong>' + (state.decision === "approved" ? "Approved" : state.decision === "rejected" ? "Rejected" : "Review before authorization") + "</strong><span>" + decisionCopy + "</span></div>",
      '<div class="button-row">' + button("Approve draft", "approve", "button-primary") + button("Reject with reason", "reject", "button-tertiary") + button("Investigate further", "rerun", "button-ghost") + "</div>",
      "</section>"
    ].join("");
  }

  function renderAuditPanel() {
    return [
      '<section class="audit-panel">',
      '<div class="audit-header"><div><span class="section-kicker">Act 6 · Governance & audit</span><h2>Replay what was known, recommended, and authorized</h2></div><span class="status-mark status-supported">Immutable snapshot</span></div>',
      '<div class="audit-meta">',
      '<div class="audit-meta-item"><span>Analysis run</span><strong>run-2026-07-31-' + String(state.runCount + 1).padStart(3, "0") + "</strong></div>",
      '<div class="audit-meta-item"><span>Trigger</span><strong>' + triggerLabel() + "</strong></div>",
      '<div class="audit-meta-item"><span>Evidence digest</span><strong>sha256: 3f2a…91d4</strong></div>',
      '<div class="audit-meta-item"><span>Decision state</span><strong>' + (state.decision === "pending" ? "Awaiting manager" : state.decision) + "</strong></div>",
      "</div>",
      '<ol class="audit-list">',
      "<li><span>09:42 · Context frozen</span>Risk signal and pre-decision covariates were normalized into the causal handoff.</li>",
      "<li><span>09:43 · Eligibility passed</span>Exposure, temporal ordering, overlap, and missingness checks were recorded.</li>",
      "<li><span>09:44 · Evidence published</span>Verdict, effect, interval, Robustness Grade, diagnostics, and claim scope were sealed.</li>",
      "<li><span>09:45 · Decision support evaluated</span>Protected slot remained eligible; reroute and generic expedite were suppressed with named reasons.</li>",
      "<li><span>09:46 · Manager operation</span>" + (state.decision === "pending" ? "No authorization has been recorded." : "Manager decision was recorded against the exact recommendation.") + "</li>",
      "</ol>",
      '<div class="button-row">' + button("Close replay", "close-audit", "button-ghost") + "</div>",
      "</section>"
    ].join("");
  }

  function renderGuardrails() {
    return [
      '<div class="inspector-stack">',
      '<section class="guardrail-panel"><span class="section-kicker">Always visible</span><h2>Decision guardrails</h2><p>The verdict and Robustness Grade are separate. “Supported” never means “this action will save 6.8 days.”</p><div class="tag-row">' + tag("Verdict-first", "blue") + tag("Grade separate", "green") + "</div></section>",
      '<section class="guardrail-panel attention"><span class="section-kicker">Progressive layer</span><h2>One tap deeper</h2><p>Diagnostics, adjustment set, refuters, sensitivity, and overturning strength stay available without competing with the manager’s first read.</p><div class="tag-row">' + tag(state.details ? "Expanded" : "Collapsed", "yellow") + "</div></section>",
      '<section class="guardrail-panel read-only"><span class="section-kicker">Abstention example</span><h2>Insufficient evidence — abstain</h2><p>If subject overlap fails, the action lane becomes read-only. The next step is to collect comparable cases or use the non-causal risk workflow.</p><div class="tag-row">' + tag("No driver-linked recommendation", "red") + "</div></section>",
      "</div>"
    ].join("");
  }

  function renderVariantA() {
    return [
      '<div class="variant variant-a">',
      renderContextBar(),
      '<div class="workspace-grid">',
      renderStageRail(),
      '<section class="evidence-column">',
      '<div class="section-heading"><div><span class="section-kicker">Variant A</span><h1>Signal desk</h1><p>A calm evidence desk with a persistent journey rail and a single visual handoff from signal to decision.</p></div></div>',
      state.stage === "intake" ? renderIntakePanel() : "",
      state.stage === "eligibility" ? renderEligibilityPanel() : "",
      state.stage === "evidence" ? renderEvidenceCard() : "",
      state.stage === "actions" ? renderActionComparison() : "",
      state.stage === "draft" ? renderDraftPanel() : "",
      state.stage === "audit" ? renderAuditPanel() : "",
      "</section>",
      '<aside class="inspector-column">' + renderGuardrails() + "</aside>",
      "</div>",
      "</div>"
    ].join("");
  }

  function renderGuidedStage() {
    if (state.stage === "intake") {
      return renderIntakePanel();
    }
    if (state.stage === "eligibility") {
      return renderEligibilityPanel();
    }
    if (state.stage === "actions") {
      return renderActionComparison();
    }
    if (state.stage === "draft") {
      return renderDraftPanel();
    }
    if (state.stage === "audit") {
      return renderAuditPanel();
    }
    return renderEvidenceCard();
  }

  function renderVariantB() {
    var previousIndex = Math.max(0, stageIndex() - 1);
    var nextIndex = Math.min(STAGES.length - 1, stageIndex() + 1);
    return [
      '<div class="variant variant-b">',
      renderContextBar(),
      renderProgressStepper(),
      '<div class="focus-layout">',
      '<section class="focus-card">',
      '<div class="section-heading"><div><span class="section-kicker">Variant B</span><h1>Decision brief</h1><p>A paced review brief that gives one manager question the full width of attention at a time.</p></div></div>',
      renderGuidedStage(),
      '<div class="focus-footer">',
      stageIndex() > 0 ? button("← Previous", "previous-stage", "button-ghost", ' data-target-stage="' + STAGES[previousIndex].key + '"') : "<span></span>",
      stageIndex() < STAGES.length - 1 ? button("Next →", "next-stage", "button-primary", ' data-target-stage="' + STAGES[nextIndex].key + '"') : "<span></span>",
      "</div>",
      "</section>",
      '<aside class="focus-aside"><h2>What the manager should know</h2><ul><li>The upstream score starts an investigation; it never becomes the verdict.</li><li>Eligibility failures stop the estimate before the estimator runs.</li><li>Evidence and intervention benefit use separate labels.</li><li>Approval is an auditable manager operation, never an automatic send.</li></ul><div class="guardrail-stack">' + renderGuardrails() + "</div></aside>",
      "</div>",
      "</div>"
    ].join("");
  }

  function timelineEvent(title, body, content, stateClass) {
    return [
      '<article class="timeline-event ' + (stateClass || "") + '">',
      '<div class="timeline-content"><h2>' + title + "</h2><p>" + body + "</p>",
      content ? '<div class="timeline-card">' + content + "</div>" : "",
      "</div>",
      "</article>"
    ].join("");
  }

  function renderCaseList() {
    var cases = [
      { id: "SWG-0241", label: "Switchgear package", detail: "72% risk · active" },
      { id: "PMP-0198", label: "Pump skid", detail: "Subject overlap · abstain" },
      { id: "VAL-0087", label: "Valve assembly", detail: "Proactive check · draft" }
    ];
    return [
      '<aside class="case-list"><h2>Open investigations</h2>',
      cases.map(function (item) {
        var selected = item.id === state.selectedCase;
        return '<button class="case-row' + (selected ? " selected" : "") + '" type="button" data-case="' + item.id + '"' + (selected ? ' aria-current="true"' : "") + '><span class="case-status" aria-hidden="true"></span><span><strong>' + item.id + "</strong><span>" + item.label + "</span><span>" + item.detail + "</span></span></button>";
      }).join(""),
      '<p class="helper-text">The list is a prototype probe, not a general control tower.</p>',
      "</aside>"
    ].join("");
  }

  function renderVariantC() {
    return [
      '<div class="variant variant-c">',
      renderContextBar(),
      '<div class="board-toolbar"><div><span class="section-kicker">Variant C</span><h1>Command ledger</h1><p>A compact case ledger where chronology, evidence, constraints, and authorization stay visible together.</p></div><div class="tag-row">' + tag("Selected: " + state.selectedCase, "blue") + tag("Run " + (state.runCount + 1), "neutral") + "</div></div>",
      '<div class="command-board">',
      renderCaseList(),
      '<section class="timeline-stack" aria-label="Investigation timeline">',
      timelineEvent("Risk signal received", "Prediction opened an investigation at 09:42.", '<div class="tag-row">' + tag(triggerLabel(), "blue") + tag("Untrusted input", "yellow") + "</div>", "complete"),
      timelineEvent("Eligibility gate", "Context frozen; 38 prior supplier orders and adequate subject overlap.", '<div class="tag-row">' + tag("Eligible", "green") + tag("No post-risk data", "green") + "</div>", "complete"),
      timelineEvent("Verdict-first evidence", "The evidence card is the decision boundary before action comparison.", renderEvidenceCard(), "active"),
      timelineEvent("Action comparison", "Options inherit evidence scope but carry their own constraints and assumptions.", renderActionComparison(), state.stage === "actions" ? "active" : ""),
      "</section>",
      '<aside class="decision-lane"><h2>Decision lane</h2>',
      state.stage === "draft" ? renderDraftPanel() : '<section class="guardrail-panel"><span class="section-kicker">Next operation</span><h2>' + (state.decision === "approved" ? "Authorization recorded" : "Select an eligible option") + "</h2><p>" + (state.decision === "approved" ? "Replay the exact snapshot from audit when needed." : "The protected slot option is the only active recommendation candidate in this case.") + "</p>" + button(state.decision === "approved" ? "Open audit" : "Open action comparison", state.decision === "approved" ? "audit" : "proceed-actions", "button-primary") + "</section>",
      renderGuardrails(),
      "</aside>",
      "</div>",
      state.auditOpen ? renderAuditPanel() : "",
      "</div>"
    ].join("");
  }

  function render() {
    if (state.variant === "A") {
      app.innerHTML = renderVariantA();
    } else if (state.variant === "B") {
      app.innerHTML = renderVariantB();
    } else {
      app.innerHTML = renderVariantC();
    }

    var variant = currentVariant();
    variantLabel.textContent = variant.key + " — " + variant.name;
    switcher.hidden = params.get("production") === "true";
    document.querySelectorAll("[data-trigger]").forEach(function (control) {
      control.setAttribute("aria-pressed", String(control.getAttribute("data-trigger") === state.trigger));
    });
    document.querySelectorAll("[data-action=\"audit\"]").forEach(function (control) {
      control.setAttribute("aria-expanded", String(state.auditOpen));
    });
  }

  function setVariant(direction) {
    var index = VARIANTS.findIndex(function (item) { return item.key === state.variant; });
    var next = (index + direction + VARIANTS.length) % VARIANTS.length;
    state.variant = VARIANTS[next].key;
    updateUrl();
    render();
    announce("Showing variant " + VARIANTS[next].key + ", " + VARIANTS[next].name + ".");
  }

  function handleAction(action, element) {
    if (action === "variant-prev") {
      setVariant(-1);
      return;
    }
    if (action === "variant-next") {
      setVariant(1);
      return;
    }
    if (action === "audit") {
      state.auditOpen = true;
      state.stage = "audit";
      render();
      announce("Audit replay opened.");
      return;
    }
    if (action === "close-audit") {
      state.auditOpen = false;
      state.stage = "evidence";
      render();
      announce("Audit replay closed.");
      return;
    }
    if (action === "details") {
      state.details = !state.details;
      render();
      announce(state.details ? "Evidence diagnostics expanded." : "Evidence diagnostics collapsed.");
      return;
    }
    if (action === "check") {
      state.stage = "eligibility";
      render();
      announce("Context frozen. Eligibility checks passed.");
      return;
    }
    if (action === "investigate" || action === "back-evidence") {
      state.stage = "evidence";
      render();
      announce("Evidence verdict opened.");
      return;
    }
    if (action === "back-intake") {
      state.stage = "intake";
      render();
      announce("Risk intake reopened.");
      return;
    }
    if (action === "proceed-actions") {
      state.stage = "actions";
      render();
      announce("Action comparison opened.");
      return;
    }
    if (action === "draft") {
      state.stage = "draft";
      render();
      announce("Draft artefact opened for manager review.");
      return;
    }
    if (action === "approve") {
      state.decision = "approved";
      render();
      announce("Draft approved. The manager authorization is recorded in memory for this prototype.");
      return;
    }
    if (action === "reject") {
      state.decision = "rejected";
      render();
      announce("Draft rejected. A reason would be required in the production contract.");
      return;
    }
    if (action === "rerun") {
      state.runCount += 1;
      state.stage = "evidence";
      state.auditOpen = false;
      state.decision = "pending";
      render();
      announce("Fresh local investigation run completed. New evidence is shown.");
      return;
    }
    if (action.indexOf("choose-") === 0) {
      var choice = action.replace("choose-", "");
      state.chosenAction = choice === "protected-slot" ? "protected-slot" : choice;
      render();
      announce("Action selection changed to " + choice + ".");
      return;
    }
    if (action === "previous-stage" || action === "next-stage") {
      state.stage = element.getAttribute("data-target-stage");
      render();
      announce("Moved to " + STAGES.find(function (item) { return item.key === state.stage; }).label + ".");
    }
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-trigger]");
    if (trigger) {
      state.trigger = trigger.getAttribute("data-trigger");
      render();
      announce("Trigger changed to " + triggerLabel() + ".");
      return;
    }

    var stage = event.target.closest("[data-stage]");
    if (stage) {
      state.stage = stage.getAttribute("data-stage");
      state.auditOpen = state.stage === "audit";
      render();
      announce("Opened " + STAGES.find(function (item) { return item.key === state.stage; }).label + ".");
      return;
    }

    var caseButton = event.target.closest("[data-case]");
    if (caseButton) {
      state.selectedCase = caseButton.getAttribute("data-case");
      render();
      announce("Selected case " + state.selectedCase + ".");
      return;
    }

    var action = event.target.closest("[data-action]");
    if (action) {
      handleAction(action.getAttribute("data-action"), action);
    }
  });

  document.addEventListener("keydown", function (event) {
    var target = event.target;
    var tagName = target && target.tagName ? target.tagName.toLowerCase() : "";
    if (tagName === "input" || tagName === "textarea" || target.isContentEditable) {
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setVariant(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setVariant(1);
    }
  });

  render();
})();
