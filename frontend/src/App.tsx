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
  Cpu,
  FileSearch,
  FlaskConical,
  Gauge,
  Layers3,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  Wifi,
  X
} from "lucide-react";

import {
  API,
  api,
  date,
  demoLog,
  displayRunStatus,
  fallbackPersonas,
  isRunActive,
  type Analysis,
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
  const [loading, setLoading] = useState(true);

  const persona = personas.find((p) => p.id === selected) || fallbackPersonas[0];

  const currentTab = location.pathname.startsWith("/runs")
    ? "runs"
    : location.pathname.startsWith("/analysis")
    ? "analysis"
    : "overview";

  async function refresh(silent = false) {
    if (!silent) setLoading(true);
    try {
      const [p, r, w] = await Promise.all([
        api<{ items: Persona[] }>("/api/v1/personas"),
        api<{ items: Run[] }>("/api/v1/runs"),
        api<{ items: Worker[] }>("/api/v1/workers")
      ]);
      setPersonas(p.items);
      setRuns(r.items);
      setWorkers(w.items);
      setApiStatus("online");
      setError("");
    } catch (err) {
      setApiStatus("offline");
      setWorkers([]);
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
      const body = new FormData();
      body.append("persona_id", selected);
      if (apk) body.append("apk", apk);
      const run = await api<Run & { message: string }>("/api/v1/runs", {
        method: "POST",
        body
      });
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
      setError("Paste logcat output first, or load the sample log.");
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
            <small>THE CHEAP PHONE TEST</small>
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
                Built for the phones
                <br />
                the world <em>actually uses.</em>
              </h1>
              <p>
                Find edge cases worth investigating. Register Android smoke runs, inspect real logcat evidence, and prioritize what to fix. Emulator latency and bandwidth controls are applied and read back; storage pressure and battery-saver simulation are supported on disposable emulators. Packet loss and CPU throttling remain unsupported, RAM is report-only, and arbitrary-app traffic-path verification is not claimed.
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
                <button
                  className="secondary-button"
                  onClick={() => {
                    setLogText(demoLog);
                    void analyzeLogs(demoLog);
                  }}
                >
                  <FileSearch size={16} /> Try illustrative sample
                </button>
              </div>
            </div>

            <div className="hero-visual">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="phone">
                <div className="phone-speaker" />
                <div className="phone-screen">
                  <div className="screen-top">
                    <span>9:41</span>
                    <span>▮ ▴ ▰</span>
                  </div>
                  <div className="phone-logo">
                    <Activity size={19} />
                  </div>
                  <span className="phone-label">ILLUSTRATIVE PROFILE VIEW</span>
                  <b>
                    Testing in
                    <br />
                    the real world.
                  </b>
                  <div className="screen-metric">
                    <span>Selected network profile</span>
                    <b>
                      <i /> {persona.network.replaceAll("-", " ")}
                    </b>
                  </div>
                  <div className="screen-bars">
                    {Array.from({ length: 12 }, (_, i) => (
                      <i key={i} />
                    ))}
                  </div>
                </div>
              </div>
              <div className="float-chip chip-top">
                <Wifi size={15} />
                <span>
                  <b>{persona.latency_ms} ms</b>
                  <small>Requested latency · not verified</small>
                </span>
              </div>
              <div className="float-chip chip-bottom">
                <Cpu size={15} />
                <span>
                  <b>{persona.ram_mb / 1024} GB RAM</b>
                  <small>Profile target · not measured</small>
                </span>
              </div>
              <span className="visual-cross cross-one">✳</span>
              <span className="visual-cross cross-two">✳</span>
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
                    onSubmit={submitApk}
                  />

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
                        className="text-button"
                        onClick={() => setLogText(demoLog)}
                      >
                        Load illustrative sample
                      </button>
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
