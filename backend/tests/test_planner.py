from app.main import PlanRequest, create_plan


def test_planner_surfaces_pairwise_interaction_hypotheses():
    result = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        critical_flows=["payment retry"],
        max_scenarios=5,
    ))

    assert result["strategy"] == "deterministic-category-aware-risk-and-pairwise-interaction-v3"
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



def test_planner_uses_app_category_to_prioritize_relevant_flows():
    general = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        app_category="general",
        critical_flows=["UPI transfer"],
        max_scenarios=1,
    ))
    fintech = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        app_category="fintech",
        critical_flows=["UPI transfer"],
        max_scenarios=1,
    ))

    assert general["scenarios"][0]["category_flow_sensitive"] is False
    assert fintech["scenarios"][0]["category_flow_sensitive"] is True
    assert fintech["scenarios"][0]["risk_score"] == general["scenarios"][0]["risk_score"] + 15
    assert fintech["app_category"] == "fintech"


def test_planner_normalizes_and_deduplicates_user_critical_flows():
    result = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        app_category="ecommerce",
        critical_flows=["  Checkout   flow ", "checkout flow", "", "Cart"],
        max_scenarios=10,
    ))

    assert result["critical_flows"] == ["Checkout flow", "Cart"]
    assert {item["flow"] for item in result["scenarios"]} == {"Checkout flow", "Cart"}


def test_planner_rejects_unknown_app_category_and_too_many_flows():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlanRequest(app_category="healthcare")

    with pytest.raises(ValidationError):
        PlanRequest(critical_flows=[f"flow {index}" for index in range(11)])


def test_planner_defaults_empty_flow_list_to_safe_generic_flows():
    result = create_plan(PlanRequest(
        persona_ids=["budget-android"],
        app_category="general",
        critical_flows=[],
        max_scenarios=10,
    ))

    assert result["critical_flows"] == ["cold start", "login", "primary action", "network retry"]
