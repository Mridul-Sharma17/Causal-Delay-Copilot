import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { JourneyStageNav, type JourneyStage } from "./App";

const stages: JourneyStage[] = [
  { key: "risk-intake", label: "Risk intake", targetId: "stage-risk-intake", status: "Ready" },
  { key: "eligibility", label: "Eligibility", targetId: "stage-eligibility", status: "Ready" },
  { key: "evidence", label: "Evidence", targetId: "stage-evidence", status: "Ready" },
  { key: "actions", label: "Actions", targetId: "stage-actions", status: "Read-only" },
  { key: "draft", label: "Draft & decide", targetId: "stage-draft", status: "Unavailable" },
  { key: "audit", label: "Audit replay", targetId: "stage-audit", status: "Replay verified" },
];

afterEach(cleanup);

describe("Decision Brief accessibility seam", () => {
  test("exposes all six stages as labelled keyboard-operable navigation", () => {
    render(
      <>
        <JourneyStageNav stages={stages} />
        <section id="stage-risk-intake" tabIndex={-1} aria-label="Risk intake stage" />
      </>,
    );

    expect(
      screen.getByRole("navigation", { name: "Decision journey" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision journey" })).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(6);
    expect(screen.getByRole("link", { name: /Risk intake.*Ready/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Draft & decide.*Unavailable/ })).toBeInTheDocument();
  });

  test("focuses the target and announces stage movement", () => {
    render(
      <>
        <JourneyStageNav stages={stages} />
        <section id="stage-risk-intake" tabIndex={-1} aria-label="Risk intake stage" />
      </>,
    );

    fireEvent.click(screen.getByRole("link", { name: /Risk intake.*Ready/ }));

    expect(screen.getByLabelText("Risk intake stage")).toHaveFocus();
    expect(screen.getByText("Moved to Risk intake. Ready.")).toBeInTheDocument();
  });

  test("announces an unavailable stage instead of pretending to navigate", () => {
    render(<JourneyStageNav stages={stages} />);

    fireEvent.click(screen.getByRole("link", { name: /Draft & decide.*Unavailable/ }));

    expect(screen.getByText("Draft & decide is unavailable. Unavailable.")).toBeInTheDocument();
  });
});
