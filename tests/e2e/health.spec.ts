import { expect, test } from "@playwright/test";

test("shows the typed health journey and one audit occurrence", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("status")).toContainText(
    "Core ready with Gemini-only drafting unavailable",
  );
  await expect(page.getByText("Process liveness")).toBeVisible();
  await expect(page.getByText("Core readiness")).toBeVisible();
  await expect(page.getByText(/Audit occurrence recorded · event \d+/)).toBeVisible();
});
