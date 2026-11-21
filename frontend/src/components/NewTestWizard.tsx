import { useState, useRef, type ChangeEvent, type DragEvent } from "react";
import {
  Upload,
  AlertTriangle,
  Play,
  FileCheck,
  LoaderCircle,
  X
} from "lucide-react";
import { type Persona } from "../api";

interface NewTestWizardProps {
  personas: Persona[];
  selectedPersona: string;
  onSelectPersona: (id: string) => void;
  busy: boolean;
  uploadAvailable: boolean;
  maxUploadMb?: number;
  lockedReason?: string;
  onSubmit: (apkFile: File) => Promise<void>;
  onCancel: () => void;
}

export default function NewTestWizard({
  personas,
  selectedPersona,
  onSelectPersona,
  busy,
  uploadAvailable,
  maxUploadMb = 150,
  lockedReason,
  onSubmit,
  onCancel
}: NewTestWizardProps) {
  const [apkFile, setApkFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [fileSha, setFileSha] = useState<string | null>(null);
  const [calculatingHash, setCalculatingHash] = useState(false);
  // Current worker API applies fixed defaults; these are shown read-only until per-run overrides are supported.
  const interactionCount = 100;
  const enableGfxinfo = true;
  const enableMeminfo = true;
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activePersonaObj = personas.find((p) => p.id === selectedPersona) || personas[0];

  const validateAndSetFile = async (file: File) => {
    setValidationError(null);
    setFileSha(null);
    setApkFile(null);

    if (!uploadAvailable) {
      setValidationError(lockedReason || "APK registration is unavailable on this deployment.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".apk")) {
      setValidationError("File must be an Android APK package (.apk extension).");
      return;
    }

    if (file.size > maxUploadMb * 1024 * 1024) {
      setValidationError(`File exceeds the configured maximum upload size of ${maxUploadMb} MB.`);
      return;
    }

    // Verify ZIP magic bytes (PK\x03\x04)
    try {
      const slice = file.slice(0, 4);
      const buffer = await slice.arrayBuffer();
      const view = new DataView(buffer);
      const magic = view.getUint32(0, false);
      if (magic !== 0x504b0304) {
        setValidationError("Invalid APK signature: File does not start with standard ZIP magic bytes.");
        return;
      }
    } catch {
      setValidationError("Could not read file header.");
      return;
    }

    setApkFile(file);

    // Compute SHA-256 for integrity verification
    setCalculatingHash(true);
    try {
      const fullBuffer = await file.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", fullBuffer);
      const hashArray = Array.from(new Uint8Array(digest));
      const hashHex = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
      setFileSha(hashHex);
    } catch {
      // Best-effort calculation
    } finally {
      setCalculatingHash(false);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void validateAndSetFile(file);
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void validateAndSetFile(file);
  };

  const handleSubmit = async () => {
    if (!apkFile) return;
    await onSubmit(apkFile);
  };

  return (
    <div className="panel full-panel wizard-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">STEP-BY-STEP TEST SETUP</div>
          <h2>Configure Android Resilience Execution</h2>
          <p>
            Upload your production or staging APK, select an Indian network and hardware persona, and launch automated exploration.
          </p>
        </div>
        <button type="button" className="icon-button" onClick={onCancel} aria-label="Cancel">
          <X size={18} />
        </button>
      </div>

      <div className="wizard-stepper">
        {/* Step 1: Upload APK */}
        <div className="wizard-step-section">
          <div className="step-badge">
            <span>01</span>
            <h3>Select Android APK</h3>
          </div>

          <div
            className={"wizard-upload-dropzone " + (isDragging ? "dragging" : "") + (apkFile ? "has-file" : "")}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            role="button"
            tabIndex={uploadAvailable ? 0 : -1}
            aria-label="Choose Android APK file"
            aria-disabled={!uploadAvailable}
            onKeyDown={(event) => {
              if (uploadAvailable && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onClick={() => { if (uploadAvailable) fileInputRef.current?.click(); }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".apk"
              style={{ display: "none" }}
              disabled={!uploadAvailable}
              onChange={handleFileChange}
            />

            {apkFile ? (
              <div className="file-preview-card">
                <FileCheck size={36} className="text-accent" />
                <div className="file-preview-meta">
                  <b>{apkFile.name}</b>
                  <span>{(apkFile.size / (1024 * 1024)).toFixed(2)} MB · ZIP Signature Verified</span>
                  {calculatingHash ? (
                    <small><LoaderCircle size={12} className="spin" /> Calculating SHA-256…</small>
                  ) : fileSha ? (
                    <code>SHA-256: {fileSha.slice(0, 24)}…</code>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="change-file-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setApkFile(null);
                  }}
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="upload-placeholder">
                <Upload size={32} />
                <b>Drag and drop your Android APK here, or click to browse</b>
                <p>Supports .apk packages up to {maxUploadMb} MB. Binary signature is validated before upload.</p>
              </div>
            )}
          </div>

          {validationError && (
            <div className="alert error-alert" style={{ marginTop: 10 }}>
              <AlertTriangle size={15} />
              <span>{validationError}</span>
            </div>
          )}
        </div>

        {/* Step 2: Target Persona Selection */}
        <div className="wizard-step-section">
          <div className="step-badge">
            <span>02</span>
            <h3>Choose BharatSim Device & Network Persona</h3>
          </div>

          <div className="wizard-persona-grid">
            {personas.map((p) => (
              <button
                type="button"
                key={p.id}
                className={"wizard-persona-card " + (selectedPersona === p.id ? "selected" : "")}
                aria-pressed={selectedPersona === p.id}
                onClick={() => onSelectPersona(p.id)}
              >
                <div className="persona-top">
                  <div className="persona-title-group">
                    <strong>{p.name}</strong>
                    <small>{p.device}</small>
                  </div>
                  <span className={"risk-badge " + p.risk}>{p.risk.toUpperCase()}</span>
                </div>

                <p className="persona-desc">{p.description}</p>

                <div className="persona-specs">
                  <div>
                    <small>RAM Budget</small>
                    <b>{p.ram_mb} MB</b>
                  </div>
                  <div>
                    <small>Latency</small>
                    <b className="text-warning">+{p.latency_ms} ms</b>
                  </div>
                  <div>
                    <small>Bandwidth</small>
                    <b>{p.down_kbps} kbps</b>
                  </div>
                  <div>
                    <small>Packet Loss Target · Unsupported</small>
                    <b>{p.packet_loss_pct}%</b>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <p className="worker-defaults-note">
            Persona values are requested targets, not proof that every condition is applied. The worker verifies supported latency/bandwidth and reversible battery/storage controls; packet loss and CPU throttling are unsupported, while RAM is report-only.
          </p>
        </div>

        {/* Step 3: Exploration & Telemetry Options */}
        <div className="wizard-step-section">
          <div className="step-badge">
            <span>03</span>
            <h3>Exploration & Telemetry Settings</h3>
          </div>

          <div className="wizard-settings-row">
            <div className="setting-box">
              <label htmlFor="monkey-events">Automated UI Exploration</label>
              <select id="monkey-events" value={interactionCount} disabled aria-describedby="worker-defaults-note">
                <option value={50}>50 Throttled Monkey Events (Quick Smoke)</option>
                <option value={100}>100 Throttled Monkey Events (Recommended)</option>
                <option value={200}>200 Throttled Monkey Events (Deep Stress)</option>
              </select>
              <small>Throttled at 250ms per action, zero system/appswitch key exits.</small>
            </div>

            <div className="telemetry-toggles">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={enableGfxinfo}
                  disabled
                />
                <span>Capture Frame Render Jank (`dumpsys gfxinfo`)</span>
              </label>

              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={enableMeminfo}
                  disabled
                />
                <span>Capture Memory Footprint (`dumpsys meminfo PSS`)</span>
              </label>
            </div>
          </div>
          <p id="worker-defaults-note" className="worker-defaults-note">These are the current worker defaults. Per-run monkey-event and telemetry overrides are not yet supported by the run-registration API, so these controls are read-only and will not imply a custom configuration.</p>
        </div>

        {/* Action Summary & Submit */}
        <div className="wizard-submit-bar">
          <div className="wizard-summary-text">
            <span>Selected Target: <b>{activePersonaObj?.name}</b></span>
            <span>Target APK: <b>{apkFile?.name || "None selected"}</b></span>
          </div>

          <div className="wizard-buttons">
            <button type="button" className="secondary-button" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
            <button
              type="button"
              className="primary-button"
              disabled={!apkFile || busy || !uploadAvailable}
              onClick={() => void handleSubmit()}
            >
              {busy ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}
              <span>{busy ? "Registering Run…" : "Launch Resilience Test"}</span>
            </button>
          </div>
        </div>

        {!uploadAvailable && lockedReason && (
          <div className="alert error-alert" style={{ marginTop: 12 }}>
            <AlertTriangle size={15} />
            <span>{lockedReason}</span>
          </div>
        )}
      </div>
    </div>
  );
}

