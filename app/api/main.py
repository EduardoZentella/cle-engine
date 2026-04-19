"""FastAPI application entrypoint for CLE Engine backend.

Responsibilities:

- assemble runtime dependencies during startup
- register API routes
- expose service health information
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import Settings
from app.api.db import DatabasePool
from app.api.embeddings import build_embedding_provider
from app.api.intelligence import build_intelligence_provider
from app.api.recommendation_repository import RecommendationRepository
from app.api.recommendation_routes import router as recommendation_router
from app.api.recommendation_service import RecommendationService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and dispose shared backend dependencies.

    Startup actions:

    1. Load runtime settings.
    2. Open DB connection pool.
    3. Build embedding provider.
    4. Create recommendation service and store in app state.

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

    embedding_provider = build_embedding_provider(settings)
    intelligence_provider = build_intelligence_provider(settings)
    repository = RecommendationRepository(database=database, settings=settings)
    app.state.recommendation_service = RecommendationService(
        repository=repository,
        embedding_provider=embedding_provider,
        intelligence_provider=intelligence_provider,
        settings=settings,
    )

    try:
        yield
    finally:
        await app.state.recommendation_service.aclose()
        database.close()

app = FastAPI(
    title="CLE Engine API",
    description="A location-triggered language learning prototype",
    version="0.1.0",
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
    return {"message": "Welcome to CLE Engine API"}


@app.get("/health")
async def health():
    """Return API and database readiness status."""
    service = app.state.recommendation_service
    db_ok = await service.ping()
    provider_health = service.provider_health()
    providers_degraded = any(
        bool(snapshot.get("degraded")) for snapshot in provider_health.values()
    )
    if db_ok and not providers_degraded:
        return {"status": "healthy", "database": "up", "providers": provider_health}
    return {
        "status": "degraded",
        "database": "up" if db_ok else "down",
        "providers": provider_health,
    }
