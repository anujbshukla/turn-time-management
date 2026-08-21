from datetime import datetime
import os

import pytest

from app.services.copilot_v2.nl_interpreter import NaturalLanguageInterpreter
from app.services.copilot_v2.query_engine import NaturalLanguageQueryEngine
from app.services.copilot_v2.models import CanonicalCopilotQuery


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COPILOT_NL_LIVE_TESTS", "false").lower() != "true",
    reason="Live LLM semantic regression is opt-in.",
)

NOW = datetime(2026, 8, 18, 11, 0, 0)


def _interpret(question, state=None):
    return NaturalLanguageInterpreter().interpret(
        question=question,
        now=NOW,
        dashboard_context={"facility_id": "FAC001"},
        conversation_state=state or {},
        reference_data={},
    )


@pytest.mark.parametrize(
    "question,metric,group_by",
    [
        ("which carrier has the worst sla performance?", "sla_miss_rate_percent", "carrier"),
        ("rank carriers by missed sla", "sla_miss_rate_percent", "carrier"),
        ("who takes longest to turn", "average_turn_time_minutes", None),
        ("what did detention cost us last month", "detention_exposure", None),
        ("how many were late yesterday", "late_appointments", None),
        ("avg dock congestion last week", "average_dock_congestion_percent", None),
    ],
)
def test_metric_and_ranking_semantics(question, metric, group_by):
    q = _interpret(question)
    assert q.metric == metric
    if group_by is not None:
        assert q.group_by == group_by


@pytest.mark.parametrize(
    "question,appointment_type",
    [
        ("only inbound", "Inbound"),
        ("inbound only please", "Inbound"),
        ("what about outbound", "Outbound"),
    ],
)
def test_appointment_type_follow_up_semantics(question, appointment_type):
    q = _interpret(question)
    assert q.filters.get("appointment_type") == appointment_type


def test_multi_turn_state_merge():
    prior = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={"facility_id": "FAC001"},
        date_from=datetime(2026, 7, 19),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
        limit=5,
    )
    prior.apply_dates_to_filters()

    follow = _interpret(
        "only inbound",
        state=prior.to_state_dict(),
    )
    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        follow,
        prior,
    )

    assert merged.metric == "sla_miss_rate_percent"
    assert merged.group_by == "carrier"
    assert merged.filters["appointment_type"] == "Inbound"
    assert merged.date_from == datetime(2026, 7, 19)
    assert merged.date_to == datetime(2026, 8, 18)
