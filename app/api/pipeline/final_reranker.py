"""Final reranker stage for contextual recommendation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import math
from pathlib import Path
import pickle
from typing import Any, Protocol

from app.api.embeddings import EmbeddingProvider
from app.api.intelligence import IntelligenceContext
from app.api.perf_analytics import PerfAnalytics


logger = logging.getLogger(__name__)

DEFAULT_FEATURE_ORDER = [
    "semantic_similarity",
    "fusion_score",
    "vector_score",
    "lexical_score",
    "llm_score",
    "source_vector",
    "source_lexical",
    "source_hybrid",
    "source_llm_refine",
]


class FinalReranker(Protocol):
    """Contract for final reranking stage."""

    async def rerank(
        self,
        *,
        context: IntelligenceContext,
        candidates: list[dict[str, Any]],
        approval_threshold: float,
    ) -> list[dict[str, Any]]:
        """Score and rerank candidates in descending order."""

        ...

    def health_snapshot(self) -> dict[str, Any]:
        """Return reranker health snapshot for diagnostics."""

        ...

    async def aclose(self) -> None:
        """Release reranker resources."""

        ...


@dataclass(frozen=True, slots=True)
class PretrainedRerankerManifest:
    """Model artifact metadata used to run pretrained reranker inference."""

    version: int = 1
    model_file: str = "model.pkl"
    score_method: str = "auto"
    positive_class_index: int = 1
    threshold: float | None = None
    feature_order: list[str] = field(default_factory=lambda: DEFAULT_FEATURE_ORDER.copy())

    @classmethod
    def load(cls, path: Path) -> "PretrainedRerankerManifest":
        """Load and validate manifest from disk."""

        raw = json.loads(path.read_text(encoding="utf-8"))
        feature_order = raw.get("feature_order")
        if not isinstance(feature_order, list) or not feature_order:
            feature_order = DEFAULT_FEATURE_ORDER.copy()

        cleaned_order = [str(name).strip() for name in feature_order if str(name).strip()]
        if not cleaned_order:
            cleaned_order = DEFAULT_FEATURE_ORDER.copy()

        score_method = str(raw.get("score_method", "auto")).strip().lower() or "auto"
        if score_method not in {"auto", "predict_proba", "decision_function", "predict", "call"}:
            score_method = "auto"

        threshold_raw = raw.get("threshold")
        threshold: float | None
        if threshold_raw is None:
            threshold = None
        else:
            threshold = cls._clamp01(float(threshold_raw))

        return cls(
            version=int(raw.get("version", 1)),
            model_file=str(raw.get("model_file", "model.pkl")).strip() or "model.pkl",
            score_method=score_method,
            positive_class_index=max(0, int(raw.get("positive_class_index", 1))),
            threshold=threshold,
            feature_order=cleaned_order,
        )

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, value))


class EmbeddingSimilarityFinalReranker:
    """Final reranker that scores candidates in embedding space.

    This stage is intentionally separated from candidate generation to keep the
    hybrid flow explicit:

    1. generate candidate pool,
    2. rerank with pretrained embedding model,
    3. decide use vs regenerate.
    """

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self._embedding_provider = embedding_provider

    async def rerank(
        self,
        *,
        context: IntelligenceContext,
        candidates: list[dict[str, Any]],
        approval_threshold: float,
    ) -> list[dict[str, Any]]:
        analytics = PerfAnalytics(
            logger=logger,
            scope="embedding_similarity_final_reranker.rerank",
            context={"user_id": context.user_id, "candidate_count": len(candidates)},
        )
        try:
            if not candidates:
                return []

            with analytics.stage("build_embedding_inputs", kind="compute"):
                context_text = self._context_to_text(context)
                candidate_texts = [self._candidate_to_text(candidate) for candidate in candidates]

            with analytics.stage("embed_context_and_candidates", kind="network"):
                vectors = await self._embedding_provider.embed_many([context_text, *candidate_texts])

            if len(vectors) != len(candidate_texts) + 1:
                with analytics.stage("fallback_scoring_mismatch", kind="compute"):
                    return self._fallback_scoring(candidates, approval_threshold)

            context_vector = vectors[0]
            candidate_vectors = vectors[1:]

            with analytics.stage("score_candidates", kind="compute"):
                for candidate, vector in zip(candidates, candidate_vectors):
                    cosine = self._cosine_similarity(context_vector, vector)
                    score = max(0.0, min(1.0, (cosine + 1.0) / 2.0))
                    candidate["ml_relevance_score"] = score
                    candidate["ml_approved"] = score >= approval_threshold
                    candidate["ml_reason"] = (
                        "Final reranker semantic similarity in pretrained embedding space: "
                        f"{score:.3f}."
                    )

            with analytics.stage("sort_candidates", kind="compute"):
                reranked = sorted(
                    candidates,
                    key=lambda item: (
                        float(item.get("ml_relevance_score") or 0.0),
                        float(item.get("fusion_score") or 0.0),
                    ),
                    reverse=True,
                )

                for index, candidate in enumerate(reranked, start=1):
                    candidate["rank_position"] = index

            return reranked
        finally:
            analytics.log_summary()

    def health_snapshot(self) -> dict[str, Any]:
        embedding_health = self._embedding_provider.health_snapshot()
        return {
            "backend": "embedding_similarity",
            "embedding_backend": embedding_health.get("backend"),
            "degraded": bool(embedding_health.get("degraded", False)),
            "total_failures": int(embedding_health.get("total_failures", 0)),
            "consecutive_failures": int(embedding_health.get("consecutive_failures", 0)),
        }

    async def aclose(self) -> None:
        return None

    @staticmethod
    def _context_to_text(context: IntelligenceContext) -> str:
        fields = [
            context.source_text,
            context.translated_text,
            context.location or "",
            context.environment or "",
            context.sentiment or "",
            context.intent or "",
            context.ocr_text or "",
            context.topic or "",
        ]
        return " | ".join(chunk for chunk in fields if chunk)

    @staticmethod
    def _candidate_to_text(candidate: dict[str, Any]) -> str:
        return " | ".join(
            part
            for part in [
                str(candidate.get("word") or ""),
                str(candidate.get("meaning") or ""),
                str(candidate.get("description") or ""),
                str(candidate.get("llm_rationale") or ""),
            ]
            if part
        )

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0

        limit = min(len(left), len(right))
        dot_product = sum(left[index] * right[index] for index in range(limit))
        left_norm = math.sqrt(sum(value * value for value in left[:limit]))
        right_norm = math.sqrt(sum(value * value for value in right[:limit]))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot_product / (left_norm * right_norm)

    @staticmethod
    def _fallback_scoring(
        candidates: list[dict[str, Any]],
        approval_threshold: float,
    ) -> list[dict[str, Any]]:
        for candidate in candidates:
            score = max(0.0, min(1.0, float(candidate.get("fusion_score") or 0.0)))
            candidate["ml_relevance_score"] = score
            candidate["ml_approved"] = score >= approval_threshold
            candidate["ml_reason"] = "Fallback reranking based on fusion score."

        reranked = sorted(
            candidates,
            key=lambda item: float(item.get("fusion_score") or 0.0),
            reverse=True,
        )
        for index, candidate in enumerate(reranked, start=1):
            candidate["rank_position"] = index
        return reranked


class PretrainedModelFinalReranker:
    """Drop-in final reranker that uses pretrained model artifacts when available.

    Behavior:

    - if manifest/model artifacts are present and valid in the configured folder,
      use the pretrained model for final reranking,
    - otherwise use embedding similarity reranker as fallback.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        model_dir: str,
        manifest_file: str = "manifest.json",
    ) -> None:
        self._embedding_provider = embedding_provider
        self._model_dir = Path(model_dir)
        self._manifest_file = manifest_file
        self._fallback = EmbeddingSimilarityFinalReranker(embedding_provider)
        self._manifest: PretrainedRerankerManifest | None = None
        self._model: Any | None = None
        self._load_error: str | None = None

    async def rerank(
        self,
        *,
        context: IntelligenceContext,
        candidates: list[dict[str, Any]],
        approval_threshold: float,
    ) -> list[dict[str, Any]]:
        analytics = PerfAnalytics(
            logger=logger,
            scope="pretrained_model_final_reranker.rerank",
            context={"user_id": context.user_id, "candidate_count": len(candidates)},
        )
        try:
            if not candidates:
                return []

            with analytics.stage("ensure_model_loaded", kind="io"):
                model_loaded = self._ensure_model_loaded()

            if not model_loaded or self._manifest is None or self._model is None:
                with analytics.stage("fallback_rerank_model_unavailable", kind="network"):
                    return await self._fallback.rerank(
                        context=context,
                        candidates=candidates,
                        approval_threshold=approval_threshold,
                    )

            try:
                with analytics.stage("build_embedding_inputs", kind="compute"):
                    context_text = self._context_to_text(context)
                    candidate_texts = [self._candidate_to_text(candidate) for candidate in candidates]

                with analytics.stage("embed_context_and_candidates", kind="network"):
                    vectors = await self._embedding_provider.embed_many(
                        [context_text, *candidate_texts]
                    )
                if len(vectors) != len(candidate_texts) + 1:
                    with analytics.stage("fallback_rerank_vector_mismatch", kind="network"):
                        return await self._fallback.rerank(
                            context=context,
                            candidates=candidates,
                            approval_threshold=approval_threshold,
                        )

                context_vector = vectors[0]
                candidate_vectors = vectors[1:]
                with analytics.stage("build_feature_rows", kind="compute"):
                    feature_rows: list[list[float]] = []
                    for candidate, vector in zip(candidates, candidate_vectors):
                        feature_map = self._build_feature_map(candidate, context_vector, vector)
                        feature_rows.append(
                            [
                                float(feature_map.get(name, 0.0))
                                for name in self._manifest.feature_order
                            ]
                        )

                with analytics.stage("model_inference", kind="compute"):
                    scores = self._score_with_model(feature_rows)
                if len(scores) != len(candidates):
                    with analytics.stage("fallback_rerank_score_mismatch", kind="network"):
                        return await self._fallback.rerank(
                            context=context,
                            candidates=candidates,
                            approval_threshold=approval_threshold,
                        )

                with analytics.stage("apply_scores_and_sort", kind="compute"):
                    threshold = (
                        self._manifest.threshold
                        if self._manifest.threshold is not None
                        else approval_threshold
                    )

                    for candidate, score in zip(candidates, scores):
                        candidate["ml_relevance_score"] = score
                        candidate["ml_approved"] = score >= threshold
                        candidate["ml_reason"] = (
                            "Pretrained final reranker score based on model artifact: "
                            f"{score:.3f}."
                        )

                    reranked = sorted(
                        candidates,
                        key=lambda item: (
                            float(item.get("ml_relevance_score") or 0.0),
                            float(item.get("fusion_score") or 0.0),
                        ),
                        reverse=True,
                    )

                    for index, candidate in enumerate(reranked, start=1):
                        candidate["rank_position"] = index

                return reranked
            except Exception as exc:
                self._load_error = str(exc)
                logger.warning("Pretrained reranker failed; using fallback: %s", exc)
                with analytics.stage("fallback_rerank_exception", kind="network"):
                    return await self._fallback.rerank(
                        context=context,
                        candidates=candidates,
                        approval_threshold=approval_threshold,
                    )
        finally:
            analytics.log_summary()

    def health_snapshot(self) -> dict[str, Any]:
        fallback_health = self._fallback.health_snapshot()
        manifest_path = self._model_dir / self._manifest_file

        if self._model is not None and self._manifest is not None:
            return {
                "backend": "pretrained_model",
                "model_loaded": True,
                "model_dir": str(self._model_dir),
                "manifest_file": self._manifest_file,
                "model_file": self._manifest.model_file,
                "score_method": self._manifest.score_method,
                "degraded": False,
                "fallback_backend": fallback_health.get("backend"),
            }

        return {
            "backend": "embedding_similarity_fallback",
            "model_loaded": False,
            "model_dir": str(self._model_dir),
            "manifest_file": self._manifest_file,
            "manifest_exists": manifest_path.exists(),
            "load_error": self._load_error,
            "degraded": bool(fallback_health.get("degraded", False)),
            "fallback_backend": fallback_health.get("backend"),
        }

    async def aclose(self) -> None:
        await self._fallback.aclose()

    def _ensure_model_loaded(self) -> bool:
        if self._manifest is not None and self._model is not None:
            return True

        manifest_path = self._model_dir / self._manifest_file
        if not manifest_path.exists():
            self._load_error = None
            return False

        try:
            manifest = PretrainedRerankerManifest.load(manifest_path)
            model_path = self._model_dir / manifest.model_file
            if not model_path.exists():
                self._load_error = (
                    f"Model artifact '{manifest.model_file}' not found in {self._model_dir}."
                )
                return False

            with model_path.open("rb") as handle:
                model = pickle.load(handle)

            self._manifest = manifest
            self._model = model
            self._load_error = None
            return True
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to load pretrained reranker artifacts: %s", exc)
            return False

    def _score_with_model(self, feature_rows: list[list[float]]) -> list[float]:
        if self._manifest is None or self._model is None:
            return []

        model = self._model
        method = self._manifest.score_method

        if method in {"auto", "predict_proba"} and hasattr(model, "predict_proba"):
            raw = model.predict_proba(feature_rows)
            matrix = self._as_matrix(raw)
            if not matrix:
                return []
            index = min(self._manifest.positive_class_index, len(matrix[0]) - 1)
            return [self._clamp01(float(row[index])) for row in matrix]

        if method in {"auto", "decision_function"} and hasattr(model, "decision_function"):
            raw = model.decision_function(feature_rows)
            values = self._as_vector(raw)
            return [self._clamp01(1.0 / (1.0 + math.exp(-value))) for value in values]

        if method in {"auto", "predict"} and hasattr(model, "predict"):
            raw = model.predict(feature_rows)
            values = self._as_vector(raw)
            return [self._clamp01(value) for value in values]

        if method in {"auto", "call"} and callable(model):
            raw = model(feature_rows)
            values = self._as_vector(raw)
            return [self._clamp01(value) for value in values]

        raise RuntimeError(
            "No supported scoring method found on pretrained reranker model."
        )

    @staticmethod
    def _build_feature_map(
        candidate: dict[str, Any],
        context_vector: list[float],
        candidate_vector: list[float],
    ) -> dict[str, float]:
        source = str(candidate.get("source") or "")
        semantic_similarity = EmbeddingSimilarityFinalReranker._cosine_similarity(
            context_vector,
            candidate_vector,
        )

        return {
            "semantic_similarity": semantic_similarity,
            "fusion_score": float(candidate.get("fusion_score") or 0.0),
            "vector_score": float(candidate.get("vector_score") or 0.0),
            "lexical_score": float(candidate.get("lexical_score") or 0.0),
            "llm_score": float(candidate.get("llm_score") or 0.0),
            "source_vector": 1.0 if source == "vector" else 0.0,
            "source_lexical": 1.0 if source == "lexical" else 0.0,
            "source_hybrid": 1.0 if source == "hybrid" else 0.0,
            "source_llm_refine": 1.0 if source == "llm_refine" else 0.0,
        }

    @staticmethod
    def _as_vector(raw: Any) -> list[float]:
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        if isinstance(raw, (int, float)):
            return [float(raw)]

        if isinstance(raw, list):
            if not raw:
                return []
            if isinstance(raw[0], list):
                return [float(row[0]) for row in raw if row]
            return [float(value) for value in raw]

        raise RuntimeError("Unsupported model output format for reranker scores.")

    @staticmethod
    def _as_matrix(raw: Any) -> list[list[float]]:
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        if isinstance(raw, list):
            if not raw:
                return []
            if isinstance(raw[0], list):
                return [[float(value) for value in row] for row in raw]
            return [[float(value)] for value in raw]

        raise RuntimeError("Unsupported predict_proba output format.")

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _context_to_text(context: IntelligenceContext) -> str:
        return EmbeddingSimilarityFinalReranker._context_to_text(context)

    @staticmethod
    def _candidate_to_text(candidate: dict[str, Any]) -> str:
        return EmbeddingSimilarityFinalReranker._candidate_to_text(candidate)
