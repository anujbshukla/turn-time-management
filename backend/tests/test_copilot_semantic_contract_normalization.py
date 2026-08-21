from datetime import datetime

from app.services.copilot_v2.nl_interpreter import (
    NaturalLanguageInterpreter,
)


class FakeProvider:
    def __init__(self, response):
        self.response = response

    def generate_json(
        self,
        *,
        system_prompt,
        user_prompt,
        schema,
    ):
        return self.response


def base_response():
    return {
        "domain": "appointments",
        "intent": "summary",
        "metric": "appointment_count",
        "group_by": None,
        "sort_direction": "desc",
        "filters": {
            "facility_id": None,
            "customer_id": None,
            "carrier_id": None,
            "dock_id": None,
            "assigned_dock_id": None,
            "appointment_type": None,
            "status": None,
            "risk_level": None,
            "product_id": None,
            "load_type": None,
            "temperature_zone": None,
            "pallet_band": None,
            "congestion_band": None,
            "pallet_min": None,
            "pallet_max": None,
            "sku_min": None,
            "sku_max": None,
        },
        "date_from": None,
        "date_to": None,
        "explicit_time": False,
        "raw_time_expression": None,
        "explicit_dimensions": [],
        "limit": 10,
        "confidence": 0.95,
        "clarification_needed": False,
        "clarification_question": None,
        "resource_type": None,
    }


def interpret(response):
    return NaturalLanguageInterpreter(
        provider=FakeProvider(response)
    ).interpret(
        question="test",
        now=datetime(2026, 8, 18, 11, 0),
        dashboard_context={},
        conversation_state={},
        reference_data={},
    )


def test_inbound_is_canonicalized():
    response = base_response()
    response["filters"]["appointment_type"] = "inbound"
    query = interpret(response)
    assert query.filters["appointment_type"] == "Inbound"


def test_outbound_is_canonicalized():
    response = base_response()
    response["filters"]["appointment_type"] = "outbound"
    query = interpret(response)
    assert query.filters["appointment_type"] == "Outbound"


def test_risk_level_is_canonicalized():
    response = base_response()
    response["filters"]["risk_level"] = "critical"
    query = interpret(response)
    assert query.filters["risk_level"] == "Critical"


def test_schema_constrains_appointment_type_values():
    schema = NaturalLanguageInterpreter._schema()
    appt = schema["properties"]["filters"]["properties"]["appointment_type"]
    assert "Inbound" in appt["anyOf"][0]["enum"]
    assert "Outbound" in appt["anyOf"][0]["enum"]


def test_prompt_distinguishes_count_from_rate():
    interpreter = NaturalLanguageInterpreter(
        provider=FakeProvider(base_response())
    )
    prompt = interpreter.catalog.prompt_text().lower()
    assert "raw number" in prompt
    assert "normalized percent" in prompt
    assert "performance comparisons" in prompt
