import { useEffect, useRef, useState } from "react";
import { Volume2, VolumeX, LoaderCircle } from "lucide-react";
import { api, synthesizeSpeechAudio, type Capabilities } from "../api";

interface SarvamAudioPlayerProps {
  text: string;
  defaultLang?: string;
  label?: string;
}

let ttsCapabilityPromise: Promise<boolean> | null = null;

function getTtsAvailability(): Promise<boolean> {
  if (!ttsCapabilityPromise) {
    ttsCapabilityPromise = api<Capabilities>("/api/v1/capabilities")
      .then((capabilities) => capabilities.sarvam_audio_tts === true)
      .catch(() => {
        ttsCapabilityPromise = null;
        return false;
      });
  }
  return ttsCapabilityPromise;
}

const LANGUAGES = [
  { code: "hi-IN", name: "Hindi" },
  { code: "ta-IN", name: "Tamil" },
  { code: "mr-IN", name: "Marathi" },
  { code: "en-IN", name: "English" }
];

export default function SarvamAudioPlayer({
  text,
  defaultLang = "hi-IN",
  label = "Listen to diagnostic briefing (Sarvam Bulbul TTS)"
}: SarvamAudioPlayerProps) {
  const [lang, setLang] = useState(defaultLang);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ttsAvailable, setTtsAvailable] = useState<boolean | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    void getTtsAvailability().then((available) => {
      if (active) setTtsAvailable(available);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const handlePlay = async () => {
    if (ttsAvailable !== true) {
      setError("Speech generation is unavailable. Configure SARVAM_API_KEY in the server environment.");
      return;
    }
    if (playing && audioRef.current) {
      audioRef.current.pause();
      setPlaying(false);
      return;
    }

    if (audioUrl && audioRef.current) {
      try {
        await audioRef.current.play();
        setPlaying(true);
      } catch {
        setError("The browser could not start audio playback.");
      }
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await synthesizeSpeechAudio(text.slice(0, 500), lang);

      // The API deliberately returns an explicitly marked silent fixture when
      // SARVAM_API_KEY is absent. Never present that fixture as spoken output.
      if (response.is_fixture) {
        throw new Error(response.note || "Sarvam speech generation is not configured. No spoken audio was generated.");
      }
      if (!response.audio_base64) {
        throw new Error("Sarvam returned an empty audio response.");
      }

      const binary = atob(response.audio_base64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      const blob = new Blob([bytes], { type: response.format || "audio/wav" });
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      audio.onerror = () => {
        setPlaying(false);
        setError("Audio playback failed.");
      };
      setAudioUrl(url);
      await audio.play();
      setPlaying(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speech synthesis failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageChange = (newLanguage: string) => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setAudioUrl(null);
    setPlaying(false);
    setError(null);
    setLang(newLanguage);
  };

  return (
    <div className="sarvam-audio-player">
      <div className="audio-player-header">
        <span className="audio-label">{label}</span>
        <div className="audio-lang-selector" aria-label="Audio language">
          {LANGUAGES.map((language) => (
            <button
              key={language.code}
              type="button"
              className={"lang-chip " + (lang === language.code ? "active" : "")}
              aria-pressed={lang === language.code}
              onClick={() => handleLanguageChange(language.code)}
            >
              {language.name}
            </button>
          ))}
        </div>
      </div>

      <div className="audio-player-controls">
        <button
          type="button"
          className={"audio-play-button " + (playing ? "playing" : "")}
          onClick={() => void handlePlay()}
          disabled={ttsAvailable !== true || loading || !text.trim()}
          title={ttsAvailable === true ? (playing ? "Pause briefing" : "Generate and play voice briefing") : "Sarvam speech generation is not configured"}
        >
          {loading ? (
            <LoaderCircle size={15} className="spin" />
          ) : playing ? (
            <VolumeX size={15} />
          ) : (
            <Volume2 size={15} />
          )}
          <span>{ttsAvailable === null ? "Checking voice availability…" : ttsAvailable === false ? "Voice unavailable" : loading ? "Generating audio…" : playing ? "Pause audio" : audioUrl ? "Play audio" : "Generate voice briefing"}</span>
        </button>
      </div>

      {ttsAvailable === false && <span className="audio-error" role="status">Voice generation is not configured on this backend. Add SARVAM_API_KEY as a server-only environment variable.</span>}
      {error && <span className="audio-error" role="status">{error}</span>}
    </div>
  );
}
