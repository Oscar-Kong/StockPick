import { test, expect } from "@playwright/test";

const LEGACY_TABS = [
  "factor-performance",
  "walk-forward",
  "predictions",
  "pairs",
] as const;

const PRIMARY_SECTIONS = [
  "overview",
  "ideas",
  "experiments",
  "factor-discovery",
  "results",
  "model-monitor",
] as const;

function collectConsoleErrors(page: import("@playwright/test").Page) {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
}

test.describe("Quant Lab", () => {
  test("1. loads overview by default with no console errors", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/quant-lab");
    await expect(page.getByRole("heading", { name: /quant lab/i })).toBeVisible();
    await expect(page).toHaveURL(/section=overview|\/quant-lab$/);
    await expect(page.locator(".data-panel")).toBeVisible();
    expect(errors.filter((e) => !e.includes("favicon"))).toEqual([]);
  });

  for (const section of PRIMARY_SECTIONS) {
    test(`primary section ${section} renders`, async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto(`/quant-lab?section=${section}`);
      await expect(page).toHaveURL(new RegExp(`section=${section}`));
      await expect(page.locator(".data-panel")).toBeVisible();
      // Factor Discovery returns 503 when mining is disabled — UI still renders with banner.
      if (section !== "factor-discovery") {
        expect(errors.filter((e) => !e.includes("favicon"))).toEqual([]);
      }
    });
  }

  for (const tab of LEGACY_TABS) {
    test(`legacy tab ${tab} renders`, async ({ page }) => {
      await page.goto(`/quant-lab?section=legacy&tab=${tab}`);
      await expect(page).toHaveURL(new RegExp(`tab=${tab}`));
      await expect(page.getByText(/Compatibility path for existing experiment tabs/i)).toBeVisible();
    });
  }

  test("2. overview shows research state summary", async ({ page }) => {
    await page.goto("/quant-lab?section=overview");
    await expect(page.getByText(/100|confidence|fresh|stale/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("3. ideas section supports manual create form", async ({ page }) => {
    await page.goto("/quant-lab?section=ideas");
    await expect(page.getByRole("button", { name: /create|new idea|manual/i }).first()).toBeVisible();
  });

  test("4. experiment studio choose step lists templates", async ({ page }) => {
    await page.goto("/quant-lab?section=experiments&step=choose");
    await expect(page.getByText(/walk.?forward|factor|pairs|prediction|similar|portfolio|scan/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("5. results index loads paginated list", async ({ page }) => {
    await page.goto("/quant-lab?section=results");
    await expect(page.locator(".data-panel")).toBeVisible();
    await expect(page.getByText(/results|run|verdict|type/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("6. model monitor section renders health panels", async ({ page }) => {
    await page.goto("/quant-lab?section=model-monitor");
    await expect(page).toHaveURL(/section=model-monitor/);
    await expect(page.getByText(/factor|prediction|data|job|audit|review/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("7. refresh preserves section query", async ({ page }) => {
    await page.goto("/quant-lab?section=ideas");
    await page.reload();
    await expect(page).toHaveURL(/section=ideas/);
  });

  test("8. refresh preserves legacy tab query", async ({ page }) => {
    await page.goto("/quant-lab?section=legacy&tab=walk-forward");
    await page.reload();
    await expect(page).toHaveURL(/tab=walk-forward/);
  });

  test("9. experiment studio configure step via template param", async ({ page }) => {
    await page.goto("/quant-lab?section=experiments&step=configure&template=walk_forward");
    await expect(page).toHaveURL(/template=walk_forward/);
    await expect(page.locator(".data-panel")).toBeVisible();
  });

  test("9b. experiment studio scan_evaluation configure fields", async ({ page }) => {
    await page.goto("/quant-lab?section=experiments&step=configure&template=scan_evaluation");
    await expect(page.getByText(/alphabetical_baseline|stage_a_v2/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("10. results compare query accepted", async ({ page }) => {
    await page.goto("/quant-lab?section=results&compare=run_a,run_b");
    await expect(page).toHaveURL(/compare=run_a/);
    await expect(page.locator(".data-panel")).toBeVisible();
  });

  test("11. partial backend failure shows error state not blank panel", async ({ page }) => {
    await page.route("**/api/v2/research/overview**", (route) =>
      route.fulfill({ status: 503, body: JSON.stringify({ detail: "service unavailable" }) })
    );
    await page.goto("/quant-lab?section=overview");
    await expect(page.getByText(/fail|error|retry|unavailable/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("12. research-only badge visible on overview", async ({ page }) => {
    await page.goto("/quant-lab?section=overview");
    await expect(page.getByText(/research only|validation only|does not change/i).first()).toBeVisible();
  });
});
