# backend/api/v1/routes/pricing/_helpers.py
"""
Shared helper functions for pricing endpoints.
"""

from fastapi import HTTPException

from services.pricing.approval_service import ApprovalError


def approval_error_to_http(error: ApprovalError) -> HTTPException:
    """
    Convert ApprovalError to HTTPException with user-friendly message.
    
    Returns structured JSON:
    {
        "detail": {
            "message": "User-friendly message",
            "error_code": "MACHINE_READABLE_CODE",
            "suggestion": "What the user should do"
        }
    }
    """
    suggestions = {
        "DAILY_LIMIT_REACHED": "Go to Settings → Pricing to increase your daily limit.",
        "NO_ACTIVE_INTEGRATION_LINK": "Go to Integrations → Sync Products to link this product to your store.",
        "PRODUCT_NOT_LINKED": "Go to Integrations → Sync Products to link this product to your store.",
        "PLATFORM_PUSH_FAILED": "Check your store connection in Integrations. The platform may be temporarily unavailable.",
        "RECOMMENDATION_EXPIRED": "Generate a new recommendation for this product.",
        "INVALID_STATUS": "This recommendation has already been processed.",
        "NOT_FOUND": "The recommendation may have been deleted or you don't have access to it.",
        "PRODUCT_NOT_FOUND": "The product associated with this recommendation no longer exists.",
    }
    
    suggestion = suggestions.get(error.error_code, "Please try again or contact support.")
    
    return HTTPException(
        status_code=400,
        detail={
            "message": error.message,
            "error_code": error.error_code,
            "suggestion": suggestion
        }
    )


    