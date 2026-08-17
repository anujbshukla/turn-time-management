from pathlib import Path

def test_realized_outcome_api_exists():
    api = (Path(__file__).parents[1] / "app/api/optimization.py").read_text(encoding="utf-8")
    assert "/missions/{mission_id}/outcomes/refresh" in api
    assert "refresh_realized_outcomes" in api

def test_completion_captures_realized_outcomes():
    source = (Path(__file__).parents[1] / "app/services/multi_appointment_optimizer.py").read_text(encoding="utf-8")
    assert 'elif status == "Completed":' in source
    assert "self._capture_realized_outcomes(mission_id)" in source
    assert "actual_turn_time_minutes IS NOT NULL" in source

def test_learning_persists_observed_outcomes():
    source = (Path(__file__).parents[1] / "app/services/multi_appointment_optimizer.py").read_text(encoding="utf-8")
    for field in ["actual_turn_time_minutes", "actual_sla_missed", "realized_net_savings", "outcome_sample_size"]:
        assert field in source
