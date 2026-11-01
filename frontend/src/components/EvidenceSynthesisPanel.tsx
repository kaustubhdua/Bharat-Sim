import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  FileSearch,
  GitBranch,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { EvidenceFusion } from "../api";

function label(value: string): string {
  return value.replaceAll("_", " ").toLowerCase();
}

function statusClass(value: string): string {
  return value.toLowerCase().replaceAll("_", "-");
}

export default function EvidenceSynthesisPanel({ diagnostics }: { diagnostics: EvidenceFusion }) {
  const correlated = diagnostics.status === "CORRELATED";
  const noMarkers = diagnostics.status === "NO_MARKER_OBSERVED";

  return (
    <section className="evidence-section evidence-fusion-panel" aria-labelledby="evidence-fusion-title">
      <div className="section-kicker">00 / CROSS-SOURCE EVIDENCE FUSION</div>
      <div className="evidence-fusion-heading">
        <div>
          <h3 id="evidence-fusion-title">Diagnostic evidence synthesis</h3>
          <p className="section-desc">
            Deterministic correlation across logcat, condition readbacks, network controls and execution steps.
            It prioritizes investigation; it does not confirm a root cause.
          </p>
        </div>
        <span className={"evidence-fusion-status " + statusClass(diagnostics.status)}>
          {correlated ? <ShieldCheck size={14} /> : noMarkers ? <CircleHelp size={14} /> : <ShieldAlert size={14} />}
          {label(diagnostics.status)}
        </span>
      </div>

      <div className="evidence-fusion-summary">
        <div className="evidence-fusion-summary-icon">
          {correlated ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
        </div>
        <div>
          <b>{diagnostics.review_required ? "Human review required" : "Evidence summary"}</b>
          <p>{diagnostics.summary}</p>
        </div>
      </div>

      <div className="evidence-fusion-sources">
        {diagnostics.sources.map((source) => (
          <div className="evidence-source" key={source.id}>
            <span className={"evidence-source-state " + statusClass(source.status)} />
            <div>
              <b>{label(source.id)}</b>
              <small>{label(source.status)}</small>
              <p>{source.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="evidence-condition-strip">
        <div><b>Verified conditions</b><span>{diagnostics.verified_conditions.length ? diagnostics.verified_conditions.map(label).join(" · ") : "None"}</span></div>
        <div><b>Pre-existing conditions</b><span>{diagnostics.preexisting_conditions?.length ? diagnostics.preexisting_conditions.map(label).join(" · ") : "None"}</span></div>
        <div><b>Unsupported conditions</b><span>{diagnostics.unsupported_conditions.length ? diagnostics.unsupported_conditions.map(label).join(" · ") : "None"}</span></div>
      </div>

      <div className="evidence-fusion-observations">
        <div className="section-kicker">OBSERVED SIGNALS</div>
        <div className="evidence-observation-grid">
          {diagnostics.observations.map((observation) => (
            <article className={"evidence-observation " + statusClass(observation.status)} key={observation.category}>
              <div>
                <b>{observation.category.toUpperCase()}</b>
                <span>{observation.count > 0 ? observation.count + " marker(s)" : "No marker"}</span>
              </div>
              <p>{observation.interpretation}</p>
              {observation.evidence.slice(0, 2).map((item, index) => (
                <div className="evidence-observation-marker" key={item.marker + index}>
                  <small>{item.marker || "Marker flag"}{item.line_number ? " · L" + item.line_number : ""}</small>
                  {item.evidence.slice(0, 2).map((line, lineIndex) => (
                    <code key={line.line_number ?? lineIndex}>
                      {line.line_number ? "L" + line.line_number + ": " : ""}{line.text}
                    </code>
                  ))}
                </div>
              ))}
            </article>
          ))}
        </div>
      </div>

      <div className="evidence-fusion-hypotheses">
        <div className="section-kicker">ROOT-CAUSE HYPOTHESES · UNCONFIRMED</div>
        {diagnostics.hypotheses.length === 0 ? (
          <div className="no-evidence">
            No root-cause hypothesis was generated from the available evidence. Missing markers are not a pass.
          </div>
        ) : (
          diagnostics.hypotheses.map((hypothesis) => (
            <article className="evidence-hypothesis" key={hypothesis.id}>
              <div className="evidence-hypothesis-heading">
                <b>{label(hypothesis.category)} hypothesis</b>
                <span className={"risk-badge " + hypothesis.confidence}>{hypothesis.confidence} confidence</span>
              </div>
              <p>{hypothesis.statement}</p>
              <div className="evidence-hypothesis-sources">
                <GitBranch size={13} /> Supported by: {hypothesis.supporting_sources.map(label).join(" · ")}
              </div>
              <details>
                <summary><FileSearch size={13} /> Validation steps</summary>
                <ol>{hypothesis.validation_steps.map((step) => <li key={step}>{step}</li>)}</ol>
              </details>
            </article>
          ))
        )}
      </div>

      <div className="evidence-fusion-footer">
        <b>Method limitations</b>
        <ul>{diagnostics.limitations.slice(0, 5).map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
    </section>
  );
}
