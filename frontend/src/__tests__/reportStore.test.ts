import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearSavedAnalysis, loadSavedAnalysis, saveAnalysisForSession } from "../reportStore";
import type { Analysis } from "../api";

const report: Analysis = {
  id: "report-123",
  source: "FATAL EXCEPTION: main",
  evidence_lines: 1,
  findings: [],
  summary: { finding_count: 0, critical: 0, high: 0, medium: 0, clean: true },
  bharat_score: { value: 100, label: "Low risk", method: "heuristic", warning: "Not a guarantee." },
  limitations: [],
  persona: {
    id: "baseline", name: "Baseline", device: "Android 14", ram_mb: 6144,
    storage_free_mb: 8000, network: "good-4g", latency_ms: 35,
    down_kbps: 12000, up_kbps: 3000, packet_loss_pct: 0,
    battery_saver: false, risk: "low", description: "Control profile."
  },
  persistence: { saved: false, reason: "Browser-only report." }
};

describe("tab-scoped analysis report storage", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("restores the latest report after a page refresh in the same tab", () => {
    expect(saveAnalysisForSession("user-a", report)).toBe(true);
    expect(loadSavedAnalysis("user-a")).toEqual(report);
  });

  it("isolates reports between authenticated users", () => {
    saveAnalysisForSession("user-a", report);
    expect(loadSavedAnalysis("user-b")).toBeNull();
  });

  it("rejects malformed and oversized stored values", () => {
    sessionStorage.setItem("bharatsim.analysis.latest.user-a", JSON.stringify({ id: "bad" }));
    expect(loadSavedAnalysis("user-a")).toBeNull();
    sessionStorage.setItem("bharatsim.analysis.latest.user-b", "x".repeat(750_001));
    expect(loadSavedAnalysis("user-b")).toBeNull();
  });

  it("clears only the selected user's report", () => {
    saveAnalysisForSession("user-a", report);
    saveAnalysisForSession("user-b", report);
    clearSavedAnalysis("user-a");
    expect(loadSavedAnalysis("user-a")).toBeNull();
    expect(loadSavedAnalysis("user-b")).toEqual(report);
  });

  it("does not break analysis when browser storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    expect(saveAnalysisForSession("user-a", report)).toBe(false);
  });
});
