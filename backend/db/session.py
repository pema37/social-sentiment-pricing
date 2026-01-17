# backend/db/session.py

import asyncio
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SyncSession
from sqlmodel import SQLModel
from core.config import settings

# =============================================================================
# ASYNC DATABASE ENGINE (for FastAPI routes)
# =============================================================================

DATABASE_URL = settings.DATABASE_URL

# Create async URL
ASYNC_DATABASE_URL = DATABASE_URL
if ASYNC_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif ASYNC_DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# asyncpg uses 'ssl' instead of 'sslmode', and doesn't support 'channel_binding'
ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("sslmode=", "ssl=")
ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("&channel_binding=require", "")
ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("?channel_binding=require&", "?")

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# SYNC DATABASE ENGINE (for Celery tasks)
# =============================================================================

# Create sync URL (keep postgresql://, remove asyncpg if present)
SYNC_DATABASE_URL = DATABASE_URL
if "+asyncpg" in SYNC_DATABASE_URL:
    SYNC_DATABASE_URL = SYNC_DATABASE_URL.replace("+asyncpg", "")
# Ensure it starts with postgresql:// (not postgres://)
if SYNC_DATABASE_URL.startswith("postgres://"):
    SYNC_DATABASE_URL = SYNC_DATABASE_URL.replace("postgres://", "postgresql://", 1)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=SyncSession,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# SESSION PROVIDERS
# =============================================================================

async def get_session():
    """FastAPI dependency that provides an async database session."""
    async with async_session() as session:
        yield session


# Alias for backward compatibility - some files import get_db
get_db = get_session


@asynccontextmanager
async def get_session_context():
    """Async context manager for use outside FastAPI (e.g., async Celery tasks)."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_sync_session():
    """
    Synchronous session context manager for Celery tasks.
    
    Usage:
        with get_sync_session() as session:
            # do database operations
            session.commit()
    """
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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



        