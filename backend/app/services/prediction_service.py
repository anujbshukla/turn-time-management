from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class PredictionService:
    """Build explainable, deterministic operational forecasts from dashboard data.

    These forecasts intentionally use the application's existing risk scores,
    SLA probabilities and operational aggregates. This keeps the demo
    transparent and repeatable while preserving a clean boundary for a future
    machine-learning implementation.
    """

    RISK_ORDER = ("Critical", "High", "Medium", "Low")

    def build(self, dashboard: dict[str, Any]) -> dict[str, Any]:
        summary = dashboard.get("summary", {})
        high_risk = dashboard.get("high_risk_appointments", [])
        risk_distribution = dashboard.get("risk_distribution", [])
        delay_reasons = dashboard.get("delay_sla_reasons", [])
        trend = dashboard.get("daily_compliance_trend", [])

        predicted_misses = self._predicted_misses(summary, high_risk)
        recovery_probability = self._recovery_probability(summary, high_risk)
        detention_forecast = self._detention_forecast(summary, high_risk)
        congestion = self._congestion_forecast(high_risk)
        carrier_delay = self._carrier_delay_forecast(high_risk)
        turn_time = self._turn_time_forecast(summary, high_risk)
        top_reason = self._top_reason(delay_reasons)

        predictions = [
            {
                "key": "sla_misses",
                "label": "Expected SLA misses",
                "value": str(predicted_misses),
                "unit": "next 60 min",
                "confidence": self._confidence(88, len(high_risk)),
                "trend": "up" if predicted_misses > 0 else "stable",
                "primary_factor": top_reason or congestion["primary_factor"],
                "recommendation": self._sla_recommendation(high_risk),
                "tone": "critical" if predicted_misses >= 3 else "warning" if predicted_misses else "positive",
            },
            {
                "key": "congestion",
                "label": "Dock congestion",
                "value": congestion["value"],
                "unit": congestion["unit"],
                "confidence": congestion["confidence"],
                "trend": congestion["trend"],
                "primary_factor": congestion["primary_factor"],
                "recommendation": congestion["recommendation"],
                "tone": congestion["tone"],
            },
            {
                "key": "recovery_probability",
                "label": "Recovery probability",
                "value": f"{recovery_probability:.0f}%",
                "unit": "at-risk turns",
                "confidence": self._confidence(91, len(high_risk)),
                "trend": "up" if recovery_probability >= 75 else "down",
                "primary_factor": "Existing recovery capacity and accepted actions",
                "recommendation": "Prioritize the top three appointments before their SLA windows narrow.",
                "tone": "positive" if recovery_probability >= 80 else "warning",
            },
            {
                "key": "detention_cost",
                "label": "Expected detention cost",
                "value": f"${detention_forecast:,.0f}",
                "unit": "forecast exposure",
                "confidence": self._confidence(84, len(high_risk)),
                "trend": "down" if detention_forecast < float(summary.get("detention_exposure") or 0) else "up",
                "primary_factor": f"{predicted_misses} predicted SLA miss{'es' if predicted_misses != 1 else ''}",
                "recommendation": "Execute high-value recovery actions before overtime exposure begins.",
                "tone": "warning" if detention_forecast > 0 else "positive",
            },
            {
                "key": "turn_time",
                "label": "Turn time forecast",
                "value": f"{turn_time:.0f}",
                "unit": "minutes average",
                "confidence": self._confidence(86, len(high_risk)),
                "trend": "down" if turn_time <= float(summary.get("average_turn_time_minutes") or turn_time) else "up",
                "primary_factor": congestion["primary_factor"],
                "recommendation": "Use pre-staging for high-SKU appointments to reduce service duration.",
                "tone": "stable",
            },
            {
                "key": "carrier_delay",
                "label": "Carrier delay risk",
                "value": carrier_delay["value"],
                "unit": carrier_delay["unit"],
                "confidence": carrier_delay["confidence"],
                "trend": carrier_delay["trend"],
                "primary_factor": carrier_delay["primary_factor"],
                "recommendation": carrier_delay["recommendation"],
                "tone": carrier_delay["tone"],
            },
        ]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "forecast_window_minutes": 60,
            "narrative": self._narrative(
                predicted_misses,
                congestion,
                recovery_probability,
                detention_forecast,
                high_risk,
            ),
            "predictions": predictions,
            "risk_matrix": self._risk_matrix(risk_distribution),
            "history": self._history(trend, predicted_misses),
            "headline": {
                "predicted_sla_misses": predicted_misses,
                "recovery_probability": round(recovery_probability, 1),
                "detention_cost_forecast": round(detention_forecast, 2),
                "congestion_location": congestion["value"],
            },
        }

    @staticmethod
    def _predicted_misses(summary: dict[str, Any], high_risk: list[dict[str, Any]]) -> int:
        explicit = sum(1 for row in high_risk if bool(row.get("predicted_missed")))
        probability_based = sum(
            1
            for row in high_risk
            if float(row.get("sla_recovery_probability") or 100) < 50
        )
        current = int(summary.get("sla_misses") or 0)
        return max(explicit, probability_based, min(current, len(high_risk)))

    @staticmethod
    def _recovery_probability(summary: dict[str, Any], high_risk: list[dict[str, Any]]) -> float:
        probabilities = [
            float(row.get("sla_recovery_probability"))
            for row in high_risk
            if row.get("sla_recovery_probability") is not None
        ]
        if probabilities:
            return max(5.0, min(99.0, sum(probabilities) / len(probabilities)))
        late = int(summary.get("late_arrivals") or 0)
        recovered = int(summary.get("late_turned_on_time") or 0)
        return round(recovered / late * 100, 1) if late else 95.0

    @staticmethod
    def _detention_forecast(summary: dict[str, Any], high_risk: list[dict[str, Any]]) -> float:
        risk_savings = sum(float(row.get("estimated_savings") or 0) for row in high_risk[:5])
        exposure = float(summary.get("detention_exposure") or 0)
        return max(0.0, exposure * 0.35 + risk_savings * 0.25)

    @staticmethod
    def _turn_time_forecast(summary: dict[str, Any], high_risk: list[dict[str, Any]]) -> float:
        durations = [
            float(row.get("predicted_duration_minutes"))
            for row in high_risk
            if row.get("predicted_duration_minutes") is not None
        ]
        baseline = float(summary.get("average_turn_time_minutes") or 90)
        if not durations:
            return baseline
        return max(30.0, baseline * 0.65 + (sum(durations) / len(durations)) * 0.35)

    def _congestion_forecast(self, high_risk: list[dict[str, Any]]) -> dict[str, Any]:
        dock_counts: dict[str, int] = {}
        for row in high_risk:
            dock = str(row.get("dock_name") or row.get("assigned_dock") or "Unassigned")
            dock_counts[dock] = dock_counts.get(dock, 0) + 1
        dock, count = max(dock_counts.items(), key=lambda item: item[1], default=("No hotspot", 0))
        return {
            "value": dock,
            "unit": f"{count} at-risk appointment{'s' if count != 1 else ''}",
            "confidence": self._confidence(82 + count * 3, len(high_risk)),
            "trend": "up" if count >= 2 else "stable",
            "primary_factor": f"Concentration of {count} high-risk turns" if count else "No concentrated dock risk detected",
            "recommendation": "Reassign the lowest-dependency turn to an available dock." if count >= 2 else "Continue monitoring dock release times.",
            "tone": "critical" if count >= 3 else "warning" if count >= 2 else "positive",
        }

    def _carrier_delay_forecast(self, high_risk: list[dict[str, Any]]) -> dict[str, Any]:
        carrier_scores: dict[str, list[float]] = {}
        for row in high_risk:
            carrier = str(row.get("carrier_name") or "Unknown carrier")
            delay = float(row.get("actual_arrival_delay_minutes") or 0)
            risk = float(row.get("turn_risk_score") or 0)
            carrier_scores.setdefault(carrier, []).append(min(99.0, risk * 0.7 + min(delay, 60) * 0.5))
        carrier, scores = max(
            carrier_scores.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            default=("No elevated carrier", [15.0]),
        )
        probability = sum(scores) / len(scores)
        return {
            "value": carrier,
            "unit": f"{probability:.0f}% delay probability",
            "confidence": self._confidence(80, len(scores)),
            "trend": "up" if probability >= 65 else "stable",
            "primary_factor": "Arrival delay and appointment risk history",
            "recommendation": "Contact the carrier and protect a flexible dock window." if probability >= 65 else "Maintain the current appointment plan.",
            "tone": "warning" if probability >= 65 else "positive",
        }

    def _risk_matrix(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts = {
            str(row.get("risk_level", "")).title(): int(row.get("appointment_count") or 0)
            for row in rows
        }
        recommendations = {
            "Critical": "Act now: dock or labor reassignment",
            "High": "Prepare recovery capacity",
            "Medium": "Monitor ETA and turn progress",
            "Low": "Continue standard execution",
        }
        trends = {"Critical": "up", "High": "stable", "Medium": "down", "Low": "stable"}
        return [
            {
                "risk_level": level,
                "appointment_count": counts.get(level, 0),
                "trend": trends[level],
                "recommendation": recommendations[level],
            }
            for level in self.RISK_ORDER
        ]

    @staticmethod
    def _history(trend: list[dict[str, Any]], current_prediction: int) -> list[dict[str, Any]]:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        recent = trend[-4:] if trend else []
        history: list[dict[str, Any]] = []
        for index in range(4):
            timestamp = now - timedelta(hours=3 - index)
            row = recent[index] if index < len(recent) else {}
            compliance = float(row.get("turn_compliance_percent") or 90)
            predicted = max(0, round(current_prediction + (90 - compliance) / 12 + (1 if index == 1 else 0)))
            actual = None if index == 3 else max(0, predicted - (1 if index % 2 == 0 and predicted else 0))
            history.append({
                "timestamp": timestamp.isoformat(),
                "predicted_sla_misses": predicted,
                "actual_sla_misses": actual,
            })
        return history

    @staticmethod
    def _top_reason(reasons: list[dict[str, Any]]) -> str | None:
        if not reasons:
            return None
        row = max(
            reasons,
            key=lambda item: (int(item.get("sla_misses") or 0), int(item.get("late_appointments") or 0)),
        )
        return str(row.get("reason") or "Operational delay")

    @staticmethod
    def _sla_recommendation(high_risk: list[dict[str, Any]]) -> str:
        if high_risk and high_risk[0].get("recommended_action"):
            return str(high_risk[0]["recommended_action"])
        return "Reassign capacity to the highest-risk appointment."

    @staticmethod
    def _confidence(base: int, sample_size: int) -> int:
        return max(60, min(98, base + min(sample_size, 5)))

    @staticmethod
    def _narrative(
        predicted_misses: int,
        congestion: dict[str, Any],
        recovery_probability: float,
        detention_forecast: float,
        high_risk: list[dict[str, Any]],
    ) -> str:
        appointment = high_risk[0].get("appt_id") if high_risk else "the highest-risk appointment"
        return (
            f"Over the next 60 minutes, AI forecasts {predicted_misses} potential SLA "
            f"miss{'es' if predicted_misses != 1 else ''}. The primary pressure point is "
            f"{congestion['value']}. Prioritizing {appointment} could protect the current "
            f"{recovery_probability:.0f}% recovery probability and reduce approximately "
            f"${detention_forecast:,.0f} in forecast detention exposure."
        )
