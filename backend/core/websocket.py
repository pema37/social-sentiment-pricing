# backend/core/websocket.py
"""
WebSocket connection manager and broadcast helpers.

Connections are tracked per-user so broadcasts only reach the
owning user's sessions — never leaked to other merchants.

FIXED (2026-03-29): AP-032 — Added heartbeat ping + stale connection cleanup.
Previously, connections that closed without a clean disconnect (browser tab
killed, mobile sleep, network drop) would remain in active_connections
indefinitely. On a long-running server these accumulate unboundedly and
every broadcast attempt to a dead connection logs an exception.

Fix: ConnectionManager.heartbeat() runs as an asyncio background task
(started in main.py lifespan), pings every connection every 30s, and
removes any that fail to respond. Called via start_heartbeat() helper.
"""

import asyncio
import contextlib
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# How often to ping all connections (seconds)
_HEARTBEAT_INTERVAL = 30


class ConnectionManager:
    """Manages WebSocket connections for real-time updates with per-user isolation."""

    def __init__(self):
        # channel -> user_id -> [websockets]
        self.active_connections: dict[str, dict[str, list[WebSocket]]] = {
            "prices": {},
            "alerts": {},
        }
        # product_id -> user_id -> [websockets]
        self.sentiment_connections: dict[str, dict[str, list[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, channel: str, user_id: str):
        """Connect to a global channel (prices, alerts) scoped to a user."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = {}
        if user_id not in self.active_connections[channel]:
            self.active_connections[channel][user_id] = []
        self.active_connections[channel][user_id].append(websocket)

    async def connect_sentiment(self, websocket: WebSocket, product_id: str, user_id: str):
        """Connect to a product-specific sentiment channel scoped to a user."""
        await websocket.accept()
        if product_id not in self.sentiment_connections:
            self.sentiment_connections[product_id] = {}
        if user_id not in self.sentiment_connections[product_id]:
            self.sentiment_connections[product_id][user_id] = []
        self.sentiment_connections[product_id][user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str, user_id: str):
        """Disconnect from a global channel."""
        user_conns = self.active_connections.get(channel, {}).get(user_id, [])
        if websocket in user_conns:
            user_conns.remove(websocket)
        if not user_conns and channel in self.active_connections:
            self.active_connections[channel].pop(user_id, None)

    def disconnect_sentiment(self, websocket: WebSocket, product_id: str, user_id: str):
        """Disconnect from a product-specific sentiment channel."""
        user_conns = self.sentiment_connections.get(product_id, {}).get(user_id, [])
        if websocket in user_conns:
            user_conns.remove(websocket)
        if not user_conns and product_id in self.sentiment_connections:
            self.sentiment_connections[product_id].pop(user_id, None)
            if not self.sentiment_connections[product_id]:
                del self.sentiment_connections[product_id]

    async def broadcast(self, channel: str, message: dict, user_id: str):
        """Broadcast message to a specific user's connections on a channel."""
        user_conns = self.active_connections.get(channel, {}).get(user_id, [])
        dead: list[WebSocket] = []
        for connection in user_conns:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for ws in dead:
            self._remove_from_channel(ws, channel, user_id)

    async def broadcast_sentiment(self, product_id: str, message: dict, user_id: str):
        """Broadcast message to a specific user's connections watching a product."""
        user_conns = self.sentiment_connections.get(product_id, {}).get(user_id, [])
        dead: list[WebSocket] = []
        for connection in user_conns:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for ws in dead:
            self.disconnect_sentiment(ws, product_id, user_id)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection."""
        await websocket.send_json(message)

    # ── AP-032: Heartbeat ─────────────────────────────────────────

    async def heartbeat(self) -> None:
        """
        Ping all active connections every _HEARTBEAT_INTERVAL seconds.
        Remove any that fail to respond (dead browser tab, network drop, etc.).

        Run as a background task via start_heartbeat() in main.py lifespan:

            async with asyncio.TaskGroup() as tg:
                tg.create_task(manager.heartbeat())

        or equivalently:

            asyncio.create_task(manager.heartbeat())
        """
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await self._ping_all()

    async def _ping_all(self) -> None:
        """Send a ping frame to every tracked connection; prune dead ones."""
        ping_message = {"type": "ping"}

        # Global channels
        for channel, users in list(self.active_connections.items()):
            for user_id, conns in list(users.items()):
                dead: list[WebSocket] = []
                for ws in conns:
                    try:
                        await ws.send_json(ping_message)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self._remove_from_channel(ws, channel, user_id)
                    logger.debug(
                        "heartbeat: removed stale connection from channel=%s user=%s",
                        channel,
                        user_id,
                    )

        # Sentiment channels
        for product_id, users in list(self.sentiment_connections.items()):
            for user_id, conns in list(users.items()):
                dead = []
                for ws in conns:
                    try:
                        await ws.send_json(ping_message)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self.disconnect_sentiment(ws, product_id, user_id)
                    logger.debug(
                        "heartbeat: removed stale sentiment connection product=%s user=%s",
                        product_id,
                        user_id,
                    )

    def _remove_from_channel(self, websocket: WebSocket, channel: str, user_id: str) -> None:
        """Remove a single websocket from a global channel without raising."""
        with contextlib.suppress(Exception):
            user_conns = self.active_connections.get(channel, {}).get(user_id, [])
            if websocket in user_conns:
                user_conns.remove(websocket)
            if not user_conns and channel in self.active_connections:
                self.active_connections[channel].pop(user_id, None)

    def connection_count(self) -> dict[str, int]:
        """Return connection counts per channel — useful for monitoring."""
        counts: dict[str, int] = {}
        for channel, users in self.active_connections.items():
            counts[channel] = sum(len(conns) for conns in users.values())
        sentiment_total = sum(
            len(conns)
            for users in self.sentiment_connections.values()
            for conns in users.values()
        )
        counts["sentiment"] = sentiment_total
        return counts


# Singleton instance
manager = ConnectionManager()


async def start_heartbeat() -> None:
    """
    Start the WebSocket heartbeat as a background task.

    Call this from main.py lifespan:

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            task = asyncio.create_task(start_heartbeat())
            yield
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    """
    await manager.heartbeat()

# ───────────────────── Broadcast Helpers ───────────────────── #
#
# These helpers route through the Redis-backed ws_bridge instead of calling
# manager.broadcast(...) directly. That makes them safe to call from any
# process (Celery workers as well as FastAPI request handlers): ConnectionManager
# holds WS clients in an in-process dict, so only the FastAPI process can
# dispatch to live clients. The subscriber task (started in main.py lifespan)
# receives envelopes from Redis and calls manager.broadcast / .broadcast_sentiment.
#
# Helpers are best-effort: Redis errors are logged and swallowed so a transient
# pub/sub failure never breaks the upstream operation (a price apply must not
# fail just because a WS broadcast couldn't go out).


async def _publish_best_effort(envelope: dict) -> None:
    """Publish via the WS bridge, swallowing Redis errors. Broadcasts are
    fire-and-forget; never propagate failure to the caller."""
    # Deferred import to avoid circular dependency with ws_bridge.
    from core.ws_bridge import publish
    try:
        await publish(envelope)
    except Exception:
        logger.exception("ws broadcast publish failed (swallowed)")


async def broadcast_price_update(product_id: str, data: dict, user_id: str):
    """Call from pricing service when prices change."""
    await _publish_best_effort({
        "method": "broadcast",
        "kwargs": {
            "channel": "prices",
            "message": {"type": "price_update", "product_id": product_id, "data": data},
            "user_id": user_id,
        },
    })


async def broadcast_alert(alert_data: dict, user_id: str):
    """Call from alert service when new alerts are created."""
    await _publish_best_effort({
        "method": "broadcast",
        "kwargs": {
            "channel": "alerts",
            "message": {"type": "new_alert", "data": alert_data},
            "user_id": user_id,
        },
    })


async def broadcast_sentiment_update(product_id: str, sentiment_data: dict, user_id: str):
    """Call from sentiment service when new analysis is complete."""
    await _publish_best_effort({
        "method": "broadcast_sentiment",
        "kwargs": {
            "product_id": product_id,
            "message": {"type": "sentiment_update", "product_id": product_id, "data": sentiment_data},
            "user_id": user_id,
        },
    })


async def broadcast_mention_received(product_id: str, mention_data: dict, user_id: str):
    """Call when a new social mention is received."""
    await _publish_best_effort({
        "method": "broadcast_sentiment",
        "kwargs": {
            "product_id": product_id,
            "message": {"type": "new_mention", "product_id": product_id, "data": mention_data},
            "user_id": user_id,
        },
    })



    