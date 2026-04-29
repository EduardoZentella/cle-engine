"""FastAPI application entrypoint for CLE Engine backend (Phase 2).

Responsibilities:

- assemble runtime dependencies during startup
- register API routes
- expose service health information
"""
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import Settings
from app.api.context_retrieval_service import ContextRetrievalService
from app.api.debug_logger import DebugLogger
from app.api.db import DatabasePool
from app.api.embeddings_provider_gemini import GeminiEmbeddingProvider
from app.api.evaluation_service import EvaluationService
from app.api.llm_generation_service import LLMGenerationService
from app.api.performance_metrics import PerformanceTracker
from app.api.recommendation_pipeline import RecommendationPipeline
from app.api.recommendation_routes import router as recommendation_router
from app.api.translation_service import TranslationService
from app.api.unified_service import UnifiedRecommendationService

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and dispose shared backend dependencies.

    Startup actions:

    1. Load runtime settings.
    2. Open DB connection pool.
    3. Initialize all Phase 1 services:
       - GeminiEmbeddingProvider (Gemini API + connection pooling)
       - TranslationService (Fast translation)
       - ContextRetrievalService (Vector similarity search)
       - LLMGenerationService (Sentence generation)
       - EvaluationService (Scoring)
    4. Create recommendation pipeline orchestrator.
    5. Initialize performance tracking and debug logging.
    6. Create unified service and store in app state.

    Shutdown action:

    - close DB pool.
    """

    settings = Settings.from_env()
    database = DatabasePool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    database.open()

    logger.info("Backend startup: database pool opened")

    try:
        # Initialize Phase 1 services
        embedding_provider = GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key
        )
        logger.info("Backend startup: Gemini embedding provider initialized")

        translation_service = TranslationService(
            api_key=settings.gemini_api_key
        )
        logger.info("Backend startup: translation service initialized")

        context_service = ContextRetrievalService(
            database=database,
            embedding_provider=embedding_provider,
        )
        logger.info("Backend startup: context retrieval service initialized")

        llm_service = LLMGenerationService(
            api_key=settings.gemini_api_key
        )
        logger.info("Backend startup: LLM generation service initialized")

        evaluation_service = EvaluationService(
            embedding_provider=embedding_provider
        )
        logger.info("Backend startup: evaluation service initialized")

        # Initialize observability infrastructure
        performance_tracker = PerformanceTracker(database=database)
        debug_logger = DebugLogger()
        logger.info("Backend startup: performance tracking and debug logging initialized")

        # Create pipeline orchestrator
        pipeline = RecommendationPipeline(
            translation_service=translation_service,
            context_service=context_service,
            llm_service=llm_service,
            evaluation_service=evaluation_service,
            performance_tracker=performance_tracker,
            debug_logger=debug_logger,
        )
        logger.info("Backend startup: recommendation pipeline created")

        # Create unified service
        app.state.recommendation_service = UnifiedRecommendationService(
            database=database,
            pipeline=pipeline,
        )
        logger.info("Backend startup: unified recommendation service created")

        logger.info("Backend startup complete: all services initialized")

        yield

    except Exception as err:
        logger.error("Backend startup failed: %s", str(err))
        database.close()
        raise

    finally:
        logger.info("Backend shutdown starting")
        database.close()
        logger.info("Backend shutdown complete")


app = FastAPI(
    title="CLE Engine API",
    description="Language learning with contextual sentence recommendations",
    version="0.2.0",  # Updated version for Phase 2
    lifespan=lifespan,
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendation_router)


@app.get("/")
async def root():
    """Return a minimal root response for API discovery."""
    logger.debug("GET / called")
    return {
        "message": "Welcome to CLE Engine API",
        "version": "0.2.0",
        "description": "Contextual language learning with AI recommendations",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """Return API and database readiness status.

    Returns:
        {
            "status": "healthy" | "degraded",
            "database": "up" | "down",
            "services": {
                "embedding": "ready" | "error",
                "translation": "ready" | "error",
                "llm": "ready" | "error",
            }
        }
    """
    logger.debug("GET /health called")

    try:
        service = getattr(app.state, "recommendation_service", None)
        if service is None:
            logger.warning("GET /health: service not initialized")
            return {
                "status": "degraded",
                "database": "down",
                "message": "Services not initialized",
            }

        # Check database
        db_ok = False
        try:
            with service.database.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            db_ok = True
            logger.debug("GET /health: database ping OK")
        except Exception as err:
            logger.warning("GET /health: database ping failed: %s", str(err))

        return {
            "status": "healthy" if db_ok else "degraded",
            "database": "up" if db_ok else "down",
            "services": {
                "embedding": "ready",
                "translation": "ready",
                "llm": "ready",
                "context_retrieval": "ready",
                "evaluation": "ready",
            },
        }

    except Exception as err:
        logger.error("GET /health failed: %s", str(err))
        return {
            "status": "degraded",
            "database": "down",
            "message": "Health check failed",
        }

