from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CanonicalCopilotQuery:
    domain: str = "appointments"
    intent: str = "summary"
    metric: str = "appointment_count"
    group_by: str | None = None
    sort_direction: str = "desc"
    filters: dict[str, Any] = field(default_factory=dict)
    date_from: datetime | None = None
    date_to: datetime | None = None
    explicit_time: bool = False
    explicit_dimensions: list[str] = field(default_factory=list)
    limit: int = 10
    confidence: float = 0.0
    clarification_needed: bool = False
    clarification_question: str | None = None
    resource_type: str | None = None
    raw_time_expression: str | None = None


    def to_state_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "intent": self.intent,
            "metric": self.metric,
            "group_by": self.group_by,
            "sort_direction": self.sort_direction,
            "filters": dict(self.filters),
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "explicit_time": self.explicit_time,
            "explicit_dimensions": list(self.explicit_dimensions),
            "limit": self.limit,
            "confidence": self.confidence,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "resource_type": self.resource_type,
            "raw_time_expression": self.raw_time_expression,
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, Any] | None):
        if not state:
            return None

        def parse_dt(value):
            if not value:
                return None
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        query = cls(
            domain=str(state.get("domain") or "appointments"),
            intent=str(state.get("intent") or "summary"),
            metric=str(state.get("metric") or "appointment_count"),
            group_by=state.get("group_by"),
            sort_direction=str(state.get("sort_direction") or "desc"),
            filters=dict(state.get("filters") or {}),
            date_from=parse_dt(state.get("date_from")),
            date_to=parse_dt(state.get("date_to")),
            explicit_time=bool(state.get("explicit_time")),
            explicit_dimensions=list(state.get("explicit_dimensions") or []),
            limit=int(state.get("limit") or 10),
            confidence=float(state.get("confidence") or 0),
            clarification_needed=bool(state.get("clarification_needed")),
            clarification_question=state.get("clarification_question"),
            resource_type=state.get("resource_type"),
            raw_time_expression=state.get("raw_time_expression"),
        )
        if query.explicit_time:
            query.apply_dates_to_filters()
        return query

    def apply_dates_to_filters(self) -> None:
        if self.date_from is not None:
            self.filters["date_from"] = self.date_from
        if self.date_to is not None:
            self.filters["date_to"] = self.date_to
