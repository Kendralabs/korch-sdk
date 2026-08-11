import { defineConfig } from "@playwright/test";

const ALB_URL =
  process.env.DASHBOARD_URL ??
  "http://korchestrator-dashboard-alb-1152581108.eu-west-2.elb.amazonaws.com";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: ALB_URL,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
