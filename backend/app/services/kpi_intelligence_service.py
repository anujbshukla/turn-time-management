from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.outcome_rules import (
    completed_sla_met_sql,
    completed_sla_missed_sql,
    recommendation_used_exists_sql,
)


class KpiIntelligenceService:
    """Build KPI intelligence for the active dashboard operating window."""

    KPI_DEFINITIONS = (
        {
            "key": "appointments",
            "label": "Appointments",
            "detail": "Scheduled for the selected operating window",
            "target": None,
            "better_when": "neutral",
            "format": "number",
        },
        {
            "key": "late_arrivals",
            "label": "Late Arrivals",
            "detail": "Arrived after scheduled time",
            "target": 10.0,
            "better_when": "down",
            "format": "number",
        },
        {
            "key": "sla_misses",
            "label": "SLA Misses",
            "detail": "Completed beyond SLA",
            "target": 0.0,
            "better_when": "down",
            "format": "number",
        },
        {
            "key": "late_turns_recovered",
            "label": "Late Turns Recovered",
            "detail": "Late arrivals turned within SLA",
            "target": 90.0,
            "better_when": "up",
            "format": "number",
        },
        {
            "key": "recovered_by_actions",
            "label": "Recovered by Actions",
            "detail": "Recoveries supported by accepted actions",
            "target": 75.0,
            "better_when": "up",
            "format": "number",
        },
    )

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def build(
        self,
        facility_id: str | None = None,
        *,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        # date_to is exclusive throughout the dashboard API.
        selected_start = date_from or date.today()
        selected_end = date_to or (selected_start + timedelta(days=1))
        if selected_end <= selected_start:
            selected_end = selected_start + timedelta(days=1)

        period_days = max(1, (selected_end - selected_start).days)

        # Multi-day windows show exactly the selected dates.
        # Single-day windows retain useful historical context in the sparkline.
        if period_days > 1:
            trend_start = selected_start
            trend_end = selected_end
        else:
            trend_start = selected_start - timedelta(days=13)
            trend_end = selected_end

        previous_start = selected_start - timedelta(days=period_days)
        previous_end = selected_start

        history_start = min(trend_start, previous_start)
        rows = self._daily_rows(
            history_start,
            selected_end,
            facility_id=facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            appointment_type=appointment_type,
        )
        by_date = {row["operation_date"]: row for row in rows}

        def row_for(operation_date: date) -> dict[str, Any]:
            return by_date.get(
                operation_date,
                {
                    "operation_date": operation_date,
                    "appointments": 0,
                    "late_arrivals": 0,
                    "sla_misses": 0,
                    "late_turns_recovered": 0,
                    "recovered_by_actions": 0,
                },
            )

        selected_dates = [
            selected_start + timedelta(days=index)
            for index in range(period_days)
        ]
        previous_dates = [
            previous_start + timedelta(days=index)
            for index in range(period_days)
        ]
        trend_dates = [
            trend_start + timedelta(days=index)
            for index in range((trend_end - trend_start).days)
        ]

        result: list[dict[str, Any]] = []
        for definition in self.KPI_DEFINITIONS:
            key = definition["key"]

            current = float(
                sum(float(row_for(day).get(key) or 0) for day in selected_dates)
            )
            previous = float(
                sum(float(row_for(day).get(key) or 0) for day in previous_dates)
            )

            trend = [
                float(row_for(day).get(key) or 0)
                for day in trend_dates
            ]

            if period_days > 1:
                rolling_average = round(current / period_days, 1)
            else:
                seven_day_dates = [
                    selected_start - timedelta(days=offset)
                    for offset in range(6, -1, -1)
                ]
                seven_day_values = [
                    float(row_for(day).get(key) or 0)
                    for day in seven_day_dates
                ]
                rolling_average = round(
                    sum(seven_day_values) / len(seven_day_values),
                    1,
                )

            delta_value = round(current - previous, 1)
            delta_percent = (
                round((current - previous) / abs(previous) * 100.0, 1)
                if previous != 0
                else (100.0 if current > 0 else 0.0)
            )
            forecast = self._forecast(trend)
            direction = (
                "up"
                if delta_value > 0
                else "down"
                if delta_value < 0
                else "stable"
            )
            tone = self._tone(direction, definition["better_when"])

            result.append(
                {
                    **definition,
                    "value": current,
                    "previous_value": previous,
                    "delta_value": delta_value,
                    "delta_percent": delta_percent,
                    "direction": direction,
                    "tone": tone,
                    "rolling_average": rolling_average,
                    "trend": trend,
                    "trend_dates": [day.isoformat() for day in trend_dates],
                    "forecast": forecast,
                    "forecast_confidence": self._confidence(trend),
                    "explanation": self._explanation(
                        label=definition["label"],
                        current=current,
                        previous=previous,
                        rolling_average=rolling_average,
                        direction=direction,
                        better_when=definition["better_when"],
                        period_days=period_days,
                    ),
                }
            )

        return result

    def _daily_rows(
        self,
        start_date: date,
        end_date: date,
        *,
        facility_id: str | None,
        customer_id: str | None,
        carrier_id: str | None,
        appointment_type: str | None,
    ) -> list[dict[str, Any]]:
        sla_met = completed_sla_met_sql("appointment")
        sla_missed = completed_sla_missed_sql("appointment")
        recommendation_used = recommendation_used_exists_sql("appointment")

        rows = self.repository.db.execute(
            text(
                """
                SELECT
                    DATE(appointment.scheduled_time) AS operation_date,
                    COUNT(*) AS appointments,
                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                    ) AS late_arrivals,
                    COUNT(*) FILTER (
                        WHERE ({sla_missed})
                    ) AS sla_misses,
                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                          AND ({sla_met})
                    ) AS late_turns_recovered,
                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                          AND ({sla_met})
                          AND ({recommendation_used})
                    ) AS recovered_by_actions
                FROM public.appointments AS appointment
                WHERE appointment.appt_id LIKE 'DEMO%%'
                  AND appointment.scheduled_time >= :start_date
                  AND appointment.scheduled_time < :end_date
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                  AND (
                      CAST(:customer_id AS VARCHAR) IS NULL
                      OR appointment.customer_id = CAST(:customer_id AS VARCHAR)
                  )
                  AND (
                      CAST(:carrier_id AS VARCHAR) IS NULL
                      OR appointment.carrier_id = CAST(:carrier_id AS VARCHAR)
                  )
                  AND (
                      CAST(:appointment_type AS VARCHAR) IS NULL
                      OR LOWER(appointment.appointment_type) =
                         LOWER(CAST(:appointment_type AS VARCHAR))
                  )
                GROUP BY DATE(appointment.scheduled_time)
                ORDER BY operation_date;
                """.format(
                    sla_met=sla_met,
                    sla_missed=sla_missed,
                    recommendation_used=recommendation_used,
                )
            ),
            {
                "start_date": start_date,
                "end_date": end_date,
                "facility_id": facility_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "appointment_type": appointment_type,
            },
        ).mappings().all()

        return [dict(row) for row in rows]

    @staticmethod
    def _forecast(values: list[float]) -> float:
        recent = values[-7:]
        if not recent:
            return 0.0
        weighted = sum((index + 1) * value for index, value in enumerate(recent))
        denominator = sum(range(1, len(recent) + 1))
        baseline = weighted / denominator
        momentum = (recent[-1] - recent[0]) / max(1, len(recent) - 1)
        return round(max(0.0, baseline + momentum), 1)

    @staticmethod
    def _confidence(values: list[float]) -> int:
        recent = values[-7:]
        if len(recent) < 2:
            return 70
        average = sum(recent) / len(recent)
        spread = sum(abs(value - average) for value in recent) / len(recent)
        relative_spread = spread / max(1.0, average)
        return max(55, min(96, round(94 - relative_spread * 45)))

    @staticmethod
    def _tone(direction: str, better_when: str) -> str:
        if direction == "stable" or better_when == "neutral":
            return "neutral"
        improved = (better_when == "up" and direction == "up") or (
            better_when == "down" and direction == "down"
        )
        return "positive" if improved else "negative"

    @staticmethod
    def _explanation(
        *,
        label: str,
        current: float,
        previous: float,
        rolling_average: float,
        direction: str,
        better_when: str,
        period_days: int,
    ) -> str:
        period_label = (
            "the selected day"
            if period_days == 1
            else f"the selected {period_days}-day window"
        )
        comparison_label = (
            "the previous day"
            if period_days == 1
            else "the immediately preceding period"
        )
        average_label = (
            "seven-day average"
            if period_days == 1
            else "daily average"
        )

        if direction == "stable":
            return (
                f"{label} is unchanged versus {comparison_label}. "
                f"For {period_label}, the {average_label} is "
                f"{rolling_average:g}."
            )

        change = abs(current - previous)
        outcome = "improved" if (
            (better_when == "up" and direction == "up")
            or (better_when == "down" and direction == "down")
        ) else "needs attention"
        return (
            f"{label} moved {direction} by {change:g} versus "
            f"{comparison_label}. The selected-period value is {current:g}, "
            f"with a {average_label} of {rolling_average:g}; "
            f"the trend {outcome}."
        )
