from types import SimpleNamespace

import pytest

from app.services.query_planner import WarehouseQueryPlanner


@pytest.mark.parametrize(
    "question",
    [
        "Which recovery actions have actually worked best historically?",
        "Which recovery actions have worked best?",
        "What actions have been most effective?",
        "Which AI recommendations actually worked?",
        "What recovery strategies have the best outcomes?",
        "Which actions improve SLA recovery the most?",
    ],
)
def test_action_effectiveness_natural_phrasings_route_correctly(question):
    plan = WarehouseQueryPlanner().plan(question, conversation_history=[])
    assert plan.intent == "action_effectiveness"
    assert plan.metric == "avg_realized_minutes_saved"
    assert plan.understood is True


def test_historical_action_effectiveness_ignores_dashboard_date_context():
    plan = WarehouseQueryPlanner().plan(
        "Which recovery actions have actually worked best historically?",
        conversation_history=[],
    )
    assert plan.intent == "action_effectiveness"
    assert plan.ignore_request_date_context is True
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters


def test_action_effectiveness_intent_survives_follow_up_refinement():
    history = [
        SimpleNamespace(
            role="user",
            content="Which recovery actions have actually worked best historically?",
        ),
        SimpleNamespace(role="assistant", content="Action effectiveness response"),
    ]
    plan = WarehouseQueryPlanner().plan(
        "What about only inbound appointments?",
        conversation_history=history,
    )
    assert plan.intent == "action_effectiveness"
    assert plan.ignore_request_date_context is True
    assert plan.filters["appointment_type"] == "Inbound"
