from __future__ import annotations

from typing import Any

from app.repositories.copilot_analytics_repository import (
    CopilotAnalyticsRepository,
)
from app.schemas import GlobalCopilotRequest
from app.services.dashboard_service import DashboardService
from app.services.data_copilot_service import DataCopilotService
from app.services.query_planner import WarehouseQueryPlan, WarehouseQueryPlanner


class WarehouseAgent:
    """Orchestrates warehouse analytics tools for the Global Copilot.

    The agent remains deterministic and read-only for analytical questions.
    It can combine multiple approved repository operations for compound
    questions, while delegating ordinary analytical requests to the existing
    DataCopilotService.
    """

    EXECUTIVE_SUMMARY_PHRASES = (
        "summarize today",
        "summarize today's warehouse",
        "summarize todays warehouse",
        "operations summary",
        "warehouse summary",
        "executive summary",
        "daily brief",
        "daily briefing",
        "how are operations",
        "how is the warehouse doing",
    )

    DRIVER_PHRASES = (
        "which appointments are causing",
        "which appointments are driving",
        "appointments causing it",
        "appointments driving it",
        "show the appointments behind",
        "show the drivers",
        "and which appointments",
    )

    def __init__(
        self,
        *,
        data_service: DataCopilotService,
        analytics_repository: CopilotAnalyticsRepository,
        dashboard_service: DashboardService,
    ) -> None:
        self.data_service = data_service
        self.analytics_repository = analytics_repository
        self.dashboard_service = dashboard_service
        self.planner = WarehouseQueryPlanner()

    def answer(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any] | None:
        normalized = self.planner.normalize(payload.question)

        if any(
            phrase in normalized
            for phrase in self.EXECUTIVE_SUMMARY_PHRASES
        ):
            return self._executive_summary(payload)

        if any(
            phrase in normalized
            for phrase in self.DRIVER_PHRASES
        ):
            compound = self._ranking_with_drivers(payload)
            if compound is not None:
                return compound

        return self.data_service.answer(payload)

    def _executive_summary(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any]:
        dashboard = self.dashboard_service.get_dashboard(
            payload.facility_id,
        )
        summary = dashboard["summary"]
        reasons = dashboard.get("delay_sla_reasons", [])
        priorities = dashboard.get("high_risk_appointments", [])
        savings = dashboard.get("recommendation_savings", {})

        total = int(summary.get("total_appointments") or 0)
        late = int(summary.get("late_arrivals") or 0)
        misses = int(summary.get("sla_misses") or 0)
        recovered = int(summary.get("late_turned_on_time") or 0)
        exposure = float(summary.get("detention_exposure") or 0)
        net_savings = float(savings.get("net_savings") or 0)

        top_reason = reasons[0] if reasons else None
        top_priority = priorities[0] if priorities else None

        narrative_parts = [
            f"The current operating scope contains {total:,} appointments.",
            f"{late:,} arrived late, {misses:,} missed SLA, and "
            f"{recovered:,} late turns were recovered.",
        ]

        if top_reason:
            narrative_parts.append(
                f"The leading disruption is {top_reason['reason']}."
            )

        if top_priority:
            narrative_parts.append(
                f"The first appointment to review is "
                f"{top_priority['appt_id']}."
            )

        facts = [
            {"label": "Appointments", "value": f"{total:,}"},
            {"label": "Late arrivals", "value": f"{late:,}"},
            {"label": "SLA misses", "value": f"{misses:,}"},
            {"label": "Late turns recovered", "value": f"{recovered:,}"},
            {"label": "Detention exposure", "value": f"${exposure:,.0f}"},
            {"label": "Net recommendation value", "value": f"${net_savings:,.0f}"},
        ]

        if top_reason:
            facts.append(
                {"label": "Top delay cause", "value": str(top_reason["reason"])}
            )

        if top_priority:
            facts.append(
                {"label": "Highest priority", "value": str(top_priority["appt_id"])}
            )

        suggestions = [
            "Which appointments need attention first?",
            "Why are SLAs being missed?",
            "Which carrier has the highest average delay?",
            "Run a scenario with 1 extra loader and 1 forklift",
        ]
        if top_priority:
            suggestions.insert(0, f"Open {top_priority['appt_id']}")

        return {
            "mode": "answer",
            "answer": " ".join(narrative_parts),
            "facts": facts,
            "suggested_questions": suggestions,
            "action_intent": None,
        }

    def _ranking_with_drivers(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any] | None:
        plan = self.planner.plan(
            payload.question,
            conversation_history=payload.conversation_history,
        )

        if plan.intent != "ranking" or not plan.group_by:
            return None

        if plan.group_by not in {"facility", "carrier", "customer"}:
            return None

        if (
            payload.facility_id
            and "facility_id" not in plan.filters
        ):
            plan.filters["facility_id"] = payload.facility_id

        rows = self.analytics_repository.grouped_appointment_metrics(
            group_by=plan.group_by,
            limit=max(5, plan.limit),
            **plan.filters,
        )
        if not rows:
            return {
                "mode": "answer",
                "answer": "No warehouse records matched that analytical request.",
                "facts": [],
                "suggested_questions": [],
                "action_intent": None,
            }

        metric = plan.metric
        rows.sort(
            key=lambda row: float(row.get(metric) or 0),
            reverse=True,
        )
        leader = rows[0]
        leader_id = str(leader.get("group_id") or "")
        leader_label = str(
            leader.get("group_label")
            or leader.get("group_id")
            or "The leading group"
        )

        driver_filters = dict(plan.filters)
        driver_filters[f"{plan.group_by}_id"] = leader_id

        supported_filters = {
            "facility_id",
            "customer_id",
            "carrier_id",
            "appointment_type",
            "date_from",
            "date_to",
        }
        driver_filters = {
            key: value
            for key, value in driver_filters.items()
            if key in supported_filters
        }

        appointments = self.analytics_repository.top_risk_appointments(
            limit=5,
            **driver_filters,
        )

        metric_label = self._metric_label(metric)
        metric_value = self._format_metric(metric, leader.get(metric))
        appointment_ids = [
            str(row["appt_id"])
            for row in appointments
        ]

        if appointment_ids:
            answer = (
                f"{leader_label} ranks first for {metric_label.lower()} at "
                f"{metric_value}. The highest-risk appointments contributing "
                f"to that operating scope are {', '.join(appointment_ids)}."
            )
        else:
            answer = (
                f"{leader_label} ranks first for {metric_label.lower()} at "
                f"{metric_value}, but no scored driver appointments were "
                "available in that scope."
            )

        facts = [
            {"label": "Leading group", "value": leader_label},
            {"label": metric_label, "value": metric_value},
        ]
        facts.extend(
            {
                "label": str(row["appt_id"]),
                "value": (
                    f"{float(row.get('turn_risk_score') or 0):.1f} risk"
                ),
            }
            for row in appointments
        )

        suggestions = [
            "What about only inbound appointments?",
            "Show the top three",
        ]
        if appointment_ids:
            suggestions.insert(0, f"Open {appointment_ids[0]}")

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts,
            "suggested_questions": suggestions,
            "action_intent": None,
        }

    @staticmethod
    def _metric_label(metric: str) -> str:
        labels = {
            "appointment_count": "Appointment count",
            "late_appointments": "Late appointments",
            "sla_risk_or_misses": "SLA risk or misses",
            "critical_appointments": "Critical appointments",
            "average_delay_minutes": "Average delay",
            "average_turn_time_minutes": "Average turn time",
            "average_risk_score": "Average risk score",
            "detention_exposure": "Detention exposure",
        }
        return labels.get(metric, metric.replace("_", " ").title())

    @staticmethod
    def _format_metric(metric: str, value: Any) -> str:
        numeric = float(value or 0)
        if metric == "detention_exposure":
            return f"${numeric:,.0f}"
        if metric in {
            "average_delay_minutes",
            "average_turn_time_minutes",
        }:
            return f"{numeric:.1f} min"
        if metric == "average_risk_score":
            return f"{numeric:.1f}"
        return f"{int(numeric):,}"
