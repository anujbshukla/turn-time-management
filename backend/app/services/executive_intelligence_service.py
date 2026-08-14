from __future__ import annotations

from typing import Any


class ExecutiveIntelligenceService:
    """Build an explainable executive view from the live dashboard payload."""

    def build(self, dashboard: dict[str, Any]) -> dict[str, Any]:
        summary = dashboard.get("summary", {})
        risks = dashboard.get("risk_distribution", [])
        high_risk = dashboard.get("high_risk_appointments", [])
        savings = dashboard.get("recommendation_savings", {})
        recovery_plans = dashboard.get("recovery_plan_performance", [])

        total = int(summary.get("total_appointments") or 0)
        completed = int(summary.get("completed") or 0)
        misses = int(summary.get("sla_misses") or 0)
        late = int(summary.get("late_arrivals") or 0)
        recovered = int(summary.get("late_turned_on_time") or 0)

        critical = self._risk_count(risks, "critical")
        high = self._risk_count(risks, "high")

        completed_base = max(1, completed)
        total_base = max(1, total)
        late_base = max(1, late)

        sla_score = max(0.0, 100.0 - (misses / completed_base * 100.0))
        arrival_score = max(0.0, 100.0 - (late / total_base * 100.0))
        recovery_score = min(100.0, recovered / late_base * 100.0) if late else 100.0
        risk_score = max(0.0, 100.0 - ((critical * 1.8 + high * 0.8) / total_base * 100.0))
        recommendation_score = self._recommendation_score(recovery_plans)

        score = round(
            sla_score * 0.30
            + arrival_score * 0.20
            + recovery_score * 0.20
            + risk_score * 0.20
            + recommendation_score * 0.10
        )
        score = max(0, min(100, score))
        status, tone = self._status(score)

        net_savings = float(savings.get("net_savings") or 0)
        detention_exposure = float(summary.get("detention_exposure") or 0)
        predicted_misses = sum(
            1 for row in high_risk if bool(row.get("predicted_missed"))
        )

        top_priorities = [
            {
                "appt_id": row.get("appt_id"),
                "title": self._priority_title(row),
                "reason": self._priority_reason(row),
                "risk_score": round(float(row.get("turn_risk_score") or 0), 1),
                "estimated_savings": float(row.get("estimated_savings") or 0),
                "severity": self._severity(float(row.get("turn_risk_score") or 0)),
            }
            for row in high_risk[:3]
        ]

        briefing = self._briefing(
            status=status,
            total=total,
            critical=critical,
            predicted_misses=predicted_misses,
            net_savings=net_savings,
            detention_exposure=detention_exposure,
            top_priorities=top_priorities,
        )

        return {
            "health_score": score,
            "health_status": status,
            "health_tone": tone,
            "briefing": briefing,
            "top_priorities": top_priorities,
            "indicators": [
                {"label": "SLA compliance", "score": round(sla_score)},
                {"label": "Arrival reliability", "score": round(arrival_score)},
                {"label": "Recovery performance", "score": round(recovery_score)},
                {"label": "Portfolio risk", "score": round(risk_score)},
                {"label": "AI action effectiveness", "score": round(recommendation_score)},
            ],
            "headline_metrics": {
                "critical_appointments": critical,
                "predicted_sla_misses": predicted_misses,
                "net_ai_savings": net_savings,
                "detention_exposure": detention_exposure,
            },
        }

    @staticmethod
    def _risk_count(rows: list[dict[str, Any]], level: str) -> int:
        return int(next(
            (
                row.get("appointment_count") or 0
                for row in rows
                if str(row.get("risk_level", "")).lower() == level
            ),
            0,
        ))

    @staticmethod
    def _recommendation_score(rows: list[dict[str, Any]]) -> float:
        weighted_success = 0.0
        uses = 0
        for row in rows:
            times_used = int(row.get("times_used") or 0)
            success_rate = float(row.get("success_rate") or 0)
            weighted_success += success_rate * times_used
            uses += times_used
        return weighted_success / uses if uses else 75.0

    @staticmethod
    def _status(score: int) -> tuple[str, str]:
        if score >= 90:
            return "Excellent", "positive"
        if score >= 78:
            return "Good", "stable"
        if score >= 65:
            return "Watch", "warning"
        return "Critical", "critical"

    @staticmethod
    def _severity(risk_score: float) -> str:
        if risk_score >= 80:
            return "Critical"
        if risk_score >= 60:
            return "High"
        return "Medium"

    @staticmethod
    def _priority_title(row: dict[str, Any]) -> str:
        action = row.get("recommended_action")
        if action:
            return str(action)
        dock = row.get("dock_name") or row.get("assigned_dock")
        return f"Protect the SLA{f' at {dock}' if dock else ''}"

    @staticmethod
    def _priority_reason(row: dict[str, Any]) -> str:
        pieces: list[str] = []
        delay = float(row.get("actual_arrival_delay_minutes") or 0)
        if delay > 0:
            pieces.append(f"{delay:.0f} min arrival delay")
        probability = row.get("sla_recovery_probability")
        if probability is not None:
            pieces.append(f"{float(probability):.0f}% recovery probability")
        if bool(row.get("predicted_missed")):
            pieces.append("predicted SLA miss")
        return " · ".join(pieces) or "Elevated turn-risk score"

    @staticmethod
    def _briefing(
        *,
        status: str,
        total: int,
        critical: int,
        predicted_misses: int,
        net_savings: float,
        detention_exposure: float,
        top_priorities: list[dict[str, Any]],
    ) -> str:
        priority_text = (
            f" Immediate attention should start with {top_priorities[0]['appt_id']}."
            if top_priorities
            else " No immediate appointment escalation is required."
        )
        return (
            f"Warehouse health is {status.lower()}. The active portfolio contains "
            f"{total:,} appointments, including {critical} at critical risk and "
            f"{predicted_misses} predicted SLA misses. AI-supported recovery actions "
            f"have generated an estimated ${net_savings:,.0f} in net value, while "
            f"current detention exposure is ${detention_exposure:,.0f}."
            f"{priority_text}"
        )
