import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const healthResponse = {
  service: "causal-delay-copilot",
  state: "degraded",
  code: "CORE_READY_GEMINI_DEGRADED",
  liveness: { state: "live", code: "CORE_LIVE" },
  readiness: { state: "degraded", code: "CORE_READY_GEMINI_DEGRADED" },
  degraded_capabilities: ["GEMINI_DRAFTING"],
  observed_at: "2026-08-05T00:00:00Z",
};

describe("Core health journey", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("shows typed liveness/readiness and records one audited boot occurrence", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async (input, init) => {
      if (input === "/api/health") {
        return new Response(JSON.stringify(healthResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      expect(input).toBe("/api/audit/occurrences");
      expect(init?.method).toBe("POST");
      const request = JSON.parse(String(init?.body)) as {
        idempotency_key: string;
        occurrence_kind: string;
        outcome_code: string;
      };
      expect(request.idempotency_key).toBe(
        "core-boot-health-v1:CORE_READY_GEMINI_DEGRADED",
      );
      expect(request.occurrence_kind).toBe("BOOT_HEALTH_CHECK");
      expect(request.outcome_code).toBe("CORE_READY_GEMINI_DEGRADED");

      return new Response(
        JSON.stringify({
          result: "CREATED",
          occurrence_id: "occurrence-1",
          event_seq: 1,
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core ready with Gemini-only drafting unavailable",
    );
    expect(screen.getByText("Process liveness")).toBeInTheDocument();
    expect(screen.getByText("Core readiness")).toBeInTheDocument();
    expect(screen.getByText("Audit occurrence recorded · event 1")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  test("does not expose an internal error when health is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ code: "CORE_STORE_UNAVAILABLE" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core health is unavailable",
    );
    expect(screen.queryByText("CORE_STORE_UNAVAILABLE")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("keeps health available when the audit write is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async (input) => {
      if (input === "/api/health") {
        return new Response(JSON.stringify(healthResponse), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(null, { status: 503 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Core ready with Gemini-only drafting unavailable",
    );
    expect(screen.getByText("Audit occurrence unavailable")).toBeInTheDocument();
  });
});
