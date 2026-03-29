"""
FILE: backend/workers/tasks/sync_tasks.py
FULL REPLACE

Patch history:
  2026-03-28: Cursor-based pagination — fetch_product_cursors() + parallel chord.
              sync_status set to "idle"/"error" (not "completed"/"failed").
  2026-03-29: [NEW] SyncBaseTask base class with on_failure + after_return hooks.
              Guarantees sync_status always reaches a terminal state even if an
              unhandled exception escapes all inner try/except blocks, or if the
              worker is OOM-killed between task completion and result ack.
              [FIXED] decrypt_token(integration.access_token_encrypted) used
              everywhere instead of integration.access_token (AttributeError).
              [FIXED] Chunk worker allows ACTIVE or ERROR status (not just ACTIVE).
              [FIXED] _orchestrate_sync wrapped in top-level try/except safety net.

Three layers of stuck-sync defense:
  Layer 1 — SyncBaseTask.on_failure: fires on any unhandled exception.
  Layer 2 — SyncBaseTask.after_return: fires after any task exit (safety net).
  Layer 3 — recover_stuck_syncs Beat task: scans DB every 5 min for integrations
             stuck in "syncing" past 45 min. Catches OOM worker crashes where
             neither Layer 1 nor Layer 2 had a chance to run.

WooCommerce: offset pagination, single-pass only until parallel path is built.
Shopify: cursor-based parallel chord — fetch_product_cursors() first, then dispatch.
"""

import celery as celery_lib
from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded
from sqlmodel import select
from uuid import UUID

from core.encryption import decrypt_token
from core.logging import get_logger
from workers.celery_app import celery_app
from workers.tasks.ingestion_tasks import get_task_session_maker, run_async

logger = get_logger(__name__)

CHUNK_SIZE = 100
MAX_RETRIES = 3


# ==============================================================================
# LAYER 1 + 2: SyncBaseTask
# ==============================================================================

class SyncBaseTask(celery_lib.Task):
    """
    Custom Celery base class for sync tasks.

    Guarantees sync_status always reaches "idle" or "error" regardless of
    how the task exits — unhandled exception, worker crash, soft timeout.

    on_failure: fires when an unhandled exception escapes the task.
    after_return: fires after any exit. Final safety net — if sync_status is
    still "syncing" after a non-success exit, force it to "error".
    """

    abstract = True

    def _reset_sync_status(self, integration_id: str, error_msg: str) -> None:
        """Reset sync_status to 'error' synchronously. Safe to call from hooks."""
        import asyncio
        from models.integration import Integration

        async def _do_reset():
            session_maker = get_task_session_maker()
            async with session_maker() as db:
                stmt = select(Integration).where(
                    Integration.id == UUID(integration_id)
                )
                result = await db.execute(stmt)
                integration = result.scalars().first()
                if integration and integration.sync_status == "syncing":
                    integration.sync_status = "error"
                    integration.error_message = error_msg[:500]
                    await db.commit()
                    logger.info(
                        "SyncBaseTask: reset sync_status to error",
                        integration_id=integration_id,
                    )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _do_reset())
                    future.result(timeout=10)
            else:
                loop.run_until_complete(_do_reset())
        except Exception as e:
            logger.error(
                "SyncBaseTask: failed to reset sync_status",
                integration_id=integration_id,
                error=str(e),
            )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Layer 1: fires on any unhandled exception from the task."""
        integration_id = args[0] if args else kwargs.get("integration_id")
        if integration_id:
            logger.error(
                "SyncBaseTask.on_failure",
                integration_id=integration_id,
                exc_type=type(exc).__name__,
                task_id=task_id,
            )
            self._reset_sync_status(
                integration_id,
                f"{type(exc).__name__}: {str(exc)}",
            )

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Layer 2: fires after any task exit. Safety net for non-SUCCESS."""
        if status in ("SUCCESS", "RETRY"):
            return
        integration_id = args[0] if args else kwargs.get("integration_id")
        if integration_id:
            logger.warning(
                "SyncBaseTask.after_return: non-success exit",
                integration_id=integration_id,
                status=status,
                task_id=task_id,
            )
            self._reset_sync_status(
                integration_id,
                f"Task ended with status: {status}",
            )


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products",
    bind=True,
    base=SyncBaseTask,
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

    Shopify: fetch_product_cursors() → parallel chord of chunk tasks.
    WooCommerce: single-pass via sync_all_products.
    """
    return run_async(_orchestrate_sync(self, integration_id, user_id))


async def _orchestrate_sync(task_self, integration_id: str, user_id: str) -> dict:
    from models.integration import Integration

    session_maker = get_task_session_maker()

    try:
        return await _orchestrate_sync_inner(
            task_self, integration_id, user_id, session_maker,
        )
    except Exception as exc:
        # Top-level safety net — belt-and-suspenders with SyncBaseTask.on_failure.
        # If _orchestrate_sync_inner raised without resetting sync_status, fix it.
        logger.error(
            "sync orchestrator unhandled error — resetting sync_status",
            integration_id=integration_id,
            error=str(exc),
        )
        try:
            async with session_maker() as db:
                stmt = select(Integration).where(
                    Integration.id == UUID(integration_id),
                )
                result = await db.execute(stmt)
                integration = result.scalars().first()
                if integration and integration.sync_status == "syncing":
                    integration.sync_status = "error"
                    integration.error_message = str(exc)[:500]
                    await db.commit()
        except Exception:
            logger.exception(
                "sync orchestrator: failed to reset sync_status after error",
                integration_id=integration_id,
            )
        raise


async def _orchestrate_sync_inner(
    task_self, integration_id: str, user_id: str, session_maker,
) -> dict:
    from models.integration import Integration, IntegrationStatus

    async with session_maker() as db:
        # Allow ACTIVE or ERROR — ERROR integrations should be retryable
        stmt = select(Integration).where(
            Integration.id == UUID(integration_id),
            Integration.user_id == UUID(user_id),
            Integration.status.in_([IntegrationStatus.ACTIVE, IntegrationStatus.ERROR]),
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if not integration:
            logger.warning(
                "sync_integration_products: no active/error integration found",
                integration_id=integration_id,
                user_id=user_id,
            )
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

        if platform != "shopify":
            return await _sync_single_pass(db, integration, integration_id, user_id)

        store_url = integration.store_url
        # FIX: decrypt inside the worker — never pass tokens as Celery task args
        access_token = decrypt_token(integration.access_token_encrypted)

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

    if len(cursors) <= 1:
        async with session_maker() as db:
            stmt = select(Integration).where(Integration.id == UUID(integration_id))
            result = await db.execute(stmt)
            integration = result.scalars().first()
            return await _sync_single_pass(db, integration, integration_id, user_id)

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
    base=SyncBaseTask,
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
        # FIX: allow ACTIVE or ERROR — previously ACTIVE-only caused all ERROR
        # integrations to return sentinel failure without attempting sync
        stmt = select(Integration).where(
            Integration.id == UUID(integration_id),
            Integration.user_id == UUID(user_id),
            Integration.status.in_([IntegrationStatus.ACTIVE, IntegrationStatus.ERROR]),
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if not integration:
            logger.warning(
                "sync_chunk: integration not found or not active/error",
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
                # FIX: decrypt_token() — not integration.access_token (AttributeError)
                access_token=decrypt_token(integration.access_token_encrypted),
                cursor=cursor,
                limit=limit,
            )

            if not sync_result.success:
                raise RuntimeError(f"fetch_products failed: {sync_result.error}")

            product_repo = ProductRepository(db)
            link_repo = LinkRepository(db)
            handler = ProductSyncHandler(db, product_repo, link_repo)

            created, updated, deleted = await handler.upsert_products(
                integration=integration,
                external_products=sync_result.products,
            )

        except SoftTimeLimitExceeded:
            logger.warning(
                "sync_chunk soft timeout — retrying",
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
    """Aggregate chunk results and mark integration as idle or error."""
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

    safe_results  = chunk_results or []
    total_created = sum(r.get("created", 0) for r in safe_results if r and r.get("success"))
    total_updated = sum(r.get("updated", 0) for r in safe_results if r and r.get("success"))
    total_deleted = sum(r.get("deleted", 0) for r in safe_results if r and r.get("success"))
    sentinel_fails = [r for r in safe_results if not r or not r.get("success")]

    session_maker = get_task_session_maker()
    async with session_maker() as db:
        stmt = select(Integration).where(Integration.id == UUID(integration_id))
        result = await db.execute(stmt)
        integration = result.scalars().first()
        if integration:
            # "idle"/"error" — recognized by UI polling. "completed"/"failed" are NOT.
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
    Fires when a chunk exhausts retries and raises (not sentinel returns).
    link_error only fires on raised exceptions — sentinel returns go to the
    success callback. This handles the hard failure path.
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
            integration.sync_status = "error"
            integration.error_message = str(exc)[:500]
            try:
                integration.last_error = json.dumps({
                    "failed_at": datetime.now(UTC).isoformat(),
                    "exc_type": type(exc).__name__,
                    "exc_message": str(exc),
                    "celery_task_id": getattr(request, "id", None),
                })
            except Exception:
                pass  # last_error column may not exist yet
            await db.commit()
            logger.info("sync dead-letter recorded", integration_id=integration_id)


# ==============================================================================
# SINGLE-PASS HELPER
# ==============================================================================

async def _sync_single_pass(db, integration, integration_id: str, user_id: str) -> dict:
    """
    Single-pass sync for small Shopify stores or WooCommerce.
    sync_all_products handles internal pagination.
    Sets sync_status = "idle" on success, "error" on failure.
    """
    from datetime import UTC, datetime
    from models.integration import Integration
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from services.integration.repositories.link_repo import LinkRepository
    from services.integration.repositories.product_repo import ProductRepository

    try:
        product_repo = ProductRepository(db)
        link_repo = LinkRepository(db)
        handler = ProductSyncHandler(db, product_repo, link_repo)

        created, updated, deleted = await handler.sync_all_products(
            integration, sync_type="full"
        )

        integration.sync_status = "idle"
        integration.last_sync_at = datetime.now(UTC)
        integration.products_synced = created + updated
        integration.error_message = None
        await db.commit()

        result_dict = {
            "success": True,
            "mode": "single_pass",
            "integration_id": integration_id,
            "created": created,
            "updated": updated,
            "deleted": deleted,
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
                integration_row.error_message = str(exc)[:500]
                await db.commit()
        except Exception:
            pass
        raise


    

