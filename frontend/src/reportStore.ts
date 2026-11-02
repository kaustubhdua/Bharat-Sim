import type { Analysis } from "./api";

const KEY_PREFIX = "bharatsim.analysis.latest.";
const MAX_REPORT_BYTES = 750_000;

function storageKey(userId?: string): string {
  // Production reports are scoped to the signed-in user. The anonymous key is
  // only used when auth is intentionally not configured in local development.
  return KEY_PREFIX + encodeURIComponent(userId || "anonymous");
}

function isAnalysis(value: unknown): value is Analysis {
  if (!value || typeof value !== "object") return false;
  const report = value as Partial<Analysis>;
  return typeof report.id === "string"
    && Array.isArray(report.findings)
    && Boolean(report.summary && typeof report.summary === "object")
    && Boolean(report.bharat_score && typeof report.bharat_score === "object")
    && Boolean(report.persona && typeof report.persona === "object");
}

export function loadSavedAnalysis(userId?: string): Analysis | null {
  try {
    const raw = sessionStorage.getItem(storageKey(userId));
    if (!raw || raw.length > MAX_REPORT_BYTES) return null;
    const parsed: unknown = JSON.parse(raw);
    return isAnalysis(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveAnalysisForSession(userId: string | undefined, report: Analysis): boolean {
  try {
    if (!isAnalysis(report)) return false;
    const serialized = JSON.stringify(report);
    if (serialized.length > MAX_REPORT_BYTES) return false;
    sessionStorage.setItem(storageKey(userId), serialized);
    return true;
  } catch {
    // Storage can be disabled or full. Analysis itself must still succeed.
    return false;
  }
}

export function clearSavedAnalysis(userId?: string): void {
  try {
    sessionStorage.removeItem(storageKey(userId));
  } catch {
    // Clearing an unavailable browser store is a no-op.
  }
}
