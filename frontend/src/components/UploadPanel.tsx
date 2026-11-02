import { useState, type FormEvent, type DragEvent, type ChangeEvent } from "react";
import { ArrowUpRight, CircleAlert, FlaskConical, LoaderCircle, UploadCloud } from "lucide-react";
import type { Persona, Worker } from "../api";

interface UploadPanelProps {
  apk: File | null;
  setApk: (file: File | null) => void;
  selected: string;
  setSelected: (id: string) => void;
  personas: Persona[];
  workers: Worker[];
  busy: boolean;
  apiStatus: string;
  directUploadAvailable: boolean;
  uploadAvailable: boolean;
  lockedReason?: string;
  onSubmit: (e: FormEvent) => Promise<void>;
}

const MAX_SIZE_BYTES = 150 * 1024 * 1024; // 150 MB

export default function UploadPanel({
  apk,
  setApk,
  selected,
  setSelected,
  personas,
  workers,
  busy,
  apiStatus,
  directUploadAvailable,
  uploadAvailable,
  lockedReason = "Run registration is unavailable until persistent PostgreSQL and private Supabase Storage are configured.",
  onSubmit
}: UploadPanelProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState("");

  function validateAndSetFile(file: File | null) {
    if (!uploadAvailable) {
      setApk(null);
      setFileError(lockedReason);
      return;
    }
    if (!file) {
      setApk(null);
      setFileError("");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".apk")) {
      setApk(null);
      setFileError("Invalid file type. Only .apk files are supported.");
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      setApk(null);
      setFileError(`File exceeds the 150 MB limit (${sizeMb} MB). Please choose a smaller APK.`);
      return;
    }

    setFileError("");
    setApk(file);
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] || null;
    validateAndSetFile(file);
  }

  function handleDragOver(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  }

  function handleDragLeave(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0] || null;
    validateAndSetFile(file);
  }

  return (
    <section className="panel run-panel" id="new-run">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">02 / START A SESSION</div>
          <h2>New test run</h2>
          <p>Upload an APK to register a run. Execution needs a worker.</p>
        </div>
        <div className="panel-icon">
          <UploadCloud size={19} />
        </div>
      </div>

      <form onSubmit={onSubmit}>
        <label
          className={"upload-zone" + (isDragging ? " dragging" : "")}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept=".apk,application/vnd.android.package-archive"
            onChange={handleFileChange}
            disabled={!uploadAvailable}
          />
          <span className="upload-icon">
            <UploadCloud size={22} />
          </span>
          <b>{apk ? apk.name : isDragging ? "Drop your APK here" : "Drop your APK here or click to browse"}</b>
          <small>
            {apk
              ? `${(apk.size / 1024 / 1024).toFixed(1)} MB · Ready to upload`
              : "Choose an APK to enable run registration"}
          </small>
          <span className="file-limit">{!uploadAvailable ? "APK registration unavailable" : directUploadAvailable ? "APK · Max 150 MB" : "APK · Max 4 MB"}</span>
        </label>

        {apiStatus === "offline" && (
          <div className="alert error-alert upload-inline-error" role="alert">
            <CircleAlert size={16} />
            <span>API is down or unreachable. Run registration is disabled.</span>
          </div>
        )}
        {apiStatus !== "offline" && !uploadAvailable && (
          <div className="alert error-alert upload-inline-error" role="status">
            <CircleAlert size={16} />
            <span>{lockedReason}</span>
          </div>
        )}

        {fileError && (
          <div className="alert error-alert upload-inline-error" role="alert">
            <CircleAlert size={16} />
            <span>{fileError}</span>
          </div>
        )}

        <label className="field-label" htmlFor="persona-select">
          Testing persona
        </label>
        <select
          id="persona-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={personas.length === 0 || apiStatus === "offline"}
        >
          {personas.length === 0 ? (
            <option value="">No personas available</option>
          ) : (
            personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name + " — " + p.device}
              </option>
            ))
          )}
        </select>

        <div className="run-warning">
          <CircleAlert size={16} />
          <span>
            {!uploadAvailable
              ? lockedReason + " No upload or test run will be attempted."
              : workers.some((w) => w.online)
                ? "A worker is online. The run will only count as executed after it submits a report with evidence."
                : "No worker heartbeat detected. This registers the APK; execution will wait for a worker and no test pass/failure is implied."}
          </span>
        </div>

        <button
          type="submit"
          className="primary-button full-button"
          disabled={busy || apiStatus === "offline" || !uploadAvailable || !apk}
        >
          {busy ? <LoaderCircle className="spin" size={16} /> : <FlaskConical size={16} />}
          {" "}
          {busy ? "Working…" : "Start / Register test run"}
          <ArrowUpRight size={15} />
        </button>
      </form>
    </section>
  );
}
