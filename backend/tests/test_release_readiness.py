from pathlib import Path

from app.services.readiness_service import (
    EXPECTED_ALEMBIC_HEAD,
    ReadinessService,
)


def test_readiness_requires_all_required_dependencies():
    assert ReadinessService._overall_status(
        {
            "database": {"status": "ready", "required": True},
            "model": {"status": "ready", "required": True},
        }
    ) == (True, "ready")
    assert ReadinessService._overall_status(
        {
            "database": {"status": "ready", "required": True},
            "model": {"status": "failed", "required": True},
        }
    ) == (False, "not_ready")


def test_readiness_tracks_current_schema_head():
    assert EXPECTED_ALEMBIC_HEAD == "h5f2c8a7d630"


def test_registry_status_parameter_is_explicitly_typed():
    source = (
        Path(__file__).parents[1]
        / "app/services/ml_monitoring_service.py"
    ).read_text(encoding="utf-8")
    assert "CAST(:status AS VARCHAR)" in source
