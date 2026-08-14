from __future__ import annotations

import re
from typing import Any

from app.schemas import (
    CopilotActionIntent,
    CopilotActionType,
)


class CopilotIntentDetector:
    """
    Deterministic intent detector for the Warehouse Copilot.

    It interprets action-oriented commands without modifying
    the database. The returned intent can later be presented
    to the user for confirmation.
    """

    def detect(
        self,
        *,
        question: str,
        actions: list[dict[str, Any]] | None = None,
    ) -> CopilotActionIntent:
        normalized = self._normalize(question)
        available_actions = actions or []

        if self._is_accept_command(normalized):
            action_ids = self._resolve_action_ids(
                question=normalized,
                actions=available_actions,
            )

            return CopilotActionIntent(
                action=CopilotActionType.ACCEPT_ACTIONS,
                action_ids=action_ids,
                confirmation_required=True,
                response_message=(
                    self._build_decision_message(
                        decision="accept",
                        action_ids=action_ids,
                        actions=available_actions,
                    )
                ),
                metadata={
                    "decision_status": "Accepted",
                },
            )

        if self._is_reject_command(normalized):
            action_ids = self._resolve_action_ids(
                question=normalized,
                actions=available_actions,
            )

            return CopilotActionIntent(
                action=CopilotActionType.REJECT_ACTIONS,
                action_ids=action_ids,
                confirmation_required=True,
                response_message=(
                    self._build_decision_message(
                        decision="reject",
                        action_ids=action_ids,
                        actions=available_actions,
                    )
                ),
                metadata={
                    "decision_status": "Rejected",
                },
            )

        if self._is_what_if_command(normalized):
            return CopilotActionIntent(
                action=CopilotActionType.RUN_WHAT_IF,
                action_ids=self._resolve_action_ids(
                    question=normalized,
                    actions=available_actions,
                ),
                confirmation_required=False,
                response_message=(
                    "I can run a What-If simulation using "
                    "the selected recovery actions and resource changes."
                ),
                metadata=self._extract_what_if_metadata(
                    normalized
                ),
            )

        if self._is_filter_command(normalized):
            return CopilotActionIntent(
                action=(
                    CopilotActionType
                    .FILTER_APPOINTMENTS
                ),
                action_ids=[],
                confirmation_required=False,
                response_message=(
                    "I identified an appointment filter "
                    "request."
                ),
                metadata=self._extract_filter_metadata(
                    normalized
                ),
            )

        if self._is_open_command(normalized):
            appointment_id = (
                self._extract_appointment_id(
                    normalized
                )
            )

            return CopilotActionIntent(
                action=CopilotActionType.OPEN_APPOINTMENT,
                action_ids=[],
                confirmation_required=False,
                response_message=(
                    f"I can open appointment {appointment_id}."
                    if appointment_id
                    else (
                        "Please provide the appointment ID "
                        "you want to open."
                    )
                ),
                metadata=(
                    {"appt_id": appointment_id}
                    if appointment_id
                    else {}
                ),
            )

        return CopilotActionIntent(
            action=CopilotActionType.ANSWER,
            action_ids=[],
            confirmation_required=False,
            response_message=(
                "This is an informational question."
            ),
            metadata={},
        )

    def _normalize(
        self,
        question: str,
    ) -> str:
        return " ".join(
            question
            .strip()
            .lower()
            .replace("recommendations", "actions")
            .replace("recommendation", "action")
            .split()
        )

    def _is_accept_command(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "accept ",
                "approve ",
                "apply ",
                "use the action",
                "take the action",
                "implement the action",
            )
        )

    def _is_reject_command(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "reject ",
                "decline ",
                "do not use",
                "don't use",
                "remove the action",
                "skip the action",
            )
        )

    def _is_what_if_command(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "what if",
                "simulate",
                "simulation",
                "run scenario",
                "model the impact",
                "show the impact",
            )
        )

    def _is_filter_command(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "filter ",
                "show only",
                "show me only",
                "show critical",
                "show high risk",
                "show medium risk",
                "show low risk",
                "show scheduled",
                "show completed",
                "show arrived",
                "show waiting",
            )
        )

    def _is_open_command(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "open appointment",
                "show appointment",
                "view appointment",
                "go to appointment",
            )
        )

    def _resolve_action_ids(
        self,
        *,
        question: str,
        actions: list[dict[str, Any]],
    ) -> list[int]:
        if not actions:
            return []

        ordered_actions = sorted(
            actions,
            key=lambda action: (
                action.get("sequence_number", 0)
                or 0
            ),
        )

        if self._references_all(question):
            return [
                self._action_id(action)
                for action in ordered_actions
            ]

        first_count = self._extract_first_count(
            question
        )

        if first_count is not None:
            return [
                self._action_id(action)
                for action in ordered_actions[
                    :first_count
                ]
            ]

        explicit_positions = (
            self._extract_action_positions(
                question
            )
        )

        if explicit_positions:
            return [
                self._action_id(
                    ordered_actions[position - 1]
                )
                for position in explicit_positions
                if 1 <= position <= len(
                    ordered_actions
                )
            ]

        category_action_ids = (
            self._resolve_category_actions(
                question=question,
                actions=ordered_actions,
            )
        )

        if category_action_ids:
            return category_action_ids

        highest_impact_requested = any(
            phrase in question
            for phrase in (
                "highest impact",
                "best action",
                "top action",
                "most valuable",
                "highest roi",
            )
        )

        if highest_impact_requested:
            best_action = max(
                ordered_actions,
                key=lambda action: (
                    action.get(
                        "estimated_minutes_saved",
                        0,
                    )
                    or 0
                ),
            )

            return [
                self._action_id(best_action)
            ]

        return []

    def _references_all(
        self,
        question: str,
    ) -> bool:
        return any(
            phrase in question
            for phrase in (
                "all actions",
                "every action",
                "all of them",
                "everything",
                "entire plan",
                "full plan",
            )
        )

    def _extract_first_count(
        self,
        question: str,
    ) -> int | None:
        word_numbers = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }

        match = re.search(
            r"\bfirst\s+(\d+)\b",
            question,
        )

        if match:
            return max(
                0,
                int(match.group(1)),
            )

        for word, count in word_numbers.items():
            if f"first {word}" in question:
                return count

        return None

    def _extract_action_positions(
        self,
        question: str,
    ) -> list[int]:
        positions: set[int] = set()

        number_matches = re.findall(
            r"\b(?:action|actions)\s*"
            r"(?:number\s*)?"
            r"(\d+)\b",
            question,
        )

        for value in number_matches:
            positions.add(int(value))

        ordinal_patterns = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
        }

        for word, position in (
            ordinal_patterns.items()
        ):
            if (
                f"the {word} action" in question
                or f"{word} action" in question
            ):
                positions.add(position)

        return sorted(positions)

    def _resolve_category_actions(
        self,
        *,
        question: str,
        actions: list[dict[str, Any]],
    ) -> list[int]:
        category_keywords = {
            "dock": (
                "dock",
                "door",
                "reassign",
                "move",
            ),
            "labor": (
                "loader",
                "labor",
                "worker",
                "staff",
                "crew",
            ),
            "forklift": (
                "forklift",
                "equipment",
            ),
            "prestage": (
                "pre-stage",
                "prestage",
                "stage product",
                "inventory ready",
            ),
            "paperwork": (
                "paperwork",
                "document",
                "label",
                "printing",
            ),
            "qa": (
                "qa",
                "quality",
                "inspection",
            ),
        }

        selected_categories = [
            category
            for category, keywords
            in category_keywords.items()
            if any(
                keyword in question
                for keyword in keywords
            )
        ]

        if not selected_categories:
            return []

        matching_ids: list[int] = []

        for action in actions:
            searchable_text = " ".join(
                str(
                    action.get(field, "")
                    or ""
                ).lower()
                for field in (
                    "action_code",
                    "action_title",
                    "action_description",
                    "owner_role",
                    "required_equipment_type",
                    "required_dock_id",
                )
            )

            for category in selected_categories:
                if any(
                    keyword in searchable_text
                    for keyword in (
                        category_keywords[category]
                    )
                ):
                    matching_ids.append(
                        self._action_id(action)
                    )
                    break

        return matching_ids

    def _extract_what_if_metadata(
        self,
        question: str,
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}

        loader_count = self._extract_resource_count(
            question=question,
            singular="loader",
            plural="loaders",
        )

        forklift_count = (
            self._extract_resource_count(
                question=question,
                singular="forklift",
                plural="forklifts",
            )
        )

        if loader_count is not None:
            metadata["extra_loaders"] = str(
                loader_count
            )

        if forklift_count is not None:
            metadata["extra_forklifts"] = str(
                forklift_count
            )

        if any(
            phrase in question
            for phrase in (
                "pre-stage",
                "prestage",
                "stage products",
                "stage inventory",
            )
        ):
            metadata["pre_stage_products"] = (
                "true"
            )

        return metadata

    def _extract_resource_count(
        self,
        *,
        question: str,
        singular: str,
        plural: str,
    ) -> int | None:
        numeric_match = re.search(
            rf"\b(\d+)\s+"
            rf"(?:extra\s+)?"
            rf"(?:{singular}|{plural})\b",
            question,
        )

        if numeric_match:
            return int(
                numeric_match.group(1)
            )

        word_numbers = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }

        for word, count in word_numbers.items():
            if (
                f"{word} extra {singular}"
                in question
                or f"{word} {plural}"
                in question
                or f"{word} {singular}"
                in question
            ):
                return count

        return None

    def _extract_filter_metadata(
        self,
        question: str,
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}

        risk_levels = (
            "Critical",
            "High",
            "Medium",
            "Low",
        )

        for risk_level in risk_levels:
            if (
                risk_level.lower()
                in question
            ):
                metadata["risk_level"] = (
                    risk_level
                )
                break

        statuses = (
            "Scheduled",
            "Completed",
            "Arrived",
            "Waiting",
            "In Progress",
        )

        for status in statuses:
            if status.lower() in question:
                metadata["status"] = status
                break

        facility_match = re.search(
            r"\bfacility\s+"
            r"([a-z0-9_-]+)\b",
            question,
        )

        if facility_match:
            metadata["facility_id"] = (
                facility_match.group(1)
                .upper()
            )

        return metadata

    def _extract_appointment_id(
        self,
        question: str,
    ) -> str | None:
        match = re.search(
            r"\b(?:demo|app|appt)"
            r"[a-z0-9_-]*\d+\b",
            question,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return match.group(0).upper()

    def _build_decision_message(
        self,
        *,
        decision: str,
        action_ids: list[int],
        actions: list[dict[str, Any]],
    ) -> str:
        if not action_ids:
            return (
                f"I identified a request to {decision} "
                "recovery actions, but I could not "
                "determine which actions you meant."
            )

        action_lookup = {
            self._action_id(action): action
            for action in actions
        }

        selected_titles = [
            action_lookup[action_id].get(
                "action_title",
                f"Action {action_id}",
            )
            for action_id in action_ids
            if action_id in action_lookup
        ]

        title_list = ", ".join(
            selected_titles
        )

        return (
            f"I found {len(action_ids)} recovery "
            f"action{'s' if len(action_ids) != 1 else ''} "
            f"to {decision}: {title_list}. "
            "Please confirm before I update the plan."
        )

    def _action_id(
        self,
        action: dict[str, Any],
    ) -> int:
        return int(
            action[
                "recommendation_action_id"
            ]
        )