# backend/api/v1/routes/pricing/_helpers.py
"""
API Helper Functions - Shared utilities for pricing route handlers.

FIX (2026-01-28) Priority 3: Added specific HTTP status codes for different
error types. Previously all errors returned 400, causing frontend to show
generic "Invalid request" message.

This file provides:
1. RecommendationError class hierarchy for route-level validation
2. approval_error_to_http() for converting service-layer ApprovalErrors
3. Helper functions like get_recommendation_or_error()
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.product import Product
from services.pricing.approval_service import ApprovalError

# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION CLASSES (for route-level validation)
# ═══════════════════════════════════════════════════════════════════════════════


class RecommendationError(Exception):
    """Base exception for recommendation-related errors."""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "RECOMMENDATION_ERROR"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class RecommendationNotFoundError(RecommendationError):
    """Raised when recommendation doesn't exist."""

    def __init__(self, recommendation_id: UUID):
        super().__init__(
            message=f"Recommendation {recommendation_id} not found",
            status_code=404,
            error_code="RECOMMENDATION_NOT_FOUND",
        )


class RecommendationExpiredError(RecommendationError):
    """Raised when recommendation has expired."""

    def __init__(self, recommendation_id: UUID | None = None):
        super().__init__(
            message="This price recommendation has expired. Please generate a new one.",
            status_code=410,  # 410 Gone - resource no longer available
            error_code="RECOMMENDATION_EXPIRED",
        )


class RecommendationAlreadyProcessedError(RecommendationError):
    """Raised when recommendation was already approved/rejected."""

    def __init__(self, recommendation_id: UUID | None = None, current_status: str = "processed"):
        super().__init__(
            message=f"This recommendation has already been {current_status}.",
            status_code=409,  # 409 Conflict - resource state conflict
            error_code="RECOMMENDATION_ALREADY_PROCESSED",
        )


class ProductNotFoundError(RecommendationError):
    """Raised when the product for a recommendation doesn't exist."""

    def __init__(self, product_id: UUID):
        super().__init__(message=f"Product {product_id} not found", status_code=404, error_code="PRODUCT_NOT_FOUND")


class IntegrationNotFoundError(RecommendationError):
    """Raised when no active integration exists for price push."""

    def __init__(self):
        super().__init__(
            message="No store connected. Please connect your Shopify or WooCommerce store in Settings → Integrations.",
            status_code=422,
            error_code="INTEGRATION_NOT_FOUND",
        )


class IntegrationNotActiveError(RecommendationError):
    """Raised when integration exists but is not active."""

    def __init__(self, platform: str = "store"):
        super().__init__(
            message=f"Your {platform} connection is inactive. Please reconnect in Settings → Integrations.",
            status_code=422,
            error_code="INTEGRATION_NOT_ACTIVE",
        )


class ProductNotLinkedError(RecommendationError):
    """Raised when product is not linked to store."""

    def __init__(self, product_name: str = "Product"):
        super().__init__(
            message=f"'{product_name}' is not linked to your store. Go to Products → Edit → Link to Store.",
            status_code=422,
            error_code="PRODUCT_NOT_LINKED",
        )


class PricePushFailedError(RecommendationError):
    """Raised when pushing price to store fails."""

    def __init__(self, product_name: str = "Product", reason: str = "Unknown error"):
        super().__init__(
            message=f"Failed to update price for '{product_name}': {reason}",
            status_code=502,  # 502 Bad Gateway - upstream service failed
            error_code="PRICE_PUSH_FAILED",
        )


class UnauthorizedError(RecommendationError):
    """Raised when user doesn't own the recommendation."""

    def __init__(self):
        super().__init__(
            message="You don't have permission to access this recommendation",
            status_code=403,
            error_code="UNAUTHORIZED",
        )


class DailyLimitReachedError(RecommendationError):
    """Raised when user has hit their daily approval limit."""

    def __init__(self, limit: int = 0):
        super().__init__(
            message=f"You've reached your daily limit of {limit} price changes. Upgrade your plan for more.",
            status_code=429,
            error_code="DAILY_LIMIT_REACHED",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE ERROR CONVERSION
# Maps ApprovalError codes from approval_service.py to HTTP responses
# ═══════════════════════════════════════════════════════════════════════════════

# Mapping from ApprovalService error codes to HTTP status codes
ERROR_CODE_TO_STATUS = {
    # Not found errors -> 404
    "NOT_FOUND": 404,
    "RECOMMENDATION_NOT_FOUND": 404,
    "PRODUCT_NOT_FOUND": 404,
    # State conflict errors -> 409
    "INVALID_STATUS": 409,
    "RECOMMENDATION_ALREADY_PROCESSED": 409,
    "ALREADY_APPLIED": 409,
    "ALREADY_APPROVED": 409,
    "ALREADY_REJECTED": 409,
    # Expired -> 410
    "RECOMMENDATION_EXPIRED": 410,
    "EXPIRED": 410,
    # Validation/config errors -> 422
    "NO_ACTIVE_INTEGRATION_LINK": 422,
    "PRODUCT_NOT_LINKED": 422,
    "INTEGRATION_NOT_FOUND": 422,
    "INTEGRATION_NOT_ACTIVE": 422,
    # Rate limits -> 429
    "DAILY_LIMIT_REACHED": 429,
    "RATE_LIMIT": 429,
    # External service failures -> 502
    "PLATFORM_PUSH_FAILED": 502,
    "PRICE_PUSH_FAILED": 502,
    "STORE_ERROR": 502,
    # Auth errors -> 403
    "UNAUTHORIZED": 403,
    "NOT_OWNER": 403,
}

# User-friendly messages for error codes
ERROR_CODE_TO_MESSAGE = {
    "NOT_FOUND": "Recommendation not found",
    "RECOMMENDATION_NOT_FOUND": "Recommendation not found",
    "PRODUCT_NOT_FOUND": "Product not found",
    "INVALID_STATUS": "This recommendation cannot be modified in its current state",
    "RECOMMENDATION_ALREADY_PROCESSED": "This recommendation has already been processed",
    "ALREADY_APPLIED": "This recommendation has already been applied",
    "ALREADY_APPROVED": "This recommendation has already been approved",
    "ALREADY_REJECTED": "This recommendation has already been rejected",
    "RECOMMENDATION_EXPIRED": "This recommendation has expired. Please generate a new one.",
    "EXPIRED": "This recommendation has expired. Please generate a new one.",
    "NO_ACTIVE_INTEGRATION_LINK": "Product is not linked to your store. Go to Products → Edit → Link to Store.",
    "PRODUCT_NOT_LINKED": "Product is not linked to your store. Go to Products → Edit → Link to Store.",
    "INTEGRATION_NOT_FOUND": "No store connected. Go to Settings → Integrations to connect your store.",
    "INTEGRATION_NOT_ACTIVE": "Your store connection is inactive. Please reconnect in Settings → Integrations.",
    "DAILY_LIMIT_REACHED": "You've reached your daily limit for price changes. Upgrade your plan for more.",
    "RATE_LIMIT": "Too many requests. Please wait a moment.",
    "PLATFORM_PUSH_FAILED": "Failed to update price in your store. Please try again.",
    "PRICE_PUSH_FAILED": "Failed to update price in your store. Please try again.",
    "STORE_ERROR": "Your store returned an error. Please check your store connection.",
    "UNAUTHORIZED": "You don't have permission to access this recommendation",
    "NOT_OWNER": "You don't have permission to access this recommendation",
}


def approval_error_to_http(error: ApprovalError) -> HTTPException:
    """
    Convert ApprovalError from approval_service.py to HTTPException.

    Maps error codes to appropriate HTTP status codes and provides
    user-friendly messages with structured detail for frontend parsing.

    Args:
        error: ApprovalError from ApprovalService

    Returns:
        HTTPException with structured detail containing message and error_code
    """
    error_code = getattr(error, "error_code", "UNKNOWN_ERROR")
    original_message = getattr(error, "message", str(error))

    # Get HTTP status code (default to 400)
    status_code = ERROR_CODE_TO_STATUS.get(error_code, 400)

    # Get user-friendly message, fall back to original if not mapped
    message = ERROR_CODE_TO_MESSAGE.get(error_code, original_message)

    # If original message has more specific info (like product name), use it
    # but only if it's not a generic "Error" message
    if original_message and len(original_message) > len(message) and "Error" not in original_message[:10]:
        message = original_message

    return HTTPException(status_code=status_code, detail={"message": message, "error_code": error_code})


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (for route handlers)
# ═══════════════════════════════════════════════════════════════════════════════


async def get_recommendation_or_error(db: AsyncSession, recommendation_id: UUID, user_id: UUID) -> PriceRecommendation:
    """
    Fetch a recommendation and validate ownership.

    Raises appropriate exceptions with specific HTTP status codes:
    - 404: Recommendation not found
    - 403: User doesn't own recommendation
    - 410: Recommendation expired
    - 409: Recommendation already processed

    Returns:
        PriceRecommendation if valid and pending
    """
    stmt = select(PriceRecommendation).where(PriceRecommendation.id == recommendation_id)
    result = await db.execute(stmt)
    recommendation = result.scalars().first()

    if not recommendation:
        raise RecommendationNotFoundError(recommendation_id)

    if recommendation.user_id != user_id:
        raise UnauthorizedError()

    # Check if already processed
    if recommendation.status == RecommendationStatus.APPROVED:
        raise RecommendationAlreadyProcessedError(recommendation_id, "approved")

    if recommendation.status == RecommendationStatus.REJECTED:
        raise RecommendationAlreadyProcessedError(recommendation_id, "rejected")

    if recommendation.status == RecommendationStatus.APPLIED:
        raise RecommendationAlreadyProcessedError(recommendation_id, "applied")

    if recommendation.status == RecommendationStatus.EXPIRED:
        raise RecommendationExpiredError(recommendation_id)

    # Check if valid_until has passed (even if status not updated yet)
    if recommendation.valid_until and recommendation.valid_until < datetime.now(UTC):
        raise RecommendationExpiredError(recommendation_id)

    return recommendation


async def get_product_or_error(db: AsyncSession, product_id: UUID, user_id: UUID) -> Product:
    """
    Fetch a product and validate ownership.

    Raises:
    - 404: Product not found
    - 403: User doesn't own product
    """
    stmt = select(Product).where(Product.id == product_id)
    result = await db.execute(stmt)
    product = result.scalars().first()

    if not product:
        raise ProductNotFoundError(product_id)

    if product.user_id != user_id:
        raise UnauthorizedError()

    return product


def raise_http_exception(error: RecommendationError) -> HTTPException:
    """
    Convert RecommendationError to FastAPI HTTPException with structured detail.

    Response format:
    {
        "detail": {
            "message": "Human-readable error message",
            "error_code": "MACHINE_READABLE_CODE"
        }
    }
    """
    raise HTTPException(
        status_code=error.status_code, detail={"message": error.message, "error_code": error.error_code}
    )
