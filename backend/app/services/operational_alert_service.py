from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class OperationalAlertService:
    """Build deterministic, dashboard-grounded operational alerts.

    Alerts are derived from the same normalized dashboard payload used by the
    control tower, so counts and appointment IDs remain consistent with the
    visible KPI cards and risk tables.
    """

    def build(self, dashboard: dict[str, Any]) -> list[dict[str, Any]]:
        generated_at = datetime.now(timezone.utc).isoformat()
        alerts: list[dict[str, Any]] = []

        summary = dashboard.get("summary", {})
        high_risk = dashboard.get("high_risk_appointments", [])
        delay_reasons = dashboard.get("delay_sla_reasons", [])
        risk_distribution = dashboard.get("risk_distribution", [])
        savings = dashboard.get("recommendation_savings", {})

        critical_count = next(
            (
                int(row.get("appointment_count") or 0)
                for row in risk_distribution
                if str(row.get("risk_level", "")).casefold() == "critical"
            ),
            0,
        )
        critical_ids = [
            str(row["appt_id"])
            for row in high_risk
            if float(row.get("turn_risk_score") or 0) >= 80
        ][:25]

        if critical_count:
            alerts.append(
                self._alert(
                    alert_id="sla-critical-risk",
                    severity="Critical" if critical_count >= 10 else "High",
                    category="SLA Risk",
                    title=f"{critical_count} appointments require immediate SLA attention",
                    description=(
                        "ML scoring identifies appointments with Critical turn risk. "
                        "Review the queue and apply recovery actions before execution."
                    ),
                    impacted_count=critical_count,
                    financial_exposure=float(summary.get("detention_exposure") or 0),
                    generated_at=generated_at,
                    appointment_ids=critical_ids,
                    risk_level="Critical",
                    recommended_action="Prioritize the highest-risk appointments and run a recovery scenario.",
                )
            )

        predicted_misses = sum(
            1 for row in high_risk if bool(row.get("predicted_missed"))
        )
        predicted_ids = [
            str(row["appt_id"])
            for row in high_risk
            if bool(row.get("predicted_missed"))
        ][:25]
        if predicted_misses:
            alerts.append(
                self._alert(
                    alert_id="predicted-sla-misses",
                    severity="High",
                    category="SLA Risk",
                    title=f"{predicted_misses} scored appointments are predicted to miss SLA",
                    description=(
                        "Predicted duration, arrival delay and current operating conditions "
                        "place these appointments outside their target SLA."
                    ),
                    impacted_count=predicted_misses,
                    financial_exposure=float(summary.get("detention_exposure") or 0),
                    generated_at=generated_at,
                    appointment_ids=predicted_ids,
                    risk_level="High",
                    recommended_action="Open the highest-risk appointment or simulate additional labor and equipment.",
                )
            )

        if delay_reasons:
            leader = max(
                delay_reasons,
                key=lambda row: (
                    int(row.get("sla_misses") or 0),
                    int(row.get("late_appointments") or 0),
                ),
            )
            cause = str(leader.get("reason") or "Operational variance")
            affected = max(
                int(leader.get("late_appointments") or 0),
                int(leader.get("sla_misses") or 0),
            )
            category = self._category_for_cause(cause)
            if affected:
                alerts.append(
                    self._alert(
                        alert_id=f"delay-cause-{self._slug(cause)}",
                        severity="High" if int(leader.get("sla_misses") or 0) > 0 else "Warning",
                        category=category,
                        title=f"{cause} is the leading operational disruption",
                        description=(
                            f"{affected} appointments are affected. Average delay is "
                            f"{float(leader.get('average_delay_minutes') or 0):.0f} minutes; "
                            f"the most affected dock is {leader.get('most_affected_dock') or 'unassigned'}."
                        ),
                        impacted_count=affected,
                        financial_exposure=0.0,
                        generated_at=generated_at,
                        appointment_ids=[],
                        recommended_action="Review the impacted operating area and rebalance the next available recovery resources.",
                    )
                )

        detention = float(summary.get("detention_exposure") or 0)
        if detention > 0:
            alerts.append(
                self._alert(
                    alert_id="detention-exposure",
                    severity="Critical" if detention >= 10000 else "High" if detention >= 5000 else "Warning",
                    category="Detention Exposure",
                    title=f"Detention exposure has reached ${detention:,.0f}",
                    description=(
                        "Completed and projected turns beyond SLA are accumulating financial exposure. "
                        "Accepted recovery actions can reduce the remaining risk."
                    ),
                    impacted_count=int(summary.get("sla_misses") or 0),
                    financial_exposure=detention,
                    generated_at=generated_at,
                    appointment_ids=predicted_ids,
                    recommended_action="Prioritize recommendations with the highest net savings and recovery probability.",
                )
            )

        net_savings = float(savings.get("net_savings") or 0)
        pending_recovery = max(0, int(summary.get("late_arrivals") or 0) - int(summary.get("late_turned_on_time") or 0))
        if pending_recovery > 0:
            alerts.append(
                self._alert(
                    alert_id="recovery-opportunity",
                    severity="Warning",
                    category="Resource Constraint",
                    title=f"{pending_recovery} late arrivals remain unrecovered",
                    description=(
                        f"Current accepted recommendations have generated ${net_savings:,.0f} in net savings, "
                        "but additional recovery opportunities remain."
                    ),
                    impacted_count=pending_recovery,
                    financial_exposure=detention,
                    generated_at=generated_at,
                    appointment_ids=predicted_ids,
                    recommended_action="Run What-If with one additional loader and forklift to identify recoverable turns.",
                )
            )

        severity_order = {"Critical": 0, "High": 1, "Warning": 2, "Info": 3}
        alerts.sort(
            key=lambda row: (
                severity_order.get(str(row["severity"]), 9),
                -int(row["impacted_appointment_count"]),
            )
        )
        return alerts

    @staticmethod
    def _alert(
        *,
        alert_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        impacted_count: int,
        financial_exposure: float,
        generated_at: str,
        appointment_ids: list[str],
        recommended_action: str,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        return {
            "alert_id": alert_id,
            "severity": severity,
            "category": category,
            "title": title,
            "description": description,
            "status": "Active",
            "impacted_appointment_count": impacted_count,
            "estimated_financial_exposure": round(financial_exposure, 2),
            "generated_at": generated_at,
            "appointment_ids": appointment_ids,
            "highest_priority_appointment_id": appointment_ids[0] if appointment_ids else None,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
        }

    @staticmethod
    def _category_for_cause(cause: str) -> str:
        normalized = cause.casefold()
        if "dock" in normalized:
            return "Dock Congestion"
        if "carrier" in normalized or "traffic" in normalized:
            return "Carrier Delay"
        if "loading" in normalized:
            return "Resource Constraint"
        if "weather" in normalized:
            return "Facility Capacity"
        return "Operational Variance"

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join("".join(character if character.isalnum() else " " for character in value.casefold()).split())
