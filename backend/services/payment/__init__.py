"""
Payment Services Package
"""
# Existing exports
from services.payment.mnee_service import MneeService, get_mnee_service, close_mnee_service
from services.payment.mnee_client import MneeClient
from services.payment.exceptions import MneeBaseError, MneeValidationError, MneeApiError, MneeConfigError, MneeNetworkError

# Alias for compatibility
PaymentError = MneeBaseError

# New exports
from services.payment.base import PaymentVerificationService, PaymentServiceFactory
from services.payment.subscription_service import SubscriptionService, PLANS
from services.payment.eth_service import ethereum_payment_service
from services.payment.bsv_service import bsv_payment_service

# Register blockchain services
PaymentServiceFactory.register("ethereum", ethereum_payment_service)
PaymentServiceFactory.register("bsv", bsv_payment_service)

__all__ = [
    # Existing
    "MneeService",
    "MneeClient",
    "MneeBaseError",
    "MneeValidationError",
    "MneeApiError",
    "MneeConfigError",
    "MneeNetworkError",
    "PaymentError",
    "get_mnee_service",
    "close_mnee_service",
    # New
    "PaymentVerificationService",
    "PaymentServiceFactory",
    "SubscriptionService",
    "PLANS",
    "ethereum_payment_service",
    "bsv_payment_service",
]
