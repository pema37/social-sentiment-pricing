"""
WebSocket event bridge.

Decouples broadcast helpers from the FastAPI process holding WS connections.
Producers (Celery workers, route handlers, anywhere) call publish().
The FastAPI process runs subscribe_loop() as a background task; it receives
envelopes from Redis and dispatches to the ConnectionManager.

Why this exists: ConnectionManager holds WS connections in an in-process
dict. A Celery worker calling manager.broadcast(...) directly hits a
different process's empty manager — the message never reaches the client.
Redis pub/sub crosses the process boundary.

Envelope schema:
    {
        "method": "broadcast" | "broadcast_sentiment",
        "kwargs": {
            # for "broadcast":          channel, message, user_id
            # for "broadcast_sentiment": product_id, message, user_id
        }
    }
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger(__name__)

WS_CHANNEL = "ws:events"

# Lazily-initialized publish client. Reused across calls in a process.
_publish_client: aioredis.Redis | None = None
_publish_lock = asyncio.Lock()


async def _get_publish_client() -> aioredis.Redis:
    global _publish_client
    if _publish_client is None:
        async with _publish_lock:
            if _publish_client is None:
                _publish_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
    return _publish_client


async def publish(envelope: dict[str, Any]) -> None:
    """
    Publish a WS event envelope to Redis. Safe to call from any process.
    Raises on Redis failure — callers decide whether to swallow.
    """
    client = await _get_publish_client()
    payload = json.dumps(envelope)
    await client.publish(WS_CHANNEL, payload)


async def _dispatch(envelope: dict[str, Any]) -> None:
    """Dispatch a received envelope to the appropriate manager method."""
    # Deferred import: avoids circular dependency with core.websocket
    from core.websocket import manager

    method = envelope.get("method")
    kwargs = envelope.get("kwargs", {})

    try:
        if method == "broadcast":
            await manager.broadcast(**kwargs)
        elif method == "broadcast_sentiment":
            await manager.broadcast_sentiment(**kwargs)
        else:
            logger.warning("ws_bridge: unknown method %r in envelope", method)
    except TypeError as e:
        logger.exception("ws_bridge: bad kwargs for method=%s: %s", method, e)
    except Exception:
        logger.exception("ws_bridge: dispatch failed for method=%s", method)


async def _safe_close(pubsub, client) -> None:
    if pubsub is not None:
        try:
            await pubsub.unsubscribe(WS_CHANNEL)
            await pubsub.close()
        except Exception:
            pass
    if client is not None:
        try:
            await client.close()
        except Exception:
            pass


async def subscribe_loop() -> None:
    """
    Long-running subscriber. Run as a FastAPI background task via lifespan.
    Reconnects on Redis errors with exponential backoff. Cancellable.
    """
    backoff = 1.0
    max_backoff = 30.0

    while True:
        client = None
        pubsub = None
        try:
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe(WS_CHANNEL)
            logger.info("ws_bridge: subscribed to %s", WS_CHANNEL)
            backoff = 1.0  # reset after successful connect

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("ws_bridge: invalid JSON in payload")
                    continue
                await _dispatch(envelope)

        except asyncio.CancelledError:
            logger.info("ws_bridge: subscribe_loop cancelled, shutting down")
            await _safe_close(pubsub, client)
            raise

        except Exception:
            logger.exception("ws_bridge: subscribe_loop error, reconnecting in %.1fs", backoff)
            await _safe_close(pubsub, client)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
