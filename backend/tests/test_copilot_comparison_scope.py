from datetime import date

from app.schemas import GlobalCopilotRequest
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import (
    WarehouseQueryPlan,
    WarehouseQueryPlanner,
)


class Message:
    role = "user"

    def __init__(self, content: str) -> None:
        self.content = content


def test_facility_ranking_clears_inherited_facility_filter():
    planner = WarehouseQueryPlanner()
    plan = planner.plan(
        "Rank facilities by average turn time for the last 30 days",
        conversation_history=[],
    )

    payload = GlobalCopilotRequest(
        question="Rank facilities by average turn time for the last 30 days",
        facility_id="FAC001",
        date_from=date(2026, 8, 17),
        date_to=date(2026, 8, 18),
    )
    DataCopilotService._apply_request_context(plan, payload)

    # Context application happens after planning, so apply the same
    # comparison rule after UI context is merged.
    WarehouseQueryPlanner._clear_group_dimension_filter(plan)

    assert plan.group_by == "facility"
    assert "facility_id" not in plan.filters
    assert "date_from" in plan.filters
    assert "date_to" in plan.filters


def test_carrier_ranking_clears_only_carrier_filter():
    plan = WarehouseQueryPlan(
        intent="ranking",
        group_by="carrier",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "carrier_id": "CAR001",
            "appointment_type": "Inbound",
        },
    )

    WarehouseQueryPlanner._clear_group_dimension_filter(plan)

    assert plan.filters["facility_id"] == "FAC001"
    assert plan.filters["appointment_type"] == "Inbound"
    assert "carrier_id" not in plan.filters


def test_customer_ranking_clears_only_customer_filter():
    plan = WarehouseQueryPlan(
        intent="ranking",
        group_by="customer",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "customer_id": "CUS001",
        },
    )

    WarehouseQueryPlanner._clear_group_dimension_filter(plan)

    assert plan.filters["facility_id"] == "FAC001"
    assert "customer_id" not in plan.filters


def test_appointment_type_comparison_clears_type_filter():
    plan = WarehouseQueryPlan(
        intent="ranking",
        group_by="appointment_type",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "appointment_type": "Inbound",
        },
    )

    WarehouseQueryPlanner._clear_group_dimension_filter(plan)

    assert plan.filters["facility_id"] == "FAC001"
    assert "appointment_type" not in plan.filters


def test_dock_comparison_clears_dock_filter_only():
    plan = WarehouseQueryPlan(
        intent="ranking",
        group_by="dock",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "assigned_dock_id": "DOCK001",
        },
    )

    WarehouseQueryPlanner._clear_group_dimension_filter(plan)

    assert plan.filters["facility_id"] == "FAC001"
    assert "assigned_dock_id" not in plan.filters


def test_ranking_fact_shows_sla_miss_denominator():
    text = DataCopilotService._ranking_fact_value(
        "sla_miss_rate_percent",
        {
            "sla_miss_rate_percent": 5.6,
            "sla_risk_or_misses": 2,
            "appointment_count": 36,
        },
    )

    assert text == "5.6% · 2 misses / 36 appointments"


def test_ranking_fact_shows_sample_size_for_average_metric():
    text = DataCopilotService._ranking_fact_value(
        "average_turn_time_minutes",
        {
            "average_turn_time_minutes": 72.5,
            "appointment_count": 421,
        },
    )

    assert text == "72.5 min · 421 appointments"



class _RankingRepository:
    def __init__(self, rows):
        self.rows = rows

    def advanced_grouped_metrics(self, **kwargs):
        return list(self.rows)


class _UnusedAppointmentRepository:
    pass


def _ranking_service(rows):
    return DataCopilotService(
        analytics_repository=_RankingRepository(rows),
        appointment_repository=_UnusedAppointmentRepository(),
    )


def test_ranking_uses_reliable_leader_and_surfaces_limited_sample():
    service = _ranking_service([
        {
            "group_id": "DOCK01",
            "group_label": "Dock 01",
            "average_risk_score": 68.0,
            "appointment_count": 1,
        },
        {
            "group_id": "DOCK07",
            "group_label": "Dock 07",
            "average_risk_score": 32.7,
            "appointment_count": 8,
        },
        {
            "group_id": "DOCK11",
            "group_label": "Dock 11",
            "average_risk_score": 31.5,
            "appointment_count": 9,
        },
    ])
    plan = WarehouseQueryPlan(
        intent="ranking",
        metric="average_risk_score",
        group_by="dock",
        limit=5,
        understood=True,
    )

    response = service._ranking_response(plan)

    assert response["answer"].startswith("Dock 07 ranks first")
    assert "at least 5 appointments" in response["answer"]
    assert "Dock 01 has a higher observed value of 68.0" in response["answer"]
    assert "only 1 appointment" in response["answer"]

    dock_01 = next(
        fact for fact in response["facts"]
        if fact["label"] == "Dock 01"
    )
    assert dock_01["value"] == "68.0 · 1 appointment · Limited sample"


def test_all_small_groups_return_limited_evidence_warning():
    service = _ranking_service([
        {
            "group_id": "A",
            "group_label": "Dock A",
            "average_risk_score": 60.0,
            "appointment_count": 2,
        },
        {
            "group_id": "B",
            "group_label": "Dock B",
            "average_risk_score": 50.0,
            "appointment_count": 4,
        },
    ])
    plan = WarehouseQueryPlan(
        intent="ranking",
        metric="average_risk_score",
        group_by="dock",
        limit=5,
        understood=True,
    )

    response = service._ranking_response(plan)

    assert response["answer"].startswith("Dock A has the highest observed")
    assert "limited evidence" in response["answer"]
    assert all(
        "Limited sample" in fact["value"]
        for fact in response["facts"]
    )


def test_ranking_fact_uses_singular_appointment_grammar():
    text = DataCopilotService._ranking_fact_value(
        "average_risk_score",
        {
            "average_risk_score": 68.0,
            "appointment_count": 1,
        },
        limited_sample=True,
    )

    assert text == "68.0 · 1 appointment · Limited sample"
