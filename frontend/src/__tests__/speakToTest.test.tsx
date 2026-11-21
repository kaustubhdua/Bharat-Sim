import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import SpeakToTestView from "../components/SpeakToTestView";
import FixProofView from "../components/FixProofView";
import ScenarioResult from "../components/ScenarioResult";
import { runScenarioPayload, type TestSpec } from "../speak";

const spec: TestSpec = {
  spec_id: "STS-0123456789", spec_hash: "0123456789abcdef", request_text: "payment retry", language_detected: "hinglish",
  objective: "Verify a retried payment is not charged twice.", app_hint: "", journey: "payment", journey_description: "",
  persona_id: "budget-android", conditions: ["server_delay", "cpu_throttle"],
  supported_conditions: [{ condition: "server_delay", support: "scenario_only", note: "mock gateway" }],
  unsupported_conditions: [{ condition: "cpu_throttle", support: "unsupported", note: "no per-app throttle" }],
  expected_behaviour: ["Shows pending"], assertions: ["no_duplicate_charge", "session_recovery"],
  machine_checked_assertions: [{ id: "no_duplicate_charge", label: "A retry never charges the user twice" }],
  not_machine_verified: ["session_recovery"], evidence: ["ui_text"], matched_scenario: "upi-pending-retry",
  safety: { flags: [], classification: "controlled-test-only" }, clarifications_needed: [],
  execution: { eligible: true, mode: "scenario", scenario_id: "upi-pending-retry", persona_id: "budget-android", reason: "Runs the scenario." },
  interpreter: { provider: "sarvam", model: "sarvam-105b", request_id: "req-9", latency_ms: 900, fallback: false }
};

const packs = [
  {
    id: "upi-pending-retry", status: "executable", pack: "Janjeevan A: payments", title: "UPI-style payment pending + retry",
    user_problem: "double charge", setup: "mock gateway",
    assertions: [{ id: "no_duplicate_charge", label: "A retry never charges the user twice" }],
    sample_builds: [
      { variant: "original", label: "BharatPay Mock 1.0 (original)", path: "/samples/bharatpay-original.apk" },
      { variant: "fixed", label: "BharatPay Mock 1.1 (fixed)", path: "/samples/bharatpay-fixed.apk" }
    ]
  },
  { id: "gov-form-dropout", status: "planned", pack: "Janjeevan B", title: "Gov form", user_problem: "lost form", reason: "Needs a fixture" }
];

let container: HTMLDivElement;
let root: Root;
const json = (body: unknown, ok = true, status = 200) =>
  Promise.resolve({ ok, status, json: async () => body, blob: async () => new Blob(["PK"]) });

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

function setText(el: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

function button(label: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(label));
  if (!found) throw new Error("button not found: " + label);
  return found as HTMLButtonElement;
}

describe("Speak-to-Test", () => {
  it("interprets a request and shows supported, unsupported and machine-checked items", async () => {
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => (url.includes("/scenarios") ? json({ items: packs }) : json(spec)));
    vi.stubGlobal("fetch", fetchMock);
    const onSubmitRun = vi.fn(async () => undefined);
    await act(async () => {
      root.render(<MemoryRouter><SpeakToTestView personas={[]} previewMode={false} busy={false} onSubmitRun={onSubmitRun} /></MemoryRouter>);
    });
    await act(async () => { setText(container.querySelector("textarea")!, "Mera payment app retry par double charge karta hai"); });
    await act(async () => { button("Create test plan").click(); });
    const text = container.textContent || "";
    expect(text).toContain("Verify a retried payment is not charged twice.");
    expect(text).toContain("not applied: no per-app throttle");
    expect(text).toContain("machine-checked");
    expect(text).toContain("not machine-verified");
    expect(text).toContain("Interpreted by Sarvam sarvam-105b");
    expect(text).toContain("Run BharatPay Mock 1.0 (original)");
    expect(text).toContain("Run BharatPay Mock 1.1 (fixed)");
    expect(text).not.toContain("Needs a fixture");
    expect(text).not.toContain("JANJEEVAN SCENARIO PACKS");
    expect(container.querySelector(".pack-grid")).toBeNull();
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/speak/interpret"));
    expect(JSON.parse(String(call![1]?.body))).toEqual({ text: "Mera payment app retry par double charge karta hai" });

    await act(async () => { button("Run BharatPay Mock 1.0").click(); });
    expect(onSubmitRun).toHaveBeenCalledTimes(1);
    const [file, options] = onSubmitRun.mock.calls[0] as unknown as [File, { personaId: string; scenario: { scenario_id: string } }];
    expect(file.name).toBe("bharatpay-original.apk");
    expect(options.personaId).toBe("budget-android");
    expect(options.scenario.scenario_id).toBe("upi-pending-retry");
  });

  it("shows an API error instead of a plan", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) =>
      url.includes("/scenarios") ? json({ items: [] }) : json({ detail: "Too many AI requests" }, false, 429)));
    await act(async () => {
      root.render(<MemoryRouter><SpeakToTestView personas={[]} previewMode={false} busy={false} onSubmitRun={vi.fn()} /></MemoryRouter>);
    });
    await act(async () => { setText(container.querySelector("textarea")!, "payment retry test"); });
    await act(async () => { button("Create test plan").click(); });
    expect(container.textContent).toContain("Too many AI requests");
  });

  it("stores only the validated spec fields with a run", () => {
    const payload = runScenarioPayload(spec, "upi-pending-retry")!;
    expect(Object.keys(payload.spec!)).not.toContain("interpreter");
    expect(payload.scenario_id).toBe("upi-pending-retry");
    expect(runScenarioPayload(null, null)).toBeNull();
  });
});

describe("FixProof", () => {
  it("asks for two scenario runs when there are none", async () => {
    await act(async () => { root.render(<MemoryRouter><FixProofView runs={[]} previewMode={false} /></MemoryRouter>); });
    expect(container.textContent).toContain("FixProof needs two scenario runs");
  });

  it("renders the verdict and per-assertion comparison", async () => {
    const verdict = {
      verdict: "FIXED_AND_VERIFIED", label: "Fixed and verified", summary: "All 3 assertions pass.",
      preconditions: [{ check: "different builds", passed: true, detail: "sha" }],
      assertions: [{ id: "no_duplicate_charge", label: "A retry never charges the user twice", original: false, candidate: true, candidate_observed: "1 charge" }],
      original: { run_id: "aaaaaaaa-1", apk_sha256: "93d8a5db8c1c" },
      candidate: { run_id: "bbbbbbbb-2", apk_sha256: "e400222ba5eb" }
    };
    vi.stubGlobal("fetch", vi.fn(() => json(verdict)));
    const runs = [
      { id: "bbbbbbbb-2", created_at: "2026-11-21T18:00:00Z", status: "completed", persona_id: "budget-android",
        scenario_id: "upi-pending-retry", scenario_verdict: "pass", apk_name: "bharatpay-fixed.apk" },
      { id: "aaaaaaaa-1", created_at: "2026-11-21T17:50:00Z", status: "completed", persona_id: "budget-android",
        scenario_id: "upi-pending-retry", scenario_verdict: "fail", apk_name: "bharatpay-original.apk" }
    ];
    await act(async () => { root.render(<MemoryRouter><FixProofView runs={runs} previewMode={false} /></MemoryRouter>); });
    const selects = container.querySelectorAll("select");
    expect((selects[0] as HTMLSelectElement).value).toBe("aaaaaaaa-1");
    expect((selects[1] as HTMLSelectElement).value).toBe("bbbbbbbb-2");
    await act(async () => { button("Verify the fix").click(); });
    expect(container.textContent).toContain("FIXED AND VERIFIED");
    expect(container.textContent).toContain("1 charge");
  });
});

describe("Scenario result", () => {
  it("shows measured assertions, the journey and the gateway charge log", async () => {
    const scenario = {
      id: "upi-pending-retry", title: "UPI-style payment pending + retry", pack: "Janjeevan A", status: "completed", verdict: "fail",
      fault_injection: "The mock gateway delays confirmation.",
      assertions: [{ id: "no_duplicate_charge", label: "A retry never charges the user twice", passed: false, observed: "2 charge(s)" }],
      steps: [{ step: "tap Pay" }, { step: "state after timeout", screen: "Payment failed. Please retry." }],
      gateway: {
        charges: [
          { order_id: "ORD-1", idempotency_key: "k1", at: "2026-11-21T17:00:01Z" },
          { order_id: "ORD-1", idempotency_key: "k2", at: "2026-11-21T17:00:08Z" }
        ]
      }
    };
    await act(async () => { root.render(<MemoryRouter><ScenarioResult scenario={scenario} /></MemoryRouter>); });
    const text = container.textContent || "";
    expect(text).toContain("ASSERTIONS FAILED");
    expect(text).toContain("2 charge(s)");
    expect(text).toContain("Payment failed. Please retry.");
    expect(container.querySelectorAll("tbody tr").length).toBe(2);
    expect(text).toContain("The mock gateway delays confirmation.");
  });

  it("explains a blocked scenario", async () => {
    await act(async () => {
      root.render(<MemoryRouter><ScenarioResult scenario={{ id: "upi-pending-retry", status: "blocked", reason: "needs the fixture" }} /></MemoryRouter>);
    });
    expect(container.textContent).toContain("needs the fixture");
  });
});
