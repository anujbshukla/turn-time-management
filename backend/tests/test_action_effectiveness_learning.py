from app.services.multi_appointment_optimizer import (
    InterventionOption,
    MultiAppointmentOptimizerService,
)


def _row():
    return {
        "appointment_type": "Inbound",
        "load_type": "Palletized",
        "required_temperature_zone": "Ambient",
        "pallet_count": 25,
        "dock_congestion_percent": 55,
        "baseline_turn_minutes": 135,
        "sla_minutes": 120,
        "detention_cost_per_hour": 120,
        "baseline_exposure": 30,
        "complex_load": True,
    }


def test_learning_does_not_override_baseline_with_tiny_sample():
    option = InterventionOption(
        ("ADD_LOADER",),
        12,
        extra_loaders=1,
        action_cost=50,
    )
    profiles = {
        (
            "ADD_LOADER",
            "Inbound",
            "Palletized",
            "Ambient",
            "20-29",
            "High",
        ): {
            "sample_size": 2,
            "confidence_weight": 0.8,
            "avg_realized_minutes_saved": 30,
            "sla_success_rate": 1.0,
            "avg_realized_net_savings": 90,
        }
    }

    estimate = MultiAppointmentOptimizerService._learned_option_estimate(
        _row(),
        option,
        profiles,
    )

    assert estimate["source"] == "baseline_assumption"
    assert estimate["minutes_saved"] == 12


def test_learning_blends_realized_effect_with_baseline():
    option = InterventionOption(
        ("ADD_LOADER",),
        12,
        extra_loaders=1,
        action_cost=50,
    )
    profiles = {
        (
            "ADD_LOADER",
            "Inbound",
            "Palletized",
            "Ambient",
            "20-29",
            "High",
        ): {
            "sample_size": 20,
            "confidence_weight": 20 / 30,
            "avg_realized_minutes_saved": 18,
            "sla_success_rate": 0.85,
            "avg_realized_net_savings": 65,
        }
    }

    estimate = MultiAppointmentOptimizerService._learned_option_estimate(
        _row(),
        option,
        profiles,
    )

    assert estimate["source"] == "realized_outcome_learning"
    assert 12 < estimate["minutes_saved"] < 18
    assert estimate["sample_size"] == 20


def test_learning_context_is_specific_to_operating_conditions():
    option = InterventionOption(
        ("ADD_FORKLIFT",),
        9,
        extra_forklifts=1,
        action_cost=35,
    )
    profiles = {
        (
            "ADD_FORKLIFT",
            "Outbound",
            "Palletized",
            "Ambient",
            "20-29",
            "High",
        ): {
            "sample_size": 30,
            "confidence_weight": 0.75,
            "avg_realized_minutes_saved": 20,
            "sla_success_rate": 0.9,
            "avg_realized_net_savings": 70,
        }
    }

    estimate = MultiAppointmentOptimizerService._learned_option_estimate(
        _row(),
        option,
        profiles,
    )

    # Inbound row must not borrow an Outbound effectiveness profile.
    assert estimate["source"] == "baseline_assumption"
    assert estimate["minutes_saved"] == 9
