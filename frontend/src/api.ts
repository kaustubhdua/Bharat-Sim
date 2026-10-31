export const API = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export type Capabilities = {
  apk_upload: boolean; log_analysis: boolean; risk_planner: boolean;
  failure_fingerprinting: boolean; bharat_score: boolean; android_execution: boolean;
  worker_dispatch: boolean; network_shaping: boolean; sarvam_translation: boolean;
  emulator_network_controls: {
    latency: boolean; bandwidth: boolean; configuration_readback: boolean;
    packet_loss: boolean; outage_and_recovery: boolean; arbitrary_app_traffic_verified: boolean; scope: string;
  };
  persona_condition_simulation: {
    supported: string[]; control_plane_verifiable: string[]; report_only: string[]; unsupported: string[]; scope: string;
  };
  notes: string[];
};

export type Persona = {
  id: string;
  name: string;
  device: string;
  ram_mb: number;
  storage_free_mb: number;
  network: string;
  latency_ms: number;
  down_kbps: number;
  up_kbps: number;
  packet_loss_pct: number;
  battery_saver: boolean;
  risk: string;
  description: string;
};

export type FindingEvidence = {
  line: number;
  text: string;
};

export type Finding = {
  id: string;
  kind: string;
  title: string;
  severity: string;
  evidence: FindingEvidence[];
  explanation: string;
  recommendation: string;
};

export type Analysis = {
  id: string;
  source: string;
  evidence_lines: number;
  findings: Finding[];
  summary: {
    finding_count: number;
    critical: number;
    high: number;
    medium: number;
    clean: boolean;
  };
  bharat_score: {
    value: number;
    label: string;
    method: string;
    warning: string;
  };
  limitations: string[];
  persona: Persona;
};

export type Run = {
  id: string;
  created_at: string;
  status: string;
  apk_name?: string;
  apk_sha256?: string;
  persona_id: string;
  error?: string;
};

export type Worker = {
  id: string;
  status: string;
  online: boolean;
  current_run_id?: string | null;
  last_seen: string;
};

export type LogSignalEvidence = {
  line_number: number;
  text: string;
};

export type LogSignal = {
  category: string;
  line_number: number;
  marker: string;
  evidence: LogSignalEvidence[];
};

export type SmokeStep = {
  name: string;
  return_code: number;
  duration_seconds: number;
  stdout_tail?: string;
  stderr_tail?: string;
};

export type NetworkProfileRequested = {
  latency_ms?: number;
  download_kbps?: number;
  upload_kbps?: number;
  packet_loss_pct?: number;
};

export type NetworkProfileReadback = {
  download_bps?: number;
  upload_bps?: number;
  minimum_latency_ms?: number;
  maximum_latency_ms?: number;
};

export type NetworkProfileEvidence = {
  requested?: NetworkProfileRequested;
  supported_controls?: string[];
  unsupported_controls?: string[];
  traffic_path_verified?: boolean;
  control_plane?: {
    status?: string;
    readback?: NetworkProfileReadback;
    commands?: Record<string, unknown>;
    status_command_return_code?: number;
  };
  network_constraints_applied?: boolean;
  reset?: {
    status?: string;
    readback?: NetworkProfileReadback;
  };
};

export type ConditionRecord = {
  condition: string;
  requested: boolean;
  requested_target?: unknown;
  apply_status: string;
  verification_status: string;
  readback?: unknown;
  cleanup_status?: string;
  reason?: string;
  details?: Record<string, unknown>;
};

export type ConditionEvidence = {
  persona_id?: string;
  target_serial?: string;
  is_emulator?: boolean;
  overall_status?: string;
  constraints_applied?: boolean;
  traffic_path_verified?: boolean;
  applied_conditions_count?: number;
  partially_applied_conditions_count?: number;
  preexisting_conditions_count?: number;
  conditions?: ConditionRecord[];
  cleanup?: {
    status?: string;
    verified?: boolean;
    details?: unknown;
  };
  note?: string;
};

export type WorkerReport = {
  schema_version?: string;
  started_at?: string;
  finished_at?: string;
  apk_name?: string;
  apk_sha256?: string;
  device_serial?: string;
  package_name?: string;
  status?: string;
  error?: string;
  cleanup_warning?: string;
  fatal_exception_marker?: boolean;
  anr_marker?: boolean;
  oom_marker?: boolean;
  network_failure_marker?: boolean;
  storage_failure_marker?: boolean;
  log_signals?: LogSignal[];
  log_signals_may_be_truncated?: boolean;
  network_profile?: NetworkProfileEvidence | null;
  condition_evidence?: ConditionEvidence | null;
  constraints_applied?: boolean;
  constraint_verification?: string;
  steps?: SmokeStep[];
  limitations?: string[];
  result_interpretation?: string;
};

export type RunDetail = Run & {
  result?: WorkerReport | Record<string, unknown> | null;
};

export const demoLog = [
  "10-25 10:21:02.114 1812 1812 E AndroidRuntime: FATAL EXCEPTION: main",
  "10-25 10:21:02.114 1812 1812 E AndroidRuntime: java.lang.OutOfMemoryError: Failed to allocate 4194304 bytes",
  "10-25 10:21:03.301 1812 1812 W Network: java.net.SocketTimeoutException: timeout",
  "10-25 10:21:03.301 1812 1812 W Network: retry attempt 3 failed"
].join("\n");

export const fallbackPersonas: Persona[] = [
  {
    id: "budget-android",
    name: "Budget Android",
    device: "Android 10 · 2 GB RAM",
    ram_mb: 2048,
    storage_free_mb: 600,
    network: "unstable-4g",
    latency_ms: 180,
    down_kbps: 1200,
    up_kbps: 350,
    packet_loss_pct: 2,
    battery_saver: true,
    risk: "high",
    description: "Constrained memory and storage with variable mobile connectivity."
  },
  {
    id: "edge-village",
    name: "Edge / weak signal",
    device: "Android 11 · 3 GB RAM",
    ram_mb: 3072,
    storage_free_mb: 900,
    network: "high-latency",
    latency_ms: 450,
    down_kbps: 256,
    up_kbps: 96,
    packet_loss_pct: 8,
    battery_saver: true,
    risk: "critical",
    description: "Slow throughput, high latency and intermittent packet loss."
  },
  {
    id: "storage-pressure",
    name: "Low storage",
    device: "Android 10 · 2 GB RAM",
    ram_mb: 2048,
    storage_free_mb: 180,
    network: "moderate-4g",
    latency_ms: 90,
    down_kbps: 2500,
    up_kbps: 700,
    packet_loss_pct: 0,
    battery_saver: false,
    risk: "high",
    description: "Small free-storage budget to expose cache and download assumptions."
  },
  {
    id: "baseline",
    name: "Baseline",
    device: "Android 14 · 6 GB RAM",
    ram_mb: 6144,
    storage_free_mb: 8000,
    network: "good-4g",
    latency_ms: 35,
    down_kbps: 12000,
    up_kbps: 3000,
    packet_loss_pct: 0,
    battery_saver: false,
    risk: "low",
    description: "Control profile for comparison."
  }
];

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const token = sessionStorage.getItem("bharatsim.supabase.session");
    let accessToken = "";
    if (token) { try { accessToken = JSON.parse(token).access_token || ""; } catch { sessionStorage.removeItem("bharatsim.supabase.session"); } }
    const headers = new Headers(init?.headers || {});
    if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
    const r = await fetch(API + path, { ...init, headers });
    if (!r.ok) {
      const b = await r.json().catch(() => ({}));
      throw new Error(b.detail || `Request failed (${r.status})`);
    }
    return (await r.json()) as T;
  } catch (err) {
    if (
      err instanceof TypeError &&
      (err.message.toLowerCase().includes("fetch") ||
        err.message.toLowerCase().includes("network") ||
        err.message.toLowerCase().includes("failed"))
    ) {
      throw new Error("API is down or unreachable. Could not connect to backend server.");
    }
    throw err;
  }
}

export function isRunActive(status: string): boolean {
  return (
    status === "queued" ||
    status === "leased" ||
    status === "running" ||
    status === "awaiting_worker"
  );
}

export function cls(v: string): string {
  return v === "critical" ? "critical" : v === "high" ? "high" : v === "medium" ? "medium" : "low";
}

export function displayRunStatus(status: string): string {
  if (status === "completed") return "smoke completed";
  if (status === "awaiting_worker") return "awaiting worker";
  if (status === "queued") return "queued for worker";
  if (status === "leased") return "worker running";
  return status.replaceAll("_", " ");
}

export function date(v: string): string {
  return new Date(v).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}
