import { Activity, CheckCircle2, CircleAlert, Clock3, ShieldCheck, XCircle } from "lucide-react";
import type { Capabilities } from "../api";

interface CapabilityPanelProps {
  capabilities: Capabilities | null;
  loading: boolean;
}

type Tone = "good" | "caution" | "off";

function Status({ label, tone }: { label: string; tone: Tone }) {
  const Icon = tone === "good" ? CheckCircle2 : tone === "caution" ? Clock3 : XCircle;
  return <span className={"capability-status " + tone}><Icon size={12} aria-hidden="true" /> {label}</span>;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CapabilityPanel({ capabilities, loading }: CapabilityPanelProps) {
  if (loading && !capabilities) {
    return (
      <section className="panel capability-panel" aria-busy="true">
        <div className="panel-heading">
          <div><div className="section-kicker">PLATFORM CONTRACT</div><h2>Live capabilities</h2><p>Loading the capability contract from the API…</p></div>
          <div className="panel-icon"><Activity size={19} /></div>
        </div>
        <div className="empty-state"><Clock3 size={24} /><b>Checking supported features</b></div>
      </section>
    );
  }

  if (!capabilities) {
    return (
      <section className="panel capability-panel">
        <div className="panel-heading">
          <div><div className="section-kicker">PLATFORM CONTRACT</div><h2>Live capabilities</h2><p>Capability data is unavailable while the API is offline.</p></div>
          <div className="panel-icon"><CircleAlert size={19} /></div>
        </div>
        <div className="alert error-alert" role="status"><CircleAlert size={16} /><span>Reconnect to the API to load the authoritative capability contract. No feature availability is inferred.</span></div>
      </section>
    );
  }

  const productFeatures = [
    ["APK upload and validation", capabilities.apk_upload],
    ["Logcat signal analysis", capabilities.log_analysis],
    ["Risk prioritization", capabilities.risk_planner],
    ["Failure fingerprinting", capabilities.failure_fingerprinting],
    ["BharatScore heuristic", capabilities.bharat_score],
  ] as const;
  const network = capabilities.emulator_network_controls;
  const conditions = capabilities.persona_condition_simulation;

  return (
    <section className="panel capability-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">PLATFORM CONTRACT · LIVE API DATA</div>
          <h2>What BharatSim can verify</h2>
          <p>Support is reported by the backend capability endpoint, not inferred from a selected persona or a UI control.</p>
        </div>
        <div className="panel-icon"><ShieldCheck size={19} /></div>
      </div>

      <div className="capability-groups">
        <section className="capability-group">
          <div className="capability-group-title"><Activity size={15} /><h3>Analysis tools</h3></div>
          {productFeatures.map(([label, enabled]) => (
            <div className="capability-row" key={label}>
              <span>{label}</span><Status label={enabled ? "Available" : "Unavailable"} tone={enabled ? "good" : "off"} />
            </div>
          ))}
          <div className="capability-row">
            <span>Sarvam translation</span><Status label={capabilities.sarvam_translation ? "Integrated" : "Not integrated"} tone={capabilities.sarvam_translation ? "good" : "off"} />
          </div>
        </section>

        <section className="capability-group">
          <div className="capability-group-title"><ShieldCheck size={15} /><h3>Execution readiness</h3></div>
          <div className="capability-row">
            <span>Worker dispatch</span><Status label={capabilities.worker_dispatch ? "Configured" : "Not configured"} tone={capabilities.worker_dispatch ? "good" : "off"} />
          </div>
          <div className="capability-row">
            <span>Android execution proof</span><Status label={capabilities.android_execution ? "Attested" : "Evidence required"} tone={capabilities.android_execution ? "good" : "caution"} />
          </div>
          <p className="capability-note">A configured worker is not proof that a specific APK ran. Each run must have a worker-submitted report and inspectable evidence.</p>
        </section>

        <section className="capability-group">
          <div className="capability-group-title"><Activity size={15} /><h3>Emulator network controls</h3></div>
          <div className="capability-row"><span>Latency</span><Status label={network.latency ? "Supported" : "Unsupported"} tone={network.latency ? "good" : "off"} /></div>
          <div className="capability-row"><span>Bandwidth</span><Status label={network.bandwidth ? "Supported" : "Unsupported"} tone={network.bandwidth ? "good" : "off"} /></div>
          <div className="capability-row"><span>Control readback</span><Status label={network.configuration_readback ? "Supported" : "Unsupported"} tone={network.configuration_readback ? "good" : "off"} /></div>
          <div className="capability-row"><span>Packet loss / outage recovery</span><Status label={network.packet_loss || network.outage_and_recovery ? "Supported" : "Unsupported"} tone={network.packet_loss || network.outage_and_recovery ? "good" : "off"} /></div>
          <div className="capability-row"><span>Arbitrary app traffic verification</span><Status label={network.arbitrary_app_traffic_verified ? "Verified" : "Not verified"} tone={network.arbitrary_app_traffic_verified ? "good" : "caution"} /></div>
          <p className="capability-note">{network.scope}</p>
        </section>
      </div>

      <div className="condition-contract">
        <div><b>Persona condition support</b><span>Actual backend declarations</span></div>
        <div className="condition-chips">
          {conditions.supported.map((item) => <span className="condition-chip supported" key={item}><CheckCircle2 size={12} />{humanize(item)}</span>)}
          {conditions.control_plane_verifiable.map((item) => <span className="condition-chip verifiable" key={item}><Clock3 size={12} />{humanize(item)} · control readback</span>)}
          {conditions.report_only.map((item) => <span className="condition-chip report-only" key={item}><Clock3 size={12} />{humanize(item)} · report-only</span>)}
          {conditions.unsupported.map((item) => <span className="condition-chip unsupported" key={item}><XCircle size={12} />{humanize(item)} · unsupported</span>)}
        </div>
        <p className="capability-note">{conditions.scope}</p>
      </div>
    </section>
  );
}
