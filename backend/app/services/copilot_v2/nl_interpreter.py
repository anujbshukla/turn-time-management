from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, time
from typing import Any

from .models import CanonicalCopilotQuery
from .semantic_catalog import WarehouseSemanticCatalog
from .providers import SemanticProvider, build_semantic_provider


class NaturalLanguageInterpreter:
    SYSTEM_PROMPT = (
        "You are the semantic interpreter for a warehouse data copilot. "
        "Interpret business meaning, not exact phrases. Users may use shorthand, "
        "incorrect grammar, abbreviations, misspellings, or conversational follow-ups. "
        "Never invent entities or fields. Explicit user language overrides prior state; "
        "prior canonical state overrides dashboard defaults. Resolve explicit relative "
        "dates from the supplied current local datetime and use an exclusive date_to. "
        "If time is not mentioned, set explicit_time=false and leave date_from/date_to null. "
        "For analytical metric selection, distinguish a RAW COUNT from a NORMALIZED RATE: "
        "when the user compares or ranks groups by performance (for example carriers, "
        "facilities, customers, or docks) and does not explicitly request a number/count/"
        "total/volume, use the corresponding rate metric. If the user explicitly asks "
        "how many, number, count, total, or volume, use the count metric. "
        "Return canonical dimension values when known. Do not generate SQL."
    )

    APPOINTMENT_TYPE_VALUES = {
        "inbound": "Inbound",
        "outbound": "Outbound",
    }

    RISK_LEVEL_VALUES = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }

    def __init__(
        self,
        provider: SemanticProvider | None = None,
    ) -> None:
        self.catalog = WarehouseSemanticCatalog()
        self._provider = provider

    @property
    def provider(self) -> SemanticProvider:
        if self._provider is None:
            self._provider = build_semantic_provider()
        return self._provider

    def interpret(
        self,
        *,
        question: str,
        now: datetime,
        dashboard_context: dict[str, Any],
        conversation_state: dict[str, Any] | None = None,
        reference_data: dict[str, Any] | None = None,
    ) -> CanonicalCopilotQuery:
        schema = self._schema()
        prompt = (
            self.catalog.prompt_text()
            + "\nCurrent local datetime: "
            + now.isoformat()
            + "\nDashboard defaults: "
            + json.dumps(dashboard_context, default=str)
            + "\nPrior canonical state: "
            + json.dumps(conversation_state or {}, default=str)
            + "\nKnown reference data: "
            + json.dumps(reference_data or {}, default=str)[:12000]
            + "\nUser question: "
            + question
        )

        data = self.provider.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=schema,
        )

        filters = {
            key: value
            for key, value in data["filters"].items()
            if value is not None
        }

        parse_dt = (
            lambda value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if value else None
        )

        query = CanonicalCopilotQuery(
            domain=data["domain"],
            intent=data["intent"],
            metric=data["metric"],
            group_by=data["group_by"],
            sort_direction=data["sort_direction"],
            filters=filters,
            date_from=parse_dt(data["date_from"]),
            date_to=parse_dt(data["date_to"]),
            explicit_time=data["explicit_time"],
            explicit_dimensions=data["explicit_dimensions"],
            limit=data["limit"],
            confidence=data["confidence"],
            clarification_needed=data["clarification_needed"],
            clarification_question=data["clarification_question"],
            resource_type=data["resource_type"],
            raw_time_expression=data["raw_time_expression"],
        )
        # Canonicalize whole-day date windows to half-open intervals:
        # [date_from 00:00, date_to 00:00).
        #
        # The semantic provider may occasionally represent a one-day scope as
        # 00:00 -> 00:00 on the same date or 00:00 -> 23:59 on the same date.
        # Warehouse date filtering always uses the next midnight as the
        # exclusive upper boundary.
        if (
            query.explicit_time
            and query.date_from is not None
            and query.date_to is not None
            and query.date_from.time() == time.min
            and query.date_to.date() == query.date_from.date()
        ):
            query.date_to = query.date_from + timedelta(days=1)
        self._normalize_numeric_bounds(query, question)
        self._normalize_canonical_values(query)

        if query.explicit_time:
            query.apply_dates_to_filters()

        return query

    @staticmethod
    def _normalize_numeric_bounds(
        query: CanonicalCopilotQuery,
        question: str,
    ) -> None:
        """
        Canonicalize integer quantity filters from user language.

        The semantic provider identifies the relevant filter; this layer makes
        strict/inclusive integer boundaries deterministic and idempotent.

        Examples:
          more than 30 pallets -> pallet_min = 31
          at least 20 pallets  -> pallet_min = 20
          under 10 pallets     -> pallet_max = 9
          at most 10 pallets   -> pallet_max = 10

        The same rules apply to SKU counts.
        """
        text = question.casefold()

        dimensions = (
            ("pallet", "pallet_min", "pallet_max"),
            ("sku", "sku_min", "sku_max"),
        )

        operator_patterns = (
            (
                "strict_min",
                r"\b(?:more\s+than|greater\s+than|over)\s+(\d+)\b",
            ),
            (
                "inclusive_min",
                r"\b(?:at\s+least|minimum\s+of|no\s+fewer\s+than)\s+(\d+)\b",
            ),
            (
                "strict_max",
                r"\b(?:under|less\s+than|fewer\s+than|below)\s+(\d+)\b",
            ),
            (
                "inclusive_max",
                r"\b(?:at\s+most|no\s+more\s+than|maximum\s+of)\s+(\d+)\b",
            ),
        )

        for dimension_word, min_key, max_key in dimensions:
            if dimension_word not in text:
                continue

            for operator, pattern in operator_patterns:
                match = re.search(pattern, text)
                if match is None:
                    continue

                threshold = int(match.group(1))

                if operator == "strict_min":
                    query.filters[min_key] = threshold + 1
                    query.filters.pop(max_key, None)
                elif operator == "inclusive_min":
                    query.filters[min_key] = threshold
                    query.filters.pop(max_key, None)
                elif operator == "strict_max":
                    query.filters[max_key] = threshold - 1
                    query.filters.pop(min_key, None)
                elif operator == "inclusive_max":
                    query.filters[max_key] = threshold
                    query.filters.pop(min_key, None)

                break

    @classmethod
    def _normalize_canonical_values(
        cls,
        query: CanonicalCopilotQuery,
    ) -> None:
        """Normalize semantic values, not user phrases, into DB contracts."""
        appointment_type = query.filters.get("appointment_type")
        if isinstance(appointment_type, str):
            canonical = cls.APPOINTMENT_TYPE_VALUES.get(
                appointment_type.strip().casefold()
            )
            if canonical:
                query.filters["appointment_type"] = canonical

        risk_level = query.filters.get("risk_level")
        if isinstance(risk_level, str):
            canonical = cls.RISK_LEVEL_VALUES.get(
                risk_level.strip().casefold()
            )
            if canonical:
                query.filters["risk_level"] = canonical

        if isinstance(query.sort_direction, str):
            query.sort_direction = query.sort_direction.lower()

        if isinstance(query.resource_type, str):
            query.resource_type = query.resource_type.lower()

    @staticmethod
    def _schema() -> dict[str, Any]:
        nullable_string = {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        }
        nullable_int = {
            "anyOf": [
                {"type": "integer"},
                {"type": "null"},
            ]
        }

        filter_props = {
            "facility_id": nullable_string,
            "customer_id": nullable_string,
            "carrier_id": nullable_string,
            "dock_id": nullable_string,
            "assigned_dock_id": nullable_string,
            "appointment_type": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": ["Inbound", "Outbound"],
                    },
                    {"type": "null"},
                ]
            },
            "status": nullable_string,
            "risk_level": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": [
                            "Low",
                            "Medium",
                            "High",
                            "Critical",
                        ],
                    },
                    {"type": "null"},
                ]
            },
            "product_id": nullable_string,
            "load_type": nullable_string,
            "temperature_zone": nullable_string,
            "pallet_band": nullable_string,
            "congestion_band": nullable_string,
            "pallet_min": nullable_int,
            "pallet_max": nullable_int,
            "sku_min": nullable_int,
            "sku_max": nullable_int,
        }

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": list(WarehouseSemanticCatalog.DOMAINS),
                },
                "intent": {
                    "type": "string",
                    "enum": [
                        "summary",
                        "ranking",
                        "top_risk",
                        "risk_drivers",
                        "driver_analysis",
                        "mission_summary",
                        "action_effectiveness",
                        "resource_effectiveness",
                        "product_handling",
                    ],
                },
                "metric": {
                    "type": "string",
                    "enum": list(WarehouseSemanticCatalog.METRICS),
                },
                "group_by": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": [
                                "facility",
                                "customer",
                                "carrier",
                                "dock",
                                "appointment_type",
                                "status",
                                "product",
                            ],
                        },
                        {"type": "null"},
                    ]
                },
                "sort_direction": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                },
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": filter_props,
                    "required": list(filter_props),
                },
                "date_from": nullable_string,
                "date_to": nullable_string,
                "explicit_time": {"type": "boolean"},
                "raw_time_expression": nullable_string,
                "explicit_dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "clarification_needed": {"type": "boolean"},
                "clarification_question": nullable_string,
                "resource_type": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": ["loaders", "forklifts"],
                        },
                        {"type": "null"},
                    ]
                },
            },
            "required": [
                "domain",
                "intent",
                "metric",
                "group_by",
                "sort_direction",
                "filters",
                "date_from",
                "date_to",
                "explicit_time",
                "raw_time_expression",
                "explicit_dimensions",
                "limit",
                "confidence",
                "clarification_needed",
                "clarification_question",
                "resource_type",
            ],
        }