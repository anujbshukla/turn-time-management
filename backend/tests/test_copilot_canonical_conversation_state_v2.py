from datetime import datetime

from app.services.copilot_v2.models import CanonicalCopilotQuery
from app.services.copilot_v2.query_engine import NaturalLanguageQueryEngine


def test_canonical_state_round_trip():
    original = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={"facility_id": "FAC001", "appointment_type": "Inbound"},
        date_from=datetime(2026, 7, 19),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
        limit=5,
    )
    original.apply_dates_to_filters()
    restored = CanonicalCopilotQuery.from_state_dict(
        original.to_state_dict()
    )
    assert restored is not None
    assert restored.metric == "sla_miss_rate_percent"
    assert restored.group_by == "carrier"
    assert restored.filters["appointment_type"] == "Inbound"
    assert restored.date_from == datetime(2026, 7, 19)
    assert restored.date_to == datetime(2026, 8, 18)


def test_follow_up_keeps_prior_metric_grouping_and_time():
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

    current = CanonicalCopilotQuery(
        filters={"appointment_type": "Inbound"},
        explicit_dimensions=["appointment_type"],
    )

    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        current,
        prior,
    )

    assert merged.intent == "ranking"
    assert merged.metric == "sla_miss_rate_percent"
    assert merged.group_by == "carrier"
    assert merged.filters["facility_id"] == "FAC001"
    assert merged.filters["appointment_type"] == "Inbound"
    assert merged.date_from == datetime(2026, 7, 19)
    assert merged.date_to == datetime(2026, 8, 18)


def test_explicit_new_time_replaces_prior_time():
    prior = CanonicalCopilotQuery(
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        date_from=datetime(2026, 1, 1),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
    )
    prior.apply_dates_to_filters()

    current = CanonicalCopilotQuery(
        date_from=datetime(2026, 7, 19),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
        explicit_dimensions=["time"],
    )
    current.apply_dates_to_filters()

    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        current,
        prior,
    )

    assert merged.date_from == datetime(2026, 7, 19)
    assert merged.date_to == datetime(2026, 8, 18)

def test_demo_three_turn_ranking_context_chain():
    # Turn 1:
    # "Rank carriers by average turn time in the last 30 days"
    initial = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="average_turn_time_minutes",
        group_by="carrier",
        sort_direction="desc",
        filters={
            "facility_id": "FAC001",
        },
        date_from=datetime(2026, 7, 21),
        date_to=datetime(2026, 8, 20),
        explicit_time=True,
        explicit_dimensions=[
            "metric",
            "group_by",
            "time",
        ],
        limit=25,
    )
    initial.apply_dates_to_filters()

    assert initial.intent == "ranking"
    assert initial.metric == "average_turn_time_minutes"
    assert initial.group_by == "carrier"

    # Turn 2:
    # "What about only inbound appointments?"
    #
    # The semantic layer has interpreted the current turn while
    # preserving the analytical dimensions from the prior state.
    inbound_follow_up = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="average_turn_time_minutes",
        group_by="carrier",
        sort_direction="desc",
        filters={
            "appointment_type": "Inbound",
        },
        explicit_time=False,
        explicit_dimensions=[
            "appointment_type",
        ],
        limit=25,
    )

    inbound = NaturalLanguageQueryEngine.merge_with_prior_state(
        inbound_follow_up,
        initial,
    )

    assert inbound.intent == "ranking"
    assert inbound.metric == "average_turn_time_minutes"
    assert inbound.group_by == "carrier"

    assert inbound.filters["facility_id"] == "FAC001"
    assert inbound.filters["appointment_type"] == "Inbound"

    assert inbound.date_from == initial.date_from
    assert inbound.date_to == initial.date_to

    # Turn 3:
    # "Rank by SLA miss rate instead"
    metric_follow_up = CanonicalCopilotQuery(
        domain="appointments",
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        sort_direction="desc",
        filters={},
        explicit_time=False,
        explicit_dimensions=[
            "metric",
        ],
        limit=25,
    )

    final = NaturalLanguageQueryEngine.merge_with_prior_state(
        metric_follow_up,
        inbound,
    )

    # Metric changes...
    assert final.metric == "sla_miss_rate_percent"

    # ...while the rest of the analytical context survives.
    assert final.intent == "ranking"
    assert final.group_by == "carrier"

    assert final.filters["facility_id"] == "FAC001"
    assert final.filters["appointment_type"] == "Inbound"

    assert final.date_from == initial.date_from
    assert final.date_to == initial.date_to