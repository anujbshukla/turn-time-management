from datetime import datetime

from app.services.copilot_v2.models import CanonicalCopilotQuery
from app.services.copilot_v2.query_engine import NaturalLanguageQueryEngine


def test_follow_up_filter_does_not_drop_other_filters():
    prior = CanonicalCopilotQuery(
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={
            "facility_id": "FAC001",
            "appointment_type": "Inbound",
            "risk_level": "High",
        },
    )

    current = CanonicalCopilotQuery(
        filters={"appointment_type": "Outbound"},
        explicit_dimensions=["appointment_type"],
    )

    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        current,
        prior,
    )

    assert merged.filters["facility_id"] == "FAC001"
    assert merged.filters["appointment_type"] == "Outbound"
    assert merged.filters["risk_level"] == "High"


def test_metric_switch_does_not_drop_grouping():
    prior = CanonicalCopilotQuery(
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={"facility_id": "FAC001"},
    )

    current = CanonicalCopilotQuery(
        metric="average_turn_time_minutes",
        explicit_dimensions=["metric"],
    )

    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        current,
        prior,
    )

    assert merged.metric == "average_turn_time_minutes"
    assert merged.group_by == "carrier"
    assert merged.filters["facility_id"] == "FAC001"


def test_explicit_date_replacement_preserves_non_date_filters():
    prior = CanonicalCopilotQuery(
        intent="ranking",
        metric="sla_miss_rate_percent",
        group_by="carrier",
        filters={
            "facility_id": "FAC001",
            "appointment_type": "Inbound",
        },
        date_from=datetime(2026, 7, 19),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
    )
    prior.apply_dates_to_filters()

    current = CanonicalCopilotQuery(
        date_from=datetime(2026, 8, 11),
        date_to=datetime(2026, 8, 18),
        explicit_time=True,
        explicit_dimensions=["time"],
    )
    current.apply_dates_to_filters()

    merged = NaturalLanguageQueryEngine.merge_with_prior_state(
        current,
        prior,
    )

    assert merged.filters["facility_id"] == "FAC001"
    assert merged.filters["appointment_type"] == "Inbound"
    assert merged.date_from == datetime(2026, 8, 11)
    assert merged.date_to == datetime(2026, 8, 18)
