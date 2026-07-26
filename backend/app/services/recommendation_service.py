from typing import Any

from app.errors import AppError
from app.repositories.recommendation_repository import (
    RecommendationRepository,
)
from app.schemas import RecommendationDecisionRequest


class RecommendationService:
    def __init__(
        self,
        repository: RecommendationRepository,
    ) -> None:
        self.repository = repository

    def update_decisions(
        self,
        *,
        recommendation_id: int,
        payload: RecommendationDecisionRequest,
    ) -> dict[str, Any]:
        try:
            result = (
                self.repository.update_action_decisions(
                    recommendation_id=recommendation_id,
                    actions=[
                        action.model_dump()
                        for action in payload.actions
                    ],
                    decided_by=payload.decided_by,
                )
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="INVALID_RECOMMENDATION_ACTION",
                status_code=400,
            ) from exc

        if result is None:
            raise AppError(
                message="Recommendation not found",
                code="RECOMMENDATION_NOT_FOUND",
                status_code=404,
                details={
                    "recommendation_id":
                        recommendation_id,
                },
            )

        return result