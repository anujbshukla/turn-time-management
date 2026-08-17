from app.engines.what_if_engine import WhatIfEngine


def _appointment():
    return {
        "sla_minutes": 120,
        "detention_cost_per_hour": 120.0,
    }


def _prediction():
    return {
        "predicted_delay_minutes": 5,
        "predicted_duration_minutes": 100,
        "sla_miss_probability": 0.80,
        "sla_recovery_probability": 0.20,
        "turn_risk_score": 79,
        "model_version": "baseline-v2",
    }


def test_no_action_scenario_is_exactly_the_baseline_even_if_ml_rescore_is_worse():
    result = WhatIfEngine().simulate(
        appointment=_appointment(),
        prediction=_prediction(),
        actions=[],
        selected_action_ids=[],
        extra_loaders=0,
        extra_forklifts=0,
        pre_stage_products=False,
        scenario_prediction={
            "predicted_delay_minutes": 8,
            "predicted_duration_minutes": 103,
            "sla_miss_probability": 0.82,
            "sla_recovery_probability": 0.04,
            "turn_risk_score": 82,
            "model_version": "warehouse-ml-v2-test",
        },
    )

    assert result["baseline"]["predicted_turn_time_minutes"] == 105
    assert result["scenario"]["projected_turn_time_minutes"] == 105
    assert result["scenario"]["minutes_saved"] == 0
    assert result["scenario"]["projected_risk_score"] == 79
    assert result["scenario"]["projected_sla_miss_probability"] == 0.80
    assert result["scenario"]["projected_recovery_probability"] == 0.20


def test_resource_intervention_cannot_make_turn_time_or_risk_worse():
    result = WhatIfEngine().simulate(
        appointment=_appointment(),
        prediction=_prediction(),
        actions=[],
        selected_action_ids=[],
        extra_loaders=0,
        extra_forklifts=1,
        pre_stage_products=False,
        scenario_prediction={
            # Observational ML can return a worse raw re-score because
            # high-complexity appointments historically used more equipment.
            "predicted_delay_minutes": 8,
            "predicted_duration_minutes": 103,
            "sla_miss_probability": 0.90,
            "sla_recovery_probability": 0.10,
            "turn_risk_score": 88,
            "model_version": "warehouse-ml-v2-test",
        },
    )

    assert result["scenario"]["projected_turn_time_minutes"] == 96
    assert result["scenario"]["minutes_saved"] == 9
    assert result["scenario"]["projected_turn_time_minutes"] <= 105
    assert result["scenario"]["projected_risk_score"] <= 79
    assert result["scenario"]["projected_sla_miss_probability"] <= 0.80
    assert result["scenario"]["projected_recovery_probability"] >= 0.20


def test_selected_action_and_manual_resource_savings_stack_from_same_baseline():
    actions = [
        {
            "recommendation_action_id": 10,
            "action_code": "RESERVE_DOCK",
            "estimated_minutes_saved": 8,
            "estimated_action_cost": 15,
            "additional_loaders": 0,
            "additional_forklifts": 0,
        }
    ]

    result = WhatIfEngine().simulate(
        appointment=_appointment(),
        prediction=_prediction(),
        actions=actions,
        selected_action_ids=[10],
        extra_loaders=1,
        scenario_prediction=None,
    )

    # 105 baseline - 8 dock action - 12 loader = 85
    assert result["scenario"]["projected_turn_time_minutes"] == 85
    assert result["scenario"]["minutes_saved"] == 20
    assert result["scenario"]["action_cost"] == 65
