from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.recommendation_repository import (
    RecommendationRepository,
)
from app.schemas import RecommendationDecisionRequest
from app.services.recommendation_service import (
    RecommendationService,
)


router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
)


def get_recommendation_service(
    db: Session = Depends(get_db),
) -> RecommendationService:
    repository = RecommendationRepository(db)
    return RecommendationService(repository)


@router.patch("/{recommendation_id}/decisions")
def update_recommendation_decisions(
    recommendation_id: int,
    payload: RecommendationDecisionRequest,
    service: RecommendationService = Depends(
        get_recommendation_service
    ),
):
    return service.update_decisions(
        recommendation_id=recommendation_id,
        payload=payload,
    )