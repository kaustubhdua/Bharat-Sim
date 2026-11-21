import { CircleAlert, FileSearch, CheckCircle2, GitBranch, Gauge, Brain, Sparkles, Code2 } from "lucide-react";
import { type Finding, cls } from "../api";
import SarvamAudioPlayer from "./SarvamAudioPlayer";

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
          <span className="finding-kind">{(f.kind || "finding").toUpperCase() + " · " + f.id}</span>
          <h3>{f.title}</h3>
        </div>
        <div className="finding-badges">
          {f.ml_classification && typeof f.ml_classification === "object" && f.ml_classification.category && (
            <span className="ml-badge" title={`Confidence: ${(f.ml_classification.confidence * 100).toFixed(1)}%`}>
              <Brain size={12} /> ML: {f.ml_classification.category.toUpperCase()} ({Math.round(f.ml_classification.confidence * 100)}%)
            </span>
          )}
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
        {(Array.isArray(f.evidence) ? f.evidence : []).map((ev, i) => (
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
          <ol>{(f.root_cause_hypothesis.validation_steps || []).map((step) => <li key={step}>{step}</li>)}</ol>
        </details>
      ) : null}

      {f.sarvam_explanation && (
        <div className="sarvam-explanation-card">
          <div className="sarvam-exp-header">
            <Sparkles size={14} />
            <span>SARVAM AI DIAGNOSTIC & DEVELOPER REMEDY</span>
          </div>
          <div className="sarvam-exp-body">
            <p><strong>Root Cause:</strong> {f.sarvam_explanation.root_cause}</p>
            <p><strong>Impact:</strong> {f.sarvam_explanation.impact}</p>
            <p><strong>Fix:</strong> {f.sarvam_explanation.remediation}</p>
            {f.sarvam_explanation.hindi_explanation && (
              <div className="hindi-briefing-box" lang="hi">
                <small>हिंदी सारांश:</small>
                <p>{f.sarvam_explanation.hindi_explanation}</p>
              </div>
            )}
            {f.sarvam_explanation.defensive_code && (
              <details className="defensive-code-details">
                <summary><Code2 size={13} /> View defensive code fix</summary>
                <pre><code>{f.sarvam_explanation.defensive_code}</code></pre>
              </details>
            )}
            <SarvamAudioPlayer
              text={f.sarvam_explanation.hindi_explanation || f.sarvam_explanation.remediation}
              defaultLang="hi-IN"
              label="Listen to voice briefing (Bulbul TTS)"
            />
          </div>
        </div>
      )}

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
