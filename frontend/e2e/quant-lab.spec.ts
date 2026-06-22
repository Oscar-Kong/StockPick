import { test, expect } from "@playwright/test";

const LEGACY_TABS = [
  "factor-performance",
  "walk-forward",
  "predictions",
  "pairs",
] as const;

test.describe("Quant Lab", () => {
  test("loads overview by default", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/quant-lab");
    await expect(page.getByRole("heading", { name: /quant lab/i })).toBeVisible();
    await expect(page).toHaveURL(/section=overview|\/quant-lab$/);
    expect(errors).toEqual([]);
  });

  for (const tab of LEGACY_TABS) {
    test(`legacy tab ${tab} renders`, async ({ page }) => {
      await page.goto(`/quant-lab?section=legacy&tab=${tab}`);
      await expect(page).toHaveURL(new RegExp(`tab=${tab}`));
      await expect(page.locator(".data-panel")).toBeVisible();
    });
  }

  test("model monitor section renders", async ({ page }) => {
    await page.goto("/quant-lab?section=model-monitor");
    await expect(page).toHaveURL(/section=model-monitor/);
    await expect(page.locator(".data-panel")).toBeVisible();
  });

  test("refresh preserves legacy tab query", async ({ page }) => {
    await page.goto("/quant-lab?section=legacy&tab=walk-forward");
    await page.reload();
    await expect(page).toHaveURL(/tab=walk-forward/);
  });
});
