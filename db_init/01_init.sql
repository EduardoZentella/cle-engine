-- Schema initialization for CLE Engine

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Keep updated_at fields consistent.
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Build searchable text payload for vocabulary entries.
CREATE OR REPLACE FUNCTION set_vocabulary_search_text()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.search_text = to_tsvector(
        'simple',
        trim(
            both ' ' from
            coalesce(NEW.word, '') || ' ' ||
            coalesce(NEW.description, '') || ' ' ||
            coalesce(NEW.meaning, '') || ' ' ||
            coalesce(NEW.example_sentence, '') || ' ' ||
            array_to_string(coalesce(NEW.tags, ARRAY[]::TEXT[]), ' ')
        )
    );
    RETURN NEW;
END;
$$;

-- User profiles used to personalize retrieval + generation.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_user_id TEXT UNIQUE,
    email VARCHAR(255) UNIQUE,
    username VARCHAR(100) UNIQUE,
    first_name VARCHAR(120),
    middle_name VARCHAR(120),
    last_name VARCHAR(120),
    base_language VARCHAR(10) NOT NULL DEFAULT 'en',
    target_language VARCHAR(10) NOT NULL DEFAULT 'de',
    current_level VARCHAR(10) NOT NULL DEFAULT 'A1',
    city VARCHAR(120),
    country VARCHAR(120),
    region VARCHAR(120),
    area_type VARCHAR(20),
    profile_summary TEXT,
    profile_embedding vector(384),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_external_user_id ON users (external_user_id);
CREATE INDEX IF NOT EXISTS idx_users_base_target_lang ON users (base_language, target_language);

-- Master phrase/word catalogue that retrieval targets.
CREATE TABLE IF NOT EXISTS vocabulary_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    word_key TEXT UNIQUE,
    word VARCHAR(255) NOT NULL,
    description TEXT,
    meaning TEXT,
    example_sentence TEXT,
    category VARCHAR(120),
    cefr_level VARCHAR(10),
    tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    source_language VARCHAR(10) NOT NULL DEFAULT 'de',
    target_language VARCHAR(10) NOT NULL DEFAULT 'en',
    embedding vector(384),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    search_text TSVECTOR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (word, source_language, target_language)
);

CREATE INDEX IF NOT EXISTS idx_vocab_entries_active ON vocabulary_entries (is_active);
CREATE INDEX IF NOT EXISTS idx_vocab_entries_source_target ON vocabulary_entries (source_language, target_language);
CREATE INDEX IF NOT EXISTS idx_vocab_entries_search_text ON vocabulary_entries USING GIN (search_text);
CREATE INDEX IF NOT EXISTS idx_vocab_entries_word_trgm ON vocabulary_entries USING GIN (word gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_vocab_entries_embedding_hnsw ON vocabulary_entries USING HNSW (embedding vector_cosine_ops);

-- Every translation interaction from the client, with context trace.
CREATE TABLE IF NOT EXISTS translation_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    location TEXT,
    environment TEXT,
    sentiment VARCHAR(50),
    intent TEXT,
    context JSONB NOT NULL DEFAULT '{}'::JSONB,
    context_text TEXT NOT NULL,
    context_embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_translation_events_user_id ON translation_events (user_id);
CREATE INDEX IF NOT EXISTS idx_translation_events_created_at ON translation_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_translation_events_context_hnsw ON translation_events USING HNSW (context_embedding vector_cosine_ops);

-- One recommendation run per request; stores final model decision.
CREATE TABLE IF NOT EXISTS recommendation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    translation_event_id UUID REFERENCES translation_events(id) ON DELETE SET NULL,
    retrieval_query TEXT NOT NULL,
    retrieval_embedding vector(384),
    predicted_level VARCHAR(10),
    model_action VARCHAR(40) NOT NULL DEFAULT 'use_retrieved',
    model_trace JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (model_action IN ('use_retrieved', 'regenerate_with_llm', 'fallback_llm', 'manual_review'))
);

CREATE INDEX IF NOT EXISTS idx_recommendation_runs_user_id ON recommendation_runs (user_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_runs_created_at ON recommendation_runs (created_at DESC);

-- Candidate phrases from vector retrieval, lexical retrieval, and reranking.
CREATE TABLE IF NOT EXISTS recommendation_candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    vocabulary_id UUID NOT NULL REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
    source VARCHAR(30) NOT NULL,
    vector_score DOUBLE PRECISION,
    lexical_score DOUBLE PRECISION,
    fusion_score DOUBLE PRECISION NOT NULL,
    rank_position INT NOT NULL,
    selected BOOLEAN NOT NULL DEFAULT FALSE,
    relevance_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source IN ('vector', 'lexical', 'hybrid', 'llm_refine')),
    UNIQUE (run_id, vocabulary_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_candidates_run_id ON recommendation_candidates (run_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_candidates_rank ON recommendation_candidates (run_id, rank_position);
CREATE INDEX IF NOT EXISTS idx_recommendation_candidates_selected ON recommendation_candidates (selected);

-- Learning/progress signals per user and vocabulary entry.
CREATE TABLE IF NOT EXISTS user_vocabulary_progress (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocabulary_id UUID NOT NULL REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
    encounter_count INT NOT NULL DEFAULT 0,
    mastery_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_seen_at TIMESTAMPTZ,
    last_practiced_at TIMESTAMPTZ,
    last_source VARCHAR(50),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, vocabulary_id)
);

CREATE INDEX IF NOT EXISTS idx_user_vocab_progress_mastery ON user_vocabulary_progress (user_id, mastery_score DESC);

-- Persist generated practice payloads from the backend.
CREATE TABLE IF NOT EXISTS exercise_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE SET NULL,
    context_theme TEXT,
    generated_by VARCHAR(30) NOT NULL DEFAULT 'llm',
    status VARCHAR(20) NOT NULL DEFAULT 'generated',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('generated', 'served', 'completed', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_exercise_sessions_user_id ON exercise_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_exercise_sessions_created_at ON exercise_sessions (created_at DESC);

CREATE TABLE IF NOT EXISTS exercise_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES exercise_sessions(id) ON DELETE CASCADE,
    exercise_type VARCHAR(40) NOT NULL,
    prompt TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]'::JSONB,
    correct_answer TEXT,
    explanation TEXT,
    difficulty VARCHAR(10),
    position INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (exercise_type IN ('fill_in_the_blank', 'multiple_choice', 'translation', 'open_response'))
);

CREATE INDEX IF NOT EXISTS idx_exercise_items_session_id ON exercise_items (session_id, position);

-- Triggers for tables with updated_at columns.
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_timestamp();

DROP TRIGGER IF EXISTS trg_vocab_entries_updated_at ON vocabulary_entries;
CREATE TRIGGER trg_vocab_entries_updated_at
BEFORE UPDATE ON vocabulary_entries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_timestamp();

DROP TRIGGER IF EXISTS trg_vocab_entries_search_text ON vocabulary_entries;
CREATE TRIGGER trg_vocab_entries_search_text
BEFORE INSERT OR UPDATE ON vocabulary_entries
FOR EACH ROW
EXECUTE FUNCTION set_vocabulary_search_text();

DROP TRIGGER IF EXISTS trg_user_vocab_progress_updated_at ON user_vocabulary_progress;
CREATE TRIGGER trg_user_vocab_progress_updated_at
BEFORE UPDATE ON user_vocabulary_progress
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_timestamp();

-- Keep permissions explicit for local dev role.
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;

-- Seed student profiles used by recommendation flows.
INSERT INTO users (
    username,
    email,
    first_name,
    middle_name,
    last_name,
    base_language,
    target_language,
    current_level,
    city,
    area_type,
    profile_summary,
    metadata
)
VALUES
(
    'eduardo.zentella.castillo',
    'eduardo.zentella.castillo@student.local',
    'Eduardo',
    null,
    'Zentella Castillo',
    'es',
    'de',
    'A2',
    'Cologne',
    'urban',
    'Student profile: native Spanish speaker, English C1, German A2.',
    jsonb_build_object(
        'full_name', 'Eduardo Zentella Castillo',
        'is_student', true,
        'languages', jsonb_build_array(
            jsonb_build_object('language', 'Spanish', 'code', 'es', 'proficiency', 'Native'),
            jsonb_build_object('language', 'English', 'code', 'en', 'proficiency', 'C1'),
            jsonb_build_object('language', 'German', 'code', 'de', 'proficiency', 'A2')
        ),
        'common_locations', jsonb_build_array(
            'University',
            'Library',
            'Supermarket',
            'Bar',
            'Bank',
            'Restaurant',
            'Cafeteria',
            'Bus Stop'
        )
    )
),
(
    'anton.aivazov',
    'anton.aivazov@student.local',
    'Anton',
    null,
    'Aivazov',
    'ru',
    'de',
    'B1',
    'Cologne',
    'urban',
    'Student profile: native Russian and Spanish speaker, English C1, German B1.',
    jsonb_build_object(
        'full_name', 'Anton Aivazov',
        'is_student', true,
        'languages', jsonb_build_array(
            jsonb_build_object('language', 'Russian', 'code', 'ru', 'proficiency', 'Native'),
            jsonb_build_object('language', 'Spanish', 'code', 'es', 'proficiency', 'Native'),
            jsonb_build_object('language', 'English', 'code', 'en', 'proficiency', 'C1'),
            jsonb_build_object('language', 'German', 'code', 'de', 'proficiency', 'B1')
        ),
        'common_locations', jsonb_build_array(
            'University',
            'Library',
            'Supermarket',
            'Bar',
            'Bank',
            'Restaurant',
            'Cafeteria',
            'Student Housing'
        )
    )
),
(
    'raspina.jafari',
    'raspina.jafari@student.local',
    'Raspina',
    null,
    'Jafari',
    'fa',
    'de',
    'A1',
    'Cologne',
    'urban',
    'Student profile: native Persian speaker, English C1, German A1.',
    jsonb_build_object(
        'full_name', 'Raspina Jafari',
        'is_student', true,
        'languages', jsonb_build_array(
            jsonb_build_object('language', 'Persian', 'code', 'fa', 'proficiency', 'Native'),
            jsonb_build_object('language', 'English', 'code', 'en', 'proficiency', 'C1'),
            jsonb_build_object('language', 'German', 'code', 'de', 'proficiency', 'A1')
        ),
        'common_locations', jsonb_build_array(
            'University',
            'Library',
            'Supermarket',
            'Bar',
            'Bank',
            'Restaurant',
            'Cafeteria',
            'Gym'
        )
    )
)
ON CONFLICT (username) DO UPDATE
SET
    email = EXCLUDED.email,
    first_name = EXCLUDED.first_name,
    middle_name = EXCLUDED.middle_name,
    last_name = EXCLUDED.last_name,
    base_language = EXCLUDED.base_language,
    target_language = EXCLUDED.target_language,
    current_level = EXCLUDED.current_level,
    city = EXCLUDED.city,
    area_type = EXCLUDED.area_type,
    profile_summary = EXCLUDED.profile_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Performance metrics table for tracking pipeline stage timings
CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    stage VARCHAR(50) NOT NULL,
    duration_ms FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    attempt SMALLINT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_metrics_stage ON performance_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_user_id ON performance_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_created_at ON performance_metrics(created_at DESC);

-- Debug logs table for detailed troubleshooting
CREATE TABLE IF NOT EXISTS debug_logs (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    stage VARCHAR(50),
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debug_logs_level ON debug_logs(level);
CREATE INDEX IF NOT EXISTS idx_debug_logs_user_id ON debug_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_debug_logs_stage ON debug_logs(stage);
CREATE INDEX IF NOT EXISTS idx_debug_logs_created_at ON debug_logs(created_at DESC);

-- Extend users table with activity tracking columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS activity_count INT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS level_confidence FLOAT DEFAULT 0.5;
