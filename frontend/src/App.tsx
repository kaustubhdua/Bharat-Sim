import { useEffect, useState, type FormEvent } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
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

const API_DOCS_URL = API || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  const [personas, setPersonas] = useState<Persona[]>(fallbackPersonas);
  const [selected, setSelected] = useState("budget-android");
  const [runs, setRuns] = useState<Run[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [logText, setLogText] = useState("");
  const [apk, setApk] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);


  const currentTab = location.pathname.startsWith("/runs")
    ? "runs"
    : location.pathname.startsWith("/analysis")
    ? "analysis"
    : "overview";

  async function refresh(silent = false) {
    if (!silent) setLoading(true);
    try {
      const [p, r, w, capabilityContract] = await Promise.all([
        api<{ items: Persona[] }>("/api/v1/personas"),
        api<{ items: Run[] }>("/api/v1/runs"),
        api<{ items: Worker[] }>("/api/v1/workers"),
        api<Capabilities>("/api/v1/capabilities")
      ]);
      setPersonas(p.items);
      setRuns(r.items);
      setWorkers(w.items);
      setCapabilities(capabilityContract);
      setApiStatus("online");
      setError("");
    } catch (err) {
      setApiStatus("offline");
      setWorkers([]);
      setCapabilities(null);
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
    setError("");
    setNotice("");
    setBusy(true);
    try {
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
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const a = await api<Analysis>("/api/v1/analyze/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, persona_id: selected })
      });
      setAnalysis(a);
      setNotice("Log analysis complete. Findings reference source lines.");
      navigate("/analysis");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
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
            <span className="nav-count">{runs.length}</span>
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
                {workers.some((w) => w.online)
                  ? workers.filter((w) => w.online).length +
                    " heartbeat(s) · " +
                    (workers.some((w) => w.status === "running") ? "running" : "idle")
                  : "No recent heartbeat"}
              </small>
            </div>
            <span className="status-pill">
              {workers.some((w) => w.online) ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <p>
            {workers.some((w) => w.online)
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
                          .getElementById("new-run")
                          ?.scrollIntoView({ behavior: "smooth", block: "center" }),
                      50
                    );
                  }}
                >
                  <FlaskConical size={16} /> Configure a test <ArrowUpRight size={15} />
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
                  <div><small>Execution workers</small><b>{workers.filter((worker) => worker.online).length} online</b></div>
                  <div><small>APK upload</small><b>{capabilities ? (capabilities.apk_upload ? "Available" : "Unavailable") : "Checking"}</b></div>
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
                {runs.length}
                <span className="metric-unit"> recorded</span>
              </div>
              <div className="metric-foot">
                <span className="metric-neutral" /> No synthetic execution results
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
                    directUploadAvailable={Boolean(capabilities?.direct_apk_upload)}
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
                    <textarea
                      value={logText}
                      onChange={(e) => setLogText(e.target.value)}
                      placeholder="Paste Android logcat output here…"
                      rows={5}
                    />
                    <div className="log-actions">
                      <button
                        className="primary-button"
                        disabled={busy}
                        onClick={() => void analyzeLogs()}
                      >
                        {busy ? (
                          <LoaderCircle className="spin" size={15} />
                        ) : (
                          <Activity size={15} />
                        )}
                        {" "}
                        Analyze evidence
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
              element={<RunDetailView personas={personas} />}
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
                        <FileSearch size={22} />
                      </div>
                      <b>No analysis report yet</b>
                      <p>
                        Paste logs in Overview or run the sample analysis to see evidence-linked findings.
                      </p>
                      <button
                        className="primary-button"
                        onClick={() => navigate("/")}
                      >
                        Open log analyzer
                      </button>
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
