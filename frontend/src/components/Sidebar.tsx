import {
  Layers3,
  FlaskConical,
  FileSearch,
  GitCompare,
  Settings,
  PlusCircle,
  Moon,
  Sun,
  Smartphone,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Flame,
  Mic,
  ShieldCheck,
  Laptop
} from "lucide-react";
import { useTheme } from "../theme";
import { type Worker } from "../api";
import { readSession, signOut } from "../auth";

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  workers: Worker[];
  previewMode: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  runsCount: number;
}

export default function Sidebar({
  currentTab,
  onSelectTab,
  workers,
  previewMode,
  collapsed,
  onToggleCollapse,
  runsCount
}: SidebarProps) {
  const { theme, toggleTheme } = useTheme();
  const session = readSession();
  const onlineWorkers = workers.filter((w) => w.online);
  const isOnline = onlineWorkers.length > 0;

  return (
    <aside className={"sidebar page-enter " + (collapsed ? "collapsed" : "")}>
      {/* Brand Header */}
      <div className="brand">
        <div className="brand-mark">
          <span style={{ background: "linear-gradient(135deg, #7667F8, #9A8BFF)" }}>B</span>
        </div>
        {!collapsed && (
          <div className="brand-copy">
            <b>BharatSim</b>
            <small>THE CHEAP PHONE TEST</small>
          </div>
        )}
        <button
          type="button"
          className="collapse-toggle-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Workspace Indicator */}
      {!collapsed && (
        <div className="workspace-pill">
          <div className="workspace-icon">
            <Smartphone size={14} />
          </div>
          <div className="workspace-copy">
            <b>Production Workspace</b>
            <small>{previewMode ? "Guest Preview" : session?.user?.email || "Enterprise Tier"}</small>
          </div>
        </div>
      )}

      {/* Main Navigation */}
      <div className="nav-label">{!collapsed && "NAVIGATION"}</div>
      <nav className="sidebar-nav">
        <button
          type="button"
          className={"nav-item " + (currentTab === "landing" ? "active" : "")}
          onClick={() => onSelectTab("landing")}
          title="Product Showcase Landing Page"
        >
          <Flame size={17} />
          {!collapsed && <span>Platform Showcase</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "overview" ? "active" : "")}
          onClick={() => onSelectTab("overview")}
          title="Overview & Dashboard"
        >
          <Layers3 size={17} />
          {!collapsed && <span>Overview</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "speak" ? "active" : "")}
          onClick={() => onSelectTab("speak")}
          title="Speak-to-Test with Sarvam AI"
        >
          <Mic size={17} />
          {!collapsed && <span>Speak to Test</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "fixproof" ? "active" : "")}
          onClick={() => onSelectTab("fixproof")}
          title="FixProof: verify a fix"
        >
          <ShieldCheck size={17} />
          {!collapsed && <span>FixProof</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "connect" ? "active" : "")}
          onClick={() => onSelectTab("connect")}
          title="Connect your laptop as a test worker"
        >
          <Laptop size={17} />
          {!collapsed && <span>Connect a Laptop</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "new-test" ? "active" : "")}
          onClick={() => onSelectTab("new-test")}
          title="Configure New Test"
        >
          <PlusCircle size={17} />
          {!collapsed && <span>New Test Run</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "runs" ? "active" : "")}
          onClick={() => onSelectTab("runs")}
          title="Test Execution History"
        >
          <FlaskConical size={17} />
          {!collapsed && (
            <>
              <span>Test Runs</span>
              <span className="nav-count">{previewMode ? "DEMO" : runsCount}</span>
            </>
          )}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "analysis" ? "active" : "")}
          onClick={() => onSelectTab("analysis")}
          title="Logcat & ML Failure Analysis"
        >
          <FileSearch size={17} />
          {!collapsed && <span>Log Analysis</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "compare" ? "active" : "")}
          onClick={() => onSelectTab("compare")}
          title="Compare Telemetry Anomaly"
        >
          <GitCompare size={17} />
          {!collapsed && <span>Run Comparison</span>}
        </button>

        <button
          type="button"
          className={"nav-item " + (currentTab === "settings" ? "active" : "")}
          onClick={() => onSelectTab("settings")}
          title="Settings & Preferences"
        >
          <Settings size={17} />
          {!collapsed && <span>Settings</span>}
        </button>
      </nav>

      {/* Sidebar Footer */}
      <div className="sidebar-bottom">
        {/* Worker Heartbeat Card */}
        {!collapsed && (
          <div className="worker-card">
            <span
              className={"pulse-dot " + (isOnline ? "worker-online" : "")}
              style={{ color: isOnline ? "#36C995" : "#4A5570" }}
            />
            <div>
              <b>Android Worker</b>
              <small>
                {previewMode
                  ? "Operational"
                  : !session
                  ? "Sign in to see status"
                  : isOnline
                  ? `${onlineWorkers.length} heartbeat(s)`
                  : "No recent heartbeat"}
              </small>
            </div>
            <span
              className="status-pill"
              style={
                isOnline
                  ? { background: "rgba(54,201,149,0.1)", color: "#36C995", border: "1px solid rgba(54,201,149,0.3)" }
                  : { background: "rgba(74,85,112,0.15)", color: "#727F98", border: "1px solid rgba(74,85,112,0.3)" }
              }
            >
              {isOnline ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
        )}

        {/* Theme and Account Action Buttons */}
        <div className="sidebar-actions-row">
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            {!collapsed && <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
          </button>

          {!previewMode && !collapsed && (
            <button
              type="button"
              className="signout-btn"
              onClick={() => void signOut().then(() => window.location.reload())}
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
