export const API = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export type Capabilities = {
  database_persistence?: boolean;
  analysis_persistence?: boolean;
  apk_upload: boolean; direct_apk_upload: boolean; log_analysis: boolean; risk_planner: boolean;
  failure_fingerprinting: boolean; bharat_score: boolean; android_execution: boolean;
  worker_dispatch: boolean; network_shaping: boolean; sarvam_translation: boolean;
  sarvam_audio_tts?: boolean; ml_classifier?: boolean; evaluator_scenarios?: boolean; run_comparison?: boolean;
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
  occurrence_count?: number;
  line_numbers?: number[];
  evidence_context?: Array<{ line: number; text: string; relation: string }>;
  impact_priority?: { score: number; label: string; persona_risk: string; warning: string };
  root_cause_hypothesis?: { statement: string; confidence: string; validation_steps: string[]; status: string };
  ml_classification?: {
    category: string;
    confidence: number;
    probabilities?: Record<string, number>;
  };
  sarvam_explanation?: {
    root_cause: string;
    impact: string;
    remediation: string;
    defensive_code?: string;
    hindi_explanation?: string;
  };
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
    occurrence_count?: number;
  };
  bharat_score: {
    value: number;
    label: string;
    method: string;
    warning: string;
  };
  limitations: string[];
  persistence?: { saved: boolean; reason?: string };
  persona: Persona;
  analysis_mode?: string;
  failure_dna?: { groups: Array<{ fingerprint: string; kind: string; severity: string; occurrence_count: number; line_numbers: number[]; first_line: number; last_line: number }>; group_count: number; total_occurrences: number; method: string };
  user_impact?: { priority_score: number; label: string; persona_risk: string; drivers: string[]; assumptions: string[] };
  root_cause_hypotheses?: Array<{ finding_id: string; kind: string; statement: string; confidence: string; validation_steps: string[]; status: string }>;
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
  busy?: boolean;
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

export type EvidenceFusionObservation = {
  category: string;
  status: string;
  count: number;
  evidence: Array<{
    line_number: number | null;
    marker: string;
    evidence: Array<{ line_number: number | null; text: string }>;
  }>;
  interpretation: string;
};

export type EvidenceFusionHypothesis = {
  id: string;
  category: string;
  confidence: "low" | "medium" | string;
  status: string;
  statement: string;
  supporting_sources: string[];
  validation_steps: string[];
};

export type EvidenceFusionSource = {
  id: string;
  status: string;
  detail: string;
};

export type EvidenceFusion = {
  schema_version: string;
  status: "INCOMPLETE" | "OBSERVED_ONLY" | "CORRELATED" | "NO_MARKER_OBSERVED" | string;
  review_required: boolean;
  summary: string;
  execution: {
    status: string;
    logcat_collected: boolean;
    apk_sha256_valid: boolean;
    successful_steps: string[];
  };
  observations: EvidenceFusionObservation[];
  hypotheses: EvidenceFusionHypothesis[];
  sources: EvidenceFusionSource[];
  verified_conditions: string[];
  preexisting_conditions?: string[];
  unsupported_conditions: string[];
  limitations: string[];
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
  diagnostics?: EvidenceFusion;
};

export type RunDetail = Run & {
  result?: WorkerReport | Record<string, unknown> | null;
};

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
    id: "crowded-station",
    name: "Crowded Station",
    device: "Android 10 · 2 GB RAM",
    ram_mb: 2048,
    storage_free_mb: 500,
    network: "congested-3g",
    latency_ms: 250,
    down_kbps: 384,
    up_kbps: 128,
    packet_loss_pct: 3,
    battery_saver: true,
    risk: "high",
    description: "Congested public network with packet drops and bandwidth contention."
  },
  {
    id: "congested-urban-4g",
    name: "Congested Urban 4G",
    device: "Android 11 · 3 GB RAM",
    ram_mb: 3072,
    storage_free_mb: 1200,
    network: "throttled-4g",
    latency_ms: 120,
    down_kbps: 1500,
    up_kbps: 400,
    packet_loss_pct: 1,
    battery_saver: false,
    risk: "medium",
    description: "Peak-hour cell tower congestion with buffer bloat and jitter."
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

export async function downloadApi(path: string): Promise<Blob> {
  const token = sessionStorage.getItem("bharatsim.supabase.session");
  let accessToken = "";
  if (token) {
    try { accessToken = JSON.parse(token).access_token || ""; }
    catch { sessionStorage.removeItem("bharatsim.supabase.session"); }
  }
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
  let response: Response;
  try {
    response = await fetch(API + path, { headers });
  } catch {
    throw new Error("API is down or unreachable. Could not connect to backend server.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.blob();
}

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

export function isRunExecuting(status: string): boolean {
  return status === "leased" || status === "running";
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


export type PlanScenario = {
  id: string;
  persona_id: string;
  persona_name: string;
  flow: string;
  app_category: string;
  category_flow_sensitive: boolean;
  risk_score: number;
  reason: string;
  requested_conditions: Array<{ id: string; label: string; target: string }>;
  interaction_hypotheses: Array<{ conditions: string[]; labels: string[]; risk_bonus: number; hypothesis: string; validation: string }>;
  interaction_count: number;
  interaction_risk_bonus: number;
};

export type PlanResponse = {
  generated_at: string;
  strategy: string;
  app_category: string;
  critical_flows: string[];
  scenarios: PlanScenario[];
  total_candidates: number;
  interaction_hunter: {
    candidate_pairwise_interactions: number;
    selected_scenario_interactions: number;
    method: string;
    warning: string;
  };
};


export type RunEvent = {
  id: number;
  event_type: string;
  created_at: string;
  actor_type: "user" | "worker" | "system" | "admin";
  actor_id?: string | null;
  payload: Record<string, unknown>;
};

export type EvaluatorScenario = {
  id: string;
  name: string;
  persona_id: string;
  persona_name: string;
  description: string;
  app_name: string;
  package_name: string;
  logcat: string;
  expected_failure: string;
  expected_ml_category: string;
  summary: {
    finding_count: number;
    critical: number;
    high: number;
    medium: number;
  };
  metrics: {
    cold_start_ms: number;
    jank_frame_pct: number;
    memory_peak_mb: number;
    network_latency_ms: number;
  };
  sarvam_insight: {
    hi: string;
    en: string;
  };
};

export type SarvamAudioResponse = {
  audio_base64: string;
  format: string;
  language_code: string;
  speaker: string;
  is_fixture: boolean;
  note?: string;
};

export type AnomalyDetail = {
  metric: string;
  baseline: number | string;
  constrained: number | string;
  delta_pct: number;
  status: "severe_anomaly" | "elevated" | "normal";
  explanation?: string;
};

export type ComparisonResult = {
  baseline_run_id: string;
  constrained_run_id: string;
  baseline_metrics: Record<string, number>;
  constrained_metrics: Record<string, number>;
  deltas: Record<string, { delta: number; delta_pct: number }>;
  anomaly_detected: boolean;
  anomaly_score: number;
  anomalies: AnomalyDetail[];
  verdict: string;
  details: string;
};

export async function fetchEvaluatorScenarios(): Promise<EvaluatorScenario[]> {
  const res = await api<{ items: EvaluatorScenario[] }>("/api/v1/evaluator/scenarios");
  return res.items;
}

export async function fetchEvaluatorScenario(id: string): Promise<EvaluatorScenario> {
  return await api<EvaluatorScenario>("/api/v1/evaluator/scenarios/" + encodeURIComponent(id));
}

export async function synthesizeSpeechAudio(text: string, languageCode: string = "hi-IN"): Promise<SarvamAudioResponse> {
  return await api<SarvamAudioResponse>("/api/v1/translate/audio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_language_code: languageCode })
  });
}

export async function compareRuns(baselineRunId: string, constrainedRunId: string): Promise<ComparisonResult> {
  return await api<ComparisonResult>("/api/v1/runs/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      constrained_run_id: constrainedRunId
    })
  });
}
