import type { Analysis } from "./api";

type PdfLine = { text: string; bold?: boolean; size?: number };

function ascii(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[^\x20-\x7E]/g, "?")
    .replace(/\s+/g, " ")
    .trim();
}

function escapePdf(value: string): string {
  return ascii(value).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function wrap(value: unknown, width = 88): string[] {
  const text = ascii(value);
  if (!text) return [""];
  const words = text.split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if (word.length > width) {
      if (current) lines.push(current);
      for (let offset = 0; offset < word.length; offset += width) {
        const chunk = word.slice(offset, offset + width);
        if (chunk.length === width) lines.push(chunk);
        else current = chunk;
      }
      continue;
    }
    const next = current ? current + " " + word : word;
    if (next.length > width) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [""];
}

function buildLines(report: Analysis): PdfLine[] {
  const lines: PdfLine[] = [];
  const add = (value: unknown, options: Omit<PdfLine, "text"> = {}) => {
    for (const text of wrap(value)) lines.push({ text, ...options });
  };
  const blank = () => lines.push({ text: "" });

  add("BHARATSIM ANDROID EVIDENCE REPORT", { bold: true, size: 15 });
  add("Evidence-led log analysis. Findings are diagnostic signals, not confirmed root causes.", { size: 9 });
  blank();
  add("REPORT METADATA", { bold: true, size: 11 });
  add("Report ID: " + report.id);
  add("Source: " + report.source);
  add("Evidence lines analysed: " + report.evidence_lines);
  add("Generated (UTC): " + new Date().toISOString());
  blank();
  add("BHARAT READINESS SCORE", { bold: true, size: 11 });
  add("Score: " + report.bharat_score.value + " / 100 - " + report.bharat_score.label, { bold: true });
  add("Method: " + report.bharat_score.method);
  add("Caveat: " + report.bharat_score.warning);
  blank();
  add("SUMMARY", { bold: true, size: 11 });
  add("Findings: " + report.summary.finding_count + " | Critical: " + report.summary.critical +
    " | High: " + report.summary.high + " | Medium: " + report.summary.medium);
  add("Repeated occurrences: " + (report.summary.occurrence_count ?? "not reported"));
  add("Clean: " + (report.summary.clean ? "yes" : "no"));
  blank();

  report.findings.forEach((finding, index) => {
    add((index + 1) + ". " + finding.title, { bold: true, size: 11 });
    add("ID: " + finding.id + " | Type: " + finding.kind + " | Severity: " + finding.severity.toUpperCase());
    add("Explanation: " + finding.explanation);
    add("Recommendation: " + finding.recommendation);
    if (finding.occurrence_count !== undefined) add("Occurrences: " + finding.occurrence_count);
    if (finding.ml_classification && typeof finding.ml_classification === "object") {
      add("Classifier: " + finding.ml_classification.category + " (" +
        (finding.ml_classification.confidence * 100).toFixed(1) + "% confidence)");
    }
    if (finding.root_cause_hypothesis?.statement) {
      add("Root-cause hypothesis (unconfirmed): " + finding.root_cause_hypothesis.statement);
    }
    const evidence = Array.isArray(finding.evidence) ? finding.evidence : [];
    if (evidence.length) {
      add("Source evidence:", { bold: true });
      evidence.slice(0, 12).forEach(item => add("Line " + item.line + ": " + item.text));
    }
    if (finding.sarvam_explanation?.developer_fix) add("Developer guidance: " + finding.sarvam_explanation.developer_fix);
    blank();
  });

  add("INTERPRETATION LIMITS", { bold: true, size: 11 });
  add("This report is based only on the submitted log evidence and selected persona. It does not prove that an APK was installed, executed, or measured on a physical device or production emulator.");
  add("A detected marker is not a confirmed root cause. Validate each recommendation against the application's source code and reproducible device evidence.");
  return lines;
}

function buildPageContent(lines: PdfLine[], pageNumber: number, pageCount: number): string {
  const commands = [
    "BT",
    "/F2 15 Tf",
    "50 748 Td",
    "13 TL",
    "(BharatSim Evidence Report) Tj",
    "/F1 8 Tf",
    "T*",
    "(Evidence-led diagnostic summary - not a confirmed app-health certification) Tj",
    "/F1 9 Tf",
    "T*",
  ];
  for (const line of lines) {
    commands.push("/" + (line.bold ? "F2" : "F1") + " " + (line.size ?? 9) + " Tf");
    commands.push("(" + escapePdf(line.text) + ") Tj");
    commands.push("T*");
  }
  commands.push("ET");
  commands.push("BT /F1 8 Tf 50 28 Td (" + escapePdf("Page " + pageNumber + " of " + pageCount) + ") Tj ET");
  return commands.join("\n");
}

/** Create a dependency-free, valid PDF from the current analysis result. */
export function createAnalysisPdf(report: Analysis): Blob {
  const allLines = buildLines(report);
  const pageSize = 49;
  const pages: PdfLine[][] = [];
  for (let index = 0; index < allLines.length; index += pageSize) {
    pages.push(allLines.slice(index, index + pageSize));
  }
  if (!pages.length) pages.push([]);

  const objects: string[] = [];
  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  const pageIds = pages.map((_, index) => 5 + index * 2);
  objects[2] = "<< /Type /Pages /Kids [" + pageIds.map(id => id + " 0 R").join(" ") + "] /Count " + pages.length + " >>";
  objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";
  objects[4] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>";

  pages.forEach((page, index) => {
    const pageId = pageIds[index];
    const contentId = pageId + 1;
    const stream = buildPageContent(page, index + 1, pages.length);
    objects[pageId] = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents " + contentId + " 0 R >>";
    objects[contentId] = "<< /Length " + stream.length + " >>\nstream\n" + stream + "\nendstream";
  });

  let output = "%PDF-1.4\n%BharatSim\n";
  const offsets: number[] = [0];
  for (let id = 1; id < objects.length; id++) {
    offsets[id] = output.length;
    output += id + " 0 obj\n" + objects[id] + "\nendobj\n";
  }
  const xrefOffset = output.length;
  output += "xref\n0 " + objects.length + "\n";
  output += "0000000000 65535 f \n";
  for (let id = 1; id < objects.length; id++) {
    output += String(offsets[id]).padStart(10, "0") + " 00000 n \n";
  }
  output += "trailer\n<< /Size " + objects.length + " /Root 1 0 R >>\n";
  output += "startxref\n" + xrefOffset + "\n%%EOF";
  return new Blob([output], { type: "application/pdf" });
}

export function downloadAnalysisPdf(report: Analysis): void {
  const blob = createAnalysisPdf(report);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "bharatsim-analysis-" + report.id.slice(0, 8) + ".pdf";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
