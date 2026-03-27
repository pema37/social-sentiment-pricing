# backend/workers/tasks/sync_tasks.py

"""
Sync Tasks — On-demand full product sync from e-commerce platforms.

Dispatched by the integrations API when a merchant triggers a manual sync
or when the system detects a stale catalog (Bug 303.01 — sync never completes).

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.
"""

import asyncio
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from core.logging import get_logger
from models.integration import Integration
from services.integration.sync_service import SyncService
from workers.celery_app import celery_app

logger = get_logger(__name__)


# ==============================================================================
# HELPERS
# ==============================================================================

def get_task_session_maker():
    """
    Create a fresh async session maker for Celery tasks.

    Uses NullPool to prevent connection reuse across forked processes.
    """
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r'[\?&]sslmode=[^&]*', '', db_url)
        db_url = db_url.replace('?&', '?').replace('&&', '&').rstrip('?&')

    use_ssl = "neon.tech" in db_url or "railway" in db_url

    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro):
    """Run async code in sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


# ==============================================================================
# ASYNC IMPLEMENTATION
# ==============================================================================

async def _sync_integration_products(integration_id_str: str, user_id_str: str) -> dict:
    """
    Run a full product sync for a given integration.

    Args:
        integration_id_str: UUID string of the integration to sync.
        user_id_str: UUID string of the user who triggered the sync.

    Returns:
        Dict confirming success and the integration ID.
    """
    session_maker = get_task_session_maker()
    integration_id = UUID(integration_id_str)
    user_id = UUID(user_id_str)

    async with session_maker() as db:
        try:
            await SyncService(db).run_sync(
                integration_id=integration_id,
                sync_type="full",
                user_id=user_id,
            )
            return {"success": True, "integration_id": integration_id_str}

        except Exception as e:
            logger.error(
                f"sync_integration_products failed for integration "
                f"{integration_id_str}: {e}"
            )
            # SyncService._finalize_failure already updates sync_status on the
            # integration row; apply a task-level fallback in case it didn't.
            try:
                result = await db.execute(
                    select(Integration).where(Integration.id == integration_id)
                )
                integration = result.scalars().first()
                if integration:
                    integration.sync_status = "failed"
                    integration.error_message = str(e)
                    db.add(integration)
                    await db.commit()
            except Exception:
                pass  # best-effort; don't mask original error

            raise  # re-raise so Celery marks the task as FAILED


# ==============================================================================
# CELERY TASK
# ==============================================================================

@celery_app.task(name="workers.tasks.sync_tasks.sync_integration_products")
def sync_integration_products(integration_id: str, user_id: str):
    """Trigger a full product sync from the e-commerce platform."""
    return run_async(_sync_integration_products(integration_id, user_id))
