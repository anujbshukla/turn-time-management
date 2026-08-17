from datetime import datetime

import pytest

from app.schemas import (
    OptimizationMissionAcceptRequest,
    OptimizationMissionStatusRequest,
)


def test_accept_request_preserves_exact_operating_window():
    payload = OptimizationMissionAcceptRequest(
        facility_id="FAC001",
        customer_id="CUS001",
        carrier_id="CAR001",
        appointment_type="Inbound",
        window_start="2026-08-17T00:00:00",
        window_end="2026-08-18T00:00:00",
    )

    assert payload.facility_id == "FAC001"
    assert isinstance(payload.window_start, datetime)
    assert payload.window_end > payload.window_start


@pytest.mark.parametrize(
    "status",
    [
        "Proposed",
        "Accepted",
        "In Progress",
        "Completed",
        "Dismissed",
    ],
)
def test_mission_execution_status_contract(status):
    payload = OptimizationMissionStatusRequest(status=status)
    assert payload.status == status
