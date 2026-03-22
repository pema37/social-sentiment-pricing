# backend/core/websocket.py
"""
WebSocket connection manager and broadcast helpers.

Connections are tracked per-user so broadcasts only reach the
owning user's sessions — never leaked to other merchants.
"""

import contextlib

from fastapi import WebSocket


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
        for connection in user_conns:
            with contextlib.suppress(Exception):
                await connection.send_json(message)

    async def broadcast_sentiment(self, product_id: str, message: dict, user_id: str):
        """Broadcast message to a specific user's connections watching a product."""
        user_conns = self.sentiment_connections.get(product_id, {}).get(user_id, [])
        for connection in user_conns:
            with contextlib.suppress(Exception):
                await connection.send_json(message)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection."""
        await websocket.send_json(message)


# Singleton instance
manager = ConnectionManager()


# ───────────────────── Broadcast Helpers ───────────────────── #


async def broadcast_price_update(product_id: str, data: dict, user_id: str):
    """Call from pricing service when prices change."""
    await manager.broadcast("prices", {"type": "price_update", "product_id": product_id, "data": data}, user_id)


async def broadcast_alert(alert_data: dict, user_id: str):
    """Call from alert service when new alerts are created."""
    await manager.broadcast("alerts", {"type": "new_alert", "data": alert_data}, user_id)


async def broadcast_sentiment_update(product_id: str, sentiment_data: dict, user_id: str):
    """Call from sentiment service when new analysis is complete."""
    await manager.broadcast_sentiment(
        product_id, {"type": "sentiment_update", "product_id": product_id, "data": sentiment_data}, user_id
    )


async def broadcast_mention_received(product_id: str, mention_data: dict, user_id: str):
    """Call when a new social mention is received."""
    await manager.broadcast_sentiment(
        product_id, {"type": "new_mention", "product_id": product_id, "data": mention_data}, user_id
    )
