# backend/services/integration/woocommerce_service.py

"""
WooCommerce Integration Service

Uses WooCommerce REST API with consumer key/secret authentication.
Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/
"""

import hmac
import hashlib
import base64
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin

import httpx

from backend.services.integration.base import (
    EcommerceService,
    OAuthResult,
    ExternalProduct,
    ExternalProductVariant,
    ProductSyncResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    PriceUpdateResult,
    WebhookRegistration,
    ConnectionStatus,
)


class WooCommerceService(EcommerceService):
    """
    WooCommerce REST API integration.
    
    Unlike Shopify, WooCommerce uses API keys (consumer key/secret)
    rather than OAuth. Keys are generated in WooCommerce admin.
    """
    
    API_VERSION = "wc/v3"
    
    @property
    def platform_name(self) -> str:
        return "woocommerce"
    
    # ========== Authentication ==========
    # WooCommerce uses consumer key/secret, not OAuth
    
    def generate_oauth_url(
        self,
        store_url: str,
        state: str,
        redirect_uri: str
    ) -> str:
        """
        WooCommerce doesn't use OAuth flow.
        Users generate API keys in WooCommerce admin.
        Return instructions URL instead.
        """
        base_url = self.normalize_store_url(store_url)
        # Direct to WooCommerce REST API settings page
        return f"{base_url}/wp-admin/admin.php?page=wc-settings&tab=advanced&section=keys"
    
    async def exchange_oauth_code(
        self,
        store_url: str,
        code: str,
        redirect_uri: str
    ) -> OAuthResult:
        """
        WooCommerce doesn't use OAuth code exchange.
        Consumer key/secret are entered directly.
        """
        return OAuthResult(
            success=False,
            error="WooCommerce uses API keys, not OAuth. Enter consumer key/secret directly."
        )
    
    async def refresh_access_token(
        self,
        store_url: str,
        refresh_token: str
    ) -> OAuthResult:
        """WooCommerce API keys don't expire."""
        return OAuthResult(
            success=False,
            error="WooCommerce API keys don't expire or refresh."
        )
    
    async def verify_credentials(
        self,
        store_url: str,
        access_token: str,  # Format: "consumer_key:consumer_secret"
    ) -> bool:
        """Verify API keys by fetching store info."""
        try:
            base_url = self.normalize_store_url(store_url)
            consumer_key, consumer_secret = self._parse_credentials(access_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/system_status",
                    auth=(consumer_key, consumer_secret),
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception:
            return False
    
    # ========== Product Operations ==========
    
    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 100
    ) -> ProductSyncResult:
        """Fetch products from WooCommerce."""
        try:
            base_url = self.normalize_store_url(store_url)
            consumer_key, consumer_secret = self._parse_credentials(access_token)
            
            # WooCommerce uses page-based pagination
            page = int(cursor) if cursor else 1
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/products",
                    auth=(consumer_key, consumer_secret),
                    params={
                        "per_page": min(limit, 100),
                        "page": page,
                        "status": "publish"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 401:
                    return ProductSyncResult(success=False, error="Unauthorized")
                
                response.raise_for_status()
                products_data = response.json()
                
                # Check for more pages
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                has_more = page < total_pages
                next_cursor = str(page + 1) if has_more else None
                
                products = [self._parse_product(p) for p in products_data]
                
                return ProductSyncResult(
                    success=True,
                    products=products,
                    has_more=has_more,
                    next_cursor=next_cursor
                )
                
        except httpx.RequestError as e:
            return ProductSyncResult(success=False, error=str(e))
    
    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str
    ) -> Optional[ExternalProduct]:
        """Fetch a single product by ID."""
        try:
            base_url = self.normalize_store_url(store_url)
            consumer_key, consumer_secret = self._parse_credentials(access_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/products/{external_product_id}",
                    auth=(consumer_key, consumer_secret),
                    timeout=10.0
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                return self._parse_product(response.json())
                
        except httpx.RequestError:
            return None
    
    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest
    ) -> PriceUpdateResponse:
        """Update product price in WooCommerce."""
        try:
            base_url = self.normalize_store_url(store_url)
            consumer_key, consumer_secret = self._parse_credentials(access_token)
            
            # Get current price first
            current_product = await self.fetch_single_product(
                store_url, access_token, request.external_product_id
            )
            old_price = current_product.price if current_product else None
            
            # Determine endpoint (product or variation)
            if request.external_variant_id:
                url = f"{base_url}/wp-json/{self.API_VERSION}/products/{request.external_product_id}/variations/{request.external_variant_id}"
            else:
                url = f"{base_url}/wp-json/{self.API_VERSION}/products/{request.external_product_id}"
            
            # Build update payload
            update_data = {
                "regular_price": str(request.new_price)
            }
            if request.compare_at_price:
                update_data["sale_price"] = str(request.new_price)
                update_data["regular_price"] = str(request.compare_at_price)
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    url,
                    auth=(consumer_key, consumer_secret),
                    json=update_data,
                    timeout=10.0
                )
                
                if response.status_code == 401:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.UNAUTHORIZED,
                        external_product_id=request.external_product_id,
                        error="Invalid API credentials"
                    )
                
                if response.status_code == 404:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="Product not found"
                    )
                
                response.raise_for_status()
                
                return PriceUpdateResponse(
                    result=PriceUpdateResult.SUCCESS,
                    external_product_id=request.external_product_id,
                    old_price=old_price,
                    new_price=request.new_price
                )
                
        except httpx.RequestError as e:
            return PriceUpdateResponse(
                result=PriceUpdateResult.FAILED,
                external_product_id=request.external_product_id,
                error=str(e)
            )
    
    # ========== Webhooks ==========
    
    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str
    ) -> List[WebhookRegistration]:
        """Register webhooks for product updates."""
        base_url = self.normalize_store_url(store_url)
        consumer_key, consumer_secret = self._parse_credentials(access_token)
        
        topics = [
            ("product.created", "Product created"),
            ("product.updated", "Product updated"),
            ("product.deleted", "Product deleted"),
        ]
        
        results = []
        
        async with httpx.AsyncClient() as client:
            for topic, name in topics:
                try:
                    response = await client.post(
                        f"{base_url}/wp-json/{self.API_VERSION}/webhooks",
                        auth=(consumer_key, consumer_secret),
                        json={
                            "name": f"SSP - {name}",
                            "topic": topic,
                            "delivery_url": callback_url,
                            "status": "active"
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code in (200, 201):
                        data = response.json()
                        results.append(WebhookRegistration(
                            success=True,
                            webhook_id=str(data.get("id")),
                            topic=topic
                        ))
                    else:
                        results.append(WebhookRegistration(
                            success=False,
                            topic=topic,
                            error=f"HTTP {response.status_code}"
                        ))
                        
                except httpx.RequestError as e:
                    results.append(WebhookRegistration(
                        success=False,
                        topic=topic,
                        error=str(e)
                    ))
        
        return results
    
    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str]
    ) -> bool:
        """Remove registered webhooks."""
        base_url = self.normalize_store_url(store_url)
        consumer_key, consumer_secret = self._parse_credentials(access_token)
        
        success = True
        
        async with httpx.AsyncClient() as client:
            for webhook_id in webhook_ids:
                try:
                    response = await client.delete(
                        f"{base_url}/wp-json/{self.API_VERSION}/webhooks/{webhook_id}",
                        auth=(consumer_key, consumer_secret),
                        params={"force": "true"},
                        timeout=10.0
                    )
                    if response.status_code not in (200, 204):
                        success = False
                except httpx.RequestError:
                    success = False
        
        return success
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify WooCommerce webhook signature.
        WooCommerce sends signature in X-WC-Webhook-Signature header.
        """
        expected = base64.b64encode(
            hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).digest()
        ).decode()
        
        return hmac.compare_digest(signature, expected)
    
    # ========== Health Check ==========
    
    async def health_check(
        self,
        store_url: str,
        access_token: str
    ) -> ConnectionStatus:
        """Check WooCommerce connection health."""
        try:
            base_url = self.normalize_store_url(store_url)
            consumer_key, consumer_secret = self._parse_credentials(access_token)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/wp-json/{self.API_VERSION}/system_status",
                    auth=(consumer_key, consumer_secret),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return ConnectionStatus.HEALTHY
                elif response.status_code == 401:
                    return ConnectionStatus.UNAUTHORIZED
                elif response.status_code == 429:
                    return ConnectionStatus.RATE_LIMITED
                else:
                    return ConnectionStatus.UNHEALTHY
                    
        except httpx.RequestError:
            return ConnectionStatus.UNHEALTHY
    
    # ========== Helper Methods ==========
    
    def _parse_credentials(self, access_token: str) -> tuple[str, str]:
        """
        Parse consumer key and secret from stored token.
        Format: "consumer_key:consumer_secret"
        """
        if ":" in access_token:
            parts = access_token.split(":", 1)
            return parts[0], parts[1]
        raise ValueError("Invalid WooCommerce credentials format")
    
    def _parse_product(self, data: dict) -> ExternalProduct:
        """Convert WooCommerce product JSON to ExternalProduct."""
        # Parse variants (variations in WooCommerce)
        variants = []
        for var in data.get("variations", []):
            variants.append(ExternalProductVariant(
                id=str(var.get("id")),
                title=var.get("attributes", [{}])[0].get("option", ""),
                price=float(var.get("price", 0)) if var.get("price") else None,
                sku=var.get("sku"),
                inventory_quantity=var.get("stock_quantity"),
                compare_at_price=float(var.get("regular_price", 0)) if var.get("regular_price") and var.get("sale_price") else None
            ))
        
        # Get images
        images = [img.get("src") for img in data.get("images", []) if img.get("src")]
        
        # Parse price (sale_price takes precedence if set)
        price = None
        compare_at_price = None
        if data.get("sale_price"):
            price = float(data["sale_price"])
            compare_at_price = float(data.get("regular_price", 0)) if data.get("regular_price") else None
        elif data.get("price"):
            price = float(data["price"])
        
        return ExternalProduct(
            id=str(data.get("id")),
            title=data.get("name", ""),
            price=price,
            compare_at_price=compare_at_price,
            sku=data.get("sku"),
            description=data.get("description", ""),
            inventory_quantity=data.get("stock_quantity"),
            product_type=data.get("type", "simple"),
            vendor="",  # WooCommerce doesn't have vendor field
            tags=[tag.get("name") for tag in data.get("tags", [])],
            images=images,
            variants=variants if variants else None,
            created_at=self._parse_datetime(data.get("date_created")),
            updated_at=self._parse_datetime(data.get("date_modified"))
        )
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse WooCommerce datetime string."""
        if not date_str:
            return None
        try:
            # WooCommerce format: 2024-01-15T10:30:00
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    def normalize_store_url(self, store_url: str) -> str:
        """Normalize WooCommerce store URL."""
        url = store_url.strip().lower()
        
        # Remove trailing slash
        url = url.rstrip("/")
        
        # Add https if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        return url

