from __future__ import annotations

from typing import Any

from app.engines.what_if_engine import WhatIfEngine
from app.errors import AppError
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import AppointmentCopilotRequest


class CopilotService:
    def __init__(
        self,
        repository: AppointmentRepository,
    ) -> None:
        self.repository = repository

    def answer(
        self,
        *,
        appt_id: str,
        payload: AppointmentCopilotRequest,
    ) -> dict[str, Any]:
        details = self.repository.get_details(
            appt_id
        )

        if details is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        appointment = details["appointment"]
        prediction = details["prediction"]
        actions = details[
            "recommendation_actions"
        ]
        products = details["products"]
        recovery = details["recovery_summary"]

        question = payload.question.strip().lower()
        conversation_history = [
            message.model_dump()
            for message in payload.conversation_history
        ]
        simulation = None

        if (
            payload.what_if is not None
            and prediction is not None
        ):
            simulation = WhatIfEngine().simulate(
                appointment=appointment,
                prediction=prediction,
                actions=actions,
                selected_action_ids=(
                    payload.what_if
                    .selected_action_ids
                ),
                extra_loaders=(
                    payload.what_if.extra_loaders
                ),
                extra_forklifts=(
                    payload.what_if
                    .extra_forklifts
                ),
                pre_stage_products=(
                    payload.what_if
                    .pre_stage_products
                ),
            )

        answer = self._build_answer(
    question=question,
    appointment=appointment,
    prediction=prediction,
    products=products,
    actions=actions,
    recovery=recovery,
    simulation=simulation,
    conversation_history=conversation_history,
)

        return {
            "appt_id": appt_id,
            "answer": answer,
            "facts": self._build_facts(
                appointment=appointment,
                prediction=prediction,
                recovery=recovery,
                simulation=simulation,
            ),
            "suggested_questions": [
                "Why is this appointment at risk?",
                "Which recovery action has the highest impact?",
                "Can we meet SLA without extra labor?",
                "What is the projected detention savings?",
                "Summarize this appointment.",
            ],
        }
    def _detect_intent(
        self,
        *,
        question: str,
        conversation_history: list[
            dict[str, str]
        ],
    ) -> str:
        normalized = question.strip().lower()

        # Always classify explicit questions using
        # the current message only.
        if any(
            phrase in normalized
            for phrase in (
                "highest impact",
                "best action",
                "highest roi",
                "which action",
                "which one",
                "accept first",
                "do first",
            )
        ):
            return "highest_impact"

        if any(
            phrase in normalized
            for phrase in (
                "without extra labor",
                "without labor",
                "without adding labor",
                "without another loader",
                "without a loader",
            )
        ):
            return "without_labor"

        if any(
            phrase in normalized
            for phrase in (
                "saving",
                "savings",
                "cost",
                "detention",
                "roi",
                "worth it",
                "financial",
            )
        ):
            return "savings"

        if any(
            phrase in normalized
            for phrase in (
                "what if",
                "simulation",
                "selected actions",
                "meet sla",
                "recover sla",
                "projected turn",
                "what happens",
            )
        ):
            return "simulation"

        if any(
            phrase in normalized
            for phrase in (
                "product",
                "products",
                "load",
                "pallet",
                "sku",
                "temperature zone",
            )
        ):
            return "products"

        if any(
            phrase in normalized
            for phrase in (
                "why",
                "risk",
                "at risk",
                "miss sla",
                "causing",
                "root cause",
            )
        ):
            return "risk"

        if any(
            phrase in normalized
            for phrase in (
                "summarize",
                "summary",
                "overview",
                "executive summary",
            )
        ):
            return "summary"

        # Use history only for genuinely vague
        # follow-up messages.
        vague_follow_ups = {
            "explain that",
            "why is that",
            "what about that",
            "tell me more",
            "and then",
            "what next",
            "how so",
        }

        if normalized not in vague_follow_ups:
            return "unknown"

        previous_user_questions = [
            message["content"].strip().lower()
            for message in conversation_history
            if message["role"] == "user"
        ]

        if not previous_user_questions:
            return "unknown"

        previous_question = (
            previous_user_questions[-1]
        )

        # Resolve the prior question without adding
        # the previous assistant answer.
        return self._detect_intent(
            question=previous_question,
            conversation_history=[],
        )
    def _build_answer(
        self,
        *,
        question: str,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        products: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        recovery: dict[str, Any],
        simulation: dict[str, Any] | None,
        conversation_history: list[
            dict[str, str]
        ],
    ) -> str:
        intent = self._detect_intent(
            question=question,
            conversation_history=
                conversation_history,
        )

        if intent == "summary":
            return self._summary_answer(
                appointment,
                prediction,
                recovery,
            )

        if intent == "risk":
            return self._risk_answer(
                appointment,
                prediction,
                products,
            )

        if intent == "highest_impact":
            return self._highest_impact_answer(
                actions
            )

        if intent == "without_labor":
            return self._without_labor_answer(
                appointment,
                prediction,
                actions,
            )

        if intent == "savings":
            return self._savings_answer(
                recovery,
                simulation,
            )

        if intent == "products":
            return self._product_answer(
                products
            )

        if intent == "simulation":
            return self._simulation_answer(
                simulation
            )

        return (
            "I can answer questions about this "
            "appointment’s risk, products, recovery "
            "actions, What-If scenario, SLA, or "
            "financial impact. Please provide a little "
            "more detail."
        )

    def _resolve_follow_up_question(
        self,
        *,
        question: str,
        conversation_history: list[
            dict[str, str]
        ],
    ) -> str:
        normalized_question = (
            question.strip().lower()
        )

        if not conversation_history:
            return normalized_question

        previous_user_messages = [
            str(message.get("content", ""))
            .strip()
            .lower()
            for message in conversation_history
            if message.get("role") == "user"
            and message.get("content")
        ]

        previous_assistant_messages = [
            str(message.get("content", ""))
            .strip()
            .lower()
            for message in conversation_history
            if message.get("role") == "assistant"
            and message.get("content")
        ]

        last_user_question = (
            previous_user_messages[-1]
            if previous_user_messages
            else ""
        )

        last_assistant_answer = (
            previous_assistant_messages[-1]
            if previous_assistant_messages
            else ""
        )

        recent_context = " ".join(
            value
            for value in [
                last_user_question,
                last_assistant_answer,
            ]
            if value
        )

        action_follow_ups = (
            "which one",
            "which action",
            "what should i accept",
            "what should i do first",
            "which should i accept first",
            "what about that action",
            "which is better",
            "what is the best one",
        )

        if any(
            phrase in normalized_question
            for phrase in action_follow_ups
        ):
            return (
                f"{normalized_question} "
                "highest impact best action "
                "highest roi accept first "
                f"{recent_context}"
            )

        cost_follow_ups = (
            "what about the cost",
            "how much will it cost",
            "what about savings",
            "how much will we save",
            "is it worth it",
            "what is the roi",
            "what about the money",
            "financial impact",
        )

        if any(
            phrase in normalized_question
            for phrase in cost_follow_ups
        ):
            return (
                f"{normalized_question} "
                "savings detention cost roi "
                "financial impact "
                f"{recent_context}"
            )

        simulation_follow_ups = (
            "what happens then",
            "what happens now",
            "will that recover sla",
            "does that meet sla",
            "will it meet sla",
            "and after that",
            "what if i do that",
            "what will that change",
            "will that work",
        )

        if any(
            phrase in normalized_question
            for phrase in simulation_follow_ups
        ):
            return (
                f"{normalized_question} "
                "simulation selected actions "
                "meet sla recover sla "
                f"{recent_context}"
            )

        risk_follow_ups = (
            "why",
            "why is that",
            "explain that",
            "explain why",
            "what is causing it",
            "what caused that",
            "why did that happen",
        )

        if normalized_question in risk_follow_ups:
            return (
                f"{normalized_question} "
                "why risk delay miss sla "
                f"{recent_context}"
            )

        product_follow_ups = (
            "which products",
            "what products",
            "what about the load",
            "which pallets",
            "what is making it complex",
        )

        if any(
            phrase in normalized_question
            for phrase in product_follow_ups
        ):
            return (
                f"{normalized_question} "
                "products load pallets skus "
                f"{recent_context}"
            )

        summary_follow_ups = (
            "summarize that",
            "give me a summary",
            "give me the overview",
            "recap that",
        )

        if any(
            phrase in normalized_question
            for phrase in summary_follow_ups
        ):
            return (
                f"{normalized_question} "
                "summary overview "
                f"{recent_context}"
            )

        return normalized_question

    def _summary_answer(
        self,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        recovery: dict[str, Any],
    ) -> str:
        risk_score = (
            prediction.get("turn_risk_score")
            if prediction
            else None
        )

        predicted_turn = recovery.get(
            "predicted_turn_time_minutes"
        )

        sla = recovery.get("sla_minutes")

        return (
            f"Appointment {appointment['appt_id']} "
            f"is currently {appointment['status']} at "
            f"{appointment['facility_name']}. "
            f"It includes {appointment['pallet_count']} pallets "
            f"across {appointment['sku_count']} SKUs. "
            f"The current risk score is "
            f"{risk_score if risk_score is not None else 'unavailable'} "
            f"and predicted turn time is "
            f"{predicted_turn if predicted_turn is not None else 'unavailable'} "
            f"minutes against a {sla}-minute SLA."
        )

    def _risk_answer(
        self,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        products: list[dict[str, Any]],
    ) -> str:
        reasons: list[str] = []

        delay = (
            appointment.get(
                "actual_arrival_delay_minutes"
            )
            or (
                prediction.get(
                    "predicted_delay_minutes"
                )
                if prediction
                else 0
            )
            or 0
        )

        if delay > 0:
            reasons.append(
                f"the carrier is delayed by approximately "
                f"{delay} minutes"
            )

        if appointment.get("pallet_count", 0) >= 25:
            reasons.append(
                f"the load contains "
                f"{appointment['pallet_count']} pallets"
            )

        if appointment.get("sku_count", 0) >= 7:
            reasons.append(
                f"the load contains "
                f"{appointment['sku_count']} SKUs"
            )

        temperature_zones = {
            product.get("temperature_zone")
            for product in products
            if product.get("temperature_zone")
        }

        if len(temperature_zones) > 1:
            reasons.append(
                "multiple temperature zones increase "
                "staging and handling complexity"
            )

        if appointment.get("surge_indicator"):
            reasons.append(
                "the facility is operating under surge conditions"
            )

        if not reasons:
            reasons.append(
                "the current prediction combines load, arrival, "
                "facility, and operational factors"
            )

        return (
            "This appointment is at risk because "
            + "; ".join(reasons)
            + "."
        )

    def _highest_impact_answer(
        self,
        actions: list[dict[str, Any]],
    ) -> str:
        if not actions:
            return (
                "No structured recovery actions are available "
                "for this appointment."
            )

        best = max(
            actions,
            key=lambda action:
                action.get(
                    "estimated_minutes_saved",
                    0,
                )
                or 0,
        )

        minutes = (
            best.get(
                "estimated_minutes_saved",
                0,
            )
            or 0
        )

        cost = float(
            best.get(
                "estimated_action_cost",
                0,
            )
            or 0
        )

        return (
            f"The highest-impact action is "
            f"'{best['action_title']}'. "
            f"It is estimated to save {minutes} minutes "
            f"at an estimated cost of ${cost:,.2f}."
        )

    def _without_labor_answer(
        self,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        actions: list[dict[str, Any]],
    ) -> str:
        if prediction is None:
            return (
                "A prediction is required to evaluate "
                "a no-extra-labor scenario."
            )

        non_labor_action_ids = [
            action["recommendation_action_id"]
            for action in actions
            if (
                action.get(
                    "additional_loaders",
                    0,
                )
                or 0
            ) == 0
        ]

        simulation = WhatIfEngine().simulate(
            appointment=appointment,
            prediction=prediction,
            actions=actions,
            selected_action_ids=(
                non_labor_action_ids
            ),
            extra_loaders=0,
            extra_forklifts=0,
            pre_stage_products=False,
        )

        scenario = simulation["scenario"]

        if scenario["sla_recovered"]:
            return (
                "Yes. Using only non-labor recovery actions, "
                f"the projected turn time is "
                f"{scenario['projected_turn_time_minutes']} minutes, "
                "which is within the SLA."
            )

        return (
            "No. Using only non-labor recovery actions, "
            f"the projected turn time remains "
            f"{scenario['projected_turn_time_minutes']} minutes. "
            "Additional labor or another operational intervention "
            "would still be required."
        )

    def _savings_answer(
        self,
        recovery: dict[str, Any],
        simulation: dict[str, Any] | None,
    ) -> str:
        if simulation is not None:
            scenario = simulation["scenario"]

            return (
                f"The current simulated plan produces gross savings "
                f"of ${scenario['gross_savings']:,.2f}, "
                f"action cost of ${scenario['action_cost']:,.2f}, "
                f"and net savings of ${scenario['net_savings']:,.2f}."
            )

        accepted_cost = float(
            recovery.get(
                "accepted_action_cost",
                0,
            )
            or 0
        )

        accepted_minutes = (
            recovery.get(
                "accepted_minutes_saved",
                0,
            )
            or 0
        )

        return (
            f"The accepted plan currently saves "
            f"{accepted_minutes} minutes with an accepted action "
            f"cost of ${accepted_cost:,.2f}. "
            "Run a What-If scenario to estimate detention savings."
        )

    def _product_answer(
        self,
        products: list[dict[str, Any]],
    ) -> str:
        if not products:
            return (
                "No product-line details are available "
                "for this appointment."
            )

        top_products = sorted(
            products,
            key=lambda product:
                product.get("pallet_count", 0)
                or 0,
            reverse=True,
        )[:3]

        product_text = ", ".join(
            f"{product['product_name']} "
            f"({product.get('pallet_count', 0)} pallets)"
            for product in top_products
        )

        return (
            f"The largest product contributors are {product_text}. "
            "These products contribute most to handling volume."
        )

    def _simulation_answer(
        self,
        simulation: dict[str, Any] | None,
    ) -> str:
        if simulation is None:
            return (
                "No active What-If scenario was provided. "
                "Select recovery actions or adjust warehouse resources "
                "and ask again."
            )

        scenario = simulation["scenario"]

        return (
            f"The selected scenario projects a turn time of "
            f"{scenario['projected_turn_time_minutes']} minutes, "
            f"saves {scenario['minutes_saved']} minutes, "
            f"and produces net savings of "
            f"${scenario['net_savings']:,.2f}. "
            f"The SLA is "
            f"{'recovered' if scenario['sla_recovered'] else 'still at risk'}."
        )

    def _build_facts(
        self,
        *,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        recovery: dict[str, Any],
        simulation: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        facts = [
            {
                "label": "Appointment",
                "value": appointment["appt_id"],
            },
            {
                "label": "Facility",
                "value": appointment[
                    "facility_name"
                ],
            },
            {
                "label": "SLA",
                "value": (
                    f"{recovery['sla_minutes']} min"
                ),
            },
        ]

        if prediction is not None:
            facts.extend(
                [
                    {
                        "label": "Risk score",
                        "value": (
                            f"{prediction['turn_risk_score']}/100"
                        ),
                    },
                    {
                        "label": "Miss probability",
                        "value": (
                            f"{round(
                                float(
                                    prediction[
                                        'sla_miss_probability'
                                    ]
                                    or 0
                                ) * 100
                            )}%"
                        ),
                    },
                ]
            )

        if simulation is not None:
            facts.extend(
                [
                    {
                        "label": "Simulated turn",
                        "value": (
                            f"{simulation['scenario']['projected_turn_time_minutes']} min"
                        ),
                    },
                    {
                        "label": "Net savings",
                        "value": (
                            f"${simulation['scenario']['net_savings']:,.2f}"
                        ),
                    },
                ]
            )

        return facts