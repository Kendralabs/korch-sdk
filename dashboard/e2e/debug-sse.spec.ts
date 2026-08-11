import { test, expect } from "@playwright/test";

test("debug SSE events", async ({ page }) => {
  await page.goto("/");
  
  // Intercept console to see what the EventSource receives
  const consoleLogs: string[] = [];
  page.on("console", msg => consoleLogs.push(msg.text()));
  
  // Inject a debugging hook before starting
  await page.evaluate(() => {
    const origES = window.EventSource;
    (window as any).EventSource = class extends origES {
      constructor(url: string) {
        super(url);
        this.onmessage = (ev: MessageEvent) => {
          console.log(`[SSE onmessage] type=${ev.type} data=${ev.data?.slice(0, 100)}`);
        };
        this.addEventListener("status_change", (ev: any) => {
          console.log(`[SSE named:status_change] data=${ev.data?.slice(0, 100)}`);
        });
        this.addEventListener("agent_thinking", (ev: any) => {
          console.log(`[SSE named:agent_thinking] data=${ev.data?.slice(0, 100)}`);
        });
      }
    };
  });
  
  // Click scenario2 and start a run  
  await page.locator("#scenario-scenario2").click();
  await page.locator("#objective-input").fill("Say hello");
  await page.locator("#run-btn").click();
  
  // Wait for things to happen
  await page.waitForTimeout(15000);
  
  // Print logs
  for (const log of consoleLogs) {
    if (log.includes("[SSE")) console.log(log);
  }
  
  expect(consoleLogs.some(l => l.includes("[SSE"))).toBe(true);
});
