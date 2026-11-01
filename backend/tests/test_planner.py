from app.main import PlanRequest, create_plan


def test_planner_surfaces_pairwise_interaction_hypotheses():
    result = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        critical_flows=["payment retry"],
        max_scenarios=5,
    ))

    assert result["strategy"] == "deterministic-risk-and-pairwise-interaction-v2"
    assert result["total_candidates"] == 1
    assert result["interaction_hunter"]["candidate_pairwise_interactions"] >= 3
    scenario = result["scenarios"][0]
    assert scenario["risk_score"] <= 100
    assert scenario["interaction_count"] >= 3
    pairs = [set(item["conditions"]) for item in scenario["interaction_hypotheses"]]
    assert {"high_latency", "limited_bandwidth"} in pairs
    assert all(item["validation"].startswith("Run the paired condition") for item in scenario["interaction_hypotheses"])
    assert "not predicted failure probability" in scenario["reason"]


def test_planner_marks_memory_as_profile_target_not_verified_cap():
    result = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        critical_flows=["cold start"],
        max_scenarios=1,
    ))
    conditions = result["scenarios"][0]["requested_conditions"]
    memory = next(item for item in conditions if item["id"] == "low_memory_profile")
    assert "not a verified RAM cap" in memory["target"]


def test_planner_rejects_unknown_persona():
    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as error:
        create_plan(PlanRequest(persona_ids=["unknown"]))
    assert error.value.status_code == 422
