import { useState } from "react";
import { Languages, LoaderCircle, ShieldCheck } from "lucide-react";
import { api } from "../api";

type Props = { enabled: boolean; text: string };
const languages = [
  { code: "hi-IN", label: "Hindi" },
  { code: "ta-IN", label: "Tamil" },
  { code: "mr-IN", label: "Marathi" }
] as const;

export default function SarvamTranslation({ enabled, text }: Props) {
  const [language, setLanguage] = useState<(typeof languages)[number]["code"]>("hi-IN");
  const [translated, setTranslated] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function translate() {
    setBusy(true);
    setError("");
    setTranslated("");
    try {
      const result = await api<{ translated_text: string }>("/api/v1/translate/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 2000), target_language_code: language })
      });
      setTranslated(result.translated_text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation failed. Your original report is unchanged.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel sarvam-panel" aria-labelledby="sarvam-title">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">INDIC-LANGUAGE REPORT</div>
          <h2 id="sarvam-title">Sarvam AI translation</h2>
          <p>Translate concise findings and recommendations for regional teams.</p>
        </div>
        <div className="panel-icon"><Languages size={19} /></div>
      </div>
      <div className="evidence-note">
        <ShieldCheck size={15} />
        Only this condensed report summary is sent after you choose Translate. Raw logcat is not sent.
      </div>
      {!enabled && (
        <p className="translation-unavailable" role="status">
          Translation is not configured on this backend. Add SARVAM_API_KEY as a server-only environment variable to enable it.
        </p>
      )}
      <div className="sarvam-controls">
        <label htmlFor="sarvam-language">Report language</label>
        <select id="sarvam-language" value={language} onChange={event => setLanguage(event.target.value as typeof language)}>
          {languages.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}
        </select>
        <button className="secondary-button" onClick={() => void translate()} disabled={!enabled || busy || !text.trim()}>
          {busy ? <LoaderCircle className="spin" size={15} /> : <Languages size={15} />}
          {busy ? "Translating…" : "Translate report"}
        </button>
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {translated && <div className="translation-result" lang={language} aria-live="polite">{translated}</div>}
    </section>
  );
}
