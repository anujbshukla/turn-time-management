from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlanner, WarehouseQueryPlan


class _Repo:
    def action_effectiveness(self, **kwargs):
        return [
            {
                "action_signature": "REASSIGN_DOCK",
                "sample_size": 10,
                "sla_success_percent": 70.0,
                "avg_realized_minutes_saved": 24.6,
                "avg_realized_net_savings": 43,
            },
            {
                "action_signature": "ADD_FORKLIFT",
                "sample_size": 10,
                "sla_success_percent": 80.0,
                "avg_realized_minutes_saved": 13.4,
                "avg_realized_net_savings": 24,
            },
        ]


class _Appointments:
    pass


def _service():
    return DataCopilotService(
        analytics_repository=_Repo(),
        appointment_repository=_Appointments(),
    )


def test_action_effectiveness_uses_friendly_labels_and_all_evidence():
    plan = WarehouseQueryPlan(
        intent="action_effectiveness",
        metric="avg_realized_minutes_saved",
        understood=True,
        limit=5,
    )
    response = _service()._action_effectiveness_response(plan)
    assert response["answer"].startswith("Reassign Dock")
    assert "70.0% SLA success rate" in response["answer"]
    assert "10 observed executions" in response["answer"]
    assert response["facts"][0]["label"] == "Reassign Dock"
    assert "24.6 min saved" in response["facts"][0]["value"]
    assert "70.0% SLA success" in response["facts"][0]["value"]
    assert "$43 avg. savings" in response["facts"][0]["value"]
    assert "10 samples" in response["facts"][0]["value"]


def test_action_effectiveness_can_rank_by_sla_success():
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


def test_planner_routes_action_sla_success_metric():
    plan = WarehouseQueryPlanner().plan(
        "Which recovery actions have the highest SLA success rate historically?",
        conversation_history=[],
    )
    assert plan.intent == "action_effectiveness"
    assert plan.metric == "sla_success_rate"
    assert plan.ignore_request_date_context is True


def test_existing_worked_best_question_still_ranks_minutes_saved():
    plan = WarehouseQueryPlanner().plan(
        "Which recovery actions have actually worked best historically?",
        conversation_history=[],
    )
    assert plan.intent == "action_effectiveness"
    assert plan.metric == "avg_realized_minutes_saved"
