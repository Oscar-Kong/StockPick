import { defineConfig, devices } from "@playwright/test";

const FRONTEND_PORT = process.env.QUANT_LAB_E2E_FRONTEND_PORT ?? "18930";
const BACKEND_PORT = process.env.QUANT_LAB_E2E_BACKEND_PORT ?? "18931";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bash ../scripts/quant-lab-e2e-up.sh",
    url: `http://127.0.0.1:${FRONTEND_PORT}/quant-lab`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
