# backend/db/session.py

import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel
from core.config import settings

# =============================================================================
# ASYNC DATABASE ENGINE
# =============================================================================

DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# asyncpg uses 'ssl' instead of 'sslmode', and doesn't support 'channel_binding'
DATABASE_URL = DATABASE_URL.replace("sslmode=", "ssl=")
DATABASE_URL = DATABASE_URL.replace("&channel_binding=require", "")
DATABASE_URL = DATABASE_URL.replace("?channel_binding=require&", "?")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# SESSION PROVIDERS
# =============================================================================

async def get_session():
    """FastAPI dependency that provides an async database session."""
    async with async_session() as session:
        yield session


@asynccontextmanager
async def get_session_context():
    """Async context manager for use outside FastAPI (e.g., Celery tasks)."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# CELERY ASYNC HELPER
# =============================================================================

def run_async(coro):
    """
    Run an async coroutine in a sync context (for Celery workers).
    Creates a new event loop for each call.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def init_db():
    """Initialize database tables (for development)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


