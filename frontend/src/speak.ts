import { api } from "./api";

export type ConditionSupport = { condition: string; support: string; note: string };

export type TestSpec = {
  spec_id: string;
  spec_hash: string;
  request_text: string;
  language_detected: string;
  objective: string;
  app_hint: string;
  journey: string;
  journey_description: string;
  persona_id: string;
  conditions: string[];
  supported_conditions: ConditionSupport[];
  unsupported_conditions: ConditionSupport[];
  expected_behaviour: string[];
  assertions: string[];
  machine_checked_assertions: { id: string; label: string }[];
  not_machine_verified: string[];
  evidence: string[];
  matched_scenario: string | null;
  safety: { flags: string[]; classification: string };
  clarifications_needed: string[];
  execution: {
    eligible: boolean; mode: "scenario" | "generic" | "blocked" | "needs_clarification"; scenario_id: string | null;
    persona_id: string; custom_persona?: Record<string, unknown> | null; reason: string;
  };
  symptom?: string;
  symptom_label?: string;
  symptom_checkable?: boolean;
  interpreter: { provider: string; model: string | null; request_id: string | null; latency_ms: number | null; fallback: boolean; fallback_reason?: string; redacted_input?: boolean };
};

export type ScenarioPack = {
  id: string;
  status: "executable" | "planned";
  pack: string;
  title: string;
  user_problem: string;
  reason?: string;
  setup?: string;
  steps?: string[];
  expected?: string[];
  assertions?: { id: string; label: string }[];
  limitations?: string[];
  sample_builds?: { variant: string; label: string; path: string }[];
};

export type Transcript = { transcript: string; language_code: string | null; request_id: string | null; model: string; latency_ms: number };

export type FixProofVerdict = {
  verdict: string;
  label: string;
  summary: string;
  preconditions: { check: string; passed: boolean; detail: string }[];
  assertions: { id: string; label: string; original: boolean | null; candidate: boolean | null; original_observed?: string; candidate_observed?: string }[];
  original: { run_id: string; apk_sha256: string };
  candidate: { run_id: string; apk_sha256: string };
};

export type RunExplanation = {
  audience: string;
  language_code: string;
  english: { headline: string; points: string[]; recommendation: string };
  translated_text: string | null;
  translation_failed: boolean;
  cited_evidence: { id: string; fact: string }[];
  interpreter: { provider: string; model: string; request_id: string | null; latency_ms: number };
};

export function interpretRequest(text: string): Promise<TestSpec> {
  return api<TestSpec>("/api/v1/speak/interpret", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });
}

export function transcribeVoice(blob: Blob): Promise<Transcript> {
  const body = new FormData();
  const type = blob.type || "audio/webm";
  const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : type.includes("wav") ? "wav" : "webm";
  body.append("audio", new File([blob], "voice." + ext, { type }));
  return api<Transcript>("/api/v1/speak/transcribe", { method: "POST", body });
}

export async function listScenarioPacks(): Promise<ScenarioPack[]> {
  return (await api<{ items: ScenarioPack[] }>("/api/v1/scenarios")).items;
}

export function runFixProof(originalRunId: string, candidateRunId: string): Promise<FixProofVerdict> {
  return api<FixProofVerdict>("/api/v1/fixproof", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ original_run_id: originalRunId, candidate_run_id: candidateRunId })
  });
}

export function explainRun(runId: string, audience: string, languageCode: string): Promise<RunExplanation> {
  return api<RunExplanation>("/api/v1/runs/" + encodeURIComponent(runId) + "/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audience, language_code: languageCode })
  });
}

/** Fetch a bundled sample build so it goes through the normal private upload flow. */
export async function fetchSampleBuild(path: string, filename: string): Promise<File> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load the sample build (" + response.status + ").");
  const blob = await response.blob();
  return new File([blob], filename, { type: "application/vnd.android.package-archive" });
}

/** What gets stored with a run: an allowlisted scenario id plus the validated spec (no interpreter data). */
export function runScenarioPayload(spec: TestSpec | null, scenarioId: string | null) {
  if (!spec && !scenarioId) return null;
  return {
    scenario_id: scenarioId,
    spec: spec
      ? {
          spec_id: spec.spec_id,
          spec_hash: spec.spec_hash,
          objective: spec.objective,
          language_detected: spec.language_detected,
          journey: spec.journey,
          persona_id: spec.persona_id,
          conditions: spec.conditions,
          assertions: spec.assertions,
          matched_scenario: spec.matched_scenario,
          request_text: spec.request_text,
          symptom: spec.symptom || "other"
        }
      : null
  };
}

export type Diagnosis = {
  problem: string;
  reproduction: { symptom: string; symptom_label: string; verdict: "REPRODUCED" | "NOT_REPRODUCED" | "CANNOT_CHECK" | "BLOCKED"; summary: string; symptom_source?: string; evidence: { id: string; fact: string }[] };
  diagnosis: { why: string; fix_steps: string[]; code_hint: string; confidence: "low" | "medium" | "high" } | null;
  cited_evidence?: { id: string; fact: string }[];
  language_code?: string;
  translated_text: string | null;
  translation_failed?: boolean;
  interpreter?: { provider: string; model: string; request_id: string | null; latency_ms: number };
};

export function diagnoseRun(runId: string, languageCode: string, problem?: string): Promise<Diagnosis> {
  return api<Diagnosis>("/api/v1/runs/" + encodeURIComponent(runId) + "/diagnose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(problem ? { problem, language_code: languageCode } : { language_code: languageCode })
  });
}
