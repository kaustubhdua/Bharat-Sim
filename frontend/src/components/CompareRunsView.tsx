import { useState, useEffect } from "react";
import { GitCompare, AlertTriangle, CheckCircle2, TrendingUp, LoaderCircle, ArrowLeft } from "lucide-react";
import { compareRuns, type ComparisonResult, type Run } from "../api";

interface CompareRunsViewProps {
  runs: Run[];
  onBack: () => void;
}

function defaultPair(runs: Run[]): [string, string] {
  // Only completed runs carry a report that can be compared.
  const done = runs.filter((r) => r.status === "completed");
  const base = done.find((r) => r.persona_id === "baseline") || done[1] || done[0];
  const constrained = done.find((r) => r.id !== base?.id && r.persona_id !== "baseline") || done.find((r) => r.id !== base?.id);
  return [base?.id || "", constrained?.id || ""];
}

export default function CompareRunsView({ runs: allRuns, onBack }: CompareRunsViewProps) {
  const runs = allRuns.filter((r) => r.status === "completed");
  const [baselineId, setBaselineId] = useState<string>(() => defaultPair(allRuns)[0]);
  const [constrainedId, setConstrainedId] = useState<string>(() => defaultPair(allRuns)[1]);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (!baselineId || !constrainedId) {
      setError("Please select both a baseline and a constrained run to compare.");
      return;
    }
    if (baselineId === constrainedId) {
      setError("Choose two different runs to compare.");
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

  // Runs can arrive after the first render; pick a default pair once they do.
  useEffect(() => {
    if (!baselineId && !constrainedId && allRuns.length) {
      const [b, c] = defaultPair(allRuns);
      setBaselineId(b);
      setConstrainedId(c);
    }
  }, [allRuns, baselineId, constrainedId]);

  useEffect(() => {
    if (baselineId && constrainedId && baselineId !== constrainedId && !result && !loading) {
      void handleCompare();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baselineId, constrainedId]);

  return (
    <div className="panel full-panel compare-view-panel">
      <div className="panel-heading">
        <div>
          <button type="button" className="text-button" onClick={onBack} style={{ marginBottom: 8 }}>
            <ArrowLeft size={14} /> Back to dashboard
          </button>
          <div className="section-kicker">COMPARATIVE TELEMETRY</div>
          <h2>Baseline vs. Constrained Run Comparison</h2>
          <p>
            Compare measured startup, frame and memory metrics from two completed runs. The comparison uses transparent thresholds and reference-score heuristics; it is not a trained covariance model.
          </p>
        </div>
        <div className="panel-icon">
          <GitCompare size={20} />
        </div>
      </div>

      <div className="comparison-config-card">
        <div className="comparison-selectors">
          <div className="selector-group">
            <label htmlFor="comp-base-select">Baseline Control Run (Unconstrained)</label>
            <select
              id="comp-base-select"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              {runs.map((r) => (
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
            {loading ? "Comparing runs…" : "Compare completed runs"}
          </button>
        </div>
      </div>

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
                Heuristic anomaly score (0–100; not a probability): <b>{result.anomaly_score.toFixed(1)}</b> / 100
              </small>
            </div>
          </div>

          <h3>Metric changes</h3>
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
                  <span>{an.delta_pct >= 0 ? `+${an.delta_pct}%` : `${an.delta_pct}%`} change</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

