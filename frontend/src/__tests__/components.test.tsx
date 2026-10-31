import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import UploadPanel from "../components/UploadPanel";
import ScoreRing from "../components/ScoreRing";
import FindingCard from "../components/FindingCard";
import PersonaPanel from "../components/PersonaPanel";
import RunsTable from "../components/RunsTable";
import { BrowserRouter } from "react-router-dom";
import { cls, displayRunStatus, fallbackPersonas, isRunActive } from "../api";

describe("api helper utilities", () => {
  it("formats risk classes correctly", () => {
    expect(cls("critical")).toBe("critical");
    expect(cls("high")).toBe("high");
    expect(cls("medium")).toBe("medium");
    expect(cls("low")).toBe("low");
    expect(cls("unknown")).toBe("low");
  });

  it("formats run statuses cleanly", () => {
    expect(displayRunStatus("completed")).toBe("smoke completed");
    expect(displayRunStatus("awaiting_worker")).toBe("awaiting worker");
    expect(displayRunStatus("queued")).toBe("queued for worker");
    expect(displayRunStatus("leased")).toBe("worker running");
    expect(displayRunStatus("custom_state")).toBe("custom state");
  });

  it("identifies active runs for auto-refresh correctly", () => {
    expect(isRunActive("queued")).toBe(true);
    expect(isRunActive("leased")).toBe(true);
    expect(isRunActive("running")).toBe(true);
    expect(isRunActive("awaiting_worker")).toBe(true);
    expect(isRunActive("completed")).toBe(false);
    expect(isRunActive("failed")).toBe(false);
    expect(isRunActive("timed_out")).toBe(false);
  });
});

describe("Components tests with jsdom", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it("ScoreRing renders score value and /100", async () => {
    await act(async () => {
      root.render(<ScoreRing score={88} />);
    });
    expect(container.textContent).toContain("88");
    expect(container.textContent).toContain("/100");
  });

  it("FindingCard renders finding details and evidence", async () => {
    const finding = {
      id: "SIG-01",
      kind: "crash",
      title: "Fatal crash exception",
      severity: "critical",
      evidence: [{ line: 12, text: "FATAL EXCEPTION: main" }],
      explanation: "App died upon launch.",
      recommendation: "Inspect crash stack trace."
    };

    await act(async () => {
      root.render(<FindingCard finding={finding} />);
    });

    expect(container.textContent).toContain("Fatal crash exception");
    expect(container.textContent).toContain("App died upon launch.");
    expect(container.textContent).toContain("L12: FATAL EXCEPTION: main");
    expect(container.textContent).toContain("Inspect crash stack trace.");
  });

  it("UploadPanel disables submit button when apk is null", async () => {
    await act(async () => {
      root.render(
        <UploadPanel
          apk={null}
          setApk={vi.fn()}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="online"
          onSubmit={vi.fn().mockImplementation((e) => e.preventDefault())}
        />
      );
    });

    const button = container.querySelector("button[type='submit']") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("UploadPanel enables submit button when valid apk is passed", async () => {
    const mockFile = new File(["content"], "app.apk", { type: "application/vnd.android.package-archive" });
    await act(async () => {
      root.render(
        <UploadPanel
          apk={mockFile}
          setApk={vi.fn()}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="online"
          onSubmit={vi.fn().mockImplementation((e) => e.preventDefault())}
        />
      );
    });

    const button = container.querySelector("button[type='submit']") as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("UploadPanel rejects non-apk files with inline error message", async () => {
    const setApkMock = vi.fn();
    await act(async () => {
      root.render(
        <UploadPanel
          apk={null}
          setApk={setApkMock}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="online"
          onSubmit={vi.fn().mockImplementation((e) => e.preventDefault())}
        />
      );
    });

    const input = container.querySelector("input[type='file']") as HTMLInputElement;
    const invalidFile = new File(["test"], "notes.txt", { type: "text/plain" });

    await act(async () => {
      Object.defineProperty(input, "files", { value: [invalidFile] });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(setApkMock).toHaveBeenCalledWith(null);
    expect(container.textContent).toContain("Only .apk files are supported");
  });

  it("UploadPanel rejects files larger than 150 MB", async () => {
    const setApkMock = vi.fn();
    await act(async () => {
      root.render(
        <UploadPanel
          apk={null}
          setApk={setApkMock}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="online"
          onSubmit={vi.fn().mockImplementation((e) => e.preventDefault())}
        />
      );
    });

    const input = container.querySelector("input[type='file']") as HTMLInputElement;
    const largeFile = new File([""], "heavy.apk");
    Object.defineProperty(largeFile, "size", { value: 160 * 1024 * 1024 });

    await act(async () => {
      Object.defineProperty(input, "files", { value: [largeFile] });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(setApkMock).toHaveBeenCalledWith(null);
    expect(container.textContent).toContain("exceeds the 150 MB limit");
  });

  it("UploadPanel toggles dragging highlight class", async () => {
    await act(async () => {
      root.render(
        <UploadPanel
          apk={null}
          setApk={vi.fn()}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="online"
          onSubmit={vi.fn().mockImplementation((e) => e.preventDefault())}
        />
      );
    });

    const zone = container.querySelector(".upload-zone") as HTMLLabelElement;

    await act(async () => {
      zone.dispatchEvent(new Event("dragover", { bubbles: true }));
    });
    expect(zone.classList.contains("dragging")).toBe(true);

    await act(async () => {
      zone.dispatchEvent(new Event("dragleave", { bubbles: true }));
    });
    expect(zone.classList.contains("dragging")).toBe(false);
  });
  it("PersonaPanel renders loading state when loading and personas empty", async () => {
    await act(async () => {
      root.render(
        <PersonaPanel
          personas={[]}
          selected=""
          setSelected={vi.fn()}
          apiStatus="checking"
          loading={true}
        />
      );
    });

    expect(container.textContent).toContain("Loading test profiles…");
  });

  it("PersonaPanel renders empty state when not loading and personas empty", async () => {
    await act(async () => {
      root.render(
        <PersonaPanel
          personas={[]}
          selected=""
          setSelected={vi.fn()}
          apiStatus="online"
          loading={false}
        />
      );
    });

    expect(container.textContent).toContain("No personas available");
  });

  it("PersonaPanel displays clear error message when api is offline", async () => {
    await act(async () => {
      root.render(
        <PersonaPanel
          personas={fallbackPersonas}
          selected="budget-android"
          setSelected={vi.fn()}
          apiStatus="offline"
          loading={false}
        />
      );
    });

    expect(container.textContent).toContain("API is down or unreachable. Live test profiles could not be loaded.");
  });

  it("UploadPanel displays clear error message when api is offline", async () => {
    await act(async () => {
      root.render(
        <UploadPanel
          apk={null}
          setApk={vi.fn()}
          selected="budget-android"
          setSelected={vi.fn()}
          personas={fallbackPersonas}
          workers={[]}
          busy={false}
          apiStatus="offline"
          onSubmit={vi.fn()}
        />
      );
    });

    expect(container.textContent).toContain("API is down or unreachable. Run registration is disabled.");
  });

  it("RunsTable renders runs and their statuses", async () => {
    const mockRuns = [
      {
        id: "run-12345678",
        created_at: new Date().toISOString(),
        status: "queued",
        apk_name: "test.apk",
        apk_sha256: "abc1234567890def",
        persona_id: "budget-android"
      }
    ];

    await act(async () => {
      root.render(
        <BrowserRouter>
          <RunsTable runs={mockRuns} personas={fallbackPersonas} />
        </BrowserRouter>
      );
    });

    expect(container.textContent).toContain("test.apk");
    expect(container.textContent).toContain("queued for worker");
    expect(container.textContent).toContain("Budget Android");
  });
});
