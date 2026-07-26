from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class RecommendationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def update_action_decisions(
        self,
        *,
        recommendation_id: int,
        actions: list[dict[str, Any]],
        decided_by: str,
    ) -> dict[str, Any] | None:
        recommendation_exists = self.db.execute(
            text(
                """
                SELECT recommendation_id
                FROM appointment_recommendations
                WHERE recommendation_id = :recommendation_id;
                """
            ),
            {
                "recommendation_id":
                    recommendation_id,
            },
        ).scalar_one_or_none()

        if recommendation_exists is None:
            return None

        for action in actions:
            decision_status = action["decision_status"]

            action_status = (
                "Accepted"
                if decision_status == "Accepted"
                else "Rejected"
                if decision_status == "Rejected"
                else "Proposed"
            )

            updated_action_id = self.db.execute(
                text(
                    """
                    UPDATE recommendation_actions
                    SET
                        decision_status = :decision_status,
                        decision_at = NOW(),
                        decision_by = :decided_by,
                        decision_notes = :notes,
                        status = :status
                    WHERE
                        recommendation_action_id =
                            :recommendation_action_id
                        AND recommendation_id =
                            :recommendation_id
                    RETURNING recommendation_action_id;
                    """
                ),
                {
                    "recommendation_id":
                        recommendation_id,
                    "recommendation_action_id":
                        action[
                            "recommendation_action_id"
                        ],
                    "decision_status":
                        decision_status,
                    "decided_by":
                        decided_by,
                    "notes":
                        action.get("notes"),
                    "status":
                        action_status,
                },
            ).scalar_one_or_none()

            if updated_action_id is None:
                self.db.rollback()

                raise ValueError(
                    "One or more actions do not belong "
                    "to this recommendation."
                )

        summary = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_actions,

                    COUNT(*) FILTER (
                        WHERE decision_status = 'Accepted'
                    ) AS accepted_actions,

                    COUNT(*) FILTER (
                        WHERE decision_status = 'Rejected'
                    ) AS rejected_actions,

                    COUNT(*) FILTER (
                        WHERE decision_status = 'Pending'
                    ) AS pending_actions,

                    COALESCE(
                        SUM(estimated_minutes_saved)
                        FILTER (
                            WHERE decision_status = 'Accepted'
                        ),
                        0
                    ) AS accepted_minutes_saved,

                    COALESCE(
                        SUM(estimated_action_cost)
                        FILTER (
                            WHERE decision_status = 'Accepted'
                        ),
                        0
                    ) AS accepted_action_cost

                FROM recommendation_actions
                WHERE recommendation_id =
                    :recommendation_id;
                """
            ),
            {
                "recommendation_id":
                    recommendation_id,
            },
        ).mappings().one()

        total = summary["total_actions"] or 0
        accepted = summary["accepted_actions"] or 0
        rejected = summary["rejected_actions"] or 0
        pending = summary["pending_actions"] or 0

        if total == 0 or pending == total:
            parent_status = "Pending"
        elif accepted == total:
            parent_status = "Accepted"
        elif rejected == total:
            parent_status = "Rejected"
        else:
            parent_status = "Partially Accepted"

        self.db.execute(
            text(
                """
                UPDATE appointment_recommendations
                SET
                    status = :status,
                    responded_at = NOW(),
                    responded_by = :decided_by
                WHERE recommendation_id =
                    :recommendation_id;
                """
            ),
            {
                "recommendation_id":
                    recommendation_id,
                "status": parent_status,
                "decided_by": decided_by,
            },
        )

        self.db.commit()

        return {
            "recommendation_id": recommendation_id,
            "status": parent_status,
            **dict(summary),
        }