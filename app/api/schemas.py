"""Pydantic schemas for backend API contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.config import read_embedding_dimension_from_env


EMBEDDING_DIMENSION = read_embedding_dimension_from_env()


class UserUpsertRequest(BaseModel):
    """Request payload to create or update a user profile."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    external_user_id: str | None = None
    email: str | None = None
    username: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    base_language: str = "en"
    target_language: str = "de"
    current_level: str = "A1"
    city: str | None = None
    country: str | None = None
    region: str | None = None
    area_type: str | None = None
    profile_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserUpsertResponse(BaseModel):
    """Response payload returned after user upsert."""

    user_id: UUID
    created: bool


class VocabularyUpsertItem(BaseModel):
    """Single vocabulary record for bulk ingestion/upsert."""

    model_config = ConfigDict(extra="forbid")

    word_key: str | None = None
    word: str = Field(min_length=1)
    description: str | None = None
    meaning: str | None = None
    example_sentence: str | None = None
    category: str | None = None
    cefr_level: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_language: str = "de"
    target_language: str = "en"
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, value: list[float] | None) -> list[float] | None:
        """Validate optional embedding dimension for pgvector compatibility."""

        if value is not None and len(value) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding must have exactly {EMBEDDING_DIMENSION} dimensions."
            )
        return value


class VocabularyBulkUpsertRequest(BaseModel):
    """Request payload for vocabulary batch upsert."""

    model_config = ConfigDict(extra="forbid")

    items: list[VocabularyUpsertItem] = Field(min_length=1)


class VocabularyBulkUpsertResponse(BaseModel):
    """Result payload for vocabulary batch upsert."""

    upserted: int


class RecommendationContext(BaseModel):
    """Optional contextual metadata accompanying user translation events."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = None
    environment: str | None = None
    sentiment: str | None = None
    intent: str | None = None
    topic: str | None = None


class RecommendationAction(BaseModel):
    """Action payload capturing source text, translation, and context."""

    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(min_length=1)
    translation: str = Field(min_length=1)
    source_language: str = Field(default="de", min_length=2, max_length=10)
    target_language: str = Field(default="en", min_length=2, max_length=10)
    input_mode: str = Field(default="text", min_length=2, max_length=20)
    ocr_text: str | None = None
    context: RecommendationContext = Field(default_factory=RecommendationContext)


class RecommendationRequest(BaseModel):
    """Request payload for contextual recommendation generation."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    action: RecommendationAction


class RecommendationItem(BaseModel):
    """One recommendation item returned to API consumers."""

    phrase: str
    meaning: str | None = None
    relevance: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    """Response payload for contextual recommendation endpoint."""

    predicted_level: str
    model_action: str
    reranked_recommendations: list[RecommendationItem]


class PracticeExercise(BaseModel):
    """Single generated practice exercise."""

    type: str
    prompt: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str | None = None
    explanation: str | None = None


class PracticeResponse(BaseModel):
    """Response payload for practice generation endpoint."""

    context_theme: str
    exercises: list[PracticeExercise]