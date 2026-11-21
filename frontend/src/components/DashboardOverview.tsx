import {
  Smartphone,
  FlaskConical,
  FileSearch,
  Gauge,
  ArrowUpRight,
  ShieldCheck,
  Clock3,
  ChevronRight,
  Layers3,
  Activity,
  Plus
} from "lucide-react";
import {
  type Persona,
  type Run,
  type Worker,
  type Analysis,
  type Capabilities,
  type EvaluatorScenario,
  date,
  displayRunStatus
} from "../api";

import EvaluatorTourBanner from "./EvaluatorTourBanner";

interface DashboardOverviewProps {
  personas: Persona[];
  runs: Run[];
  workers: Worker[];
  analysis: Analysis | null;
  capabilities: Capabilities | null;
  apiStatus: string;
  previewMode: boolean;
  onNavigateTab: (tab: string) => void;
  onNavigateRun: (id: string) => void;
  onLoadScenario: (scenario: EvaluatorScenario) => void;
}

export default function DashboardOverview({
  personas,
  runs,
  workers,
  analysis,
  capabilities,
  apiStatus,
  previewMode,
  onNavigateTab,
  onNavigateRun,
  onLoadScenario
}: DashboardOverviewProps) {
  const activeWorkersCount = workers.filter((w) => w.online).length;

  return (
    <div className="dashboard-overview-container">
      {/* Evaluator Quick Tour Banner */}
      <EvaluatorTourBanner onLoadScenario={onLoadScenario} />

      {/* KPI Cards Row */}
      <section className="metric-grid">
        <div className="metric-card">
          <div className="metric-heading">
            TEST PROFILES <Smartphone size={16} />
          </div>
          <div className="metric-value">
            {personas.length}
            <span className="metric-unit"> personas</span>
          </div>
          <div className="metric-foot">
            <span className="mini-bars">
              <i /><i /><i /><i />
            </span>
            <span>{apiStatus === "online" ? "Profiles returned by API" : "Built-in profile definitions"}</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-heading">
            TEST EXECUTIONS <FlaskConical size={16} />
          </div>
          <div className="metric-value">
            {previewMode ? "Private" : runs.length}
            <span className="metric-unit">{previewMode ? " mode" : " recorded"}</span>
          </div>
          <div className="metric-foot">
            <span className="metric-neutral" />
            <span>{previewMode ? "Sign in for private history" : runs.filter(r => r.status === "completed").length + " completed runs"}</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-heading">
            ACTIVE WORKERS <Activity size={16} />
          </div>
          <div className="metric-value">
            {previewMode ? "Private" : activeWorkersCount}
            <span className="metric-unit"> online</span>
          </div>
          <div className="metric-foot">
            <span className={"pulse-dot " + (activeWorkersCount > 0 ? "worker-online" : "")} />
            <span>{apiStatus === "offline" ? "Status unavailable" : activeWorkersCount > 0 ? "Heartbeats active" : "Waiting for worker"}</span>
          </div>
        </div>

        <div className="metric-card score-card">
          <div className="metric-heading">
            BHARATSCORE <Gauge size={16} />
          </div>
          <div className="metric-value">
            {analysis ? analysis.bharat_score.value : "—"}
            <span className="metric-unit">{analysis ? " / 100" : " no report"}</span>
          </div>
          <div className="metric-foot">
            <span className="score-dot" />
            <span>{analysis ? analysis.bharat_score.label : "Calculated from submitted evidence"}</span>
          </div>
        </div>
      </section>

      {/* Quick Launch & Action Bar */}
      <div className="quick-actions-bar">
        <button
          type="button"
          className="quick-action-pill primary"
          onClick={() => onNavigateTab("new-test")}
        >
          <Plus size={15} />
          <span>Launch New Test</span>
        </button>

        <button
          type="button"
          className="quick-action-pill"
          onClick={() => onNavigateTab("analysis")}
        >
          <FileSearch size={15} />
          <span>Analyze Android Logcat</span>
        </button>

        <button
          type="button"
          className="quick-action-pill"
          onClick={() => onNavigateTab("compare")}
        >
          <Layers3 size={15} />
          <span>Compare Telemetry Anomaly</span>
        </button>
      </div>

      {/* Main Dashboard Split Grid */}
      <div className="dashboard-grid">
        {/* Left Column: Recent Activity & Executions */}
        <section className="panel recent-panel">
          <div className="panel-heading">
            <div>
              <div className="section-kicker">01 / ACTIVITY STREAM</div>
              <h2>Recent Test Sessions</h2>
              <p>Operational execution history from the connected API.</p>
            </div>
            <button
              type="button"
              className="text-button"
              onClick={() => onNavigateTab("runs")}
            >
              View all runs <ArrowUpRight size={13} />
            </button>
          </div>

          {runs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon"><Clock3 size={24} /></div>
              <b>No test runs registered yet</b>
              <p>Launch a new test run with your APK or load a pre-verified evaluator scenario.</p>
              <button
                type="button"
                className="secondary-button"
                onClick={() => onNavigateTab("new-test")}
              >
                Configure first test
              </button>
            </div>
          ) : (
            <div className="recent-list">
              {runs.slice(0, 5).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="recent-row"
                  onClick={() => onNavigateRun(r.id)}
                >
                  <span className="recent-file"><Smartphone size={16} /></span>
                  <span className="recent-info">
                    <b>{r.apk_name || "Android APK Execution"}</b>
                    <small>{date(r.created_at)} · {r.persona_id} · {r.id.slice(0, 8)}</small>
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
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          )}
        </section>

        {/* Right Column: Platform Readiness & Health */}
        <section className="panel workspace-status-panel">
          <div className="panel-heading">
            <div>
              <div className="section-kicker">02 / WORKSPACE READINESS</div>
              <h2>Service & Worker Status</h2>
              <p>Live health verified through control plane contracts.</p>
            </div>
            <span className={"status-pill " + apiStatus}>
              {apiStatus.toUpperCase()}
            </span>
          </div>

          <div className="workspace-status-grid">
            <div className="status-grid-item">
              <small>API Gateway</small>
              <b className={apiStatus === "online" ? "text-success" : "text-danger"}>
                {apiStatus === "online" ? "Connected" : "Offline"}
              </b>
            </div>
            <div className="status-grid-item">
              <small>Android Workers</small>
              <b>{previewMode ? "Private" : `${activeWorkersCount} online`}</b>
            </div>
            <div className="status-grid-item">
              <small>ML Classifier</small>
              <b className={capabilities?.ml_classifier === true ? "text-success" : "text-danger"}>
                {capabilities?.ml_classifier === true
                  ? "TF-IDF centroid classifier available"
                  : capabilities?.ml_classifier === false
                  ? "Classifier unavailable"
                  : "Capability status unknown"}
              </b>
            </div>
            <div className="status-grid-item">
              <small>Sarvam AI Bulbul</small>
              <b className={
                capabilities?.sarvam_translation === true && capabilities?.sarvam_audio_tts === true
                  ? "text-success"
                  : "text-danger"
              }>
                {capabilities?.sarvam_translation === true && capabilities?.sarvam_audio_tts === true
                  ? "Translation & voice configured"
                  : capabilities?.sarvam_translation === true
                  ? "Translation only · voice unavailable"
                  : capabilities?.sarvam_audio_tts === true
                  ? "Voice only · translation unavailable"
                  : capabilities
                  ? "Provider not configured"
                  : "Capability status unknown"}
              </b>
            </div>
          </div>

          <div className="workspace-status-foot">
            <ShieldCheck size={16} />
            <span>
              {capabilities?.notes?.[0] ||
                "Live capability details are unavailable. Database readiness, tenant isolation and worker execution have not been verified."}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}

