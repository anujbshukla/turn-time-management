from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.repositories.dashboard_repository import DashboardRepository


class OperationsFeedService:
    """Build a unified, read-only stream of warehouse operational activity."""

    MAX_DATABASE_EVENTS = 36
    MAX_FEED_ITEMS = 40

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository
        self.db = repository.db

    def build(
        self,
        dashboard: dict[str, Any],
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        items.extend(self._appointment_events(facility_id))
        items.extend(self._prediction_events(facility_id))
        items.extend(self._recommendation_events(facility_id))
        items.extend(self._alert_events(dashboard))
        items.extend(self._mission_events(dashboard))

        # De-duplicate records that describe the same event and order newest first.
        unique: dict[str, dict[str, Any]] = {}
        for item in items:
            unique[item["feed_id"]] = item

        ordered = sorted(
            unique.values(),
            key=lambda item: self._sort_time(item.get("occurred_at")),
            reverse=True,
        )
        return ordered[: self.MAX_FEED_ITEMS]

    def _appointment_events(
        self,
        facility_id: str | None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    event.event_id,
                    event.appt_id,
                    event.event_type,
                    event.event_time,
                    event.notes,
                    event.performed_by,
                    event.field_name,
                    event.old_value,
                    event.new_value,
                    event.details_json,
                    appointment.status,
                    appointment.customer_name,
                    facility.facility_name
                FROM appointment_events AS event
                JOIN appointments AS appointment
                  ON appointment.appt_id = event.appt_id
                LEFT JOIN facilities AS facility
                  ON facility.facility_id = appointment.facility_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY event.event_time DESC, event.event_id DESC
                LIMIT :limit;
                """
            ),
            {
                "facility_id": facility_id,
                "limit": self.MAX_DATABASE_EVENTS,
            },
        ).mappings().all()

        return [self._map_appointment_event(dict(row)) for row in rows]

    def _prediction_events(
        self,
        facility_id: str | None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    prediction.prediction_id,
                    prediction.appt_id,
                    prediction.generated_at,
                    prediction.turn_risk_score,
                    prediction.sla_miss_probability,
                    prediction.predicted_duration_minutes,
                    prediction.predicted_missed,
                    appointment.customer_name,
                    facility.facility_name
                FROM appointment_predictions AS prediction
                JOIN appointments AS appointment
                  ON appointment.appt_id = prediction.appt_id
                LEFT JOIN facilities AS facility
                  ON facility.facility_id = appointment.facility_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY prediction.generated_at DESC, prediction.prediction_id DESC
                LIMIT 10;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        events: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            risk_score = float(row.get("turn_risk_score") or 0)
            probability = self._as_percent(row.get("sla_miss_probability"))
            severity = (
                "Critical"
                if risk_score >= 80
                else "High"
                if risk_score >= 60
                else "Warning"
                if risk_score >= 30
                else "Info"
            )
            events.append(
                {
                    "feed_id": f"prediction-{row['prediction_id']}",
                    "category": "AI Decisions",
                    "event_type": "PREDICTION_UPDATED",
                    "title": f"Risk prediction updated for {row['appt_id']}",
                    "description": (
                        f"Risk score {risk_score:.0f}/100 · "
                        f"SLA miss probability {probability:.0f}% · "
                        f"Predicted turn {int(row.get('predicted_duration_minutes') or 0)} min."
                    ),
                    "occurred_at": row["generated_at"],
                    "appointment_id": row["appt_id"],
                    "facility_name": row.get("facility_name"),
                    "severity": severity,
                    "actor": "ML Prediction Engine",
                    "old_value": None,
                    "new_value": f"{risk_score:.0f} risk",
                    "details": {
                        "risk_score": risk_score,
                        "sla_miss_probability": probability,
                        "predicted_missed": bool(row.get("predicted_missed")),
                    },
                    "action": "open_appointment",
                }
            )
        return events

    def _recommendation_events(
        self,
        facility_id: str | None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    recommendation.recommendation_id,
                    recommendation.appt_id,
                    recommendation.recommended_action,
                    recommendation.estimated_savings,
                    recommendation.status,
                    recommendation.created_at,
                    facility.facility_name
                FROM appointment_recommendations AS recommendation
                JOIN appointments AS appointment
                  ON appointment.appt_id = recommendation.appt_id
                LEFT JOIN facilities AS facility
                  ON facility.facility_id = appointment.facility_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY recommendation.created_at DESC,
                         recommendation.recommendation_id DESC
                LIMIT 10;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        events: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            status = str(row.get("status") or "Pending")
            savings = float(row.get("estimated_savings") or 0)
            if status == "Accepted":
                event_type = "RECOMMENDATION_ACCEPTED"
                title = f"Recovery recommendation accepted for {row['appt_id']}"
                severity = "Info"
            elif status == "Rejected":
                event_type = "RECOMMENDATION_REJECTED"
                title = f"Recovery recommendation rejected for {row['appt_id']}"
                severity = "Warning"
            else:
                event_type = "RECOMMENDATION_GENERATED"
                title = f"AI recovery plan generated for {row['appt_id']}"
                severity = "High" if savings > 0 else "Info"

            events.append(
                {
                    "feed_id": f"recommendation-{row['recommendation_id']}-{status}",
                    "category": "AI Decisions",
                    "event_type": event_type,
                    "title": title,
                    "description": (
                        f"{row.get('recommended_action') or 'Recovery action proposed'}"
                        + (f" · Estimated savings ${savings:,.0f}." if savings else ".")
                    ),
                    "occurred_at": row["created_at"],
                    "appointment_id": row["appt_id"],
                    "facility_name": row.get("facility_name"),
                    "severity": severity,
                    "actor": "Recommendation Engine",
                    "old_value": None,
                    "new_value": status,
                    "details": {
                        "recommendation_id": row["recommendation_id"],
                        "estimated_savings": savings,
                        "status": status,
                    },
                    "action": "open_appointment",
                }
            )
        return events

    def _alert_events(
        self,
        dashboard: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "feed_id": f"alert-{alert['alert_id']}",
                "category": "Alerts",
                "event_type": "ALERT_GENERATED",
                "title": alert["title"],
                "description": alert["description"],
                "occurred_at": alert["generated_at"],
                "appointment_id": alert.get("highest_priority_appointment_id"),
                "facility_name": None,
                "severity": alert["severity"],
                "actor": "Operational Alert Engine",
                "old_value": None,
                "new_value": f"{alert['impacted_appointment_count']} impacted",
                "details": {
                    "alert_id": alert["alert_id"],
                    "category": alert["category"],
                    "financial_exposure": alert["estimated_financial_exposure"],
                    "recommended_action": alert["recommended_action"],
                },
                "action": (
                    "open_appointment"
                    if alert.get("highest_priority_appointment_id")
                    else "filter_queue"
                ),
            }
            for alert in dashboard.get("operational_alerts", [])
        ]

    def _mission_events(
        self,
        dashboard: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "feed_id": f"mission-{mission['mission_id']}",
                "category": "Missions",
                "event_type": "MISSION_CREATED",
                "title": mission["title"],
                "description": mission["objective"],
                "occurred_at": mission["generated_at"],
                "appointment_id": mission.get("primary_appointment_id"),
                "facility_name": None,
                "severity": mission["severity"],
                "actor": "AI Mission Engine",
                "old_value": None,
                "new_value": f"Priority {mission['priority_score']}",
                "details": {
                    "mission_id": mission["mission_id"],
                    "projected_minutes_saved": mission["projected_minutes_saved"],
                    "estimated_financial_benefit": mission[
                        "estimated_financial_benefit"
                    ],
                    "recommended_actions": mission["recommended_actions"],
                },
                "action": (
                    "open_appointment"
                    if mission.get("primary_appointment_id")
                    else "run_what_if"
                ),
            }
            for mission in dashboard.get("ai_missions", [])
        ]

    def _map_appointment_event(
        self,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        event_type = str(row.get("event_type") or "APPOINTMENT_UPDATED").upper()
        title_map = {
            "APPOINTMENT_CREATED": "Appointment created",
            "APPOINTMENT_UPDATED": "Appointment details updated",
            "CARRIER_CHANGED": "Carrier assignment changed",
            "FACILITY_CHANGED": "Facility assignment changed",
            "DOCK_CHANGED": "Dock assignment changed",
            "SCHEDULE_CHANGED": "Appointment rescheduled",
            "ETA_CHANGED": "Estimated arrival updated",
            "STATUS_CHANGED": "Appointment status changed",
            "PRODUCT_ADDED": "Appointment product added",
            "PRODUCT_REMOVED": "Appointment product removed",
            "QUANTITY_CHANGED": "Product quantity changed",
            "PREDICTION_UPDATED": "ML prediction recalculated",
            "RECOMMENDATION_CREATED": "Recovery recommendation generated",
            "RECOMMENDATION_ACCEPTED": "Recovery recommendation accepted",
            "RECOMMENDATION_REJECTED": "Recovery recommendation rejected",
            "COMPLETED": "Appointment completed",
            "RECOVERED": "Appointment recovered within SLA",
            "SLA_MISSED": "Appointment missed SLA",
            "CANCELLED": "Appointment cancelled",
        }

        ai_types = {
            "PREDICTION_UPDATED",
            "RECOMMENDATION_CREATED",
            "RECOMMENDATION_ACCEPTED",
            "RECOMMENDATION_REJECTED",
        }
        operational_types = {
            "CARRIER_CHANGED",
            "FACILITY_CHANGED",
            "DOCK_CHANGED",
            "SCHEDULE_CHANGED",
            "ETA_CHANGED",
            "STATUS_CHANGED",
            "PRODUCT_ADDED",
            "PRODUCT_REMOVED",
            "QUANTITY_CHANGED",
        }
        critical_types = {"SLA_MISSED", "CANCELLED"}
        positive_types = {"COMPLETED", "RECOVERED", "RECOMMENDATION_ACCEPTED"}

        category = (
            "AI Decisions"
            if event_type in ai_types
            else "Operational Changes"
            if event_type in operational_types
            else "Appointments"
        )
        severity = (
            "Critical"
            if event_type in critical_types
            else "Info"
            if event_type in positive_types
            else "Warning"
            if event_type in {"STATUS_CHANGED", "RECOMMENDATION_REJECTED"}
            else "Info"
        )

        field_name = row.get("field_name")
        old_value = row.get("old_value")
        new_value = row.get("new_value")
        notes = row.get("notes")
        if field_name and (old_value is not None or new_value is not None):
            description = (
                f"{str(field_name).replace('_', ' ').title()}: "
                f"{old_value or '—'} → {new_value or '—'}."
            )
        else:
            description = notes or f"Operational activity recorded for {row['appt_id']}."

        return {
            "feed_id": f"appointment-event-{row['event_id']}",
            "category": category,
            "event_type": event_type,
            "title": f"{title_map.get(event_type, self._humanize(event_type))} · {row['appt_id']}",
            "description": description,
            "occurred_at": row["event_time"],
            "appointment_id": row["appt_id"],
            "facility_name": row.get("facility_name"),
            "severity": severity,
            "actor": row.get("performed_by") or "Warehouse Operations",
            "old_value": old_value,
            "new_value": new_value,
            "details": row.get("details_json") or {},
            "action": "open_appointment",
        }

    @staticmethod
    def _humanize(value: str) -> str:
        return value.replace("_", " ").strip().title()

    @staticmethod
    def _as_percent(value: Any) -> float:
        numeric = float(value or 0)
        return numeric * 100 if 0 <= numeric <= 1 else numeric

    @staticmethod
    def _sort_time(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError:
                pass
        return datetime.min
