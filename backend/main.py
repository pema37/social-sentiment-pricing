# backend/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import json

from core.config import settings
from api.v1.routes.auth import router as auth_router
from api.v1.routes.health import router as health_router
from api.v1.routes.users import router as users_router
from api.v1.routes.products import router as products_router
from api.v1.routes.sentiment import router as sentiment_router
from api.v1.routes.competitors import router as competitors_router
from api.v1.routes.integrations import router as integrations_router
from api.v1.routes.webhooks import router as webhooks_router
from api.v1.routes.pricing import router as pricing_router
from api.v1.routes.alerts import router as alerts_router  
from api.v1.routes.analytics import router as analytics_router


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ───────────────────── CORS Configuration ───────────────────── #

ALLOWED_ORIGINS: List[str] = getattr(settings, 'CORS_ORIGINS', None) or [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["X-Total-Count", "X-Total-Pages"],
)


# ───────────────────── WebSocket Connection Manager ───────────────────── #

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Global channels
        self.active_connections: Dict[str, List[WebSocket]] = {
            "prices": [],
            "alerts": [],
        }
        # Product-specific sentiment channels
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
            # Clean up empty lists
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


manager = ConnectionManager()


# ───────────────────── WebSocket Endpoints ───────────────────── #

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """
    WebSocket endpoint for real-time price updates.
    
    Clients receive:
    - Price recommendation updates
    - Price change notifications
    - Sentiment score changes affecting pricing
    """
    await manager.connect(websocket, "prices")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "subscribe":
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "channel": "prices",
                        "message": "Subscribed to price updates"
                    })
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "prices")


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert notifications.
    
    Clients receive:
    - New alert notifications
    - Alert status changes
    - Critical alerts requiring immediate attention
    """
    await manager.connect(websocket, "alerts")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "subscribe":
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "channel": "alerts",
                        "message": "Subscribed to alert notifications"
                    })
                elif message.get("type") == "acknowledge":
                    alert_id = message.get("alert_id")
                    await manager.send_personal(websocket, {
                        "type": "acknowledged",
                        "alert_id": alert_id
                    })
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")


@app.websocket("/ws/sentiment/{product_id}")
async def websocket_sentiment(websocket: WebSocket, product_id: str):
    """
    WebSocket endpoint for real-time sentiment updates for a specific product.
    
    Clients receive:
    - New sentiment analysis results
    - Sentiment score changes
    - Social mention notifications
    - Sentiment trend updates
    """
    await manager.connect_sentiment(websocket, product_id)
    try:
        # Send initial connection confirmation
        await manager.send_personal(websocket, {
            "type": "connected",
            "channel": "sentiment",
            "product_id": product_id,
            "message": f"Subscribed to sentiment updates for product {product_id}"
        })
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif message.get("type") == "get_status":
                    # Could return current sentiment status
                    await manager.send_personal(websocket, {
                        "type": "status",
                        "product_id": product_id,
                        "message": "Listening for sentiment updates"
                    })
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect_sentiment(websocket, product_id)


# ───────────────────── Broadcast Helper Functions ───────────────────── #

async def broadcast_price_update(product_id: str, data: dict):
    """Call this from pricing service when prices change."""
    await manager.broadcast("prices", {
        "type": "price_update",
        "product_id": product_id,
        "data": data
    })


async def broadcast_alert(alert_data: dict):
    """Call this from alert service when new alerts are created."""
    await manager.broadcast("alerts", {
        "type": "new_alert",
        "data": alert_data
    })


async def broadcast_sentiment_update(product_id: str, sentiment_data: dict):
    """Call this from sentiment service when new analysis is complete."""
    await manager.broadcast_sentiment(product_id, {
        "type": "sentiment_update",
        "product_id": product_id,
        "data": sentiment_data
    })


async def broadcast_mention_received(product_id: str, mention_data: dict):
    """Call this when a new social mention is received."""
    await manager.broadcast_sentiment(product_id, {
        "type": "new_mention",
        "product_id": product_id,
        "data": mention_data
    })


# ───────────────────── Root Endpoint ───────────────────── #

@app.get("/", tags=["root"])
def read_root():
    return {
        "message": "SSP backend is running",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "websockets": {
            "prices": "/ws/prices",
            "alerts": "/ws/alerts",
            "sentiment": "/ws/sentiment/{product_id}",
        }
    }


# ───────────────────── API Routers ───────────────────── #

app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(competitors_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")  
app.include_router(analytics_router, prefix="/api/v1")
