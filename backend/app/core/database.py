from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Async SQLAlchemy Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


_tables_initialized = False


async def init_db() -> None:
    """Ensure all SQLAlchemy tables are created in PostgreSQL."""
    global _tables_initialized
    import app.models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _tables_initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for acquiring async database sessions."""
    global _tables_initialized
    if not _tables_initialized:
        try:
            await init_db()
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
