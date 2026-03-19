"""
Payment Services Package
"""

# Existing exports
from services.payment.exceptions import (
    MneeApiError,
    MneeBaseError,
    MneeConfigError,
    MneeNetworkError,
    MneeValidationError,
)
from services.payment.mnee_client import MneeClient
from services.payment.mnee_service import MneeService, close_mnee_service, get_mnee_service

# Alias for compatibility
PaymentError = MneeBaseError

# New exports
from services.payment.base import PaymentServiceFactory, PaymentVerificationService
from services.payment.bsv_service import bsv_payment_service
from services.payment.eth_service import ethereum_payment_service
from services.payment.subscription_service import PLANS, SubscriptionService

# Register blockchain services
PaymentServiceFactory.register("ethereum", ethereum_payment_service)
PaymentServiceFactory.register("bsv", bsv_payment_service)

__all__ = [
    "PLANS",
    "MneeApiError",
    "MneeBaseError",
    "MneeClient",
    "MneeConfigError",
    "MneeNetworkError",
    # Existing
    "MneeService",
    "MneeValidationError",
    "PaymentError",
    "PaymentServiceFactory",
    # New
    "PaymentVerificationService",
    "SubscriptionService",
    "bsv_payment_service",
    "close_mnee_service",
    "ethereum_payment_service",
    "get_mnee_service",
]
