from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.repositories.dashboard_repository import DashboardRepository


class PredictiveTimelineService:
    """Build the next 8 hours of operational risk from scheduled appointments."""

    HORIZON_HOURS = 8

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository
        self.db = repository.db

    def build(self, facility_id: str | None = None) -> dict[str, Any]:
        now = datetime.now()
        horizon_end = now + timedelta(hours=self.HORIZON_HOURS)

        rows = self.db.execute(
            text(
                """
                WITH latest_prediction AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.predicted_delay_minutes,
                        prediction.predicted_duration_minutes,
                        prediction.sla_miss_probability,
                        prediction.turn_risk_score,
                        prediction.predicted_missed
                    FROM appointment_predictions AS prediction
                    ORDER BY prediction.appt_id, prediction.prediction_id DESC
                )
                SELECT
                    appointment.appt_id,
                    appointment.scheduled_time,
                    appointment.status,
                    appointment.assigned_dock_id,
                    appointment.sla_minutes,
                    appointment.detention_cost_per_hour,
                    appointment.customer_name,
                    facility.facility_id,
                    facility.facility_name,
                    dock.dock_name,
                    prediction.predicted_delay_minutes,
                    prediction.predicted_duration_minutes,
                    prediction.sla_miss_probability,
                    prediction.turn_risk_score,
                    prediction.predicted_missed
                FROM appointments AS appointment
                LEFT JOIN facilities AS facility
                  ON facility.facility_id = appointment.facility_id
                LEFT JOIN docks AS dock
                  ON dock.dock_id = appointment.assigned_dock_id
                LEFT JOIN latest_prediction AS prediction
                  ON prediction.appt_id = appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%%'
                  AND appointment.status NOT IN ('Cancelled', 'Completed')
                  AND appointment.scheduled_time >= :window_start
                  AND appointment.scheduled_time < :window_end
                  AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY appointment.scheduled_time;
                """
            ),
            {
                "window_start": now - timedelta(minutes=30),
                "window_end": horizon_end,
                "facility_id": facility_id,
            },
        ).mappings().all()

        buckets: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            row = dict(raw)
            scheduled = row["scheduled_time"]
            bucket = scheduled.replace(minute=0, second=0, microsecond=0)
            buckets[bucket].append(row)

        events: list[dict[str, Any]] = []
        cursor = now.replace(minute=0, second=0, microsecond=0)
        while cursor <= horizon_end:
            bucket_rows = buckets.get(cursor, [])
            events.extend(self._build_bucket_events(cursor, bucket_rows))
            cursor += timedelta(hours=1)

        events.sort(key=lambda event: (event["forecast_time"], -event["priority_score"]))

        critical = sum(1 for event in events if event["severity"] == "Critical")
        high = sum(1 for event in events if event["severity"] == "High")
        exposure = sum(float(event["detention_exposure"] or 0) for event in events)

        return {
            "generated_at": now.isoformat(),
            "horizon_hours": self.HORIZON_HOURS,
            "facility_id": facility_id,
            "summary": {
                "forecast_events": len(events),
                "critical_events": critical,
                "high_events": high,
                "detention_exposure": round(exposure, 2),
                "appointments_in_window": len(rows),
            },
            "events": events,
        }

    def _build_bucket_events(
        self,
        bucket: datetime,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        risk_rows = [
            row
            for row in rows
            if self._percent(row.get("sla_miss_probability")) >= 50
            or float(row.get("turn_risk_score") or 0) >= 60
            or bool(row.get("predicted_missed"))
        ]
        critical_rows = [
            row
            for row in rows
            if self._percent(row.get("sla_miss_probability")) >= 75
            or float(row.get("turn_risk_score") or 0) >= 80
            or bool(row.get("predicted_missed"))
        ]

        dock_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            dock_counts[row.get("dock_name") or "Unassigned"] += 1
        busiest_dock, busiest_count = max(dock_counts.items(), key=lambda item: item[1])

        events: list[dict[str, Any]] = []
        if len(rows) >= 4:
            severity = "Critical" if len(rows) >= 8 else "High" if len(rows) >= 6 else "Warning"
            events.append(
                self._event(
                    bucket,
                    "APPOINTMENT_SURGE",
                    severity,
                    f"{len(rows)} appointments enter the operating window",
                    f"Volume is concentrated around {busiest_dock} ({busiest_count} appointment"
                    f"{'s' if busiest_count != 1 else ''}).",
                    rows,
                    "Pre-stage products and verify dock/labor readiness before the surge.",
                    priority=70 + min(len(rows) * 3, 25),
                )
            )

        if risk_rows:
            severity = "Critical" if critical_rows else "High"
            avg_probability = sum(
                self._percent(row.get("sla_miss_probability")) for row in risk_rows
            ) / len(risk_rows)
            events.append(
                self._event(
                    bucket,
                    "SLA_RISK_WINDOW",
                    severity,
                    f"{len(risk_rows)} appointment{'s' if len(risk_rows) != 1 else ''} forecast at SLA risk",
                    f"Average predicted SLA-miss probability is {avg_probability:.0f}%.",
                    risk_rows,
                    "Prioritize the highest-risk turns and run a recovery What-If before execution.",
                    priority=92 if critical_rows else 82,
                )
            )

        if busiest_count >= 3 and busiest_dock != "Unassigned":
            severity = "Critical" if busiest_count >= 6 else "High" if busiest_count >= 4 else "Warning"
            affected = [row for row in rows if (row.get("dock_name") or "Unassigned") == busiest_dock]
            events.append(
                self._event(
                    bucket,
                    "DOCK_CONGESTION",
                    severity,
                    f"{busiest_dock} predicted to become congested",
                    f"{busiest_count} appointments are concentrated at the dock in this hour.",
                    affected,
                    f"Evaluate reassignment from {busiest_dock} to a lower-load compatible dock.",
                    priority=88 if severity == "Critical" else 76,
                )
            )

        detention_rows = [
            row
            for row in risk_rows
            if float(row.get("detention_cost_per_hour") or 0) > 0
        ]
        if detention_rows:
            exposure = sum(
                float(row.get("detention_cost_per_hour") or 0)
                * max(
                    0.25,
                    float(row.get("predicted_delay_minutes") or 0) / 60,
                )
                for row in detention_rows
            )
            if exposure >= 100:
                severity = "Critical" if exposure >= 1000 else "High" if exposure >= 500 else "Warning"
                events.append(
                    self._event(
                        bucket,
                        "DETENTION_EXPOSURE",
                        severity,
                        f"${exposure:,.0f} detention exposure forecast",
                        f"{len(detention_rows)} at-risk appointment"
                        f"{'s' if len(detention_rows) != 1 else ''} contribute to the projected cost.",
                        detention_rows,
                        "Recover the highest-cost appointment first and validate dock capacity.",
                        priority=90 if severity == "Critical" else 78,
                        detention_exposure=exposure,
                    )
                )

        return events

    def _event(
        self,
        bucket: datetime,
        event_type: str,
        severity: str,
        title: str,
        description: str,
        rows: list[dict[str, Any]],
        recommendation: str,
        *,
        priority: int,
        detention_exposure: float = 0,
    ) -> dict[str, Any]:
        ranked = sorted(
            rows,
            key=lambda row: (
                float(row.get("turn_risk_score") or 0),
                self._percent(row.get("sla_miss_probability")),
            ),
            reverse=True,
        )
        top = ranked[0] if ranked else {}
        appointment_ids = [str(row["appt_id"]) for row in ranked[:8]]

        return {
            "event_id": f"{event_type.lower()}-{bucket.strftime('%Y%m%d%H')}-{top.get('facility_id') or 'all'}",
            "event_type": event_type,
            "forecast_time": bucket.isoformat(),
            "severity": severity,
            "priority_score": priority,
            "title": title,
            "description": description,
            "facility_id": top.get("facility_id"),
            "facility_name": top.get("facility_name"),
            "dock_name": top.get("dock_name"),
            "impacted_appointment_count": len(rows),
            "appointment_ids": appointment_ids,
            "primary_appointment_id": top.get("appt_id"),
            "detention_exposure": round(detention_exposure, 2),
            "recommended_action": recommendation,
            "confidence": self._confidence(rows),
        }

    def _confidence(self, rows: list[dict[str, Any]]) -> int:
        predicted = sum(
            1
            for row in rows
            if row.get("turn_risk_score") is not None
            or row.get("sla_miss_probability") is not None
        )
        if not rows:
            return 0
        coverage = predicted / len(rows)
        return round(70 + (coverage * 25))

    @staticmethod
    def _percent(value: Any) -> float:
        numeric = float(value or 0)
        return numeric * 100 if 0 <= numeric <= 1 else numeric
