import { CircleAlert, FileSearch, CheckCircle2, GitBranch, Gauge, Brain, Sparkles, Code2 } from "lucide-react";
import { type Finding, cls } from "../api";
import SarvamAudioPlayer from "./SarvamAudioPlayer";

interface FindingCardProps {
  finding: Finding;
}

export default function FindingCard({ finding: f }: FindingCardProps) {
  const sx = f.sarvam_explanation;
  // The API names these developer_fix / code_remedy; older payloads used remediation / defensive_code.
  const fix = sx?.developer_fix || sx?.remediation || "";
  const code = sx?.code_remedy || sx?.defensive_code || "";
  const voiceText = sx?.hindi_explanation || fix || sx?.root_cause || f.recommendation || "";
  return (
    <article className="finding-card">
      <div className="finding-top">
        <span className={"severity-icon " + cls(f.severity)}>
          <CircleAlert size={17} />
        </span>
        <div className="finding-title">
          <span className="finding-kind">{String(f.kind || "signal").toUpperCase() + " · " + f.id}</span>
          <h3>{f.title}</h3>
        </div>
        <div className="finding-badges">
          {f.ml_classification && (
            <span className="ml-badge" title={`Confidence: ${(f.ml_classification.confidence * 100).toFixed(1)}%`}>
              <Brain size={12} /> ML: {String(f.ml_classification.category || "other").toUpperCase()} ({Math.round(f.ml_classification.confidence * 100)}%)
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

      {f.sarvam_explanation && (
        <div className="sarvam-explanation-card">
          <div className="sarvam-exp-header">
            <Sparkles size={14} />
            <span>DEVELOPER GUIDANCE · RULE-BASED TEMPLATE</span>
          </div>
          <div className="sarvam-exp-body">
            <p><strong>Typical failure pattern:</strong> {f.sarvam_explanation.root_cause}</p>
            <p><strong>Potential impact:</strong> {f.sarvam_explanation.impact}</p>
            <small>Template guidance is a starting point, not a confirmed root cause.</small>
            {fix && <p><strong>Fix:</strong> {fix}</p>}
            {f.sarvam_explanation.hindi_explanation && (
              <div className="hindi-briefing-box" lang="hi">
                <small>हिंदी सारांश:</small>
                <p>{f.sarvam_explanation.hindi_explanation}</p>
              </div>
            )}
            {code && (
              <details className="defensive-code-details">
                <summary><Code2 size={13} /> View defensive code fix</summary>
                <pre><code>{code}</code></pre>
              </details>
            )}
            <SarvamAudioPlayer
              text={voiceText}
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
