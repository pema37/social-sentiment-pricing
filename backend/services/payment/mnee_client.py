"""
MNEE HTTP Client

Low-level HTTP client for MNEE API communication.
Handles authentication, retries, and error handling.
"""

import logging
from enum import StrEnum
from typing import Any

import httpx

from .exceptions import MneeApiError, MneeConfigError, MneeNetworkError

logger = logging.getLogger(__name__)


class MneeEnvironment(StrEnum):
    """MNEE API environments."""

    SANDBOX = "sandbox"
    PRODUCTION = "production"


class MneeClient:
    """
    Low-level HTTP client for MNEE API.

    Handles:
    - Authentication with API key
    - Request/response handling
    - Error translation
    - Connection management
    """

    # API endpoints per environment
    API_URLS = {
        MneeEnvironment.SANDBOX: "https://sandbox-proxy-api.mnee.net",
        MneeEnvironment.PRODUCTION: "https://proxy-api.mnee.net",
    }

    def __init__(
        self,
        api_key: str,
        environment: str = "sandbox",
        timeout: float = 30.0,
    ):
        """
        Initialize MNEE client.

        Args:
            api_key: MNEE API key from developer portal
            environment: 'sandbox' or 'production'
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise MneeConfigError("MNEE API key is required", missing_key="MNEE_API_KEY")

        self.api_key = api_key
        self.environment = MneeEnvironment(environment)
        self.base_url = self.API_URLS[self.environment]
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

        logger.info(f"MNEE client initialized for {self.environment.value} environment")

    @property
    def _headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "auth_token": self.api_key,  # MNEE uses auth_token header
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
    ) -> Any:
        """
        Make HTTP request to MNEE API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/v1/config')
            params: Query parameters
            json_data: JSON body data

        Returns:
            Parsed JSON response

        Raises:
            MneeApiError: On API errors
            MneeNetworkError: On network errors
        """
        try:
            client = await self._get_client()

            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_data,
            )

            # Log request for debugging
            logger.debug(f"MNEE {method} {endpoint} -> {response.status_code}")

            # Handle errors
            if response.status_code >= 400:
                error_detail = self._parse_error(response)
                raise MneeApiError(
                    message=f"MNEE API error: {error_detail}",
                    status_code=response.status_code,
                    response=error_detail,
                )

            # Parse response
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            else:
                # Some endpoints return plain text (like ticket IDs)
                return response.text

        except httpx.TimeoutException as e:
            logger.error(f"MNEE request timeout: {endpoint}")
            raise MneeNetworkError("Request to MNEE timed out", original_error=e)
        except httpx.RequestError as e:
            logger.error(f"MNEE network error: {e}")
            raise MneeNetworkError(f"Network error: {e}", original_error=e)

    def _parse_error(self, response: httpx.Response) -> dict[str, Any]:
        """Parse error response from MNEE."""
        try:
            return response.json()
        except Exception:
            return {"message": response.text, "status": response.status_code}

    # =========================================================================
    # API Methods
    # =========================================================================

    async def get_config(self) -> dict[str, Any]:
        """
        Get MNEE configuration and fee structure.

        Returns:
            {
                "approver": "02bed35e...",
                "decimals": 5,
                "feeAddress": "1H9wgHCT...",
                "burnAddress": "1HNuPi9Y...",
                "mintAddress": "1AZNdbFY...",
                "fees": [{"fee": 1000, "max": 1000000, "min": 10000}],
                "tokenId": "833a7720..."
            }
        """
        return await self._request("GET", "/v1/config")

    async def get_balances(self, addresses: list[str]) -> list[dict[str, Any]]:
        """
        Get MNEE balances for addresses.

        Args:
            addresses: List of BSV addresses

        Returns:
            [
                {"address": "1A1QNE...", "amt": 30300303, "precised": 34.22},
                ...
            ]
        """
        return await self._request("POST", "/v2/balance", json_data=addresses)

    async def get_utxos(
        self,
        addresses: list[str],
        page: int = 1,
        size: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get UTXOs for addresses.

        Args:
            addresses: List of BSV addresses
            page: Page number (default 1)
            size: Page size (default 10)

        Returns:
            List of UTXO objects
        """
        return await self._request(
            "POST",
            "/v2/utxos",
            params={"page": str(page), "size": str(size)},
            json_data=addresses,
        )

    async def get_transaction(self, txid: str) -> dict[str, Any]:
        """
        Get transaction by ID.

        Args:
            txid: Transaction ID

        Returns:
            Transaction data with rawtx
        """
        return await self._request("GET", f"/v1/tx/{txid}")

    async def get_transactions(
        self,
        addresses: list[str],
        limit: int = 100,
        from_score: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get transactions for addresses.

        Args:
            addresses: List of BSV addresses
            limit: Max transactions per address (0 = all)
            from_score: Min score for pagination

        Returns:
            List of transaction objects
        """
        params = {"limit": limit}
        if from_score:
            params["from"] = from_score

        return await self._request("POST", "/v1/sync", params=params, json_data=addresses)

    async def submit_transfer(self, rawtx: str) -> str:
        """
        Submit a transfer transaction.

        Note: rawtx must be a properly constructed and signed BSV transaction.
        Building raw transactions requires the MNEE TypeScript SDK.

        Args:
            rawtx: Base64 encoded raw transaction

        Returns:
            Ticket ID for tracking the transaction
        """
        result = await self._request("POST", "/v2/transfer", json_data={"rawtx": rawtx})
        return result if isinstance(result, str) else result.get("ticketId", result)

    async def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        """
        Get transfer ticket status.

        Args:
            ticket_id: Ticket ID from transfer

        Returns:
            {
                "id": "a1b2c3...",
                "status": "pending|confirmed|failed",
                "tx_id": "...",
                "errors": "...",
                ...
            }
        """
        return await self._request("GET", "/v2/ticket", params={"ticketID": ticket_id})
