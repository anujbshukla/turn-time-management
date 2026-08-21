from app.services.query_planner import WarehouseQueryPlanner


def test_planner_routes_recovery_action_effectiveness():
    plan = WarehouseQueryPlanner().plan(
        "Which recovery actions actually worked best historically?",
        conversation_history=[],
    )
    assert plan.understood
    assert plan.intent == "action_effectiveness"


def test_planner_routes_loader_effectiveness():
    plan = WarehouseQueryPlanner().plan(
        "Are additional loaders improving turn time historically?",
        conversation_history=[],
    )
    assert plan.understood
    assert plan.intent == "resource_effectiveness"
    assert plan.resource_type == "loaders"


def test_planner_routes_risk_driver_diagnostics():
    plan = WarehouseQueryPlanner().plan(
        "What are the biggest reasons appointments are predicted late today?",
        conversation_history=[],
    )
    assert plan.understood
    assert plan.intent == "risk_drivers"
    assert "date_from" in plan.filters
    assert "date_to" in plan.filters


def test_planner_supports_pallet_threshold_and_sla_percentage():
    plan = WarehouseQueryPlanner().plan(
        "What percentage of appointments with more than 30 pallets missed SLA?",
        conversation_history=[],
    )
    assert plan.understood
    assert plan.metric == "sla_miss_rate_percent"
    assert plan.filters["pallet_min"] == 31


def test_explicit_follow_up_time_overrides_prior_time():
    class Message:
        role = "user"
        content = "Rank carriers by average delay today"

    plan = WarehouseQueryPlanner().plan(
        "What about the last 30 days?",
        conversation_history=[Message()],
    )
    assert (
        plan.filters["date_to"]
        - plan.filters["date_from"]
    ).days == 30
    assert plan.group_by == "carrier"
    assert plan.metric == "average_delay_minutes"


def test_next_24_hours_is_understood():
    plan = WarehouseQueryPlanner().plan(
        "How much detention exposure do we have over the next 24 hours?",
        conversation_history=[],
    )
    assert plan.understood
    assert plan.metric == "detention_exposure"
    assert (
        plan.filters["date_to"]
        - plan.filters["date_from"]
    ).total_seconds() == 24 * 60 * 60


def test_product_minutes_per_pallet_uses_product_history_tool():
    plan = WarehouseQueryPlanner().plan(
        "Which products have the highest historical minutes per pallet?",
        conversation_history=[],
    )
    assert plan.intent == "product_handling"
    assert plan.group_by == "product"


def test_mission_questions_use_mission_summary():
    plan = WarehouseQueryPlanner().plan(
        "How many active recovery missions do we have?",
        conversation_history=[],
    )
    assert plan.intent == "mission_summary"
