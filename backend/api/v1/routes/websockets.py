# backend/api/v1/routes/websockets.py
"""
WebSocket endpoint handlers.
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket import manager

router = APIRouter()


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for real-time price updates."""
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
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert notifications."""
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
async def websocket_sentiment(websocket: WebSocket, product_id: str):
    """WebSocket endpoint for real-time sentiment updates."""
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
