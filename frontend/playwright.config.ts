import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/health/ready",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        BHARATSIM_DATA_DIR: `/tmp/bharatsim-playwright-e2e-${process.env.GITHUB_RUN_ID || process.pid}`,
        BHARATSIM_WORKER_TOKEN: "ci-test-token-not-for-production-0123456789",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
