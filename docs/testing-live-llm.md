# Live LLM and Embedding Integration Tests

This document explains how to run the end-to-end test that uses real external provider calls for both:

- embeddings,
- recommendation/practice intelligence.

The test simulates one user journey through the API:

1. user upsert,
2. vocabulary bulk upsert,
3. contextual recommendation request (with OCR and topic context),
4. practice generation,
5. health snapshot verification.

## Important Notes

- This test is opt-in and skipped by default.
- It performs real network calls to your configured model provider.
- It may incur billing cost.

## Test File

- [tests/live/test_live_llm_flow.py](tests/live/test_live_llm_flow.py)

## Prerequisites

1. Backend API must be running and reachable.
2. Backend must be configured to use live providers:
   - `EMBEDDING_BACKEND=llm_api`
   - `INTELLIGENCE_BACKEND=generic_http`
3. Python test dependencies must be installed.

Install test dependencies:

```bash
pip install -e ".[dev]"
```

If you use Docker Compose for local stack:

```bash
make start
```

## Gemini Environment Example

Set these in `.env` before startup:

```bash
LLM_API_KEY=your-gemini-api-key
BACKEND_EMBEDDING_BACKEND=llm_api
BACKEND_INTELLIGENCE_BACKEND=generic_http
LLM_EMBEDDING_MODEL=text-embedding-004
LLM_EMBEDDING_URL=https://generativelanguage.googleapis.com/v1beta/openai/embeddings
LLM_COMPLETION_MODEL=gemini-2.0-flash
LLM_COMPLETION_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
```

Optional pretrained final reranker location:

```bash
FINAL_RERANKER_MODEL_DIR=models/final_reranker
FINAL_RERANKER_MANIFEST_FILE=manifest.json
```

When no reranker artifact exists in that folder, backend falls back automatically to embedding-similarity reranking.

## Clean Reinstall (Recommended)

For a clean bootstrap using updated Vault secrets:

```bash
make clean-all
make build
make start
```

`make start` removes the completed `vault-init` container after bootstrap.

## Required Environment Variables

Set these before running the test:

- `RUN_LIVE_LLM_TESTS=1`
- `LIVE_API_BASE_URL` (optional, default: `http://localhost:8000`)

The test validates the running backend health contract and expects these provider backends to be active:

- `llm_api` for embeddings,
- `generic_http` for intelligence.

## Run Commands

Run only live tests:

```bash
RUN_LIVE_LLM_TESTS=1 pytest -m live -q
```

Run the specific live flow test:

```bash
RUN_LIVE_LLM_TESTS=1 pytest tests/live/test_live_llm_flow.py -q
```

## Expected Outcome

A successful run means:

- the API accepts and persists a simulated user,
- vocabulary is inserted and retrieved,
- contextual recommendations are produced,
- practice exercises are generated,
- provider health shows the expected backends (`llm_api`, `generic_http`).

If the backend is not reachable or not configured with those provider backends, the test should fail with explicit assertions.
