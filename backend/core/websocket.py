# backend/core/websocket.py
"""
WebSocket connection manager and broadcast helpers.
"""

from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "prices": [],
            "alerts": [],
        }
        self.sentiment_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Connect to a global channel (prices, alerts)."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
    
    async def connect_sentiment(self, websocket: WebSocket, product_id: str):
        """Connect to a product-specific sentiment channel."""
        await websocket.accept()
        if product_id not in self.sentiment_connections:
            self.sentiment_connections[product_id] = []
        self.sentiment_connections[product_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect from a global channel."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
    
    def disconnect_sentiment(self, websocket: WebSocket, product_id: str):
        """Disconnect from a product-specific sentiment channel."""
        if product_id in self.sentiment_connections:
            if websocket in self.sentiment_connections[product_id]:
                self.sentiment_connections[product_id].remove(websocket)
            if not self.sentiment_connections[product_id]:
                del self.sentiment_connections[product_id]
    
    async def broadcast(self, channel: str, message: dict):
        """Broadcast message to all connections on a global channel."""
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass
    
    async def broadcast_sentiment(self, product_id: str, message: dict):
        """Broadcast message to all connections watching a specific product."""
        if product_id in self.sentiment_connections:
            for connection in self.sentiment_connections[product_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection."""
        await websocket.send_json(message)


# Singleton instance
manager = ConnectionManager()


# ───────────────────── Broadcast Helpers ───────────────────── #

async def broadcast_price_update(product_id: str, data: dict):
    """Call from pricing service when prices change."""
    await manager.broadcast("prices", {
        "type": "price_update",
        "product_id": product_id,
        "data": data
    })


async def broadcast_alert(alert_data: dict):
    """Call from alert service when new alerts are created."""
    await manager.broadcast("alerts", {
        "type": "new_alert",
        "data": alert_data
    })


async def broadcast_sentiment_update(product_id: str, sentiment_data: dict):
    """Call from sentiment service when new analysis is complete."""
    await manager.broadcast_sentiment(product_id, {
        "type": "sentiment_update",
        "product_id": product_id,
        "data": sentiment_data
    })


async def broadcast_mention_received(product_id: str, mention_data: dict):
    """Call when a new social mention is received."""
    await manager.broadcast_sentiment(product_id, {
        "type": "new_mention",
        "product_id": product_id,
        "data": mention_data
    })
