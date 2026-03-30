# backend/services/integration/exceptions.py
"""
Typed exceptions for integration service layer.

Using typed exceptions instead of generic ValueError/RuntimeError lets
callers (routes, Celery tasks) distinguish credential failures from
network failures and surface the right message to the merchant.
"""


class IntegrationError(Exception):
    """Base class for all integration errors."""


class CredentialsInvalidError(IntegrationError):
    """
    Raised when a stored OAuth token is rejected by the platform (HTTP 401).

    Callers should:
      1. Set integration.status = IntegrationStatus.ERROR
      2. Set integration.error_message = CREDENTIALS_INVALID_RECONNECT_REQUIRED
      3. Surface a reconnect CTA to the merchant (not a generic 500)

    The integration OAuth flow already allows reconnect from ERROR state
    (see _RECONNECTABLE_STATUSES in oauth.py), so no other changes are needed.
    """

    DEFAULT_MESSAGE = "CREDENTIALS_INVALID_RECONNECT_REQUIRED"

    def __init__(
        self,
        store_url: str,
        integration_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.store_url = store_url
        self.integration_id = integration_id
        self.detail = detail or self.DEFAULT_MESSAGE
        super().__init__(
            f"Shopify credentials invalid for {store_url} "
            f"(integration_id={integration_id}): {self.detail}. "
            "Merchant must reconnect via OAuth."
        )


class RateLimitedError(IntegrationError):
    """Raised when the platform returns HTTP 429. Caller should back off."""

    def __init__(self, store_url: str, retry_after: int = 60) -> None:
        self.store_url = store_url
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited by Shopify for {store_url}. "
            f"Retry after {retry_after}s."
        )


class SyncError(IntegrationError):
    """Raised when a sync operation fails for a recoverable reason."""



    