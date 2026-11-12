import { defineConfig, devices } from "@playwright/test";

const API_PORT = 8018;
const AUTH_PORT = 54500;
const WEB_PORT = 3100;
const JWT_SECRET = "e2e-secret-" + "x".repeat(40);

// The suite runs the REAL admin web and REAL FastAPI + Postgres. Only Supabase Auth is a stand-in
// (e2e/support/mock-supabase.mjs). Chrome comes from the machine (no browser download needed).
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/report" }]],
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/, use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    {
      name: "desktop",
      testMatch: /.*\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 }, storageState: "e2e/.stack/admin.json" },
    },
    {
      name: "tablet",
      testMatch: /(responsive|screenshots)\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 820, height: 1100 }, storageState: "e2e/.stack/admin.json" },
    },
  ],
  webServer: [
    {
      command: `E2E_USERS_FILE=e2e/.stack/users.json MOCK_SUPABASE_PORT=${AUTH_PORT} E2E_JWT_SECRET=${JWT_SECRET} node e2e/support/mock-supabase.mjs`,
      url: `http://127.0.0.1:${AUTH_PORT}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `E2E_JWT_SECRET=${JWT_SECRET} E2E_API_PORT=${API_PORT} bash e2e/support/start-backend.sh`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
    {
      command: `npx next build && npx next start --port ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: {
        NEXT_PUBLIC_SUPABASE_URL: `http://127.0.0.1:${AUTH_PORT}`,
        NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-anon-key",
        NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${API_PORT}/api/v1`,
      },
    },
  ],
});
