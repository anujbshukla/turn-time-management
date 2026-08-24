from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas import AppointmentRescheduleRequest


def test_reschedule_request_requires_reason() -> None:
    with pytest.raises(ValidationError):
        AppointmentRescheduleRequest(
            scheduled_time=datetime(2026, 8, 22, 9, 0),
            reason="",
        )


def test_reschedule_request_accepts_new_schedule() -> None:
    request = AppointmentRescheduleRequest(
        scheduled_time=datetime(2026, 8, 22, 9, 0),
        reason="Carrier requested a later delivery window.",
    )

    assert request.reason.startswith("Carrier")
