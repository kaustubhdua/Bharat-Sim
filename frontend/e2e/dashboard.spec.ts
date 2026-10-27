import { expect, test } from "@playwright/test";

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
