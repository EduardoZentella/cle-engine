"""Pydantic schemas for backend API contracts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

        if value is not None and len(value) != 384:
            raise ValueError("Embedding must have exactly 384 dimensions.")
        return value


class VocabularyBulkUpsertRequest(BaseModel):
    """Request payload for vocabulary batch upsert."""

    model_config = ConfigDict(extra="forbid")

    items: list[VocabularyUpsertItem] = Field(min_length=1)


class VocabularyBulkUpsertResponse(BaseModel):
    """Result payload for vocabulary batch upsert."""

    upserted: int


class ContextScenario(BaseModel):
    """Optional contextual metadata for recommendations."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = None
    environment: str | None = None
    sentiment: str | None = None
    intent: str | None = None


class RecommendationGenerateRequest(BaseModel):
    """Request payload for single unified recommendation generation endpoint."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    original_text: str = Field(min_length=1, max_length=1000)
    translation: str | None = None
    source_language: str = Field(default="de", min_length=2, max_length=10)
    target_language: str = Field(default="en", min_length=2, max_length=10)
    context_scenario: ContextScenario | None = Field(default_factory=ContextScenario)


class RecommendationItem(BaseModel):
    """Single scored recommendation."""

    text: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    usage: str | None = None

class RecommendationMetadata(BaseModel):
    """Metadata about recommendation generation."""

    attempts: int
    duration_ms: float


class RecommendationGenerateResponse(BaseModel):
    """Response payload for recommendation generation endpoint."""

    translation: str
    recommendations: list[RecommendationItem]
    metadata: RecommendationMetadata


class UserVerifyRequest(BaseModel):
    """Request payload to verify if user exists."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class UserVerifyResponse(BaseModel):
    """Response payload indicating if user exists."""

    exists: bool
    user_id: UUID | None = None
    username: str | None = None
    first_name: str | None = None
    base_language: str | None = None
    target_language: str | None = None
    current_level: str | None = None
    city: str | None = None

class TranslateRequest(BaseModel):
    """Request payload for standalone translation."""
    model_config = ConfigDict(extra="forbid")
    original_text: str = Field(min_length=1)
    source_language: str
    target_language: str
    user_level: str = "A1"

class TranslateResponse(BaseModel):
    """Response payload for standalone translation."""
    translation: str

class PracticeGenerateRequest(BaseModel):
    """Request payload to generate a specific practice exercise."""
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    exercise_type: str  # e.g., "match-pairs", "complete-sentences", etc.
    original_text: str
    translation: str
    source_language: str
    target_language: str
    current_level: str
    context_label: str
    recommendations: list[str] = Field(default_factory=list)

class PracticeExercise(BaseModel):
    """Structured practice exercise returned from LLM."""
    type: str  # e.g., "match-pairs", "complete-sentences", etc.
    prompt: str  # The sentence with blanks or instruction
    options: list[str] = Field(default_factory=list)  # Options for the exercise
    correct_answer: str  # The exact correct option string
    explanation: str | None = None  # Brief explanation of the correct answer
