"""FastAPI routes for recommendation workflows (Phase 2)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    TranslateResponse,
    TranslateRequest,
    UserVerifyRequest,
    UserVerifyResponse,
    VocabularyBulkUpsertRequest,
    VocabularyBulkUpsertResponse,
)
from app.api.unified_service import UnifiedRecommendationService

router = APIRouter(prefix="/api/v1", tags=["recommendations"])

logger = logging.getLogger(__name__)


def get_recommendation_service(request: Request) -> UnifiedRecommendationService:
    """Resolve the recommendation service from application state.

    Raises HTTP 503 when startup has not completed or the service is missing.
    """
    service = getattr(request.app.state, "recommendation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Recommendation service is unavailable.")
    return service


@router.post("/users/verify", response_model=UserVerifyResponse)
def verify_user(
    payload: UserVerifyRequest,
    service: UnifiedRecommendationService = Depends(get_recommendation_service),
) -> UserVerifyResponse:
    """Verify if a user exists by name (username or first_name).

    Used during login to check if user exists and get their ID.

    Args:
        payload: Request with name to search for

    Returns:
        UserVerifyResponse with exists, user_id, and profile details
    """
    logger.debug("POST /users/verify payload=%s", payload.model_dump(mode="json", exclude_none=False))
    response = service.verify_user(payload.name)
    logger.debug(
        "POST /users/verify result exists=%s user_id=%s",
        response.exists,
        response.user_id,
    )
    return response


@router.post("/recommendations/generate", response_model=RecommendationGenerateResponse)
async def generate_recommendations(
    payload: RecommendationGenerateRequest,
    service: UnifiedRecommendationService = Depends(get_recommendation_service),
) -> RecommendationGenerateResponse:
    """Generate translation recommendations using full pipeline.

    Single unified endpoint that:
    1. Translates the text (fast, no context)
    2. Retrieves relevant vocabulary
    3. Generates candidate sentences using LLM
    4. Evaluates and scores them
    5. Returns top 3 recommendations

    Args:
        payload: Request with user_id, original_text, languages, context

    Returns:
        RecommendationGenerateResponse with translation, recommendations, metadata

    Raises:
        HTTPException 503 if service unavailable
        HTTPException 500 if pipeline fails
    """
    logger.debug(
        "POST /recommendations/generate payload=%s",
        payload.model_dump(mode="json", exclude_none=False),
    )

    try:
        response = await service.generate_recommendations(payload)

        logger.debug(
            "POST /recommendations/generate result recommendation_count=%s duration_ms=%.2f",
            len(response.recommendations),
            response.metadata.duration_ms,
        )

        return response

    except Exception as err:
        logger.error("POST /recommendations/generate failed error=%s", str(err))
        raise HTTPException(status_code=500, detail="Recommendation generation failed") from err

@router.post("/recommendations/translate", response_model=TranslateResponse)
async def translate_text(
    payload: TranslateRequest,
    request: Request,
) -> TranslateResponse:
    """Get an immediate translation before running the heavy generation pipeline."""
    service = request.app.state.recommendation_service
    return await service.translate_text(payload)

from app.api.schemas import PracticeGenerateRequest, PracticeExercise

@router.post("/practice/generate-exercise", response_model=PracticeExercise)
async def generate_practice_exercise(
    payload: PracticeGenerateRequest,
    request: Request,
) -> PracticeExercise:
    """Generate a specific LLM-driven practice exercise."""
    service = request.app.state.recommendation_service
    return service.generate_practice(payload)

@router.post("/vocabulary/bulk-upsert", response_model=VocabularyBulkUpsertResponse)
def bulk_upsert_vocabulary(
    payload: VocabularyBulkUpsertRequest,
    service: UnifiedRecommendationService = Depends(get_recommendation_service),
) -> VocabularyBulkUpsertResponse:
    """Bulk create/update vocabulary entries used by retrieval (Admin endpoint).

    Args:
        payload: Request with list of vocabulary items to upsert

    Returns:
        Response with count of upserted items
    """
    logger.debug("POST /vocabulary/bulk-upsert item_count=%s", len(payload.items))

    try:
        response = service.bulk_upsert_vocabulary(payload.items)
        logger.debug("POST /vocabulary/bulk-upsert result upserted=%s", response.upserted)
        return response

    except Exception as err:
        logger.error("POST /vocabulary/bulk-upsert failed error=%s", str(err))
        raise HTTPException(status_code=500, detail="Vocabulary upsert failed") from err
