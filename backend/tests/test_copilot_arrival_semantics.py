from app.services.query_planner import WarehouseQueryPlanner


def test_worst_on_time_arrival_rate_maps_to_highest_late_rate():
    plan = WarehouseQueryPlanner().plan(
        "Which carrier has the worst on-time arrival rate for the last 30 days?",
        conversation_history=[],
    )

    assert plan.intent == "ranking"
    assert plan.group_by == "carrier"
    assert plan.metric == "late_rate_percent"
    assert plan.ranking_direction == "desc"


def test_best_on_time_arrival_rate_maps_to_lowest_late_rate():
    plan = WarehouseQueryPlanner().plan(
        "Which carrier has the best on-time arrival rate for the last 30 days?",
        conversation_history=[],
    )

    assert plan.intent == "ranking"
    assert plan.group_by == "carrier"
    assert plan.metric == "late_rate_percent"
    assert plan.ranking_direction == "asc"


def test_most_late_carrier_maps_to_late_rate():
    plan = WarehouseQueryPlanner().plan(
        "Which carriers are most late this month?",
        conversation_history=[],
    )

    assert plan.group_by == "carrier"
    assert plan.metric == "late_rate_percent"
    assert plan.ranking_direction == "desc"


def test_most_punctual_carrier_uses_ascending_late_rate():
    plan = WarehouseQueryPlanner().plan(
        "Rank carriers by most punctual for the last 30 days",
        conversation_history=[],
    )

    assert plan.group_by == "carrier"
    assert plan.metric == "late_rate_percent"
    assert plan.ranking_direction == "asc"


class _RankingRepository:
    def __init__(self, rows):
        self.rows = rows

    def advanced_grouped_metrics(self, **kwargs):
        return list(self.rows)


class _UnusedAppointmentRepository:
    pass


def test_ascending_punctuality_ranking_still_applies_reliability_threshold():
    from app.services.data_copilot_service import DataCopilotService
    from app.services.query_planner import WarehouseQueryPlan

    service = DataCopilotService(
        analytics_repository=_RankingRepository([
            {
                "group_id": "CAR1",
                "group_label": "Tiny Carrier",
                "late_rate_percent": 0.0,
                "late_appointments": 0,
                "appointment_count": 1,
            },
            {
                "group_id": "CAR2",
                "group_label": "Reliable Carrier",
                "late_rate_percent": 8.0,
                "late_appointments": 4,
                "appointment_count": 50,
            },
            {
                "group_id": "CAR3",
                "group_label": "Other Carrier",
                "late_rate_percent": 12.0,
                "late_appointments": 6,
                "appointment_count": 50,
            },
        ]),
        appointment_repository=_UnusedAppointmentRepository(),
    )

    plan = WarehouseQueryPlan(
        intent="ranking",
        metric="late_rate_percent",
        group_by="carrier",
        ranking_direction="asc",
        limit=5,
        understood=True,
    )

    response = service._ranking_response(plan)

    assert response["answer"].startswith("Reliable Carrier ranks first")
    assert "at least 5 appointments" in response["answer"]
    assert "Tiny Carrier has a lower observed value of 0.0%" in response["answer"]
    assert "Limited sample" in response["answer"]
