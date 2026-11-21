import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

async function installLocalWorkspaceSession(page: import("@playwright/test").Page) {
  // Non-production UI fixture, used only against the localhost E2E API.
  await page.addInitScript(() => {
    // Seed once per isolated browser context. A localStorage sentinel survives
    // reloads, allowing tests to clear sessionStorage and verify logout/guest gates.
    if (localStorage.getItem("bharatsim.e2e.auth-seeded") === "1") return;
    sessionStorage.setItem("bharatsim.supabase.session", JSON.stringify({
      access_token: "playwright-local-test-token",
      refresh_token: "playwright-local-refresh-token",
      expires_at: 4102444800,
      token_type: "bearer",
      user: { id: "11111111-1111-4111-8111-111111111111", email: "playwright@example.test" },
    }));
    localStorage.setItem("bharatsim.e2e.auth-seeded", "1");
  });
}


test("public preview exposes the live planner but keeps private actions gated", async ({ page }) => {
  // Fresh Playwright context is unauthenticated; this test intentionally uses guest preview.
  await page.goto("/");

  let protectedRequestCount = 0;
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === "/api/v1/runs" || pathname === "/api/v1/workers" || pathname.startsWith("/api/v1/runs/")) {
      protectedRequestCount += 1;
    }
  });
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await page.getByRole("button", { name: /Explore public planner preview/ }).click();

  await expect(page.getByText(/Public preview · live persona and risk planner/)).toBeVisible();
  await expect(page.getByText("API Connected")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bharat personas" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk-first test plan" })).toBeVisible();
  await page.locator("#risk-planner").scrollIntoViewIfNeeded();
  await expect(page.locator("#risk-planner")).toBeInViewport();
  await expect(page.getByPlaceholder("Paste Android logcat output here…")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Analyze evidence" })).toBeDisabled();
  await expect(page.locator('input[type="file"]')).toBeDisabled();
  await expect(page.getByText(/Log analysis and report export require a signed-in account/)).toBeVisible();
  expect(protectedRequestCount).toBe(0);
});

test("dashboard connects to the real API and renders authored profiles", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bharat personas" })).toBeVisible();
  await expect(page.getByText("Budget Android", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Profiles returned by API")).toBeVisible();
  await expect(page.getByText(/These are authored targets, not measurements from physical devices/)).toBeVisible();
  await expect(page.getByText(/Only traffic that uses the Android system proxy is shaped/)).toBeVisible();
  await expect(page.getByText("PACKET LOSS", { exact: true })).toBeVisible();
  await expect(page.getByText("2% target", { exact: true })).toBeVisible();
});

test("log analysis reports findings from submitted evidence and preserves source lines", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.stack || error.message));
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  const input = [
    "01-01 00:00:01.000 100 100 E AndroidRuntime: FATAL EXCEPTION: main",
    "01-01 00:00:01.001 100 100 E AndroidRuntime: java.lang.OutOfMemoryError: Failed allocation",
  ].join("\n");
  await page.getByPlaceholder("Paste Android logcat output here…").fill(input);
  const analysisResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/v1/analyze/logs") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Analyze evidence" }).click();
  const analysisResponse = await analysisResponsePromise;
  const analysisBody = await analysisResponse.text();
  expect(
    analysisResponse.ok(),
    `Log analysis API returned ${analysisResponse.status()}: ${analysisBody}`
  ).toBe(true);
  let analysisPayload: Record<string, unknown>;
  try {
    analysisPayload = JSON.parse(analysisBody) as Record<string, unknown>;
  } catch {
    throw new Error(`Log analysis API returned non-JSON content: ${analysisBody.slice(0, 1000)}`);
  }
  expect(analysisPayload).toHaveProperty("summary");
  expect(analysisPayload).toHaveProperty("bharat_score");
  expect(analysisPayload).toHaveProperty("findings");

  await expect(page).toHaveURL(new RegExp("/analysis$"));
  try {
    await expect(page.getByRole("heading", { name: "Log analysis results" })).toBeVisible();
  } catch (error) {
    const bodyText = await page.locator("body").innerText().catch(() => "<body unavailable>");
    throw new Error(
      `Analysis result screen did not render. URL=${page.url()}\\nPage errors=${pageErrors.join("\\n")}\\nBody=${bodyText.slice(0, 3000)}\\nOriginal=${String(error)}`
    );
  }
  await expect(page.getByText("Signals detected in supplied logs")).toBeVisible();
  await expect(page.getByText(/SOURCE EVIDENCE/).first()).toBeVisible();
  await expect(page.getByText(/FATAL EXCEPTION/).first()).toBeVisible();
  await expect(page.getByText(/Findings are heuristic signals, not confirmed root causes/)).toBeVisible();

  const pdfDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF" }).click();
  const pdfDownload = await pdfDownloadPromise;
  expect(pdfDownload.suggestedFilename()).toMatch(/^bharatsim-analysis-[a-f0-9]{8}\.pdf$/);
  const pdfPath = await pdfDownload.path();
  expect(pdfPath).not.toBeNull();
  const pdfBytes = await readFile(pdfPath!);
  expect(pdfBytes.subarray(0, 8).toString("ascii")).toBe("%PDF-1.4");

  const jsonDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const jsonDownload = await jsonDownloadPromise;
  expect(jsonDownload.suggestedFilename()).toMatch(/^bharatsim-analysis-[a-f0-9]{8}\.json$/);
  const jsonPath = await jsonDownload.path();
  expect(jsonPath).not.toBeNull();
  const jsonPayload = JSON.parse(await readFile(jsonPath!, "utf8"));
  expect(jsonPayload).toHaveProperty("findings");
});

test("run registration is disabled until a real APK is selected", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  const register = page.getByRole("button", { name: /Start test/ });
  await expect(register).toBeDisabled();
  await expect(page.getByText("Choose an APK to enable run registration")).toBeVisible();
  await expect(page.getByRole("button", { name: /Test Runs/i })).toContainText("0");
});

test("Configure a test navigates to the real APK registration form", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByRole("button", { name: /Launch New Test/ }).click();
  await expect(page.getByRole("heading", { name: "Configure Android Resilience Execution" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Select Android APK" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Choose BharatSim Device & Network Persona" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Launch Resilience Test/ })).toBeDisabled();
  const apkPicker = page.getByRole("button", { name: "Choose Android APK file" });
  if (await apkPicker.getAttribute("aria-disabled") === "true") {
    await expect(page.getByText(/Run registration is unavailable until production PostgreSQL and private APK storage are configured/)).toBeVisible();
    await expect(page.locator('input[type="file"]')).toBeDisabled();
  } else {
    await expect(page.locator('input[type="file"]')).toBeEnabled();
    await expect(page.getByText(/Supports .apk packages up to \d+ MB/)).toBeVisible();
  }
  await expect(page.getByRole("button", { name: /Budget Android/ })).toHaveAttribute("aria-pressed", "true");
});
test("dashboard remains usable at narrow mobile widths without horizontal overflow", async ({ page }) => {
  await installLocalWorkspaceSession(page);
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


test("project documentation link points to the canonical GitHub README", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/");
  const docsLink = page.getByRole("link", { name: /Project documentation on GitHub/ });
  const href = await docsLink.getAttribute("href");
  expect(href).toContain("github.com/kaustubhdua/Bharat-Sim#readme");
  expect(href).not.toContain("localhost:8000");
});


test("overview uses live readiness instead of a synthetic device demo", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Service & Worker Status" })).toBeVisible();
  await expect(page.getByText("Live health verified through control plane contracts.")).toBeVisible();
  await expect(page.getByText(/TF-IDF centroid classifier available|Classifier unavailable|Capability status unknown/)).toBeVisible();
  await expect(page.getByText(/TTS & Translation Enabled/)).toHaveCount(0);
  await expect(page.getByText(/Provider not configured|Translation & voice configured|Translation only · voice unavailable|Voice only · translation unavailable|Capability status unknown/)).toBeVisible();
});

test("secure workspace requires sign-in when no session exists", async ({ page }) => {
  // No auth fixture is installed for this test; assert the default guest gate.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("workspace deep links render after direct browser navigation", async ({ page }) => {
  await installLocalWorkspaceSession(page);
  await page.goto("/runs");
  await expect(page).toHaveURL(/runs$/);
  await expect(page.getByRole("heading", { name: "Test sessions" })).toBeVisible();

  // The browser-facing alias is plural; the canonical React route remains /analysis.
  await page.goto("/analyses");
  await expect(page).toHaveURL(/analysis$/);
  await expect(page.getByRole("heading", { name: "Log analysis results" })).toBeVisible();
});


test("workspace sections never overlap at common desktop, tablet and phone widths", async ({ page }) => {
  // Measure stable layout geometry, not intentional staggered entrance transforms.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installLocalWorkspaceSession(page);
  const widths = [320, 375, 520, 720, 768, 1024, 1280, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByText("API connected")).toBeVisible();

    if (width <= 720) {
      const mobileShell = await page.evaluate(() => ({
        sidebarPosition: getComputedStyle(document.querySelector(".sidebar")!).position,
        sidebarWidth: document.querySelector(".sidebar")!.getBoundingClientRect().width,
        mainMarginLeft: Number.parseFloat(getComputedStyle(document.querySelector(".main")!).marginLeft),
        viewport: document.documentElement.clientWidth,
      }));
      expect(mobileShell.sidebarPosition).not.toBe("fixed");
      expect(mobileShell.sidebarWidth).toBeCloseTo(mobileShell.viewport, 0);
      expect(mobileShell.mainMarginLeft).toBe(0);
    }

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
  await installLocalWorkspaceSession(page);
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
  await expect(page.locator(".interaction-item")).toHaveCount(0);
  await expect(page.locator(".planner-caveat")).toHaveCount(0);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export plan JSON/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^bharatsim-risk-plan-fintech\.json$/);
});


test("public product landing is reachable without signing in", async ({ page }) => {
  await page.goto("/landing");
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await expect(page.getByRole("heading", { name: /Test Android Apps Under/ })).toBeVisible();
  await expect(page.getByText(/BHARATSIM 2.0 · THE CHEAP PHONE TEST/)).toBeVisible();
});
