"""
Payment Routes Module

Handles MNEE payment operations:
- Wallet management (BSV addresses)
- Subscription plans and billing
- Payment webhooks
"""

from fastapi import APIRouter

from .subscription import router as subscription_router
from .wallet import router as wallet_router
from .webhook import router as webhook_router

router = APIRouter(prefix="/payments", tags=["Payments"])

# Include sub-routers
router.include_router(wallet_router)
router.include_router(subscription_router)
router.include_router(webhook_router)

__all__ = ["router"]
