import { defineConfig } from "@playwright/test";

// Browser-level checks against a RUNNING frontend (E2E_BASE_URL) whose /api proxy points at a
// RUNNING exploration API (E2E_API_URL). Read-only: no investigation is created or stepped.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  // Specs share one backend database (some create records), so run them one at a time.
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    channel: process.env.E2E_BROWSER_CHANNEL ?? "chrome",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
  },
});
