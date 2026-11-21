import { CircleAlert, Cpu, HardDrive, LoaderCircle, Radio, ShieldCheck, Smartphone, Wifi } from "lucide-react";
import { type Persona, cls } from "../api";

interface PersonaPanelProps {
  personas: Persona[];
  selected: string;
  setSelected: (id: string) => void;
  apiStatus: string;
  loading?: boolean;
}

export default function PersonaPanel({
  personas,
  selected,
  setSelected,
  apiStatus,
  loading = false
}: PersonaPanelProps) {
  const persona = personas.find((p) => p.id === selected) || personas[0];

  return (
    <section className="panel persona-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">01 / TEST ENVIRONMENT</div>
          <h2>Bharat personas</h2>
          <p>Choose a requested test profile for constrained usage conditions.</p>
          {apiStatus === "offline" && (
            <div className="alert error-alert" role="alert" style={{ margin: "10px 0" }}>
              <CircleAlert size={16} />
              <span>API is down or unreachable. Live test profiles could not be loaded.</span>
            </div>
          )}
          <p className="profile-caveat">
            These are authored targets, not measurements from physical devices. Full engine mode (BHARATSIM_WORKER_ENGINE=engine) can shape latency, bandwidth, packet-loss stalls, connection resets and outages through the Android system proxy; only traffic that uses that proxy is affected. The default legacy smoke worker has a narrower control set. Reports distinguish applied controls from observed app traffic. CPU throttling is unsupported; RAM behavior depends on emulator provisioning.
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
      {loading && personas.length === 0 ? (
        <div className="empty-state">
          <LoaderCircle className="spin" size={24} />
          <b>Loading test profiles…</b>
          <p>Fetching profiles from the API.</p>
        </div>
      ) : personas.length === 0 ? (
        <div className="empty-state">
          <Smartphone size={24} />
          <b>No personas available</b>
          <p>No test profiles found.</p>
        </div>
      ) : (
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
      )}
      {persona && (
        <div className="persona-detail">
          <div>
            <span>SELECTED PROFILE</span>
            <b>{persona.name}</b>
          </div>
          <p>{persona.description}</p>
          <p className="profile-caveat">
            Profile targets are not device measurements. Full engine mode (BHARATSIM_WORKER_ENGINE=engine) uses a host proxy for latency, bandwidth, packet-loss stalls, resets and outages, plus supported emulator device controls. Only app traffic that uses the Android system proxy is shaped; each report records whether traffic was observed. The default legacy smoke worker supports fewer controls. CPU throttling is unsupported and RAM limits depend on emulator provisioning.
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
              <small>PACKET LOSS</small>
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
