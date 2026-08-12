import { expect, test } from "@playwright/test";

test("shows the real browser rejection boundary without creating an investigation", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByText("Validated reference", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Try the rejected conformance fixture" })
    .click();

  await expect(
    page.getByRole("status").filter({ hasText: "Fail-closed path:" }),
  ).toBeVisible();
  await expect(
    page.getByText("No Investigation Request was created.", { exact: true }),
  ).toBeVisible();
});
