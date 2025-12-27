"""
Payment Services Package
"""

# Existing exports (keep these)
from services.payment.mnee_service import MNEEService
from services.payment.mnee_client import MNEEClient
from services.payment.exceptions import PaymentError

# New exports (add these)
from services.payment.base import PaymentVerificationService, PaymentServiceFactory
from services.payment.subscription_service import SubscriptionService, PLANS
from services.payment.eth_service import ethereum_payment_service
from services.payment.bsv_service import bsv_payment_service

# Register blockchain services
PaymentServiceFactory.register("ethereum", ethereum_payment_service)
PaymentServiceFactory.register("bsv", bsv_payment_service)

__all__ = [
    # Existing
    "MNEEService",
    "MNEEClient", 
    "PaymentError",
    # New
    "PaymentVerificationService",
    "PaymentServiceFactory",
    "SubscriptionService",
    "PLANS",
    "ethereum_payment_service",
    "bsv_payment_service",
]
