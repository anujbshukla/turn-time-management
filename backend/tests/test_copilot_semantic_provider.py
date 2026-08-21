from datetime import datetime

from app.services.copilot_v2.nl_interpreter import NaturalLanguageInterpreter
from app.services.copilot_v2.providers import SemanticProvider


class FakeProvider(SemanticProvider):
    def generate_json(self, *, system_prompt, user_prompt, schema):
        assert "not exact phrases" in system_prompt
        assert "meaning" in system_prompt
        assert "how many appts did we hav last frday" in user_prompt
        filters = {key: None for key in schema["properties"]["filters"]["properties"]}
        return {
            "domain": "appointments",
            "intent": "summary",
            "metric": "appointment_count",
            "group_by": None,
            "sort_direction": "desc",
            "filters": filters,
            "date_from": "2026-08-14T00:00:00",
            "date_to": "2026-08-15T00:00:00",
            "explicit_time": True,
            "raw_time_expression": "last frday",
            "explicit_dimensions": [],
            "limit": 10,
            "confidence": 0.98,
            "clarification_needed": False,
            "clarification_question": None,
            "resource_type": None,
        }


def test_interpreter_is_provider_independent():
    query = NaturalLanguageInterpreter(provider=FakeProvider()).interpret(
        question="how many appts did we hav last frday",
        now=datetime(2026, 8, 18, 11, 0),
        dashboard_context={"facility_id": "FAC001"},
        conversation_state={},
        reference_data={},
    )
    assert query.metric == "appointment_count"
    assert query.explicit_time is True
    assert query.filters["date_from"] == datetime(2026, 8, 14)
    assert query.filters["date_to"] == datetime(2026, 8, 15)
