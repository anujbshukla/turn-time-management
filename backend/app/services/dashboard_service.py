from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.repositories.dashboard_repository import (
    DashboardRepository,
)


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {
            key: normalize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_value(item)
            for item in value
        ]

    return value


class DashboardService:
    def __init__(
        self,
        repository: DashboardRepository,
    ) -> None:
        self.repository = repository

    def get_dashboard(
        self,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        dashboard = {
            "summary": self.repository.get_summary(
                facility_id
            ),
            "status_distribution": (
                self.repository.get_status_distribution(
                    facility_id
                )
            ),
            "late_appointment_outcomes": (
                self.repository.get_late_outcomes(
                    facility_id
                )
            ),
            "facility_performance": (
                self.repository.get_facility_performance()
            ),
            "risk_distribution": (
                self.repository.get_risk_distribution(
                    facility_id
                )
            ),
            "daily_compliance_trend": (
                self.repository.get_daily_compliance_trend(
                    facility_id
                )
            ),
            "high_risk_appointments": (
                self.repository.get_high_risk_appointments(
                    facility_id
                )
            ),
        }

        return normalize_value(dashboard)