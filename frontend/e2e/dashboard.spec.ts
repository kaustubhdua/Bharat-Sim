import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // The local API deliberately does not enforce JWTs, but production builds
  // still exercise the same authenticated dashboard gate.
  await page.goto("/");
  await page.evaluate(() => {
    sessionStorage.setItem("bharatsim.supabase.session", JSON.stringify({
      access_token: "playwright-local-test-token",
      refresh_token: "playwright-local-refresh-token",
      expires_at: 4102444800,
      token_type: "bearer",
      user: { id: "11111111-1111-4111-8111-111111111111", email: "playwright@example.test" },
    }));
  });
  await page.reload();
});


test("public preview exposes the live planner but keeps private actions gated", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();

  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await page.getByRole("button", { name: /Explore public planner preview/ }).click();

  await expect(page.getByText(/Public preview · live persona and risk planner/)).toBeVisible();
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bharat personas" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk-first test plan" })).toBeVisible();
  await expect(page.getByPlaceholder("Paste Android logcat output here…")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Analyze evidence" })).toBeDisabled();
  await expect(page.locator('input[type="file"]')).toBeDisabled();
  await expect(page.getByText(/Log analysis and report export require a signed-in account/)).toBeVisible();
});

test("dashboard connects to the real API and renders authored profiles", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bharat personas" })).toBeVisible();
  await expect(page.getByText("Budget Android", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Profiles loaded from connected API/)).toBeVisible();
  await expect(page.getByText(/not measurements from physical devices/)).toBeVisible();
  await expect(page.getByText("PACKET LOSS · NOT APPLIED")).toBeVisible();
  await expect(page.getByText("2% target", { exact: true })).toBeVisible();
});

test("log analysis reports findings from submitted evidence and preserves source lines", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  const input = [
    "01-01 00:00:01.000 100 100 E AndroidRuntime: FATAL EXCEPTION: main",
    "01-01 00:00:01.001 100 100 E AndroidRuntime: java.lang.OutOfMemoryError: Failed allocation",
  ].join("\n");
  await page.getByPlaceholder("Paste Android logcat output here…").fill(input);
  await page.getByRole("button", { name: "Analyze evidence" }).click();

  await expect(page.getByRole("heading", { name: "Log analysis results" })).toBeVisible();
  await expect(page.getByText("Signals detected in supplied logs")).toBeVisible();
  await expect(page.getByText(/SOURCE EVIDENCE/).first()).toBeVisible();
  await expect(page.getByText(/FATAL EXCEPTION/).first()).toBeVisible();
  await expect(page.getByText(/Findings are heuristic signals, not confirmed root causes/)).toBeVisible();
});

test("run registration is disabled until a real APK is selected", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  const register = page.getByRole("button", { name: /Register test run/ });
  await expect(register).toBeDisabled();
  await expect(page.getByText("Choose an APK to enable run registration")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Test runs/ })).toContainText("0");
});

test("Configure a test navigates to the real APK registration form", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByRole("button", { name: /Configure a test/ }).click();
  await expect(page.getByRole("heading", { name: "New test run" })).toBeVisible();
  await expect(page.getByLabel("Testing persona")).toBeVisible();
  await expect(page.getByRole("button", { name: /Register test run/ })).toBeDisabled();
  await expect(page.getByText("Choose an APK to enable run registration")).toBeVisible();
});
test("dashboard remains usable at narrow mobile widths without horizontal overflow", async ({ page }) => {
  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 812 });
    await page.goto("/");
    await expect(page.getByText("API connected")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bharat personas" })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(
      dimensions.document,
      `unexpected horizontal overflow at ${width}px: ${JSON.stringify(dimensions)}`,
    ).toBeLessThanOrEqual(dimensions.viewport);
  }
});


test("API documentation link stays same-origin in production builds", async ({ page }) => {
  await page.goto("/");
  const docsLink = page.getByRole("link", { name: /API documentation/ });
  const href = await docsLink.getAttribute("href");
  expect(href).toMatch(/\/docs$/);
  expect(href).not.toContain("localhost:8000");
});


test("overview uses live readiness instead of a synthetic device demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Run readiness" })).toBeVisible();
  await expect(page.getByText("Current service and worker state, reported by the connected API.")).toBeVisible();
  await expect(page.getByText("Try illustrative sample")).toHaveCount(0);
  await expect(page.getByText("Load illustrative sample")).toHaveCount(0);
  await expect(page.getByText("No sample execution metrics are shown.")).toHaveCount(0);
});

test("secure workspace requires sign-in when no session exists", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.removeItem("bharatsim.supabase.session"));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("workspace deep links render after direct browser navigation", async ({ page }) => {
  await page.goto("/runs");
  await expect(page).toHaveURL(/runs$/);
  await expect(page.getByRole("heading", { name: "Test sessions" })).toBeVisible();

  // The browser-facing alias is plural; the canonical React route remains /analysis.
  await page.goto("/analyses");
  await expect(page).toHaveURL(/analysis$/);
  await expect(page.getByRole("heading", { name: "Log analysis results" })).toBeVisible();
});


test("workspace sections never overlap at common desktop, tablet and phone widths", async ({ page }) => {
  const widths = [320, 375, 520, 720, 768, 1024, 1280, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByText("API connected")).toBeVisible();

    const layout = await page.evaluate(() => {
      const selectors = [".topbar > *", ".sidebar nav > *", ".metric-grid > *", ".dashboard-grid > *"];
      const overlaps: string[] = [];
      const outside: string[] = [];
      for (const selector of selectors) {
        const nodes = Array.from(document.querySelectorAll<HTMLElement>(selector))
          .filter((node) => {
            const rect = node.getBoundingClientRect();
            const style = getComputedStyle(node);
            return style.display !== "none" && rect.width > 0 && rect.height > 0;
          });
        const rects = nodes.map((node) => ({ node, rect: node.getBoundingClientRect() }));
        for (let i = 0; i < rects.length; i++) {
          const { node, rect } = rects[i];
          if (rect.left < -1 || rect.right > document.documentElement.clientWidth + 1) {
            outside.push(selector + ": " + (node.className?.toString() || node.tagName));
          }
          for (let j = i + 1; j < rects.length; j++) {
            const other = rects[j].rect;
            const overlapX = Math.min(rect.right, other.right) - Math.max(rect.left, other.left);
            const overlapY = Math.min(rect.bottom, other.bottom) - Math.max(rect.top, other.top);
            if (overlapX > 1 && overlapY > 1) {
              overlaps.push(selector + ": sibling elements intersect");
            }
          }
        }
      }
      return {
        viewport: document.documentElement.clientWidth,
        document: document.documentElement.scrollWidth,
        overlaps,
        outside,
      };
    });

    expect(layout.document, `horizontal overflow at ${width}px: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.viewport);
    expect(layout.overlaps, `overlapping layout at ${width}px: ${JSON.stringify(layout)}`).toEqual([]);
    expect(layout.outside, `content outside viewport at ${width}px: ${JSON.stringify(layout)}`).toEqual([]);
  }
});


test("risk planner validates journeys and returns a real API-generated plan", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk-first test plan" })).toBeVisible();

  await page.getByLabel("Application category").selectOption("fintech");
  const journeys = page.getByLabel("Critical user journeys");
  const generate = page.getByRole("button", { name: "Generate plan" });
  await journeys.fill("   \n  ");
  await expect(generate).toBeDisabled();
  await expect(page.getByText(/add at least one journey to continue/)).toBeVisible();

  await journeys.fill(Array.from({ length: 11 }, (_, index) => "Journey " + (index + 1)).join("\n"));
  await expect(generate).toBeDisabled();
  await expect(page.getByText(/remove extra journeys to continue/)).toBeVisible();

  await journeys.fill("UPI transfer\nPayment retry");
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect(page.locator(".planner-active-config")).toContainText("2 critical journeys ranked");
  await expect(page.locator(".planner-active-config")).toContainText("Deterministic heuristic");
  await expect(page.getByText(/This ranks tests; it does not execute them or claim a failure/)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export plan JSON/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^bharatsim-risk-plan-fintech\.json$/);
});
