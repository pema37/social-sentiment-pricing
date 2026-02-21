"""
MNEE Payment Exceptions

Custom exceptions for MNEE payment operations.
"""


class MneeBaseError(Exception):
    """Base exception for MNEE errors."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class MneeApiError(MneeBaseError):
    """Error from MNEE API."""
    
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.status_code = status_code
        self.response = response
        super().__init__(
            message=message,
            code="MNEE_API_ERROR",
            details={"status_code": status_code, "response": response}
        )


class MneeValidationError(MneeBaseError):
    """Validation error for MNEE operations."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(
            message=message,
            code="MNEE_VALIDATION_ERROR",
            details={"field": field}
        )


class MneeConfigError(MneeBaseError):
    """Configuration error for MNEE service."""
    
    def __init__(self, message: str, missing_key: str = None):
        self.missing_key = missing_key
        super().__init__(
            message=message,
            code="MNEE_CONFIG_ERROR",
            details={"missing_key": missing_key}
        )


class MneeNetworkError(MneeBaseError):
    """Network error when communicating with MNEE."""
    
    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(
            message=message,
            code="MNEE_NETWORK_ERROR",
            details={"original_error": str(original_error) if original_error else None}
        )

