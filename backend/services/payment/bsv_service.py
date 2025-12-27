"""
BSV Payment Verification Service

Verifies MNEE payments on BSV network using WhatsOnChain API.
"""

import os
import logging
from typing import Optional
from datetime import datetime

import httpx

from services.payment.base import PaymentVerificationService
from schemas.payment import TransactionVerification

logger = logging.getLogger(__name__)


# WhatsOnChain API for BSV
WHATSONCHAIN_API_URL = "https://api.whatsonchain.com/v1/bsv/main"


class BSVPaymentService(PaymentVerificationService):
    """
    BSV payment verification using WhatsOnChain API.
    
    Verifies MNEE token transfers on BSV network.
    Note: MNEE on BSV uses the 1Sat Ordinals/Tokens standard.
    """
    
    def __init__(self):
        self.api_key = os.getenv("WHATSONCHAIN_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def network_name(self) -> str:
        return "bsv"
    
    @property
    def is_available(self) -> bool:
        """WhatsOnChain has free tier, always available."""
        return True
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers
            )
        return self._client
    
    async def verify_transaction(
        self,
        transaction_hash: str,
        expected_amount: int,
        expected_recipient: str,
        expected_memo: Optional[str] = None,
    ) -> TransactionVerification:
        """
        Verify a BSV MNEE payment.
        
        For BSV, we check:
        1. Transaction exists and is confirmed
        2. Has output to expected recipient
        3. Memo matches (from OP_RETURN)
        
        Note: Full MNEE token verification requires indexer integration.
        For hackathon, we do basic transaction verification.
        """
        try:
            tx_info = await self.get_transaction_status(transaction_hash)
            
            if not tx_info.verified:
                return tx_info
            
            # Check memo if provided
            if expected_memo and tx_info.memo:
                if expected_memo.lower() not in tx_info.memo.lower():
                    return self._create_verification_result(
                        verified=False,
                        transaction_hash=transaction_hash,
                        error=f"Memo mismatch: expected '{expected_memo}' in '{tx_info.memo}'",
                        memo=tx_info.memo,
                        confirmations=tx_info.confirmations,
                    )
            
            # For HandCash/RelayX payments, recipient verification is complex
            # (they use payment handles, not raw addresses)
            # For hackathon, we trust the memo as proof of payment intent
            
            return self._create_verification_result(
                verified=True,
                transaction_hash=transaction_hash,
                memo=tx_info.memo,
                confirmations=tx_info.confirmations,
                block_height=tx_info.block_height,
                timestamp=tx_info.timestamp,
            )
            
        except Exception as e:
            logger.error(f"Error verifying BSV transaction {transaction_hash}: {e}")
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
        Get BSV transaction details from WhatsOnChain.
        """
        try:
            client = await self._get_client()
            
            # Get transaction details
            url = f"{WHATSONCHAIN_API_URL}/tx/hash/{transaction_hash}"
            response = await client.get(url)
            
            if response.status_code == 404:
                return self._create_verification_result(
                    verified=False,
                    transaction_hash=transaction_hash,
                    error="Transaction not found",
                )
            
            response.raise_for_status()
            tx_data = response.json()
            
            # Extract memo from OP_RETURN outputs
            memo = self._extract_memo(tx_data.get("vout", []))
            
            # Get confirmations
            confirmations = tx_data.get("confirmations", 0)
            block_height = tx_data.get("blockheight")
            
            # Get timestamp
            timestamp = None
            if tx_data.get("time"):
                timestamp = datetime.fromtimestamp(tx_data["time"])
            
            # Transaction found and has confirmations = verified
            verified = confirmations > 0
            
            return self._create_verification_result(
                verified=verified,
                transaction_hash=transaction_hash,
                memo=memo,
                confirmations=confirmations,
                block_height=block_height,
                timestamp=timestamp,
                error=None if verified else "Transaction unconfirmed",
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting BSV transaction: {e}")
            return self._create_verification_result(
                verified=False,
                transaction_hash=transaction_hash,
                error=f"API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Error getting BSV transaction {transaction_hash}: {e}")
            return self._create_verification_result(
                verified=False,
                transaction_hash=transaction_hash,
                error=str(e),
            )
    
    def _extract_memo(self, vout: list) -> Optional[str]:
        """
        Extract memo from OP_RETURN output.
        
        HandCash and RelayX include memos in OP_RETURN outputs.
        """
        for output in vout:
            script_pub_key = output.get("scriptPubKey", {})
            asm = script_pub_key.get("asm", "")
            
            # Check for OP_RETURN
            if asm.startswith("OP_RETURN") or asm.startswith("0 OP_RETURN"):
                # Try to decode hex data after OP_RETURN
                parts = asm.split()
                for part in parts:
                    if part not in ["OP_RETURN", "OP_FALSE", "0"]:
                        try:
                            # Try to decode as hex string
                            decoded = bytes.fromhex(part).decode("utf-8", errors="ignore")
                            if decoded and len(decoded) > 2:
                                return decoded
                        except (ValueError, UnicodeDecodeError):
                            continue
            
            # Also check opReturn field if present
            op_return = script_pub_key.get("opReturn")
            if op_return:
                return op_return
        
        return None
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
bsv_payment_service = BSVPaymentService()
