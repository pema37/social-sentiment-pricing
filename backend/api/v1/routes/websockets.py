"""
WebSocket endpoint handlers.

All endpoints require JWT authentication. Auth is resolved from either:
  - the ``token`` query parameter on the handshake URL
    (e.g. ``/ws/prices?token=<jwt>`` — used by App Bridge / non-browser
    clients that hold the bearer in JS memory), or
  - the ``ssp_access_token`` httpOnly cookie, which the browser sends
    automatically on the upgrade request (regular browser flow).
"""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from core.security import decode_access_token
from core.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_websocket(websocket: WebSocket, token: str | None) -> str | None:
    """Validate JWT on the WebSocket handshake. Returns user_id if authenticated, None otherwise.

    Auth resolution order:
      1. ``?token=<jwt>`` query param (App Bridge / non-browser clients)
      2. ``ssp_access_token`` cookie (regular browser flow)
    """
    if not token:
        token = websocket.cookies.get("ssp_access_token")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return None

    payload = decode_access_token(token)
    if payload is None or payload.get("sub") is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return None

    return str(payload["sub"])


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time price updates."""
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        return

    await manager.connect(websocket, "prices", user_id)
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
        manager.disconnect(websocket, "prices", user_id)


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time alert notifications."""
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        return

    await manager.connect(websocket, "alerts", user_id)
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
        manager.disconnect(websocket, "alerts", user_id)


@router.websocket("/ws/sentiment/{product_id}")
async def websocket_sentiment(websocket: WebSocket, product_id: str, token: str | None = Query(default=None)):
    """WebSocket endpoint for real-time sentiment updates."""
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        return

    await manager.connect_sentiment(websocket, product_id, user_id)
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
        manager.disconnect_sentiment(websocket, product_id, user_id)



        