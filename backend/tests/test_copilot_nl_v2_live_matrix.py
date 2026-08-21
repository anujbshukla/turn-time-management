from datetime import datetime
import os
import pytest
from app.services.copilot_v2.nl_interpreter import NaturalLanguageInterpreter

pytestmark = pytest.mark.skipif(os.getenv("RUN_COPILOT_NL_LIVE_TESTS", "false").lower() != "true", reason="Live LLM regression is opt-in.")
NOW = datetime(2026, 8, 18, 11, 0, 0)

@pytest.mark.parametrize("question", [
    "How many appointments did I have last Friday?",
    "appointments last fri count",
    "last friday appts?",
    "how many appts did we hav last frday",
    "appt count previous friday",
])
def test_last_friday_semantic_family(question):
    q = NaturalLanguageInterpreter().interpret(question=question, now=NOW, dashboard_context={"facility_id": "FAC001", "date_from": "2026-08-18", "date_to": "2026-08-19"}, conversation_state={}, reference_data={})
    assert q.metric == "appointment_count"
    assert q.explicit_time
    assert q.date_from.date().isoformat() == "2026-08-14"
    assert q.date_to.date().isoformat() == "2026-08-15"
