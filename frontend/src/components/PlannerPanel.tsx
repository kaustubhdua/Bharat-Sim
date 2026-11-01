import { useEffect, useState } from "react";
import { Activity, FlaskConical, RefreshCw } from "lucide-react";
import { api, cls, type PlanResponse } from "../api";

const FLOW_PRESETS = {
  general: ["cold start", "login", "primary action", "network retry"],
  ecommerce: ["product search", "cart update", "checkout", "payment confirmation", "order tracking"],
  fintech: ["login and authentication", "UPI transfer", "balance refresh", "payment retry", "statement sync"],
  social: ["feed load", "image upload", "message send", "notification open", "media playback"],
  education: ["course listing", "lesson playback", "quiz submission", "offline download", "progress sync"],
  delivery: ["location lookup", "address selection", "order placement", "live tracking", "payment confirmation"],
  media: ["home feed", "video playback", "stream buffering", "offline download", "playback recovery"],
} as const;

type AppCategory = keyof typeof FLOW_PRESETS;

const CATEGORY_LABELS: Record<AppCategory, string> = {
  general: "General",
  ecommerce: "E-commerce",
  fintech: "Fintech / Banking",
  social: "Social",
  education: "Education",
  delivery: "Delivery / Mobility",
  media: "Media / Streaming",
};

export default function PlannerPanel({ selected }: { selected: string }) {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [draftCategory, setDraftCategory] = useState<AppCategory>("general");
  const [draftFlowsText, setDraftFlowsText] = useState(FLOW_PRESETS.general.join("\n"));
  const [activeConfig, setActiveConfig] = useState<{ appCategory: AppCategory; criticalFlows: string[] }>({
    appCategory: "general",
    criticalFlows: [...FLOW_PRESETS.general],
  });

  const draftFlows = draftFlowsText
    .split(/[\n,]/)
    .map((flow) => flow.trim())
    .filter(Boolean)
    .slice(0, 10);

  function generatePlan() {
    setActiveConfig({
      appCategory: draftCategory,
      criticalFlows: draftFlows,
    });
    setRefresh((value) => value + 1);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<PlanResponse>("/api/v1/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        persona_ids: [selected],
        app_category: activeConfig.appCategory,
        critical_flows: activeConfig.criticalFlows,
        max_scenarios: 4,
      }),
    }).then((value) => { if (active) setPlan(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "Could not generate a test plan."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected, refresh, activeConfig]);

  function updateCategory(value: string) {
    const category = value as AppCategory;
    setDraftCategory(category);
    setDraftFlowsText(FLOW_PRESETS[category].join("\n"));
  }

  return (
    <section className="panel planner-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">02B / INTERACTION HUNTER</div>
          <h2>Risk-first test plan</h2>
          <p>Choose the app's critical journeys; the planner ranks them against persona constraints and paired conditions.</p>
        </div>
      </div>

      <div className="planner-config">
        <div className="planner-config-fields">
          <label className="planner-field">
            <span>Application category</span>
            <select value={draftCategory} onChange={(event) => updateCategory(event.target.value)}>
              {(Object.keys(CATEGORY_LABELS) as AppCategory[]).map((category) => (
                <option key={category} value={category}>{CATEGORY_LABELS[category]}</option>
              ))}
            </select>
          </label>
          <label className="planner-field">
            <span>Critical user journeys <small>One per line or comma-separated · up to 10</small></span>
            <textarea
              rows={4}
              maxLength={1200}
              value={draftFlowsText}
              onChange={(event) => setDraftFlowsText(event.target.value)}
              placeholder="Login and authentication&#10;Payment retry&#10;Offline recovery"
            />
          </label>
        </div>
        <div className="planner-config-footer">
          <span>{draftFlows.length} / 10 journeys · category-specific risk keywords</span>
          <button type="button" className="planner-generate" onClick={generatePlan} disabled={loading}>
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            Generate plan
          </button>
        </div>
      </div>

      {loading && !plan ? <div className="planner-empty">Generating ranked scenarios…</div> : null}
      {error ? <div className="planner-empty">{error}</div> : null}
      {plan ? <>
        <div className="planner-active-config">
          <span>{CATEGORY_LABELS[plan.app_category as AppCategory] || plan.app_category}</span>
          <span>{plan.critical_flows.length} critical journeys ranked</span>
          <span>Deterministic heuristic · not failure probability</span>
        </div>
        <div className="planner-stats">
          <div><b>{plan.total_candidates}</b><span>candidate scenarios</span></div>
          <div><b>{plan.interaction_hunter.candidate_pairwise_interactions}</b><span>pairwise interactions examined</span></div>
          <div><b>{plan.interaction_hunter.selected_scenario_interactions}</b><span>interactions in selected plan</span></div>
        </div>
        <div className="scenario-list">
          {plan.scenarios.map((scenario, index) => (
            <article className="scenario-card" key={scenario.id}>
              <div className="scenario-topline">
                <span className="scenario-index">0{index + 1}</span>
                <div className="scenario-title">
                  <b>{scenario.flow}</b>
                  <small>{scenario.persona_name} · {CATEGORY_LABELS[scenario.app_category as AppCategory] || scenario.app_category}</small>
                </div>
                <span className={"risk-badge " + cls(scenario.risk_score >= 85 ? "critical" : scenario.risk_score >= 65 ? "high" : scenario.risk_score >= 45 ? "medium" : "low")}>{scenario.risk_score} / 100</span>
              </div>
              <div className="scenario-tags">
                {scenario.requested_conditions.map((condition) => <span key={condition.id}>{condition.label}: {condition.target}</span>)}
                {scenario.category_flow_sensitive ? <span className="scenario-category-match">Category-sensitive flow</span> : null}
              </div>
              {scenario.interaction_hypotheses.slice(0, 3).map((interaction) => (
                <div className="interaction-item" key={interaction.conditions.join("+")}>
                  <span><Activity size={13} /> {interaction.labels.join(" × ")}</span>
                  <p>{interaction.hypothesis}</p>
                  <small>{interaction.validation}</small>
                </div>
              ))}
            </article>
          ))}
        </div>
        <div className="planner-caveat"><FlaskConical size={14} /> {plan.interaction_hunter.warning} This ranks tests; it does not execute them or claim a failure.</div>
      </> : null}
      {!loading && !error && !plan ? <div className="planner-empty">No scenarios returned for this persona.</div> : null}
    </section>
  );
}
