from datetime import date, datetime

from app.schemas import GlobalCopilotRequest
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlan, WarehouseQueryPlanner


def test_planner_understands_common_historical_windows():
    planner = WarehouseQueryPlanner()

    yesterday = planner.plan(
        "How many appointments were late yesterday?",
        conversation_history=[],
    )
    assert yesterday.understood
    assert "date_from" in yesterday.filters
    assert "date_to" in yesterday.filters
    assert (
        yesterday.filters["date_to"]
        - yesterday.filters["date_from"]
    ).days == 1

    last_30 = planner.plan(
        "Rank carriers by average delay for the last 30 days",
        conversation_history=[],
    )
    assert last_30.understood
    assert last_30.group_by == "carrier"
    assert (
        last_30.filters["date_to"]
        - last_30.filters["date_from"]
    ).days == 30


def test_active_dashboard_filters_ground_copilot_queries():
    plan = WarehouseQueryPlan(
        intent="summary",
        understood=True,
    )
    payload = GlobalCopilotRequest(
        question="How many appointments are there?",
        facility_id="FAC001",
        customer_id="CUS001",
        carrier_id="CAR001",
        appointment_type="Inbound",
        status="Scheduled",
        date_from=date(2026, 8, 17),
        date_to=date(2026, 8, 18),
    )

    DataCopilotService._apply_request_context(plan, payload)

    assert plan.filters["facility_id"] == "FAC001"
    assert plan.filters["customer_id"] == "CUS001"
    assert plan.filters["carrier_id"] == "CAR001"
    assert plan.filters["appointment_type"] == "Inbound"
    assert plan.filters["status"] == "Scheduled"
    assert plan.filters["date_from"] == datetime(2026, 8, 17)
    # The Operations UI already supplies an exclusive upper bound.
    assert plan.filters["date_to"] == datetime(2026, 8, 18)


def test_question_time_filter_overrides_dashboard_time_context():
    planner = WarehouseQueryPlanner()
    plan = planner.plan(
        "How many appointments are late tomorrow?",
        conversation_history=[],
    )
    original_from = plan.filters["date_from"]
    original_to = plan.filters["date_to"]

    payload = GlobalCopilotRequest(
        question="How many appointments are late tomorrow?",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 17),
    )
    DataCopilotService._apply_request_context(plan, payload)

    assert plan.filters["date_from"] == original_from
    assert plan.filters["date_to"] == original_to
