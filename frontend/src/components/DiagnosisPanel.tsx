import { useState, type ReactNode } from "react";
import { CheckCircle2, CircleAlert, HelpCircle, LoaderCircle, Stethoscope, Wrench, XCircle } from "lucide-react";
import SarvamAudioPlayer from "./SarvamAudioPlayer";
import { diagnoseRun, type Diagnosis } from "../speak";

const LANGUAGES = [
  { code: "hi-IN", label: "Hindi" },
  { code: "en-IN", label: "English" },
  { code: "ta-IN", label: "Tamil" },
  { code: "mr-IN", label: "Marathi" }
] as const;

const VERDICT: Record<string, { label: string; tone: string; icon: ReactNode }> = {
  REPRODUCED: { label: "PROBLEM REPRODUCED", tone: "critical", icon: <CircleAlert size={16} /> },
  NOT_REPRODUCED: { label: "NOT REPRODUCED", tone: "low", icon: <CheckCircle2 size={16} /> },
  CANNOT_CHECK: { label: "CANNOT CHECK AUTOMATICALLY", tone: "medium", icon: <HelpCircle size={16} /> },
  BLOCKED: { label: "COULD NOT CHECK", tone: "medium", icon: <XCircle size={16} /> }
};

interface DiagnosisPanelProps {
  runId: string;
  runFinished: boolean;
  reportedProblem?: string;
}

export default function DiagnosisPanel({ runId, runFinished, reportedProblem }: DiagnosisPanelProps) {
  const [problem, setProblem] = useState(reportedProblem || "");
  const [language, setLanguage] = useState<string>("hi-IN");
  const [result, setResult] = useState<Diagnosis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const typed = problem.trim();
      setResult(await diagnoseRun(runId, language, reportedProblem && typed === reportedProblem ? undefined : typed || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not diagnose this run.");
    } finally {
      setBusy(false);
    }
  }

  const verdict = result ? VERDICT[result.reproduction.verdict] : null;
  const spoken = result
    ? result.translated_text ||
      [result.reproduction.summary, result.diagnosis?.why, ...(result.diagnosis?.fix_steps || [])].filter(Boolean).join(" ")
    : "";

  return (
    <section className="panel sarvam-panel diagnosis-panel" aria-labelledby="diagnosis-title">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">DIAGNOSE A PROBLEM · SARVAM AI</div>
          <h2 id="diagnosis-title">Did your problem happen, why, and how to fix it</h2>
          <p>BharatSim first checks the measured evidence from this run for the problem you describe, then Sarvam explains the cause and a fix from that evidence only.</p>
        </div>
        <div className="panel-icon"><Stethoscope size={19} /></div>
      </div>

      <label className="field-label" htmlFor="diag-problem">The problem you saw</label>
      <textarea id="diag-problem" className="speak-textarea" rows={2} maxLength={1000} value={problem}
        placeholder="e.g. App band ho jati hai jab network slow hota hai"
        onChange={(e) => setProblem(e.target.value)} />
      <div className="explain-controls">
        <label htmlFor="diag-lang" className="field-label">Answer in</label>
        <select id="diag-lang" value={language} onChange={(e) => setLanguage(e.target.value)}>
          {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
        <button type="button" className="primary-button" onClick={() => void run()} disabled={busy || !runFinished || problem.trim().length < 3}>
          {busy ? <LoaderCircle size={14} className="spin" /> : <Stethoscope size={14} />} {busy ? "Checking the evidence…" : "Diagnose"}
        </button>
      </div>
      {!runFinished && <p className="speak-note">The run is still executing on the emulator. Diagnose it when it finishes.</p>}
      <div className="evidence-note">
        Sent to Sarvam: your problem text, the run's summary facts and up to 8 failure log lines, with secrets and personal data removed.
      </div>
      {error && <div className="alert error-alert" role="alert"><CircleAlert size={16} /><span>{error}</span></div>}

      {result && verdict && (
        <div className="explain-result" aria-live="polite">
          <div className={"fp-verdict " + verdict.tone}>
            <span className={"risk-badge " + verdict.tone}>{verdict.label}</span>
            <p>{result.reproduction.summary}</p>
          </div>
          <small className="speak-note">
            Understood your problem as: {result.reproduction.symptom_label}
            {result.reproduction.symptom_source ? ` (by ${result.reproduction.symptom_source})` : ""}. If that's wrong, reword it and diagnose again.
          </small>
          {result.reproduction.evidence.length > 0 && (
            <details>
              <summary>What BharatSim measured ({result.reproduction.evidence.length})</summary>
              <ul>{result.reproduction.evidence.map((e) => <li key={e.id}><code>{e.id}</code> {e.fact}</li>)}</ul>
            </details>
          )}
          {result.diagnosis && (
            <>
              {result.translated_text && <p className="explain-translated">{result.translated_text}</p>}
              {result.translation_failed && <p className="speak-note">Translation is unavailable right now; showing English.</p>}
              <h3>Why it happens <small className="speak-note">confidence: {result.diagnosis.confidence}</small></h3>
              <p>{result.diagnosis.why}</p>
              {result.diagnosis.fix_steps.length > 0 && (
                <div className="recommendation">
                  <Wrench size={14} />
                  <span><b>How to fix it</b><ol>{result.diagnosis.fix_steps.map((s) => <li key={s}>{s}</li>)}</ol></span>
                </div>
              )}
              {result.diagnosis.code_hint && <pre className="spec-json">{result.diagnosis.code_hint}</pre>}
              {result.cited_evidence && result.cited_evidence.length > 0 && (
                <details>
                  <summary>Evidence this diagnosis is based on ({result.cited_evidence.length})</summary>
                  <ul>{result.cited_evidence.map((e) => <li key={e.id}><code>{e.id}</code> {e.fact}</li>)}</ul>
                </details>
              )}
              {result.interpreter && (
                <small className="speak-note">Sarvam {result.interpreter.model} · {result.interpreter.latency_ms} ms · request {result.interpreter.request_id}</small>
              )}
              <SarvamAudioPlayer text={spoken.slice(0, 500)} defaultLang={language} label="Listen (Bulbul voice)" />
            </>
          )}
        </div>
      )}
    </section>
  );
}
