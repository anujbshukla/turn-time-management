from datetime import date

from app.schemas import GlobalCopilotRequest
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlanner


class Message:
    role = "user"

    def __init__(self, content: str) -> None:
        self.content = content


def test_historically_clears_prior_conversation_dates():
    plan = WarehouseQueryPlanner().plan(
        "Are additional loaders actually improving turn time historically?",
        conversation_history=[Message("Show me today's appointments")],
    )
    assert plan.intent == "resource_effectiveness"
    assert plan.resource_type == "loaders"
    assert plan.ignore_request_date_context is True
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters


def test_historically_does_not_inherit_dashboard_today_dates():
    plan = WarehouseQueryPlanner().plan(
        "Are additional loaders actually improving turn time historically?",
        conversation_history=[],
    )
    payload = GlobalCopilotRequest(
        question="Are additional loaders actually improving turn time historically?",
        facility_id="FAC001",
        date_from=date(2026, 8, 17),
        date_to=date(2026, 8, 18),
    )
    DataCopilotService._apply_request_context(plan, payload)
    assert plan.filters["facility_id"] == "FAC001"
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters


def test_explicit_last_30_days_wins_over_historical_wording():
    plan = WarehouseQueryPlanner().plan(
        "Historically, are additional loaders improving turn time over the last 30 days?",
        conversation_history=[],
    )
    assert plan.intent == "resource_effectiveness"
    assert plan.ignore_request_date_context is False
    assert (plan.filters["date_to"] - plan.filters["date_from"]).days == 30


def test_over_time_is_unbounded_history_without_explicit_period():
    plan = WarehouseQueryPlanner().plan(
        "Are additional loaders improving turn time over time?",
        conversation_history=[],
    )
    assert plan.intent == "resource_effectiveness"
    assert plan.ignore_request_date_context is True
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters
