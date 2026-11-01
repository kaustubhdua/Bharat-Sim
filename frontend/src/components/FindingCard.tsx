import { CircleAlert, FileSearch, CheckCircle2, GitBranch, Gauge } from "lucide-react";
import { type Finding, cls } from "../api";

interface FindingCardProps {
  finding: Finding;
}

export default function FindingCard({ finding: f }: FindingCardProps) {
  return (
    <article className="finding-card">
      <div className="finding-top">
        <span className={"severity-icon " + cls(f.severity)}>
          <CircleAlert size={17} />
        </span>
        <div className="finding-title">
          <span className="finding-kind">{f.kind.toUpperCase() + " · " + f.id}</span>
          <h3>{f.title}</h3>
        </div>
        <div className="finding-badges">
          {f.occurrence_count ? <span className="occurrence-badge">{f.occurrence_count} occurrence{f.occurrence_count === 1 ? "" : "s"}</span> : null}
          <span className={"risk-badge " + cls(f.severity)}>{f.severity}</span>
        </div>
      </div>
      <p>{f.explanation}</p>
      {f.impact_priority ? (
        <div className="finding-impact"><Gauge size={14} /><b>Investigation priority {f.impact_priority.score}/100</b><span>{f.impact_priority.persona_risk} persona · relative heuristic</span></div>
      ) : null}
      <div className="evidence-box">
        <div>
          <FileSearch size={14} /> SOURCE EVIDENCE
        </div>
        {f.evidence.map((ev, i) => (
          <code key={i}>{"L" + ev.line + ": " + ev.text}</code>
        ))}
      </div>
      {f.evidence_context?.length ? (
        <details className="evidence-context">
          <summary><GitBranch size={13} /> Show surrounding log context</summary>
          {f.evidence_context.map((ev) => (
            <code key={ev.line} className={ev.relation === "match" ? "context-match" : ""}>{"L" + ev.line + ": " + ev.text}</code>
          ))}
        </details>
      ) : null}
      {f.root_cause_hypothesis ? (
        <details className="hypothesis-box">
          <summary>Root-cause hypothesis · {f.root_cause_hypothesis.confidence} confidence</summary>
          <p>{f.root_cause_hypothesis.statement}</p>
          <b>Validation steps</b>
          <ol>{f.root_cause_hypothesis.validation_steps.map((step) => <li key={step}>{step}</li>)}</ol>
        </details>
      ) : null}
      <div className="recommendation">
        <CheckCircle2 size={16} />
        <span>
          <b>Suggested next step</b>
          {f.recommendation}
        </span>
      </div>
    </article>
  );
}
