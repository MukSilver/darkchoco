import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests", testMatch: "**/*.spec.ts", timeout: 30000,
  use: { baseURL: "http://localhost:4321", locale: "ko-KR" },
  webServer: { command: "npx astro preview --port 4321", url: "http://localhost:4321/", reuseExistingServer: true, timeout: 60000 },
});
