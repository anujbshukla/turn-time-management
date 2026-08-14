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
    understood: bool = False


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

    def plan(
        self,
        question: str,
        *,
        conversation_history: list[Any],
    ) -> WarehouseQueryPlan:
        normalized = self.normalize(question)
        context = self._conversation_context(conversation_history)
        combined = f"{context} {normalized}".strip()

        plan = WarehouseQueryPlan()
        prior = self._latest_follow_up_context(conversation_history)
        plan.filters.update(prior.get("filters", {}))
        if prior.get("group_by"):
            plan.group_by = prior["group_by"]
        if prior.get("metric"):
            plan.metric = prior["metric"]
        if prior.get("limit"):
            plan.limit = prior["limit"]

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
            plan.intent = "summary"
            plan.metric = "appointment_count"
            plan.understood = True

        metric_terms = {
            "late_appointments": (
                "late",
                "late arrival",
                "late appointments",
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
        }

        for metric, phrases in metric_terms.items():
            if self._contains_any(normalized, phrases):
                plan.metric = metric
                plan.understood = True
                break

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
                    ),
                )
            ):
                plan.group_by = group
                plan.intent = "ranking"
                plan.understood = True
                break

        if normalized.startswith("compare "):
            plan.intent = "ranking"
            plan.understood = True

        numeric_limit_match = re.search(
            r"\b(?:show\s+(?:me\s+)?(?:the\s+)?)?"
            r"(?:top|first)\s+(\d{1,2})\b",
            normalized,
        )

        word_limit_match = re.search(
            r"\b(?:show\s+(?:me\s+)?(?:the\s+)?)?"
            r"(?:top|first)\s+("
            + "|".join(self.NUMBER_WORDS.keys())
            + r")\b",
            normalized,
        )

        if numeric_limit_match:
            plan.limit = min(
                25,
                max(
                    1,
                    int(numeric_limit_match.group(1)),
                ),
            )

        elif word_limit_match:
            plan.limit = min(
                25,
                max(
                    1,
                    self.NUMBER_WORDS[
                        word_limit_match.group(1)
                    ],
                ),
            )

        plan.filters.update(
            self._parse_time_filters(combined)
        )

        appointment_type = self._choice(
            combined,
            {
                "inbound": "Inbound",
                "outbound": "Outbound",
            },
        )
        if appointment_type:
            plan.filters["appointment_type"] = (
                appointment_type
            )
            plan.understood = True

        statuses = (
            "Scheduled",
            "En Route",
            "Arrived",
            "Waiting",
            "Dock Assigned",
            "In Progress",
            "Completed",
        )
        for status in statuses:
            if self.normalize(status) in combined:
                plan.filters["status"] = status
                plan.understood = True
                break

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

    def _parse_time_filters(
        self,
        normalized: str,
    ) -> dict[str, datetime]:
        today = datetime.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

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

        if "today" in normalized:
            return {
                "date_from": today,
                "date_to": today + timedelta(days=1),
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
            if "appointment_type" not in filters:
                appointment_type = self._choice(value, {"inbound":"Inbound","outbound":"Outbound"})
                if appointment_type:
                    filters["appointment_type"] = appointment_type
            if "status" not in filters:
                for status in ("Scheduled","En Route","Arrived","Waiting","Dock Assigned","In Progress","Completed"):
                    if self.normalize(status) in value:
                        filters["status"] = status; break
            if "date_from" not in filters:
                time_filters = self._parse_time_filters(value)
                if time_filters:
                    filters.update(time_filters)
            if "group_by" not in context:
                for group, phrases in self.GROUP_TERMS.items():
                    if self._contains_any(value, phrases):
                        context["group_by"] = group; break
            if "limit" not in context:
                match = re.search(r"\b(?:top|first|show)\s+(\d{1,2})\b", value)
                if match:
                    context["limit"] = min(25,max(1,int(match.group(1))))
        return context

    def _conversation_context(
        self,
        history: list[Any],
    ) -> str:
        user_messages = [
            self.normalize(message.content)
            for message in history[-6:]
            if getattr(message, "role", None) == "user"
        ]
        return " ".join(user_messages)

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