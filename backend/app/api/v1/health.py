from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.vector_service import vector_service

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def liveness():
    """Basic liveness check."""
    return {"status": "ok", "service": "personal-vault-backend"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe checking PostgreSQL & pgvector extension availability."""
    checks = {}

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "connected"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {str(e)}"

    # Check pgvector extension
    try:
        is_pgvector_ready = await vector_service.ping(db)
        checks["pgvector"] = "connected" if is_pgvector_ready else "unhealthy"
    except Exception as e:
        checks["pgvector"] = f"unhealthy: {str(e)}"

    is_ready = all(v == "connected" for v in checks.values())
    return {
        "status": "ready" if is_ready else "degraded",
        "checks": checks,
    }
