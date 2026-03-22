# backend/api/v1/routes/websockets.py
"""
WebSocket endpoint handlers.

All endpoints require JWT authentication via a ``token`` query parameter
on the WebSocket handshake URL (e.g. ``/ws/prices?token=<jwt>``).
"""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from core.security import decode_access_token
from core.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_websocket(websocket: WebSocket, token: str | None) -> bool:
    """Validate JWT on the WebSocket handshake. Returns True if authenticated."""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return False

    payload = decode_access_token(token)
    if payload is None or payload.get("sub") is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return False

    return True


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time price updates."""
    if not await _authenticate_websocket(websocket, token):
        return

    await manager.connect(websocket, "prices")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "subscribe":
                    await manager.send_personal(
                        websocket, {"type": "subscribed", "channel": "prices", "message": "Subscribed to price updates"}
                    )
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "prices")


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time alert notifications."""
    if not await _authenticate_websocket(websocket, token):
        return

    await manager.connect(websocket, "alerts")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "subscribe":
                    await manager.send_personal(
                        websocket,
                        {"type": "subscribed", "channel": "alerts", "message": "Subscribed to alert notifications"},
                    )
                elif message.get("type") == "acknowledge":
                    await manager.send_personal(
                        websocket, {"type": "acknowledged", "alert_id": message.get("alert_id")}
                    )
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")


@router.websocket("/ws/sentiment/{product_id}")
async def websocket_sentiment(websocket: WebSocket, product_id: str, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time sentiment updates."""
    if not await _authenticate_websocket(websocket, token):
        return

    await manager.connect_sentiment(websocket, product_id)
    try:
        await manager.send_personal(
            websocket,
            {
                "type": "connected",
                "channel": "sentiment",
                "product_id": product_id,
                "message": f"Subscribed to sentiment updates for product {product_id}",
            },
        )

        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "get_status":
                    await manager.send_personal(
                        websocket,
                        {"type": "status", "product_id": product_id, "message": "Listening for sentiment updates"},
                    )
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect_sentiment(websocket, product_id)
