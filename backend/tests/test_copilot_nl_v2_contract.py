from datetime import datetime
from app.services.copilot_v2.models import CanonicalCopilotQuery
from app.services.copilot_v2.query_validator import CanonicalQueryValidator
from app.services.copilot_v2.legacy_bridge import LegacyPlanBridge


def test_explicit_user_time_beats_dashboard_time():
    q = CanonicalCopilotQuery(metric="appointment_count", explicit_time=True, date_from=datetime(2026, 8, 14), date_to=datetime(2026, 8, 15))
    q.apply_dates_to_filters()
    plan = LegacyPlanBridge.to_legacy_plan(q)
    assert plan.filters["date_from"] == datetime(2026, 8, 14)
    assert plan.filters["date_to"] == datetime(2026, 8, 15)
    assert plan.ignore_request_date_context is True


def test_validator_rejects_unknown_filters():
    q = CanonicalCopilotQuery(filters={"made_up_filter": "x"})
    try:
        CanonicalQueryValidator().validate(q)
        assert False
    except ValueError as exc:
        assert "Unsupported Copilot filters" in str(exc)
