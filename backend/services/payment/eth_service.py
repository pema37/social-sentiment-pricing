"""
Ethereum Payment Verification Service

Verifies MNEE ERC-20 token payments on Ethereum mainnet using Etherscan API.
"""

import logging
import os
from datetime import datetime

import httpx

from schemas.payment import TransactionVerification
from services.payment.base import PaymentVerificationService

logger = logging.getLogger(__name__)


# MNEE Token Contract on Ethereum Mainnet
MNEE_CONTRACT_ADDRESS = "0x8ccedbAe4916b79da7F3F612Ef82EB93A2bFD6cF"

# Etherscan API endpoints
ETHERSCAN_API_URL = "https://api.etherscan.io/api"


class EthereumPaymentService(PaymentVerificationService):
    """
    Ethereum payment verification using Etherscan API.

    Verifies ERC-20 MNEE token transfers on Ethereum mainnet.
    """

    def __init__(self):
        self.api_key = os.getenv("ETHERSCAN_API_KEY", "")
        self.mnee_contract = MNEE_CONTRACT_ADDRESS.lower()
        self._client: httpx.AsyncClient | None = None

    @property
    def network_name(self) -> str:
        return "ethereum"

    @property
    def is_available(self) -> bool:
        """Service is available only when API key is configured."""
        return bool(self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def verify_transaction(
        self,
        transaction_hash: str,
        expected_amount: int,
        expected_recipient: str,
        expected_memo: str | None = None,
    ) -> TransactionVerification:
        """
        Verify an Ethereum MNEE token transfer.

        Args:
            transaction_hash: Ethereum transaction hash (0x...)
            expected_amount: Expected MNEE amount (5 decimal places, so 29 MNEE = 2900000)
            expected_recipient: Expected recipient address
            expected_memo: Not used for Ethereum (no memo field)
        """
        try:
            # Get transaction details
            tx_info = await self.get_transaction_status(transaction_hash)

            if not tx_info.verified:
                return tx_info

            # Verify recipient
            if tx_info.to_address and tx_info.to_address.lower() != expected_recipient.lower():
                return self._create_verification_result(
                    verified=False,
                    transaction_hash=transaction_hash,
                    error=f"Recipient mismatch: expected {expected_recipient}, got {tx_info.to_address}",
                    to_address=tx_info.to_address,
                    from_address=tx_info.from_address,
                    amount_raw=tx_info.amount_raw,
                )

            # Verify amount (with 1% tolerance for gas variations)
            if tx_info.amount_raw:
                tolerance = expected_amount * 0.01
                if abs(tx_info.amount_raw - expected_amount) > tolerance:
                    return self._create_verification_result(
                        verified=False,
                        transaction_hash=transaction_hash,
                        error=f"Amount mismatch: expected {expected_amount}, got {tx_info.amount_raw}",
                        to_address=tx_info.to_address,
                        from_address=tx_info.from_address,
                        amount_raw=tx_info.amount_raw,
                    )

            # All checks passed
            return self._create_verification_result(
                verified=True,
                transaction_hash=transaction_hash,
                to_address=tx_info.to_address,
                from_address=tx_info.from_address,
                amount_raw=tx_info.amount_raw,
                amount=tx_info.amount,
                confirmations=tx_info.confirmations,
                block_height=tx_info.block_height,
                timestamp=tx_info.timestamp,
            )

        except Exception as e:
            logger.error(f"Error verifying Ethereum transaction {transaction_hash}: {e}")
            return self._create_verification_result(
                verified=False,
                transaction_hash=transaction_hash,
                error=str(e),
            )

    async def get_transaction_status(
        self,
        transaction_hash: str,
    ) -> TransactionVerification:
        """
        Get Ethereum transaction details from Etherscan.

        Checks for ERC-20 token transfers (Transfer events).
        """
        try:
            client = await self._get_client()

            # First, get the transaction receipt to check status
            params = {
                "module": "proxy",
                "action": "eth_getTransactionReceipt",
                "txhash": transaction_hash,
            }
            if self.api_key:
                params["apikey"] = self.api_key

            response = await client.get(ETHERSCAN_API_URL, params=params)
            data = response.json()

            if data.get("error") or not data.get("result"):
                return self._create_verification_result(
                    verified=False,
                    transaction_hash=transaction_hash,
                    error="Transaction not found or pending",
                )

            receipt = data["result"]

            # Check if transaction succeeded (status = 0x1)
            if receipt.get("status") != "0x1":
                return self._create_verification_result(
                    verified=False,
                    transaction_hash=transaction_hash,
                    error="Transaction failed",
                )

            # Parse ERC-20 Transfer events from logs
            transfer_info = self._parse_transfer_logs(receipt.get("logs", []))

            if not transfer_info:
                return self._create_verification_result(
                    verified=False,
                    transaction_hash=transaction_hash,
                    error="No MNEE token transfer found in transaction",
                )

            # Get block info for confirmations
            block_number = int(receipt.get("blockNumber", "0x0"), 16)
            confirmations = await self._get_confirmations(block_number)

            # Get timestamp
            timestamp = await self._get_block_timestamp(block_number)

            # Calculate human-readable amount (MNEE has 5 decimals)
            amount_raw = transfer_info["amount_raw"]
            amount = f"{amount_raw / 100000:.2f}"

            return self._create_verification_result(
                verified=True,
                transaction_hash=transaction_hash,
                from_address=transfer_info["from"],
                to_address=transfer_info["to"],
                amount_raw=amount_raw,
                amount=amount,
                confirmations=confirmations,
                block_height=block_number,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Error getting Ethereum transaction {transaction_hash}: {e}")
            return self._create_verification_result(
                verified=False,
                transaction_hash=transaction_hash,
                error=str(e),
            )

    def _parse_transfer_logs(self, logs: list) -> dict | None:
        """
        Parse ERC-20 Transfer event logs to find MNEE transfers.

        Transfer event signature: Transfer(address,address,uint256)
        Topic0: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
        """
        TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

        for log in logs:
            # Check if this is from the MNEE contract
            if log.get("address", "").lower() != self.mnee_contract:
                continue

            topics = log.get("topics", [])
            if len(topics) < 3:
                continue

            # Check for Transfer event
            if topics[0].lower() != TRANSFER_TOPIC.lower():
                continue

            # Parse from/to addresses (remove padding)
            from_address = "0x" + topics[1][-40:]
            to_address = "0x" + topics[2][-40:]

            # Parse amount from data field
            data = log.get("data", "0x0")
            amount_raw = int(data, 16)

            return {
                "from": from_address,
                "to": to_address,
                "amount_raw": amount_raw,
            }

        return None

    async def _get_confirmations(self, block_number: int) -> int:
        """Get number of confirmations for a block."""
        try:
            client = await self._get_client()

            params = {
                "module": "proxy",
                "action": "eth_blockNumber",
            }
            if self.api_key:
                params["apikey"] = self.api_key

            response = await client.get(ETHERSCAN_API_URL, params=params)
            data = response.json()

            current_block = int(data.get("result", "0x0"), 16)
            return max(0, current_block - block_number)

        except Exception:
            return 0

    async def _get_block_timestamp(self, block_number: int) -> datetime | None:
        """Get timestamp for a block."""
        try:
            client = await self._get_client()

            params = {
                "module": "proxy",
                "action": "eth_getBlockByNumber",
                "tag": hex(block_number),
                "boolean": "false",
            }
            if self.api_key:
                params["apikey"] = self.api_key

            response = await client.get(ETHERSCAN_API_URL, params=params)
            data = response.json()

            if data.get("result"):
                timestamp = int(data["result"].get("timestamp", "0x0"), 16)
                if timestamp:
                    return datetime.fromtimestamp(timestamp)

            return None

        except Exception:
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
ethereum_payment_service = EthereumPaymentService()
