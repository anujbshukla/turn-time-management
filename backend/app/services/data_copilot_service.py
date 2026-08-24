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
from app.services.data_copilot_responses import DataCopilotResponseMixin


class DataCopilotService(DataCopilotResponseMixin):
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

