import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import DiagnosisPanel from "../components/DiagnosisPanel";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

const reply = {
  problem: "App crashes on slow network",
  reproduction: { symptom: "crash", symptom_label: "the app crashes or closes", verdict: "REPRODUCED",
    summary: "Yes: the app crashes or closes happened in this run only under your conditions.",
    evidence: [{ id: "R-1", fact: "1 crashes; baseline 0" }] },
  diagnosis: { why: "The feed download throws on timeout and nothing catches it.", fix_steps: ["Catch the timeout", "Show an offline state"],
    code_hint: "try { load() } catch (e: IOException) { showOffline() }", confidence: "medium" },
  cited_evidence: [{ id: "R-1", fact: "1 crashes; baseline 0" }],
  translated_text: "ऐप धीमे नेटवर्क पर बंद हो जाता है।",
  interpreter: { provider: "sarvam", model: "sarvam-105b", request_id: "q1", latency_ms: 800 }
};

describe("Diagnosis panel", () => {
  it("diagnoses the reported problem and shows verdict, cause and fix", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve({ ok: true, status: 200, json: async () => reply }));
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => { root.render(<DiagnosisPanel runId="run-1" runFinished={true} reportedProblem="App crashes on slow network" />); });
    const button = [...container.querySelectorAll("button")].find((b) => b.textContent?.includes("Diagnose"))!;
    await act(async () => { button.click(); });
    const text = container.textContent || "";
    expect(text).toContain("PROBLEM REPRODUCED");
    expect(text).toContain("nothing catches it");
    expect(text).toContain("Show an offline state");
    expect(text).toContain("ऐप धीमे नेटवर्क");
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/runs/run-1/diagnose"))!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ language_code: "hi-IN" });
  });

  it("waits while the run is still executing", async () => {
    await act(async () => { root.render(<DiagnosisPanel runId="run-2" runFinished={false} reportedProblem="slow app" />); });
    const button = [...container.querySelectorAll("button")].find((b) => b.textContent?.includes("Diagnose")) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(container.textContent).toContain("still executing");
  });
});
