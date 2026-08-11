import { test, expect } from "@playwright/test";

test("verify SSE events reach frontend", async ({ page }) => {
  await page.goto("/");
  
  // Click scenario2 and start a run  
  await page.locator("#scenario-scenario2").click();
  await page.locator("#objective-input").fill("Say hello world");
  await page.locator("#run-btn").click();
  
  // Wait for completion
  await expect(page.locator(".topbar-status")).toContainText(/Completed|Error/, { timeout: 60000 });
  
  // Check what's in logs
  const logTexts = await page.locator(".log-entry .log-msg").allTextContents();
  console.log("LOG ENTRIES:", JSON.stringify(logTexts.slice(0, 10), null, 2));
  
  const logTags = await page.locator(".log-entry .log-tag").allTextContents();
  console.log("LOG TAGS:", JSON.stringify(logTags.slice(0, 10), null, 2));
  
  expect(logTexts.length).toBeGreaterThan(0);
});
