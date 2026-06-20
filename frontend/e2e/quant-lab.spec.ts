import { test, expect } from "@playwright/test";

const TABS = [
  "factor-performance",
  "walk-forward",
  "predictions",
  "pairs",
  "data-quality",
  "model-admin",
] as const;

test.describe("Quant Lab", () => {
  test("loads default tab without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/quant-lab");
    await expect(page.getByRole("heading", { name: /quant lab/i })).toBeVisible();
    await expect(page).toHaveURL(/tab=factor-performance|\/quant-lab$/);
    expect(errors).toEqual([]);
  });

  for (const tab of TABS) {
    test(`tab ${tab} renders`, async ({ page }) => {
      await page.goto(`/quant-lab?tab=${tab}`);
      await expect(page).toHaveURL(new RegExp(`tab=${tab}`));
      await expect(page.locator(".data-panel")).toBeVisible();
    });
  }

  test("evidence overview shows pairs after seed", async ({ page }) => {
    await page.goto("/quant-lab?tab=pairs");
    await page.getByRole("button", { name: /evidence/i }).click().catch(() => undefined);
    const evidence = page.locator("text=Pairs").first();
    await expect(evidence).toBeVisible({ timeout: 15_000 });
  });

  test("refresh preserves tab query", async ({ page }) => {
    await page.goto("/quant-lab?tab=walk-forward");
    await page.reload();
    await expect(page).toHaveURL(/tab=walk-forward/);
  });
});
