from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AiMissionService:
    """Build prioritized, actionable AI missions from operational intelligence.

    Missions intentionally reuse alerts, ML-scored appointments and recovery
    economics already present in the dashboard payload. This keeps every count,
    appointment ID and financial value aligned with the visible control tower.
    """

    def build(self, dashboard: dict[str, Any]) -> list[dict[str, Any]]:
        generated_at = datetime.now(timezone.utc).isoformat()
        alerts = dashboard.get("operational_alerts", [])
        high_risk = dashboard.get("high_risk_appointments", [])
        summary = dashboard.get("summary", {})
        savings = dashboard.get("recommendation_savings", {})
        delay_reasons = dashboard.get("delay_sla_reasons", [])

        missions: list[dict[str, Any]] = []

        critical_rows = [
            row
            for row in high_risk
            if float(row.get("turn_risk_score") or 0) >= 80
        ]
        if critical_rows:
            appointment_ids = [str(row["appt_id"]) for row in critical_rows[:20]]
            projected_savings = sum(
                float(row.get("estimated_savings") or 0)
                for row in critical_rows
            )
            recovery_values = [
                float(row.get("sla_recovery_probability") or 0)
                for row in critical_rows
                if row.get("sla_recovery_probability") is not None
            ]
            recovery_probability = (
                round(sum(recovery_values) / len(recovery_values), 1)
                if recovery_values
                else 0.0
            )
            missions.append(
                self._mission(
                    mission_id="recover-critical-appointments",
                    severity="Critical",
                    category="SLA Recovery",
                    title=f"Recover {len(critical_rows)} Critical appointments",
                    objective=(
                        "Prioritize the highest-risk turns and execute the recommended "
                        "dock, labor and sequencing actions before SLA exposure increases."
                    ),
                    priority_score=100,
                    impacted_count=len(critical_rows),
                    appointment_ids=appointment_ids,
                    projected_minutes_saved=sum(
                        max(
                            0.0,
                            float(row.get("predicted_duration_minutes") or 0)
                            - 90.0,
                        )
                        for row in critical_rows
                    ),
                    financial_benefit=projected_savings,
                    recovery_probability=recovery_probability,
                    generated_at=generated_at,
                    recommended_actions=self._recommended_actions(critical_rows),
                    alert_ids=self._matching_alert_ids(alerts, "SLA Risk"),
                )
            )

        detention = float(summary.get("detention_exposure") or 0)
        if detention > 0:
            predicted_rows = [
                row for row in high_risk if bool(row.get("predicted_missed"))
            ]
            appointment_ids = [str(row["appt_id"]) for row in predicted_rows[:20]]
            net_savings = float(savings.get("net_savings") or 0)
            missions.append(
                self._mission(
                    mission_id="reduce-detention-exposure",
                    severity="High" if detention < 10000 else "Critical",
                    category="Financial Recovery",
                    title=f"Reduce ${detention:,.0f} in detention exposure",
                    objective=(
                        "Focus on predicted SLA misses with the highest detention rate "
                        "and accept recovery actions that produce positive net savings."
                    ),
                    priority_score=min(99, 70 + int(detention / 1000)),
                    impacted_count=max(
                        len(predicted_rows),
                        int(summary.get("sla_misses") or 0),
                    ),
                    appointment_ids=appointment_ids,
                    projected_minutes_saved=sum(
                        max(0.0, float(row.get("actual_arrival_delay_minutes") or 0))
                        for row in predicted_rows
                    ),
                    financial_benefit=max(net_savings, detention * 0.2),
                    recovery_probability=self._average_recovery_probability(predicted_rows),
                    generated_at=generated_at,
                    recommended_actions=[
                        "Prioritize actions with positive net savings",
                        "Open the highest detention-risk appointment",
                        "Run a labor and forklift recovery scenario",
                    ],
                    alert_ids=self._matching_alert_ids(alerts, "Detention Exposure"),
                )
            )

        pending_recovery = max(
            0,
            int(summary.get("late_arrivals") or 0)
            - int(summary.get("late_turned_on_time") or 0),
        )
        if pending_recovery:
            candidate_rows = high_risk[: min(20, pending_recovery)]
            missions.append(
                self._mission(
                    mission_id="recover-late-arrivals",
                    severity="High" if pending_recovery >= 10 else "Warning",
                    category="Turn Recovery",
                    title=f"Recover {pending_recovery} late arrivals",
                    objective=(
                        "Rebalance available docks and resources to return late arrivals "
                        "to an achievable SLA path."
                    ),
                    priority_score=min(94, 55 + pending_recovery),
                    impacted_count=pending_recovery,
                    appointment_ids=[str(row["appt_id"]) for row in candidate_rows],
                    projected_minutes_saved=pending_recovery * 12.0,
                    financial_benefit=max(
                        0.0,
                        float(savings.get("net_savings") or 0),
                    ),
                    recovery_probability=self._average_recovery_probability(candidate_rows),
                    generated_at=generated_at,
                    recommended_actions=[
                        "Assign the next available compatible dock",
                        "Add one loader to the highest-risk turn",
                        "Pre-stage products for the next inbound appointment",
                    ],
                    alert_ids=self._matching_alert_ids(alerts, "Resource Constraint"),
                )
            )

        if delay_reasons:
            leading_reason = max(
                delay_reasons,
                key=lambda row: (
                    int(row.get("sla_misses") or 0),
                    int(row.get("late_appointments") or 0),
                ),
            )
            affected = max(
                int(leading_reason.get("sla_misses") or 0),
                int(leading_reason.get("late_appointments") or 0),
            )
            if affected:
                reason = str(leading_reason.get("reason") or "Operational variance")
                missions.append(
                    self._mission(
                        mission_id=f"mitigate-{self._slug(reason)}",
                        severity="High" if int(leading_reason.get("sla_misses") or 0) else "Warning",
                        category="Root Cause Mitigation",
                        title=f"Mitigate {reason.lower()}",
                        objective=(
                            f"Address the leading operational cause affecting {affected} "
                            "appointments and reduce recurrence in the next execution window."
                        ),
                        priority_score=min(90, 45 + affected),
                        impacted_count=affected,
                        appointment_ids=[],
                        projected_minutes_saved=(
                            affected
                            * float(leading_reason.get("average_delay_minutes") or 0)
                            * 0.25
                        ),
                        financial_benefit=0.0,
                        recovery_probability=0.0,
                        generated_at=generated_at,
                        recommended_actions=[
                            f"Review {leading_reason.get('most_affected_dock') or 'the most affected dock'}",
                            "Rebalance the next available operational resources",
                            "Monitor the next three appointments for recurrence",
                        ],
                        alert_ids=[
                            str(alert.get("alert_id"))
                            for alert in alerts
                            if reason.casefold() in str(alert.get("title") or "").casefold()
                        ],
                    )
                )

        missions.sort(
            key=lambda mission: (
                -int(mission["priority_score"]),
                -float(mission["estimated_financial_benefit"]),
            )
        )
        return missions

    @staticmethod
    def _mission(
        *,
        mission_id: str,
        severity: str,
        category: str,
        title: str,
        objective: str,
        priority_score: int,
        impacted_count: int,
        appointment_ids: list[str],
        projected_minutes_saved: float,
        financial_benefit: float,
        recovery_probability: float,
        generated_at: str,
        recommended_actions: list[str],
        alert_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "mission_id": mission_id,
            "severity": severity,
            "category": category,
            "title": title,
            "objective": objective,
            "status": "Proposed",
            "priority_score": max(0, min(100, int(priority_score))),
            "impacted_appointment_count": max(0, int(impacted_count)),
            "appointment_ids": appointment_ids,
            "primary_appointment_id": appointment_ids[0] if appointment_ids else None,
            "projected_minutes_saved": round(max(0.0, projected_minutes_saved), 1),
            "estimated_financial_benefit": round(max(0.0, financial_benefit), 2),
            "recovery_probability": round(max(0.0, recovery_probability), 1),
            "generated_at": generated_at,
            "recommended_actions": recommended_actions[:5],
            "source_alert_ids": alert_ids,
        }

    @staticmethod
    def _recommended_actions(rows: list[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        for row in rows:
            action = str(row.get("recommended_action") or "").strip()
            if action and action not in actions:
                actions.append(action)
            if len(actions) == 3:
                break
        if not actions:
            actions = [
                "Open the highest-risk appointment",
                "Run a recovery What-If scenario",
                "Apply the highest-value recommendation",
            ]
        return actions

    @staticmethod
    def _average_recovery_probability(rows: list[dict[str, Any]]) -> float:
        values = [
            float(row.get("sla_recovery_probability") or 0)
            for row in rows
            if row.get("sla_recovery_probability") is not None
        ]
        return round(sum(values) / len(values), 1) if values else 0.0

    @staticmethod
    def _matching_alert_ids(alerts: list[dict[str, Any]], category: str) -> list[str]:
        return [
            str(alert.get("alert_id"))
            for alert in alerts
            if str(alert.get("category") or "").casefold() == category.casefold()
        ]

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(
            "".join(
                character if character.isalnum() else " "
                for character in value.casefold()
            ).split()
        )
