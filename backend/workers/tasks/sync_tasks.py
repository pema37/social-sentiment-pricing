# backend/workers/tasks/sync_tasks.py
"""
Sync Tasks — Celery tasks for importing products from connected e-commerce platforms.

These tasks pull products from Shopify/WooCommerce and create
ProductIntegrationLink records for any unlinked products.

PATCHED (2026-03-28): Refactored sync_integration_products into a parallel
chunked pipeline:
  1. Orchestrator enumerates all page cursors (lightweight pass, no product data)
  2. Dispatches one chunk task per 100-product page via a Celery chord
  3. Chord callback (_finalize_sync) marks sync complete when all chunks finish
  Fixes BULK_PRODUCTS_UNLINKED (Bug 303.02) and resolves multi-hour sync times
  on large stores.
"""

from datetime import UTC, datetime
from uuid import UUID

from celery import chord, group
from sqlmodel import select

from core.encryption import decrypt_token
from core.logging import get_logger
from workers.celery_app import celery_app
from workers.tasks.sync_verification_tasks import get_task_session_maker, run_async

logger = get_logger(__name__)


# ==============================================================================
# ORCHESTRATOR TASK
# ==============================================================================


async def _sync_integration_products(integration_id: str, user_id: str) -> dict:
    """
    Orchestrate a parallel chunked sync:
    1. Verify integration is active
    2. Enumerate all page-boundary cursors (lightweight pass)
    3. Dispatch chord of chunk tasks + finalize callback
    """
    from models.integration import EcommercePlatform, Integration, IntegrationStatus
    from services.integration.shopify_service import ShopifyService

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

        integration.sync_status = "syncing"
        integration.sync_cursor = None
        db.add(integration)
        await db.commit()

        try:
            access_token = decrypt_token(integration.access_token_encrypted)

            if integration.platform == EcommercePlatform.SHOPIFY:
                service = ShopifyService()
                cursors = await service.fetch_product_cursors(
                    store_url=integration.store_url,
                    access_token=access_token,
                    page_size=100,
                )
            else:
                # WooCommerce: single chunk (no cursor enumeration needed)
                cursors = [None]

            if not cursors:
                # No products found — mark complete immediately
                integration.sync_status = "idle"
                integration.last_sync_at = datetime.now(UTC)
                db.add(integration)
                await db.commit()
                return {"status": "completed", "chunk_count": 0, "integration_id": integration_id}

            # Dispatch chord: parallel chunks + finalize callback
            chunk_tasks = group(
                sync_integration_products_chunk.si(integration_id, cursor, idx)
                for idx, cursor in enumerate(cursors)
            )
            callback = _finalize_sync.s(integration_id)
            chord(chunk_tasks, callback).apply_async(queue="sync")

            logger.info(
                "sync_integration_products dispatched",
                integration_id=integration_id,
                chunk_count=len(cursors),
            )
            return {
                "status": "dispatched",
                "chunk_count": len(cursors),
                "integration_id": integration_id,
            }

        except Exception as exc:
            logger.error(
                "sync_integration_products orchestration failed",
                integration_id=integration_id,
                error=str(exc),
            )
            integration.sync_status = "error"
            integration.error_message = str(exc)
            db.add(integration)
            await db.commit()
            return {"success": False, "error": str(exc), "integration_id": integration_id}


@celery_app.task(name="workers.tasks.sync_tasks.sync_integration_products", queue="sync")
def sync_integration_products(integration_id: str, user_id: str) -> dict:
    """
    Orchestrate a parallel chunked product sync.

    Enqueued by POST /api/v1/product-sync/sync/bulk.
    Fixes Bug 303.02 — BULK_PRODUCTS_UNLINKED.
    """
    return run_async(_sync_integration_products(integration_id, user_id))


# ==============================================================================
# CHUNK TASK
# ==============================================================================


async def _sync_integration_products_chunk(
    integration_id: str,
    cursor: str | None,
    chunk_index: int,
) -> dict:
    """Process one 100-product page starting at cursor."""
    from models.integration import EcommercePlatform, Integration, IntegrationStatus
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from services.integration.repositories.link_repo import LinkRepository
    from services.integration.repositories.product_repo import ProductRepository
    from services.integration.shopify_service import ShopifyService
    from services.integration.woocommerce_service import WooCommerceService

    session_maker = get_task_session_maker()

    async with session_maker() as db:
        stmt = select(Integration).where(
            Integration.id == UUID(integration_id),
            Integration.status == IntegrationStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if not integration:
            logger.warning(
                "sync_chunk: integration not found",
                integration_id=integration_id,
                chunk_index=chunk_index,
            )
            return {"created": 0, "updated": 0, "chunk_index": chunk_index, "success": False}

        access_token = decrypt_token(integration.access_token_encrypted)

        if integration.platform == EcommercePlatform.SHOPIFY:
            service = ShopifyService()
        else:
            service = WooCommerceService()

        result_page = await service.fetch_products(
            store_url=integration.store_url,
            access_token=access_token,
            cursor=cursor,
            limit=100,
        )

        if not result_page.success:
            logger.error(
                "sync_chunk: fetch failed",
                integration_id=integration_id,
                chunk_index=chunk_index,
                error=result_page.error,
            )
            return {"created": 0, "updated": 0, "chunk_index": chunk_index, "success": False}

        product_repo = ProductRepository(db)
        link_repo = LinkRepository(db)
        handler = ProductSyncHandler(db, product_repo, link_repo)

        created, updated = 0, 0
        for external_product in result_page.products:
            c, u = await handler.upsert_product(integration, external_product)
            created += c
            updated += u

        await db.commit()

        logger.info(
            "sync_chunk complete",
            integration_id=integration_id,
            chunk_index=chunk_index,
            created=created,
            updated=updated,
        )
        return {
            "created": created,
            "updated": updated,
            "chunk_index": chunk_index,
            "success": True,
        }


@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products_chunk",
    queue="sync",
)
def sync_integration_products_chunk(
    integration_id: str,
    cursor: str | None,
    chunk_index: int,
) -> dict:
    """Process one 100-product page. Called by sync_integration_products chord."""
    return run_async(_sync_integration_products_chunk(integration_id, cursor, chunk_index))


# ==============================================================================
# CHORD CALLBACK — FINALIZE
# ==============================================================================


async def _finalize_sync_async(chunk_results: list[dict], integration_id: str) -> dict:
    """Sum all chunk results and mark sync as complete."""
    from models.integration import Integration, IntegrationSyncLog

    total_created = sum(r.get("created", 0) for r in chunk_results if isinstance(r, dict))
    total_updated = sum(r.get("updated", 0) for r in chunk_results if isinstance(r, dict))

    session_maker = get_task_session_maker()
    now = datetime.now(UTC)

    async with session_maker() as db:
        stmt = select(Integration).where(Integration.id == UUID(integration_id))
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if integration:
            integration.sync_status = "idle"
            integration.last_sync_at = now
            integration.error_message = None
            db.add(integration)

            sync_log = IntegrationSyncLog(
                integration_id=UUID(integration_id),
                sync_type="full",
                started_at=now,
                completed_at=now,
                success=True,
                products_created=total_created,
                products_updated=total_updated,
                products_deleted=0,
            )
            db.add(sync_log)
            await db.commit()

    logger.info(
        "sync finalized",
        integration_id=integration_id,
        total_created=total_created,
        total_updated=total_updated,
        chunks=len(chunk_results),
    )
    return {
        "success": True,
        "integration_id": integration_id,
        "created": total_created,
        "updated": total_updated,
        "chunks": len(chunk_results),
    }


@celery_app.task(
    name="workers.tasks.sync_tasks._finalize_sync",
    queue="sync",
)
def _finalize_sync(chunk_results: list[dict], integration_id: str) -> dict:
    """Chord callback: aggregate chunk results and mark sync complete."""
    return run_async(_finalize_sync_async(chunk_results, integration_id))
