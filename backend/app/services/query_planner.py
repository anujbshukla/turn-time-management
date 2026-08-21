from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class WarehouseQueryPlan:
    intent: str = "summary"
    metric: str = "appointment_count"
    group_by: str | None = None
    limit: int = 5
    filters: dict[str, Any] = field(default_factory=dict)
    resource_type: str | None = None
    ranking_direction: str = "desc"
    ignore_request_date_context: bool = False
    understood: bool = False

    # Used when the user compares two independent time periods.
    # Example:
    #   "Total appointments last Thursday vs today"
    comparison_a: dict[str, Any] | None = None
    comparison_b: dict[str, Any] | None = None


class WarehouseQueryPlanner:
    NUMBER_WORDS = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }

    GROUP_TERMS = {
        "facility": (
            "facility",
            "facilities",
            "warehouse",
            "warehouses",
            "distribution center",
        ),
        "carrier": (
            "carrier",
            "carriers",
            "transport company",
        ),
        "customer": (
            "customer",
            "customers",
            "client",
            "clients",
        ),
        "dock": (
            "dock",
            "docks",
        ),
        "product": (
            "product",
            "products",
            "item",
            "items",
            "sku",
            "skus",
        ),
        "status": (
            "status",
            "statuses",
        ),
        "appointment_type": (
            "appointment type",
            "inbound vs outbound",
            "inbound and outbound",
        ),
    }

    METRIC_TERMS = {
        "late_appointments": (
            "late appointments",
            "late arrival",
            "late arrivals",
        ),
        "sla_miss_rate_percent": (
            "sla miss rate",
            "sla miss percentage",
            "percentage missed sla",
            "percent missed sla",
            "what percentage",
            "percentage of appointments",
        ),
        "sla_risk_or_misses": (
            "sla miss",
            "missed sla",
            "sla misses",
            "service level",
        ),
        "critical_appointments": (
            "critical",
            "critical risk",
        ),
        "average_delay_minutes": (
            "average delay",
            "avg delay",
            "most delayed",
            "highest delay",
        ),
        "average_turn_time_minutes": (
            "average turn",
            "avg turn",
            "turn time",
            "longest turn",
            "slowest",
        ),
        "detention_exposure": (
            "detention",
            "detention exposure",
            "detention cost",
        ),
        "average_risk_score": (
            "average risk",
            "avg risk",
            "risk score",
        ),
        "late_rate_percent": (
            "late arrival rate",
            "late arrivals rate",
            "late percentage",
            "percentage late",
            "percent late",
            "on-time arrival rate",
            "on time arrival rate",
            "on-time rate",
            "on time rate",
            "arrival reliability",
            "arrival punctuality",
            "punctuality",
            "arrival performance",
            "most punctual",
            "least on-time",
            "least on time",
            "most late",
            "worst on-time",
            "worst on time",
        ),
        "average_pallet_count": (
            "average pallets",
            "avg pallets",
            "pallet volume",
        ),
        "average_sku_count": (
            "average skus",
            "avg skus",
            "sku complexity",
        ),
        "average_dock_congestion_percent": (
            "average congestion",
            "dock congestion",
            "congestion",
        ),
        "average_labor_utilization_percent": (
            "labor utilization",
            "loader utilization",
        ),
        "average_forklift_utilization_percent": (
            "forklift utilization",
        ),
    }

    def plan(
        self,
        question: str,
        *,
        conversation_history: list[Any],
    ) -> WarehouseQueryPlan:
        normalized = self.normalize(question)
        prior = self._latest_follow_up_context(
            conversation_history
        )

        plan = WarehouseQueryPlan()
        plan.filters.update(prior.get("filters", {}))
        if prior.get("intent"):
            plan.intent = prior["intent"]
        if prior.get("resource_type"):
            plan.resource_type = prior["resource_type"]
        if prior.get("group_by"):
            plan.group_by = prior["group_by"]
        if prior.get("metric"):
            plan.metric = prior["metric"]
        if prior.get("limit"):
            plan.limit = prior["limit"]
        if prior.get("ignore_request_date_context"):
            plan.ignore_request_date_context = True

        temporal_comparison = self._parse_temporal_comparison(
            normalized
        )

        explicit_time = (
            {}
            if temporal_comparison
            else self._parse_time_filters(normalized)
        )

        if temporal_comparison:
            comparison_a, comparison_b = temporal_comparison

            plan.intent = "temporal_comparison"
            plan.comparison_a = comparison_a
            plan.comparison_b = comparison_b

            # Temporal comparison replaces any inherited date range,
            # while preserving non-date operating filters.
            plan.filters.pop("date_from", None)
            plan.filters.pop("date_to", None)

            plan.ignore_request_date_context = True
            plan.understood = True

        historical_scope = self._contains_any(
            normalized,
            (
                "historically",
                "historical",
                "all history",
                "full history",
                "entire history",
                "over time",
                "across history",
            ),
        )
        if historical_scope and not explicit_time:
            plan.filters.pop("date_from", None)
            plan.filters.pop("date_to", None)
            plan.ignore_request_date_context = True
            plan.understood = True

        # Specialized warehouse analytical tools.
        if self._contains_any(
            normalized,
            (
                "recovery action worked best",
                "recovery actions worked best",
                "recovery action has worked best",
                "recovery actions have worked best",
                "recovery action has actually worked best",
                "recovery actions have actually worked best",
                "recommendations actually worked",
                "ai recommendations actually worked",
                "actions have been most effective",
                "actions were most effective",
                "recovery strategies have the best outcomes",
                "recovery strategies had the best outcomes",
                "actions improve sla recovery the most",
                "actions improved sla recovery the most",
                "best recovery action",
                "best recovery actions",
                "most effective recovery action",
                "most effective recovery actions",
                "action effectiveness",
                "actions actually worked",
                "recovery effectiveness",
                "highest sla success",
                "best sla success",
                "sla success rate historically",
                "sla recovery rate historically",
                "highest sla recovery",
                "best sla recovery",
            ),
        ):
            plan.intent = "action_effectiveness"
            plan.metric = (
                "sla_success_rate"
                if self._contains_any(
                    normalized,
                    (
                        "highest sla success",
                        "best sla success",
                        "sla success rate",
                        "sla recovery rate",
                        "highest sla recovery",
                        "best sla recovery",
                    ),
                )
                else "avg_realized_minutes_saved"
            )
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "additional loaders",
                "more loaders",
                "extra loaders",
                "loader effectiveness",
                "loaders improve",
                "loader allocation",
            ),
        ):
            plan.intent = "resource_effectiveness"
            plan.resource_type = "loaders"
            plan.metric = "average_turn_time_minutes"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "additional forklifts",
                "more forklifts",
                "extra forklifts",
                "forklift effectiveness",
                "forklifts improve",
                "forklift allocation",
            ),
        ):
            plan.intent = "resource_effectiveness"
            plan.resource_type = "forklifts"
            plan.metric = "average_turn_time_minutes"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "what factors are driving high turn time",
                "what factors are driving high turn times",
                "what is driving high turn time",
                "what is driving high turn times",
                "what drives high turn time",
                "what drives high turn times",
                "turn time drivers",
                "turn-time drivers",
                "drivers of turn time",
                "drivers of high turn time",
                "drivers of high turn times",
                "why are turn times high",
                "why is turn time high",
                "why are appointments taking longer",
                "why do appointments take longer",
                "what makes appointments take longer",
                "what factors affect turn time",
                "what factors affect turn times",
            ),
        ):
            plan.intent = "driver_analysis"
            plan.metric = "average_turn_time_minutes"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "why are appointments predicted late",
                "why are they predicted late",
                "why are appointments at risk",
                "what is driving risk",
                "what is driving the risk",
                "biggest reasons",
                "top reasons",
                "risk drivers",
                "delay drivers",
            ),
        ):
            plan.intent = "risk_drivers"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "active missions",
                "optimization missions",
                "recovery missions",
                "missions are active",
                "mission status",
                "completed missions",
            ),
        ):
            plan.intent = "mission_summary"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "product handling history",
                "minutes per pallet",
                "slowest products",
                "fastest products",
                "historical product handling",
            ),
        ):
            plan.intent = "product_handling"
            plan.group_by = "product"
            plan.metric = "minutes_per_pallet"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "highest risk appointment",
                "highest risk appointments",
                "most critical appointment",
                "appointments need attention",
                "appointments needing attention",
                "top risk appointment",
            ),
        ):
            plan.intent = "top_risk"
            plan.metric = "risk_score"
            plan.understood = True

        if self._contains_any(
            normalized,
            (
                "how many",
                "number of",
                "count of",
                "total appointments",
                "appointments are",
            ),
        ):
            if plan.intent == "summary":
                plan.metric = "appointment_count"
            plan.understood = True

        current_metric = self._metric_from_text(normalized)
        if current_metric:
            plan.metric = current_metric
            plan.understood = True

        # Ranking semantics: normalize positive punctuality wording onto
        # late_rate_percent, then choose the direction that matches the user's
        # intent. "Worst on-time" == highest late rate; "best on-time" ==
        # lowest late rate.
        if plan.metric == "late_rate_percent":
            if self._contains_any(
                normalized,
                (
                    "best on-time",
                    "best on time",
                    "highest on-time",
                    "highest on time",
                    "most on-time",
                    "most on time",
                    "best arrival reliability",
                    "best punctuality",
                    "most punctual",
                    "least late",
                    "lowest late",
                    "lowest late arrival rate",
                ),
            ):
                plan.ranking_direction = "asc"
            else:
                plan.ranking_direction = "desc"

        for group, phrases in self.GROUP_TERMS.items():
            if (
                self._contains_any(normalized, phrases)
                and self._contains_any(
                    normalized,
                    (
                        "by ",
                        "which ",
                        "rank",
                        "compare",
                        "highest",
                        "lowest",
                        "most",
                        "least",
                        "top",
                        "worst",
                        "best",
                    ),
                )
            ):
                plan.group_by = group
                if plan.intent == "summary":
                    plan.intent = "ranking"
                plan.understood = True
                break

        if (
            normalized.startswith("compare ")
            and plan.intent != "temporal_comparison"
        ):
            plan.intent = "ranking"
            plan.understood = True

        self._parse_limit(normalized, plan)

        # Explicit current-question time wins over prior conversation context.
        current_time = explicit_time
        if current_time:
            plan.filters.update(current_time)
            plan.ignore_request_date_context = False
            plan.understood = True

        appointment_type = self._choice(
            normalized,
            {
                "inbound": "Inbound",
                "outbound": "Outbound",
            },
        )
        if appointment_type:
            plan.filters["appointment_type"] = appointment_type
            plan.understood = True

        for status in (
            "Scheduled",
            "En Route",
            "Arrived",
            "Waiting",
            "Dock Assigned",
            "In Progress",
            "Completed",
        ):
            if self.normalize(status) in normalized:
                plan.filters["status"] = status
                plan.understood = True
                break

        self._parse_numeric_filters(
            normalized,
            plan.filters,
        )
        if any(
            key in plan.filters
            for key in (
                "pallet_min",
                "pallet_max",
                "sku_min",
                "sku_max",
            )
        ):
            plan.understood = True

        if plan.intent == "ranking" and plan.group_by:
            self._clear_group_dimension_filter(plan)

        return plan

    @classmethod
    def normalize(cls, value: str) -> str:
        decomposed = unicodedata.normalize(
            "NFKD",
            value,
        )
        ascii_value = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        return " ".join(
            re.sub(
                r"[^a-z0-9]+",
                " ",
                ascii_value.casefold(),
            ).split()
        )
    @staticmethod
    def _weekday_date(
        today: datetime,
        weekday_name: str,
        *,
        force_previous: bool = False,
    ) -> datetime | None:
        weekday_indexes = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        target_weekday = weekday_indexes.get(weekday_name)
        if target_weekday is None:
            return None

        days_back = (today.weekday() - target_weekday) % 7

        if force_previous and days_back == 0:
            days_back = 7

        return today - timedelta(days=days_back)
    def _parse_temporal_comparison(
        self,
        normalized: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        separators = (
            r"\s+vs\.?\s+",
            r"\s+versus\s+",
            r"\s+compared\s+(?:with|to)\s+",
        )

        parts: list[str] | None = None

        for separator in separators:
            split = re.split(
                separator,
                normalized,
                maxsplit=1,
            )
            if len(split) == 2:
                parts = split
                break

        # Support:
        # "compare yesterday to today"
        # "compare last Wednesday with today"
        if parts is None and normalized.startswith("compare "):
            comparison_text = normalized[len("compare "):]

            split = re.split(
                r"\s+(?:with|to)\s+",
                comparison_text,
                maxsplit=1,
            )

            if len(split) == 2:
                parts = split

        if not parts:
            return None

        left_text, right_text = parts

        left_range = self._parse_time_filters(left_text)
        right_range = self._parse_time_filters(right_text)

        if not left_range or not right_range:
            return None

        return (
            {
                "label": self._comparison_period_label(left_text),
                **left_range,
            },
            {
                "label": self._comparison_period_label(right_text),
                **right_range,
            },
        )

    @staticmethod
    def _comparison_period_label(value: str) -> str:
        normalized = " ".join(value.split())

        weekday_match = re.search(
            r"\b(last\s+)?"
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            normalized,
        )

        if weekday_match:
            prefix = "Last " if weekday_match.group(1) else ""
            return f"{prefix}{weekday_match.group(2).title()}"

        for phrase, label in (
            ("day after tomorrow", "Day after tomorrow"),
            ("yesterday", "Yesterday"),
            ("today", "Today"),
            ("tomorrow", "Tomorrow"),
            ("last week", "Last week"),
            ("this week", "This week"),
            ("next week", "Next week"),
            ("last month", "Last month"),
            ("this month", "This month"),
        ):
            if phrase in normalized:
                return label

        return normalized.title()

    def _parse_time_filters(
        self,
        normalized: str,
    ) -> dict[str, datetime]:
        now = datetime.now().replace(
            second=0,
            microsecond=0,
        )
        today = now.replace(
            hour=0,
            minute=0,
        )
        weekday_match = re.search(
            r"\b(last\s+)?"
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            normalized,
        )

        if weekday_match:
            force_previous = bool(weekday_match.group(1))
            weekday_name = weekday_match.group(2)

            start = self._weekday_date(
                today,
                weekday_name,
                force_previous=force_previous,
            )

            if start is not None:
                return {
                    "date_from": start,
                    "date_to": start + timedelta(days=1),
                }
        hours_match = re.search(
            r"\bnext\s+(\d{1,3})\s+hours?\b",
            normalized,
        )
        if hours_match:
            hours = max(
                1,
                min(168, int(hours_match.group(1))),
            )
            return {
                "date_from": now,
                "date_to": now + timedelta(hours=hours),
            }

        days_match = re.search(
            r"\b(?:last|past)\s+(\d{1,3})\s+days?\b",
            normalized,
        )
        if days_match:
            days = max(
                1,
                min(365, int(days_match.group(1))),
            )
            return {
                "date_from": today - timedelta(days=days - 1),
                "date_to": today + timedelta(days=1),
            }

        if "day after tomorrow" in normalized:
            start = today + timedelta(days=2)
            return {
                "date_from": start,
                "date_to": start + timedelta(days=1),
            }

        if "tomorrow" in normalized:
            start = today + timedelta(days=1)
            return {
                "date_from": start,
                "date_to": start + timedelta(days=1),
            }

        if "yesterday" in normalized:
            return {
                "date_from": today - timedelta(days=1),
                "date_to": today,
            }

        if "today" in normalized:
            return {
                "date_from": today,
                "date_to": today + timedelta(days=1),
            }

        if "this month" in normalized:
            start = today.replace(day=1)
            if start.month == 12:
                end = start.replace(
                    year=start.year + 1,
                    month=1,
                )
            else:
                end = start.replace(month=start.month + 1)
            return {
                "date_from": start,
                "date_to": end,
            }

        if "last month" in normalized:
            this_month = today.replace(day=1)
            prior_day = this_month - timedelta(days=1)
            return {
                "date_from": prior_day.replace(day=1),
                "date_to": this_month,
            }

        if "this week" in normalized:
            start = today - timedelta(
                days=today.weekday()
            )
            return {
                "date_from": start,
                "date_to": start + timedelta(days=7),
            }

        if "next week" in normalized:
            start = (
                today
                - timedelta(days=today.weekday())
                + timedelta(days=7)
            )
            return {
                "date_from": start,
                "date_to": start + timedelta(days=7),
            }

        return {}

    def _latest_follow_up_context(
        self,
        history: list[Any],
    ) -> dict[str, Any]:
        context: dict[str, Any] = {"filters": {}}

        for message in reversed(history[-12:]):
            if getattr(message, "role", None) != "user":
                continue

            value = self.normalize(message.content)
            filters = context["filters"]

            if "intent" not in context:
                if self._contains_any(
                    value,
                    (
                        "recovery action worked best",
                        "recovery actions worked best",
                        "recovery action has worked best",
                        "recovery actions have worked best",
                        "recovery action has actually worked best",
                        "recovery actions have actually worked best",
                        "best recovery action",
                        "best recovery actions",
                        "most effective recovery action",
                        "most effective recovery actions",
                        "action effectiveness",
                        "actions actually worked",
                        "recommendations actually worked",
                        "ai recommendations actually worked",
                        "actions have been most effective",
                        "actions were most effective",
                        "recovery strategies have the best outcomes",
                        "recovery strategies had the best outcomes",
                        "actions improve sla recovery the most",
                        "actions improved sla recovery the most",
                        "recovery effectiveness",
                    ),
                ):
                    context["intent"] = "action_effectiveness"
                elif self._contains_any(
                    value,
                    (
                        "additional loaders",
                        "more loaders",
                        "extra loaders",
                        "loader effectiveness",
                        "loaders improve",
                        "loader allocation",
                    ),
                ):
                    context["intent"] = "resource_effectiveness"
                    context["resource_type"] = "loaders"
                elif self._contains_any(
                    value,
                    (
                        "additional forklifts",
                        "more forklifts",
                        "extra forklifts",
                        "forklift effectiveness",
                        "forklifts improve",
                        "forklift allocation",
                    ),
                ):
                    context["intent"] = "resource_effectiveness"
                    context["resource_type"] = "forklifts"

            if "ignore_request_date_context" not in context:
                history_time = self._parse_time_filters(value)
                history_is_unbounded = self._contains_any(
                    value,
                    (
                        "historically",
                        "historical",
                        "all history",
                        "full history",
                        "entire history",
                        "over time",
                        "across history",
                    ),
                )
                if history_is_unbounded and not history_time:
                    context["ignore_request_date_context"] = True

            if "appointment_type" not in filters:
                appointment_type = self._choice(
                    value,
                    {
                        "inbound": "Inbound",
                        "outbound": "Outbound",
                    },
                )
                if appointment_type:
                    filters["appointment_type"] = appointment_type

            if "status" not in filters:
                for status in (
                    "Scheduled",
                    "En Route",
                    "Arrived",
                    "Waiting",
                    "Dock Assigned",
                    "In Progress",
                    "Completed",
                ):
                    if self.normalize(status) in value:
                        filters["status"] = status
                        break

            if "date_from" not in filters:
                time_filters = self._parse_time_filters(value)
                if time_filters:
                    filters.update(time_filters)

            self._parse_numeric_filters(value, filters)

            if "group_by" not in context:
                for group, phrases in self.GROUP_TERMS.items():
                    if self._contains_any(value, phrases):
                        context["group_by"] = group
                        break

            if "metric" not in context:
                metric = self._metric_from_text(value)
                if metric:
                    context["metric"] = metric

            if "limit" not in context:
                match = re.search(
                    r"\b(?:top|first|show)\s+(\d{1,2})\b",
                    value,
                )
                if match:
                    context["limit"] = min(
                        25,
                        max(1, int(match.group(1))),
                    )

        return context

    @staticmethod
    def _clear_group_dimension_filter(
        plan: WarehouseQueryPlan,
    ) -> None:
        """Do not constrain the dimension the user is explicitly comparing.

        Dashboard context remains the default for all unrelated dimensions.
        """
        group_filter_map = {
            "facility": ("facility_id",),
            "carrier": ("carrier_id",),
            "customer": ("customer_id",),
            "appointment_type": ("appointment_type",),
            "dock": (
                "dock_id",
                "assigned_dock_id",
            ),
            "status": ("status",),
            "product": ("product_id",),
        }
        for filter_name in group_filter_map.get(
            plan.group_by or "",
            (),
        ):
            plan.filters.pop(filter_name, None)

    def _parse_limit(
        self,
        normalized: str,
        plan: WarehouseQueryPlan,
    ) -> None:
        numeric_match = re.search(
            r"\b(?:show\s+(?:me\s+)?(?:the\s+)?)?"
            r"(?:top|first)\s+(\d{1,2})\b",
            normalized,
        )
        word_match = re.search(
            r"\b(?:show\s+(?:me\s+)?(?:the\s+)?)?"
            r"(?:top|first)\s+("
            + "|".join(self.NUMBER_WORDS.keys())
            + r")\b",
            normalized,
        )

        if numeric_match:
            plan.limit = min(
                25,
                max(1, int(numeric_match.group(1))),
            )
        elif word_match:
            plan.limit = min(
                25,
                max(
                    1,
                    self.NUMBER_WORDS[word_match.group(1)],
                ),
            )

    @staticmethod
    def _parse_numeric_filters(
        normalized: str,
        filters: dict[str, Any],
    ) -> None:
        patterns = (
            (
                "pallet_min",
                r"\b(?:more than|over|greater than)\s+(\d+)\s+pallet",
                lambda value: value + 1,
            ),
            (
                "pallet_min",
                r"\bat least\s+(\d+)\s+pallet",
                lambda value: value,
            ),
            (
                "pallet_max",
                r"\b(?:fewer than|less than|under)\s+(\d+)\s+pallet",
                lambda value: max(0, value - 1),
            ),
            (
                "sku_min",
                r"\b(?:more than|over|greater than)\s+(\d+)\s+(?:sku|skus)",
                lambda value: value + 1,
            ),
            (
                "sku_min",
                r"\bat least\s+(\d+)\s+(?:sku|skus)",
                lambda value: value,
            ),
            (
                "sku_max",
                r"\b(?:fewer than|less than|under)\s+(\d+)\s+(?:sku|skus)",
                lambda value: max(0, value - 1),
            ),
        )
        for key, pattern, transform in patterns:
            match = re.search(pattern, normalized)
            if match:
                filters[key] = transform(
                    int(match.group(1))
                )

    def _metric_from_text(
        self,
        value: str,
    ) -> str | None:
        for metric, phrases in self.METRIC_TERMS.items():
            if self._contains_any(value, phrases):
                return metric
        return None

    @staticmethod
    def _contains_any(
        value: str,
        phrases: tuple[str, ...],
    ) -> bool:
        return any(
            phrase in value
            for phrase in phrases
        )

    @staticmethod
    def _choice(
        value: str,
        choices: dict[str, str],
    ) -> str | None:
        for phrase, mapped in choices.items():
            if phrase in value:
                return mapped
        return None
