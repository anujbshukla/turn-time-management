from datetime import datetime

from app.services.multi_appointment_optimizer import (
    MultiAppointmentOptimizerService,
)


def _row(**overrides):
    row = {
        "appt_id": "DEMO1",
        "facility_id": "FAC001",
        "facility_name": "Atlanta Distribution Center",
        "scheduled_time": datetime(2026, 8, 14, 10, 0),
        "assigned_dock_id": "FAC001-DOCK-01",
        "dock_name": "Dock 01",
        "pallet_count": 30,
        "sku_count": 10,
        "sla_minutes": 120,
        "detention_cost_per_hour": 200,
        "predicted_delay_minutes": 20,
        "predicted_duration_minutes": 115,
        "sla_miss_probability": 0.88,
        "sla_recovery_probability": 0.12,
        "turn_risk_score": 91,
        "predicted_missed": True,
    }
    row.update(overrides)
    return MultiAppointmentOptimizerService._enrich_candidate(row)


def test_optimizer_prefers_recovery_option_when_capacity_exists():
    row = _row()
    option = MultiAppointmentOptimizerService._choose_option(
        row,
        available_loaders=3,
        available_forklifts=2,
    )

    projected_turn = row["baseline_turn_minutes"] - option.minutes_saved
    assert projected_turn <= row["sla_minutes"]
    assert option.minutes_saved >= 15


def test_optimizer_respects_zero_resource_headroom():
    row = _row()
    option = MultiAppointmentOptimizerService._choose_option(
        row,
        available_loaders=0,
        available_forklifts=0,
    )

    assert option.extra_loaders == 0
    assert option.extra_forklifts == 0
    assert option.staging_labor == 0
    assert option.minutes_saved == 0


def test_simple_load_does_not_receive_prestaging_option():
    row = _row(pallet_count=8, sku_count=2)
    option = MultiAppointmentOptimizerService._choose_option(
        row,
        available_loaders=3,
        available_forklifts=2,
    )

    assert "PRE_STAGE_PRODUCTS" not in option.action_codes
