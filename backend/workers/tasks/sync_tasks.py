"""
FILE: backend/workers/tasks/sync_tasks.py
FULL REPLACE

Changes vs previous version (cursor-based pagination fix 2026-03-28):

  [CRITICAL FIX] Orchestrator now uses fetch_product_cursors() + cursor-based
  chunk dispatch instead of offset/limit arithmetic.

  Root cause of previous bug: Shopify GraphQL has NO offset pagination.
  The previous code called sync_products_page(offset=100, limit=100) which
  would have failed at runtime — GraphQL cursors cannot be computed from
  an integer offset. fetch_product_cursors() already existed in
  shopify_products.py and is purpose-built for this exact use case.

  [REMOVED] _get_platform_product_count() — replaced by fetch_product_cursors()
  which is a single GraphQL pass that returns both the count (len(cursors)) and
  the cursor values needed for dispatch, without a separate round-trip.

  [REMOVED] sync_products_page(offset, limit) requirement from ProductSyncHandler.
  Now calls fetch_products(cursor=cursor, limit=CHUNK_SIZE) directly via
  ShopifyService, then passes raw ExternalProduct list to the handler.

  [KEPT] All PDF best practices: retry_backoff, retry_jitter, chord link_error,
  dead-letter error callback, SoftTimeLimitExceeded handling.

  [KEPT] Single-pass fallback for small stores.
  [KEPT] Bug 303.01 + 303.02 fixes.

  FIX (2026-03-29): sync_status set to "idle"/"error" on completion instead of
  "completed"/"failed" so the UI polling (which checks sync_status == "syncing")
  correctly stops spinning. "completed"/"failed" are not recognized by the
  frontend's polling logic.

WooCommerce note: WooCommerce REST API DOES support offset pagination
(?offset=N&per_page=100). The cursor path is Shopify-only. WooCommerce
stores still use single-pass (sync_all_products) until a WooCommerce
parallel-chunk path is implemented separately.
"""

from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded
from sqlmodel import select
from uuid import UUID

from core.logging import get_logger
from workers.celery_app import celery_app
from workers.tasks.ingestion_tasks import get_task_session_maker, run_async

logger = get_logger(__name__)

CHUNK_SIZE = 100   # products per parallel chunk
MAX_RETRIES = 3


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products",
    bind=True,
    max_retries=MAX_RETRIES,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    soft_time_limit=270,
    time_limit=300,
)
def sync_integration_products(self, integration_id: str, user_id: str) -> dict:
    """
    Orchestrate a full product sync for one integration.

    Shopify (GraphQL, cursor-based):
      Small stores (≤ 1 page): single-pass via sync_all_products.
      Large stores: fetch_product_cursors() → parallel chord of chunk tasks.

    WooCommerce (REST, offset-based):
      Always single-pass via sync_all_products.
      Parallel chunking for WooCommerce is a separate future task.
    """
    return run_async(_orchestrate_sync(self, integration_id, user_id))


async def _orchestrate_sync(task_self, integration_id: str, user_id: str) -> dict:
    from models.integration import Integration, IntegrationStatus

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
                "sync_integration_products: no active integration",
                integration_id=integration_id,
                user_id=user_id,
            )
            # Reset sync_status so UI doesn't stay stuck
            stmt2 = select(Integration).where(Integration.id == UUID(integration_id))
            result2 = await db.execute(stmt2)
            integration2 = result2.scalars().first()
            if integration2 and integration2.sync_status == "syncing":
                integration2.sync_status = "error"
                integration2.error_message = "Integration not found or not active"
                await db.commit()
            return {
                "success": False,
                "error": "Integration not found or not active",
                "integration_id": integration_id,
            }

        platform = getattr(integration, "platform", "").lower()

        # WooCommerce: REST API supports offset but not cursor pagination.
        # Run single-pass until a WooCommerce parallel path is built.
        if platform != "shopify":
            return await _sync_single_pass(db, integration, integration_id, user_id)

        # Shopify: use cursor enumeration for parallel dispatch.
        store_url    = integration.store_url
        access_token = integration.access_token

    # ----------------------------------------------------------------
    # Fetch page-boundary cursors — one lightweight GraphQL pass.
    # ----------------------------------------------------------------
    from services.integration.shopify_service import ShopifyService

    shopify = ShopifyService()
    cursors = await shopify.fetch_product_cursors(
        store_url=store_url,
        access_token=access_token,
        page_size=CHUNK_SIZE,
    )

    logger.info(
        "sync orchestrator: cursor enumeration complete",
        integration_id=integration_id,
        chunks=len(cursors),
        chunk_size=CHUNK_SIZE,
    )

    # Small store — single page, no parallel overhead needed
    if len(cursors) <= 1:
        session_maker = get_task_session_maker()
        async with session_maker() as db:
            stmt = select(Integration).where(Integration.id == UUID(integration_id))
            result = await db.execute(stmt)
            integration = result.scalars().first()
            return await _sync_single_pass(db, integration, integration_id, user_id)

    # Large store — dispatch parallel chunks (sync_status already "syncing")
    chunk_tasks = group(
        sync_integration_products_chunk.si(
            integration_id=integration_id,
            user_id=user_id,
            cursor=cursor,
            limit=CHUNK_SIZE,
        )
        for cursor in cursors
    )

    callback = sync_integration_products_complete.si(
        integration_id=integration_id,
        user_id=user_id,
        total_chunks=len(cursors),
    )
    error_callback = sync_integration_products_error.s(
        integration_id=integration_id,
        user_id=user_id,
    )

    workflow = chord(chunk_tasks)(callback)
    workflow.link_error(error_callback)

    return {
        "success": True,
        "mode": "parallel",
        "integration_id": integration_id,
        "chunks_dispatched": len(cursors),
    }


# ==============================================================================
# CHUNK WORKER
# ==============================================================================

@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products_chunk",
    bind=True,
    max_retries=MAX_RETRIES,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=240,
    time_limit=270,
)
def sync_integration_products_chunk(
    self,
    integration_id: str,
    user_id: str,
    cursor: str | None,
    limit: int,
) -> dict:
    """Fetch and upsert one page of products starting at `cursor`."""
    return run_async(_sync_chunk(self, integration_id, user_id, cursor, limit))


async def _sync_chunk(
    task_self,
    integration_id: str,
    user_id: str,
    cursor: str | None,
    limit: int,
) -> dict:
    from models.integration import Integration, IntegrationStatus
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from services.integration.repositories.link_repo import LinkRepository
    from services.integration.repositories.product_repo import ProductRepository
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
                "sync_chunk: integration not found",
                integration_id=integration_id,
                cursor=cursor,
            )
            return {
                "success": False,
                "cursor": cursor,
                "error": "Integration not found",
            }

        try:
            shopify = ShopifyService()
            sync_result = await shopify.fetch_products(
                store_url=integration.store_url,
                access_token=integration.access_token,
                cursor=cursor,
                limit=limit,
            )

            if not sync_result.success:
                raise RuntimeError(f"fetch_products failed: {sync_result.error}")

            product_repo = ProductRepository(db)
            link_repo    = LinkRepository(db)
            handler      = ProductSyncHandler(db, product_repo, link_repo)

            created, updated, deleted = await handler.upsert_products(
                integration=integration,
                external_products=sync_result.products,
            )

        except SoftTimeLimitExceeded:
            logger.warning(
                "sync_chunk soft timeout, retrying",
                integration_id=integration_id,
                cursor=cursor,
            )
            raise task_self.retry(countdown=30)
        except Exception as exc:
            logger.error(
                "sync_chunk failed",
                integration_id=integration_id,
                cursor=cursor,
                error=str(exc),
            )
            raise task_self.retry(exc=exc)

        result_dict = {
            "success": True,
            "integration_id": integration_id,
            "cursor": cursor,
            "created": created,
            "updated": updated,
            "deleted": deleted,
        }
        logger.info("sync_chunk complete", **result_dict)
        return result_dict


# ==============================================================================
# CHORD SUCCESS CALLBACK
# ==============================================================================

@celery_app.task(name="workers.tasks.sync_tasks.sync_integration_products_complete")
def sync_integration_products_complete(
    chunk_results: list,
    integration_id: str,
    user_id: str,
    total_chunks: int,
) -> dict:
    """Aggregates chunk results and marks integration completed."""
    return run_async(
        _mark_sync_complete(chunk_results, integration_id, user_id, total_chunks)
    )


async def _mark_sync_complete(
    chunk_results: list,
    integration_id: str,
    user_id: str,
    total_chunks: int,
) -> dict:
    from datetime import UTC, datetime
    from models.integration import Integration

    safe_results   = chunk_results or []
    total_created  = sum(r.get("created", 0) for r in safe_results if r and r.get("success"))
    total_updated  = sum(r.get("updated", 0) for r in safe_results if r and r.get("success"))
    total_deleted  = sum(r.get("deleted", 0) for r in safe_results if r and r.get("success"))
    sentinel_fails = [r for r in safe_results if not r or not r.get("success")]

    session_maker = get_task_session_maker()
    async with session_maker() as db:
        stmt = select(Integration).where(Integration.id == UUID(integration_id))
        result = await db.execute(stmt)
        integration = result.scalars().first()
        if integration:
            # FIX: "idle"/"error" — recognized by UI polling and SyncService
            integration.sync_status = "error" if sentinel_fails else "idle"
            integration.products_synced = total_created + total_updated
            if not sentinel_fails:
                integration.last_sync_at = datetime.now(UTC)
                integration.error_message = None
            await db.commit()

    summary = {
        "success": not sentinel_fails,
        "integration_id": integration_id,
        "chunks_total": total_chunks,
        "chunks_failed": len(sentinel_fails),
        "total_created": total_created,
        "total_updated": total_updated,
        "total_deleted": total_deleted,
    }
    logger.info("sync complete (all chunks)", **summary)
    return summary


# ==============================================================================
# CHORD ERROR CALLBACK
# ==============================================================================

@celery_app.task(name="workers.tasks.sync_tasks.sync_integration_products_error")
def sync_integration_products_error(
    request,
    exc,
    traceback,
    integration_id: str,
    user_id: str,
) -> None:
    """
    Fires when any chunk exhausts retries and raises (not sentinel returns).
    Marks integration as error. PDF §Chords link_error pattern.
    """
    return run_async(_handle_sync_error(request, exc, traceback, integration_id, user_id))


async def _handle_sync_error(
    request, exc, traceback, integration_id: str, user_id: str,
) -> None:
    import json
    from datetime import UTC, datetime
    from models.integration import Integration

    logger.error(
        "sync chord failed — marking integration as error",
        integration_id=integration_id,
        exc=str(exc),
    )

    session_maker = get_task_session_maker()
    async with session_maker() as db:
        stmt = select(Integration).where(Integration.id == UUID(integration_id))
        result = await db.execute(stmt)
        integration = result.scalars().first()
        if integration:
            # FIX: "error" — recognized by UI and SyncService.recover_stuck_syncs
            integration.sync_status = "error"
            integration.error_message = str(exc)
            try:
                integration.last_error = json.dumps({
                    "failed_at":      datetime.now(UTC).isoformat(),
                    "exc_type":       type(exc).__name__,
                    "exc_message":    str(exc),
                    "celery_task_id": getattr(request, "id", None),
                })
            except Exception:
                pass  # last_error column may not exist yet
            await db.commit()
            logger.info("sync dead-letter recorded", integration_id=integration_id)


# ==============================================================================
# HELPERS
# ==============================================================================

async def _sync_single_pass(db, integration, integration_id: str, user_id: str) -> dict:
    """
    Original single-pass sync for small stores or non-Shopify platforms.
    Sets sync_status = "idle" on success, "error" on failure.
    """
    from datetime import UTC, datetime
    from models.integration import Integration
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from services.integration.repositories.link_repo import LinkRepository
    from services.integration.repositories.product_repo import ProductRepository

    try:
        product_repo = ProductRepository(db)
        link_repo    = LinkRepository(db)
        handler      = ProductSyncHandler(db, product_repo, link_repo)

        created, updated, deleted = await handler.sync_all_products(
            integration, sync_type="full"
        )

        integration.sync_status = "idle"
        integration.last_sync_at = datetime.now(UTC)
        integration.products_synced = created + updated
        integration.error_message = None
        await db.commit()

        result_dict = {
            "success":        True,
            "mode":           "single_pass",
            "integration_id": integration_id,
            "created":        created,
            "updated":        updated,
            "deleted":        deleted,
        }
        logger.info("sync_integration_products (single-pass) complete", **result_dict)
        return result_dict

    except Exception as exc:
        logger.error(
            "sync_integration_products (single-pass) failed",
            integration_id=integration_id,
            error=str(exc),
        )
        try:
            stmt = select(Integration).where(Integration.id == UUID(integration_id))
            result = await db.execute(stmt)
            integration_row = result.scalars().first()
            if integration_row:
                integration_row.sync_status = "error"
                integration_row.error_message = str(exc)
                await db.commit()
        except Exception:
            pass
        raise



    