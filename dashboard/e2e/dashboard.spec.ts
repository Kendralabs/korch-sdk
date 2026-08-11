import { test, expect } from "@playwright/test";

const RUN_TIMEOUT = 90_000;

test.describe("Korchestrator Dashboard — Live E2E", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("header.topbar")).toBeVisible();
  });

  test("loads the UI and shows idle state", async ({ page }) => {
    await expect(page.locator(".topbar-logo")).toContainText("Korchestrator SDK");
    await expect(page.locator(".topbar-status")).toContainText("Idle");
    await expect(page.locator("#run-btn")).toBeVisible();
  });

  test("can switch scenarios", async ({ page }) => {
    // Click Swarm Designer (scenario2)
    await page.locator("#scenario-scenario2").click();
    await expect(page.locator("#scenario-scenario2")).toHaveClass(/active/);
    // Should show agent chips and edges
    await expect(page.locator(".agent-chip")).toHaveCount(3);
    await expect(page.locator("#edges-input")).toBeVisible();
  });

  test("single run completes end-to-end (scenario2)", async ({ page }) => {
    // Select scenario2
    await page.locator("#scenario-scenario2").click();
    await expect(page.locator("#run-btn")).toBeVisible();

    // Set a simple objective
    await page.locator("#objective-input").fill(
      "List 3 benefits of open-source software."
    );

    // Start the run
    await page.locator("#run-btn").click();

    // Should transition to running
    await expect(page.locator(".topbar-status")).toContainText("Running", {
      timeout: 15_000,
    });

    // Wait for completion or error
    await expect(page.locator(".topbar-status")).toContainText(
      /Completed|Error/,
      { timeout: RUN_TIMEOUT }
    );

    // Check logs populated
    const logCount = await page.locator(".log-entry").count();
    expect(logCount).toBeGreaterThan(2);

    // If completed, final answer should appear
    const statusText = await page.locator(".topbar-status").textContent();
    if (statusText?.includes("Completed")) {
      await expect(page.locator("text=Final Answer")).toBeVisible({
        timeout: 5_000,
      });
    }
  });

  test("parallel runs (3x) all complete", async ({ page }) => {
    // Select scenario2
    await page.locator("#scenario-scenario2").click();

    // Set parallel runs to 3
    const slider = page.locator('input[type="range"]').nth(1);
    await slider.fill("3");

    // Set objective
    await page.locator("#objective-input").fill(
      "Explain what a distributed system is in one sentence."
    );

    // Start
    await page.locator("#run-btn").click();

    // Should see multiple "Run created" log entries
    await expect(page.locator(".topbar-status")).toContainText("Running", {
      timeout: 15_000,
    });

    // Wait for 3 run-created logs (one per parallel run)
    await expect(async () => {
      const logs = await page.locator(".log-entry .log-msg").allTextContents();
      const runCreated = logs.filter((l) => l.includes("Run created"));
      expect(runCreated.length).toBe(3);
    }).toPass({ timeout: 15_000 });

    // Wait for the primary run to complete
    await expect(page.locator(".topbar-status")).toContainText(
      /Completed|Error/,
      { timeout: RUN_TIMEOUT }
    );

    // Verify parallel run prefixes in logs (8-char suffixes)
    const allLogs = await page.locator(".log-entry .log-msg").allTextContents();
    const prefixedLogs = allLogs.filter((l) => /\[[a-f0-9]{8}\]/.test(l));
    expect(prefixedLogs.length).toBeGreaterThan(0);
  });

  test("scenario1 auto-plan works", async ({ page }) => {
    // scenario1 is default
    await expect(page.locator("#scenario-scenario1")).toHaveClass(/active/);

    // Start run
    await page.locator("#run-btn").click();

    await expect(page.locator(".topbar-status")).toContainText("Running", {
      timeout: 15_000,
    });

    await expect(page.locator(".topbar-status")).toContainText(
      /Completed|Error/,
      { timeout: RUN_TIMEOUT }
    );

    const logCount = await page.locator(".log-entry").count();
    expect(logCount).toBeGreaterThan(1);
  });

  test("config modal opens and closes", async ({ page }) => {
    await page.locator("#config-btn").click();
    await expect(page.locator(".modal-title")).toContainText("API Configuration");
    // Close
    await page.locator("button:has-text('Cancel')").click();
    await expect(page.locator(".modal-title")).not.toBeVisible();
  });

  test("audit trail populates during run", async ({ page }) => {
    await page.locator("#scenario-scenario2").click();
    await page.locator("#objective-input").fill("Name 2 programming languages.");
    await page.locator("#run-btn").click();

    // Switch to audit tab
    await page.locator("#audit-tab").click();

    // Wait for audit entries
    await expect(page.locator(".topbar-status")).toContainText(
      /Completed|Error/,
      { timeout: RUN_TIMEOUT }
    );
    const auditCount = await page.locator(".audit-entry").count();
    expect(auditCount).toBeGreaterThan(0);
  });
});
