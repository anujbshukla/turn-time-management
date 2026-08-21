from pathlib import Path


def test_copilot_repository_does_not_reference_nonexistent_estimated_delay_column():
    repository_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "repositories"
        / "copilot_analytics_repository.py"
    )
    source = repository_path.read_text(encoding="utf-8")

    assert "appointment.estimated_delay_minutes" not in source
    assert "prediction.predicted_delay_minutes" in source


def test_turn_time_driver_uses_prediction_delay_for_arrival_delay_signal():
    repository_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "repositories"
        / "copilot_analytics_repository.py"
    )
    source = repository_path.read_text(encoding="utf-8")

    assert "'Predicted arrival delay'" in source
    assert "scoped.predicted_delay_minutes > 0" in source
