from datetime import datetime
import os

import pytest

from app.services.copilot_v2.models import CanonicalCopilotQuery
from app.services.copilot_v2.nl_interpreter import NaturalLanguageInterpreter
from app.services.copilot_v2.query_engine import NaturalLanguageQueryEngine


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COPILOT_NL_LIVE_TESTS", "false").lower() != "true",
    reason="Live LLM semantic regression is opt-in.",
)

NOW = datetime(2026, 8, 18, 11, 0, 0)

REFERENCE_DATA = {
    "facilities": [
        {"id": "FAC001", "label": "Atlanta Distribution Center"},
        {"id": "FAC002", "label": "Dallas Distribution Center"},
    ],
    "carriers": [
        {"id": "CAR001", "label": "United Cargo"},
        {"id": "CAR002", "label": "National Express"},
    ],
    "customers": [
        {"id": "CUS001", "label": "Acme Foods"},
        {"id": "CUS002", "label": "Northstar Retail"},
    ],
    "products": [
        {"id": "PROD0378", "label": "Electronics Item 0378", "sku": "SKU0378"},
    ],
}


def _interpret(
    question: str,
    *,
    state: dict | None = None,
    dashboard_context: dict | None = None,
):
    return NaturalLanguageInterpreter().interpret(
        question=question,
        now=NOW,
        dashboard_context=dashboard_context or {"facility_id": "FAC001"},
        conversation_state=state or {},
        reference_data=REFERENCE_DATA,
    )


@pytest.mark.parametrize(
    "question,metric,intent,group_by",
    [
        ("how many appointments yesterday", "appointment_count", "summary", None),
        ("how many SLA misses last week", "sla_risk_or_misses", "summary", None),
        ("what percent missed SLA last month", "sla_miss_rate_percent", "summary", None),
        ("which carrier performs worst on SLA", "sla_miss_rate_percent", "ranking", "carrier"),
        ("rank facilities by turn time", "average_turn_time_minutes", "ranking", "facility"),
        ("compare customers by late arrival rate", "late_rate_percent", "ranking", "customer"),
        ("which dock has the highest risk score", "average_risk_score", "ranking", "dock"),
        ("what was average turn time last friday", "average_turn_time_minutes", "summary", None),
        ("how much detention exposure did we have last month", "detention_exposure", "summary", None),
    ],
)
def test_core_metric_intent_grouping(question, metric, intent, group_by):
    q = _interpret(question)
    assert q.metric == metric
    assert q.intent == intent
    assert q.group_by == group_by


@pytest.mark.parametrize(
    "question,expected_from,expected_to",
    [
        ("appointments yesterday", "2026-08-17", "2026-08-18"),
        ("appointments last friday", "2026-08-14", "2026-08-15"),
        ("appointments last 7 days", "2026-08-11", "2026-08-18"),
        ("appointments last 30 days", "2026-07-19", "2026-08-18"),
        ("appointments august 1 through august 10", "2026-08-01", "2026-08-11"),
    ],
)
def test_temporal_language(question, expected_from, expected_to):
    q = _interpret(question)
    assert q.explicit_time is True
    assert q.date_from.date().isoformat() == expected_from
    assert q.date_to.date().isoformat() == expected_to


@pytest.mark.parametrize(
    "question,filter_name,expected",
    [
        ("only inbound", "appointment_type", "Inbound"),
        ("outbound appointments", "appointment_type", "Outbound"),
        ("only critical risk", "risk_level", "Critical"),
        ("high risk appointments", "risk_level", "High"),
    ],
)
def test_canonical_dimension_filters(question, filter_name, expected):
    q = _interpret(question)
    assert q.filters.get(filter_name) == expected


@pytest.mark.parametrize(
    "question,key,expected",
    [
        ("appointments with more than 30 pallets", "pallet_min", 31),
        ("appointments with at least 20 pallets", "pallet_min", 20),
        ("appointments under 10 pallets", "pallet_max", 9),
        ("appointments with more than 10 SKUs", "sku_min", 11),
    ],
)
def test_numeric_filter_semantics(question, key, expected):
    q = _interpret(question)
    assert q.filters.get(key) == expected


@pytest.mark.parametrize(
    "question,expected_group,expected_metric",
    [
        ("which recovery actions worked best historically", None, "avg_realized_minutes_saved"),
        ("which recovery actions have the best SLA success", None, "sla_success_rate"),
        ("do extra loaders help historically", None, "average_turn_time_minutes"),
        ("do extra forklifts help outbound appointments", None, "average_turn_time_minutes"),
    ],
)
def test_specialized_analytics_semantics(question, expected_group, expected_metric):
    q = _interpret(question)
    assert q.metric == expected_metric
    if "recovery actions" in question:
        assert q.intent == "action_effectiveness"
    if "loaders" in question or "forklifts" in question:
        assert q.intent == "resource_effectiveness"


@pytest.mark.parametrize(
    "question,expected_intent",
    [
        ("what are the biggest risk drivers", "risk_drivers"),
        ("why is turn time high", "driver_analysis"),
        ("which products take longest to handle", "product_handling"),
        ("how many optimization missions were completed", "mission_summary"),
        ("show the five highest risk appointments", "top_risk"),
    ],
)
def test_specialized_intents(question, expected_intent):
    q = _interpret(question)
    assert q.intent == expected_intent


def test_follow_up_chain_preserves_and_mutates_state():
    prior = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={"facility_id": "FAC001"},
        date_from=datetime(2026, 7, 19),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
        explicit_dimensions=["metric", "group_by", "time"],
        limit=5,
    )
    prior.apply_dates_to_filters()

    follow_1 = _interpret(
        "only inbound",
        state=prior.to_state_dict(),
    )
    merged_1 = NaturalLanguageQueryEngine.merge_with_prior_state(
        follow_1,
        prior,
    )
    assert merged_1.metric == "sla_miss_rate_percent"
    assert merged_1.group_by == "carrier"
    assert merged_1.filters["appointment_type"] == "Inbound"
    assert merged_1.date_from.date().isoformat() == "2026-07-19"

    follow_2 = _interpret(
        "last 7 days",
        state=merged_1.to_state_dict(),
    )
    merged_2 = NaturalLanguageQueryEngine.merge_with_prior_state(
        follow_2,
        merged_1,
    )
    assert merged_2.metric == "sla_miss_rate_percent"
    assert merged_2.group_by == "carrier"
    assert merged_2.filters["appointment_type"] == "Inbound"
    assert merged_2.date_from.date().isoformat() == "2026-08-11"
    assert merged_2.date_to.date().isoformat() == "2026-08-18"

    follow_3 = _interpret(
        "rank by turn time instead",
        state=merged_2.to_state_dict(),
    )
    merged_3 = NaturalLanguageQueryEngine.merge_with_prior_state(
        follow_3,
        merged_2,
    )
    assert merged_3.metric == "average_turn_time_minutes"
    assert merged_3.group_by == "carrier"
    assert merged_3.filters["appointment_type"] == "Inbound"
    assert merged_3.date_from.date().isoformat() == "2026-08-11"


def test_dashboard_date_is_not_used_when_user_specifies_time():
    q = _interpret(
        "how many appointments last friday",
        dashboard_context={
            "facility_id": "FAC001",
            "date_from": "2026-08-18",
            "date_to": "2026-08-19",
        },
    )
    assert q.explicit_time is True
    assert q.date_from.date().isoformat() == "2026-08-14"
    assert q.date_to.date().isoformat() == "2026-08-15"
