"""
MNEE Payment Service

High-level service for MNEE payment operations.
Provides business logic on top of the low-level client.
"""

import logging
from decimal import Decimal
from typing import Any

from .exceptions import MneeConfigError, MneeValidationError
from .mnee_client import MneeClient

logger = logging.getLogger(__name__)


class MneeService:
    """
    High-level MNEE payment service.

    Provides:
    - Address validation
    - Balance checking
    - Transaction monitoring
    - Amount formatting
    """

    # MNEE uses 5 decimal places (from config.decimals)
    DECIMALS = 5

    def __init__(self, client: MneeClient):
        """
        Initialize service with MNEE client.

        Args:
            client: Configured MneeClient instance
        """
        self._client = client
        self._config: dict[str, Any] | None = None

    @property
    def environment(self) -> str:
        """Get current environment."""
        return self._client.environment.value

    async def close(self) -> None:
        """Close underlying client."""
        await self._client.close()

    # =========================================================================
    # Configuration
    # =========================================================================

    async def get_config(self) -> dict[str, Any]:
        """
        Get MNEE configuration (cached).

        Returns:
            MNEE config with fees, addresses, etc.
        """
        if self._config is None:
            self._config = await self._client.get_config()
        return self._config

    async def get_fee_structure(self) -> list[dict[str, int]]:
        """
        Get fee structure for transfers.

        Returns:
            List of fee tiers with min/max/fee amounts
        """
        config = await self.get_config()
        return config.get("fees", [])

    # =========================================================================
    # Address Validation
    # =========================================================================

    @staticmethod
    def validate_bsv_address(address: str) -> bool:
        """
        Validate BSV address format.

        BSV addresses use Base58Check encoding:
        - P2PKH (Pay to Public Key Hash): Start with '1', 25-34 chars
        - P2SH (Pay to Script Hash): Start with '3', 25-34 chars

        Args:
            address: Address to validate

        Returns:
            True if valid BSV address
        """
        if not address or not isinstance(address, str):
            return False

        # Reject Ethereum addresses explicitly
        if address.startswith("0x"):
            return False

        # Check BSV legacy format
        if not address.startswith(("1", "3")):
            return False

        # Length check (25-34 characters)
        if not (25 <= len(address) <= 34):
            return False

        # Base58 characters only (excludes 0, O, I, l)
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return all(c in base58_chars for c in address)

    def require_valid_address(self, address: str, field_name: str = "address") -> str:
        """
        Validate address and raise if invalid.

        Args:
            address: Address to validate
            field_name: Field name for error message

        Returns:
            Validated address

        Raises:
            MneeValidationError: If address is invalid
        """
        if not address:
            raise MneeValidationError(f"{field_name} is required", field=field_name)

        address = address.strip()

        if address.startswith("0x"):
            raise MneeValidationError(
                "Ethereum addresses (0x...) are not supported. MNEE uses BSV addresses starting with '1' or '3'.",
                field=field_name,
            )

        if not self.validate_bsv_address(address):
            raise MneeValidationError(
                "Invalid BSV address. Must start with '1' or '3' and be 25-34 characters.",
                field=field_name,
            )

        return address

    # =========================================================================
    # Balance Operations
    # =========================================================================

    async def get_balance(self, address: str) -> dict[str, Any]:
        """
        Get MNEE balance for a single address.

        Args:
            address: BSV wallet address

        Returns:
            {
                "address": "1...",
                "balance": "34.22",  # Human readable
                "balance_raw": 3422000,  # Raw amount (5 decimals)
            }
        """
        address = self.require_valid_address(address)

        balances = await self._client.get_balances([address])

        if not balances:
            return {
                "address": address,
                "balance": "0.00",
                "balance_raw": 0,
            }

        balance_data = balances[0]
        return {
            "address": address,
            "balance": str(balance_data.get("precised", 0)),
            "balance_raw": balance_data.get("amt", 0),
        }

    async def get_balances(self, addresses: list[str]) -> list[dict[str, Any]]:
        """
        Get MNEE balances for multiple addresses.

        Args:
            addresses: List of BSV wallet addresses

        Returns:
            List of balance objects
        """
        # Validate all addresses
        validated = [self.require_valid_address(addr) for addr in addresses]

        balances = await self._client.get_balances(validated)

        return [
            {
                "address": b.get("address"),
                "balance": str(b.get("precised", 0)),
                "balance_raw": b.get("amt", 0),
            }
            for b in balances
        ]

    # =========================================================================
    # Transaction Operations
    # =========================================================================

    async def get_transaction(self, txid: str) -> dict[str, Any]:
        """
        Get transaction details.

        Args:
            txid: Transaction ID

        Returns:
            Transaction data
        """
        if not txid:
            raise MneeValidationError("Transaction ID is required", field="txid")

        return await self._client.get_transaction(txid)

    async def get_transaction_history(
        self,
        address: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get transaction history for an address.

        Args:
            address: BSV wallet address
            limit: Max transactions to return

        Returns:
            List of transactions
        """
        address = self.require_valid_address(address)
        return await self._client.get_transactions([address], limit=limit)

    async def check_transfer_status(self, ticket_id: str) -> dict[str, Any]:
        """
        Check status of a transfer by ticket ID.

        Args:
            ticket_id: Ticket ID from transfer submission

        Returns:
            {
                "id": "...",
                "status": "pending|confirmed|failed",
                "txid": "...",
                "error": "..." (if failed)
            }
        """
        if not ticket_id:
            raise MneeValidationError("Ticket ID is required", field="ticket_id")

        ticket = await self._client.get_ticket(ticket_id)

        return {
            "id": ticket.get("id"),
            "status": ticket.get("status"),
            "txid": ticket.get("tx_id"),
            "error": ticket.get("errors"),
            "created_at": ticket.get("createdAt"),
            "updated_at": ticket.get("updatedAt"),
        }

    # =========================================================================
    # Amount Utilities
    # =========================================================================

    @classmethod
    def format_amount(cls, raw_amount: int) -> str:
        """
        Format raw amount to human-readable string.

        MNEE uses 5 decimal places.

        Args:
            raw_amount: Amount in smallest unit

        Returns:
            Formatted string (e.g., "34.22")
        """
        if raw_amount == 0:
            return "0.00"

        decimal_value = Decimal(raw_amount) / Decimal(10**cls.DECIMALS)
        return f"{decimal_value:.2f}"

    @classmethod
    def to_raw_amount(cls, amount: str) -> int:
        """
        Convert human-readable amount to raw.

        Args:
            amount: Amount string (e.g., "34.22")

        Returns:
            Raw amount in smallest unit
        """
        decimal_value = Decimal(amount)
        return int(decimal_value * Decimal(10**cls.DECIMALS))

    @classmethod
    def validate_amount(cls, amount: str) -> Decimal:
        """
        Validate and parse amount.

        Args:
            amount: Amount string

        Returns:
            Decimal value

        Raises:
            MneeValidationError: If amount is invalid
        """
        try:
            value = Decimal(amount)
            if value <= 0:
                raise MneeValidationError("Amount must be greater than 0", field="amount")
            return value
        except Exception as e:
            raise MneeValidationError(f"Invalid amount: {e}", field="amount")


# =============================================================================
# Service Factory
# =============================================================================

_service_instance: MneeService | None = None


def get_mnee_service(
    api_key: str | None = None,
    environment: str | None = None,
) -> MneeService:
    """
    Get or create MNEE service instance (singleton).

    Uses settings from core.config if not provided.

    Args:
        api_key: MNEE API key (optional, uses settings)
        environment: 'sandbox' or 'production' (optional, uses settings)

    Returns:
        MneeService instance
    """
    global _service_instance

    if _service_instance is None:
        # Import settings here to avoid circular imports
        try:
            from core.config import settings

            api_key = api_key or getattr(settings, "MNEE_API_KEY", None)
            environment = environment or getattr(settings, "MNEE_ENVIRONMENT", "sandbox")
        except ImportError:
            pass

        if not api_key:
            raise MneeConfigError(
                "MNEE_API_KEY is required. Set it in environment variables or settings.",
                missing_key="MNEE_API_KEY",
            )

        client = MneeClient(api_key=api_key, environment=environment)
        _service_instance = MneeService(client)

    return _service_instance


async def close_mnee_service() -> None:
    """Close the MNEE service and release resources."""
    global _service_instance
    if _service_instance:
        await _service_instance.close()
        _service_instance = None
