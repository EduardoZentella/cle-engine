"""FastAPI routes for recommendation and practice workflows."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.recommendation_service import RecommendationService
from app.api.schemas import (
    PracticeResponse,
    RecommendationRequest,
    RecommendationResponse,
    UserUpsertRequest,
    UserUpsertResponse,
    VocabularyBulkUpsertRequest,
    VocabularyBulkUpsertResponse,
)

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


def get_recommendation_service(request: Request) -> RecommendationService:
    """Resolve the recommendation service from application state.

    Raises HTTP 503 when startup has not completed or the service is missing.
    """

    service = getattr(request.app.state, "recommendation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Recommendation service is unavailable.")
    return service


@router.post("/users/upsert", response_model=UserUpsertResponse)
async def upsert_user(
    payload: UserUpsertRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> UserUpsertResponse:
    """Create or update a user profile used by recommendation flows."""

    return await service.upsert_user(payload)


@router.post("/vocabulary/bulk-upsert", response_model=VocabularyBulkUpsertResponse)
async def bulk_upsert_vocabulary(
    payload: VocabularyBulkUpsertRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> VocabularyBulkUpsertResponse:
    """Bulk create/update vocabulary entries used by retrieval."""

    upserted = await service.bulk_upsert_vocabulary(payload.items)
    return VocabularyBulkUpsertResponse(upserted=upserted)


@router.post("/recommendations/contextual", response_model=RecommendationResponse)
async def contextual_recommendations(
    payload: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    """Execute contextual recommendation retrieval and reranking."""

    return await service.generate_contextual_recommendations(payload)


@router.get("/practice/generate", response_model=PracticeResponse)
async def generate_practice(
    user_id: UUID,
    limit: int = Query(default=5, ge=1, le=12),
    service: RecommendationService = Depends(get_recommendation_service),
) -> PracticeResponse:
    """Generate practice exercises based on latest user recommendations."""

    return await service.generate_practice_exercises(user_id=user_id, limit=limit)