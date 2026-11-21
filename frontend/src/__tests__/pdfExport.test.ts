import { describe, expect, it } from "vitest";
import type { Analysis } from "../api";
import { createAnalysisPdf } from "../pdfExport";

const report: Analysis = {
  id: "pdf-report-12345678",
  source: "FATAL EXCEPTION: main",
  evidence_lines: 2,
  findings: [{
    id: "finding-1",
    kind: "oom",
    title: "Out of memory during image allocation",
    severity: "high",
    evidence: [{ line: 2, text: "java.lang.OutOfMemoryError: Failed allocation" }],
    explanation: "The process exhausted its available heap while allocating an image.",
    recommendation: "Downsample large images and bound bitmap cache size.",
    ml_classification: { category: "oom", confidence: 0.93 },
    sarvam_explanation: {
      root_cause: "Heap exhausted",
      impact: "App may be terminated",
      remediation: "Downsample images before decoding.",
    },
  }],
  summary: { finding_count: 1, critical: 0, high: 1, medium: 0, clean: false, occurrence_count: 1 },
  bharat_score: { value: 68, label: "Elevated risk", method: "heuristic", warning: "Not a guarantee." },
  limitations: ["Log markers are not confirmed root causes."],
  persona: {
    id: "budget-android",
    name: "Budget Android",
    device: "Android 11",
    ram_mb: 2048,
    storage_free_mb: 1200,
    network: "edge",
    latency_ms: 450,
    down_kbps: 384,
    up_kbps: 96,
    packet_loss_pct: 8,
    battery_saver: true,
    risk: "high",
    description: "Authored target profile.",
  },
  persistence: { saved: false, reason: "Browser-only report." },
};

describe("PDF evidence export", () => {
  it("creates a valid PDF containing the score, finding and source evidence", async () => {
    const blob = createAnalysisPdf(report);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const text = new TextDecoder().decode(bytes);

    expect(blob.type).toBe("application/pdf");
    expect(text.startsWith("%PDF-1.4")).toBe(true);
    expect(text).toContain("/Type /Catalog");
    expect(text).toContain("Out of memory during image allocation");
    expect(text).toContain("Line 2: java.lang.OutOfMemoryError");
    expect(text).toContain("68 / 100");
    expect(text.trimEnd().endsWith("%%EOF")).toBe(true);
  });

  it("paginates long reports instead of truncating findings", async () => {
    const manyFindings = Array.from({ length: 18 }, (_, index) => ({
      ...report.findings[0],
      id: "finding-" + index,
      title: "Repeated diagnostic finding " + index,
    }));
    const blob = createAnalysisPdf({ ...report, findings: manyFindings });
    const text = await blob.text();
    expect(text).toContain("/Count 2");
    expect(text).toContain("Repeated diagnostic finding 17");
  });
});
