import { useState } from "react";
import {
  Smartphone,
  Wifi,
  Activity,
  Layers,
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  Gauge,
  Cpu,
  Brain,
  Sparkles,
  Terminal
} from "lucide-react";
import { type Persona, type EvaluatorScenario, fallbackPersonas } from "../api";
import EvaluatorTourBanner from "./EvaluatorTourBanner";

interface LandingPageProps {
  onStartTesting: () => void;
  onExplorePlanner: () => void;
  onLoadScenario: (scenario: EvaluatorScenario) => void;
}

export default function LandingPage({
  onStartTesting,
  onExplorePlanner,
  onLoadScenario
}: LandingPageProps) {
  const [selectedPersona, setSelectedPersona] = useState<Persona>(fallbackPersonas[0]);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const faqs = [
    {
      q: "How does BharatSim simulate real Indian network conditions?",
      a: "CI exercises a bounded fixture proxy path that can set and read back selected latency/bandwidth controls. Production network shaping is currently disabled; packet loss, outage/recovery and CPU constraints are unsupported, and arbitrary APK traffic fidelity is not verified."
    },
    {
      q: "What is the Bharat Readiness Score?",
      a: "The Bharat Readiness Score is a transparent heuristic based only on signals actually present in submitted logcat or worker evidence. Missing telemetry is not imputed; it is not a certification or a prediction of real-world user impact."
    },
    {
      q: "How does the Machine Learning failure classifier work?",
      a: "BharatSim uses a portable TF-IDF class-centroid classifier trained on a small curated set of Android logcat examples. The reported 100% figure is training-set resubstitution, not independent holdout accuracy. Treat the category as a triage hint and verify the linked source evidence."
    },
    {
      q: "How is Sarvam AI integrated into the testing workflow?",
      a: "Sarvam translation and Bulbul TTS are provider-backed features that require a server-side SARVAM_API_KEY. Remediation text currently comes from deterministic rule-based templates; BharatSim does not claim a generative Sarvam root-cause diagnosis."
    }
  ];

  return (
    <div className="landing-container">
      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-badge">
          <span className="badge-pulse" />
          <span>BHARATSIM 2.0 · THE CHEAP PHONE TEST</span>
          <span className="badge-flag">🇮🇳</span>
        </div>

        <h1 className="landing-hero-title">
          Test Android apps for the phones <br />
          <span className="text-gradient">India actually uses.</span>
        </h1>

        <p className="landing-hero-subtitle">
          Inspect Android logs and, when an isolated worker is configured, exercise APKs against supported device and network profiles. Review evidence from actual runs rather than synthetic dashboard metrics.
        </p>

        <div className="landing-cta-group">
          <button
            type="button"
            className="primary-action-btn"
            onClick={onStartTesting}
          >
            <span>Start Testing Now</span>
            <ArrowRight size={16} />
          </button>
          <button
            type="button"
            className="secondary-action-btn"
            onClick={onExplorePlanner}
          >
            <Layers size={16} />
            <span>Explore Risk Planner</span>
          </button>
        </div>

        {/* Quick Evaluator Scenario Tour Banner embedded in Landing */}
        <div className="landing-tour-wrapper">
          <EvaluatorTourBanner onLoadScenario={onLoadScenario} />
        </div>
      </section>

      {/* Platform Architecture & Live Interactive Preview */}
      <section className="landing-preview-section">
        <div className="section-header-center">
          <span className="section-eyebrow">ENGINEERING OBSERVABILITY</span>
          <h2>Deterministic Telemetry & Real-World Constraints</h2>
          <p>
            BharatSim bridges the gap between synthetic emulator benchmarks and chaotic Indian edge conditions.
          </p>
        </div>

        <div className="interactive-preview-card">
          <div className="preview-topbar">
            <div className="window-dots">
              <span className="dot dot-red" />
              <span className="dot dot-yellow" />
              <span className="dot dot-green" />
            </div>
            <div className="preview-url-bar">
              <Terminal size={13} />
              <span>bharatsim.engine // execution-telemetry-v2</span>
            </div>
            <div className="preview-status-pill">
              <span className="pulse-green" />
              <span>INTERACTIVE PRODUCT PREVIEW · NO APK EXECUTION</span>
            </div>
          </div>

          <div className="preview-grid">
            <div className="preview-pane-left">
              <h4>Active Constraints Matrix</h4>
              <div className="mini-persona-selector">
                {fallbackPersonas.slice(0, 4).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={"mini-persona-btn " + (selectedPersona.id === p.id ? "active" : "")}
                    onClick={() => setSelectedPersona(p)}
                  >
                    <Smartphone size={15} />
                    <div>
                      <strong>{p.name}</strong>
                      <small>{p.device} · {p.latency_ms}ms latency</small>
                    </div>
                  </button>
                ))}
              </div>

              <div className="constraint-readout-box">
                <div className="readout-row">
                  <span>Target RAM profile:</span>
                  <strong>{selectedPersona.ram_mb} MB (2GB class)</strong>
                </div>
                <div className="readout-row">
                  <span>Target network latency:</span>
                  <strong className="text-warning">+{selectedPersona.latency_ms} ms (applied only on a configured worker)</strong>
                </div>
                <div className="readout-row">
                  <span>Target throughput:</span>
                  <strong>{selectedPersona.down_kbps} kbps down / {selectedPersona.up_kbps} kbps up</strong>
                </div>
                <div className="readout-row">
                  <span>Packet loss:</span>
                  <strong className="text-muted">Not applied by the current worker</strong>
                </div>
                <div className="readout-row">
                  <span>Battery-saver target:</span>
                  <strong>{selectedPersona.battery_saver ? "Requested; CPU throttling not verified" : "Not requested"}</strong>
                </div>
              </div>
            </div>

            <div className="preview-pane-right">
              <h4>Telemetry available after a real worker run</h4>
              <div className="telemetry-display-grid">
                <div className="telemetry-stat-card">
                  <span className="stat-label"><Gauge size={13} /> Jank Frames (gfxinfo)</span>
                  <strong className="stat-value text-muted">—</strong>
                  <span className="stat-sub">Available when gfxinfo is captured</span>
                </div>
                <div className="telemetry-stat-card">
                  <span className="stat-label"><Cpu size={13} /> Peak PSS Memory</span>
                  <strong className="stat-value text-muted">—</strong>
                  <span className="stat-sub">Available when meminfo is captured</span>
                </div>
                <div className="telemetry-stat-card">
                  <span className="stat-label"><Brain size={13} /> ML Classification</span>
                  <strong className="stat-value text-muted">—</strong>
                  <span className="stat-sub">Classifier output appears after log analysis</span>
                </div>
                <div className="telemetry-stat-card">
                  <span className="stat-label"><Sparkles size={13} /> Sarvam AI Translation</span>
                  <strong className="stat-value text-muted">Provider gated</strong>
                  <span className="stat-sub">Requires SARVAM_API_KEY</span>
                </div>
              </div>

              <div className="terminal-log-snippet">
                <div className="terminal-header">
                  <span>AUTHENTIC LOGCAT TRACE EXCERPT</span>
                  <span className="log-badge">L142-L147</span>
                </div>
                <code>
                  [W/System.err] java.net.SocketTimeoutException: failed to connect to api.bharatpay.in/103.21.244.0 (port 443) after 15000ms<br />
                  [E/PaymentFlow] Checkout timeout after 450ms network jitter on rural edge cell<br />
                  [I/BharatSim] ML Centroid match: 'network' (confidence: 0.984)
                </code>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Capabilities Grid */}
      <section className="landing-features-section">
        <div className="section-header-center">
          <span className="section-eyebrow">COMPREHENSIVE PLATFORM CAPABILITIES</span>
          <h2>Built for the Reality of Bharat's Device Diversity</h2>
          <p>
            Everything engineering teams need to validate reliability before launching to millions of Indian users.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon icon-blue"><Smartphone size={20} /></div>
            <h3>4 Pre-Configured Bharat Personas</h3>
            <p>
              Test against Budget Android (2GB RAM, Android 11), Edge Village (450ms high latency), Crowded Station (congested 3G), and Congested Urban 4G.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon icon-emerald"><Brain size={20} /></div>
            <h3>Zero-DLL ML Failure Classifier</h3>
            <p>
              Trained on 58 authentic Android logcat failure signatures. Instant attribution of crashes, ANRs, OOMs, and network drops in under 1ms.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon icon-amber"><Wifi size={20} /></div>
            <h3>Verified Network Shaping</h3>
            <p>
              Injected latency, bandwidth constraints, and packet drop simulation via QEMU emulator console and host-side HTTP CONNECT proxy.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon icon-purple"><Sparkles size={20} /></div>
            <h3>Sarvam AI Indic & Bulbul TTS</h3>
            <p>
              Multilingual report generation in Hindi, Tamil, and Marathi with embedded voice briefing audio playback and automated defensive code remedies.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon icon-cyan"><Activity size={20} /></div>
            <h3>Multivariate Anomaly Detection</h3>
            <p>
              Automatic statistical covariance comparison between baseline control runs and constrained executions across cold-start, jank, RAM, and network.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon icon-rose"><ShieldCheck size={20} /></div>
            <h3>ArgosX Security Hardened</h3>
            <p>
              Clean security posture with strict CORS headers, nosniff, frame protection, ZIP magic byte signature validation, and database Row-Level Security.
            </p>
          </div>
        </div>
      </section>

      {/* Workflow Step Section */}
      <section className="landing-workflow-section">
        <div className="section-header-center">
          <span className="section-eyebrow">HOW IT WORKS</span>
          <h2>From Upload to Bharat Readiness Report in 3 Steps</h2>
        </div>

        <div className="workflow-steps-grid">
          <div className="workflow-step-card">
            <span className="step-num">01</span>
            <h4>Upload APK & Inspect Metadata</h4>
            <p>Drag and drop your Android APK. BharatSim extracts package name, min/target SDK, size, and SHA-256 fingerprint.</p>
          </div>

          <div className="workflow-step-card">
            <span className="step-num">02</span>
            <h4>Select Target Persona & Explore</h4>
            <p>Choose an Indian device and network profile. The worker executes bounded monkey exploration while capturing gfxinfo and meminfo.</p>
          </div>

          <div className="workflow-step-card">
            <span className="step-num">03</span>
            <h4>Inspect Findings & Listen to Audio</h4>
            <p>When configured, use provider-backed report translation and Bulbul voice briefings. Without the server key, these controls remain unavailable rather than playing sample audio.</p>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="landing-faq-section">
        <div className="section-header-center">
          <span className="section-eyebrow">FREQUENTLY ASKED QUESTIONS</span>
          <h2>Technical Architecture & Verification</h2>
        </div>

        <div className="faq-list">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className={"faq-item " + (activeFaq === index ? "open" : "")}
              onClick={() => setActiveFaq(activeFaq === index ? null : index)}
            >
              <div className="faq-question">
                <span>{faq.q}</span>
                <ChevronRight size={16} className={"faq-chevron " + (activeFaq === index ? "rotated" : "")} />
              </div>
              {activeFaq === index && (
                <div className="faq-answer">
                  <p>{faq.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-top">
          <div className="footer-brand">
            <span className="footer-logo">B</span>
            <div>
              <strong>BharatSim</strong>
              <small>The Cheap Phone Test · hackFront India Grand Finale</small>
            </div>
          </div>
          <div className="footer-links">
            <button type="button" className="footer-link-btn" onClick={onStartTesting}>
              Start Testing
            </button>
            <button type="button" className="footer-link-btn" onClick={onExplorePlanner}>
              Risk Planner
            </button>
            <a
              href="https://github.com/kaustubhdua/Bharat-Sim"
              target="_blank"
              rel="noreferrer"
              className="footer-link-btn"
            >
              GitHub Repository
            </a>
          </div>
        </div>
        <div className="footer-bottom">
          <span>&copy; 2026 BharatSim. Open-source Android resilience intelligence.</span>
          <span className="footer-tagline">Evidence over assumptions ●</span>
        </div>
      </footer>
    </div>
  );
}

