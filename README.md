# CLE Engine

CLE Engine is a language-learning platform that transforms contextual text input (manual text and OCR text) into personalized recommendations and practice exercises.

The system is built to answer three operational questions clearly:

1. What happened for a given user action?
2. Why did the model return those recommendations?
3. Is the system healthy enough to trust the output?

The backend architecture and persistence model are designed to preserve those answers through explicit trace records and provider health telemetry.

## System Components

- Backend API: FastAPI
- Frontend: Vite + React (pnpm)
- Admin UI: Streamlit
- Database: PostgreSQL + pgvector
- Secret management (local development): HashiCorp Vault (dev mode)

## Architecture Rationale

The backend moved from a single large service file to a modular structure with explicit responsibilities:

- [app/api/recommendation_service.py](app/api/recommendation_service.py): high-level coordinator; delegates contextual flow to pipeline stages.
- [app/api/recommendation_repository.py](app/api/recommendation_repository.py): SQL and persistence operations.
- [app/api/ranking_engine.py](app/api/ranking_engine.py): retrieval fusion and relevance explanation logic.
- [app/api/practice_engine.py](app/api/practice_engine.py): deterministic fallback practice generation.
- [app/api/embeddings.py](app/api/embeddings.py): async embedding providers with batch support and degradation tracking.
- [app/api/intelligence.py](app/api/intelligence.py): async recommendation/practice intelligence providers with explicit fail-fast behavior.
- [app/api/provider_health.py](app/api/provider_health.py): shared provider health state and degradation metrics.
- [app/api/pipeline/candidate_generator.py](app/api/pipeline/candidate_generator.py): initial hybrid candidate generation stage.
- [app/api/pipeline/final_reranker.py](app/api/pipeline/final_reranker.py): final reranker stage using pretrained model artifacts when present, with automatic fallback.
- [app/api/pipeline/decision_policy.py](app/api/pipeline/decision_policy.py): deterministic use-vs-regenerate policy stage.
- [app/api/pipeline/contextual_pipeline.py](app/api/pipeline/contextual_pipeline.py): explicit end-to-end recommendation pipeline orchestration.

This structure reduces coupling, removes N+1 persistence bottlenecks, and allows each concern to be optimized independently.

## Runtime Health Model

Health is evaluated at two levels:

- Database connectivity.
- Provider degradation state (embedding and intelligence providers).

The `/health` endpoint returns degraded when provider failure thresholds are exceeded even if the database is reachable.

## Configuration

Configuration is environment-based through [app/api/config.py](app/api/config.py).

Core variables:

- `DATABASE_URL`
- `DB_POOL_MIN_SIZE`
- `DB_POOL_MAX_SIZE`
- `EMBEDDING_BACKEND` (`hash`, `sentence_transformers`, `llm_api`)
- `INTELLIGENCE_BACKEND` (`heuristic`, `generic_http`)
- `EMBEDDING_DIMENSION`
- `LLM_API_KEY`
- `LLM_EMBEDDING_MODEL`
- `LLM_EMBEDDING_URL`
- `LLM_COMPLETION_MODEL`
- `LLM_COMPLETION_URL`
- `PROVIDER_STRICT_MODE`
- `PROVIDER_MAX_CONSECUTIVE_FAILURES`
- `RETRIEVAL_VECTOR_K`
- `RETRIEVAL_LEXICAL_K`
- `RETRIEVAL_FINAL_K`
- `RETRIEVAL_RRF_K`
- `RELEVANCE_APPROVAL_THRESHOLD`
- `RELEVANCE_REGENERATE_THRESHOLD`
- `FINAL_RERANKER_MODEL_DIR`
- `FINAL_RERANKER_MANIFEST_FILE`

Pretrained final reranker contract docs:

- [models/final_reranker/README.md](models/final_reranker/README.md)

## Vault-Managed Development Secrets

Backend, frontend, and admin variables are injected from Vault at startup.

Flow:

1. `vault` runs in dev mode.
2. `vault-init` writes policies, AppRole credentials, and service secrets.
3. Each service reads only its own Vault path.

Initialize local environment file:

```bash
cp .env.example .env
```

Set at minimum:

- `VAULT_DEV_ROOT_TOKEN_ID`
- `POSTGRES_PASSWORD`
- `FRONTEND_API_URL`
- `ADMIN_API_URL`
- `LLM_API_KEY`

## Local Setup

### Prerequisites

- Docker Desktop
- Git
- Make

Optional tools:

- mise
- LazyDocker

### Start the stack

```bash
cp .env.example .env
make clean-all
make build
make start
```

### Verify

```bash
make status
curl -s http://localhost:8000/health
```

## URLs

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Admin: http://localhost:8501
- Vault: http://localhost:8200
- PostgreSQL: localhost:5432

## Testing Strategy

The project supports three layers of testing:

1. Syntax and static validation.
2. Integration tests against local services.
3. Live model integration tests using real embedding and LLM providers.

See [docs/testing-live-llm.md](docs/testing-live-llm.md) for live test prerequisites and execution details.

## Developer Workflow

```bash
make start
make logs
make stop
```

Service-level commands:

```bash
make start-service SVC=frontend
make stop-service SVC=backend
make restart-service SVC=admin
make logs-service SVC=frontend
make shell SVC=backend
```

## Troubleshooting

### Startup instability on first boot

Retry after initialization delay:

```bash
make start
```

### Credential mismatch after DB password change

If `POSTGRES_PASSWORD` changed after DB volume creation, PostgreSQL still uses the original credential in persisted data.

Reset persisted DB state:

```bash
docker compose down -v
docker compose up --build
```

### Full reset

```bash
make clean-all
make rebuild
make start
```
