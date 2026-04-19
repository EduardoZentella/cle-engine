"""Ranking and relevance presentation helpers for recommendation candidates."""

from __future__ import annotations

from typing import Any

from app.api.config import Settings


class CandidateRanker:
    """Fuses retrieval candidate lists and builds user-facing relevance text."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fuse_candidates(
        self,
        vector_rows: list[dict[str, Any]],
        lexical_rows: list[dict[str, Any]],
        llm_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fuse vector, lexical, and LLM lists using weighted RRF strategy."""

        by_vocab: dict[str, dict[str, Any]] = {}

        for rank, row in enumerate(vector_rows, start=1):
            vocab_id = str(row["id"])
            candidate = by_vocab.setdefault(
                vocab_id,
                {
                    "vocabulary_id": vocab_id,
                    "word": row["word"],
                    "meaning": row.get("meaning"),
                    "description": row.get("description"),
                    "vector_score": None,
                    "lexical_score": None,
                    "llm_score": None,
                    "llm_rationale": None,
                    "fusion_score": 0.0,
                    "sources": set(),
                },
            )
            candidate["vector_score"] = float(row.get("vector_score") or 0.0)
            candidate["fusion_score"] += 1.0 / (self._settings.retrieval_rrf_k + rank)
            candidate["sources"].add("vector")

        for rank, row in enumerate(lexical_rows, start=1):
            vocab_id = str(row["id"])
            candidate = by_vocab.setdefault(
                vocab_id,
                {
                    "vocabulary_id": vocab_id,
                    "word": row["word"],
                    "meaning": row.get("meaning"),
                    "description": row.get("description"),
                    "vector_score": None,
                    "lexical_score": None,
                    "llm_score": None,
                    "llm_rationale": None,
                    "fusion_score": 0.0,
                    "sources": set(),
                },
            )
            candidate["lexical_score"] = float(row.get("lexical_score") or 0.0)
            candidate["fusion_score"] += 1.0 / (self._settings.retrieval_rrf_k + rank)
            candidate["sources"].add("lexical")

        for rank, row in enumerate(llm_rows, start=1):
            vocab_id = str(row["id"])
            candidate = by_vocab.setdefault(
                vocab_id,
                {
                    "vocabulary_id": vocab_id,
                    "word": row["word"],
                    "meaning": row.get("meaning"),
                    "description": row.get("description"),
                    "vector_score": None,
                    "lexical_score": None,
                    "llm_score": None,
                    "llm_rationale": None,
                    "fusion_score": 0.0,
                    "sources": set(),
                },
            )
            llm_score = float(row.get("llm_score") or 0.0)
            candidate["llm_score"] = llm_score
            candidate["llm_rationale"] = row.get("llm_rationale")
            candidate["fusion_score"] += (1.0 / (self._settings.retrieval_rrf_k + rank)) + (
                0.50 * llm_score
            )
            candidate["sources"].add("llm_refine")

        ranked = sorted(
            by_vocab.values(),
            key=lambda item: (
                item["fusion_score"],
                item.get("vector_score") or 0.0,
                item.get("lexical_score") or 0.0,
                item.get("llm_score") or 0.0,
            ),
            reverse=True,
        )

        normalized: list[dict[str, Any]] = []
        for index, candidate in enumerate(ranked, start=1):
            source_set = candidate.pop("sources")
            if source_set == {"llm_refine"}:
                source = "llm_refine"
            elif len(source_set) > 1:
                source = "hybrid"
            elif "vector" in source_set:
                source = "vector"
            elif "lexical" in source_set:
                source = "lexical"
            else:
                source = "llm_refine"

            candidate["source"] = source
            candidate["rank_position"] = index
            normalized.append(candidate)

        return normalized

    @staticmethod
    def build_relevance(candidate: dict[str, Any]) -> str:
        """Create user-facing relevance summary from candidate source type."""

        source = candidate["source"]
        ml_reason = candidate.get("ml_reason")
        llm_rationale = candidate.get("llm_rationale")

        if source == "llm_refine":
            if llm_rationale:
                return str(llm_rationale)
            if ml_reason:
                return str(ml_reason)
            return "Suggested by LLM and accepted by relevance model."

        base = "Matched by lexical search relevance in context text."
        if source == "hybrid":
            base = "Matched by both semantic vector retrieval and lexical ranking."
        elif source == "vector":
            base = "Matched by semantic similarity in embedding space."

        if ml_reason:
            return f"{base} {ml_reason}"
        return base
