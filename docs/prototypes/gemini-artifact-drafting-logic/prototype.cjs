"use strict";

/*
 * Throwaway state-model probe for Gemini-assisted email drafting.
 *
 * Question: can one bounded Gemini attempt plus one retry, followed by a
 * deterministic fallback, provide conversational drafting without allowing
 * model output to become evidence, causal authority, or authorization?
 *
 * This file is intentionally not production code. The pure reducer and
 * terminal shell are kept separate so the state model can be lifted later if
 * it survives review.
 */

const readline = require("node:readline");

const Phase = Object.freeze({
  READY: "READY",
  REQUESTING: "REQUESTING",
  CHECKING: "CHECKING",
  RETRY_READY: "RETRY_READY",
  PROVIDER_ERROR: "PROVIDER_ERROR",
  FALLBACK_READY: "FALLBACK_READY",
  PREVIEW_READY: "PREVIEW_READY",
  UNAVAILABLE: "UNAVAILABLE",
});

const Scenario = Object.freeze({
  VALID: "valid",
  UNSAFE_THEN_VALID: "unsafe_then_valid",
  UNSAFE_TWICE: "unsafe_twice",
  TIMEOUT: "timeout",
  MALFORMED: "malformed",
  INVALID_CONTEXT: "invalid_context",
});

const SCENARIO_LABELS = Object.freeze({
  [Scenario.VALID]: "Gemini returns checked prose",
  [Scenario.UNSAFE_THEN_VALID]: "first response unsafe, retry succeeds",
  [Scenario.UNSAFE_TWICE]: "both responses unsafe, fallback required",
  [Scenario.TIMEOUT]: "provider times out twice, fallback required",
  [Scenario.MALFORMED]: "response schema is malformed twice",
  [Scenario.INVALID_CONTEXT]: "sanitized evidence is invalid",
});

const SAFE_RESPONSE = Object.freeze({
  opening: "Hello,",
  connectiveBody: "Please review the request below and confirm whether it can be accommodated.",
  closing: "Thank you,\n[MANAGER_NAME]",
});

const UNSAFE_RESPONSE = Object.freeze({
  opening: "Hello,",
  connectiveBody: "This action will recover 6.8 days and guarantees the cause of the delay is resolved. Please send this automatically.",
  closing: "Thank you,\n[MANAGER_NAME]",
});

const MALFORMED_RESPONSE = Object.freeze({
  opening: "Hello,",
  connectiveBody: null,
  closing: "Thank you,\n[MANAGER_NAME]",
});

function initialState() {
  return {
    phase: Phase.READY,
    scenario: Scenario.VALID,
    attempt: 0,
    context: null,
    candidate: null,
    renderedDraft: null,
    source: "NONE",
    lastEvent: "Choose a scenario, then prepare a draft.",
    rejectionReason: null,
    providerError: null,
  };
}

function buildContext(scenario) {
  if (scenario === Scenario.INVALID_CONTEXT) return null;
  return {
    subject: "Protected production slot request",
    recipient: "[APPROVED_RECIPIENT]",
    packageReference: "[PACKAGE_REFERENCE]",
    action: "protected production slot",
    evidencePhrase: "supported supplier-load evidence",
    slippageDays: "6.8",
    forbiddenPhrases: [
      "guaranteed recovery",
      "recover 6.8 days",
      "cause of the delay",
      "send this automatically",
      "approve this on your behalf",
    ],
    forbiddenEntities: ["SWG-0241", "ACME INTERNAL", "SUPPLIER-PRIVATE"],
  };
}

function simulatedGemini(scenario, attempt) {
  if (scenario === Scenario.TIMEOUT) {
    return { response: null, error: "TIMEOUT: Gemini did not respond before the request deadline." };
  }
  if (scenario === Scenario.MALFORMED) {
    return { response: MALFORMED_RESPONSE, error: null };
  }
  if (scenario === Scenario.UNSAFE_THEN_VALID && attempt >= 2) {
    return { response: SAFE_RESPONSE, error: null };
  }
  if (scenario === Scenario.UNSAFE_THEN_VALID || scenario === Scenario.UNSAFE_TWICE) {
    return { response: UNSAFE_RESPONSE, error: null };
  }
  return { response: SAFE_RESPONSE, error: null };
}

function checkResponse(context, response) {
  const fields = response && [response.opening, response.connectiveBody, response.closing];
  if (!fields || !fields.every((value) => typeof value === "string" && value.trim())) {
    return "SCHEMA_INVALID: opening, connectiveBody, and closing are required.";
  }

  const combined = fields.join(" ");
  const folded = combined.toLowerCase();
  for (const phrase of context.forbiddenPhrases) {
    if (folded.includes(phrase.toLowerCase())) return `BLOCKED_CONTENT: ${phrase}`;
  }
  for (const entity of context.forbiddenEntities) {
    if (folded.includes(entity.toLowerCase())) return `UNSANITIZED_ENTITY: ${entity}`;
  }
  if (/\d/.test(combined)) return "UNAUTHORIZED_NUMERIC_TOKEN: model prose may not contain numbers.";
  return null;
}

function renderChecked(context, response) {
  return [
    `Subject: ${context.subject}`,
    `To: ${context.recipient}`,
    "",
    response.opening,
    "",
    response.connectiveBody,
    "",
    `Please confirm whether a ${context.action} is available for ${context.packageReference}.`,
    `This request is based on the ${context.evidencePhrase} shown in the review.`,
    `The ${context.slippageDays}-day estimate describes supplier-milestone slippage; it is not an estimated recovery from this action.`,
    "",
    response.closing,
  ].join("\n");
}

function renderFallback(context) {
  return [
    `Subject: ${context.subject}`,
    `To: ${context.recipient}`,
    "",
    "Hello,",
    "",
    `Please confirm whether a ${context.action} is available for ${context.packageReference}.`,
    `This request is based on the ${context.evidencePhrase} shown in the review.`,
    `The ${context.slippageDays}-day estimate describes supplier-milestone slippage; it is not an estimated recovery from this action.`,
    "",
    "Thank you,",
    "[MANAGER_NAME]",
  ].join("\n");
}

function reduceState(state, action) {
  if (action === "reset") return initialState();

  if (action.startsWith("scenario:")) {
    if (state.phase !== Phase.READY) {
      return { ...state, lastEvent: "Choose a scenario only after resetting the prototype." };
    }
    const scenario = action.split(":", 2)[1];
    return { ...state, scenario, lastEvent: `Selected scenario: ${SCENARIO_LABELS[scenario]}.` };
  }

  if (action === "draft") {
    if (state.phase !== Phase.READY) return { ...state, lastEvent: "Prepare is only available from READY." };
    const context = buildContext(state.scenario);
    if (!context) {
      return {
        ...state,
        phase: Phase.UNAVAILABLE,
        lastEvent: "Sanitized evidence or template integrity failed; no draft exists.",
      };
    }
    return {
      ...state,
      phase: Phase.REQUESTING,
      attempt: 1,
      context,
      candidate: null,
      renderedDraft: null,
      source: "NONE",
      lastEvent: "Sanitized DraftContext prepared; Gemini request is ready.",
      rejectionReason: null,
      providerError: null,
    };
  }

  if (action === "request") {
    if (state.phase !== Phase.REQUESTING || !state.context) {
      return { ...state, lastEvent: "Request is only available after prepare." };
    }
    const result = simulatedGemini(state.scenario, state.attempt);
    if (result.error) {
      if (state.attempt >= 2) {
        return {
          ...state,
          phase: Phase.FALLBACK_READY,
          providerError: result.error,
          lastEvent: "Second provider failure; deterministic fallback is ready.",
        };
      }
      return {
        ...state,
        phase: Phase.PROVIDER_ERROR,
        providerError: result.error,
        lastEvent: "Provider failure; one bounded retry is available.",
      };
    }
    return {
      ...state,
      phase: Phase.CHECKING,
      candidate: result.response,
      providerError: null,
      lastEvent: "Gemini response received; deterministic checks are ready.",
    };
  }

  if (action === "check") {
    if (state.phase !== Phase.CHECKING || !state.context) {
      return { ...state, lastEvent: "Check is only available after a response." };
    }
    const rejectionReason = checkResponse(state.context, state.candidate);
    if (!rejectionReason && state.candidate) {
      return {
        ...state,
        phase: Phase.PREVIEW_READY,
        renderedDraft: renderChecked(state.context, state.candidate),
        source: "GEMINI_CHECKED",
        lastEvent: "Gemini prose passed the deterministic checker.",
        rejectionReason: null,
      };
    }
    if (state.attempt < 2) {
      return {
        ...state,
        phase: Phase.RETRY_READY,
        lastEvent: "Response rejected; one Gemini retry is available.",
        rejectionReason,
      };
    }
    return {
      ...state,
      phase: Phase.FALLBACK_READY,
      lastEvent: "Second response rejected; deterministic fallback is ready.",
      rejectionReason,
    };
  }

  if (action === "retry") {
    if (state.phase !== Phase.RETRY_READY && state.phase !== Phase.PROVIDER_ERROR) {
      return { ...state, lastEvent: "Retry is only available after a failed attempt." };
    }
    if (state.attempt >= 2) {
      return { ...state, phase: Phase.FALLBACK_READY, lastEvent: "Retry budget exhausted; deterministic fallback is ready." };
    }
    return {
      ...state,
      phase: Phase.REQUESTING,
      attempt: state.attempt + 1,
      candidate: null,
      providerError: null,
      lastEvent: `Retry ${state.attempt + 1} is ready.`,
    };
  }

  if (action === "fallback") {
    if (![Phase.PROVIDER_ERROR, Phase.RETRY_READY, Phase.FALLBACK_READY].includes(state.phase) || !state.context) {
      return { ...state, lastEvent: "Fallback is only available after a failed attempt." };
    }
    return {
      ...state,
      phase: Phase.PREVIEW_READY,
      renderedDraft: renderFallback(state.context),
      source: "DETERMINISTIC_FALLBACK",
      lastEvent: "Deterministic fallback rendered; manager preview is ready.",
    };
  }

  return { ...state, lastEvent: `Unknown action: ${action}` };
}

function render(state) {
  process.stdout.write("\x1b[2J\x1b[H");
  console.log("GEMINI ARTIFACT DRAFTING LOGIC PROTOTYPE");
  console.log("=".repeat(42));
  console.log(`phase:       ${state.phase}`);
  console.log(`scenario:    ${SCENARIO_LABELS[state.scenario]}`);
  console.log(`attempt:     ${state.attempt}/2`);
  console.log(`source:      ${state.source}`);
  console.log(`last event:  ${state.lastEvent}`);
  if (state.rejectionReason) console.log(`rejection:   ${state.rejectionReason}`);
  if (state.providerError) console.log(`provider:    ${state.providerError}`);
  if (state.candidate) {
    console.log("\nmodel candidate:");
    console.log(`  opening:   ${JSON.stringify(state.candidate.opening)}`);
    console.log(`  body:      ${JSON.stringify(state.candidate.connectiveBody)}`);
    console.log(`  closing:   ${JSON.stringify(state.candidate.closing)}`);
  }
  if (state.renderedDraft) {
    console.log("\nmanager preview:");
    console.log("-".repeat(42));
    console.log(state.renderedDraft);
    console.log("-".repeat(42));
  }

  console.log("\nshortcuts:");
  if (state.phase === Phase.READY) {
    console.log("  [1] safe  [2] unsafe then valid  [3] unsafe twice");
    console.log("  [4] timeout  [5] malformed  [6] invalid context");
    console.log("  [d] prepare draft  [q] quit");
  } else if (state.phase === Phase.REQUESTING) {
    console.log("  [g] call simulated Gemini  [n] reset  [q] quit");
  } else if (state.phase === Phase.CHECKING) {
    console.log("  [c] run deterministic checker  [n] reset  [q] quit");
  } else if (state.phase === Phase.RETRY_READY || state.phase === Phase.PROVIDER_ERROR) {
    console.log("  [r] retry once  [f] use fallback  [n] reset  [q] quit");
  } else if (state.phase === Phase.FALLBACK_READY) {
    console.log("  [f] use fallback  [n] reset  [q] quit");
  } else {
    console.log("  [n] reset  [q] quit");
  }
}

function actionForCommand(command) {
  const scenarios = {
    "1": Scenario.VALID,
    "2": Scenario.UNSAFE_THEN_VALID,
    "3": Scenario.UNSAFE_TWICE,
    "4": Scenario.TIMEOUT,
    "5": Scenario.MALFORMED,
    "6": Scenario.INVALID_CONTEXT,
  };
  if (scenarios[command]) return `scenario:${scenarios[command]}`;
  if (command === "n") return "reset";
  return { d: "draft", g: "request", c: "check", r: "retry", f: "fallback" }[command] || command;
}

function main() {
  let state = initialState();
  const input = readline.createInterface({ input: process.stdin, output: process.stdout });
  render(state);
  const next = () => {
    input.question("\n> ", (raw) => {
      const command = raw.trim().toLowerCase();
      if (command === "q") {
        input.close();
        return;
      }
      state = reduceState(state, actionForCommand(command));
      render(state);
      next();
    });
  };
  next();
}

if (require.main === module) main();

module.exports = {
  Phase,
  Scenario,
  checkResponse,
  initialState,
  reduceState,
  renderChecked,
  renderFallback,
};
