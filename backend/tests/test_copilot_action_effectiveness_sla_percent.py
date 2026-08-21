from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlan


class _Repo:
    def action_effectiveness(self, **kwargs):
        return [
            {
                "action_signature": "REASSIGN_DOCK",
                "sample_size": 100,
                "sla_success_percent": 70.0,
                "avg_realized_minutes_saved": 24.3,
                "avg_realized_net_savings": 44,
            },
            {
                "action_signature": "ADD_FORKLIFT",
                "sample_size": 100,
                "sla_success_percent": 80.0,
                "avg_realized_minutes_saved": 13.0,
                "avg_realized_net_savings": 21,
            },
        ]


class _Appointments:
    pass


def _service():
    return DataCopilotService(
        analytics_repository=_Repo(),
        appointment_repository=_Appointments(),
    )


def test_minutes_saved_response_uses_repository_sla_percent():
    plan = WarehouseQueryPlan(
        intent="action_effectiveness",
        metric="avg_realized_minutes_saved",
        understood=True,
        limit=5,
    )
    response = _service()._action_effectiveness_response(plan)
    assert response["answer"].startswith("Reassign Dock")
    assert "70.0% SLA success rate" in response["answer"]
    assert "70.0% SLA success" in response["facts"][0]["value"]


def test_sla_success_response_ranks_by_repository_percent():
    plan = WarehouseQueryPlan(
        intent="action_effectiveness",
        metric="sla_success_rate",
        understood=True,
        limit=5,
    )
    response = _service()._action_effectiveness_response(plan)
    assert response["answer"].startswith("Add Forklift")
    assert "highest historical SLA success rate at 80.0%" in response["answer"]
    assert response["facts"][0]["label"] == "Add Forklift"
