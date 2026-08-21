from __future__ import annotations
from app.repositories.appointment_repository import AppointmentRepository
import re
from typing import Any

from app.repositories.copilot_analytics_repository import (
    CopilotAnalyticsRepository,
)
from app.schemas import (
    CopilotActionIntent,
    CopilotActionType,
    GlobalCopilotRequest,
)
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
    APPOINTMENT_RISK_PHRASES = (
        "why is this appointment high risk",
        "why is this appointment at risk",
        "why is this appointment risky",
        "why is that appointment high risk",
        "why is that appointment at risk",
        "why is that appointment risky",
        "why is it high risk",
        "why is it at risk",
        "why is it risky",
    )
    def __init__(
        self,
        *,
        data_service: DataCopilotService,
        analytics_repository: CopilotAnalyticsRepository,
        dashboard_service: DashboardService,
        appointment_repository: AppointmentRepository,
    ) -> None:
        self.data_service = data_service
        self.analytics_repository = analytics_repository
        self.dashboard_service = dashboard_service
        self.appointment_repository = appointment_repository
        self.planner = WarehouseQueryPlanner()

    def answer(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any] | None:
        normalized = self.planner.normalize(payload.question)

        ordinal_action = self._resolve_ordinal_open(payload, normalized)
        if ordinal_action is not None:
            return ordinal_action
        if any(
            phrase in normalized
            for phrase in self.APPOINTMENT_RISK_PHRASES
        ):
            appointment_risk = self._explain_contextual_appointment_risk(
                payload
            )
            if appointment_risk is not None:
                return appointment_risk
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
    def _explain_contextual_appointment_risk(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any] | None:
        appt_id = self._resolve_contextual_appointment_id(payload)

        if appt_id is None:
            return {
                "mode": "answer",
                "answer": (
                    "I could not determine which appointment you mean. "
                    "Ask me to show the highest-risk appointments first, "
                    "or include the appointment ID."
                ),
                "facts": [],
                "suggested_questions": [
                    "Show the five highest-risk appointments",
                ],
                "quick_actions": [],
                "action_intent": None,
            }

        details = self.appointment_repository.get_details(appt_id)

        if details is None:
            return {
                "mode": "answer",
                "answer": (
                    f"I resolved the appointment as {appt_id}, but I could "
                    "not find its current operational details."
                ),
                "facts": [
                    {
                        "label": "Appointment",
                        "value": appt_id,
                    }
                ],
                "suggested_questions": [
                    "Show the five highest-risk appointments",
                ],
                "quick_actions": [],
                "action_intent": None,
            }

        return self._build_appointment_risk_answer(
            appt_id,
            details,
        )


    def _resolve_contextual_appointment_id(
        self,
        payload: GlobalCopilotRequest,
    ) -> str | None:
        # First allow an explicit appointment ID in the current question.
        current_match = re.search(
            r"\bDEMO[A-Z0-9_-]*\b",
            payload.question,
            re.IGNORECASE,
        )
        if current_match:
            return current_match.group(0).upper()

        # Search newest messages first. This handles a previous answer such as:
        # "DEMO0152864 has the highest risk..."
        for message in reversed(payload.conversation_history):
            content = str(message.content or "")

            match = re.search(
                r"\bDEMO[A-Z0-9_-]*\b",
                content,
                re.IGNORECASE,
            )
            if match:
                return match.group(0).upper()

        return None
    def _build_appointment_risk_answer(
        self,
        appt_id: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        prediction = details.get("prediction") or {}
        recommendation = details.get("recommendation") or {}
        recovery = details.get("recovery_summary") or {}

        risk_score = float(
            prediction.get("turn_risk_score") or 0
        )
        miss_probability = float(
            prediction.get("sla_miss_probability") or 0
        )
        recovery_probability = float(
            prediction.get("sla_recovery_probability") or 0
        )
        predicted_delay = int(
            prediction.get("predicted_delay_minutes") or 0
        )
        predicted_duration = int(
            prediction.get("predicted_duration_minutes") or 0
        )

        predicted_turn = (
            recovery.get("predicted_turn_time_minutes")
        )
        if predicted_turn is None:
            predicted_turn = (
                max(0, predicted_delay)
                + predicted_duration
            )

        sla_minutes = int(
            recovery.get("sla_minutes")
            or details.get("sla_minutes")
            or 120
        )

        reasons: list[str] = []

        if predicted_delay > 0:
            reasons.append(
                f"a predicted arrival delay of "
                f"{predicted_delay} minutes"
            )

        if predicted_turn > sla_minutes:
            reasons.append(
                f"a predicted total turn time of "
                f"{int(predicted_turn)} minutes against a "
                f"{sla_minutes}-minute SLA"
            )

        if miss_probability >= 0.5:
            displayed_probability = (
                miss_probability * 100
                if miss_probability <= 1
                else miss_probability
            )
            reasons.append(
                f"an SLA miss probability of "
                f"{displayed_probability:.0f}%"
            )

        if prediction.get("predicted_missed"):
            reasons.append(
                "the current prediction classifies the "
                "appointment as an expected SLA miss"
            )

        if risk_score >= 80:
            risk_label = "Critical"
        elif risk_score >= 60:
            risk_label = "High"
        elif risk_score >= 30:
            risk_label = "Medium"
        else:
            risk_label = "Low"

        if reasons:
            reason_text = "; ".join(reasons)

            answer = (
                f"{appt_id} is currently rated {risk_label} risk "
                f"with a turn-risk score of {risk_score:.0f}/100. "
                f"The main signals are {reason_text}."
            )
        else:
            answer = (
                f"{appt_id} currently has a turn-risk score of "
                f"{risk_score:.0f}/100 ({risk_label}). "
                "The latest prediction does not expose a stronger "
                "individual risk driver beyond the current model signals."
            )

        recommended_action = recommendation.get(
            "recommended_action"
        )

        if recommended_action:
            answer += (
                f" The current recovery recommendation is: "
                f"{recommended_action}."
            )

        displayed_miss_probability = (
            miss_probability * 100
            if miss_probability <= 1
            else miss_probability
        )

        displayed_recovery_probability = (
            recovery_probability * 100
            if recovery_probability <= 1
            else recovery_probability
        )

        facts = [
            {
                "label": "Appointment",
                "value": appt_id,
            },
            {
                "label": "Risk",
                "value": f"{risk_score:.0f}/100 · {risk_label}",
            },
            {
                "label": "SLA miss probability",
                "value": f"{displayed_miss_probability:.0f}%",
            },
            {
                "label": "Predicted delay",
                "value": f"{predicted_delay} min",
            },
            {
                "label": "Predicted turn",
                "value": f"{int(predicted_turn)} min",
            },
            {
                "label": "SLA",
                "value": f"{sla_minutes} min",
            },
            {
                "label": "Recovery probability",
                "value": f"{displayed_recovery_probability:.0f}%",
            },
        ]

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts,
            "suggested_questions": [
                f"Open {appt_id}",
                "What should we do to recover this appointment?",
                "What happens if we take the recommended actions?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _resolve_ordinal_open(
        self,
        payload: GlobalCopilotRequest,
        normalized: str,
    ) -> dict[str, Any] | None:
        """Resolve phrases like "open the first appointment".

        The service is request-scoped, so the prior analytical result is
        reconstructed from conversation history. For a ranking result, the
        requested ordinal refers to the highest-risk appointment within the
        ranked group at that position. For a top-risk result, it refers to the
        appointment at that position directly.
        """

        ordinal_words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
        }
        match = re.search(
            r"\bopen\s+(?:the\s+)?"
            r"(first|second|third|fourth|fifth|[1-5])"
            r"(?:\s+appointment)?\b",
            normalized,
        )
        if not match:
            return None

        token = match.group(1)
        ordinal = int(token) if token.isdigit() else ordinal_words[token]

        plan = self.planner.plan(
            payload.question,
            conversation_history=payload.conversation_history,
        )
        if payload.facility_id and "facility_id" not in plan.filters:
            plan.filters["facility_id"] = payload.facility_id

        appointment: dict[str, Any] | None = None

        if plan.intent == "ranking" and plan.group_by in {
            "facility",
            "carrier",
            "customer",
        }:
            rows = self.analytics_repository.grouped_appointment_metrics(
                group_by=plan.group_by,
                limit=max(ordinal, plan.limit, 5),
                **plan.filters,
            )
            rows.sort(
                key=lambda row: float(row.get(plan.metric) or 0),
                reverse=True,
            )
            if len(rows) >= ordinal:
                selected_group = rows[ordinal - 1]
                group_id = str(selected_group.get("group_id") or "")
                filters = dict(plan.filters)
                filters[f"{plan.group_by}_id"] = group_id
                allowed = {
                    "facility_id",
                    "customer_id",
                    "carrier_id",
                    "appointment_type",
                    "date_from",
                    "date_to",
                }
                filters = {
                    key: value
                    for key, value in filters.items()
                    if key in allowed
                }
                appointments = (
                    self.analytics_repository.top_risk_appointments(
                        limit=1,
                        **filters,
                    )
                )
                if appointments:
                    appointment = appointments[0]
        else:
            appointments = self.analytics_repository.top_risk_appointments(
                limit=max(ordinal, 5),
                **{
                    key: value
                    for key, value in plan.filters.items()
                    if key
                    in {
                        "facility_id",
                        "customer_id",
                        "carrier_id",
                        "appointment_type",
                        "date_from",
                        "date_to",
                    }
                },
            )
            if len(appointments) >= ordinal:
                appointment = appointments[ordinal - 1]

        if appointment is None:
            return {
                "mode": "answer",
                "answer": (
                    "I could not resolve that appointment from the current "
                    "analytical result. Ask me to show the appointments first, "
                    "then open one by its position or ID."
                ),
                "facts": [],
                "suggested_questions": [
                    "Show the five highest-risk appointments"
                ],
                "quick_actions": [],
                "action_intent": None,
            }

        appt_id = str(appointment["appt_id"])
        intent = CopilotActionIntent(
            action=CopilotActionType.OPEN_APPOINTMENT,
            confirmation_required=False,
            response_message=(
                f"Opening {appt_id}, the appointment resolved from your "
                "current analytical context."
            ),
            metadata={"appt_id": appt_id},
        )
        return {
            "mode": "action",
            "answer": intent.response_message,
            "facts": [
                {"label": "Appointment", "value": appt_id}
            ],
            "suggested_questions": [
                "Why is this appointment at risk?"
            ],
            "quick_actions": [],
            "action_intent": intent,
        }

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
