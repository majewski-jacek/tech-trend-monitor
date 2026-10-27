from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base, Article, User, TrendSnapshot, SyncMetadata, RevokedToken
from app.services.aggregator import SEED_TECH_STORIES, TechDataAggregator
from app.worker.scheduler import background_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


def init_db_and_seed():
    """Initializes schema via Alembic migrations, ensures all tables exist, and seeds default data."""
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        if os.path.exists(alembic_ini_path):
            alembic_cfg = Config(alembic_ini_path)
            command.upgrade(alembic_cfg, "head")
    except Exception as e:
        logger.warning(f"Alembic auto-upgrade skipped or failed ({e}). Falling back to Base.metadata.create_all().")

    # Ensure all registered tables exist (idempotent, checkfirst=True)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed default demo admin account if no users exist
        if db.query(User).count() == 0:
            logger.info("Seeding default demo admin account (admin / admin123)...")
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                is_active=True
            )
            db.add(admin_user)
            db.commit()

        # Seed initial articles if feed is currently empty
        if db.query(Article).count() == 0:
            logger.info("Feed is empty. Ingesting initial curated tech dataset...")
            TechDataAggregator.process_and_save_stories(db, SEED_TECH_STORIES)
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler managing database initialization and background worker."""
    if not os.getenv("TESTING"):
        logger.info("Initializing TechTrend Monitor application...")
        init_db_and_seed()
        # Start periodic background ingestion worker
        background_worker.start()
    yield
    if not os.getenv("TESTING"):
        # Graceful shutdown
        logger.info("Shutting down background workers...")
        await background_worker.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Real-time Tech Trends & Sentiment Analysis Monitor with WebSockets and FastAPI.",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serves the single-page application dashboard."""
    index_file = os.path.join(static_dir, "index.html")
    return FileResponse(index_file)


@app.get("/health", tags=["Health"])
def health_check():
    """Healthcheck endpoint for container orchestration and uptime monitors."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
