import { defineConfig } from "@playwright/test";

/**
 * Real-browser end-to-end tests against the running stack:
 *   docker compose up -d backend worker stream_consumer beat   (API on :8000)
 *   (cd backend && uv run python -m scripts.seed_demo)          (demo accounts + skill)
 *   npm run build                                               (frontend production build)
 *   npm run e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
