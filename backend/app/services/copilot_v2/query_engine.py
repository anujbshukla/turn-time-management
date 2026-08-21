from __future__ import annotations

from app.config import get_settings
from datetime import datetime
from typing import Any

from .legacy_bridge import LegacyPlanBridge
from .models import CanonicalCopilotQuery
from .nl_interpreter import NaturalLanguageInterpreter
from .query_validator import CanonicalQueryValidator


class NaturalLanguageQueryEngine:
    def __init__(self) -> None:
        self.interpreter = NaturalLanguageInterpreter()
        self.validator = CanonicalQueryValidator()

    @property
    def enabled(self) -> bool:
        return get_settings().copilot_nl_v2_enabled

    @staticmethod
    def merge_with_prior_state(
        current: CanonicalCopilotQuery,
        prior: CanonicalCopilotQuery | None,
    ) -> CanonicalCopilotQuery:
        if prior is None:
            return current

        explicit = set(current.explicit_dimensions or [])

        # Conversation-state precedence:
        #
        #   explicit current-turn dimension
        #       >
        #   meaningful changed current value
        #       >
        #   prior canonical state
        #
        # Semantic providers may emit schema defaults for dimensions the user did
        # not mention, and may occasionally omit explicit_dimensions for a genuine
        # change. Defaults therefore do not overwrite prior state unless explicitly
        # requested.

        SEMANTIC_DEFAULTS = {
            "domain": "appointments",
            "intent": "summary",
            "metric": "appointment_count",
            "group_by": None,
            "resource_type": None,
        }


        def merge_dimension(field_name: str) -> None:
            current_value = getattr(current, field_name, None)
            prior_value = getattr(prior, field_name, None)
            default_value = SEMANTIC_DEFAULTS[field_name]

            # Explicit current-turn change always wins.
            if field_name in explicit:
                return

            # No actual change.
            if current_value == prior_value:
                return

            # A changed non-default semantic value is meaningful even if the
            # provider omitted the explicit-dimension marker.
            if current_value != default_value:
                explicit.add(field_name)
                return

            # Otherwise the provider most likely emitted its schema/default value.
            setattr(current, field_name, prior_value)


        for field_name in (
            "domain",
            "intent",
            "metric",
            "group_by",
            "resource_type",
        ):
            merge_dimension(field_name)

        current.explicit_dimensions = sorted(explicit)

        merged_filters = dict(prior.filters)
        merged_filters.update(current.filters)
        current.filters = merged_filters

        if not current.explicit_time:
            current.date_from = prior.date_from
            current.date_to = prior.date_to

        if current.date_from is not None:
            current.filters["date_from"] = current.date_from
        else:
            current.filters.pop("date_from", None)

        if current.date_to is not None:
            current.filters["date_to"] = current.date_to
        else:
            current.filters.pop("date_to", None)

        return current

    def plan(
        self,
        *,
        question: str,
        payload: Any,
        reference_data: dict[str, Any],
        conversation_state: dict[str, Any] | None = None,
        now: datetime | None = None,
    ):
        prior = CanonicalCopilotQuery.from_state_dict(
            conversation_state
        )

        canonical = self.interpreter.interpret(
            question=question,
            now=now or datetime.now().astimezone(),
            dashboard_context=LegacyPlanBridge.dashboard_context(
                payload
            ),
            conversation_state=conversation_state or {},
            reference_data=reference_data,
        )

        canonical = self.merge_with_prior_state(
            canonical,
            prior,
        )
        canonical = self.validator.validate(canonical)

        return (
            canonical,
            LegacyPlanBridge.to_legacy_plan(canonical),
        )
