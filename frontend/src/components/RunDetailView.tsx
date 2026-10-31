import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  CircleAlert,
  Clock3,
  FileSearch,
  Layers3,
  LoaderCircle,
  RefreshCw,
  Trash2,
  ShieldAlert,
  ShieldCheck,
  Wifi
} from "lucide-react";
import {
  api,
  downloadApi,
  displayRunStatus,
  date,
  isRunActive,
  type RunDetail,
  type Persona,
  type WorkerReport,
  type LogSignal,
  type SmokeStep,
  type ConditionRecord
} from "../api";

interface RunDetailViewProps {
  personas: Persona[];
}

function conditionStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    already_satisfied: "Already satisfied before test (no intervention)",
    applied_and_verified: "Applied and verified",
    partially_applied_and_verified: "Partially applied; readback verified",
    partially_applied: "Partially applied",
    partial_failure: "Partial failure",
    unsupported: "Unsupported",
    unverified: "Unverified",
    applied: "Applied",
    failed: "Failed",
    skipped: "Skipped",
    verified: "Verified",
    control_plane_verified: "Control plane verified"
  };
  return labels[status] || status.replaceAll("_", " ");
}

export default function RunDetailView({ personas }: RunDetailViewProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchRun = useCallback(
    async (showLoadingSpinner = true) => {
      if (!id) return;
      if (showLoadingSpinner) setLoading(true);
      try {
        const detail = await api<RunDetail>("/api/v1/runs/" + encodeURIComponent(id));
        setRun(detail);
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load test run");
      } finally {
        if (showLoadingSpinner) setLoading(false);
      }
    },
    [id]
  );

  const handleDownloadReport = async () => {
    if (!id || !run?.result) return;
    setError("");
    try {
      const blob = await downloadApi("/api/v1/runs/" + encodeURIComponent(id) + "/report");
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = "bharatsim-" + id + "-report.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not export run report");
    }
  };

  const handleDelete = async () => {
    if (!id || !run || isRunActive(run.status) || deleting) return;
    const confirmed = window.confirm(
      "Permanently delete this test run and its associated analysis evidence? This cannot be undone."
    );
    if (!confirmed) return;
    setDeleting(true);
    setError("");
    try {
      await api<{ id: string; deleted: boolean }>(
        "/api/v1/runs/" + encodeURIComponent(id),
        { method: "DELETE" }
      );
      navigate("/runs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete test run");
      setDeleting(false);
    }
  };

  useEffect(() => {
    void fetchRun(true);
  }, [fetchRun]);

  // Auto-refresh while the worker is missing, queued, or actively running.
  useEffect(() => {
    if (!run || !isRunActive(run.status)) return;

    const interval = window.setInterval(() => {
      void fetchRun(false);
    }, 3000);

    return () => window.clearInterval(interval);
  }, [run?.status, fetchRun]);

  if (loading && !run) {
    return (
      <section className="panel full-panel">
        <div className="empty-state">
          <LoaderCircle className="spin" size={32} />
          <b>Loading test run…</b>
          <p>Fetching execution evidence and worker reports from the API.</p>
        </div>
      </section>
    );
  }

  if (error && !run) {
    return (
      <section className="panel full-panel">
        <div className="alert error-alert" role="alert">
          <CircleAlert size={18} />
          <span>{error}</span>
          <button className="text-button" onClick={() => navigate("/runs")}>
            Back to test runs
          </button>
        </div>
      </section>
    );
  }

  if (!run) {
    return (
      <section className="panel full-panel">
        <div className="empty-state">
          <Clock3 size={32} />
          <b>Test run not found</b>
          <p>The requested run ID does not exist in the database.</p>
          <button className="secondary-button" onClick={() => navigate("/runs")}>
            <ArrowLeft size={15} /> Back to test runs
          </button>
        </div>
      </section>
    );
  }

  const persona = personas.find((p) => p.id === run.persona_id);
  const personaName = persona?.name || run.persona_id;
  const statusClass =
    run.status === "completed"
      ? "done"
      : run.status === "failed" || run.status === "timed_out"
      ? "failed"
      : "pending";

  const report = (run.result && typeof run.result === "object" ? run.result : null) as WorkerReport | null;

  // Signal chips based on runner.py markers
  const markers = [
    {
      id: "crash",
      label: "Crash / Fatal Exception",
      detected: Boolean(
        report?.fatal_exception_marker ||
          report?.log_signals?.some((s) => s.category === "crash")
      )
    },
    {
      id: "anr",
      label: "ANR (Application Not Responding)",
      detected: Boolean(
        report?.anr_marker ||
          report?.log_signals?.some((s) => s.category === "anr")
      )
    },
    {
      id: "oom",
      label: "OOM (Out Of Memory)",
      detected: Boolean(
        report?.oom_marker ||
          report?.log_signals?.some((s) => s.category === "oom")
      )
    },
    {
      id: "network",
      label: "Network Failure",
      detected: Boolean(
        report?.network_failure_marker ||
          report?.log_signals?.some((s) => s.category === "network")
      )
    },
    {
      id: "storage",
      label: "Storage Failure / ENOSPC",
      detected: Boolean(
        report?.storage_failure_marker ||
          report?.log_signals?.some((s) => s.category === "storage")
      )
    }
  ];

  const netProfile = report?.network_profile;
  const condEvidence = report?.condition_evidence;

  return (
    <section className="panel full-panel run-detail-panel">
      {/* Top action bar */}
      <div className="detail-top-nav">
        <button className="text-button" onClick={() => navigate("/runs")}>
          <ArrowLeft size={15} /> Back to all test runs
        </button>
        <div className="detail-actions">
          <button
            className="secondary-button report-export-button"
            onClick={() => void handleDownloadReport()}
            disabled={!run.result || deleting}
          >
            <Download size={14} /> Export report
          </button>
          <button
            className="danger-button"
            onClick={() => void handleDelete()}
            disabled={isRunActive(run.status) || deleting}
            title={isRunActive(run.status) ? "Wait until worker execution finishes before deleting" : "Permanently delete this run and its evidence"}
          >
            {deleting ? <LoaderCircle size={14} className="spin" /> : <Trash2 size={14} />}
            {deleting ? "Deleting…" : "Delete run"}
          </button>
          <button
            className="icon-button"
            onClick={() => void fetchRun(true)}
            aria-label="Refresh run evidence"
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? "spin" : ""} />
          </button>
        </div>
      </div>

      {/* Header with APK name, persona and status */}
      <div className="panel-heading run-detail-header">
        <div>
          <div className="section-kicker">EXECUTION EVIDENCE REPORT</div>
          <h2>{run.apk_name || "APK execution session"}</h2>
          <div className="run-header-meta">
            <span>
              <b>Persona:</b> {personaName}
            </span>
            <span>
              <b>Created:</b> {date(run.created_at)}
            </span>
            <span>
              <b>Run ID:</b> <code>{run.id}</code>
            </span>
            {run.apk_sha256 && (
              <span>
                <b>SHA-256:</b> <code>{run.apk_sha256.slice(0, 16)}…</code>
              </span>
            )}
            {report?.device_serial && (
              <span>
                <b>Target Device:</b> <code>{report.device_serial}</code>
              </span>
            )}
          </div>
        </div>
        <div>
          <span className={"run-status " + statusClass}>
            {displayRunStatus(run.status)}
          </span>
        </div>
      </div>

      {/* Inline alerts for run error or cleanup warnings */}
      {error && (
        <div className="alert error-alert" role="alert">
          <CircleAlert size={17} />
          <span>{error}</span>
        </div>
      )}
      {run.error && (
        <div className="alert error-alert" role="alert">
          <CircleAlert size={17} />
          <span>{run.error}</span>
        </div>
      )}
      {report?.cleanup_warning && (
        <div className="alert error-alert" role="alert">
          <CircleAlert size={17} />
          <span>{report.cleanup_warning}</span>
        </div>
      )}

      {/* Result interpretation notice if available */}
      {report?.result_interpretation && (
        <div className="alert notice-alert" role="status" aria-live="polite">
          <ShieldCheck size={16} />
          <span>{report.result_interpretation}</span>
        </div>
      )}

      {/* Empty state when no worker report exists */}
      {!report ? (
        <div className="empty-state">
          <Clock3 size={32} />
          <b>No worker report has been submitted</b>
          <p>
            {run.status === "queued"
              ? "This test run is currently queued. Auto-refreshing until a worker claims it."
              : run.status === "leased" || run.status === "running"
              ? "An authenticated Android worker is actively running this test. Auto-refreshing until finished."
              : "Execution waits until an authenticated, isolated Android worker executes the test."}
          </p>
        </div>
      ) : (
        <div className="run-evidence-body">
          {/* Signal Chips for Crash, ANR, OOM, Network, and Storage */}
          <div className="evidence-section">
            <div className="section-kicker">01 / DIAGNOSTIC MARKERS</div>
            <h3>Observation markers</h3>
            <p className="section-desc">
              Extracted from bounded logcat threadtime logs during the smoke window.
            </p>
            <div className="marker-chips">
              {markers.map((m) => (
                <div
                  key={m.id}
                  className={"marker-chip " + (m.detected ? "detected" : "clean")}
                >
                  {m.detected ? <ShieldAlert size={14} /> : <CheckCircle2 size={14} />}
                  <span>{m.label}:</span>
                  <b>{m.detected ? "DETECTED" : "None"}</b>
                </div>
              ))}
            </div>
          </div>

          {/* Findings with evidence lines from log_signals */}
          <div className="evidence-section">
            <div className="section-kicker">02 / LOG FINDINGS</div>
            <h3>Log signal evidence</h3>
            <p className="section-desc">
              Addressable markers with verbatim logcat context. Signals are diagnostic indicators, not proven root causes.
            </p>
            {!report.log_signals || report.log_signals.length === 0 ? (
              <div className="no-evidence">No evidence of crash, ANR, OOM, network or storage markers in logcat.</div>
            ) : (
              <div className="finding-list">
                {report.log_signals.map((sig: LogSignal, idx: number) => (
                  <article key={idx} className="finding-card">
                    <div className="finding-top">
                      <span className={"severity-icon " + (sig.category === "crash" || sig.category === "anr" ? "critical" : "high")}>
                        <CircleAlert size={16} />
                      </span>
                      <div className="finding-title">
                        <span className="finding-kind">
                          {sig.category.toUpperCase()} · LINE {sig.line_number}
                        </span>
                        <h3>{sig.marker}</h3>
                      </div>
                      <span className="risk-badge high">Signal</span>
                    </div>
                    {sig.evidence && sig.evidence.length > 0 && (
                      <div className="evidence-box">
                        <div>
                          <FileSearch size={14} /> CONTEXT LINES
                        </div>
                        {sig.evidence.map((ev, eIdx) => (
                          <code key={eIdx}>
                            {"L" + ev.line_number + ": " + ev.text}
                          </code>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
                {report.log_signals_may_be_truncated && (
                  <div className="profile-caveat">
                    Evidence signals capped at 20 entries to respect inline report bounds.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Requested vs actually applied conditions */}
          <div className="evidence-section">
            <div className="section-kicker">03 / CONDITIONS APPLIED</div>
            <h3>Requested vs actually applied conditions</h3>
            <p className="section-desc">
              Truthful verification: emulator control-plane commands and readbacks are verified. RAM restriction is report-only; packet loss and CPU throttling remain unsupported.
            </p>

            <div className="condition-summary-bar">
              <span className="summary-item">
                <small>CONSTRAINTS APPLIED</small>
                <b>
                  {report.constraints_applied === true
                    ? "Yes, verified"
                    : report.constraints_applied === false
                    ? "No / Partially satisfied"
                    : "No evidence"}
                </b>
              </span>
              <span className="summary-item">
                <small>TRAFFIC PATH VERIFIED</small>
                <b>
                  {netProfile?.traffic_path_verified === true
                    ? "Verified"
                    : netProfile?.traffic_path_verified === false
                    ? "Unverified (fixture-only)"
                    : "No evidence"}
                </b>
              </span>
              <span className="summary-item">
                <small>CONTROL PLANE STATUS</small>
                <b>{netProfile?.control_plane?.status || "No evidence"}</b>
              </span>
            </div>

            <div className="comparison-grid">
              {/* Network profile comparison */}
              <div className="comparison-card">
                <div className="card-top">
                  <Wifi size={16} />
                  <b>Network conditions</b>
                </div>
                <table className="mini-evidence-table">
                  <thead>
                    <tr>
                      <th>PARAMETER</th>
                      <th>REQUESTED</th>
                      <th>APPLIED READBACK</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Latency</td>
                      <td>
                        {netProfile?.requested?.latency_ms != null
                          ? `${netProfile.requested.latency_ms} ms`
                          : "No evidence"}
                      </td>
                      <td>
                        {netProfile?.control_plane?.readback?.minimum_latency_ms != null
                          ? `${netProfile.control_plane.readback.minimum_latency_ms} ms`
                          : "No evidence"}
                      </td>
                    </tr>
                    <tr>
                      <td>Download</td>
                      <td>
                        {netProfile?.requested?.download_kbps != null
                          ? `${netProfile.requested.download_kbps.toLocaleString()} kbps`
                          : "No evidence"}
                      </td>
                      <td>
                        {netProfile?.control_plane?.readback?.download_bps != null
                          ? `${(netProfile.control_plane.readback.download_bps / 1000).toLocaleString()} kbps`
                          : "No evidence"}
                      </td>
                    </tr>
                    <tr>
                      <td>Upload</td>
                      <td>
                        {netProfile?.requested?.upload_kbps != null
                          ? `${netProfile.requested.upload_kbps.toLocaleString()} kbps`
                          : "No evidence"}
                      </td>
                      <td>
                        {netProfile?.control_plane?.readback?.upload_bps != null
                          ? `${(netProfile.control_plane.readback.upload_bps / 1000).toLocaleString()} kbps`
                          : "No evidence"}
                      </td>
                    </tr>
                    <tr>
                      <td>Packet loss</td>
                      <td>
                        {netProfile?.requested?.packet_loss_pct != null
                          ? `${netProfile.requested.packet_loss_pct}%`
                          : "No evidence"}
                      </td>
                      <td>
                        <span className="unsupported-tag">Unsupported by emulator</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Condition evidence details */}
              <div className="comparison-card">
                <div className="card-top">
                  <Layers3 size={16} />
                  <b>Condition Manager Evidence</b>
                </div>
                {!condEvidence ? (
                  <div className="no-evidence">No evidence recorded by Condition Manager.</div>
                ) : (
                  <>
                    <div className="evidence-metrics">
                      <span>
                        <small>OVERALL STATUS</small>
                        <b>{condEvidence.overall_status ? conditionStatusLabel(condEvidence.overall_status) : "No evidence"}</b>
                      </span>
                      <span>
                        <small>APPLIED COUNT</small>
                        <b>
                          {condEvidence.applied_conditions_count != null
                            ? condEvidence.applied_conditions_count
                            : "No evidence"}
                        </b>
                      </span>
                      <span>
                        <small>CLEANUP STATUS</small>
                        <b>{condEvidence.cleanup?.status || "No evidence"}</b>
                      </span>
                    </div>
                    {(condEvidence.preexisting_conditions_count ?? 0) > 0 && (
                      <p className="section-desc">
                        {condEvidence.preexisting_conditions_count} target condition(s) were already satisfied before the run. They were observed and verified, not applied by BharatSim.
                      </p>
                    )}

                    {condEvidence.conditions && condEvidence.conditions.length > 0 ? (
                      <table className="mini-evidence-table">
                        <thead>
                          <tr>
                            <th>CONDITION</th>
                            <th>APPLY STATUS</th>
                            <th>VERIFICATION</th>
                          </tr>
                        </thead>
                        <tbody>
                          {condEvidence.conditions.map((c: ConditionRecord, idx: number) => (
                            <tr key={idx}>
                              <td>{c.condition}</td>
                              <td>{conditionStatusLabel(c.apply_status)}</td>
                              <td>{c.verification_status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="no-evidence">No evidence of specific condition records.</div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Smoke test steps */}
          <div className="evidence-section">
            <div className="section-kicker">04 / EXECUTION SEQUENCE</div>
            <h3>Smoke test steps</h3>
            <p className="section-desc">
              Discrete ADB commands executed on the target device with durations and exit codes.
            </p>
            {!report.steps || report.steps.length === 0 ? (
              <div className="no-evidence">No evidence of executed steps.</div>
            ) : (
              <div className="table-wrap">
                <table className="steps-table">
                  <thead>
                    <tr>
                      <th>STEP</th>
                      <th>RETURN CODE</th>
                      <th>DURATION</th>
                      <th>OUTPUT DETAILS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.steps.map((st: SmokeStep, idx: number) => {
                      const isExpanded = expandedStep === st.name + idx;
                      const hasOutput = Boolean(st.stdout_tail?.trim() || st.stderr_tail?.trim());

                      return (
                        <tr key={idx}>
                          <td>
                            <b>{st.name}</b>
                          </td>
                          <td>
                            <span
                              className={
                                "step-rc " + (st.return_code === 0 ? "rc-ok" : "rc-err")
                              }
                            >
                              {st.return_code === 0 ? "0 (OK)" : `Exit ${st.return_code}`}
                            </span>
                          </td>
                          <td>{st.duration_seconds}s</td>
                          <td>
                            {hasOutput ? (
                              <div>
                                <button
                                  className="text-button"
                                  onClick={() =>
                                    setExpandedStep(isExpanded ? null : st.name + idx)
                                  }
                                >
                                  {isExpanded ? "Hide tail output" : "Show tail output"}
                                </button>
                                {isExpanded && (
                                  <pre className="step-output-box">
                                    {st.stdout_tail && `[STDOUT]\n${st.stdout_tail}\n`}
                                    {st.stderr_tail && `[STDERR]\n${st.stderr_tail}`}
                                  </pre>
                                )}
                              </div>
                            ) : (
                              <span className="no-evidence">No output</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Limitations list */}
          <div className="evidence-section">
            <div className="section-kicker">05 / METHODOLOGY LIMITATIONS</div>
            <h3>Limitations and non-claims</h3>
            {!report.limitations || report.limitations.length === 0 ? (
              <div className="no-evidence">No evidence of limitations documented.</div>
            ) : (
              <div className="limitations">
                <b>Reported test constraints:</b>
                {report.limitations.map((lim: string, idx: number) => (
                  <p key={idx}>• {lim}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
