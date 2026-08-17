from app.schemas import (
    OptimizationMissionAcceptRequest,
    OptimizationWindowRequest,
)


def test_mission_scenario_accepts_resource_caps():
    payload = OptimizationWindowRequest(
        facility_id="FAC001",
        date_from="2026-08-17T00:00:00",
        date_to="2026-08-18T00:00:00",
        max_extra_loaders_per_hour=1,
        max_extra_forklifts_per_hour=2,
        max_staging_labor_per_hour=0,
        allow_dock_reassignment=False,
    )

    assert payload.max_extra_loaders_per_hour == 1
    assert payload.max_extra_forklifts_per_hour == 2
    assert payload.max_staging_labor_per_hour == 0
    assert payload.allow_dock_reassignment is False


def test_accepted_mission_preserves_simulated_constraints():
    payload = OptimizationMissionAcceptRequest(
        facility_id="FAC001",
        window_start="2026-08-17T00:00:00",
        window_end="2026-08-18T00:00:00",
        max_extra_loaders_per_hour=1,
        max_extra_forklifts_per_hour=2,
        max_staging_labor_per_hour=1,
        allow_dock_reassignment=True,
    )

    assert payload.max_extra_loaders_per_hour == 1
    assert payload.max_extra_forklifts_per_hour == 2
    assert payload.max_staging_labor_per_hour == 1
    assert payload.allow_dock_reassignment is True
