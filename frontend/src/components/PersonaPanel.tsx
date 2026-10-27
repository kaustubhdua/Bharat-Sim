import { Cpu, HardDrive, Radio, ShieldCheck, Smartphone, Wifi } from "lucide-react";
import { type Persona, cls } from "../api";

interface PersonaPanelProps {
  personas: Persona[];
  selected: string;
  setSelected: (id: string) => void;
  apiStatus: string;
}

export default function PersonaPanel({
  personas,
  selected,
  setSelected,
  apiStatus
}: PersonaPanelProps) {
  const persona = personas.find((p) => p.id === selected) || personas[0];

  return (
    <section className="panel persona-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">01 / TEST ENVIRONMENT</div>
          <h2>Bharat personas</h2>
          <p>Choose a requested test profile for constrained usage conditions.</p>
          <p className="profile-caveat">
            These are authored test targets, not measurements from physical devices. The worker applies and verifies emulator latency, bandwidth, battery-saver and bounded storage-pressure conditions; packet loss and CPU throttling are unsupported, RAM is report-only, and arbitrary traffic-path verification is fixture-only.
          </p>
          {apiStatus !== "online" && (
            <p className="profile-caveat">
              {apiStatus === "offline"
                ? "API unavailable: these are local reference templates, not live device measurements. Upload and execution actions remain disabled."
                : "Connecting to API; local reference templates are shown temporarily."}
            </p>
          )}
        </div>
        <span className="section-kicker">{personas.length} REFERENCE PROFILES</span>
      </div>
      <div className="persona-list">
        {personas.map((p) => (
          <button
            key={p.id}
            className={"persona-row " + (selected === p.id ? "selected" : "")}
            onClick={() => setSelected(p.id)}
          >
            <span className="persona-icon">
              {p.id === "baseline" ? (
                <ShieldCheck size={18} />
              ) : p.id === "storage-pressure" ? (
                <HardDrive size={18} />
              ) : p.id === "edge-village" ? (
                <Radio size={18} />
              ) : (
                <Smartphone size={18} />
              )}
            </span>
            <span className="persona-info">
              <b>{p.name}</b>
              <small>{p.device}</small>
              <span className="persona-tags">
                <span>
                  <Wifi size={12} />
                  {p.latency_ms} ms
                </span>
                <span>
                  <Cpu size={12} />
                  {p.ram_mb / 1024} GB RAM
                </span>
                <span>
                  <HardDrive size={12} />
                  {p.storage_free_mb} MB free
                </span>
              </span>
            </span>
            <span className={"risk-badge " + cls(p.risk)}>{p.risk}</span>
            <span className="radio-dot">{selected === p.id && <i />}</span>
          </button>
        ))}
      </div>
      {persona && (
        <div className="persona-detail">
          <div>
            <span>SELECTED PROFILE</span>
            <b>{persona.name}</b>
          </div>
          <p>{persona.description}</p>
          <p className="profile-caveat">
            Profile targets are not device measurements. Emulator runs can apply and verify latency, bandwidth, battery-saver and bounded storage-pressure conditions; fixture CI separately measures a real request. Packet loss and CPU throttling remain unsupported, RAM is report-only, and arbitrary APK traffic is not verified.
          </p>
          <div className="detail-grid">
            <span>
              <small>DOWNLOAD</small>
              <b>
                {persona.down_kbps.toLocaleString()} <i>kbps</i>
              </b>
            </span>
            <span>
              <small>UPLOAD</small>
              <b>
                {persona.up_kbps.toLocaleString()} <i>kbps</i>
              </b>
            </span>
            <span>
              <small>PACKET LOSS · NOT APPLIED</small>
              <b>{persona.packet_loss_pct}% target</b>
            </span>
            <span>
              <small>RISK LEVEL</small>
              <b>
                {persona.risk === "critical"
                  ? "Very high"
                  : persona.risk === "high"
                  ? "Elevated"
                  : "Controlled"}
              </b>
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
