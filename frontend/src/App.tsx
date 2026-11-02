import { useEffect, useState, type FormEvent } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpRight,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileSearch,
  FlaskConical,
  Gauge,
  Layers3,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  X
} from "lucide-react";

import {
  API,
  api,
  date,
  displayRunStatus,
  fallbackPersonas,
  isRunActive,
  type Analysis,
  type Capabilities,
  type Persona,
  type Run,
  type Worker
} from "./api";

import PersonaPanel from "./components/PersonaPanel";
import UploadPanel from "./components/UploadPanel";
import RunsTable from "./components/RunsTable";
import FindingCard from "./components/FindingCard";
import ScoreRing from "./components/ScoreRing";
import RunDetailView from "./components/RunDetailView";
import CapabilityPanel from "./components/CapabilityPanel";
import PlannerPanel from "./components/PlannerPanel";
import SarvamTranslation from "./components/SarvamTranslation";
import { clearPendingApkUpload, getPendingApkUpload, savePendingApkUpload, uploadApkResumable, type SignedApkUploadTicket } from "./storageUpload";
import { isDemoMode, readSession } from "./auth";
import { loadSavedAnalysis, saveAnalysisForSession } from "./reportStore";

const API_DOCS_URL = API || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const previewMode = isDemoMode();

  const [personas, setPersonas] = useState<Persona[]>(fallbackPersonas);
  const [selected, setSelected] = useState("budget-android");
  const [runs, setRuns] = useState<Run[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(() => previewMode ? null : loadSavedAnalysis(readSession()?.user?.id));
  const [logText, setLogText] = useState("");
  const [apk, setApk] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);

  // Keep the latest report across refreshes in this tab only. Reports are
  // scoped to the authenticated user and are never sent to another service.
  useEffect(() => {
    if (analysis && !previewMode) saveAnalysisForSession(readSession()?.user?.id, analysis);
  }, [analysis]);


  const currentTab = location.pathname.startsWith("/runs")
    ? "runs"
    : location.pathname.startsWith("/analysis")
    ? "analysis"
    : "overview";

  async function refresh(silent = false) {
    if (!silent) setLoading(true);
    try {
      const [p, capabilityContract] = await Promise.all([
        api<{ items: Persona[] }>("/api/v1/personas"),
        api<Capabilities>("/api/v1/capabilities")
      ]);
      setPersonas(p.items);
      setCapabilities(capabilityContract);
      setApiStatus("online");
      setError("");

      // Guest preview is limited to public personas and planning. Do not call
      // protected run-history or worker endpoints and create avoidable 401s.
      if (previewMode) {
        setRuns([]);
        setWorkers([]);
        setNotice("");
      } else {
        // Operational history is database-backed, while personas and planning
        // remain useful without a configured production database. Do not let a
        // 503 from history/status endpoints make the entire dashboard look offline.
        const [runResult, workerResult] = await Promise.allSettled([
          api<{ items: Run[] }>("/api/v1/runs"),
          api<{ items: Worker[] }>("/api/v1/workers")
        ]);
        setRuns(runResult.status === "fulfilled" ? runResult.value.items : []);
        setWorkers(workerResult.status === "fulfilled" ? workerResult.value.items : []);
        if (capabilityContract.database_persistence !== true) {
          setNotice("Persistent PostgreSQL is not configured. Risk planning and pasted-log analysis work, but run history, APK registration, and saved reports are unavailable.");
        } else if (runResult.status === "rejected" || workerResult.status === "rejected") {
          setNotice("Some operational data is temporarily unavailable. Refresh to retry.");
        }
      }
    } catch (err) {
      setApiStatus("offline");
      setWorkers([]);
      setCapabilities(null);
      setNotice("");
      setError(
        err instanceof Error && err.message
          ? err.message
          : "API is down or unreachable. Could not connect to backend server."
      );
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void refresh(true);
    }, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const hasActiveRun = runs.some((r) => isRunActive(r.status));

  useEffect(() => {
    if (!hasActiveRun) return;
    const timer = window.setInterval(() => {
      void refresh(true);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveRun]);

  async function submitApk(e: FormEvent) {
    e.preventDefault();
    if (previewMode) {
      setError("APK registration is available only after signing in. The public preview is limited to personas and risk planning.");
      return;
    }
    setError("");
    setNotice("");
    setBusy(true);
    try {
      if (capabilities?.database_persistence !== true || capabilities?.apk_upload !== true) {
        throw new Error("Run registration is unavailable until production PostgreSQL and private APK storage are configured.");
      }
      if (!apk) throw new Error("Choose an APK file first.");
      let run: Run & { message: string };
      if (capabilities?.direct_apk_upload) {
        if (!globalThis.crypto?.subtle) throw new Error("Secure file hashing is unavailable in this browser.");
        const digest = await crypto.subtle.digest("SHA-256", await apk.arrayBuffer());
        const sha256 = Array.from(new Uint8Array(digest)).map(byte => byte.toString(16).padStart(2, "0")).join("");
        let ticket = getPendingApkUpload(sha256, apk);
        if (!ticket) {
          ticket = await api<SignedApkUploadTicket>("/api/v1/uploads/sign", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: selected, filename: apk.name, size_bytes: apk.size, sha256 })
          });
          savePendingApkUpload(sha256, apk, ticket);
        } else {
          setNotice("Resuming your interrupted APK upload…");
        }
        const uploadProgress = (percentage: number) => {
          setNotice("Uploading APK securely… " + percentage + "%");
        };
        try {
          await uploadApkResumable(apk, sha256, ticket, uploadProgress);
        } catch (uploadError) {
          if (!(uploadError instanceof Error) || !uploadError.message.includes("fresh upload ticket")) throw uploadError;
          clearPendingApkUpload(sha256);
          ticket = await api<SignedApkUploadTicket>("/api/v1/uploads/sign", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: selected, filename: apk.name, size_bytes: apk.size, sha256 })
          });
          savePendingApkUpload(sha256, apk, ticket);
          setNotice("The previous upload expired. Restarting securely with a fresh upload ticket…");
          await uploadApkResumable(apk, sha256, ticket, uploadProgress);
        }
        setNotice("Upload complete. Verifying the private APK and preparing the test…");
        run = await api<Run & { message: string }>(
          "/api/v1/runs/" + encodeURIComponent(ticket.run_id) + "/upload-complete",
          { method: "POST" }
        );
        clearPendingApkUpload(sha256);
      } else {
        if (import.meta.env.PROD && apk.size > 4 * 1024 * 1024) {
          throw new Error("Large APK upload is unavailable until private Supabase Storage is configured. This deployment can accept files up to 4 MB.");
        }
        const body = new FormData();
        body.append("persona_id", selected);
        body.append("apk", apk);
        run = await api<Run & { message: string }>("/api/v1/runs", {
          method: "POST",
          body
        });
      }
      setNotice(run.message);
      setApk(null);
      await refresh();
      navigate("/runs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create run");
    } finally {
      setBusy(false);
    }
  }

  async function analyzeLogs(text = logText) {
    if (!text.trim()) {
      setError("Paste logcat output first.");
      return;
    }
    const startedAt = Date.now();
    let analysisSucceeded = false;
    setBusy(true);
    setAnalysisBusy(true);
    setError("");
    setNotice("");
    try {
      const a = await api<Analysis>("/api/v1/analyze/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, persona_id: selected })
      });
      setAnalysis(a);
      setNotice(a.persistence?.saved === false
        ? "Log analysis complete. Findings reference source lines. This report is only in this browser session and was not saved."
        : "Log analysis complete. Findings reference source lines.");
      analysisSucceeded = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      // Keep the progress indicator visible long enough to communicate the
      // analysis step, without delaying slow requests beyond their real time.
      const remaining = Math.max(0, 700 - (Date.now() - startedAt));
      if (remaining > 0) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, remaining));
      }
      setAnalysisBusy(false);
      setBusy(false);
      if (analysisSucceeded) navigate("/analysis");
    }
  }

  function exportReport() {
    if (!analysis) return;
    const blob = new Blob([JSON.stringify(analysis, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bharatsim-analysis-" + analysis.id.slice(0, 8) + ".json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          style={{ background: "transparent", border: 0, padding: "0 8px 29px", width: "100%", textAlign: "left" }}
          onClick={() => navigate("/")}
        >
          <span className="brand-mark">
            <Activity size={22} />
          </span>
          <span>
            <b>BharatSim</b>
            <small>ANDROID TESTING WORKSPACE</small>
          </span>
        </button>

        <div className="workspace">
          <span className="workspace-icon">B</span>
          <span>
            <b>BharatSim workspace</b>
            <small>Android resilience testing</small>
          </span>
          <ChevronRight size={15} />
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav>
          <button
            className={"nav-item " + (currentTab === "overview" ? "active" : "")}
            onClick={() => navigate("/")}
          >
            <Layers3 size={17} /> Overview
          </button>
          <button
            className={"nav-item " + (currentTab === "runs" ? "active" : "")}
            onClick={() => navigate("/runs")}
          >
            <FlaskConical size={17} /> Test runs{" "}
            <span className="nav-count">{previewMode ? "LOCKED" : runs.length}</span>
          </button>
          <button
            className={"nav-item " + (currentTab === "analysis" ? "active" : "")}
            onClick={() => navigate("/analysis")}
          >
            <FileSearch size={17} /> Log analysis
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="worker-card">
            <span
              className={
                "pulse-dot " +
                (workers.some((w) => w.online) ? "worker-online" : "")
              }
            />
            <div>
              <b>Execution worker</b>
              <small>
                {previewMode
                  ? "Private operational status"
                  : workers.some((w) => w.online)
                    ? workers.filter((w) => w.online).length +
                      " heartbeat(s) · " +
                      (workers.some((w) => w.status === "running") ? "running" : "idle")
                    : "No recent heartbeat"}
              </small>
            </div>
            <span className="status-pill">
              {previewMode ? "LOCKED" : workers.some((w) => w.online) ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <p>
            {previewMode
              ? "Worker heartbeats and private run details require a signed-in account."
              : workers.some((w) => w.online)
                ? "A worker heartbeat was received recently. Run status still depends on its actual report."
                : "APK execution waits until an authenticated, isolated Android worker connects."}
          </p>
          <a
            href={API_DOCS_URL + "/docs"}
            target="_blank"
            rel="noreferrer"
          >
            API documentation <ArrowUpRight size={13} />
          </a>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <ChevronRight size={14} />
            {location.pathname.startsWith("/runs/") ? (
              <>
                <button
                  className="text-button"
                  style={{ padding: 0, color: "inherit" }}
                  onClick={() => navigate("/runs")}
                >
                  Test runs
                </button>
                <ChevronRight size={14} /> <b>Run evidence</b>
              </>
            ) : (
              <b>
                {currentTab === "overview"
                  ? "Overview"
                  : currentTab === "runs"
                  ? "Test runs"
                  : "Log analysis"}
              </b>
            )}
          </div>
          <div className="top-actions">
            <span className={"api-state " + apiStatus}>
              <span /> API{" "}
              {apiStatus === "online"
                ? "connected"
                : apiStatus === "offline"
                ? "unavailable"
                : "checking"}
            </span>
            <button
              className="icon-button"
              onClick={() => void refresh()}
              aria-label="Refresh data"
              disabled={loading}
            >
              <RefreshCw size={16} className={loading ? "spin" : ""} />
            </button>
            <div className="avatar">BS</div>
          </div>
        </header>

        <div className="content">
          <div className="eyebrow">
            <span className="eyebrow-line" /> ANDROID RESILIENCE INTELLIGENCE{" "}
            <span className="flag">भारत</span>
          </div>

          <section className="hero">
            <div>
              <h1>
                Test Android apps
                <br />
                under <em>real-world constraints.</em>
              </h1>
              <p>
                Configure a test profile, register an APK run, and review the execution evidence. Inspect submitted logcat, compare measured network conditions, and see exactly which device controls were applied, verified, or are not yet supported.
              </p>
              <div className="hero-actions">
                <button
                  className="primary-button"
                  onClick={() => {
                    navigate("/");
                    window.setTimeout(
                      () =>
                        document
                          .getElementById(previewMode ? "risk-planner" : "new-run")
                          ?.scrollIntoView({ behavior: "smooth", block: "center" }),
                      50
                    );
                  }}
                >
                  <FlaskConical size={16} /> {previewMode ? "Explore risk planner" : "Configure a test"} <ArrowUpRight size={15} />
                </button>
              </div>
            </div>

            <div className="hero-visual">
              <section className="workspace-status-card" aria-label="Live workspace readiness">
                <div className="workspace-status-heading">
                  <span className="workspace-status-kicker">LIVE WORKSPACE</span>
                  <span className={"workspace-status-pill " + apiStatus}>
                    <i /> {apiStatus === "online" ? "Connected" : apiStatus === "offline" ? "Unavailable" : "Checking"}
                  </span>
                </div>
                <h2>Run readiness</h2>
                <p>Current service and worker state, reported by the connected API.</p>
                <div className="workspace-status-grid">
                  <div><small>API</small><b>{apiStatus === "online" ? "Connected" : apiStatus === "offline" ? "Unavailable" : "Checking"}</b></div>
                  <div><small>Execution workers</small><b>{previewMode ? "Private" : workers.filter((worker) => worker.online).length + " online"}</b></div>
                  <div><small>APK upload</small><b>{previewMode ? "Sign-in required" : capabilities ? (capabilities.apk_upload ? "Available" : "Unavailable") : "Checking"}</b></div>
                  <div><small>APK execution</small><b>{capabilities ? (capabilities.android_execution ? "Enabled" : "Disabled") : "Checking"}</b></div>
                </div>
                <div className="workspace-status-foot">
                  <ShieldCheck size={16} />
                  <span>{capabilities?.notes?.[0] || "Capabilities appear here after the API responds. No sample execution metrics are shown."}</span>
                </div>
              </section>
            </div>
          </section>

          {error && (
            <div className="alert error-alert" role="alert">
              <CircleAlert size={17} />
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          )}

          {notice && (
            <div className="alert notice-alert" role="status" aria-live="polite">
              <CheckCircle2 size={17} />
              <span>{notice}</span>
              <button onClick={() => setNotice("")} aria-label="Dismiss notice">
                <X size={15} />
              </button>
            </div>
          )}

          <section className="metric-grid">
            <div className="metric-card">
              <div className="metric-heading">
                TEST PROFILES <Smartphone size={17} />
              </div>
              <div className="metric-value">
                {personas.length}
                <span className="metric-unit"> profiles</span>
              </div>
              <div className="metric-foot">
                <span className="mini-bars">
                  <i />
                  <i />
                  <i />
                  <i />
                </span>{" "}
                {apiStatus === "online"
                  ? "Profiles loaded from connected API"
                  : apiStatus === "offline"
                  ? "Local reference templates · not live device data"
                  : "Waiting for API profile data"}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-heading">
                TEST RUNS <FlaskConical size={17} />
              </div>
              <div className="metric-value">
                {previewMode ? "Private" : runs.length}
                <span className="metric-unit">{previewMode ? " history" : " recorded"}</span>
              </div>
              <div className="metric-foot">
                <span className="metric-neutral" /> {previewMode ? "Sign in to view private test runs" : "No synthetic execution results"}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-heading">
                LOG FINDINGS <FileSearch size={17} />
              </div>
              <div className="metric-value">
                {analysis ? analysis.summary.finding_count : "—"}
                <span className="metric-unit">
                  {analysis ? " detected" : " run analysis"}
                </span>
              </div>
              <div className="metric-foot">
                <span className="metric-neutral" />{" "}
                {analysis
                  ? analysis.summary.critical + " critical signals"
                  : "Evidence-first diagnostics"}
              </div>
            </div>

            <div className="metric-card score-card">
              <div className="metric-heading">
                BHARATSCORE <Gauge size={17} />
              </div>
              <div className="metric-value">
                {analysis ? analysis.bharat_score.value : "—"}
                <span className="metric-unit"> / 100</span>
              </div>
              <div className="metric-foot">
                <span className="score-dot" />{" "}
                {analysis ? "Log heuristic score" : "Calculated from evidence"}
              </div>
            </div>
          </section>

          <Routes>
            {/* Overview route */}
            <Route
              path="/"
              element={
                <div className="dashboard-grid">
                  <PersonaPanel
                    personas={personas}
                    selected={selected}
                    setSelected={setSelected}
                    apiStatus={apiStatus}
                    loading={loading}
                  />

                  <UploadPanel
                    apk={apk}
                    setApk={setApk}
                    selected={selected}
                    setSelected={setSelected}
                    personas={personas}
                    workers={workers}
                    busy={busy}
                    apiStatus={apiStatus}
                    directUploadAvailable={!previewMode && capabilities?.database_persistence === true && capabilities?.direct_apk_upload === true}
                    uploadAvailable={!previewMode && capabilities?.database_persistence === true && capabilities?.apk_upload === true}
                    lockedReason={previewMode
                      ? "Public preview is read-only for private APK operations. Sign in to register APK runs."
                      : "Run registration is unavailable until production PostgreSQL and private APK storage are configured."}
                    onSubmit={submitApk}
                  />

                  <PlannerPanel selected={selected} />

                  <section className="panel log-panel">
                    <div className="panel-heading">
                      <div>
                        <div className="section-kicker">03 / EVIDENCE ANALYSIS</div>
                        <h2>Inspect logcat</h2>
                        <p>Detect crash, ANR, memory, network and storage signals.</p>
                      </div>
                      <div className="panel-icon">
                        <FileSearch size={19} />
                      </div>
                    </div>
                    {previewMode && (
                      <div className="alert preview-info" role="status">
                        <ShieldCheck size={16} />
                        <span>Public preview: explore live personas and the risk planner. Log analysis and report export require a signed-in account.</span>
                      </div>
                    )}
                    <textarea
                      disabled={previewMode}
                      value={logText}
                      onChange={(e) => setLogText(e.target.value)}
                      placeholder="Paste Android logcat output here…"
                      rows={5}
                    />
                    {apiStatus === "online" && capabilities?.analysis_persistence !== true && (
                      <div className="alert error-alert" role="status">
                        <CircleAlert size={16} />
                        <span>Logcat analysis is available, but reports remain in this browser session until persistent PostgreSQL is configured.</span>
                      </div>
                    )}
                    {analysisBusy && (
                      <div className="analysis-progress" role="status" aria-live="polite">
                        <LoaderCircle className="analysis-progress-icon spin" size={19} />
                        <div className="analysis-progress-copy">
                          <b>Analyzing submitted logcat</b>
                          <span>Extracting source-line evidence, grouping repeated failure signals, and preparing your report.</span>
                        </div>
                        <div className="analysis-progress-track" aria-hidden="true"><i /></div>
                      </div>
                    )}
                    <div className="log-actions">
                      <button
                        className="primary-button"
                        disabled={previewMode || busy || apiStatus !== "online" || capabilities?.log_analysis !== true}
                        onClick={() => void analyzeLogs()}
                      >
                        {analysisBusy ? (
                          <LoaderCircle className="spin" size={15} />
                        ) : (
                          <Activity size={15} />
                        )}
                        {" "}
                        {analysisBusy ? "Analyzing evidence…" : "Analyze evidence"}
                      </button>
                    </div>
                    <div className="evidence-note">
                      <ShieldCheck size={15} /> Sample data is illustrative, not device
                      evidence · Deterministic detection · Source-line references
                    </div>
                  </section>

                  <section className="panel recent-panel">
                    <div className="panel-heading">
                      <div>
                        <div className="section-kicker">04 / ACTIVITY</div>
                        <h2>Recent test runs</h2>
                        <p>Run status from the connected API.</p>
                      </div>
                      <button
                        className="text-button"
                        onClick={() => navigate("/runs")}
                      >
                        View all <ArrowUpRight size={13} />
                      </button>
                    </div>
                    {loading && runs.length === 0 ? (
                      <div className="empty-state">
                        <LoaderCircle className="spin" size={24} />
                        <b>Loading test runs…</b>
                        <p>Fetching recent runs from the API.</p>
                      </div>
                    ) : apiStatus === "offline" ? (
                      <div className="alert error-alert" role="alert">
                        <CircleAlert size={16} />
                        <span>API is down or unreachable. Unable to load recent runs.</span>
                      </div>
                    ) : previewMode ? (
                      <div className="empty-state">
                        <div className="empty-icon"><ShieldCheck size={22} /></div>
                        <b>Private run history</b>
                        <p>Sign in to view your saved test runs and worker evidence.</p>
                      </div>
                    ) : capabilities?.database_persistence !== true ? (
                      <div className="empty-state">
                        <div className="empty-icon">
                          <Clock3 size={22} />
                        </div>
                        <b>Run history unavailable</b>
                        <p>Persistent PostgreSQL is not configured for this deployment. No saved run history is being reported.</p>
                      </div>
                    ) : runs.length === 0 ? (
                      <div className="empty-state">
                        <div className="empty-icon">
                          <Clock3 size={22} />
                        </div>
                        <b>No test runs yet</b>
                        <p>
                          Your registered APKs and worker-reported execution results will appear here.
                        </p>
                      </div>
                    ) : (
                      <div className="recent-list">
                        {runs.slice(0, 4).map((r) => (
                          <button
                            key={r.id}
                            className="recent-row"
                            onClick={() => navigate(`/runs/${encodeURIComponent(r.id)}`)}
                          >
                            <span className="recent-file">
                              <Smartphone size={17} />
                            </span>
                            <span className="recent-info">
                              <b>{r.apk_name || "Log / test session"}</b>
                              <small>
                                {date(r.created_at)} · {r.id.slice(0, 8)}
                              </small>
                            </span>
                            <span
                              className={
                                "run-status " +
                                (r.status === "completed"
                                  ? "done"
                                  : r.status === "failed"
                                  ? "failed"
                                  : "pending")
                              }
                            >
                              {displayRunStatus(r.status)}
                            </span>
                            <ChevronRight size={15} />
                          </button>
                        ))}
                      </div>
                    )}
                  </section>

                  <CapabilityPanel capabilities={capabilities} loading={loading} />
                </div>
              }
            />

            {/* Test runs list route */}
            <Route
              path="/runs"
              element={
                <section className="panel full-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="section-kicker">RUN HISTORY</div>
                      <h2>Test sessions</h2>
                      <p>Only worker-confirmed states count as execution results.</p>
                    </div>
                    <button
                      className="icon-button"
                      onClick={() => void refresh()}
                      aria-label="Refresh test runs"
                      disabled={loading}
                    >
                      <RefreshCw size={15} className={loading ? "spin" : ""} />
                    </button>
                  </div>

                  {loading && runs.length === 0 ? (
                    <div className="empty-state">
                      <LoaderCircle className="spin" size={28} />
                      <b>Loading test runs…</b>
                      <p>Fetching test sessions and execution history from the API.</p>
                    </div>
                  ) : apiStatus === "offline" ? (
                    <div className="alert error-alert" role="alert">
                      <CircleAlert size={18} />
                      <span>API is down or unreachable. Unable to load test runs.</span>
                    </div>
                  ) : previewMode ? (
                    <div className="empty-state">
                      <div className="empty-icon"><ShieldCheck size={22} /></div>
                      <b>Private run history</b>
                      <p>Sign in to view saved test runs, worker reports and lifecycle evidence.</p>
                    </div>
                  ) : capabilities?.database_persistence !== true ? (
                    <div className="empty-state">
                      <div className="empty-icon">
                        <FlaskConical size={22} />
                      </div>
                      <b>Run history unavailable</b>
                      <p>Persistent PostgreSQL is not configured for this deployment. No saved run history is being reported.</p>
                    </div>
                  ) : runs.length === 0 ? (
                    <div className="empty-state">
                      <div className="empty-icon">
                        <FlaskConical size={22} />
                      </div>
                      <b>No runs registered</b>
                      <p>Return to Overview to upload an APK and select a persona.</p>
                      <button
                        className="secondary-button"
                        onClick={() => navigate("/")}
                      >
                        Back to overview
                      </button>
                    </div>
                  ) : (
                    <RunsTable runs={runs} personas={personas} />
                  )}
                </section>
              }
            />

            {/* Detailed run view route */}
            <Route
              path="/runs/:id"
              element={previewMode
                ? <section className="panel full-panel"><div className="empty-state"><ShieldCheck size={28} /><b>Private run evidence</b><p>Sign in to open run details, reports and lifecycle events.</p></div></section>
                : <RunDetailView personas={personas} />}
            />

            {/* Log analysis route */}
            <Route
              path="/analysis"
              element={
                <section className="panel full-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="section-kicker">EVIDENCE REPORT</div>
                      <h2>Log analysis results</h2>
                      <p>Findings are heuristic signals, not confirmed root causes.</p>
                    </div>
                    {analysis && (
                      <button className="secondary-button" onClick={exportReport}>
                        <ArrowDownToLine size={15} /> Export JSON
                      </button>
                    )}
                  </div>

                  {busy ? (
                    <div className="empty-state">
                      <LoaderCircle className="spin" size={32} />
                      <b>Analyzing logcat evidence…</b>
                      <p>Running heuristic signal detection against selected persona profile.</p>
                    </div>
                  ) : apiStatus === "offline" ? (
                    <div className="alert error-alert" role="alert">
                      <CircleAlert size={18} />
                      <span>API is down or unreachable. Log analysis service is unavailable.</span>
                    </div>
                  ) : !analysis ? (
                    <div className="empty-state">
                      <div className="empty-icon">
                        {previewMode ? <ShieldCheck size={22} /> : <FileSearch size={22} />}
                      </div>
                      <b>{previewMode ? "Private log analysis" : "No analysis report yet"}</b>
                      <p>
                        {previewMode
                          ? "Sign in to submit logcat, create private reports and export analysis evidence."
                          : "Paste Android logcat in Overview to create a report with source-line evidence."}
                      </p>
                      {!previewMode && <button className="primary-button" onClick={() => navigate("/")}>Open log analyzer</button>}
                    </div>
                  ) : (
                    <>
                      <div className="score-summary">
                        <ScoreRing score={analysis.bharat_score.value} />
                        <div className="score-copy">
                          <span className="section-kicker">
                            BHARATSCORE · {analysis.bharat_score.label.toUpperCase()}
                          </span>
                          <h3>
                            {analysis.summary.clean
                              ? "No known signals detected"
                              : "Signals detected in supplied logs"}
                          </h3>
                          <p>{analysis.bharat_score.method}</p>
                          <small>{analysis.bharat_score.warning}</small>
                        </div>
                        <div className="finding-totals">
                          <span>
                            <b>{analysis.summary.critical}</b>
                            <small>Critical</small>
                          </span>
                          <span>
                            <b>{analysis.summary.high}</b>
                            <small>High</small>
                          </span>
                          <span>
                            <b>{analysis.summary.medium}</b>
                            <small>Medium</small>
                          </span>
                        </div>
                      </div>
                      {analysis.failure_dna ? (
                        <div className="failure-dna-summary">
                          <b>Failure DNA</b>
                          <span>{analysis.failure_dna.group_count} normalized groups</span>
                          <span>{analysis.failure_dna.total_occurrences} marker occurrences</span>
                          {analysis.user_impact ? <strong>Relative investigation priority: {analysis.user_impact.priority_score}/100</strong> : null}
                          <small>Persona/severity ordering only — not an affected-user estimate.</small>
                        </div>
                      ) : null}

                      <div className="finding-list">
                        {analysis.findings.length === 0 ? (
                          <div className="empty-state">
                            <CheckCircle2 size={25} />
                            <b>No known markers found</b>
                            <p>Absence of detected markers does not prove the app is healthy.</p>
                          </div>
                        ) : (
                          analysis.findings.map((f) => (
                            <FindingCard key={f.id} finding={f} />
                          ))
                        )}
                      </div>

                      <div className="limitations">
                        <b>Interpretation limits</b>
                        {analysis.limitations.map((l) => (
                          <p key={l}>• {l}</p>
                        ))}
                      </div>
                      <SarvamTranslation
                        enabled={Boolean(capabilities?.sarvam_translation)}
                        text={[
                          "BharatScore: " + analysis.bharat_score.value + "/100 — " + analysis.bharat_score.label + ".",
                          ...analysis.findings.slice(0, 5).map((finding) => finding.severity + ": " + finding.title + ". " + finding.explanation + " Recommendation: " + finding.recommendation)
                        ].join("\n").slice(0, 2000)}
                      />
                    </>
                  )}
                </section>
              }
            />

            {/* Keep the plural browser URL compatible with the API resource naming. */}
            <Route path="/analyses" element={<Navigate to="/analysis" replace />} />

            {/* Fallback not found route */}
            <Route
              path="*"
              element={
                <section className="panel full-panel">
                  <div className="empty-state">
                    <CircleAlert size={32} />
                    <b>Page not found</b>
                    <p>The screen you are looking for does not exist.</p>
                    <button className="secondary-button" onClick={() => navigate("/")}>
                      Back to overview
                    </button>
                  </div>
                </section>
              }
            />
          </Routes>

          <footer>
            <span>
              <span className="footer-mark">B</span> BharatSim{" "}
              <span className="footer-divider" /> Android resilience testing · evidence-first diagnostics.
            </span>
            <span>
              Evidence over assumptions <span className="footer-green">●</span>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
