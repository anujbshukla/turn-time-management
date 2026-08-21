from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any
from app.repositories.copilot_analytics_repository import (
    CopilotAnalyticsRepository,
)
from app.services.data_copilot_service import (
    DataCopilotService,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas import (
    AppointmentBookingDraft,
    AppointmentBookingProduct,
    CopilotActionIntent,
    CopilotActionType,
    GlobalCopilotRequest,
)
from app.services.dashboard_service import DashboardService

from app.services.warehouse_agent import (
    WarehouseAgent,
)


class GlobalCopilotService:
    """Dashboard-grounded Copilot with deterministic appointment booking.

    Booking entity resolution is database-grounded and case-insensitive. The
    service resolves customer, carrier, facility, dock and product responses to
    canonical IDs before it ever offers the confirmation action.
    """

    BOOKING_PHRASES = (
        "book appointment",
        "book an appointment",
        "create appointment",
        "create an appointment",
        "schedule appointment",
        "schedule an appointment",
        "new appointment",
    )

    BOOKING_REQUEST_PATTERN = re.compile(
        r"\b(?:book|schedule|create|set\s+up|make)\b"
        r"(?:\s+[a-z0-9-]+){0,5}\s+appointment\b",
        re.IGNORECASE,
    )
    ANALYTICS_FOLLOW_UP_PATTERNS = (
        r"^what about\b",
        r"^how about\b",
        r"^only\b",
        r"^now\b",
        r"^and\b",
        r"^also\b",
        r"^show (?:me )?(?:the )?top\b",
        r"^top\s+\d+\b",
        r"^the top\s+\d+\b",
        r"^(?:today|tomorrow|yesterday)$",
        r"^(?:this|next|last)\s+(?:week|month)$",
        r"^(?:last|past)\s+\d+\s+days?$",
        r"^next\s+\d+\s+hours?$",
        r"^(?:inbound|outbound)$",
        r"^only\s+(?:inbound|outbound)\b",
        r"^sort by\b",
        r"^rank by\b",
        r"^compare (?:that|them|it)\b",
        r"^open (?:the )?(?:first|second|third|top)\b",
    )

    ANALYTICS_ANCHOR_TERMS = (
        "appointment",
        "appointments",
        "facility",
        "facilities",
        "warehouse",
        "carrier",
        "carriers",
        "customer",
        "customers",
        "product",
        "products",
        "dock",
        "docks",
        "risk",
        "critical",
        "sla",
        "delay",
        "late",
        "detention",
        "turn time",
        "recovery",
        "recommendation",
        "utilization",
        "savings",
        "pallet",
        "pallets",
        "sku",
        "skus",
        "loader",
        "loaders",
        "forklift",
        "forklifts",
        "mission",
        "missions",
        "action effectiveness",
        "minutes per pallet",
        "prediction",
        "predictions",
    )

    CONVERSATION_RESET_PHRASES = (
        "new question",
        "start over",
        "reset context",
        "clear context",
        "forget that",
        "different question",
    )
    @classmethod
    def _is_booking_request(cls, normalized_text: str) -> bool:
        """Detect natural booking requests with modifiers between words.

        Examples accepted:
        - book an appointment
        - book an inbound appointment
        - schedule a new outbound warehouse appointment
        - create appointment
        """
        return (
            any(phrase in normalized_text for phrase in cls.BOOKING_PHRASES)
            or cls.BOOKING_REQUEST_PATTERN.search(normalized_text) is not None
        )

    def __init__(
        self,
        repository: DashboardRepository,
    ) -> None:
        self.repository = repository

        self.dashboard_service = DashboardService(
            repository,
        )

        # Create this first because the analytics and booking
        # services both depend on it.
        self.appointment_repository = (
            AppointmentRepository(
                repository.db,
            )
        )

        self.analytics_repository = (
            CopilotAnalyticsRepository(
                repository.db,
            )
        )

        self.data_copilot_service = (
            DataCopilotService(
                analytics_repository=
                    self.analytics_repository,
                appointment_repository=
                    self.appointment_repository,
            )
        )

        self.warehouse_agent = WarehouseAgent(
            data_service=self.data_copilot_service,
            analytics_repository=self.analytics_repository,
            dashboard_service=self.dashboard_service,
            appointment_repository=self.appointment_repository,
)

    def answer(
        self,
        payload: GlobalCopilotRequest,
    ) -> dict[str, Any]:
        dashboard = self.dashboard_service.get_dashboard(
            payload.facility_id,
        )

        question = payload.question.strip()
        normalized = question.casefold()

        # Booking is a data-changing workflow and always takes priority.
        if (
            payload.booking_draft is not None
            or self._is_booking_request(normalized)
        ):
            return self._handle_booking(payload, question)

        # Explicit dashboard actions with concrete identifiers execute before
        # analytics. Ordinal actions such as "open the first appointment"
        # are resolved by WarehouseAgent using the prior analytical result.
        action_intent = self._detect_action(normalized, dashboard)
        if action_intent is not None:
            return {
                "mode": "action",
                "answer": action_intent.response_message,
                "facts": self._action_facts(action_intent),
                "suggested_questions": self._suggestions(
                    action_intent.action
                ),
                "quick_actions": [],
                "action_intent": action_intent,
            }

        contextual_payload = self._build_contextual_analytics_payload(
            payload
        )
        agent_answer = self.warehouse_agent.answer(contextual_payload)
        if agent_answer is not None:
            return agent_answer

        answer, facts = self._build_answer(normalized, dashboard)
        return {
            "mode": "answer",
            "answer": answer,
            "facts": facts,
            "suggested_questions": [
                "Book a new appointment",
                "How many appointments are scheduled tomorrow?",
                "Which facility has the most Critical appointments?",
                "Rank carriers by average delay",
                "Show the highest-risk appointments",
            ],
            "quick_actions": [],
            "action_intent": None,
        }

    def _build_contextual_analytics_payload(
        self,
        payload: GlobalCopilotRequest,
    ) -> GlobalCopilotRequest:
        """Return a request with the active analytics thread resolved.

        GlobalCopilotService is created once per HTTP request, so state
        cannot safely live in an instance dictionary. The frontend-provided
        conversation history is the source of conversational state.
        """

        current_question = payload.question.strip()

        if self._contains_reset_phrase(
            current_question
        ):
            cleaned_question = (
                self._remove_reset_phrase(
                    current_question
                )
            )

            return payload.model_copy(
                update={
                    "question":
                        cleaned_question
                        or current_question,
                    "conversation_history": [],
                },
                deep=True,
            )

        if not self._is_analytics_follow_up(
            current_question
        ):
            return payload

        analytical_thread = (
            self._extract_analytics_thread(
                payload
            )
        )

        if not analytical_thread:
            return payload

        contextual_question = (
            self._compose_contextual_question(
                analytical_thread,
                current_question,
            )
        )

        return payload.model_copy(
            update={
                "question": contextual_question,
            },
            deep=True,
        )

    def _extract_analytics_thread(
        self,
        payload: GlobalCopilotRequest,
    ) -> list[str]:
        """Find the most recent analytical question and its follow-ups."""

        user_messages = [
            message.content.strip()
            for message in payload.conversation_history
            if message.role == "user"
            and message.content.strip()
        ]

        if not user_messages:
            return []

        # Limit context so an old topic cannot accidentally contaminate
        # a later analytical question.
        recent_messages = user_messages[-12:]

        anchor_index: int | None = None

        for index in range(
            len(recent_messages) - 1,
            -1,
            -1,
        ):
            message = recent_messages[index]

            if self._contains_reset_phrase(message):
                break

            if self._is_booking_request(
                message.casefold()
            ):
                break

            if self._is_analytics_anchor(message):
                anchor_index = index
                break

        if anchor_index is None:
            return []

        thread: list[str] = []

        for message in recent_messages[
            anchor_index:
        ]:
            if self._contains_reset_phrase(message):
                break

            if self._is_booking_request(
                message.casefold()
            ):
                break

            if (
                self._is_analytics_anchor(message)
                or self._is_analytics_follow_up(
                    message
                )
            ):
                thread.append(message)

        return thread

    def _compose_contextual_question(
        self,
        previous_messages: list[str],
        current_question: str,
    ) -> str:
        """Convert short follow-ups into one complete analytical request."""

        unique_messages: list[str] = []

        for message in [
            *previous_messages,
            current_question,
        ]:
            cleaned = message.strip()

            if not cleaned:
                continue

            if (
                cleaned.casefold()
                not in {
                    value.casefold()
                    for value
                    in unique_messages
                }
            ):
                unique_messages.append(cleaned)

        if not unique_messages:
            return current_question

        anchor = unique_messages[0]
        modifications = unique_messages[1:]

        if not modifications:
            return anchor

        return (
            f"Original analytical request: {anchor}. "
            "Apply these follow-up refinements in order: "
            + "; ".join(modifications)
            + ". Preserve the original metric, grouping, "
              "entity scope and filters unless a refinement "
              "explicitly changes them."
        )

    def _is_analytics_follow_up(
        self,
        question: str,
    ) -> bool:
        normalized = self._normalize(question)

        if not normalized:
            return False

        return any(
            re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            )
            is not None
            for pattern
            in self.ANALYTICS_FOLLOW_UP_PATTERNS
        )

    def _is_analytics_anchor(
        self,
        question: str,
    ) -> bool:
        normalized = self._normalize(question)

        if not normalized:
            return False

        if self._is_analytics_follow_up(question):
            return False

        if self._is_booking_request(
            normalized
        ):
            return False

        has_entity_or_metric = any(
            term in normalized
            for term
            in self.ANALYTICS_ANCHOR_TERMS
        )

        has_analytical_language = any(
            phrase in normalized
            for phrase in (
                "how many",
                "which",
                "what",
                "show",
                "list",
                "rank",
                "compare",
                "highest",
                "lowest",
                "most",
                "least",
                "average",
                "total",
                "count",
                "top",
                "why",
            )
        )

        return (
            has_entity_or_metric
            and has_analytical_language
        )

    def _contains_reset_phrase(
        self,
        question: str,
    ) -> bool:
        normalized = self._normalize(question)

        return any(
            phrase in normalized
            for phrase
            in self.CONVERSATION_RESET_PHRASES
        )

    def _remove_reset_phrase(
        self,
        question: str,
    ) -> str:
        cleaned = question

        for phrase in (
            "new question:",
            "new question",
            "different question:",
            "different question",
            "start over:",
            "start over",
        ):
            cleaned = re.sub(
                re.escape(phrase),
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

        return cleaned.strip(" .,:;-")

    def _handle_booking(
        self,
        payload: GlobalCopilotRequest,
        question: str,
    ) -> dict[str, Any]:
        normalized = self._normalize(question)

        if any(
            phrase in normalized
            for phrase in (
                "cancel booking",
                "cancel appointment booking",
                "never mind",
                "nevermind",
                "stop booking",
            )
        ):
            intent = CopilotActionIntent(
                action=CopilotActionType.BOOK_APPOINTMENT,
                confirmation_required=False,
                response_message="The appointment booking draft has been cancelled. No appointment was created.",
                metadata={"booking_state": "cancelled"},
                booking_draft=None,
            )
            return {
                "mode": "action",
                "answer": intent.response_message,
                "facts": [],
                "suggested_questions": self._suggestions(intent.action),
                "action_intent": intent,
            }

        draft = (
            payload.booking_draft.model_copy(deep=True)
            if payload.booking_draft is not None
            else AppointmentBookingDraft()
        )
        references = self.appointment_repository.get_reference_data()

        ambiguity = self._update_booking_draft(
            draft=draft,
            question=question,
            references=references,
        )
        if ambiguity:
            return self._booking_prompt_response(draft, ambiguity)

        missing_prompt = self._next_booking_prompt(draft, references)
        if missing_prompt:
            return self._booking_prompt_response(draft, missing_prompt)

        intent = CopilotActionIntent(
            action=CopilotActionType.BOOK_APPOINTMENT,
            confirmation_required=True,
            response_message=(
                "I mapped every response to the current warehouse master data. "
                "Review the booking summary and confirm before I create the appointment."
            ),
            metadata={"booking_state": "ready"},
            booking_draft=draft,
        )
        return {
            "mode": "action",
            "answer": intent.response_message,
            "facts": self._booking_facts(draft),
            "suggested_questions": [
                "Change the scheduled time",
                "Change the carrier",
                "Add another product",
                "Cancel booking",
            ],
            "action_intent": intent,
        }

    def _booking_prompt_response(
        self,
        draft: AppointmentBookingDraft,
        prompt: str,
    ) -> dict[str, Any]:
        intent = CopilotActionIntent(
            action=CopilotActionType.BOOK_APPOINTMENT,
            confirmation_required=False,
            response_message=prompt,
            metadata={"booking_state": "collecting"},
            booking_draft=draft,
        )
        return {
            "mode": "action",
            "answer": prompt,
            "facts": self._booking_facts(draft),
            "suggested_questions": [],
            "action_intent": intent,
        }

    def _update_booking_draft(
        self,
        *,
        draft: AppointmentBookingDraft,
        question: str,
        references: dict[str, list[dict[str, Any]]],
    ) -> str | None:
        normalized = self._normalize(question)

        # Product and quantity are collected separately. A product can first
        # be resolved exactly or suggested from a partial name, then Copilot
        # asks for its quantity in a separate turn.
        if draft.pending_product_id:
            quantity_only = re.fullmatch(
                r"(?:quantity\s*(?:is|=|:)?\s*)?(\d{1,6})(?:\s+units?)?",
                normalized.strip(),
            )

            if draft.pending_product_quantity is None and quantity_only:
                quantity = max(1, int(quantity_only.group(1)))
                existing = next(
                    (
                        item
                        for item in draft.products
                        if item.product_id == draft.pending_product_id
                    ),
                    None,
                )
                if existing:
                    existing.quantity = quantity
                    existing.product_label = draft.pending_product_label
                    existing.sku = draft.pending_product_sku
                else:
                    draft.products.append(
                        AppointmentBookingProduct(
                            product_id=draft.pending_product_id,
                            quantity=quantity,
                            product_label=draft.pending_product_label,
                            sku=draft.pending_product_sku,
                        )
                    )
                self._clear_pending_product(draft)
                return None

            if self._is_affirmative(normalized):
                if draft.pending_product_quantity is not None:
                    self._upsert_booking_product(
                        draft=draft,
                        product_id=draft.pending_product_id,
                        product_label=draft.pending_product_label,
                        product_sku=draft.pending_product_sku,
                        quantity=draft.pending_product_quantity,
                    )
                    self._clear_pending_product(draft)
                    return None

                return (
                    f"What quantity of {draft.pending_product_label or draft.pending_product_id} "
                    "should I add?"
                )

            if self._is_negative(normalized):
                self._clear_pending_product(draft)
                return (
                    "No problem. Which product should be booked? Enter a product "
                    "name, SKU, or product ID. I will ask for quantity next."
                )

            # A new non-quantity response replaces the pending suggestion.
            self._clear_pending_product(draft)

        entity_specs = (
            ("facility", references["facilities"]),
            ("customer", references["customers"]),
            ("carrier", references["carriers"]),
        )
        for entity_name, rows in entity_specs:
            match, candidates = self._resolve_reference(
                question,
                rows,
                aliases=("id", "label"),
            )
            if len(candidates) > 1:
                return self._ambiguity_message(entity_name, candidates)
            if match is not None:
                previous_id = getattr(draft, f"{entity_name}_id")
                setattr(draft, f"{entity_name}_id", str(match["id"]))
                setattr(draft, f"{entity_name}_label", str(match["label"]))
                if entity_name == "facility" and previous_id != str(match["id"]):
                    draft.assigned_dock_id = None
                    draft.assigned_dock_label = None

        # A dock must belong to the resolved facility. This prevents "Dock 1"
        # at one facility from being mapped to a similarly named dock elsewhere.
        dock_rows = references["docks"]
        if draft.facility_id:
            dock_rows = [
                row
                for row in dock_rows
                if row.get("facility_id") == draft.facility_id
            ]
        dock_match, dock_candidates = self._resolve_reference(
            question,
            dock_rows,
            aliases=("id", "label"),
        )
        if len(dock_candidates) > 1:
            return self._ambiguity_message("dock", dock_candidates)
        if dock_match is not None:
            draft.assigned_dock_id = str(dock_match["id"])
            draft.assigned_dock_label = str(dock_match["label"])

        scheduled_time = self._parse_scheduled_time(question)
        if scheduled_time is not None:
            draft.scheduled_time = scheduled_time

        appointment_type = self._choice_from_text(
            normalized,
            {
                "inbound": "Inbound",
                "outbound": "Outbound",
            },
        )
        if appointment_type:
            draft.appointment_type = appointment_type

        load_type = self._choice_from_text(
            normalized,
            {
                "palletized": "Palletized",
                "floor loaded": "Floor Loaded",
                "floor-loaded": "Floor Loaded",
                "full truckload": "Full Truckload",
                "ftl": "Full Truckload",
                "less than truckload": "LTL",
                "ltl": "LTL",
            },
        )
        if load_type:
            draft.load_type = load_type

        priority_match = re.search(r"\bpriority\s*(?:is|=|:)?\s*([1-5])\b", normalized)
        if priority_match:
            draft.priority = int(priority_match.group(1))

        sla_match = re.search(r"\bsla(?:\s+minutes?)?\s*(?:is|=|:)?\s*(\d{2,4})\b", normalized)
        if sla_match:
            draft.sla_minutes = min(1440, max(15, int(sla_match.group(1))))

        detention_match = re.search(
            r"\bdetention(?:\s+cost)?(?:\s*/?\s*hour)?\s*(?:is|=|:|\$)?\s*(\d+(?:\.\d+)?)",
            normalized,
        )
        if detention_match:
            draft.detention_cost_per_hour = max(0.0, float(detention_match.group(1)))

        product_matches = self._resolve_products(question, references["products"])

        explicit_quantity = self._extract_explicit_quantity(question)

        suggestion = product_matches.get("suggestion")
        if suggestion is not None:
            product = suggestion
            draft.pending_product_id = str(product["id"])
            draft.pending_product_label = str(product["label"])
            draft.pending_product_sku = str(product.get("sku") or "")
            draft.pending_product_quantity = explicit_quantity

            quantity_suffix = (
                f" with quantity {explicit_quantity}"
                if explicit_quantity is not None
                else ""
            )
            return (
                f"Did you mean {product['label']} ({product['id']})"
                f"{quantity_suffix}? Reply yes to select it, or no to choose "
                "a different product."
            )

        if product_matches["ambiguous"]:
            return self._ambiguity_message("product", product_matches["ambiguous"])

        resolved_products = product_matches["resolved"]
        if resolved_products:
            product = resolved_products[0]
            if explicit_quantity is not None:
                self._upsert_booking_product(
                    draft=draft,
                    product_id=str(product["id"]),
                    product_label=str(product["label"]),
                    product_sku=str(product.get("sku") or ""),
                    quantity=explicit_quantity,
                )
                self._clear_pending_product(draft)
                return None

            draft.pending_product_id = str(product["id"])
            draft.pending_product_label = str(product["label"])
            draft.pending_product_sku = str(product.get("sku") or "")
            draft.pending_product_quantity = None
            return (
                f"What quantity of {product['label']} should I add?"
            )

        return None


    def _next_booking_prompt(
        self,
        draft: AppointmentBookingDraft,
        references: dict[str, list[dict[str, Any]]],
    ) -> str | None:
        if not draft.customer_id:
            return (
                "Which customer is this appointment for? You can enter the "
                "customer name or customer ID; capitalization does not matter."
            )
        if not draft.appointment_type:
            return (
                "Is this an Inbound or Outbound appointment? "
                "Please reply with either Inbound or Outbound."
            )
        if not draft.carrier_id:
            return (
                "Which carrier will handle the appointment? Enter the carrier "
                "name or carrier ID."
            )
        if not draft.facility_id:
            choices = ", ".join(
                str(row["label"]) for row in references["facilities"][:5]
            )
            return (
                "Which facility should receive the appointment? Enter its name "
                f"or ID. Available examples: {choices}."
            )
        if draft.scheduled_time is None:
            return (
                "What date and time should I schedule it for? For example: "
                "'August 7 at 10:30 AM' or 'tomorrow at 2 PM'."
            )
        if draft.pending_product_id:
            return (
                f"What quantity of {draft.pending_product_label or draft.pending_product_id} "
                "should I add?"
            )
        if not draft.products:
            return (
                "Which product should be booked? Enter a product name, SKU, or "
                "product ID. I will ask for the quantity separately."
            )
        return None

    @classmethod
    def _normalize(cls, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_value = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        return " ".join(
            re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).split()
        )

    def _resolve_reference(
        self,
        text: str,
        rows: list[dict[str, Any]],
        *,
        aliases: tuple[str, ...],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        normalized_text = self._normalize(text)
        if not normalized_text:
            return None, []

        exact: list[dict[str, Any]] = []
        contained: list[tuple[int, dict[str, Any]]] = []

        for row in rows:
            row_aliases = {
                self._normalize(str(row.get(alias) or ""))
                for alias in aliases
            }
            row_aliases.discard("")
            if normalized_text in row_aliases:
                exact.append(row)
                continue
            for alias in row_aliases:
                if len(alias) >= 3 and re.search(
                    rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                    normalized_text,
                ):
                    contained.append((len(alias), row))
                    break

        if len(exact) == 1:
            return exact[0], []
        if len(exact) > 1:
            return None, self._dedupe_rows(exact)

        if contained:
            longest = max(length for length, _ in contained)
            best = self._dedupe_rows(
                [row for length, row in contained if length == longest]
            )
            if len(best) == 1:
                return best[0], []
            return None, best

        return None, []

    def _resolve_products(
        self,
        text: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_text = self._normalize(text)
        matches: list[tuple[int, dict[str, Any], str]] = []

        for row in rows:
            label = str(row.get("label") or "")
            product_name = label.split("·", 1)[0].strip()
            aliases = {
                self._normalize(str(row.get("id") or "")),
                self._normalize(str(row.get("sku") or "")),
                self._normalize(label),
                self._normalize(product_name),
            }
            aliases.discard("")
            for alias in aliases:
                if len(alias) >= 3 and re.search(
                    rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                    normalized_text,
                ):
                    matches.append((len(alias), row, alias))
                    break

        if matches:
            longest_by_product: dict[str, tuple[int, dict[str, Any], str]] = {}
            for item in matches:
                product_id = str(item[1]["id"])
                if (
                    product_id not in longest_by_product
                    or item[0] > longest_by_product[product_id][0]
                ):
                    longest_by_product[product_id] = item

            selected = list(longest_by_product.values())
            if len(selected) > 1:
                aliases = {alias for _, _, alias in selected}
                if len(aliases) == 1:
                    return {
                        "resolved": [],
                        "ambiguous": [row for _, row, _ in selected],
                        "suggestion": None,
                    }

            return {
                "resolved": [row for _, row, _ in selected],
                "ambiguous": [],
                "suggestion": None,
            }

        # Exact direct answer by canonical product ID, SKU or complete label.
        match, ambiguous = self._resolve_reference(
            text,
            rows,
            aliases=("id", "label", "sku"),
        )
        if match:
            return {
                "resolved": [match],
                "ambiguous": [],
                "suggestion": None,
            }
        if ambiguous:
            return {"resolved": [], "ambiguous": ambiguous, "suggestion": None}

        # Partial product-name matching. This deliberately does not auto-map:
        # the user must confirm the candidate before it is added to the draft.
        #
        # First inspect the full sentence for a contiguous product-name prefix.
        # This allows a single prompt such as:
        # "Book an appointment for Quick Commerce 13 tomorrow at 12 PM EST
        #  for Dairy Product 13"
        # to populate customer, schedule and product in one request.
        sentence_candidates: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            label = str(row.get("label") or "")
            product_name = label.split("·", 1)[0].strip()
            normalized_name = self._normalize(product_name)
            name_tokens = normalized_name.split()
            if not name_tokens:
                continue

            # Prefer the longest matching prefix, but require at least two
            # meaningful tokens unless the product name itself is one token.
            minimum_tokens = 1 if len(name_tokens) == 1 else 2
            for token_count in range(len(name_tokens), minimum_tokens - 1, -1):
                prefix = " ".join(name_tokens[:token_count])
                if len(prefix) < 4:
                    continue
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(prefix)}(?![a-z0-9])",
                    normalized_text,
                ):
                    sentence_candidates.append((token_count, row))
                    break

        if sentence_candidates:
            longest = max(length for length, _ in sentence_candidates)
            candidates = self._dedupe_rows(
                [row for length, row in sentence_candidates if length == longest]
            )
            if len(candidates) == 1:
                candidate = candidates[0]
                candidate_name = self._normalize(
                    str(candidate.get("label") or "").split("·", 1)[0].strip()
                )
                # Exact full-name mentions are resolved directly. Shortened
                # prefixes are offered as a confirmation instead of guessed.
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(candidate_name)}(?![a-z0-9])",
                    normalized_text,
                ):
                    return {
                        "resolved": [candidate],
                        "ambiguous": [],
                        "suggestion": None,
                    }
                return {
                    "resolved": [],
                    "ambiguous": [],
                    "suggestion": candidate,
                }
            return {
                "resolved": [],
                "ambiguous": candidates,
                "suggestion": None,
            }

        query = self._product_query_text(normalized_text)
        if len(query) >= 3:
            query_tokens = query.split()
            prefix_candidates: list[dict[str, Any]] = []
            token_candidates: list[dict[str, Any]] = []

            for row in rows:
                label = str(row.get("label") or "")
                product_name = label.split("·", 1)[0].strip()
                normalized_name = self._normalize(product_name)
                if not normalized_name:
                    continue

                if normalized_name.startswith(query):
                    prefix_candidates.append(row)
                    continue

                name_tokens = normalized_name.split()
                if all(
                    any(name_token.startswith(query_token) for name_token in name_tokens)
                    for query_token in query_tokens
                ):
                    token_candidates.append(row)

            candidates = self._dedupe_rows(prefix_candidates or token_candidates)
            if len(candidates) == 1:
                return {
                    "resolved": [],
                    "ambiguous": [],
                    "suggestion": candidates[0],
                }
            if len(candidates) > 1:
                return {
                    "resolved": [],
                    "ambiguous": candidates,
                    "suggestion": None,
                }

        return {"resolved": [], "ambiguous": [], "suggestion": None}

    @classmethod
    def _product_query_text(cls, normalized_text: str) -> str:
        value = re.sub(
            r"\b(?:quantity|qty)\b\s*(?:is|=|:|x)?\s*\d+\b",
            " ",
            normalized_text,
        )
        value = re.sub(r"\b\d+\s+units?\b", " ", value)
        value = re.sub(r"\bunits?\s+\d+\b", " ", value)
        value = re.sub(r"\b(?:add|book|include|item)\b", " ", value)
        return " ".join(value.split())

    @staticmethod
    def _is_affirmative(normalized_text: str) -> bool:
        return normalized_text in {
            "yes", "y", "yeah", "yep", "correct", "confirm", "that one",
            "yes please", "right", "thats right", "that is right",
        }

    @staticmethod
    def _is_negative(normalized_text: str) -> bool:
        return normalized_text in {
            "no", "n", "nope", "incorrect", "not that one", "different product",
        }

    @staticmethod
    def _clear_pending_product(draft: AppointmentBookingDraft) -> None:
        draft.pending_product_id = None
        draft.pending_product_label = None
        draft.pending_product_sku = None
        draft.pending_product_quantity = None

    @staticmethod
    def _extract_explicit_quantity(text: str) -> int | None:
        normalized = GlobalCopilotService._normalize(text)
        patterns = (
            r"\b(?:quantity|qty)\s*(?:is|=|:|x)?\s*(\d{1,6})\b",
            r"\bx\s*(\d{1,6})\b",
            r"\b(\d{1,6})\s+units?\b",
            r"\bunits?\s*(?:is|=|:)?\s*(\d{1,6})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return max(1, int(match.group(1)))
        return None

    @staticmethod
    def _upsert_booking_product(
        *,
        draft: AppointmentBookingDraft,
        product_id: str,
        product_label: str | None,
        product_sku: str | None,
        quantity: int,
    ) -> None:
        existing = next(
            (item for item in draft.products if item.product_id == product_id),
            None,
        )
        if existing is not None:
            existing.quantity = quantity
            existing.product_label = product_label
            existing.sku = product_sku
            return

        draft.products.append(
            AppointmentBookingProduct(
                product_id=product_id,
                quantity=quantity,
                product_label=product_label,
                sku=product_sku,
            )
        )

    def _extract_quantity(self, text: str, alias: str) -> int:
        normalized = self._normalize(text)
        patterns = []
        if alias:
            patterns.extend(
                (
                    rf"(?:quantity\s*)?(\d{{1,6}})\s*(?:units?\s*)?(?:of\s*)?{re.escape(alias)}",
                    rf"{re.escape(alias)}\s*(?:quantity|qty|x)?\s*(\d{{1,6}})",
                )
            )
        patterns.extend(
            (
                r"\bquantity\s*(?:is|=|:)?\s*(\d{1,6})\b",
                r"\bqty\s*(?:is|=|:)?\s*(\d{1,6})\b",
            )
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return max(1, int(match.group(1)))
        return 1

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique[str(row["id"])] = row
        return list(unique.values())

    @staticmethod
    def _ambiguity_message(
        entity_name: str,
        candidates: list[dict[str, Any]],
    ) -> str:
        choices = ", ".join(
            f"{row['label']} ({row['id']})"
            for row in candidates[:5]
        )
        return (
            f"I found multiple {entity_name} matches: {choices}. "
            f"Please reply with the exact {entity_name} name or ID."
        )

    @staticmethod
    def _choice_from_text(
        normalized_text: str,
        choices: dict[str, str],
    ) -> str | None:
        for phrase, value in choices.items():
            if phrase in normalized_text:
                return value
        return None

    def _parse_scheduled_time(self, text: str) -> datetime | None:
        normalized = text.casefold()
        now = datetime.now()
        target_date = None

        # Check the more specific relative phrases first because
        # "day after tomorrow" also contains the word "tomorrow".
        if re.search(
            r"\b(?:the\s+)?day\s+after\s+tomorrow\b|\bin\s+(?:2|two)\s+days?\b|\b(?:2|two)\s+days?\s+from\s+now\b",
            normalized,
        ):
            target_date = (now + timedelta(days=2)).date()
        elif re.search(r"\btomorrow\b", normalized):
            target_date = (now + timedelta(days=1)).date()
        elif re.search(r"\btoday\b", normalized):
            target_date = now.date()

        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized)
        slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}|\d{2}))?\b", normalized)
        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
            r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b",
            normalized,
        )

        try:
            if iso_match:
                target_date = datetime(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3)),
                ).date()
            elif slash_match:
                year_text = slash_match.group(3)
                year = now.year if not year_text else int(year_text)
                if year < 100:
                    year += 2000
                target_date = datetime(
                    year,
                    int(slash_match.group(1)),
                    int(slash_match.group(2)),
                ).date()
            elif month_match:
                month_number = {
                    name.casefold(): index
                    for index, name in enumerate(
                        (
                            "",
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        )
                    )
                    if name
                }[month_match.group(1)]
                year = int(month_match.group(3) or now.year)
                target_date = datetime(
                    year,
                    month_number,
                    int(month_match.group(2)),
                ).date()
        except ValueError:
            return None

        time_match = re.search(
            r"\b(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
            normalized,
        )
        military_match = re.search(r"\b(?:at\s*)?([01]?\d|2[0-3]):([0-5]\d)\b", normalized)

        hour = minute = None
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if hour < 1 or hour > 12:
                return None
            if time_match.group(3) == "pm" and hour != 12:
                hour += 12
            if time_match.group(3) == "am" and hour == 12:
                hour = 0
        elif military_match:
            hour = int(military_match.group(1))
            minute = int(military_match.group(2))

        if target_date is None or hour is None or minute is None:
            return None
        return datetime.combine(
            target_date,
            datetime.min.time(),
        ).replace(hour=hour, minute=minute)

    @staticmethod
    def _booking_facts(
        draft: AppointmentBookingDraft,
    ) -> list[dict[str, str]]:
        facts: list[dict[str, str]] = []
        values = (
            ("Customer", draft.customer_label),
            ("Carrier", draft.carrier_label),
            ("Facility", draft.facility_label),
            ("Dock", draft.assigned_dock_label),
            (
                "Scheduled",
                draft.scheduled_time.strftime("%b %d, %Y at %I:%M %p")
                if draft.scheduled_time
                else None,
            ),
            ("Type", draft.appointment_type),
            ("Load type", draft.load_type),
            ("SLA", f"{draft.sla_minutes} min"),
            ("Detention", f"${draft.detention_cost_per_hour:,.0f}/hour"),
        )
        for label, value in values:
            if value:
                facts.append({"label": label, "value": str(value)})
        if draft.products:
            facts.append(
                {
                    "label": "Products",
                    "value": ", ".join(
                        f"{item.product_label or item.product_id} × {item.quantity}"
                        for item in draft.products
                    ),
                }
            )
        return facts

    def _detect_action(
        self,
        question: str,
        dashboard: dict[str, Any],
    ) -> CopilotActionIntent | None:
        appointment_match = re.search(r"\b(?:app|appt)[-_ ]?\d+\b", question, re.I)
        if appointment_match and any(
            phrase in question
            for phrase in ("open", "show", "view", "go to")
        ):
            appt_id = appointment_match.group(0).upper().replace(" ", "")
            if appt_id.startswith("APPT"):
                appt_id = "APP" + appt_id[4:]
            return CopilotActionIntent(
                action=CopilotActionType.OPEN_APPOINTMENT,
                confirmation_required=False,
                response_message=f"I found {appt_id}. Open its appointment intelligence drawer?",
                metadata={"appt_id": appt_id},
            )

        if any(phrase in question for phrase in ("clear filter", "clear filters", "show all appointments")):
            return CopilotActionIntent(
                action=CopilotActionType.FILTER_APPOINTMENTS,
                confirmation_required=False,
                response_message="I can clear the appointment queue filters and return to the full operating view.",
                metadata={"clear": "true"},
            )

        risk_level = next(
            (level for level in ("critical", "high", "medium", "low") if level in question),
            None,
        )
        status = next(
            (value for value in ("scheduled", "arrived", "waiting", "in progress", "completed") if value in question),
            None,
        )
        if any(
            phrase in question
            for phrase in (
                "show only",
                "filter",
                "filter to",
                "filter by",
                "limit to",
                "only show",
            )
        ) and (risk_level or status):
            metadata: dict[str, str] = {}
            if risk_level:
                metadata["risk_level"] = risk_level.title()
            if status:
                metadata["status"] = status.title()
            description = " and ".join(f"{key.replace('_', ' ')}: {value}" for key, value in metadata.items())
            return CopilotActionIntent(
                action=CopilotActionType.FILTER_APPOINTMENTS,
                confirmation_required=False,
                response_message=f"I can focus the appointment queue on {description}.",
                metadata=metadata,
            )

        if any(phrase in question for phrase in ("what if", "simulate", "run a scenario", "run scenario")):
            loaders = self._extract_resource_count(question, "loader")
            forklifts = self._extract_resource_count(question, "forklift")
            pre_stage = any(phrase in question for phrase in ("pre-stage", "prestage", "stage products"))
            if loaders == 0 and forklifts == 0 and not pre_stage:
                loaders = 1
                forklifts = 1
            return CopilotActionIntent(
                action=CopilotActionType.RUN_WHAT_IF,
                confirmation_required=False,
                response_message=(
                    "I prepared a portfolio-wide recovery scenario. Run it to update the KPI cards, charts and savings comparison."
                ),
                metadata={
                    "extra_loaders": str(loaders),
                    "extra_forklifts": str(forklifts),
                    "pre_stage_products": "true" if pre_stage else "false",
                },
            )

        return None

    @staticmethod
    def _extract_resource_count(question: str, resource: str) -> int:
        patterns = (
            rf"(\d+)\s+(?:extra\s+)?{resource}s?",
            rf"{resource}s?\s*[:=]?\s*(\d+)",
        )
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return min(5, max(0, int(match.group(1))))
        return 0

    def _build_answer(
        self,
        question: str,
        dashboard: dict[str, Any],
    ) -> tuple[str, list[dict[str, str]]]:
        summary = dashboard["summary"]
        reasons = dashboard.get("delay_sla_reasons", [])
        plans = dashboard.get("recovery_plan_performance", [])
        savings = dashboard.get("recommendation_savings", {})
        high_risk = dashboard.get("high_risk_appointments", [])

        if any(term in question for term in ("why", "reason", "root cause", "sla miss", "late")):
            top = sorted(reasons, key=lambda row: (row.get("sla_misses", 0), row.get("late_appointments", 0)), reverse=True)[:3]
            if not top:
                return "The current dashboard does not contain enough root-cause data to explain late arrivals or SLA misses.", []
            details = "; ".join(
                f"{row['reason']} ({row['late_appointments']} late, {row['sla_misses']} SLA misses)"
                for row in top
            )
            leader = top[0]
            return (
                f"The leading operational cause is {leader['reason']}. The top contributors are {details}. Use the root-cause table to compare delay duration and affected docks.",
                [
                    {"label": "Top cause", "value": leader["reason"]},
                    {"label": "Late appointments", "value": str(leader["late_appointments"])},
                    {"label": "SLA misses", "value": str(leader["sla_misses"])},
                ],
            )

        if any(term in question for term in ("recovery plan", "most effective", "helpful", "best action", "most used")):
            if not plans:
                return "Recovery-plan performance is not available in the current dashboard data.", []
            most_used = max(plans, key=lambda row: row.get("times_used", 0))
            most_effective = max(plans, key=lambda row: (row.get("success_rate") or 0, row.get("net_savings") or 0))
            return (
                f"{most_used['recovery_plan']} is the most used plan with {most_used['times_used']} executions. {most_effective['recovery_plan']} is currently the most effective at {most_effective.get('success_rate') or 0:.1f}% success and ${float(most_effective.get('net_savings') or 0):,.0f} net savings.",
                [
                    {"label": "Most used", "value": most_used["recovery_plan"]},
                    {"label": "Most effective", "value": most_effective["recovery_plan"]},
                    {"label": "Success rate", "value": f"{most_effective.get('success_rate') or 0:.1f}%"},
                ],
            )

        if any(term in question for term in ("saving", "savings", "roi", "value", "cost", "detention")):
            net = float(savings.get("net_savings") or 0)
            gross = float(savings.get("gross_savings") or 0)
            roi = float(savings.get("roi") or 0)
            reduction = float(savings.get("cost_reduction_percent") or 0)
            return (
                f"Recommendations have generated ${net:,.0f} in estimated net savings from ${gross:,.0f} gross savings. The current recommendation ROI is {roi:.1f}× and detention-related operating impact is down {reduction:.1f}%.",
                [
                    {"label": "Net savings", "value": f"${net:,.0f}"},
                    {"label": "Gross savings", "value": f"${gross:,.0f}"},
                    {"label": "ROI", "value": f"{roi:.1f}×"},
                ],
            )

        if any(term in question for term in ("attention", "risk", "critical", "priority")):
            top = high_risk[:5]
            critical_count = next((row["appointment_count"] for row in dashboard.get("risk_distribution", []) if row["risk_level"].lower() == "critical"), 0)
            ids = ", ".join(row["appt_id"] for row in top) if top else "none currently listed"
            return (
                f"{critical_count} appointments are classified as Critical risk. The highest-priority appointments are {ids}. Review these first because they combine elevated turn risk with predicted SLA exposure.",
                [
                    {"label": "Critical risk", "value": str(critical_count)},
                    {"label": "SLA misses", "value": str(summary["sla_misses"])},
                    {"label": "Detention exposure", "value": f"${float(summary.get('detention_exposure') or 0):,.0f}"},
                ],
            )

        recovery_rate = (
            summary["late_turned_on_time"] / summary["late_arrivals"] * 100
            if summary["late_arrivals"]
            else 0
        )
        return (
            f"The current portfolio contains {summary['total_appointments']} appointments, with {summary['late_arrivals']} late arrivals and {summary['sla_misses']} SLA misses. Operations recovered {summary['late_turned_on_time']} late turns, a {recovery_rate:.1f}% recovery rate. Ask me to explain causes, compare recovery plans, quantify savings, filter the queue or run a What-If scenario.",
            [
                {"label": "Appointments", "value": f"{summary['total_appointments']:,}"},
                {"label": "Late arrivals", "value": f"{summary['late_arrivals']:,}"},
                {"label": "SLA misses", "value": f"{summary['sla_misses']:,}"},
                {"label": "Recovery rate", "value": f"{recovery_rate:.1f}%"},
            ],
        )

    @staticmethod
    def _action_facts(intent: CopilotActionIntent) -> list[dict[str, str]]:
        labels = {
            "risk_level": "Risk filter",
            "status": "Status filter",
            "appt_id": "Appointment",
            "extra_loaders": "Extra loaders",
            "extra_forklifts": "Extra forklifts",
            "pre_stage_products": "Pre-stage products",
            "clear": "Filter action",
        }
        return [
            {"label": labels.get(key, key.replace("_", " ").title()), "value": "Yes" if value == "true" else value}
            for key, value in intent.metadata.items()
        ]

    @staticmethod
    def _suggestions(action: CopilotActionType) -> list[str]:
        if action == CopilotActionType.FILTER_APPOINTMENTS:
            return ["Clear filters", "Show only Critical appointments", "Summarize the filtered risk"]
        if action == CopilotActionType.OPEN_APPOINTMENT:
            return ["Why is this appointment at risk?", "Show only Critical appointments"]
        if action == CopilotActionType.RUN_WHAT_IF:
            return ["How much could this scenario save?", "Why are SLAs being missed?"]
        if action == CopilotActionType.BOOK_APPOINTMENT:
            return ["Book a new appointment", "Show only Critical appointments"]
        return ["Book a new appointment", "Summarize today's warehouse performance"]
