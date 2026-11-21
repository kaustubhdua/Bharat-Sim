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
  type Worker,
  type EvaluatorScenario
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
import EvaluatorTourBanner from "./components/EvaluatorTourBanner";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import LandingPage from "./components/LandingPage";
import DashboardOverview from "./components/DashboardOverview";
import NewTestWizard from "./components/NewTestWizard";
import CompareRunsView from "./components/CompareRunsView";
import SettingsView from "./components/SettingsView";
import { clearPendingApkUpload, getPendingApkUpload, savePendingApkUpload, uploadApkResumable, type SignedApkUploadTicket } from "./storageUpload";
import { enterDemoMode, isDemoMode, readSession } from "./auth";
import { loadSavedAnalysis, saveAnalysisForSession } from "./reportStore";

// API_DOCS_URL kept for future use
const _API_DOCS_URL = API || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
void _API_DOCS_URL;

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

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showEvaluatorModal, setShowEvaluatorModal] = useState(false);

  // Keep the latest report across refreshes in this tab only. Reports are
  // scoped to the authenticated user and are never sent to another service.
  useEffect(() => {
    if (analysis && !previewMode) saveAnalysisForSession(readSession()?.user?.id, analysis);
  }, [analysis]);

  const currentTab = location.pathname.startsWith("/runs")
    ? "runs"
    : location.pathname.startsWith("/analysis")
    ? "analysis"
    : location.pathname.startsWith("/compare")
    ? "compare"
    : location.pathname.startsWith("/new-test")
    ? "new-test"
    : location.pathname.startsWith("/settings")
    ? "settings"
    : location.pathname.startsWith("/landing")
    ? "landing"
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

  async function submitApkFile(targetFile: File) {
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
      let run: Run & { message: string };
      if (capabilities?.direct_apk_upload) {
        if (!globalThis.crypto?.subtle) throw new Error("Secure file hashing is unavailable in this browser.");
        const digest = await crypto.subtle.digest("SHA-256", await targetFile.arrayBuffer());
        const sha256 = Array.from(new Uint8Array(digest)).map(byte => byte.toString(16).padStart(2, "0")).join("");
        let ticket = getPendingApkUpload(sha256, targetFile);
        if (!ticket) {
          ticket = await api<SignedApkUploadTicket>("/api/v1/uploads/sign", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: selected, filename: targetFile.name, size_bytes: targetFile.size, sha256 })
          });
          savePendingApkUpload(sha256, targetFile, ticket);
        } else {
          setNotice("Resuming your interrupted APK upload…");
        }
        const uploadProgress = (percentage: number) => {
          setNotice("Uploading APK securely… " + percentage + "%");
        };
        try {
          await uploadApkResumable(targetFile, sha256, ticket, uploadProgress);
        } catch (uploadError) {
          if (!(uploadError instanceof Error) || !uploadError.message.includes("fresh upload ticket")) throw uploadError;
          clearPendingApkUpload(sha256);
          ticket = await api<SignedApkUploadTicket>("/api/v1/uploads/sign", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: selected, filename: targetFile.name, size_bytes: targetFile.size, sha256 })
          });
          savePendingApkUpload(sha256, targetFile, ticket);
          setNotice("The previous upload expired. Restarting securely with a fresh upload ticket…");
          await uploadApkResumable(targetFile, sha256, ticket, uploadProgress);
        }
        setNotice("Upload complete. Verifying the private APK and preparing the test…");
        run = await api<Run & { message: string }>(
          "/api/v1/runs/" + encodeURIComponent(ticket.run_id) + "/upload-complete",
          { method: "POST" }
        );
        clearPendingApkUpload(sha256);
      } else {
        if (import.meta.env.PROD && targetFile.size > 4 * 1024 * 1024) {
          throw new Error("Large APK upload is unavailable until private Supabase Storage is configured. This deployment can accept files up to 4 MB.");
        }
        const body = new FormData();
        body.append("persona_id", selected);
        body.append("apk", targetFile);
        run = await api<Run & { message: string }>("/api/v1/runs", {
          method: "POST",
          body
        });
      }
      setNotice(run.message);
      setApk(null);
      await refresh();
      navigate(`/runs/${encodeURIComponent(run.id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create run");
    } finally {
      setBusy(false);
    }
  }

  async function submitApk(e: FormEvent) {
    e.preventDefault();
    if (!apk) {
      setError("Choose an APK file first.");
      return;
    }
    await submitApkFile(apk);
  }

  async function analyzeLogs(text = logText, personaId = selected) {
    if (previewMode || (!readSession() && import.meta.env.PROD)) {
      setError("Log analysis is a private workspace feature. Sign in to analyze logs and save or export reports.");
      return;
    }
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
        body: JSON.stringify({ text, persona_id: personaId })
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

  const handleLoadScenario = (scenario: EvaluatorScenario) => {
    setSelected(scenario.persona_id);
    setLogText(scenario.logcat);
    void analyzeLogs(scenario.logcat, scenario.persona_id);
  };

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
      <Sidebar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          if (tab === "overview") navigate("/");
          else navigate(`/${tab}`);
        }}
        workers={workers}
        previewMode={previewMode}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        runsCount={runs.length}
      />

      <main className={"main " + (sidebarCollapsed ? "sidebar-collapsed" : "")}>
        <Topbar
          currentTab={currentTab}
          runId={location.pathname.startsWith("/runs/") ? location.pathname.split("/runs/")[1] : undefined}
          apiStatus={apiStatus}
          loading={loading}
          onRefresh={() => void refresh()}
          onOpenEvaluatorTour={() => setShowEvaluatorModal(true)}
          onNavigateTab={(tab) => {
            if (tab === "overview") navigate("/");
            else navigate(`/${tab}`);
          }}
        />

        <div className="content">
          <div className="eyebrow">
            <span className="eyebrow-line" /> ANDROID RESILIENCE INTELLIGENCE{" "}
            <span className="flag">भारत</span>
          </div>

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

          <Routes>
            {/* Overview route */}
            <Route
              path="/"
              element={
                <div className="overview-page-wrapper">
                  <DashboardOverview
                    personas={personas}
                    runs={runs}
                    workers={workers}
                    analysis={analysis}
                    capabilities={capabilities}
                    apiStatus={apiStatus}
                    previewMode={previewMode}
                    onNavigateTab={(tab) => {
                      if (tab === "overview") navigate("/");
                      else navigate(`/${tab}`);
                    }}
                    onNavigateRun={(id) => navigate(`/runs/${encodeURIComponent(id)}`)}
                    onLoadScenario={handleLoadScenario}
                  />

                  <div className="dashboard-grid" style={{ marginTop: 24 }}>
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
                </div>
              }
            />

            {/* Platform Showcase Landing route */}
            <Route
              path="/landing"
              element={
                <LandingPage
                  onStartTesting={() => navigate("/new-test")}
                  onExplorePlanner={() => {
                    enterDemoMode();
                    navigate("/");
                    window.setTimeout(() => {
                      document.getElementById("risk-planner")?.scrollIntoView({ behavior: "smooth", block: "center" });
                    }, 100);
                  }}
                  onLoadScenario={handleLoadScenario}
                />
              }
            />

            {/* Step-by-Step Test Setup Wizard route */}
            <Route
              path="/new-test"
              element={
                <NewTestWizard
                  personas={personas}
                  selectedPersona={selected}
                  onSelectPersona={setSelected}
                  busy={busy}
                  uploadAvailable={!previewMode && capabilities?.database_persistence === true && capabilities?.apk_upload === true}
                  lockedReason={previewMode ? "Sign in to register and execute private APK runs." : undefined}
                  onSubmit={submitApkFile}
                  onCancel={() => navigate("/")}
                />
              }
            />

            {/* Comparative Telemetry & Anomaly Analysis route */}
            <Route
              path="/compare"
              element={
                previewMode ? (
                  <section className="panel full-panel">
                    <div className="empty-state">
                      <ShieldCheck size={26} />
                      <b>Private run comparison</b>
                      <p>Sign in to compare owner-scoped completed runs.</p>
                    </div>
                  </section>
                ) : capabilities?.run_comparison === true ? (
                  <CompareRunsView runs={runs} onBack={() => navigate("/")} />
                ) : (
                  <section className="panel full-panel">
                    <div className="empty-state">
                      <CircleAlert size={26} />
                      <b>Run comparison unavailable</b>
                      <p>Persistent PostgreSQL is not configured for this deployment. Comparison is disabled rather than generating sample metrics.</p>
                      <button type="button" className="secondary-button" onClick={() => navigate("/")}>Back to overview</button>
                    </div>
                  </section>
                )
              }
            />

            {/* Settings route */}
            <Route
              path="/settings"
              element={<SettingsView capabilities={capabilities} apiStatus={apiStatus} />}
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

      {showEvaluatorModal && (
        <div className="modal-backdrop" onClick={() => setShowEvaluatorModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 840 }}>
            <div className="modal-header">
              <div>
                <span className="section-kicker">EVALUATOR QUICK TOUR</span>
                <h2>Preloaded Live Demonstration Scenarios</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowEvaluatorModal(false)}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ padding: 16 }}>
              <EvaluatorTourBanner
                onLoadScenario={(sc) => {
                  setShowEvaluatorModal(false);
                  handleLoadScenario(sc);
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
