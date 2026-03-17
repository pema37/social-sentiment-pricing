"""
Payment Service Base

Abstract base class defining the interface for payment verification services.
Implementations for BSV and Ethereum inherit from this.
"""

from abc import ABC, abstractmethod

from schemas.payment import TransactionVerification


class PaymentVerificationService(ABC):
    """
    Abstract base class for blockchain payment verification.

    Each blockchain network (BSV, Ethereum) implements this interface
    to provide consistent verification across different networks.
    """

    @property
    @abstractmethod
    def network_name(self) -> str:
        """Return the network name (e.g., 'bsv', 'ethereum')."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the service is properly configured and available."""
        pass

    @abstractmethod
    async def verify_transaction(
        self,
        transaction_hash: str,
        expected_amount: int,
        expected_recipient: str,
        expected_memo: str | None = None,
    ) -> TransactionVerification:
        """
        Verify a blockchain transaction.

        Args:
            transaction_hash: The transaction ID/hash to verify
            expected_amount: Expected amount in smallest unit (satoshis/wei)
            expected_recipient: Expected recipient address
            expected_memo: Optional memo/reference to match

        Returns:
            TransactionVerification with verification results
        """
        pass

    @abstractmethod
    async def get_transaction_status(
        self,
        transaction_hash: str,
    ) -> TransactionVerification:
        """
        Get the current status of a transaction without verification.

        Args:
            transaction_hash: The transaction ID/hash to check

        Returns:
            TransactionVerification with transaction details
        """
        pass

    def _create_verification_result(
        self, verified: bool, transaction_hash: str, error: str | None = None, **kwargs
    ) -> TransactionVerification:
        """Helper to create consistent verification results."""
        return TransactionVerification(
            verified=verified, transaction_hash=transaction_hash, network=self.network_name, error=error, **kwargs
        )


class PaymentServiceFactory:
    """
    Factory for creating payment verification services.

    Usage:
        factory = PaymentServiceFactory()
        service = factory.get_service("ethereum")
        result = await service.verify_transaction(...)
    """

    _services: dict = {}

    @classmethod
    def register(cls, network: str, service: PaymentVerificationService):
        """Register a payment service for a network."""
        cls._services[network.lower()] = service

    @classmethod
    def get_service(cls, network: str) -> PaymentVerificationService | None:
        """Get the payment service for a network."""
        return cls._services.get(network.lower())

    @classmethod
    def get_available_networks(cls) -> list:
        """Get list of available networks."""
        return [name for name, service in cls._services.items() if service.is_available]

    @classmethod
    def is_network_supported(cls, network: str) -> bool:
        """Check if a network is supported."""
        service = cls._services.get(network.lower())
        return service is not None and service.is_available
