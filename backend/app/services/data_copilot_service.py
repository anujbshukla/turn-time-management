from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.copilot_analytics_repository import (
    CopilotAnalyticsRepository,
)
from app.schemas import GlobalCopilotRequest
from app.services.query_planner import (
    WarehouseQueryPlan,
    WarehouseQueryPlanner,
)
from app.services.copilot_v2 import NaturalLanguageQueryEngine


class DataCopilotService:
    """Safe natural-language analytics over approved warehouse data."""

    RANKING_MIN_SAMPLE_SIZE = 5

    def __init__(
        self,
        analytics_repository: CopilotAnalyticsRepository,
        appointment_repository: AppointmentRepository,
    ) -> None:
        self.analytics_repository = analytics_repository
        self.appointment_repository = appointment_repository
        self.planner = WarehouseQueryPlanner()
        self.nl_query_engine = NaturalLanguageQueryEngine()

    @staticmethod
    def _conversation_state_from_history(history):
        for item in reversed(history or []):
            if not isinstance(item, dict):
                continue
            state = item.get("canonical_query_state")
            if isinstance(state, dict):
                return state
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                state = metadata.get("canonical_query_state")
                if isinstance(state, dict):
                    return state
        return {}

    def answer(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any] | None:
        references = self.appointment_repository.get_reference_data()

        if self.nl_query_engine.enabled:
            canonical, plan = self.nl_query_engine.plan(
                question=payload.question,
                payload=payload,
                reference_data=references,
                conversation_state=self._conversation_state_from_history(
                    payload.conversation_history
                ),
            )

            if canonical.clarification_needed:
                return self._response(
                    canonical.clarification_question
                    or "I need one clarification before I can query the data."
                )

            # V2 currently represents only one date range. If the deterministic
            # planner recognizes two independent time periods, preserve V2's
            # semantic metric/filter interpretation but execute the request as
            # a temporal comparison.
            temporal_plan = self.planner.plan(
                payload.question,
                conversation_history=payload.conversation_history,
            )

            if temporal_plan.intent == "temporal_comparison":
                temporal_plan.metric = plan.metric

                # Preserve V2-resolved non-date semantic filters such as
                # facility, customer, carrier, appointment type, status, etc.
                temporal_plan.filters.update(
                    {
                        key: value
                        for key, value in plan.filters.items()
                        if key not in {"date_from", "date_to"}
                    }
                )

                plan = temporal_plan

        else:
            plan = self.planner.plan(
                payload.question,
                conversation_history=payload.conversation_history,
            )

            if not plan.understood:
                return None
        clarification = self._resolve_entities(
            plan=plan,
            question=payload.question,
            references=references,
        )
        if clarification:
            return self._response(clarification)

        # Historical resource-effectiveness analysis should use the available
        # historical record unless the user explicitly supplied a time scope.
        #
        # Example:
        #   "Do extra loaders help historically?"
        #       -> historical data, not today's dashboard window
        #
        #   "Do extra loaders help in the last 30 days?"
        #       -> preserve the explicit 30-day window
        if (
            self.nl_query_engine.enabled
            and plan.intent == "resource_effectiveness"
            and not canonical.explicit_time
        ):
            plan.ignore_request_date_context = True
            plan.filters.pop("date_from", None)
            plan.filters.pop("date_to", None)

            # Keep the returned canonical state aligned with the scope actually
            # executed by the analytics query.
            canonical.date_from = None
            canonical.date_to = None
            canonical.filters.pop("date_from", None)
            canonical.filters.pop("date_to", None)
        self._apply_request_context(plan, payload)

        if plan.intent == "ranking" and plan.group_by:
            self.planner._clear_group_dimension_filter(
                plan
            )

        handlers = {
            "top_risk": self._top_risk_response,
            "resource_effectiveness":
                self._resource_effectiveness_response,
            "risk_drivers": self._risk_driver_response,
            "driver_analysis": self._turn_time_driver_response,
            "mission_summary": self._mission_summary_response,
            "action_effectiveness":
                self._action_effectiveness_response,
            "product_handling": self._product_handling_response,
            "temporal_comparison": self._temporal_comparison_response,
        }
        if plan.intent in handlers:
            response = handlers[plan.intent](plan)
        elif plan.intent == "ranking" and plan.group_by:
            response = self._ranking_response(plan)
        else:
            response = self._summary_response(plan)

        if self.nl_query_engine.enabled:
            response["canonical_query_state"] = canonical.to_state_dict()

        return response

    @staticmethod
    def _apply_request_context(
        plan: WarehouseQueryPlan,
        payload: GlobalCopilotRequest,
    ) -> None:
        """Ground analytics in current UI filters unless the question overrides."""
        context = {
            "facility_id": payload.facility_id,
            "customer_id": payload.customer_id,
            "carrier_id": payload.carrier_id,
            "appointment_type": payload.appointment_type,
            "status": payload.status,
            "risk_level": payload.risk_level,
        }
        for key, value in context.items():
            if value is not None and key not in plan.filters:
                plan.filters[key] = value

        if (
            not plan.ignore_request_date_context
            and payload.date_from is not None
            and "date_from" not in plan.filters
        ):
            plan.filters["date_from"] = datetime.combine(
                payload.date_from,
                datetime.min.time(),
            )
        if (
            not plan.ignore_request_date_context
            and payload.date_to is not None
            and "date_to" not in plan.filters
        ):
            # OperationsFilterBar / appointment APIs use an exclusive upper
            # bound. Preserve that contract exactly: Today is [today, tomorrow),
            # not [today, day-after-tomorrow).
            plan.filters["date_to"] = datetime.combine(
                payload.date_to,
                datetime.min.time(),
            )

    @staticmethod
    def _scope_fact(
        plan: WarehouseQueryPlan,
    ) -> dict[str, str] | None:
        parts: list[str] = []

        if plan.filters.get("facility_id"):
            parts.append(str(plan.filters["facility_id"]))
        if plan.filters.get("customer_id"):
            parts.append(f"Customer {plan.filters['customer_id']}")
        if plan.filters.get("carrier_id"):
            parts.append(f"Carrier {plan.filters['carrier_id']}")
        if plan.filters.get("appointment_type"):
            parts.append(str(plan.filters["appointment_type"]))
        if plan.filters.get("status"):
            parts.append(str(plan.filters["status"]))
        if plan.filters.get("risk_level"):
            parts.append(f"{plan.filters['risk_level']} risk")
        pallet_min = plan.filters.get("pallet_min")
        pallet_max = plan.filters.get("pallet_max")

        if pallet_min is not None and pallet_max is not None:
            parts.append(f"{pallet_min}–{pallet_max} pallets")
        elif pallet_min is not None:
            parts.append(f"{pallet_min}+ pallets")
        elif pallet_max is not None:
            parts.append(f"≤{pallet_max} pallets")

        sku_min = plan.filters.get("sku_min")
        sku_max = plan.filters.get("sku_max")

        if sku_min is not None and sku_max is not None:
            parts.append(f"{sku_min}–{sku_max} SKUs")
        elif sku_min is not None:
            parts.append(f"{sku_min}+ SKUs")
        elif sku_max is not None:
            parts.append(f"≤{sku_max} SKUs")

        date_from = plan.filters.get("date_from")
        date_to = plan.filters.get("date_to")
        if isinstance(date_from, datetime) and isinstance(date_to, datetime):
            # date_to is exclusive; display the inclusive calendar end.
            inclusive_end = date_to - timedelta(days=1)
            if date_from.date() == inclusive_end.date():
                parts.append(date_from.strftime("%b %d, %Y"))
            else:
                parts.append(
                    f"{date_from.strftime('%b %d, %Y')}–"
                    f"{inclusive_end.strftime('%b %d, %Y')}"
                )
        elif isinstance(date_from, datetime):
            parts.append(f"From {date_from.strftime('%b %d, %Y')}")

        if not parts:
            return None

        return {
            "label": "Scope",
            "value": " · ".join(parts),
        }
    def _temporal_comparison_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        comparison_a = plan.comparison_a
        comparison_b = plan.comparison_b

        if not comparison_a or not comparison_b:
            return self._response(
                "I could not determine both time periods for that comparison."
            )

        shared_filters = {
            key: value
            for key, value in plan.filters.items()
            if key not in {"date_from", "date_to"}
        }

        filters_a = {**shared_filters, "date_from": comparison_a["date_from"], "date_to": comparison_a["date_to"]}
        filters_b = {**shared_filters, "date_from": comparison_b["date_from"], "date_to": comparison_b["date_to"]}

        result_a = self.analytics_repository.advanced_appointment_summary(**filters_a)
        result_b = self.analytics_repository.advanced_appointment_summary(**filters_b)

        metric = plan.metric or "appointment_count"
        raw_value_a = result_a.get(metric)
        raw_value_b = result_b.get(metric)
        value_a = float(raw_value_a) if raw_value_a is not None else None
        value_b = float(raw_value_b) if raw_value_b is not None else None

        label_a = str(comparison_a.get("label") or "Period A")
        label_b = str(comparison_b.get("label") or "Period B")
        formatted_a = self._format_metric(metric, value_a) if value_a is not None else "No realized data"
        formatted_b = self._format_metric(metric, value_b) if value_b is not None else "No realized data"
        metric_label = self._metric_label(metric)

        if value_a is None or value_b is None:
            answer = (
                f"{metric_label} was {formatted_a} for {label_a} "
                f"and {formatted_b} for {label_b}. "
                "A numeric change cannot be calculated because realized data "
                "is not available for both periods."
            )
            difference = None
            percent_change = None
        else:
            difference = value_b - value_a
            percent_change = (difference / abs(value_a)) * 100 if value_a != 0 else None
            formatted_difference = self._format_metric(metric, abs(difference))

            if difference > 0:
                direction_text = f"{label_b} is {formatted_difference} higher than {label_a}"
            elif difference < 0:
                direction_text = f"{label_b} is {formatted_difference} lower than {label_a}"
            else:
                direction_text = f"{label_b} is unchanged from {label_a}"

            if percent_change is not None and difference != 0:
                direction_text += f" ({abs(percent_change):.1f}% change)"

            answer = (
                f"{metric_label} was {formatted_a} for {label_a} "
                f"and {formatted_b} for {label_b}. {direction_text}."
            )

        facts: list[dict[str, str]] = []
        scope_fact = self._scope_fact(plan)
        if scope_fact:
            facts.append(scope_fact)

        facts.extend([
            {"label": label_a, "value": formatted_a},
            {"label": label_b, "value": formatted_b},
        ])

        if difference is not None:
            facts.append({
                "label": "Difference",
                "value": (
                    f"+{self._format_metric(metric, difference)}"
                    if difference > 0
                    else self._format_metric(metric, difference)
                ),
            })

        if percent_change is not None:
            facts.append({"label": "Change", "value": f"{percent_change:+.1f}%"})

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts[:8],
            "suggested_questions": [
                f"Compare SLA miss rate for {label_a} vs {label_b}",
                f"Compare average turn time for {label_a} vs {label_b}",
                f"Compare late appointments for {label_a} vs {label_b}",
                "Which appointments are driving the difference?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _summary_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        result = self.analytics_repository.advanced_appointment_summary(
            **plan.filters
        )
        count = int(result.get("appointment_count") or 0)
        late = int(result.get("late_appointments") or 0)
        misses = int(result.get("sla_risk_or_misses") or 0)
        critical = int(result.get("critical_appointments") or 0)

        if plan.metric == "sla_miss_rate_percent":
            answer = (
                f"{float(result.get('sla_miss_rate_percent') or 0):.1f}% "
                f"of appointments in the requested scope have an actual or "
                f"predicted SLA miss ({misses:,} of {count:,})."
            )
        elif plan.metric == "late_rate_percent":
            answer = (
                f"{float(result.get('late_rate_percent') or 0):.1f}% "
                f"of appointments in the requested scope are late "
                f"({late:,} of {count:,})."
            )
        elif plan.metric == "detention_exposure":
            answer = (
                f"Detention exposure in the requested scope is "
                f"${float(result.get('detention_exposure') or 0):,.0f} "
                f"across {count:,} appointments."
            )
        elif plan.metric in {
            "average_delay_minutes",
            "average_turn_time_minutes",
            "average_risk_score",
            "average_pallet_count",
            "average_sku_count",
            "average_dock_congestion_percent",
            "average_labor_utilization_percent",
            "average_forklift_utilization_percent",
        }:
            answer = (
                f"{self._metric_label(plan.metric)} in the requested scope "
                f"is {self._format_metric(plan.metric, result.get(plan.metric))} "
                f"across {count:,} appointments."
            )
        else:
            answer = (
                f"I found {count:,} appointments in the requested operating "
                f"scope. {late:,} are late, {misses:,} have an actual or "
                f"predicted SLA miss, and {critical:,} are Critical risk."
            )

        facts: list[dict[str, str]] = []
        scope_fact = self._scope_fact(plan)
        if scope_fact:
            facts.append(scope_fact)

        facts.extend([
            {"label": "Appointments", "value": f"{count:,}"},
            {"label": "Late", "value": f"{late:,}"},
            {"label": "SLA risk / misses", "value": f"{misses:,}"},
            {"label": "Critical", "value": f"{critical:,}"},
        ])
        for metric in (
            "sla_miss_rate_percent",
            "average_delay_minutes",
            "average_turn_time_minutes",
            "average_pallet_count",
            "average_dock_congestion_percent",
        ):
            if result.get(metric) is not None:
                facts.append(
                    {
                        "label": self._metric_label(metric),
                        "value": self._format_metric(
                            metric,
                            result.get(metric),
                        ),
                    }
                )

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts[:8],
            "suggested_questions": [
                "Which facility has the most Critical appointments?",
                "Rank carriers by SLA miss rate",
                "Show the highest-risk appointments",
                "What are the biggest risk drivers?",
            ],
            "quick_actions": self._summary_quick_actions(
                plan,
                count,
                critical,
            ),
            "action_intent": None,
        }

    @classmethod
    def _ranking_fact_value(
        cls,
        metric: str,
        row: dict[str, Any],
        *,
        limited_sample: bool = False,
    ) -> str:
        metric_text = cls._format_metric(
            metric,
            row.get(metric),
        )
        sample_size = int(
            row.get("appointment_count")
            or 0
        )
        appointment_label = (
            "appointment"
            if sample_size == 1
            else "appointments"
        )

        if metric == "sla_miss_rate_percent":
            misses = int(
                row.get("sla_risk_or_misses")
                or 0
            )
            value = (
                f"{metric_text} · "
                f"{misses:,} miss"
                f"{'' if misses == 1 else 'es'} / "
                f"{sample_size:,} {appointment_label}"
            )
        elif metric == "late_rate_percent":
            late = int(
                row.get("late_appointments")
                or 0
            )
            value = (
                f"{metric_text} · "
                f"{late:,} late / "
                f"{sample_size:,} {appointment_label}"
            )
        else:
            value = (
                f"{metric_text} · "
                f"{sample_size:,} {appointment_label}"
            )

        if limited_sample:
            value += " · Limited sample"

        return value

    def _ranking_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        rows = self.analytics_repository.advanced_grouped_metrics(
            group_by=plan.group_by or "facility",
            limit=max(25, plan.limit),
            **plan.filters,
        )
        if not rows:
            return self._response(
                "No warehouse records matched that combination of filters."
            )

        rows.sort(
            key=lambda row: float(
                row.get(plan.metric) or 0
            ),
            reverse=(plan.ranking_direction != "asc"),
        )

        minimum_sample = self.RANKING_MIN_SAMPLE_SIZE
        reliable_rows = [
            row
            for row in rows
            if int(row.get("appointment_count") or 0)
            >= minimum_sample
        ]
        limited_rows = [
            row
            for row in rows
            if int(row.get("appointment_count") or 0)
            < minimum_sample
        ]

        all_limited = not reliable_rows
        primary_rows = (
            reliable_rows
            if reliable_rows
            else limited_rows
        )
        leader = primary_rows[0]
        label = str(
            leader.get("group_label")
            or leader.get("group_id")
        )
        leader_metric = self._format_metric(
            plan.metric,
            leader.get(plan.metric),
        )
        leader_sample = int(
            leader.get("appointment_count")
            or 0
        )
        leader_appointment_label = (
            "appointment"
            if leader_sample == 1
            else "appointments"
        )

        if all_limited:
            answer = (
                f"{label} has the highest observed "
                f"{self._metric_label(plan.metric).lower()} at "
                f"{leader_metric}, based on "
                f"{leader_sample:,} {leader_appointment_label}. "
                f"All groups have fewer than {minimum_sample} appointments, "
                "so this ranking has limited evidence."
            )
        else:
            answer = (
                f"{label} ranks first for "
                f"{self._metric_label(plan.metric).lower()} among groups "
                f"with at least {minimum_sample} appointments at "
                f"{leader_metric}, based on "
                f"{leader_sample:,} {leader_appointment_label}."
            )
            if limited_rows:
                observed = limited_rows[0]
                observed_metric = float(
                    observed.get(plan.metric) or 0
                )
                leader_numeric = float(
                    leader.get(plan.metric) or 0
                )
                observed_is_more_extreme = (
                    observed_metric < leader_numeric
                    if plan.ranking_direction == "asc"
                    else observed_metric > leader_numeric
                )
                if observed_is_more_extreme:
                    observed_label = str(
                        observed.get("group_label")
                        or observed.get("group_id")
                    )
                    observed_sample = int(
                        observed.get("appointment_count")
                        or 0
                    )
                    observed_appointment_label = (
                        "appointment"
                        if observed_sample == 1
                        else "appointments"
                    )
                    comparison_word = (
                        "lower"
                        if plan.ranking_direction == "asc"
                        else "higher"
                    )
                    answer += (
                        f" {observed_label} has a {comparison_word} observed value of "
                        f"{self._format_metric(plan.metric, observed_metric)}, "
                        f"but it is based on only {observed_sample:,} "
                        f"{observed_appointment_label} and is marked "
                        "Limited sample."
                    )

        # Primary ranking is evidence-qualified. Limited-sample observations
        # remain visible afterward instead of being silently discarded.
        display_rows = primary_rows[:plan.limit]
        remaining_slots = max(0, plan.limit - len(display_rows))
        if not all_limited and remaining_slots:
            display_rows.extend(limited_rows[:remaining_slots])

        facts = (
            ([self._scope_fact(plan)] if self._scope_fact(plan) else [])
            + [
                {
                    "label": str(
                        row.get("group_label")
                        or row.get("group_id")
                    ),
                    "value": self._ranking_fact_value(
                        plan.metric,
                        row,
                        limited_sample=(
                            int(row.get("appointment_count") or 0)
                            < minimum_sample
                        ),
                    ),
                }
                for row in display_rows[:8]
            ]
        )

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts,
            "suggested_questions": [
                "What about only inbound appointments?",
                "What about the last 30 days?",
                "Which appointments are driving that result?",
            ],
            "quick_actions": self._ranking_quick_actions(
                plan,
                leader,
            ),
            "action_intent": None,
        }

    def _top_risk_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        filters = {
            key: value
            for key, value in plan.filters.items()
            if key in {
                "facility_id",
                "customer_id",
                "carrier_id",
                "appointment_type",
                "date_from",
                "date_to",
            }
        }
        rows = self.analytics_repository.top_risk_appointments(
            limit=plan.limit,
            **filters,
        )
        if not rows:
            return self._response(
                "No scored appointments matched the requested scope."
            )

        first = rows[0]
        return {
            "mode": "answer",
            "answer": (
                f"{first['appt_id']} is currently the highest-risk matching "
                f"appointment with a risk score of "
                f"{float(first['turn_risk_score'] or 0):.1f}."
            ),
            "facts": [
                {
                    "label": row["appt_id"],
                    "value": (
                        f"{float(row['turn_risk_score'] or 0):.1f} risk"
                    ),
                }
                for row in rows
            ],
            "suggested_questions": [
                f"Open {first['appt_id']}",
                "Why is this appointment at risk?",
                "Run a recovery scenario",
            ],
            "quick_actions": [
                {
                    "label": f"Open {first['appt_id']}",
                    "action": "open_appointment",
                    "metadata": {
                        "appt_id": str(first["appt_id"])
                    },
                },
                {
                    "label": "Filter Critical queue",
                    "action": "filter_appointments",
                    "metadata": {"risk_level": "Critical"},
                },
                {
                    "label": "Run recovery What-If",
                    "action": "run_what_if",
                    "metadata": {
                        "extra_loaders": "1",
                        "extra_forklifts": "1",
                        "pre_stage_products": "false",
                    },
                },
            ],
            "action_intent": None,
        }

    def _resource_effectiveness_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        filters = self._subset_filters(
            plan,
            {
                "facility_id",
                "customer_id",
                "carrier_id",
                "appointment_type",
                "date_from",
                "date_to",
            },
        )
        resource_type = plan.resource_type or "loaders"
        rows = self.analytics_repository.resource_effectiveness(
            resource_type=resource_type,
            **filters,
        )
        if not rows:
            return self._response(
                "No completed appointments with realized resource allocations "
                "matched that scope."
            )

        best = min(
            rows,
            key=lambda row: float(
                row.get("average_turn_time_minutes")
                if row.get("average_turn_time_minutes") is not None
                else 10**9
            ),
        )
        singular = (
            "loader"
            if resource_type == "loaders"
            else "forklift"
        )
        count = int(best["resource_count"] or 0)
        best_sample = int(best.get("appointment_count") or 0)

        date_from = plan.filters.get("date_from")
        date_to = plan.filters.get("date_to")
        appointment_type = plan.filters.get("appointment_type")

        scope_parts: list[str] = []
        if isinstance(date_from, datetime) and isinstance(date_to, datetime):
            day_count = max(
                1,
                int((date_to - date_from).total_seconds() // 86400),
            )
            if day_count == 1:
                scope_parts.append(
                    date_from.strftime("on %b %d, %Y")
                )
            elif day_count == 30:
                scope_parts.append("over the last 30 days")
            else:
                inclusive_end = date_to - timedelta(days=1)
                scope_parts.append(
                    f"from {date_from.strftime('%b %d, %Y')} to "
                    f"{inclusive_end.strftime('%b %d, %Y')}"
                )
        else:
            scope_parts.append("historically")

        if appointment_type:
            scope_parts.append(
                f"for {str(appointment_type).lower()} appointments"
            )

        scope_phrase = " ".join(scope_parts)
        answer = (
            f"{scope_phrase.capitalize()}, appointments using {count} "
            f"{singular}{'' if count == 1 else 's'} had the lowest average "
            f"turn time in this scope at "
            f"{float(best['average_turn_time_minutes'] or 0):.1f} minutes, "
            f"based on {best_sample:,} "
            f"appointment{'' if best_sample == 1 else 's'}. "
            "This is observational evidence rather than a causal estimate; "
            "larger or more complex loads may receive more resources."
        )
        return {
            "mode": "answer",
            "answer": answer,
            "facts": [
                {
                    "label": (
                        f"{int(row['resource_count'] or 0)} "
                        f"{singular}{'' if int(row['resource_count'] or 0) == 1 else 's'}"
                    ),
                    "value": (
                        f"{float(row['average_turn_time_minutes'] or 0):.1f} min · "
                        f"{float(row['sla_miss_rate_percent'] or 0):.1f}% SLA miss · "
                        f"{int(row.get('appointment_count') or 0):,} "
                        f"appointment"
                        f"{'' if int(row.get('appointment_count') or 0) == 1 else 's'}"
                    ),
                }
                for row in rows[:8]
            ],
            "suggested_questions": [
                "What about only inbound appointments?",
                "What about the last 30 days?",
                "Which appointments are at highest risk now?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _turn_time_driver_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        filters = self._subset_filters(
            plan,
            {
                "facility_id",
                "customer_id",
                "carrier_id",
                "product_id",
                "appointment_type",
                "status",
                "risk_level",
                "date_from",
                "date_to",
            },
        )
        analysis = self.analytics_repository.turn_time_driver_analysis(
            minimum_sample=self.RANKING_MIN_SAMPLE_SIZE,
            limit=max(8, plan.limit),
            **filters,
        )

        baseline_count = int(
            analysis.get("baseline_appointments") or 0
        )
        baseline_turn = analysis.get(
            "baseline_turn_minutes"
        )
        rows = list(analysis.get("drivers") or [])

        if baseline_count == 0 or baseline_turn is None:
            return self._response(
                "I do not have completed appointments with realized turn "
                "times in that operating scope, so I cannot calculate "
                "observed turn-time drivers."
            )

        # For a "high turn time" diagnosis, only surface segments whose
        # observed average is above the scoped baseline.
        positive_rows = [
            row
            for row in rows
            if float(
                row.get("turn_time_delta_minutes") or 0
            ) > 0
        ]

        facts: list[dict[str, str]] = []
        scope_fact = self._scope_fact(plan)
        if scope_fact:
            facts.append(scope_fact)

        facts.append(
            {
                "label": "Scoped baseline",
                "value": (
                    f"{float(baseline_turn):.1f} min · "
                    f"{baseline_count:,} appointments"
                ),
            }
        )

        if not positive_rows:
            return {
                "mode": "answer",
                "answer": (
                    f"Average realized turn time is "
                    f"{float(baseline_turn):.1f} minutes across "
                    f"{baseline_count:,} appointments. None of the "
                    "predefined operational segments with sufficient sample "
                    "size ran above that scoped baseline, so I do not have a "
                    "reliable observed driver to rank for this question."
                ),
                "facts": facts,
                "suggested_questions": [
                    "Compare turn time by carrier",
                    "Compare turn time by customer",
                    "Which products take longest to handle?",
                ],
                "quick_actions": [],
                "action_intent": None,
            }

        leader = positive_rows[0]
        leader_driver = str(leader["driver"])
        leader_turn = float(
            leader.get("segment_turn_minutes") or 0
        )
        leader_delta = float(
            leader.get("turn_time_delta_minutes") or 0
        )
        leader_count = int(
            leader.get("appointment_count") or 0
        )

        answer = (
            f"Average realized turn time is "
            f"{float(baseline_turn):.1f} minutes across "
            f"{baseline_count:,} completed appointments with realized turn times. "
            f"The strongest observed "
            f"association is {leader_driver}: those appointments averaged "
            f"{leader_turn:.1f} minutes, {leader_delta:+.1f} minutes versus "
            f"the scoped baseline, across {leader_count:,} appointments. "
            "These are observed associations in the warehouse data, not "
            "proof that a factor directly caused the longer turn time."
        )

        for row in positive_rows[:7]:
            count = int(
                row.get("appointment_count") or 0
            )
            share = float(
                row.get("scope_share_percent") or 0
            )
            segment_turn = float(
                row.get("segment_turn_minutes") or 0
            )
            delta = float(
                row.get("turn_time_delta_minutes") or 0
            )
            sla_miss = float(
                row.get("sla_miss_rate_percent") or 0
            )
            facts.append(
                {
                    "label": str(row["driver"]),
                    "value": (
                        f"{segment_turn:.1f} min · "
                        f"{delta:+.1f} vs baseline · "
                        f"{count:,} appointments ({share:.1f}% of scope) · "
                        f"{sla_miss:.1f}% SLA miss"
                    ),
                }
            )

        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts[:8],
            "suggested_questions": [
                "Compare turn time by carrier",
                "Compare turn time by customer",
                "Are additional loaders improving turn time historically?",
                "Which products have the highest minutes per pallet?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _risk_driver_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        filters = self._subset_filters(
            plan,
            {
                "facility_id",
                "customer_id",
                "carrier_id",
                "appointment_type",
                "date_from",
                "date_to",
            },
        )
        rows = self.analytics_repository.risk_driver_summary(
            limit=plan.limit,
            **filters,
        )
        if not rows:
            return self._response(
                "I did not find predicted SLA misses with measurable "
                "operational drivers in that scope."
            )

        leader = rows[0]
        return {
            "mode": "answer",
            "answer": (
                f"The most common measurable risk driver is "
                f"{leader['driver']}, present on "
                f"{int(leader['affected_appointments'] or 0):,} "
                "predicted-miss appointments. These are correlated operating "
                "conditions used for diagnosis, not proof of a single root cause."
            ),
            "facts": [
                {
                    "label": str(row["driver"]),
                    "value": (
                        f"{int(row['affected_appointments'] or 0):,} appointments"
                    ),
                }
                for row in rows
            ],
            "suggested_questions": [
                "Show the highest-risk appointments",
                "Which docks have the highest average risk?",
                "Rank carriers by SLA miss rate",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _mission_summary_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        row = self.analytics_repository.mission_summary(
            **self._subset_filters(
                plan,
                {"facility_id", "date_from", "date_to"},
            )
        )
        count = int(row.get("mission_count") or 0)
        return {
            "mode": "answer",
            "answer": (
                f"I found {count:,} optimization missions in the requested "
                f"scope: {int(row.get('accepted') or 0):,} Accepted, "
                f"{int(row.get('in_progress') or 0):,} In Progress, and "
                f"{int(row.get('completed') or 0):,} Completed."
            ),
            "facts": [
                {"label": "Missions", "value": f"{count:,}"},
                {
                    "label": "Accepted",
                    "value": f"{int(row.get('accepted') or 0):,}",
                },
                {
                    "label": "In progress",
                    "value": f"{int(row.get('in_progress') or 0):,}",
                },
                {
                    "label": "Completed",
                    "value": f"{int(row.get('completed') or 0):,}",
                },
                {
                    "label": "Projected savings",
                    "value": (
                        f"${float(row.get('projected_net_savings') or 0):,.0f}"
                    ),
                },
                {
                    "label": "Realized savings",
                    "value": (
                        f"${float(row.get('realized_net_savings') or 0):,.0f}"
                    ),
                },
            ],
            "suggested_questions": [
                "Which recovery actions worked best historically?",
                "What are the biggest risk drivers today?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    @staticmethod
    def _action_display_name(action_signature: str) -> str:
        return str(action_signature or "").replace("_", " ").strip().title()

    def _action_effectiveness_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        rows = self.analytics_repository.action_effectiveness(
            facility_id=plan.filters.get("facility_id"),
            limit=max(100, plan.limit),
        )
        if not rows:
            return self._response(
                "No realized action-effectiveness profiles are available "
                "for that scope yet."
            )

        metric = (
            "sla_success_percent"
            if plan.metric == "sla_success_rate"
            else "avg_realized_minutes_saved"
        )
        rows.sort(
            key=lambda row: float(row.get(metric) or 0),
            reverse=True,
        )
        top_rows = rows[:plan.limit]
        leader = top_rows[0]
        leader_name = self._action_display_name(
            str(leader["action_signature"])
        )
        leader_samples = int(leader.get("sample_size") or 0)
        leader_success = float(leader.get("sla_success_percent") or 0)
        leader_minutes = float(
            leader.get("avg_realized_minutes_saved") or 0
        )

        if plan.metric == "sla_success_rate":
            answer = (
                f"{leader_name} currently has the highest historical SLA "
                f"success rate at {leader_success:.1f}%, with "
                f"{leader_minutes:.1f} average realized minutes saved, "
                f"based on {leader_samples:,} observed execution"
                f"{'' if leader_samples == 1 else 's'}."
            )
        else:
            answer = (
                f"{leader_name} currently has the highest historical "
                f"realized minutes saved at {leader_minutes:.1f} minutes "
                f"per observed appointment, with a "
                f"{leader_success:.1f}% SLA success rate, based on "
                f"{leader_samples:,} observed execution"
                f"{'' if leader_samples == 1 else 's'}."
            )

        return {
            "mode": "answer",
            "answer": answer,
            "facts": [
                {
                    "label": self._action_display_name(
                        str(row["action_signature"])
                    ),
                    "value": (
                        f"{float(row.get('avg_realized_minutes_saved') or 0):.1f} "
                        f"min saved · "
                        f"{float(row.get('sla_success_percent') or 0):.1f}% "
                        f"SLA success · "
                        f"${float(row.get('avg_realized_net_savings') or 0):,.0f} "
                        f"avg. savings · "
                        f"{int(row.get('sample_size') or 0):,} samples"
                    ),
                }
                for row in top_rows
            ],
            "suggested_questions": [
                "Which recovery actions have the highest SLA success rate historically?",
                "Which recovery actions save the most minutes historically?",
                "Are additional loaders improving turn time historically?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _product_handling_response(
        self,
        plan: WarehouseQueryPlan,
    ) -> dict[str, Any]:
        rows = self.analytics_repository.product_handling_metrics(
            facility_id=plan.filters.get("facility_id"),
            limit=plan.limit,
        )
        if not rows:
            return self._response(
                "No product handling history matched that scope."
            )

        leader = rows[0]
        return {
            "mode": "answer",
            "answer": (
                f"{leader['product_name']} has the highest historical "
                f"handling time in this scope at "
                f"{float(leader['minutes_per_pallet'] or 0):.2f} "
                "minutes per pallet."
            ),
            "facts": [
                {
                    "label": str(row["product_name"]),
                    "value": (
                        f"{float(row['minutes_per_pallet'] or 0):.2f} min/pallet · "
                        f"{float(row['sla_success_percent'] or 0):.1f}% SLA success"
                    ),
                }
                for row in rows[:8]
            ],
            "suggested_questions": [
                "Which appointments contain the slowest product?",
                "Which products have the lowest SLA success?",
                "What about this facility only?",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _summary_quick_actions(
        self,
        plan: WarehouseQueryPlan,
        count: int,
        critical: int,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        metadata = self._filter_metadata(plan)

        if metadata and count:
            actions.append(
                {
                    "label": "Apply to appointment queue",
                    "action": "filter_appointments",
                    "metadata": metadata,
                }
            )

        if critical:
            critical_metadata = dict(metadata)
            critical_metadata["risk_level"] = "Critical"
            actions.append(
                {
                    "label": f"Show {critical:,} Critical",
                    "action": "filter_appointments",
                    "metadata": critical_metadata,
                }
            )

        actions.extend(
            [
                {
                    "label": "Compare facilities",
                    "action": "ask",
                    "prompt": (
                        "Compare facilities for this operating scope"
                    ),
                    "metadata": {},
                },
                {
                    "label": "Show highest risk",
                    "action": "ask",
                    "prompt": (
                        "Show the five highest-risk appointments "
                        "in this operating scope"
                    ),
                    "metadata": {},
                },
            ]
        )
        return actions[:4]

    def _ranking_quick_actions(
        self,
        plan: WarehouseQueryPlan,
        leader: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        group_id = str(leader.get("group_id") or "")

        if plan.group_by == "facility" and group_id:
            actions.append(
                {
                    "label": "Filter leader facility",
                    "action": "filter_appointments",
                    "metadata": {"facility_id": group_id},
                }
            )

        actions.extend(
            [
                {
                    "label": "Show highest-risk drivers",
                    "action": "ask",
                    "prompt": (
                        "Show the five highest-risk appointments for "
                        f"{leader.get('group_label') or group_id}"
                    ),
                    "metadata": {},
                },
                {
                    "label": "Only inbound",
                    "action": "ask",
                    "prompt": "What about only inbound appointments?",
                    "metadata": {},
                },
                {
                    "label": "Last 30 days",
                    "action": "ask",
                    "prompt": "What about the last 30 days?",
                    "metadata": {},
                },
            ]
        )
        return actions[:4]

    @staticmethod
    def _filter_metadata(
        plan: WarehouseQueryPlan,
    ) -> dict[str, str]:
        mapping = {
            "facility_id": "facility_id",
            "customer_id": "customer_id",
            "carrier_id": "carrier_id",
            "appointment_type": "appointment_type",
            "status": "status",
            "risk_level": "risk_level",
            "pallet_min": "pallet_min",
            "pallet_max": "pallet_max",
            "sku_min": "sku_min",
            "sku_max": "sku_max",
        }

        metadata = {
            target: str(plan.filters[source])
            for source, target in mapping.items()
            if source in plan.filters
            and plan.filters[source] is not None
        }

        date_from = plan.filters.get("date_from")
        date_to = plan.filters.get("date_to")

        if isinstance(date_from, datetime):
            metadata["date_from"] = date_from.date().isoformat()

        if isinstance(date_to, datetime):
            metadata["date_to"] = date_to.date().isoformat()

        return metadata

    @staticmethod
    def _subset_filters(
        plan: WarehouseQueryPlan,
        allowed: set[str],
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in plan.filters.items()
            if key in allowed
        }

    def _resolve_entities(
        self,
        *,
        plan: WarehouseQueryPlan,
        question: str,
        references: dict[str, list[dict[str, Any]]],
    ) -> str | None:
        specs = (
            (
                "facility",
                "facility_id",
                references["facilities"],
            ),
            (
                "customer",
                "customer_id",
                references["customers"],
            ),
            (
                "carrier",
                "carrier_id",
                references["carriers"],
            ),
            (
                "product",
                "product_id",
                references["products"],
            ),
        )

        for entity_name, filter_name, rows in specs:
            match, candidates = self._match_reference(
                question,
                rows,
            )
            if len(candidates) > 1:
                options = ", ".join(
                    f"{row['label']} ({row['id']})"
                    for row in candidates[:5]
                )
                return (
                    f"I found multiple {entity_name} matches: "
                    f"{options}. Which one did you mean?"
                )
            if match:
                plan.filters[filter_name] = str(match["id"])

        return None

    @staticmethod
    def _match_reference(
        question: str,
        rows: list[dict[str, Any]],
    ) -> tuple[
        dict[str, Any] | None,
        list[dict[str, Any]],
    ]:
        normalized = WarehouseQueryPlanner.normalize(question)
        contained: list[tuple[int, dict[str, Any]]] = []

        for row in rows:
            aliases = {
                WarehouseQueryPlanner.normalize(
                    str(row.get("id") or "")
                ),
                WarehouseQueryPlanner.normalize(
                    str(row.get("label") or "")
                ),
                WarehouseQueryPlanner.normalize(
                    str(row.get("sku") or "")
                ),
            }
            aliases.discard("")

            for alias in aliases:
                if len(alias) >= 3 and alias in normalized:
                    contained.append((len(alias), row))
                    break

        if not contained:
            return None, []

        longest = max(
            length
            for length, _ in contained
        )
        best = {
            str(row["id"]): row
            for length, row in contained
            if length == longest
        }
        matches = list(best.values())

        if len(matches) == 1:
            return matches[0], []
        return None, matches

    @staticmethod
    def _metric_label(metric: str) -> str:
        return {
            "appointment_count": "Appointment count",
            "late_appointments": "Late appointments",
            "sla_risk_or_misses": "SLA risk or misses",
            "critical_appointments": "Critical appointments",
            "average_delay_minutes": "Average delay",
            "average_turn_time_minutes": "Average turn time",
            "average_risk_score": "Average risk score",
            "detention_exposure": "Detention exposure",
            "sla_miss_rate_percent": "SLA miss rate",
            "late_rate_percent": "Late arrival rate",
            "average_pallet_count": "Average pallets",
            "average_sku_count": "Average SKUs",
            "average_dock_congestion_percent":
                "Average dock congestion",
            "average_labor_utilization_percent":
                "Average labor utilization",
            "average_forklift_utilization_percent":
                "Average forklift utilization",
        }.get(
            metric,
            metric.replace("_", " ").title(),
        )

    @staticmethod
    def _format_metric(
        metric: str,
        value: Any,
    ) -> str:
        numeric = float(value or 0)

        if metric == "detention_exposure":
            return f"${numeric:,.0f}"
        if metric in {
            "average_delay_minutes",
            "average_turn_time_minutes",
        }:
            return f"{numeric:.1f} min"
        if metric in {
            "sla_miss_rate_percent",
            "late_rate_percent",
            "average_dock_congestion_percent",
            "average_labor_utilization_percent",
            "average_forklift_utilization_percent",
        }:
            return f"{numeric:.1f}%"
        if metric in {
            "average_risk_score",
            "average_pallet_count",
            "average_sku_count",
        }:
            return f"{numeric:.1f}"
        return f"{int(numeric):,}"

    @staticmethod
    def _response(
        answer: str,
    ) -> dict[str, Any]:
        return {
            "mode": "answer",
            "answer": answer,
            "facts": [],
            "suggested_questions": [],
            "quick_actions": [],
            "action_intent": None,
        }