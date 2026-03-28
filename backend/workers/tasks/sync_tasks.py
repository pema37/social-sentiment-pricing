# backend/workers/tasks/sync_tasks.py
"""
Sync Tasks — Parallel chunked product sync using Celery chord/group.

Products are fetched from the platform in the orchestrator (no DB writes),
then fanned out to chunk workers (DB writes only), and finalized with a
chord callback that disables missing links.

Fixes BULK_PRODUCTS_UNLINKED (Bug 303.02) and scales to 10,000+ products
by running chunk tasks in parallel across workers.
"""

import dataclasses
from datetime import datetime
from uuid import UUID

from celery import chord, group
from sqlmodel import select

from workers.celery_app import celery_app
from core.logging import get_logger
from workers.tasks.sync_verification_tasks import get_task_session_maker, run_async

logger = get_logger(__name__)

_CHUNK_SIZE = 100


# ==============================================================================
# SERIALIZATION HELPERS
# ==============================================================================


def _serialize_products(products: list) -> list[dict]:
    """Convert ExternalProduct dataclasses to JSON-safe dicts."""
    result = []
    for p in products:
        d = dataclasses.asdict(p)
        d["created_at"] = p.created_at.isoformat() if p.created_at else None
        d["updated_at"] = p.updated_at.isoformat() if p.updated_at else None
        result.append(d)
    return result


def _deserialize_products(data: list[dict]) -> list:
    """Reconstruct ExternalProduct dataclasses from JSON dicts."""
    from services.integration.schemas import ExternalProduct, ExternalProductVariant

    products = []
    for raw in data:
        d = dict(raw)
        d["variants"] = [
            ExternalProductVariant(**v)
            for v in (d.get("variants") or [])
        ]
        d["created_at"] = (
            datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None
        )
        d["updated_at"] = (
            datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else None
        )
        products.append(ExternalProduct(**d))
    return products


# ==============================================================================
# ASYNC IMPLEMENTATIONS
# ==============================================================================


async def _orchestrate_sync(integration_id: str, user_id: str) -> dict:
    """
    Fetch ALL products from the platform, split into 100-product batches,
    and dispatch a Celery chord to process chunks in parallel.

    No DB writes happen here — only API calls and task dispatch.
    """
    from models.integration import Integration, IntegrationStatus
    from services.integration.handlers.product_sync_handler import ProductSyncHandler
    from core.encryption import decrypt_token

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

        platform = integration.platform
        store_url = integration.store_url
        access_token = decrypt_token(integration.access_token_encrypted)

    # DB session closed — paginate the platform API without holding a connection.
    service = ProductSyncHandler.get_service(platform)

    all_products: list = []
    cursor = None
    has_more = True

    while has_more:
        fetch_result = await service.fetch_products(
            store_url=store_url,
            access_token=access_token,
            cursor=cursor,
            limit=_CHUNK_SIZE,
        )

        if not fetch_result.success:
            logger.error(
                "sync_integration_products: fetch_products failed",
                integration_id=integration_id,
                error=fetch_result.error,
            )
            return {
                "success": False,
                "error": f"Failed to fetch products: {fetch_result.error}",
                "integration_id": integration_id,
            }

        all_products.extend(fetch_result.products or [])
        cursor = fetch_result.next_cursor
        has_more = fetch_result.has_more

    if not all_products:
        logger.info(
            "sync_integration_products: no products found, nothing to sync",
            integration_id=integration_id,
        )
        return {
            "status": "dispatched",
            "chunks": 0,
            "integration_id": integration_id,
            "total_products": 0,
        }

    batches = [
        all_products[i : i + _CHUNK_SIZE]
        for i in range(0, len(all_products), _CHUNK_SIZE)
    ]

    chunk_tasks = [
        sync_integration_products_chunk.s(
            integration_id,
            user_id,
            _serialize_products(batch),
            chunk_index,
        )
        for chunk_index, batch in enumerate(batches)
    ]

    finalize_sig = sync_integration_products_finalize.s(integration_id, user_id)

    chord(group(chunk_tasks))(finalize_sig)

    logger.info(
        "sync_integration_products: dispatched chord",
        integration_id=integration_id,
        chunks=len(batches),
        total_products=len(all_products),
    )

    return {
        "status": "dispatched",
        "chunks": len(batches),
        "integration_id": integration_id,
        "total_products": len(all_products),
    }


async def _process_chunk(
    integration_id: str,
    user_id: str,
    products_data: list[dict],
    chunk_index: int,
) -> dict:
    """
    Upsert a batch of products into the DB.  All DB writes for this chunk
    happen here; no API calls are made.
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
                "sync_integration_products_chunk: integration not found",
                integration_id=integration_id,
                chunk_index=chunk_index,
            )
            return {
                "created": 0,
                "updated": 0,
                "seen_ids": [],
                "chunk_index": chunk_index,
            }

        products = _deserialize_products(products_data)
        product_repo = ProductRepository(db)
        link_repo = LinkRepository(db)
        handler = ProductSyncHandler(db, product_repo, link_repo)

        created = 0
        updated = 0
        seen_ids: list[str] = []

        for product in products:
            seen_ids.append(product.id)
            c, u = await handler.upsert_product(integration, product)
            created += c
            updated += u

        await db.commit()

    logger.info(
        "sync_integration_products_chunk complete",
        integration_id=integration_id,
        chunk_index=chunk_index,
        created=created,
        updated=updated,
    )

    return {
        "created": created,
        "updated": updated,
        "seen_ids": seen_ids,
        "chunk_index": chunk_index,
    }


async def _finalize_sync(
    chord_results: list[dict | None],
    integration_id: str,
    user_id: str,
) -> dict:
    """
    Aggregate chunk results and disable links for products no longer present.
    """
    from models.integration import Integration, IntegrationStatus
    from services.integration.repositories.link_repo import LinkRepository

    total_created = 0
    total_updated = 0
    all_seen_ids: set[str] = set()

    for chunk_result in chord_results:
        if not chunk_result:
            continue
        total_created += chunk_result.get("created", 0)
        total_updated += chunk_result.get("updated", 0)
        all_seen_ids.update(chunk_result.get("seen_ids") or [])

    session_maker = get_task_session_maker()
    deleted = 0

    async with session_maker() as db:
        stmt = select(Integration).where(
            Integration.id == UUID(integration_id),
            Integration.user_id == UUID(user_id),
            Integration.status == IntegrationStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if integration:
            link_repo = LinkRepository(db)
            deleted = await link_repo.disable_missing(integration.id, all_seen_ids)

    result_dict = {
        "success": True,
        "integration_id": integration_id,
        "created": total_created,
        "updated": total_updated,
        "deleted": deleted,
    }

    logger.info(
        "sync_integration_products_finalize complete",
        integration_id=integration_id,
        result=result_dict,
    )

    return result_dict


# ==============================================================================
# CELERY TASKS
# ==============================================================================


@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products",
    queue="sync",
)
def sync_integration_products(integration_id: str, user_id: str) -> dict:
    """
    Orchestrator: fetch all products from the platform and fan out to chunk tasks.

    Enqueued by POST /api/v1/product-sync/sync/bulk.
    Fixes Bug 303.02 — BULK_PRODUCTS_UNLINKED.
    """
    return run_async(_orchestrate_sync(integration_id, user_id))


@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products_chunk",
    queue="sync",
)
def sync_integration_products_chunk(
    integration_id: str,
    user_id: str,
    products_data: list[dict],
    chunk_index: int,
) -> dict:
    """
    Chunk worker: upsert a batch of pre-fetched products into the DB.

    Called by the chord dispatched from sync_integration_products.
    """
    return run_async(_process_chunk(integration_id, user_id, products_data, chunk_index))


@celery_app.task(
    name="workers.tasks.sync_tasks.sync_integration_products_finalize",
    queue="sync",
)
def sync_integration_products_finalize(
    chord_results: list,
    integration_id: str,
    user_id: str,
) -> dict:
    """
    Finalize: aggregate chunk results and disable links for deleted products.

    Called automatically by Celery once all chunk tasks complete.
    chord_results is the list of return values from all chunk tasks.
    """
    return run_async(_finalize_sync(chord_results, integration_id, user_id))
