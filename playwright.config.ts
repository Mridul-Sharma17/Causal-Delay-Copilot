import { defineConfig } from "@playwright/test";

const externalBaseUrl = process.env.CORE_E2E_BASE_URL;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: externalBaseUrl ?? "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: externalBaseUrl
    ? undefined
    : [
        {
          command:
            "uv --cache-dir .uv-cache run --locked --no-sync uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1",
          url: "http://127.0.0.1:8000/api/health",
          reuseExistingServer: true,
          timeout: 120_000,
        },
        {
          command: "npm.cmd run dev",
          url: "http://127.0.0.1:5173",
          reuseExistingServer: true,
          timeout: 120_000,
        },
      ],
});
