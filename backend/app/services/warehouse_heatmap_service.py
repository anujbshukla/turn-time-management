from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.repositories.dashboard_repository import DashboardRepository


class WarehouseHeatmapService:
    """Build a dock-level operational risk map from current warehouse data."""

    DOCK_APPOINTMENT_CAPACITY = 8

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository
        self.db = repository.db

    def build(self, facility_id: str | None = None) -> dict[str, Any]:
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
                ),
                latest_recommendation AS (
                    SELECT DISTINCT ON (recommendation.appt_id)
                        recommendation.appt_id,
                        recommendation.recommended_action,
                        recommendation.estimated_savings,
                        recommendation.status
                    FROM appointment_recommendations AS recommendation
                    ORDER BY recommendation.appt_id, recommendation.created_at DESC
                )
                SELECT
                    facility.facility_id,
                    facility.facility_name,
                    dock.dock_id,
                    dock.dock_name,
                    dock.dock_type,
                    dock.temperature_zone,
                    dock.active AS dock_active,
                    appointment.appt_id,
                    appointment.status,
                    appointment.scheduled_time,
                    appointment.sla_minutes,
                    appointment.detention_cost_per_hour,
                    appointment.actual_arrival_delay_minutes,
                    prediction.predicted_delay_minutes,
                    prediction.predicted_duration_minutes,
                    prediction.sla_miss_probability,
                    prediction.turn_risk_score,
                    prediction.predicted_missed,
                    recommendation.recommended_action,
                    recommendation.estimated_savings,
                    recommendation.status AS recommendation_status
                FROM docks AS dock
                JOIN facilities AS facility
                  ON facility.facility_id = dock.facility_id
                LEFT JOIN appointments AS appointment
                  ON appointment.assigned_dock_id = dock.dock_id
                 AND appointment.appt_id LIKE 'DEMO%'
                 AND appointment.status NOT IN ('Cancelled')
                LEFT JOIN latest_prediction AS prediction
                  ON prediction.appt_id = appointment.appt_id
                LEFT JOIN latest_recommendation AS recommendation
                  ON recommendation.appt_id = appointment.appt_id
                WHERE facility.active = TRUE
                  AND (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR facility.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY facility.facility_name, dock.dock_name, appointment.scheduled_time;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        by_dock: dict[str, list[dict[str, Any]]] = defaultdict(list)
        dock_metadata: dict[str, dict[str, Any]] = {}

        for raw in rows:
            row = dict(raw)
            dock_id = str(row["dock_id"])
            dock_metadata[dock_id] = row
            if row.get("appt_id"):
                by_dock[dock_id].append(row)

        docks = [
            self._build_dock(dock_metadata[dock_id], by_dock.get(dock_id, []))
            for dock_id in dock_metadata
        ]
        docks.sort(key=lambda item: (item["facility_name"], item["sequence"]))

        facilities: list[dict[str, Any]] = []
        facility_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for dock in docks:
            facility_groups[dock["facility_id"]].append(dock)

        for current_facility_id, facility_docks in facility_groups.items():
            risk_score = round(
                sum(float(dock["risk_score"]) for dock in facility_docks)
                / max(1, len(facility_docks)),
                1,
            )
            facilities.append(
                {
                    "facility_id": current_facility_id,
                    "facility_name": facility_docks[0]["facility_name"],
                    "dock_count": len(facility_docks),
                    "critical_docks": sum(
                        1 for dock in facility_docks if dock["health"] == "Critical"
                    ),
                    "high_docks": sum(
                        1 for dock in facility_docks if dock["health"] == "High"
                    ),
                    "average_utilization": round(
                        sum(float(dock["utilization_percent"]) for dock in facility_docks)
                        / max(1, len(facility_docks)),
                        1,
                    ),
                    "risk_score": risk_score,
                    "health": self._health(risk_score),
                    "detention_exposure": round(
                        sum(float(dock["detention_exposure"]) for dock in facility_docks),
                        2,
                    ),
                }
            )

        facilities.sort(key=lambda item: item["risk_score"], reverse=True)
        return {
            "generated_at": self.db.execute(text("SELECT NOW()" )).scalar_one(),
            "facilities": facilities,
            "docks": docks,
            "legend": [
                {"health": "Healthy", "minimum": 0, "maximum": 29},
                {"health": "Watch", "minimum": 30, "maximum": 54},
                {"health": "High", "minimum": 55, "maximum": 74},
                {"health": "Critical", "minimum": 75, "maximum": 100},
            ],
        }

    def _build_dock(
        self,
        metadata: dict[str, Any],
        appointments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        active = [
            row
            for row in appointments
            if row.get("status")
            not in {"Completed", "Cancelled"}
        ]
        queue = [
            row
            for row in active
            if row.get("status") in {"Arrived", "Waiting", "En Route", "Scheduled"}
        ]
        in_progress = [
            row
            for row in active
            if row.get("status") in {"Dock Assigned", "In Progress"}
        ]
        utilization = min(
            100.0,
            round(len(active) / self.DOCK_APPOINTMENT_CAPACITY * 100, 1),
        )
        average_delay = round(
            sum(float(row.get("actual_arrival_delay_minutes") or row.get("predicted_delay_minutes") or 0) for row in active)
            / max(1, len(active)),
            1,
        )
        average_risk = round(
            sum(float(row.get("turn_risk_score") or 0) for row in active)
            / max(1, len(active)),
            1,
        )
        sla_risk_count = sum(
            1
            for row in active
            if bool(row.get("predicted_missed"))
            or self._percent(row.get("sla_miss_probability")) >= 50
        )
        detention_exposure = 0.0
        recovery_opportunity = 0.0
        recommended_actions: list[str] = []

        for row in active:
            predicted_turn = float(row.get("predicted_delay_minutes") or 0) + float(
                row.get("predicted_duration_minutes") or 0
            )
            sla = float(row.get("sla_minutes") or 120)
            rate = float(row.get("detention_cost_per_hour") or 0)
            detention_exposure += max(0.0, predicted_turn - sla) / 60 * rate
            recovery_opportunity += float(row.get("estimated_savings") or 0)
            action = row.get("recommended_action")
            if action and action not in recommended_actions:
                recommended_actions.append(str(action))

        queue_pressure = min(100.0, len(queue) / 5 * 100)
        sla_pressure = min(100.0, sla_risk_count / max(1, len(active)) * 100)
        delay_pressure = min(100.0, average_delay / 60 * 100)
        risk_score = round(
            utilization * 0.28
            + queue_pressure * 0.20
            + average_risk * 0.30
            + sla_pressure * 0.17
            + delay_pressure * 0.05,
            1,
        )
        risk_score = min(100.0, risk_score)

        highest_risk = max(
            active,
            key=lambda row: float(row.get("turn_risk_score") or 0),
            default=None,
        )
        health = "Inactive" if not bool(metadata.get("dock_active")) else self._health(risk_score)
        recommendation = self._recommendation(
            health=health,
            queue_length=len(queue),
            utilization=utilization,
            sla_risk_count=sla_risk_count,
            action=(recommended_actions[0] if recommended_actions else None),
        )

        return {
            "dock_id": metadata["dock_id"],
            "dock_name": metadata["dock_name"],
            "facility_id": metadata["facility_id"],
            "facility_name": metadata["facility_name"],
            "dock_type": metadata.get("dock_type") or "General",
            "temperature_zone": metadata.get("temperature_zone"),
            "active": bool(metadata.get("dock_active")),
            "zone": self._zone(metadata.get("dock_type")),
            "sequence": self._sequence(str(metadata.get("dock_name") or "")),
            "health": health,
            "risk_score": risk_score,
            "utilization_percent": utilization,
            "queue_length": len(queue),
            "active_appointments": len(active),
            "in_progress_appointments": len(in_progress),
            "average_delay_minutes": average_delay,
            "sla_risk_count": sla_risk_count,
            "detention_exposure": round(detention_exposure, 2),
            "recovery_opportunity": round(recovery_opportunity, 2),
            "predicted_congestion": risk_score >= 55 or utilization >= 75,
            "highest_risk_appointment_id": (
                highest_risk.get("appt_id") if highest_risk else None
            ),
            "recommended_action": recommendation,
        }

    @staticmethod
    def _percent(value: Any) -> float:
        numeric = float(value or 0)
        return numeric * 100 if 0 <= numeric <= 1 else numeric

    @staticmethod
    def _health(score: float) -> str:
        if score >= 75:
            return "Critical"
        if score >= 55:
            return "High"
        if score >= 30:
            return "Watch"
        return "Healthy"

    @staticmethod
    def _zone(dock_type: Any) -> str:
        value = str(dock_type or "").casefold()
        if "out" in value or "ship" in value:
            return "Shipping"
        if "in" in value or "receiv" in value:
            return "Receiving"
        if "cold" in value or "freez" in value:
            return "Cold Storage"
        return "Flexible"

    @staticmethod
    def _sequence(name: str) -> int:
        digits = "".join(character for character in name if character.isdigit())
        return int(digits) if digits else 9999

    @staticmethod
    def _recommendation(
        *,
        health: str,
        queue_length: int,
        utilization: float,
        sla_risk_count: int,
        action: str | None,
    ) -> str:
        if action:
            return action
        if health == "Critical":
            return "Rebalance appointments to a healthy dock and add temporary labor."
        if utilization >= 75:
            return "Move the next flexible appointment to a lower-utilization dock."
        if queue_length >= 3:
            return "Pre-stage loads and sequence the waiting queue by SLA urgency."
        if sla_risk_count > 0:
            return "Run a recovery What-If for the highest-risk appointment."
        return "No immediate intervention required."
