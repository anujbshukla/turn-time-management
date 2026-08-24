from unittest.mock import MagicMock

from app.services.demo_appointment_lifecycle_service import (
    DemoAppointmentLifecycleService,
)


def test_reconcile_executes_and_commits() -> None:
    db = MagicMock()

    mapping_result = MagicMock()
    mapping_result.one.return_value = {
        "updated_appointments": 7,
    }

    execute_result = MagicMock()
    execute_result.mappings.return_value = mapping_result
    db.execute.return_value = execute_result

    result = DemoAppointmentLifecycleService(
        db,
    ).reconcile()

    assert result.updated_appointments == 7
    db.execute.assert_called_once()
    db.commit.assert_called_once()


def test_reconcile_normalizes_null_count() -> None:
    db = MagicMock()

    mapping_result = MagicMock()
    mapping_result.one.return_value = {
        "updated_appointments": None,
    }

    execute_result = MagicMock()
    execute_result.mappings.return_value = mapping_result
    db.execute.return_value = execute_result

    result = DemoAppointmentLifecycleService(
        db,
    ).reconcile()

    assert result.updated_appointments == 0
