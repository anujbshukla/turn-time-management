from datetime import date

from app.schemas import GlobalCopilotRequest
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlanner


class Message:
    role = "user"

    def __init__(self, content: str) -> None:
        self.content = content


def test_follow_up_retains_historical_loader_effectiveness():
    plan = WarehouseQueryPlanner().plan(
        "What about only inbound appointments?",
        conversation_history=[
            Message("Are additional loaders actually improving turn time historically?")
        ],
    )

    assert plan.intent == "resource_effectiveness"
    assert plan.resource_type == "loaders"
    assert plan.filters["appointment_type"] == "Inbound"
    assert plan.ignore_request_date_context is True
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters


def test_historical_follow_up_does_not_reinherit_dashboard_today():
    plan = WarehouseQueryPlanner().plan(
        "What about only inbound appointments?",
        conversation_history=[
            Message("Are additional loaders actually improving turn time historically?")
        ],
    )
    payload = GlobalCopilotRequest(
        question="What about only inbound appointments?",
        facility_id="FAC001",
        date_from=date(2026, 8, 17),
        date_to=date(2026, 8, 18),
    )

    DataCopilotService._apply_request_context(plan, payload)

    assert plan.filters["facility_id"] == "FAC001"
    assert plan.filters["appointment_type"] == "Inbound"
    assert "date_from" not in plan.filters
    assert "date_to" not in plan.filters


def test_explicit_follow_up_time_replaces_inherited_historical_scope():
    plan = WarehouseQueryPlanner().plan(
        "What about the last 30 days?",
        conversation_history=[
            Message("Are additional loaders actually improving turn time historically?")
        ],
    )

    assert plan.intent == "resource_effectiveness"
    assert plan.resource_type == "loaders"
    assert plan.ignore_request_date_context is False
    assert (plan.filters["date_to"] - plan.filters["date_from"]).days == 30


def test_forklift_resource_type_survives_follow_up():
    plan = WarehouseQueryPlanner().plan(
        "What about only outbound appointments?",
        conversation_history=[
            Message("Are additional forklifts improving turn time historically?")
        ],
    )

    assert plan.intent == "resource_effectiveness"
    assert plan.resource_type == "forklifts"
    assert plan.filters["appointment_type"] == "Outbound"
    assert plan.ignore_request_date_context is True
