from datetime import datetime

from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlan


class _ResourceRepository:
    def resource_effectiveness(self, **kwargs):
        return [
            {
                "resource_count": 1,
                "appointment_count": 224,
                "average_turn_time_minutes": 58.0,
                "sla_miss_rate_percent": 0.9,
                "average_pallet_count": 18.0,
            },
            {
                "resource_count": 2,
                "appointment_count": 141,
                "average_turn_time_minutes": 71.1,
                "sla_miss_rate_percent": 1.4,
                "average_pallet_count": 24.0,
            },
        ]


class _UnusedAppointmentRepository:
    pass


def _service():
    return DataCopilotService(
        analytics_repository=_ResourceRepository(),
        appointment_repository=_UnusedAppointmentRepository(),
    )


def test_resource_effectiveness_uses_last_30_days_wording_and_sample_size():
    plan = WarehouseQueryPlan(
        intent="resource_effectiveness",
        resource_type="loaders",
        metric="average_turn_time_minutes",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "appointment_type": "Inbound",
            "date_from": datetime(2026, 7, 19),
            "date_to": datetime(2026, 8, 18),
        },
    )

    response = _service()._resource_effectiveness_response(plan)

    assert response["answer"].startswith(
        "Over the last 30 days for inbound appointments"
    )
    assert "based on 224 appointments" in response["answer"]
    assert "Historically" not in response["answer"]
    assert response["facts"][0]["value"] == (
        "58.0 min · 0.9% SLA miss · 224 appointments"
    )


def test_resource_effectiveness_uses_historical_wording_without_dates():
    plan = WarehouseQueryPlan(
        intent="resource_effectiveness",
        resource_type="loaders",
        metric="average_turn_time_minutes",
        understood=True,
        filters={
            "facility_id": "FAC001",
            "appointment_type": "Inbound",
        },
    )

    response = _service()._resource_effectiveness_response(plan)

    assert response["answer"].startswith(
        "Historically for inbound appointments"
    )
    assert "based on 224 appointments" in response["answer"]


def test_resource_effectiveness_uses_singular_sample_grammar():
    class _SingleRepository:
        def resource_effectiveness(self, **kwargs):
            return [
                {
                    "resource_count": 1,
                    "appointment_count": 1,
                    "average_turn_time_minutes": 55.0,
                    "sla_miss_rate_percent": 0.0,
                    "average_pallet_count": 15.0,
                },
            ]

    service = DataCopilotService(
        analytics_repository=_SingleRepository(),
        appointment_repository=_UnusedAppointmentRepository(),
    )
    plan = WarehouseQueryPlan(
        intent="resource_effectiveness",
        resource_type="loaders",
        understood=True,
    )

    response = service._resource_effectiveness_response(plan)

    assert "based on 1 appointment." in response["answer"]
    assert response["facts"][0]["value"].endswith("1 appointment")
