import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  outputDir: "test-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:3302",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "uv run --project ../backend --locked python ../backend/tests/browser_api.py",
      url: "http://127.0.0.1:38125/workspace",
      reuseExistingServer: false,
      timeout: 30000,
      env: { ONBOARDING_WEB_ORIGIN: "http://127.0.0.1:3302" },
      gracefulShutdown: { signal: "SIGTERM", timeout: 3000 },
    },
    {
      command: "npm run start -- --hostname 127.0.0.1 --port 3302",
      url: "http://127.0.0.1:3302",
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        ONBOARDING_AGENT_URL: "http://127.0.0.1:38125/agent",
        NEXT_TELEMETRY_DISABLED: "1",
        COPILOTKIT_TELEMETRY_DISABLED: "true",
      },
      gracefulShutdown: { signal: "SIGTERM", timeout: 3000 },
    },
  ],
});
