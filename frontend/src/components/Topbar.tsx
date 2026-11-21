import {
  ChevronRight,
  RefreshCw,
  Zap
} from "lucide-react";

interface TopbarProps {
  currentTab: string;
  runId?: string;
  apiStatus: string;
  loading: boolean;
  onRefresh: () => void;
  onOpenEvaluatorTour: () => void;
  onNavigateTab: (tab: string) => void;
}

export default function Topbar({
  currentTab,
  runId,
  apiStatus,
  loading,
  onRefresh,
  onOpenEvaluatorTour,
  onNavigateTab
}: TopbarProps) {
  const tabTitles: Record<string, string> = {
    overview: "Overview & Dashboard",
    "new-test": "Configure New Test",
    runs: "Test Runs",
    analysis: "Logcat & ML Analysis",
    compare: "Telemetry Anomaly Comparison",
    landing: "Platform Showcase",
    settings: "Workspace Settings"
  };

  return (
    <header className="topbar">
      <div className="breadcrumbs">
        <button
          type="button"
          className="breadcrumb-link"
          onClick={() => onNavigateTab("overview")}
        >
          Workspace
        </button>
        <ChevronRight size={13} />
        {runId ? (
          <>
            <button
              type="button"
              className="breadcrumb-link"
              onClick={() => onNavigateTab("runs")}
            >
              Test Runs
            </button>
            <ChevronRight size={13} />
            <b className="breadcrumb-current">Run {runId.slice(0, 8)}</b>
          </>
        ) : (
          <b className="breadcrumb-current">{tabTitles[currentTab] || "Overview"}</b>
        )}
      </div>

      <div className="top-actions">
        <a className="api-docs-link" href="/docs" target="_blank" rel="noreferrer" aria-label="API documentation">
          API docs
        </a>
        {/* Evaluator Quick Tour Shortcut Button */}
        <button
          type="button"
          className="evaluator-quick-tour-btn"
          onClick={onOpenEvaluatorTour}
          title="Open Evaluator Quick Tour with 2 preloaded scenarios"
        >
          <Zap size={14} />
          <span>Evaluator Tour</span>
        </button>

        {/* API Status Pill */}
        <span className={"api-state " + apiStatus}>
          <span />
          <span>API {apiStatus === "online" ? "Connected" : apiStatus === "offline" ? "Unavailable" : "Checking"}</span>
        </span>

        {/* Refresh button */}
        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          aria-label="Refresh data"
          disabled={loading}
          title="Refresh operational state"
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
        </button>

        {/* User / Workspace Badge */}
        <div className="avatar" title="BharatSim Active Workspace">
          BS
        </div>
      </div>
    </header>
  );
}

