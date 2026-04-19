# CLE Engine Backend API Documentation

## Purpose

The [app/api](.) package implements the backend application layer for CLE Engine. It is responsible for:

1. accepting and validating API input,
2. orchestrating recommendation and practice workflows,
3. persisting all workflow traces for auditability,
4. exposing runtime health and degradation state.

The package is intentionally split so database logic, ranking logic, and orchestration logic evolve independently.

## Architectural Model

### Why this structure exists

The previous monolithic service shape created three risks:

- high coupling between SQL and ranking algorithms,
- difficult performance tuning due to mixed concerns,
- hidden provider degradation due to broad fallback paths.

The current structure addresses those risks by isolating concerns.

### Core modules

- [main.py](main.py): application assembly, startup/shutdown lifecycle, and health endpoint.
- [config.py](config.py): typed runtime settings and environment parsing.
- [db.py](db.py): thread-safe PostgreSQL pooling via `ThreadedConnectionPool`.
- [recommendation_routes.py](recommendation_routes.py): async transport handlers.
- [schemas.py](schemas.py): request and response contracts.
- [recommendation_service.py](recommendation_service.py): high-level coordinator for recommendation and practice workflows.
- [recommendation_repository.py](recommendation_repository.py): SQL repository with batch write/read paths.
- [ranking_engine.py](ranking_engine.py): candidate fusion and relevance text generation.
- [practice_engine.py](practice_engine.py): deterministic practice fallback generation.
- [embeddings.py](embeddings.py): embedding providers, batch embedding, retry, and health tracking.
- [intelligence.py](intelligence.py): recommendation/practice intelligence providers, retry, fail-fast policy, and health tracking.
- [provider_health.py](provider_health.py): provider degradation state model.
- [pipeline/](pipeline): explicit recommendation pipeline stages (generation, final reranking, and decision policy).

### Pipeline modules

- [pipeline/candidate_generator.py](pipeline/candidate_generator.py): hybrid candidate generation stage (retrieval plus draft mapping).
- [pipeline/final_reranker.py](pipeline/final_reranker.py): final reranker stage used after initial candidate generation, with drop-in pretrained artifact support plus automatic fallback.
- [pipeline/decision_policy.py](pipeline/decision_policy.py): policy gate deciding `use_retrieved`, `regenerate_with_llm`, or review/fallback behavior.
- [pipeline/contextual_pipeline.py](pipeline/contextual_pipeline.py): orchestrates the full stage flow end-to-end.

## Runtime Dependency Flow

1. [main.py](main.py) loads `Settings`.
2. Database pool is opened.
3. Embedding and intelligence providers are built.
4. Repository and service orchestrator are created and stored in app state.
5. On shutdown, provider resources close first, then DB pool closes.

## Async Execution Strategy

The transport and orchestration layers are async.

- External provider calls are async methods.
- Blocking SQL work is executed through threadpool boundaries.
- Blocking model/HTTP libraries are wrapped with async thread offloading where required.

This design preserves compatibility with the current psycopg2 stack while allowing non-blocking API request handling.

## Data and Performance Strategy

### Recommendation flow

The contextual recommendation flow follows this sequence:

1. Candidate generation stage:
   - build context text,
   - generate query embedding,
   - retrieve lexical/vector candidates,
   - add mapped draft candidates,
   - fuse into one candidate pool.
2. Final reranker stage:
   - score and reorder the full candidate pool with the final model,
   - if pretrained reranker artifacts are present, use them,
   - otherwise fallback automatically to embedding-similarity reranking.
3. Decision policy stage:
   - decide whether to use current candidates or regenerate and rerank once.
4. Persistence stage:
   - persist run metadata, candidate traces, selected recommendations, and progress updates.

### Practice flow

1. Read recommendation-based seed terms.
2. Fall back to active vocabulary terms when recommendation history is unavailable.
3. Generate practice exercises through intelligence provider.
4. Use deterministic fallback generator if provider output is empty.
5. Persist session and items in batch.

### Performance principles

- Batch operations replace row-by-row persistence where possible.
- Provider HTTP clients reuse connection pools and retry policies.
- Embeddings support `embed_many` to reduce per-item network overhead.

## Provider Reliability and Fail-Fast

Embedding and intelligence providers track:

- total failures,
- consecutive failures,
- last error,
- degradation state.

When strict mode is enabled, providers enter fail-fast mode after a configured number of consecutive failures.

Relevant settings:

- `PROVIDER_STRICT_MODE`
- `PROVIDER_MAX_CONSECUTIVE_FAILURES`

## Health Endpoint Contract

`GET /health` returns:

- database state,
- embedding provider health snapshot,
- intelligence provider health snapshot,
- overall status (`healthy` or `degraded`).

A degraded provider can mark the overall status as degraded even when database connectivity is healthy.

## API Endpoints

All endpoints are under `/api/v1`.

- `POST /users/upsert`
- `POST /vocabulary/bulk-upsert`
- `POST /recommendations/contextual`
- `GET /practice/generate`

Request/response schemas are defined in [schemas.py](schemas.py).

## Configuration Surface

Configuration is environment-driven in [config.py](config.py).

Most relevant groups:

- database and pool sizing,
- embedding and intelligence provider backends,
- embedding dimension,
- retrieval and relevance thresholds,
- strict mode and fail-fast limits.

Pretrained final reranker settings:

- `FINAL_RERANKER_MODEL_DIR`
- `FINAL_RERANKER_MANIFEST_FILE`

Artifact contract reference:

- [models/final_reranker/README.md](../../models/final_reranker/README.md)

## Engineering Guidelines

1. Keep endpoint handlers thin and orchestration-focused.
2. Keep SQL and persistence details inside repository modules.
3. Keep ranking and explanation logic deterministic and testable.
4. Keep provider clients observable and explicit about failure/degradation.
5. Preserve trace persistence semantics when modifying recommendation logic.
