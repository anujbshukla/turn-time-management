from datetime import datetime

from app.services.multi_appointment_optimizer import (
    MultiAppointmentOptimizerService,
)


def test_shift_mapping_matches_three_shift_operating_model():
    service = MultiAppointmentOptimizerService.__new__(
        MultiAppointmentOptimizerService
    )

    assert service._shift_name_for_hour(6) == "First"
    assert service._shift_name_for_hour(13) == "First"
    assert service._shift_name_for_hour(14) == "Second"
    assert service._shift_name_for_hour(21) == "Second"
    assert service._shift_name_for_hour(22) == "Third"
    assert service._shift_name_for_hour(4) == "Third"


def test_temperature_compatibility_protects_cold_chain_capacity():
    service = MultiAppointmentOptimizerService.__new__(
        MultiAppointmentOptimizerService
    )

    assert service._temperature_compatible("Frozen", "Frozen")
    assert service._temperature_compatible("Chilled", "Chilled")
    assert service._temperature_compatible("Ambient", "Ambient")
    assert not service._temperature_compatible("Frozen", "Chilled")
    assert not service._temperature_compatible("Ambient", "Frozen")


def test_interval_overlap_detects_dock_conflicts():
    service = MultiAppointmentOptimizerService.__new__(
        MultiAppointmentOptimizerService
    )

    start = datetime(2026, 8, 17, 10, 0)
    end = datetime(2026, 8, 17, 11, 0)

    assert service._interval_overlaps(
        start,
        end,
        datetime(2026, 8, 17, 10, 30),
        datetime(2026, 8, 17, 11, 30),
    )
    assert not service._interval_overlaps(
        start,
        end,
        datetime(2026, 8, 17, 11, 0),
        datetime(2026, 8, 17, 12, 0),
    )


def test_find_recovery_dock_chooses_free_temperature_compatible_dock():
    service = MultiAppointmentOptimizerService.__new__(
        MultiAppointmentOptimizerService
    )

    row = {
        "appt_id": "DEMO-1",
        "assigned_dock_id": "D1",
        "required_temperature_zone": "Frozen",
    }
    docks = [
        {
            "dock_id": "D1",
            "dock_name": "Dock 1",
            "temperature_zone": "Frozen",
        },
        {
            "dock_id": "D2",
            "dock_name": "Dock 2",
            "temperature_zone": "Frozen",
        },
        {
            "dock_id": "D3",
            "dock_name": "Dock 3",
            "temperature_zone": "Ambient",
        },
    ]
    occupancy = {
        "D2": [],
        "D3": [],
    }

    dock = service._find_recovery_dock(
        row,
        docks,
        occupancy,
        service_start=datetime(2026, 8, 17, 10, 0),
        service_end=datetime(2026, 8, 17, 11, 0),
    )

    assert dock is not None
    assert dock["dock_id"] == "D2"
