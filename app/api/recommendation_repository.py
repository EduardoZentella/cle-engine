"""Database repository for recommendation and practice workflows."""

from __future__ import annotations

import json
from typing import Any, Sequence
from uuid import UUID

from psycopg2.extras import RealDictCursor, execute_values

from app.api.config import Settings
from app.api.db import DatabasePool
from app.api.schemas import PracticeExercise, RecommendationRequest, UserUpsertRequest, VocabularyUpsertItem


class RecommendationRepository:
    """Encapsulates SQL operations for recommendation domain workflows."""

    def __init__(self, database: DatabasePool, settings: Settings) -> None:
        self._database = database
        self._settings = settings

    def ping(self) -> bool:
        try:
            with self._database.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            return True
        except Exception:
            return False

    def upsert_user(
        self,
        *,
        user_id: UUID,
        username: str,
        payload: UserUpsertRequest,
        profile_vector_literal: str | None,
    ) -> bool:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT 1 FROM users WHERE id = %s", (str(user_id),))
                exists = cur.fetchone() is not None

                if profile_vector_literal is None:
                    cur.execute(
                        """
                        INSERT INTO users (
                            id,
                            external_user_id,
                            email,
                            username,
                            first_name,
                            middle_name,
                            last_name,
                            base_language,
                            target_language,
                            current_level,
                            city,
                            country,
                            region,
                            area_type,
                            profile_summary,
                            metadata
                        )
                        VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s::jsonb
                        )
                        ON CONFLICT (id)
                        DO UPDATE SET
                            external_user_id = COALESCE(EXCLUDED.external_user_id, users.external_user_id),
                            email = COALESCE(EXCLUDED.email, users.email),
                            username = COALESCE(EXCLUDED.username, users.username),
                            first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                            middle_name = COALESCE(EXCLUDED.middle_name, users.middle_name),
                            last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                            base_language = EXCLUDED.base_language,
                            target_language = EXCLUDED.target_language,
                            current_level = EXCLUDED.current_level,
                            city = COALESCE(EXCLUDED.city, users.city),
                            country = COALESCE(EXCLUDED.country, users.country),
                            region = COALESCE(EXCLUDED.region, users.region),
                            area_type = COALESCE(EXCLUDED.area_type, users.area_type),
                            profile_summary = COALESCE(EXCLUDED.profile_summary, users.profile_summary),
                            metadata = users.metadata || EXCLUDED.metadata,
                            updated_at = NOW();
                        """,
                        (
                            str(user_id),
                            payload.external_user_id,
                            payload.email,
                            username,
                            payload.first_name,
                            payload.middle_name,
                            payload.last_name,
                            payload.base_language,
                            payload.target_language,
                            payload.current_level,
                            payload.city,
                            payload.country,
                            payload.region,
                            payload.area_type,
                            payload.profile_summary,
                            json.dumps(payload.metadata),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO users (
                            id,
                            external_user_id,
                            email,
                            username,
                            first_name,
                            middle_name,
                            last_name,
                            base_language,
                            target_language,
                            current_level,
                            city,
                            country,
                            region,
                            area_type,
                            profile_summary,
                            profile_embedding,
                            metadata
                        )
                        VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s::vector, %s::jsonb
                        )
                        ON CONFLICT (id)
                        DO UPDATE SET
                            external_user_id = COALESCE(EXCLUDED.external_user_id, users.external_user_id),
                            email = COALESCE(EXCLUDED.email, users.email),
                            username = COALESCE(EXCLUDED.username, users.username),
                            first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                            middle_name = COALESCE(EXCLUDED.middle_name, users.middle_name),
                            last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                            base_language = EXCLUDED.base_language,
                            target_language = EXCLUDED.target_language,
                            current_level = EXCLUDED.current_level,
                            city = COALESCE(EXCLUDED.city, users.city),
                            country = COALESCE(EXCLUDED.country, users.country),
                            region = COALESCE(EXCLUDED.region, users.region),
                            area_type = COALESCE(EXCLUDED.area_type, users.area_type),
                            profile_summary = COALESCE(EXCLUDED.profile_summary, users.profile_summary),
                            profile_embedding = COALESCE(EXCLUDED.profile_embedding, users.profile_embedding),
                            metadata = users.metadata || EXCLUDED.metadata,
                            updated_at = NOW();
                        """,
                        (
                            str(user_id),
                            payload.external_user_id,
                            payload.email,
                            username,
                            payload.first_name,
                            payload.middle_name,
                            payload.last_name,
                            payload.base_language,
                            payload.target_language,
                            payload.current_level,
                            payload.city,
                            payload.country,
                            payload.region,
                            payload.area_type,
                            payload.profile_summary,
                            profile_vector_literal,
                            json.dumps(payload.metadata),
                        ),
                    )

        return not exists

    def bulk_upsert_vocabulary(
        self,
        items: Sequence[VocabularyUpsertItem],
        vector_literals: Sequence[str],
    ) -> int:
        if not items:
            return 0

        rows = [
            (
                item.word_key,
                item.word,
                item.description,
                item.meaning,
                item.example_sentence,
                item.category,
                item.cefr_level,
                item.tags,
                item.source_language,
                item.target_language,
                vector_literals[index],
                json.dumps(item.metadata),
            )
            for index, item in enumerate(items)
        ]

        with self._database.connection() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO vocabulary_entries (
                        word_key,
                        word,
                        description,
                        meaning,
                        example_sentence,
                        category,
                        cefr_level,
                        tags,
                        source_language,
                        target_language,
                        embedding,
                        metadata
                    )
                    VALUES %s
                    ON CONFLICT (word, source_language, target_language)
                    DO UPDATE SET
                        word_key = COALESCE(EXCLUDED.word_key, vocabulary_entries.word_key),
                        description = COALESCE(EXCLUDED.description, vocabulary_entries.description),
                        meaning = COALESCE(EXCLUDED.meaning, vocabulary_entries.meaning),
                        example_sentence = COALESCE(EXCLUDED.example_sentence, vocabulary_entries.example_sentence),
                        category = COALESCE(EXCLUDED.category, vocabulary_entries.category),
                        cefr_level = COALESCE(EXCLUDED.cefr_level, vocabulary_entries.cefr_level),
                        tags = EXCLUDED.tags,
                        embedding = EXCLUDED.embedding,
                        metadata = vocabulary_entries.metadata || EXCLUDED.metadata,
                        is_active = TRUE,
                        updated_at = NOW();
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb)",
                )

        return len(rows)

    def prepare_recommendation_context(
        self,
        payload: RecommendationRequest,
        context_text: str,
        context_json: dict[str, Any],
        context_vector_literal: str,
    ) -> dict[str, Any]:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                predicted_level = self._ensure_user(cur=cur, payload=payload)
                translation_event_id = self._insert_translation_event(
                    cur=cur,
                    payload=payload,
                    context_text=context_text,
                    context_json=context_json,
                    context_vector_literal=context_vector_literal,
                )
                vector_rows = self._vector_candidates(
                    cur=cur,
                    source_language=payload.action.source_language,
                    target_language=payload.action.target_language,
                    retrieval_vector_literal=context_vector_literal,
                )
                lexical_rows = self._lexical_candidates(
                    cur=cur,
                    source_language=payload.action.source_language,
                    target_language=payload.action.target_language,
                    query_text=context_text,
                )

        return {
            "predicted_level": predicted_level,
            "translation_event_id": translation_event_id,
            "vector_rows": vector_rows,
            "lexical_rows": lexical_rows,
        }

    def map_llm_drafts(
        self,
        *,
        source_language: str,
        target_language: str,
        llm_drafts: Sequence[Any],
    ) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for draft in llm_drafts:
            phrase = str(getattr(draft, "phrase", "")).strip()
            if not phrase:
                continue
            key = phrase.lower()
            confidence = float(getattr(draft, "confidence", 0.5))
            existing = deduped.get(key)
            if existing is None or confidence > existing["confidence"]:
                deduped[key] = {
                    "phrase": phrase,
                    "meaning": str(getattr(draft, "meaning", "") or ""),
                    "confidence": confidence,
                    "rationale": str(getattr(draft, "rationale", "") or ""),
                }

        if not deduped:
            return []

        phrases = [entry["phrase"] for entry in deduped.values()]
        meanings = [entry["meaning"] for entry in deduped.values()]
        scores = [entry["confidence"] for entry in deduped.values()]
        rationales = [entry["rationale"] for entry in deduped.values()]

        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    WITH llm_inputs AS (
                        SELECT *
                        FROM unnest(
                            %s::text[],
                            %s::text[],
                            %s::double precision[],
                            %s::text[]
                        ) AS t(phrase, draft_meaning, llm_score, llm_rationale)
                    ),
                    ranked AS (
                        SELECT DISTINCT ON (li.phrase)
                            ve.id,
                            ve.word,
                            COALESCE(ve.meaning, NULLIF(li.draft_meaning, '')) AS meaning,
                            ve.description,
                            li.llm_score,
                            li.llm_rationale,
                            similarity(lower(ve.word), lower(li.phrase)) AS word_similarity,
                            lower(ve.word) = lower(li.phrase) AS exact_match
                        FROM llm_inputs li
                        JOIN vocabulary_entries ve
                          ON ve.is_active = TRUE
                         AND ve.source_language = %s
                         AND ve.target_language = %s
                        ORDER BY
                            li.phrase,
                            exact_match DESC,
                            similarity(lower(ve.word), lower(li.phrase)) DESC,
                            ve.updated_at DESC
                    )
                    SELECT
                        id,
                        word,
                        meaning,
                        description,
                        llm_score,
                        llm_rationale
                    FROM ranked
                    WHERE exact_match OR word_similarity >= %s;
                    """,
                    (
                        phrases,
                        meanings,
                        scores,
                        rationales,
                        source_language,
                        target_language,
                        0.25,
                    ),
                )
                return [dict(row) for row in cur.fetchall()]

    def persist_recommendation_outcome(
        self,
        *,
        payload: RecommendationRequest,
        translation_event_id: str,
        retrieval_query: str,
        retrieval_vector_literal: str,
        predicted_level: str,
        model_action: str,
        candidates: list[dict[str, Any]],
        selected_candidates: list[dict[str, Any]],
        vector_count: int,
        lexical_count: int,
        llm_count: int,
        ml_approved_count: int,
        ml_total_count: int,
    ) -> str:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                run_id = self._insert_recommendation_run(
                    cur=cur,
                    payload=payload,
                    translation_event_id=translation_event_id,
                    retrieval_query=retrieval_query,
                    retrieval_vector_literal=retrieval_vector_literal,
                    predicted_level=predicted_level,
                    model_action=model_action,
                    vector_count=vector_count,
                    lexical_count=lexical_count,
                    llm_count=llm_count,
                    ml_approved_count=ml_approved_count,
                    ml_total_count=ml_total_count,
                )
                self._persist_candidates_bulk(
                    cur=cur,
                    run_id=run_id,
                    candidates=candidates,
                )
                self._upsert_user_progress_bulk(
                    cur=cur,
                    user_id=payload.user_id,
                    selected_candidates=selected_candidates,
                )

        return run_id

    def fetch_practice_seed_rows(self, user_id: UUID, limit: int) -> list[dict[str, Any]]:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        ve.word,
                        ve.meaning,
                        ve.description,
                        ve.category
                    FROM recommendation_candidates AS rc
                    INNER JOIN recommendation_runs AS rr
                        ON rr.id = rc.run_id
                    INNER JOIN vocabulary_entries AS ve
                        ON ve.id = rc.vocabulary_id
                    WHERE rr.user_id = %s
                      AND rc.selected = TRUE
                    ORDER BY rr.created_at DESC, rc.rank_position ASC
                    LIMIT %s;
                    """,
                    (str(user_id), limit),
                )
                rows = [dict(row) for row in cur.fetchall()]

                if rows:
                    return rows

                cur.execute(
                    """
                    SELECT
                        word,
                        meaning,
                        description,
                        category
                    FROM vocabulary_entries
                    WHERE is_active = TRUE
                    ORDER BY updated_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]

    def fetch_latest_user_context(self, user_id: UUID) -> dict[str, Any]:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        u.current_level,
                        u.base_language,
                        u.target_language,
                        te.source_text,
                        te.translated_text,
                        te.location,
                        te.environment,
                        te.sentiment,
                        te.intent
                    FROM users AS u
                    LEFT JOIN LATERAL (
                        SELECT
                            source_text,
                            translated_text,
                            location,
                            environment,
                            sentiment,
                            intent
                        FROM translation_events
                        WHERE user_id = u.id
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) AS te ON TRUE
                    WHERE u.id = %s
                    LIMIT 1;
                    """,
                    (str(user_id),),
                )
                row = cur.fetchone() or {}
                return dict(row)

    def persist_practice_session(
        self,
        *,
        user_id: UUID,
        context_theme: str,
        exercises: Sequence[PracticeExercise],
    ) -> None:
        with self._database.connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO exercise_sessions (
                        user_id,
                        context_theme,
                        generated_by,
                        status
                    )
                    VALUES (%s, %s, 'llm', 'generated')
                    RETURNING id;
                    """,
                    (str(user_id), context_theme),
                )
                session_row = cur.fetchone()
                if session_row is None:
                    raise RuntimeError("Failed to create exercise session.")
                session_id = str(session_row["id"])

                rows = [
                    (
                        session_id,
                        item.type,
                        item.prompt,
                        json.dumps(item.options),
                        item.correct_answer,
                        item.explanation,
                        position,
                    )
                    for position, item in enumerate(exercises, start=1)
                ]
                if rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO exercise_items (
                            session_id,
                            exercise_type,
                            prompt,
                            options,
                            correct_answer,
                            explanation,
                            difficulty,
                            position
                        )
                        VALUES %s;
                        """,
                        rows,
                        template="(%s, %s, %s, %s::jsonb, %s, %s, NULL, %s)",
                    )

    def _ensure_user(self, cur: RealDictCursor, payload: RecommendationRequest) -> str:
        cur.execute(
            "SELECT current_level FROM users WHERE id = %s;",
            (str(payload.user_id),),
        )
        row = cur.fetchone()
        if row:
            return row["current_level"] or "A1"

        cur.execute(
            """
            INSERT INTO users (
                id,
                username,
                base_language,
                target_language,
                current_level
            )
            VALUES (%s, %s, %s, %s, 'A1')
            ON CONFLICT (id) DO NOTHING;
            """,
            (
                str(payload.user_id),
                f"user_{str(payload.user_id)[:8]}",
                payload.action.target_language,
                payload.action.source_language,
            ),
        )
        return "A1"

    def _insert_translation_event(
        self,
        cur: RealDictCursor,
        payload: RecommendationRequest,
        context_text: str,
        context_json: dict[str, Any],
        context_vector_literal: str,
    ) -> str:
        cur.execute(
            """
            INSERT INTO translation_events (
                user_id,
                source_text,
                translated_text,
                source_language,
                target_language,
                location,
                environment,
                sentiment,
                intent,
                context,
                context_text,
                context_embedding
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb, %s, %s::vector
            )
            RETURNING id;
            """,
            (
                str(payload.user_id),
                payload.action.original_text,
                payload.action.translation,
                payload.action.source_language,
                payload.action.target_language,
                payload.action.context.location,
                payload.action.context.environment,
                payload.action.context.sentiment,
                payload.action.context.intent,
                json.dumps(context_json),
                context_text,
                context_vector_literal,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to persist translation event.")
        return str(row["id"])

    def _vector_candidates(
        self,
        cur: RealDictCursor,
        source_language: str,
        target_language: str,
        retrieval_vector_literal: str,
    ) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT
                id,
                word,
                meaning,
                description,
                1 - (embedding <=> %s::vector) AS vector_score
            FROM vocabulary_entries
            WHERE is_active = TRUE
              AND embedding IS NOT NULL
              AND source_language = %s
              AND target_language = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (
                retrieval_vector_literal,
                source_language,
                target_language,
                retrieval_vector_literal,
                self._settings.retrieval_vector_k,
            ),
        )
        return [dict(row) for row in cur.fetchall()]

    def _lexical_candidates(
        self,
        cur: RealDictCursor,
        source_language: str,
        target_language: str,
        query_text: str,
    ) -> list[dict[str, Any]]:
        cleaned = query_text.strip()
        if not cleaned:
            return []

        cur.execute(
            """
            WITH query AS (
                SELECT websearch_to_tsquery('simple', %s) AS q
            )
            SELECT
                ve.id,
                ve.word,
                ve.meaning,
                ve.description,
                ts_rank_cd(ve.search_text, query.q) AS lexical_score
            FROM vocabulary_entries AS ve
            CROSS JOIN query
            WHERE ve.is_active = TRUE
              AND ve.source_language = %s
              AND ve.target_language = %s
              AND ve.search_text @@ query.q
            ORDER BY lexical_score DESC
            LIMIT %s;
            """,
            (
                cleaned,
                source_language,
                target_language,
                self._settings.retrieval_lexical_k,
            ),
        )
        return [dict(row) for row in cur.fetchall()]

    def _insert_recommendation_run(
        self,
        cur: RealDictCursor,
        payload: RecommendationRequest,
        translation_event_id: str,
        retrieval_query: str,
        retrieval_vector_literal: str,
        predicted_level: str,
        model_action: str,
        vector_count: int,
        lexical_count: int,
        llm_count: int,
        ml_approved_count: int,
        ml_total_count: int,
    ) -> str:
        trace = {
            "vector_candidates": vector_count,
            "lexical_candidates": lexical_count,
            "llm_candidates": llm_count,
            "ml_approved": ml_approved_count,
            "ml_total": ml_total_count,
            "retrieval_strategy": "rrf_hybrid_llm",
            "vector_k": self._settings.retrieval_vector_k,
            "lexical_k": self._settings.retrieval_lexical_k,
        }

        cur.execute(
            """
            INSERT INTO recommendation_runs (
                user_id,
                translation_event_id,
                retrieval_query,
                retrieval_embedding,
                predicted_level,
                model_action,
                model_trace
            )
            VALUES (%s, %s, %s, %s::vector, %s, %s, %s::jsonb)
            RETURNING id;
            """,
            (
                str(payload.user_id),
                translation_event_id,
                retrieval_query,
                retrieval_vector_literal,
                predicted_level,
                model_action,
                json.dumps(trace),
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to persist recommendation run.")
        return str(row["id"])

    def _persist_candidates_bulk(
        self,
        cur: RealDictCursor,
        run_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        if not candidates:
            return

        rows = [
            (
                run_id,
                candidate["vocabulary_id"],
                candidate["source"],
                candidate.get("vector_score"),
                candidate.get("lexical_score"),
                candidate["fusion_score"],
                candidate["rank_position"],
                candidate["selected"],
                candidate["relevance_reason"],
            )
            for candidate in candidates
        ]

        execute_values(
            cur,
            """
            INSERT INTO recommendation_candidates (
                run_id,
                vocabulary_id,
                source,
                vector_score,
                lexical_score,
                fusion_score,
                rank_position,
                selected,
                relevance_reason
            )
            VALUES %s
            ON CONFLICT (run_id, vocabulary_id)
            DO UPDATE SET
                source = EXCLUDED.source,
                vector_score = EXCLUDED.vector_score,
                lexical_score = EXCLUDED.lexical_score,
                fusion_score = EXCLUDED.fusion_score,
                rank_position = EXCLUDED.rank_position,
                selected = EXCLUDED.selected,
                relevance_reason = EXCLUDED.relevance_reason;
            """,
            rows,
        )

    def _upsert_user_progress_bulk(
        self,
        cur: RealDictCursor,
        user_id: UUID,
        selected_candidates: list[dict[str, Any]],
    ) -> None:
        if not selected_candidates:
            return

        vocabulary_ids: list[str] = []
        seen: set[str] = set()
        for candidate in selected_candidates:
            vocabulary_id = str(candidate["vocabulary_id"])
            if vocabulary_id in seen:
                continue
            seen.add(vocabulary_id)
            vocabulary_ids.append(vocabulary_id)

        rows = [(str(user_id), vocabulary_id) for vocabulary_id in vocabulary_ids]

        execute_values(
            cur,
            """
            INSERT INTO user_vocabulary_progress (
                user_id,
                vocabulary_id,
                encounter_count,
                mastery_score,
                last_seen_at,
                last_source
            )
            VALUES %s
            ON CONFLICT (user_id, vocabulary_id)
            DO UPDATE SET
                encounter_count = user_vocabulary_progress.encounter_count + 1,
                last_seen_at = NOW(),
                last_source = 'recommendation',
                updated_at = NOW();
            """,
            rows,
            template="(%s, %s, 1, 0.0, NOW(), 'recommendation')",
        )
