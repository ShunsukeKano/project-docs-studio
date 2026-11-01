import { defineConfig } from "@playwright/test";

// Browser tests. They expect a running system: `make e2e` starts a throwaway one (compose.e2e.yaml)
// and removes it afterwards. By default they use the Chrome installed on this machine, so nothing is
// downloaded; set E2E_BROWSER_CHANNEL=chromium to use the browser from `playwright install chromium`.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:13000",
    channel: process.env.E2E_BROWSER_CHANNEL ?? "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  outputDir: "./test-results",
});
