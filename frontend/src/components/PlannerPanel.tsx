import { useEffect, useState } from "react";
import { Activity, FlaskConical, RefreshCw } from "lucide-react";
import { api, cls, type PlanResponse } from "../api";

export default function PlannerPanel({ selected }: { selected: string }) {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<PlanResponse>("/api/v1/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        persona_ids: [selected],
        app_category: "general",
        critical_flows: ["cold start", "login", "payment retry", "primary action"],
        max_scenarios: 4
      })
    }).then((value) => { if (active) setPlan(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "Could not generate a test plan."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected, refresh]);

  return (
    <section className="panel planner-panel">
      <div className="panel-heading">
        <div>
          <div className="section-kicker">02B / INTERACTION HUNTER</div>
          <h2>Risk-first test plan</h2>
          <p>Prioritizes critical flows and paired constraints for the selected persona.</p>
        </div>
        <button className="icon-button" onClick={() => setRefresh((v) => v + 1)} disabled={loading} aria-label="Refresh test plan">
          <RefreshCw size={15} className={loading ? "spin" : ""} />
        </button>
      </div>
      {loading && !plan ? <div className="planner-empty">Generating ranked scenarios…</div> : null}
      {error ? <div className="planner-empty">{error}</div> : null}
      {plan ? <>
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
                <div className="scenario-title"><b>{scenario.flow}</b><small>{scenario.persona_name}</small></div>
                <span className={"risk-badge " + cls(scenario.risk_score >= 85 ? "critical" : scenario.risk_score >= 65 ? "high" : scenario.risk_score >= 45 ? "medium" : "low")}>{scenario.risk_score} / 100</span>
              </div>
              <div className="scenario-tags">
                {scenario.requested_conditions.map((condition) => <span key={condition.id}>{condition.label}: {condition.target}</span>)}
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
