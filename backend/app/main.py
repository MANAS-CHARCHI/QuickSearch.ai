from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.files import router as files_router
from app.core.config import settings
from app.core.database import init_db

logger = logging.getLogger("vaultcity.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: auto-creates PostgreSQL schema tables on startup."""
    try:
        logger.info("Initializing database schema...")
        await init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning("Database schema init warning: %s", e)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route aggregation
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(files_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "docs": "/docs",
    }
