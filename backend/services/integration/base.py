# backend/services/integration/base.py

"""
Abstract Base Class for E-commerce Integrations

Defines the interface that all e-commerce platform services must implement.
This enables a unified API for Shopify, WooCommerce, and future platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


# ==================== Enums ====================

class PriceUpdateResult(str, Enum):
    """Result of a price update operation"""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    PRODUCT_NOT_FOUND = "product_not_found"
    UNAUTHORIZED = "unauthorized"


class ConnectionStatus(str, Enum):
    """Health check status for platform connection"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


# ==================== Data Classes ====================

@dataclass
class OAuthResult:
    """Result of OAuth token exchange"""
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExternalProductVariant:
    """A product variant from external platform"""
    id: str
    title: str
    price: Optional[float] = None
    sku: Optional[str] = None
    inventory_quantity: Optional[int] = None
    compare_at_price: Optional[float] = None


@dataclass
class ExternalProduct:
    """Normalized product data from any e-commerce platform"""
    id: str
    title: str
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    inventory_quantity: Optional[int] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    variants: Optional[List[ExternalProductVariant]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProductSyncResult:
    """Result of fetching products from platform"""
    success: bool
    products: Optional[List[ExternalProduct]] = None
    has_more: bool = False
    next_cursor: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PriceUpdateRequest:
    """Request to update a product's price"""
    external_product_id: str
    external_variant_id: Optional[str] = None
    new_price: float = 0.0
    compare_at_price: Optional[float] = None


@dataclass
class PriceUpdateResponse:
    """Response from price update operation"""
    result: PriceUpdateResult
    external_product_id: str
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    error: Optional[str] = None


@dataclass
class WebhookRegistration:
    """Result of webhook registration"""
    success: bool
    webhook_id: Optional[str] = None
    topic: Optional[str] = None
    error: Optional[str] = None


# ==================== Abstract Base Class ====================

class EcommerceService(ABC):
    """
    Abstract base class for e-commerce platform integrations.
    
    All platform-specific services (Shopify, WooCommerce, etc.) must
    implement this interface to ensure consistent behavior.
    """
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'shopify', 'woocommerce')"""
        pass
    
    # ========== OAuth / Authentication ==========
    
    @abstractmethod
    def generate_oauth_url(
        self,
        store_url: str,
        state: str,
        redirect_uri: str
    ) -> str:
        """
        Generate the OAuth authorization URL for the platform.
        
        Args:
            store_url: The merchant's store URL
            state: CSRF protection token
            redirect_uri: Where to redirect after authorization
            
        Returns:
            The full authorization URL to redirect the user to
        """
        pass
    
    @abstractmethod
    async def exchange_oauth_code(
        self,
        store_url: str,
        code: str,
        redirect_uri: str
    ) -> OAuthResult:
        """
        Exchange authorization code for access token.
        
        Args:
            store_url: The merchant's store URL
            code: The authorization code from OAuth callback
            redirect_uri: The redirect URI used in authorization
            
        Returns:
            OAuthResult with tokens or error
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(
        self,
        store_url: str,
        refresh_token: str
    ) -> OAuthResult:
        """
        Refresh an expired access token.
        
        Args:
            store_url: The merchant's store URL
            refresh_token: The refresh token
            
        Returns:
            OAuthResult with new tokens or error
        """
        pass
    
    @abstractmethod
    async def verify_credentials(
        self,
        store_url: str,
        access_token: str
    ) -> bool:
        """
        Verify that credentials are valid.
        
        Args:
            store_url: The merchant's store URL
            access_token: The access token to verify
            
        Returns:
            True if credentials are valid
        """
        pass
    
    # ========== Product Operations ==========
    
    @abstractmethod
    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> ProductSyncResult:
        """
        Fetch products from the platform.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            cursor: Pagination cursor for next page
            limit: Maximum products to fetch
            
        Returns:
            ProductSyncResult with products and pagination info
        """
        pass
    
    @abstractmethod
    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str
    ) -> Optional[ExternalProduct]:
        """
        Fetch a single product by its external ID.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            external_product_id: The product ID on the platform
            
        Returns:
            ExternalProduct or None if not found
        """
        pass
    
    @abstractmethod
    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest
    ) -> PriceUpdateResponse:
        """
        Update a product's price on the platform.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            request: Price update details
            
        Returns:
            PriceUpdateResponse with result
        """
        pass
    
    async def bulk_update_prices(
        self,
        store_url: str,
        access_token: str,
        requests: List[PriceUpdateRequest]
    ) -> List[PriceUpdateResponse]:
        """
        Update multiple product prices. Default implementation
        calls update_price for each request.
        
        Subclasses can override for platform-specific bulk APIs.
        """
        results = []
        for request in requests:
            result = await self.update_price(store_url, access_token, request)
            results.append(result)
        return results
    
    # ========== Webhooks ==========
    
    @abstractmethod
    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str
    ) -> List[WebhookRegistration]:
        """
        Register webhooks for product events.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            callback_url: URL to receive webhook events
            
        Returns:
            List of WebhookRegistration results
        """
        pass
    
    @abstractmethod
    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str]
    ) -> bool:
        """
        Unregister webhooks by ID.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            webhook_ids: IDs of webhooks to remove
            
        Returns:
            True if all webhooks were removed successfully
        """
        pass
    
    @abstractmethod
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify a webhook payload signature.
        
        Args:
            payload: Raw webhook payload bytes
            signature: Signature from webhook headers
            secret: Webhook secret for this integration
            
        Returns:
            True if signature is valid
        """
        pass
    
    # ========== Health Check ==========
    
    @abstractmethod
    async def health_check(
        self,
        store_url: str,
        access_token: str
    ) -> ConnectionStatus:
        """
        Check the health of the platform connection.
        
        Args:
            store_url: The merchant's store URL
            access_token: Valid access token
            
        Returns:
            ConnectionStatus indicating health
        """
        pass
    
    # ========== Utility Methods ==========
    
    def normalize_store_url(self, store_url: str) -> str:
        """
        Normalize store URL to consistent format.
        Default implementation - subclasses can override.
        """
        url = store_url.strip().lower()
        url = url.rstrip("/")
        
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        return url

