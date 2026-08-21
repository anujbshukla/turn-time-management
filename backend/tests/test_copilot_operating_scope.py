from datetime import date, datetime

from app.schemas import GlobalCopilotRequest
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlan


def test_dashboard_today_range_is_not_expanded_by_copilot():
    plan = WarehouseQueryPlan(
        intent="summary",
        understood=True,
    )
    payload = GlobalCopilotRequest(
        question="How many appointments do we have?",
        facility_id="FAC001",
        date_from=date(2026, 8, 17),
        # OperationsFilterBar sends the exclusive end.
        date_to=date(2026, 8, 18),
    )

    DataCopilotService._apply_request_context(plan, payload)

    assert plan.filters["facility_id"] == "FAC001"
    assert plan.filters["date_from"] == datetime(2026, 8, 17)
    assert plan.filters["date_to"] == datetime(2026, 8, 18)
    assert (
        plan.filters["date_to"] - plan.filters["date_from"]
    ).days == 1


def test_scope_fact_displays_exclusive_end_as_inclusive_calendar_day():
    plan = WarehouseQueryPlan(
        intent="summary",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "date_from": datetime(2026, 8, 17),
            "date_to": datetime(2026, 8, 18),
        },
    )

    fact = DataCopilotService._scope_fact(plan)

    assert fact == {
        "label": "Scope",
        "value": "FAC001 · Aug 17, 2026",
    }
