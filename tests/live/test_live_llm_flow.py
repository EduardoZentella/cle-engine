"""Live integration tests for real LLM and embedding providers.

These tests are intentionally opt-in because they:

- call external model APIs,
- require a running backend stack,
- may incur provider costs.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import time
from typing import Any, Mapping, cast
from uuid import uuid4

import pytest
import requests


pytestmark = [pytest.mark.live]


def _log(message: str) -> None:
    print(f"[live-test] {message}", flush=True)


@contextmanager
def _timed_step(timings: list[tuple[str, float]], label: str):
    _log(f"START {label}")
    started_at = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started_at
        timings.append((label, elapsed))
        _log(f"DONE  {label} ({elapsed:.3f}s)")


def _print_timing_summary(timings: list[tuple[str, float]], total_elapsed: float) -> None:
    if not timings:
        _log("No timing data collected.")
        return

    _log("Performance summary by step:")
    for label, elapsed in timings:
        share = (elapsed / total_elapsed * 100.0) if total_elapsed > 0 else 0.0
        _log(f"  - {label}: {elapsed:.3f}s ({share:.1f}%)")
    _log(f"  - total_flow: {total_elapsed:.3f}s (100.0%)")


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _require_live_execution() -> None:
    if not _is_truthy(os.getenv("RUN_LIVE_LLM_TESTS")):
        pytest.skip(
            "Live tests are disabled. Set RUN_LIVE_LLM_TESTS=1 to execute real provider tests."
        )


def _missing_required_env_vars() -> list[str]:
    required_names: list[str] = []
    missing: list[str] = []
    for name in required_names:
        if not os.getenv(name, "").strip():
            missing.append(name)
    return missing


def _api_base_url() -> str:
    return os.getenv("LIVE_API_BASE_URL", "http://localhost:8000").rstrip("/")


def _request_json(
    session: requests.Session,
    method: str,
    path: str,
    *,
    json_body: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    query_params: dict[str, str] | None = None
    if params is not None:
        query_params = {key: str(value) for key, value in params.items()}

    request_started_at = time.perf_counter()
    try:
        response = session.request(
            method=method,
            url=f"{_api_base_url()}{path}",
            json=json_body,
            params=query_params,
            timeout=45,
        )
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - request_started_at
        _log(f"REQUEST ERROR {method} {path} after {elapsed:.3f}s: {exc}")
        raise

    elapsed = time.perf_counter() - request_started_at
    _log(f"REQUEST {method} {path} status={response.status_code} in {elapsed:.3f}s")

    if response.status_code != 200:
        _log(f"REQUEST FAILED {method} {path} response={response.text}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def test_simulated_user_live_llm_and_embedding_flow() -> None:
    """Run the full recommendation/practice flow with real provider calls.

    Flow covered:

    1. upsert user
    2. bulk upsert vocabulary
    3. contextual recommendations (with OCR + topic context)
    4. practice generation
    5. provider health contract
    """

    _require_live_execution()

    missing = _missing_required_env_vars()
    if missing:
        pytest.skip(
            "Missing required environment variables for live run: "
            + ", ".join(sorted(missing))
        )

    run_tag = uuid4().hex[:8]
    timings: list[tuple[str, float]] = []
    flow_started_at = time.perf_counter()

    _log(f"Starting live flow run_tag={run_tag}")
    _log(f"API base URL: {_api_base_url()}")

    with requests.Session() as session:
        try:
            # This test expects the running backend process to use live providers.
            with _timed_step(timings, "initial_health_check"):
                initial_health = _request_json(session, "GET", "/health")
                assert "providers" in initial_health
                assert initial_health["providers"]["embedding"]["backend"] == "llm_api"
                assert initial_health["providers"]["intelligence"]["backend"] == "generic_http"
                assert "final_reranker" in initial_health["providers"]
                assert initial_health["providers"]["final_reranker"]["backend"] in {
                    "pretrained_model",
                    "embedding_similarity_fallback",
                }
                _log(
                    "Initial providers: "
                    + f"embedding={initial_health['providers']['embedding']['backend']}, "
                    + f"intelligence={initial_health['providers']['intelligence']['backend']}, "
                    + f"final_reranker={initial_health['providers']['final_reranker']['backend']}"
                )

            upsert_payload = {
                "external_user_id": f"live-user-{run_tag}",
                "email": f"live.{run_tag}@example.local",
                "username": f"live_user_{run_tag}",
                "first_name": "Live",
                "last_name": "Tester",
                "base_language": "en",
                "target_language": "de",
                "current_level": "A2",
                "city": "Berlin",
                "country": "Germany",
                "area_type": "urban",
                "profile_summary": (
                    "Student learning German for daily shopping and transport. "
                    "Needs practical vocabulary from OCR snapshots and signs."
                ),
                "metadata": {
                    "scenario": "live-llm-integration",
                    "run_tag": run_tag,
                },
            }
            with _timed_step(timings, "user_upsert"):
                user_data = _request_json(
                    session,
                    "POST",
                    "/api/v1/users/upsert",
                    json_body=upsert_payload,
                )
                assert user_data["user_id"]

            user_id = user_data["user_id"]
            _log(f"User upserted user_id={user_id}")

            vocab_payload = {
                "items": [
                    {
                        "word_key": f"{run_tag}-kasse",
                        "word": "Kasse",
                        "meaning": "checkout counter",
                        "description": "Counter where customers pay in a store.",
                        "example_sentence": "Bitte gehen Sie zur Kasse.",
                        "category": "shopping",
                        "cefr_level": "A1",
                        "tags": ["store", "payment"],
                        "source_language": "de",
                        "target_language": "en",
                    },
                    {
                        "word_key": f"{run_tag}-bezahlen",
                        "word": "bezahlen",
                        "meaning": "to pay",
                        "description": "Action for paying a bill.",
                        "example_sentence": "Ich mochte mit Karte bezahlen.",
                        "category": "shopping",
                        "cefr_level": "A1",
                        "tags": ["payment", "verb"],
                        "source_language": "de",
                        "target_language": "en",
                    },
                    {
                        "word_key": f"{run_tag}-karte",
                        "word": "Karte",
                        "meaning": "card",
                        "description": "Bank or payment card.",
                        "example_sentence": "Kann ich mit Karte bezahlen?",
                        "category": "shopping",
                        "cefr_level": "A1",
                        "tags": ["payment", "noun"],
                        "source_language": "de",
                        "target_language": "en",
                    },
                    {
                        "word_key": f"{run_tag}-bar",
                        "word": "bar",
                        "meaning": "cash",
                        "description": "Cash payment mode.",
                        "example_sentence": "Nur bar, bitte.",
                        "category": "shopping",
                        "cefr_level": "A1",
                        "tags": ["payment", "cash"],
                        "source_language": "de",
                        "target_language": "en",
                    },
                ]
            }
            with _timed_step(timings, "vocabulary_bulk_upsert"):
                vocab_data = _request_json(
                    session,
                    "POST",
                    "/api/v1/vocabulary/bulk-upsert",
                    json_body=vocab_payload,
                )
                assert vocab_data["upserted"] == len(vocab_payload["items"])
            _log(f"Vocabulary upserted={vocab_data['upserted']}")

            recommendation_payload = {
                "user_id": user_id,
                "action": {
                    "original_text": "Bitte an der Kasse bezahlen.",
                    "translation": "Please pay at the checkout counter.",
                    "source_language": "de",
                    "target_language": "en",
                    "input_mode": "ocr",
                    "ocr_text": "BITTE AN DER KASSE BEZAHLEN",
                    "context": {
                        "location": "supermarket",
                        "environment": "shopping",
                        "sentiment": "neutral",
                        "intent": "understand payment instruction",
                        "topic": "checkout payment",
                    },
                },
            }
            with _timed_step(timings, "contextual_recommendations"):
                recommendation_data = _request_json(
                    session,
                    "POST",
                    "/api/v1/recommendations/contextual",
                    json_body=recommendation_payload,
                )

                assert recommendation_data["predicted_level"]
                assert recommendation_data["model_action"] in {
                    "use_retrieved",
                    "manual_review",
                    "regenerate_with_llm",
                    "fallback_llm",
                }
                assert recommendation_data["reranked_recommendations"]

                for item in recommendation_data["reranked_recommendations"]:
                    assert item["phrase"]
                    assert "scores" in item
                    assert "fusion" in item["scores"]
                    assert "ml" in item["scores"]
            _log(
                "Recommendations generated="
                + f"{len(recommendation_data['reranked_recommendations'])}, "
                + f"model_action={recommendation_data['model_action']}, "
                + f"predicted_level={recommendation_data['predicted_level']}"
            )

            with _timed_step(timings, "practice_generation"):
                practice_data = _request_json(
                    session,
                    "GET",
                    "/api/v1/practice/generate",
                    params={"user_id": user_id, "limit": 4},
                )
                assert practice_data["context_theme"]
                assert practice_data["exercises"]

                for exercise in practice_data["exercises"]:
                    assert exercise["type"] in {
                        "multiple_choice",
                        "fill_in_the_blank",
                        "translation",
                        "open_response",
                    }
                    assert exercise["prompt"]
            _log(
                "Practice generated="
                + f"{len(practice_data['exercises'])}, "
                + f"context_theme={practice_data['context_theme']}"
            )

            with _timed_step(timings, "final_health_check"):
                health_data = _request_json(session, "GET", "/health")
                assert health_data["database"] in {"up", "down"}
                assert "providers" in health_data
                assert health_data["providers"]["embedding"]["backend"] == "llm_api"
                assert health_data["providers"]["intelligence"]["backend"] == "generic_http"
                assert "final_reranker" in health_data["providers"]
                assert health_data["providers"]["final_reranker"]["backend"] in {
                    "pretrained_model",
                    "embedding_similarity_fallback",
                }
                _log(
                    "Final providers: "
                    + f"embedding={health_data['providers']['embedding']['backend']}, "
                    + f"intelligence={health_data['providers']['intelligence']['backend']}, "
                    + f"final_reranker={health_data['providers']['final_reranker']['backend']}"
                )
        finally:
            total_elapsed = time.perf_counter() - flow_started_at
            _print_timing_summary(timings, total_elapsed)
