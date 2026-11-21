import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, FileUp, LoaderCircle, Mic, ShieldCheck, Sparkles, Square, XCircle } from "lucide-react";
import { type Persona } from "../api";
import {
  fetchSampleBuild,
  interpretRequest,
  listScenarioPacks,
  runScenarioPayload,
  transcribeVoice,
  type ScenarioPack,
  type TestSpec
} from "../speak";

export type SubmitRunOptions = { personaId: string; scenario: ReturnType<typeof runScenarioPayload> };

interface SpeakToTestViewProps {
  personas: Persona[];
  previewMode: boolean;
  busy: boolean;
  onSubmitRun: (file: File, options: SubmitRunOptions) => Promise<void>;
}

const EXAMPLES = [
  { label: "Hindi", text: "मेरा पेमेंट ऐप धीमे नेटवर्क में पेमेंट के बाद पेंडिंग दिखा रहा है। जाँच करो कि रीट्राई करने पर डुप्लिकेट रिक्वेस्ट तो नहीं जाती।" },
  { label: "Hinglish", text: "Mera payment app slow network mein payment karne ke baad pending dikha raha hai. Check karo ki retry karne par duplicate request toh nahi hoti." },
  { label: "Tamil", text: "என் பேமெண்ட் ஆப் மெதுவான நெட்வொர்க்கில் பணம் செலுத்திய பிறகு pending காட்டுகிறது. மீண்டும் முயற்சி செய்தால் இரண்டு முறை பணம் எடுக்கப்படுகிறதா என்று சோதிக்கவும்." },
  { label: "Unsupported", text: "Test my telemedicine app when a phone call comes in and the CPU is throttled on 2G." }
];

const MAX_RECORD_MS = 25000;
const STORE_KEY = "bharatsim.speak.plan";

function loadPlan(): { text: string; spec: TestSpec | null } {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // storage blocked or corrupted: start empty
  }
  return { text: "", spec: null };
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}

export default function SpeakToTestView({ personas, previewMode, busy, onSubmitRun }: SpeakToTestViewProps) {
  // The plan survives navigating to a run and back, so the second build can reuse it.
  const [text, setText] = useState(() => loadPlan().text);
  const [spec, setSpec] = useState<TestSpec | null>(() => loadPlan().spec);
  const [error, setError] = useState("");
  const [working, setWorking] = useState<"" | "interpret" | "transcribe">("");
  const [recording, setRecording] = useState(false);
  const [transcriptNote, setTranscriptNote] = useState("");
  const [packs, setPacks] = useState<ScenarioPack[]>([]);
  const [showJson, setShowJson] = useState(false);
  const [ownApk, setOwnApk] = useState<File | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stopTimer = useRef<number | null>(null);

  useEffect(() => {
    listScenarioPacks().then(setPacks).catch(() => setPacks([]));
    return () => {
      if (stopTimer.current) window.clearTimeout(stopTimer.current);
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({ text, spec }));
    } catch {
      // per-tab convenience only
    }
  }, [text, spec]);

  const scenario = packs.find((p) => p.id === spec?.execution.scenario_id);
  const personaName = (id: string) => personas.find((p) => p.id === id)?.name || id;

  async function interpret(value = text) {
    if (value.trim().length < 3) {
      setError("Describe what you want to test (at least a few words).");
      return;
    }
    setError("");
    setWorking("interpret");
    setSpec(null);
    try {
      setSpec(await interpretRequest(value.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not interpret the request.");
    } finally {
      setWorking("");
    }
  }

  async function startRecording() {
    setError("");
    setTranscriptNote("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Voice recording is not available in this browser. Type the request instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find((m) => MediaRecorder.isTypeSupported(m));
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        if (!blob.size) return;
        setWorking("transcribe");
        try {
          const result = await transcribeVoice(blob);
          setText(result.transcript);
          setTranscriptNote(`Sarvam ${result.model} heard ${result.language_code || "an Indian language"} in ${result.latency_ms} ms.`);
          if (result.transcript.trim().length >= 3) await interpret(result.transcript);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Could not transcribe the recording.");
        } finally {
          setWorking("");
        }
      };
      recorder.current = rec;
      rec.start();
      setRecording(true);
      stopTimer.current = window.setTimeout(() => rec.state === "recording" && rec.stop(), MAX_RECORD_MS);
    } catch {
      setError("Microphone access was blocked. Allow the microphone for this site or type the request.");
    }
  }

  function stopRecording() {
    if (stopTimer.current) window.clearTimeout(stopTimer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  async function runSample(path: string, variant: string) {
    if (!spec) return;
    setError("");
    try {
      const file = await fetchSampleBuild(path, `bharatpay-${variant}.apk`);
      await onSubmitRun(file, { personaId: spec.execution.persona_id, scenario: runScenarioPayload(spec, spec.execution.scenario_id) });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run.");
    }
  }

  async function runOwnApk() {
    if (!spec || !ownApk) return;
    await onSubmitRun(ownApk, { personaId: spec.execution.persona_id, scenario: runScenarioPayload(spec, spec.execution.scenario_id) });
  }

  return (
    <div className="speak-view">
      <section className="panel full-panel">
        <div className="panel-heading">
          <div>
            <div className="section-kicker">SPEAK-TO-TEST · SARVAM AI</div>
            <h2>Describe the problem. Get a test you can run.</h2>
            <p>
              Speak or type in Hindi, Hinglish, Tamil, Marathi or English. Sarvam turns it into a structured test plan; BharatSim checks it against
              what the emulator can really do, then runs it and records evidence.
            </p>
          </div>
          <div className="panel-icon"><Sparkles size={19} /></div>
        </div>

        {previewMode && (
          <div className="alert notice-alert" role="status">
            <ShieldCheck size={16} />
            <span>Sign in to use Speak-to-Test. AI requests and runs are tied to your account and rate limited.</span>
          </div>
        )}

        <label className="field-label" htmlFor="speak-text">Your test request</label>
        <textarea
          id="speak-text"
          className="speak-textarea"
          value={text}
          maxLength={1000}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Mera payment app slow network mein pending dikhata hai. Check karo retry par double charge toh nahi hota."
          rows={4}
        />
        <div className="speak-examples" aria-label="Example requests">
          {EXAMPLES.map((ex) => (
            <button key={ex.label} type="button" className="chip-button" onClick={() => setText(ex.text)}>
              {ex.label} example
            </button>
          ))}
        </div>
        <div className="speak-actions">
          <button
            type="button"
            className={"secondary-button " + (recording ? "recording" : "")}
            onClick={recording ? stopRecording : () => void startRecording()}
            disabled={previewMode || working !== ""}
            aria-pressed={recording}
          >
            {recording ? <Square size={14} /> : <Mic size={14} />}
            {recording ? "Stop recording" : "Speak (up to 25 s)"}
          </button>
          <button type="button" className="primary-button" onClick={() => void interpret()} disabled={previewMode || working !== "" || recording}>
            {working === "interpret" ? <LoaderCircle size={14} className="spin" /> : <Sparkles size={14} />}
            {working === "interpret" ? "Sarvam is reading your request…" : "Create test plan"}
          </button>
          {working === "transcribe" && (
            <span className="speak-status"><LoaderCircle size={14} className="spin" /> Transcribing with Sarvam…</span>
          )}
        </div>
        {transcriptNote && <p className="speak-note">{transcriptNote}</p>}
        {error && (
          <div className="alert error-alert" role="alert"><CircleAlert size={16} /><span>{error}</span></div>
        )}
      </section>

      {spec && (
        <section className="panel full-panel spec-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <div className="section-kicker">INTERPRETED TEST PLAN · {spec.spec_id}</div>
              <h2>{spec.objective}</h2>
              <p>
                Journey: <b>{humanize(spec.journey)}</b> · Persona: <b>{personaName(spec.execution.persona_id)}</b> · Language heard:{" "}
                <b>{spec.language_detected}</b>
              </p>
            </div>
            <span className={"risk-badge " + (spec.execution.eligible ? "low" : spec.execution.mode === "blocked" ? "critical" : "medium")}>
              {spec.execution.mode === "scenario" ? "SCENARIO" : spec.execution.mode === "generic" ? "GENERIC RUN" : spec.execution.mode === "blocked" ? "BLOCKED" : "NEEDS DETAIL"}
            </span>
          </div>

          <div className={"alert " + (spec.execution.eligible ? "notice-alert" : "error-alert")}>
            {spec.execution.eligible ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}
            <span>{spec.execution.reason}</span>
          </div>

          {spec.clarifications_needed.length > 0 && (
            <div className="spec-block">
              <b>Questions before testing</b>
              <ul>{spec.clarifications_needed.map((q) => <li key={q}>{q}</li>)}</ul>
              <small>Add the answer to your request above and create the plan again.</small>
            </div>
          )}

          <div className="spec-grid">
            <div className="spec-block">
              <b>Conditions</b>
              {spec.supported_conditions.length === 0 && spec.unsupported_conditions.length === 0 && <small>No special conditions requested.</small>}
              {spec.supported_conditions.map((c) => (
                <div key={c.condition} className="spec-row"><CheckCircle2 size={13} className="ok" /><span><b>{humanize(c.condition)}</b> · {c.note}</span></div>
              ))}
              {spec.unsupported_conditions.map((c) => (
                <div key={c.condition} className="spec-row"><XCircle size={13} className="bad" /><span><b>{humanize(c.condition)}</b> · not applied: {c.note}</span></div>
              ))}
            </div>
            <div className="spec-block">
              <b>Pass criteria</b>
              {spec.machine_checked_assertions.map((a) => (
                <div key={a.id} className="spec-row"><CheckCircle2 size={13} className="ok" /><span>{a.label} <small>· machine-checked</small></span></div>
              ))}
              {spec.not_machine_verified.map((a) => (
                <div key={a} className="spec-row"><Clock3 size={13} className="warn" /><span>{humanize(a)} <small>· not machine-verified</small></span></div>
              ))}
              {spec.machine_checked_assertions.length === 0 && spec.not_machine_verified.length === 0 && <small>None stated.</small>}
            </div>
            <div className="spec-block">
              <b>Evidence to collect</b>
              <div className="condition-chips">{spec.evidence.map((e) => <span key={e} className="condition-chip verifiable">{humanize(e)}</span>)}</div>
              {spec.expected_behaviour.length > 0 && (
                <>
                  <b className="spec-sub">Expected behaviour</b>
                  <ul>{spec.expected_behaviour.map((e) => <li key={e}>{e}</li>)}</ul>
                </>
              )}
            </div>
          </div>

          <div className="spec-interpreter">
            <ShieldCheck size={14} />
            <span>
              {spec.interpreter.fallback
                ? `Rule-based fallback used (${spec.interpreter.fallback_reason}). Sarvam did not interpret this request.`
                : `Interpreted by Sarvam ${spec.interpreter.model} in ${spec.interpreter.latency_ms} ms · request ${spec.interpreter.request_id}.`}
              {" "}Output validated against a strict schema; only the scenario id and persona reach the worker.
              {spec.interpreter.redacted_input ? " Personal data and secrets were redacted before sending." : ""}
            </span>
            <button type="button" className="text-button" onClick={() => setShowJson(!showJson)}>{showJson ? "Hide" : "Show"} JSON</button>
          </div>
          {showJson && <pre className="spec-json">{JSON.stringify(spec, null, 2)}</pre>}

          {spec.execution.eligible && spec.execution.mode === "scenario" && scenario && (
            <div className="spec-run">
              <div>
                <div className="section-kicker">{scenario.pack.toUpperCase()}</div>
                <h3>{scenario.title}</h3>
                <p>{scenario.setup}</p>
              </div>
              <div className="spec-run-actions">
                {scenario.sample_builds?.map((b) => (
                  <button key={b.variant} type="button" className={b.variant === "original" ? "secondary-button" : "primary-button"}
                    disabled={busy || previewMode} onClick={() => void runSample(b.path, b.variant)}>
                    {busy ? <LoaderCircle size={14} className="spin" /> : <FileUp size={14} />} Run {b.label}
                  </button>
                ))}
              </div>
              <small>Run the original first, then the fixed build, and compare them in FixProof. Each run takes about 4 minutes on the emulator.</small>
            </div>
          )}

          {spec.execution.eligible && (
            <div className="spec-run">
              <div>
                <div className="section-kicker">YOUR OWN APK</div>
                <p>{spec.execution.mode === "scenario"
                  ? "Your APK gets the generic baseline vs persona run; the scenario assertions need the BharatPay Mock fixture and will be reported as blocked for other apps."
                  : "Runs the baseline vs persona comparison on your APK with this plan attached to the report."}</p>
              </div>
              <div className="spec-run-actions">
                <input type="file" accept=".apk,application/vnd.android.package-archive" aria-label="Choose your APK"
                  onChange={(e) => setOwnApk(e.target.files?.[0] || null)} disabled={busy || previewMode} />
                <button type="button" className="secondary-button" disabled={!ownApk || busy || previewMode} onClick={() => void runOwnApk()}>
                  <FileUp size={14} /> Run with this plan
                </button>
              </div>
            </div>
          )}
        </section>
      )}

    </div>
  );
}
