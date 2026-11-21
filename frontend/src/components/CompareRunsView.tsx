import { useState, useEffect } from "react";
import { GitCompare, AlertTriangle, CheckCircle2, TrendingUp, LoaderCircle, ArrowLeft } from "lucide-react";
import { compareRuns, type ComparisonResult, type Run } from "../api";

interface CompareRunsViewProps {
  runs: Run[];
  onBack: () => void;
}

export default function CompareRunsView({ runs, onBack }: CompareRunsViewProps) {
  const completedRuns = runs.filter((run) => run.status === "completed");
  const [baselineId, setBaselineId] = useState<string>("");
  const [constrainedId, setConstrainedId] = useState<string>("");
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!baselineId && completedRuns.length > 0) {
      const baseline = completedRuns.find((run) => run.persona_id === "baseline") || completedRuns[0];
      setBaselineId(baseline.id);
    }
    if (!constrainedId && completedRuns.length > 1) {
      const constrained = completedRuns.find((run) => run.persona_id !== "baseline" && run.id !== baselineId)
        || completedRuns.find((run) => run.id !== baselineId);
      if (constrained) setConstrainedId(constrained.id);
    }
  }, [runs, baselineId, constrainedId]);

  const handleCompare = async () => {
    if (!baselineId || !constrainedId || baselineId === constrainedId) {
      setError("Please select both a baseline and a constrained run to compare.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await compareRuns(baselineId, constrainedId);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed. Please verify that both runs exist.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel full-panel compare-view-panel">
      <div className="panel-heading">
        <div>
          <button type="button" className="text-button" onClick={onBack} style={{ marginBottom: 8 }}>
            <ArrowLeft size={14} /> Back to dashboard
          </button>
          <div className="section-kicker">COMPARATIVE TELEMETRY</div>
          <h2>Baseline vs. Constrained Anomaly Regression</h2>
          <p>
            Compare only telemetry captured in two completed worker reports. Missing measurements are not imputed; comparison is unavailable when persistent run storage is offline.
          </p>
        </div>
        <div className="panel-icon">
          <GitCompare size={20} />
        </div>
      </div>

      {completedRuns.length < 2 ? (
        <div className="empty-state">
          <div className="empty-icon"><GitCompare size={22} /></div>
          <b>Two completed runs are required</b>
          <p>Only worker-confirmed completed runs with shared measured telemetry can be compared.</p>
        </div>
      ) : (
      <div className="comparison-config-card">
        <div className="comparison-selectors">
          <div className="selector-group">
            <label htmlFor="comp-base-select">Baseline Control Run (Unconstrained)</label>
            <select
              id="comp-base-select"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              {completedRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.apk_name || "APK"} · {r.persona_id} ({r.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>

          <div className="selector-icon">
            <GitCompare size={20} />
          </div>

          <div className="selector-group">
            <label htmlFor="comp-const-select">Constrained Test Run (BharatSim Persona)</label>
            <select
              id="comp-const-select"
              value={constrainedId}
              onChange={(e) => setConstrainedId(e.target.value)}
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.apk_name || "APK"} · {r.persona_id} ({r.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="comparison-action-bar">
          <button
            type="button"
            className="primary-button"
            disabled={loading || !baselineId || !constrainedId}
            onClick={() => void handleCompare()}
          >
            {loading ? <LoaderCircle size={15} className="spin" /> : <GitCompare size={15} />}
            {loading ? "Comparing measured telemetry…" : "Compare measured telemetry"}
          </button>
        </div>
      </div>
      )}

      {error && <div className="alert error-alert">{error}</div>}

      {result && (
        <div className="comparison-results-section">
          <div className={"verdict-banner " + (result.anomaly_detected ? "anomaly-fail" : "anomaly-pass")}>
            <div className="verdict-icon">
              {result.anomaly_detected ? <AlertTriangle size={28} /> : <CheckCircle2 size={28} />}
            </div>
            <div>
              <h3>{result.verdict}</h3>
              <p>{result.details}</p>
              <small>
                Statistical anomaly score: <b>{result.anomaly_score.toFixed(1)}</b> / 100
              </small>
            </div>
          </div>

          <h3>Subsystem Metric Divergence</h3>
          <div className="anomaly-metric-grid">
            {result.anomalies.map((an) => (
              <div key={an.metric} className={"anomaly-card " + an.status}>
                <div className="metric-header">
                  <span>{an.metric.replace(/_/g, " ").toUpperCase()}</span>
                  <span className={"status-tag " + an.status}>
                    {an.status.replace("_", " ").toUpperCase()}
                  </span>
                </div>
                <div className="metric-values">
                  <div className="base-val">
                    <small>Baseline</small>
                    <b>{an.baseline}</b>
                  </div>
                  <div className="arrow">→</div>
                  <div className="const-val">
                    <small>Constrained</small>
                    <b>{an.constrained}</b>
                  </div>
                </div>
                <div className="delta-bar">
                  <TrendingUp size={12} />
                  <span>{an.delta_pct >= 0 ? `+${an.delta_pct}%` : `${an.delta_pct}%`} divergence</span>
                </div>
                {an.explanation && <p className="anomaly-explanation">{an.explanation}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

