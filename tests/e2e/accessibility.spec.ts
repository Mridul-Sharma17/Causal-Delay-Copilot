import { expect, test } from "@playwright/test";

const lockedViewports = [320, 672, 1056, 1312, 1584];

test.describe("Decision Brief accessibility and responsive contract", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Decision journey" })).toBeVisible();
  });

  test("exposes six labelled stages, keyboard movement, and explicit state copy", async ({
    page,
  }) => {
    const navigation = page.getByRole("navigation", { name: "Decision journey" });
    const links = navigation.getByRole("link");

    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Decision journey" })).toBeVisible();
    await expect(links).toHaveCount(6);
    await expect(navigation.getByText(/Status:/)).toHaveCount(6);
    for (const targetId of [
      "stage-risk-intake",
      "stage-eligibility",
      "stage-evidence",
      "stage-actions",
      "stage-draft",
      "stage-audit",
    ]) {
      await expect(page.locator(`#${targetId}`)).toBeAttached();
    }
    await expect(
      page.getByRole("heading", {
        name: "Check whether this subject can support a defensible result",
      }),
    ).toBeVisible();

    const riskLink = navigation.getByRole("link", { name: /Risk intake/ });
    const riskTarget = page.locator("#stage-risk-intake");
    await expect(riskTarget).toBeAttached();
    await riskLink.focus();
    await expect(riskLink).toBeFocused();
    const focusStyle = await riskLink.evaluate((element) => {
      const style = getComputedStyle(element);
      return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
    });
    expect(focusStyle.outlineStyle).not.toBe("none");
    expect(parseFloat(focusStyle.outlineWidth)).toBeGreaterThan(0);
    await page.keyboard.press("Enter");
    await expect(riskTarget).toBeFocused();
    await expect(navigation.locator('[aria-live="polite"]')).toHaveText(
      /Moved to Risk intake\./,
    );
  });

  test("keeps controls at least 48px high without horizontal overflow", async ({ page }) => {
    for (const width of lockedViewports) {
      await page.setViewportSize({ width, height: 900 });

      const dimensions = await page.locator(
        "button:visible, input:visible, select:visible, textarea:visible, summary:visible, .journey-stage-list a:visible",
      ).evaluateAll((elements) =>
        elements.map((element) => Math.round(element.getBoundingClientRect().height)),
      );
      expect(dimensions.length).toBeGreaterThan(0);
      expect(dimensions.every((height) => height >= 48)).toBe(true);

      const overflow = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
      await expect(
        page.getByRole("navigation", { name: "Decision journey" }),
      ).toBeVisible();
    }
  });

  test("honors reduced-motion preference for the journey", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload();
    await expect(page.getByRole("navigation", { name: "Decision journey" })).toBeVisible();

    const scrollBehavior = await page.evaluate(() =>
      getComputedStyle(document.documentElement).scrollBehavior,
    );
    expect(scrollBehavior).toBe("auto");
  });
});
