# backend/workers/tasks/sync_tasks.py
"""
Sync Tasks — Celery tasks for importing products from connected e-commerce platforms.

These tasks pull products from Shopify/WooCommerce and create
ProductIntegrationLink records for any unlinked products.

Fixes the BULK_PRODUCTS_UNLINKED diagnostic issue (Bug 303.02).
"""

from uuid import UUID

from sqlmodel import select

from workers.celery_app import celery_app
from core.logging import get_logger
from workers.tasks.sync_verification_tasks import get_task_session_maker, run_async

logger = get_logger(__name__)


# ==============================================================================
# ASYNC IMPLEMENTATION
# ==============================================================================

async def _sync_integration_products(integration_id: str, user_id: str) -> dict:
    """
    Pull all products from the connected platform and create
    ProductIntegrationLink records for any that are not yet linked.
    """
    from models.integration import Integration, IntegrationStatus
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from services.integration.repositories.product_repo import ProductRepository
    from services.integration.repositories.link_repo import LinkRepository

    session_maker = get_task_session_maker()

    async with session_maker() as db:
        stmt = select(Integration).where(
            Integration.id == UUID(integration_id),
            Integration.user_id == UUID(user_id),
            Integration.status == IntegrationStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if not integration:
            logger.warning(
                "sync_integration_products: no active integration found",
                integration_id=integration_id,
                user_id=user_id,
            )
            return {
                "success": False,
                "error": "Integration not found or not active",
                "integration_id": integration_id,
            }

        product_repo = ProductRepository(db)
        link_repo = LinkRepository(db)
        handler = ProductSyncHandler(db, product_repo, link_repo)
        created, updated, deleted = await handler.sync_all_products(integration, sync_type="full")

        result_dict = {
            "success": True,
            "integration_id": integration_id,
            "created": created,
            "updated": updated,
            "deleted": deleted,
        }
        logger.info(
            "sync_integration_products complete",
            integration_id=integration_id,
            result=result_dict,
        )
        return result_dict


# ==============================================================================
# CELERY TASK
# ==============================================================================

@celery_app.task(name="workers.tasks.sync_tasks.sync_integration_products")
def sync_integration_products(integration_id: str, user_id: str) -> dict:
    """
    Pull all products from a connected e-commerce platform and link any
    that are not yet tracked in ActualPrice.

    Enqueued by POST /api/v1/product-sync/sync/bulk.
    Fixes Bug 303.02 — BULK_PRODUCTS_UNLINKED.
    """
    return run_async(_sync_integration_products(integration_id, user_id))
